# scheduling/notifications.py

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
# --- FIX: Import EmailMultiAlternatives ---
from django.core.mail import send_mail, EmailMultiAlternatives
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.contrib.auth import get_user_model

from collections import defaultdict

import datetime
from datetime import timedelta

from .models import AttendanceTracking, SessionCoach
from players.models import Player

from django.db.models import Prefetch


# It's good practice to have your models imported directly
from .models import Session, CoachAvailability, SessionCoach
# Import the Payslip model
from finance.models import Payslip


# Salt can be customized for better security between apps
confirmation_signer = TimestampSigner(salt='scheduling.confirmation')
bulk_confirmation_signer = TimestampSigner(salt='scheduling.bulk_confirmation')
User = get_user_model()


def create_confirmation_token(user_id, session_id):
    """Creates a signed, timestamped token for a user and session."""
    value = f"{user_id}:{session_id}"
    return confirmation_signer.sign(value)

def verify_confirmation_token(token, max_age_days=7):
    """Verifies a token. Returns the original value or None if invalid/expired."""
    try:
        # Use timedelta for max_age as it's more robust
        return confirmation_signer.unsign(token, max_age=timedelta(days=max_age_days))
    except (BadSignature, SignatureExpired):
        return None

def create_bulk_confirmation_token(user_id, date_obj):
    """Creates a signed, timestamped token for a user and a specific date."""
    date_str = date_obj.strftime('%Y-%m-%d')
    value = f"{user_id}:{date_str}"
    return bulk_confirmation_signer.sign(value)

def verify_bulk_confirmation_token(token, max_age_days=2):
    """Verifies a bulk token. Returns the original value or None if invalid/expired."""
    try:
        return bulk_confirmation_signer.unsign(token, max_age=timedelta(days=max_age_days))
    except (BadSignature, SignatureExpired):
        return None

def send_consolidated_session_reminder_email(user, sessions_by_day, is_reminder=False):
    """
    Sends a single reminder email with ALL assigned sessions for the upcoming days,
    showing their current confirmation status.
    """
    if not user.email:
        print(f"Cannot send email: User {user.username} has no email address.")
        return False

    site_url = getattr(settings, 'APP_SITE_URL', 'http://127.0.0.1:8000')
    subject_verb = "Reminder" if is_reminder else "Confirmation Required"

    # Get all days included in the initial (unresponded) list
    relevant_dates = sorted(list(sessions_by_day.keys())) # Ensure consistent order

    if not relevant_dates:
        print(f"No relevant dates found for reminder email to {user.username}.")
        return False # Should not happen based on trigger script, but safety check

    # --- NEW: Re-query ALL assigned sessions for these specific days ---
    all_assigned_sessions_for_days = Session.objects.filter(
        coaches_attending__user=user,
        session_date__in=relevant_dates,
        is_cancelled=False
    ).select_related('school_group', 'venue').prefetch_related(
        # Prefetch the specific coach's availability status
        Prefetch(
            'coach_availabilities',
            queryset=CoachAvailability.objects.filter(coach=user),
            to_attr='my_availability'
        ),
        # Prefetch the SessionCoach entry to get duration
        Prefetch(
            'sessioncoach_set',
            queryset=SessionCoach.objects.filter(coach__user=user),
            to_attr='my_session_coach_assignment'
        )
    ).order_by('session_date', 'session_start_time')

    # --- NEW: Group ALL fetched sessions by day ---
    all_sessions_grouped_by_day = defaultdict(list)
    for session in all_assigned_sessions_for_days:
        all_sessions_grouped_by_day[session.session_date].append(session)

    # Generate a subject that covers all relevant days
    day_names = [day.strftime('%a, %d %b') for day in relevant_dates]
    subject_days = " & ".join(day_names)
    subject = f"Upcoming Session {subject_verb} for {subject_days}"

    context = {
        'coach_name': user.first_name or user.username,
        'sessions_by_day': {}, # This will be rebuilt below
        'is_reminder': is_reminder,
        'site_name': getattr(settings, 'SITE_NAME', 'SquashSync'),
    }

    # --- NEW: Build context using ALL sessions for the days ---
    for day in relevant_dates:
        sessions_for_this_day = all_sessions_grouped_by_day.get(day, [])
        if not sessions_for_this_day:
            continue # Skip if somehow no sessions were found for this day

        session_details_with_status = []
        for session in sessions_for_this_day:
            # Determine current status
            availability = session.my_availability[0] if session.my_availability else None
            status = "Pending"
            if availability:
                if availability.status == CoachAvailability.Status.UNAVAILABLE:
                    status = "Declined"
                elif availability.last_action == 'CONFIRM':
                    status = "Confirmed"

            # Get duration
            assignment = session.my_session_coach_assignment[0] if session.my_session_coach_assignment else None
            duration = assignment.coaching_duration_minutes if assignment else session.planned_duration_minutes

            session_details_with_status.append({
                'session_obj': session,
                'duration': duration,
                'status': status, # Add the current status
                'is_head_coach': getattr(session.get_head_coach(), 'user', None) == user,
            })

        # Generate bulk action tokens (remain the same)
        token = create_bulk_confirmation_token(user.id, day)
        date_str = day.strftime('%Y-%m-%d')
        context['sessions_by_day'][day] = {
            'sessions': session_details_with_status, # Use the new list with statuses
            'confirm_url': site_url + reverse('scheduling:confirm_all_for_day', args=[date_str, token]),
            'decline_url': site_url + reverse('scheduling:decline_all_for_day_reason', args=[date_str, token]),
        }

    html_message = render_to_string('scheduling/emails/consolidated_session_reminder.html', context)

    try:
        send_mail(subject, '', settings.DEFAULT_FROM_EMAIL, [user.email], html_message=html_message)
        print(f"Sent consolidated reminder (showing all sessions) to {user.email}.")
        return True
    except Exception as e:
        print(f"Error sending consolidated reminder to {user.email}: {e}")
        return False

# --- THIS IS THE UPDATED FUNCTION ---

def send_payslip_email(payslip: Payslip):
    """
    Sends a single payslip email with the PDF attachment to the coach.
    """
    if not payslip.coach.user or not payslip.coach.user.email:
        print(f"Cannot send payslip: Coach {payslip.coach.name} has no user or no email.")
        return False
    
    coach_user = payslip.coach.user
    coach_name = coach_user.first_name or coach_user.username
    period_date = datetime.date(payslip.year, payslip.month, 1)
    period = period_date.strftime('%B %Y')
    
    subject = f"Your SquashSync Payslip for {period}"
    
    context = {
        'coach_name': coach_name,
        'period': period,
    }
    
    body = render_to_string('finance/emails/payslip_email.txt', context)
    html_message = render_to_string('finance/emails/payslip_email.html', context)
    
    try:
        # --- FIX: Use EmailMultiAlternatives ---
        email = EmailMultiAlternatives(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [coach_user.email]
        )
        # --- END OF FIX ---

        email.attach_alternative(html_message, "text/html")
        
        # Attach the PDF
        if payslip.file:
            payslip.file.open('rb') # Re-open the file
            content = payslip.file.read()
            payslip.file.close()
            email.attach(payslip.filename, content, 'application/pdf')
        else:
            print(f"Could not send payslip {payslip.id}: File not found.")
            return False

        email.send()
        print(f"Successfully sent payslip for {period} to {coach_user.email}.")
        return True
        
    except Exception as e:
        print(f"Error sending payslip email to {coach_user.email}: {e}")
        return False

# --- END OF UPDATED FUNCTION ---


def send_coach_decline_notification_email(declining_coach, session, reason):
    """
    Sends a notification to all superusers when a coach declines a session.
    """
    superusers = User.objects.filter(is_superuser=True, is_active=True)
    recipient_list = [user.email for user in superusers if user.email]

    if not recipient_list:
        print("Admin notification not sent: No superusers with email addresses found.")
        return False

    site_url = getattr(settings, 'APP_SITE_URL', 'http://127.0.0.1:8000')
    staffing_url = site_url + reverse('scheduling:session_staffing')
    subject = f"ALERT: Coach Declined Session for {session.session_date.strftime('%a, %d %b')}"

    context = {
        'declining_coach_name': declining_coach.get_full_name() or declining_coach.username,
        'session_date': session.session_date.strftime('%A, %d %b %Y'),
        'session_time': session.session_start_time.strftime('%H:%M'),
        'session_group': session.school_group.name if session.school_group else "N/A",
        'reason': reason,
        'staffing_url': staffing_url,
        'site_name': getattr(settings, 'SITE_NAME', 'SquashSync'),
    }
    
    html_message = render_to_string('scheduling/emails/admin_decline_notification.html', context)

    try:
        send_mail(subject, '', settings.DEFAULT_FROM_EMAIL, recipient_list, html_message=html_message)
        print(f"Sent decline notification to {len(recipient_list)} admin(s) for session {session.id}.")
        return True
    except Exception as e:
        print(f"Error sending admin decline notification: {e}")
        return False

# Your views seem correct but ensure they are in a `views.py` file within the `scheduling` app
# and that your urls.py is configured to point to them.

@login_required
def confirm_attendance(request, session_id, token):
    payload = verify_confirmation_token(token)
    # The user check should be against the ID from the token, not request.user.id directly for security
    user_id_from_token = int(payload.split(':')[0])
    
    if not payload or user_id_from_token != request.user.id:
        messages.error(request, "Invalid or expired confirmation link.")
        return redirect('homepage') # Make sure you have a URL named 'homepage'

    session = get_object_or_404(Session, pk=session_id)
    CoachAvailability.objects.update_or_create(
        coach=request.user, session=session,
        defaults={'is_available': True, 'last_action': 'CONFIRM', 'status_updated_at': timezone.now()}
    )
    messages.success(request, f"Thank you for confirming your attendance for the session on {session.session_date}.")
    return redirect('homepage')

@login_required
def decline_attendance(request, session_id, token):
    payload = verify_confirmation_token(token)
    user_id_from_token = int(payload.split(':')[0])

    if not payload or user_id_from_token != request.user.id:
        messages.error(request, "Invalid or expired decline link.")
        return redirect('homepage')
        
    session = get_object_or_404(Session, pk=session_id)
    CoachAvailability.objects.update_or_create(
        coach=request.user, session=session,
        defaults={'is_available': False, 'last_action': 'DECLINE', 'status_updated_at': timezone.now(), 'notes': 'Declined via email link.'}
    )
    messages.warning(request, f"You have declined attendance for the session on {session.session_date}.")
    return redirect('homepage')

#PLayer attendance logic

player_attendance_signer = TimestampSigner(salt='scheduling.player_attendance')

def build_player_attendance_email(player, session):
    """
    Builds the player attendance email object but does not send it.
    Returns an EmailMultiAlternatives object or None if no notification email.
    """
    if not player.notification_email:
        print(f"Cannot build email: Player {player.full_name} has no notification email.")
        return None

    tracking_record, _ = AttendanceTracking.objects.get_or_create(session=session, player=player)

    token_attend = player_attendance_signer.sign(f"{tracking_record.id}:ATTENDING")
    token_decline = player_attendance_signer.sign(f"{tracking_record.id}:NOT_ATTENDING")

    site_url = getattr(settings, 'APP_SITE_URL', 'http://127.0.0.1:8000')
    url_attend = site_url + reverse('scheduling:player_attendance_response', args=[token_attend])
    url_decline = site_url + reverse('scheduling:player_attendance_response', args=[token_decline])

    subject = f"Squash Session Reminder for {player.first_name} - {session.session_date.strftime('%A, %d %b')}"

    context = {
        'player': player,
        'session': session,
        'url_attend': url_attend,
        'url_decline': url_decline,
        'site_name': getattr(settings, 'SITE_NAME', 'SquashSync'),
    }
    
    html_message = render_to_string('scheduling/emails/player_attendance_reminder.html', context)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body='', # Plain text body if you had one
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[player.notification_email]
    )
    email.attach_alternative(html_message, "text/html")
    
    return email

def send_player_attendance_email(player, session):
    """Sends an attendance reminder email to a player's verified notification email."""
    email = build_player_attendance_email(player, session)
    
    if not email:
        return False
        
    try:
        email.send()
        print(f"Sent player attendance reminder to {player.full_name} ({player.notification_email}).")
        return True
    except Exception as e:
        print(f"Error sending player attendance reminder for {player.full_name}: {e}")
        return False
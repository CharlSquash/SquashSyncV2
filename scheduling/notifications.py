# scheduling/notifications.py

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.contrib.auth import get_user_model

import datetime
from datetime import timedelta

from .models import AttendanceTracking
from players.models import Player




# It's good practice to have your models imported directly
from .models import Session, CoachAvailability

# Salt can be customized for better security between apps
confirmation_signer = TimestampSigner(salt='scheduling.confirmation')
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

def send_session_confirmation_email(user, session, is_reminder=False):
    """Sends a confirmation email to a coach for a specific session."""
    if not user.email:
        print(f"Cannot send email: User {user.username} has no email address.")
        return False

    token = create_confirmation_token(user.id, session.id)
    # Fallback to a default site_url if APP_SITE_URL is not set
    site_url = getattr(settings, 'APP_SITE_URL', 'http://127.0.0.1:8000')

    # Ensure you are using the correct namespace for your urls
    confirm_url = site_url + reverse('scheduling:confirm_attendance', args=[session.id, token])
    decline_url = site_url + reverse('scheduling:decline_attendance_reason', args=[session.id, token])
    
    subject_verb = "Reminder" if is_reminder else "Confirmation Required"
    subject = f"Session {subject_verb}: {session.school_group.name} on {session.session_date.strftime('%a, %d %b')}"
    
    context = {
        'coach_name': user.first_name or user.username,
        'session_date': session.session_date.strftime('%A, %d B %Y'),
        'session_time': session.session_start_time.strftime('%H:%M'),
        'session_group': session.school_group.name if session.school_group else "N/A",
        'session_venue': session.venue.name if session.venue else "N/A",
        'confirm_url': confirm_url,
        'decline_url': decline_url,
        'is_reminder': is_reminder,
        'site_name': getattr(settings, 'SITE_NAME', 'SquashSync'),
    }
    # This is the line that was causing the error
    html_message = render_to_string('scheduling/emails/session_confirmation_email.html', context)
    
    try:
        send_mail(subject, '', settings.DEFAULT_FROM_EMAIL, [user.email], html_message=html_message)
        print(f"Sent confirmation email to {user.email} for session {session.id}.")
        return True
    except Exception as e:
        print(f"Error sending confirmation email to {user.email}: {e}")
        return False

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
        'session_date': session.session_date.strftime('%A, %d B %Y'),
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

def send_player_attendance_email(player, session):
    """Sends an attendance reminder email to a player's parent."""
    if not player.parent_email:
        print(f"Cannot send email: Player {player.full_name} has no parent email.")
        return False

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
    
    try:
        send_mail(subject, '', settings.DEFAULT_FROM_EMAIL, [player.parent_email], html_message=html_message)
        print(f"Sent player attendance reminder to parent of {player.full_name}.")
        return True
    except Exception as e:
        print(f"Error sending player attendance reminder for {player.full_name}: {e}")
        return False
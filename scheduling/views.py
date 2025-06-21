# scheduling/views.py

# --- Start: Replace your existing imports with this block ---
import json
from datetime import timedelta

from collections import defaultdict

from django.core.signing import BadSignature, SignatureExpired
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.db.models import Prefetch

from django.contrib.auth import get_user_model

import calendar
from .utils import get_month_start_end # We will create this helper function next
from .forms import MonthYearFilterForm

# Import models from their new app locations
from .models import Session, TimeBlock, ActivityAssignment, CoachAvailability, Venue, ScheduledClass, AttendanceTracking
from .forms import SessionForm, SessionFilterForm, CoachAvailabilityForm, AttendanceForm
from players.models import Player, SchoolGroup
from . import notifications
from .notifications import verify_confirmation_token
from accounts.models import Coach
from assessments.models import SessionAssessment, GroupAssessment
# --- End: Replacement block ---
User = get_user_model()


@login_required
def homepage(request):
    # We'll keep the logic simple for now and can add the full context later
    today = timezone.now().date()

    # Get upcoming sessions for the logged-in coach
    upcoming_sessions = Session.objects.filter(
        coaches_attending__user=request.user,
        session_date__gte=today
    ).order_by('session_date', 'session_start_time')[:5]

    context = {
        'upcoming_sessions': upcoming_sessions,
        # We will add the other context variables (pending assessments, etc.)
        # in a later step once we have ported those views.
    }

    # Render the homepage template from its new location
    return render(request, 'scheduling/homepage.html', context)

@login_required
def session_detail(request, session_id):
    session = get_object_or_404(
        Session.objects.select_related('school_group').prefetch_related('player_attendances__player'), 
        pk=session_id
    )

    if request.method == 'POST':
        # Process the submitted attendance form
        for key, value in request.POST.items():
            if key.startswith('status_'):
                player_id = int(key.split('_')[1])
                new_status = value
                
                # Update or create the attendance record for the player
                if new_status in AttendanceTracking.Status.values:
                    AttendanceTracking.objects.update_or_create(
                        session=session,
                        player_id=player_id,
                        defaults={'status': new_status}
                    )
        messages.success(request, "Attendance statuses have been updated.")
        return redirect('scheduling:session_detail', session_id=session.id)

    # For GET request, prepare data for the template
    attendance_status_map = {
        att.player_id: att.status for att in session.player_attendances.all()
    }
    
    players = session.school_group.players.all().order_by('first_name') if session.school_group else []

    context = {
        'session': session,
        'players': players,
        'attendance_status_map': attendance_status_map,
    }
    return render(request, 'scheduling/session_detail.html', context)

@login_required
def visual_attendance(request, session_id):
    session = get_object_or_404(Session.objects.select_related('school_group'), pk=session_id)
    
    if not session.school_group:
        messages.error(request, "This session is not linked to a school group.")
        return redirect('scheduling:session_list') # Or wherever is appropriate

    players_in_group = session.school_group.players.all().order_by('first_name')

    if request.method == 'POST':
        # This part handles the submission from the coach
        attending_player_ids = request.POST.getlist('attendees')
        
        for player in players_in_group:
            status = 'ATTENDING' if str(player.id) in attending_player_ids else 'NOT_ATTENDING'
            AttendanceTracking.objects.update_or_create(
                session=session,
                player=player,
                defaults={'status': status}
            )
        
        messages.success(request, "Final attendance has been recorded.")
        return redirect('scheduling:session_detail', session_id=session.id)

    # --- This is the key part for displaying the page initially ---
    # Get IDs of players whose parents have already confirmed 'ATTENDING'
    confirmed_attending_ids = set(
        AttendanceTracking.objects.filter(
            session=session,
            status=AttendanceTracking.Status.ATTENDING
        ).values_list('player_id', flat=True)
    )

    # Build the list in the format your template expects
    player_list = []
    for player in players_in_group:
        player_list.append({
            'player': player,
            # Pre-select the player if their ID is in the confirmed set
            'is_attending': player.id in confirmed_attending_ids
        })

    context = {
        'session': session,
        'school_group': session.school_group,
        'player_list': player_list,
        'page_title': "Take Attendance"
    }
    return render(request, 'scheduling/visual_attendance.html', context)


# Replace the existing session_calendar view in scheduling/views.py with this cleaner version

@login_required
def session_calendar(request):
    # --- Simplified Logic: Get sessions based on user role ---
    if request.user.is_superuser:
        # Superuser sees all sessions
        sessions = Session.objects.all()
    else:
        # Regular staff user (coach) sees only their assigned sessions
        sessions = Session.objects.filter(coaches_attending__user=request.user)

    sessions_qs = sessions.select_related('school_group', 'venue').prefetch_related('coaches_attending')
    # --- END Simplified Logic ---

    # Build the rich event data for FullCalendar
    events = []
    for session in sessions_qs:
        events.append({
            'title': session.school_group.name if session.school_group else 'General Session',
            'start': f'{session.session_date}T{session.session_start_time}',
            'id': session.id,
            'url': reverse('scheduling:session_detail', args=[session.id]),
            'extendedProps': {
                'venue_name': session.venue.name if session.venue else 'N/A',
                'coaches_attending': [coach.name for coach in session.coaches_attending.all()],
                'status_display': "Cancelled" if session.is_cancelled else "Confirmed",
                'school_group_name': session.school_group.name if session.school_group else "N/A",
                'session_time_str': session.session_start_time.strftime('%H:%M'),
                'admin_url': reverse('admin:scheduling_session_change', args=[session.id])
            },
            'classNames': ['cancelled-session'] if session.is_cancelled else []
        })

    context = {
        'page_title': "Session Calendar",
        'events_json': json.dumps(events),
    }
    return render(request, 'scheduling/session_calendar.html', context)

@login_required
def my_availability(request):
    try:
        coach_profile = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        if not request.user.is_superuser:
            messages.error(request, "Your user account is not linked to a Coach profile.")
            return redirect('homepage')
        coach_profile = None # Allow superuser to view page, though it may be empty

    # --- Handle POST request for form submission ---
    if request.method == 'POST':
        updated_count = 0
        for key, value in request.POST.items():
            if key.startswith('availability_session_'):
                session_id = key.split('_')[-1]
                notes = request.POST.get(f'notes_session_{session_id}', '').strip()

                try:
                    session = Session.objects.get(pk=session_id)
                    is_available = None
                    if value == 'AVAILABLE': is_available = True
                    elif value == 'UNAVAILABLE': is_available = False
                    
                    if value != 'NO_CHANGE':
                        CoachAvailability.objects.update_or_create(
                            coach=request.user, session=session,
                            defaults={'is_available': is_available, 'notes': notes}
                        )
                        updated_count += 1
                except Session.DoesNotExist:
                    messages.warning(request, f"Could not find session with ID {session_id}.")
        
        if updated_count > 0:
            messages.success(request, f"Successfully updated your availability for {updated_count} session(s).")
        
        # Redirect back to the same week view
        return redirect(f"{reverse('scheduling:my_availability')}?week={request.GET.get('week', '0')}")


    # --- Handle GET request to display the page ---
    now = timezone.now()
    today = now.date()
    
    try:
        week_offset = int(request.GET.get('week', '0'))
    except (ValueError, TypeError):
        week_offset = 0

    # Calculate the start and end of the target week
    start_of_this_week = today - timedelta(days=today.weekday())
    target_week_start = start_of_this_week + timedelta(weeks=week_offset)
    target_week_end = target_week_start + timedelta(days=6)

    # Fetch all sessions for the target week
    upcoming_sessions_qs = Session.objects.filter(
        session_date__gte=target_week_start,
        session_date__lte=target_week_end,
        is_cancelled=False
    ).select_related('school_group').prefetch_related(
        'coaches_attending',
        Prefetch('coach_availabilities', queryset=CoachAvailability.objects.filter(coach=request.user), to_attr='my_availability')
    ).order_by('session_date', 'session_start_time')

    # Group sessions by day of the week
    grouped_sessions = defaultdict(list)
    for session in upcoming_sessions_qs:
        availability_info = session.my_availability[0] if session.my_availability else None
        current_status = 'NO_CHANGE'
        if availability_info:
            if availability_info.is_available and "emergency" in availability_info.notes.lower():
                current_status = 'EMERGENCY'
            elif availability_info.is_available is True:
                current_status = 'AVAILABLE'
            elif availability_info.is_available is False:
                current_status = 'UNAVAILABLE'
        
        session_data = {
            'session_obj': session,
            'current_status': current_status,
            'is_assigned': coach_profile in session.coaches_attending.all() if coach_profile else False,
            'group_description': session.school_group.description if session.school_group else ""
        }
        grouped_sessions[session.session_date.weekday()].append(session_data)

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    display_week = []
    for i in range(7):
        day_date = target_week_start + timedelta(days=i)
        display_week.append({
            'day_name': day_names[i],
            'date': day_date,
            'sessions': grouped_sessions.get(i, [])
        })

    context = {
        'page_title': "My Availability",
        'display_week': display_week,
        'week_start': target_week_start,
        'week_end': target_week_end,
        'current_week_offset': week_offset,
        'next_week_offset': week_offset + 1,
        'prev_week_offset': week_offset - 1,
    }
    return render(request, 'scheduling/my_availability.html', context)

@login_required
def set_bulk_availability_view(request):
    try:
        coach_profile = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        messages.error(request, "Your user account is not linked to a Coach profile.")
        return redirect('homepage')

    if request.method == 'POST':
        selected_month = int(request.POST.get('month'))
        selected_year = int(request.POST.get('year'))
        start_date, end_date = get_month_start_end(selected_year, selected_month)
        
        rules = ScheduledClass.objects.filter(is_active=True)
        availability_updated_count = 0

        for rule in rules:
            availability_status_str = request.POST.get(f'availability_rule_{rule.id}')
            if not availability_status_str or availability_status_str == 'NO_CHANGE':
                continue

            is_available = None
            notes = ""
            if availability_status_str == 'AVAILABLE':
                is_available = True
            elif availability_status_str == 'UNAVAILABLE':
                is_available = False
            elif availability_status_str == 'EMERGENCY':
                is_available = True
                notes = "Emergency only"

            sessions_to_update = Session.objects.filter(
                generated_from_rule=rule,
                session_date__gte=start_date,
                session_date__lte=end_date,
                is_cancelled=False
            )
            
            for session in sessions_to_update:
                CoachAvailability.objects.update_or_create(
                    coach=request.user,
                    session=session,
                    defaults={
                        'is_available': is_available,
                        'notes': notes,
                    }
                )
                availability_updated_count += 1
        
        month_name = calendar.month_name[selected_month]
        messages.success(request, f"Your availability for {availability_updated_count} potential sessions in {month_name} {selected_year} has been updated.")
        return redirect(f"{reverse('scheduling:set_bulk_availability')}?year={selected_year}&month={selected_month}")

    # --- GET request handling ---
    now = timezone.now()
    selected_year = int(request.GET.get('year', now.year))
    selected_month = int(request.GET.get('month', now.month))

    month_year_form = MonthYearFilterForm(initial={'month': selected_month, 'year': selected_year})
    
    scheduled_classes_qs = ScheduledClass.objects.filter(is_active=True).select_related('school_group').order_by('day_of_week', 'start_time')
    
    grouped_classes = defaultdict(list)
    for rule in scheduled_classes_qs:
        day_name = rule.get_day_of_week_display()
        grouped_classes[day_name].append(rule)

    context = {
        'page_title': "Set Bulk Availability",
        'month_year_form': month_year_form,
        'grouped_classes': dict(grouped_classes),
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_month_display': calendar.month_name[selected_month],
    }
    return render(request, 'scheduling/set_bulk_availability.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def session_staffing(request):
    # --- POST request logic remains the same ---
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        assigned_coach_ids = request.POST.getlist(f'coaches_for_session_{session_id}')
        try:
            session = get_object_or_404(Session, pk=session_id)
            session.coaches_attending.set(assigned_coach_ids)
            messages.success(request, f"Assignments updated for session on {session.session_date.strftime('%d %b')}.")
        except (ValueError, ObjectDoesNotExist):
            messages.error(request, "Invalid session ID.")
        return redirect(f"{reverse('scheduling:session_staffing')}?week={request.GET.get('week', '0')}")

    # --- Corrected GET request logic ---
    now = timezone.now()
    today = now.date()
    
    try:
        week_offset = int(request.GET.get('week', '0'))
    except (ValueError, TypeError):
        week_offset = 0

    start_of_this_week = today - timedelta(days=today.weekday())
    target_week_start = start_of_this_week + timedelta(weeks=week_offset)
    target_week_end = target_week_start + timedelta(days=6)

    all_active_coaches = list(Coach.objects.filter(is_active=True).select_related('user').order_by('name'))
    
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    display_week = []

    for i in range(7):
        current_day = target_week_start + timedelta(days=i)
        
        sessions_for_day = Session.objects.filter(
            session_date=current_day,
            is_cancelled=False
        ).select_related('school_group', 'venue').prefetch_related(
            'coaches_attending__user',
            # CHANGE 1: Use the correct related_name in the Prefetch object
            Prefetch('coach_availabilities', queryset=CoachAvailability.objects.select_related('coach'))
        ).order_by('session_start_time')
        
        processed_sessions = []
        for session in sessions_for_day:
            # CHANGE 2: Use the correct related_name to access the prefetched data
            availability_map = {avail.coach_id: avail for avail in session.coach_availabilities.all()}
            
            assigned_coaches_status = []
            has_pending = False
            has_declined = False
            
            for coach in session.coaches_attending.all():
                if coach.user:
                    avail = availability_map.get(coach.user.id)
                    
                    if avail:
                        if avail.is_available:
                            status = "Confirmed"
                        else:
                            status = "Declined"
                            has_declined = True
                    else:
                        status = "Pending"
                        has_pending = True

                    assigned_coaches_status.append({'coach': coach, 'status': status, 'notes': avail.notes if avail else ''})

            available_coaches = []
            for coach in all_active_coaches:
                if coach not in session.coaches_attending.all() and coach.user:
                    avail = availability_map.get(coach.user.id)
                    if avail and avail.is_available:
                        available_coaches.append({
                            'coach': coach,
                            'is_emergency': "emergency" in (avail.notes or "").lower()
                        })
            
            processed_sessions.append({
                'session_obj': session,
                'assigned_coaches_with_status': assigned_coaches_status,
                'available_coaches_for_assignment': sorted(available_coaches, key=lambda x: x['is_emergency']),
                'has_pending_confirmations': has_pending,
                'has_declined_coaches': has_declined,
            })
            
        display_week.append({
            'day_name': day_names[i],
            'date': current_day,
            'sessions': processed_sessions
        })

    context = {
        'page_title': "Session Staffing",
        'all_coaches_for_form': all_active_coaches,
        'display_week': display_week,
        'week_start': target_week_start,
        'week_end': target_week_end,
        'current_week_offset': week_offset,
        'next_week_offset': week_offset + 1,
        'prev_week_offset': week_offset - 1,
    }
    return render(request, 'scheduling/session_staffing.html', context)

def confirm_attendance(request, session_id, token):
    """
    Handles attendance confirmation from an email link.
    Does not require login; authentication is handled by the token.
    """
    payload = notifications.verify_confirmation_token(token)
    
    if not payload:
        context = {
            'message_type': 'error',
            'message': 'This confirmation link is invalid or has expired. Please contact the administrator.'
        }
        return render(request, 'scheduling/confirmation_response.html', context)

    try:
        user_id, token_session_id = payload.split(':')
        user_id = int(user_id)
        
        # Security check: ensure the session_id in the token matches the one in the URL
        if int(token_session_id) != session_id:
             raise ValueError("Token-URL mismatch.")

    except (ValueError, IndexError):
        context = {
            'message_type': 'error',
            'message': 'The confirmation link is malformed. Please use the link exactly as it was provided in the email.'
        }
        return render(request, 'scheduling/confirmation_response.html', context)

    # Fetch the user and session from the database using IDs from the token/URL
    user = get_object_or_404(User, pk=user_id)
    session = get_object_or_404(Session, pk=session_id)
    
    # Update the availability record
    CoachAvailability.objects.update_or_create(
        coach=user, 
        session=session,
        defaults={
            'is_available': True, 
            'last_action': 'CONFIRM', 
            'status_updated_at': timezone.now()
        }
    )

    # Render a clear response to the user
    context = {
        'message_type': 'success',
        'message': f"Thank you, {user.first_name}! Your attendance for the session on {session.session_date.strftime('%A, %d %B')} is confirmed."
    }
    return render(request, 'scheduling/confirmation_response.html', context)


def decline_attendance(request, session_id, token):
    """
    Handles attendance decline from an email link.
    Does not require login; authentication is handled by the token.
    """
    payload = notifications.verify_confirmation_token(token)
    
    if not payload:
        context = {
            'message_type': 'error',
            'message': 'This decline link is invalid or has expired.'
        }
        return render(request, 'scheduling/confirmation_response.html', context)

    try:
        user_id, token_session_id = payload.split(':')
        user_id = int(user_id)
        if int(token_session_id) != session_id:
            raise ValueError("Token-URL mismatch.")
    except (ValueError, IndexError):
        context = {
            'message_type': 'error',
            'message': 'The decline link is malformed.'
        }
        return render(request, 'scheduling/confirmation_response.html', context)

    user = get_object_or_404(User, pk=user_id)
    session = get_object_or_404(Session, pk=session_id)
    
    CoachAvailability.objects.update_or_create(
        coach=user, 
        session=session,
        defaults={
            'is_available': False, 
            'last_action': 'DECLINE', 
            'status_updated_at': timezone.now(), 
            'notes': 'Declined via email link.'
        }
    )

    context = {
        'message_type': 'warning',
        'message': f"Thank you, {user.first_name}. We have recorded that you are unavailable for the session on {session.session_date.strftime('%A, %d %B')}."
    }
    return render(request, 'scheduling/confirmation_response.html', context)

def player_attendance_response(request, token):
    """ Handles a parent's attendance response from an email link. """
    try:
        # FIX 1: Use `timedelta` directly, not `datetime.timedelta`
        payload = notifications.player_attendance_signer.unsign(token, max_age=timedelta(days=7))
        record_id, new_status = payload.split(':')
    except (BadSignature, SignatureExpired): # FIX 2: Use exceptions directly
        context = {
            'message_type': 'error',
            'message': 'This attendance link is invalid or has expired. Please contact your coach.'
        }
        return render(request, 'scheduling/confirmation_response.html', context)
    except ValueError:
        context = {
            'message_type': 'error',
            'message': 'This attendance link appears to be malformed.'
        }
        return render(request, 'scheduling/confirmation_response.html', context)

    try:
        tracking_record = AttendanceTracking.objects.select_related('player', 'session').get(pk=record_id)
        
        if new_status in AttendanceTracking.Status.values:
            tracking_record.status = new_status
            tracking_record.save()
            
            player_name = tracking_record.player.first_name
            session_date_str = tracking_record.session.session_date.strftime('%A, %d %B')
            
            if new_status == AttendanceTracking.Status.ATTENDING:
                message = f"Thank you! {player_name}'s attendance for the session on {session_date_str} has been confirmed."
                message_type = 'success'
            else:
                message = f"Thank you. We've recorded that {player_name} will not attend the session on {session_date_str}."
                message_type = 'warning'
        else:
            message = "Invalid status provided in the link."
            message_type = 'error'

        context = {'message_type': message_type, 'message': message}

    except AttendanceTracking.DoesNotExist:
        context = {
            'message_type': 'error',
            'message': 'We could not find the corresponding attendance record. Please contact an administrator.'
        }

    return render(request, 'scheduling/confirmation_response.html', context)
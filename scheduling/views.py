# scheduling/views.py

# --- Start: Replace your existing imports with this block ---
import json
from datetime import timedelta, datetime

from collections import defaultdict

from django.core.signing import BadSignature, SignatureExpired
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.db.models import Prefetch
from django.db import IntegrityError
import time 

from django.contrib.auth import get_user_model

import calendar
from .utils import get_month_start_end # We will create this helper function next
from .forms import MonthYearFilterForm

# Import models from their new app locations
from .models import Session, CoachAvailability, Venue, ScheduledClass, AttendanceTracking, Drill, DrillTag
from .forms import SessionForm, SessionFilterForm, CoachAvailabilityForm, AttendanceForm
from players.models import Player, SchoolGroup
from . import notifications
from .notifications import verify_confirmation_token
from accounts.models import Coach
from assessments.models import SessionAssessment, GroupAssessment
# --- End: Replacement block ---
User = get_user_model()

def is_staff(user):
    """
    Check if the user is a coach (staff) or a superuser.
    This will be used to protect the session detail page.
    """
    return user.is_staff


@login_required
def homepage(request):
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)

    # Get upcoming sessions based on user role
    if request.user.is_superuser:
        upcoming_sessions = Session.objects.filter(
            session_date__in=[today, tomorrow]
        ).order_by('session_date', 'session_start_time')
    else:
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


def _get_default_plan(session):
    # This function remains the same as the last version
    duration = session.planned_duration_minutes
    plan = {
        "playerGroups": [
            {"id": "groupA", "name": "Group A", "player_ids": []},
            {"id": "groupB", "name": "Group B", "player_ids": []},
            {"id": "groupC", "name": "Group C", "player_ids": []},
        ], "timeline": []
    }
    all_group_ids = [g['id'] for g in plan['playerGroups']]
    ts = int(time.time())
    warmup_court = [{"id": f"court_warmup_{ts}", "name": "Court 1", "assignedGroupIds": all_group_ids, "activities": []}]
    if duration >= 90:
        phases = [
            {"id": f"phase_{ts}_1", "type": "Warmup", "name": "Warmup", "duration": 10, "courts": warmup_court},
            {"id": f"phase_{ts}_2", "type": "Rotation", "name": "Rotation Drills", "duration": 45, "courts": [], "sub_blocks": []},
            {"id": f"phase_{ts}_3", "type": "Freeplay", "name": "Match Play", "duration": 20, "courts": []},
            {"id": f"phase_{ts}_4", "type": "Fitness", "name": "Fitness", "duration": 15, "courts": []},
        ]
    elif duration >= 60:
        phases = [
            {"id": f"phase_{ts}_1", "type": "Warmup", "name": "Warmup", "duration": 10, "courts": warmup_court},
            {"id": f"phase_{ts}_2", "type": "Rotation", "name": "Rotation Drills", "duration": 40, "courts": [], "sub_blocks": []},
            {"id": f"phase_{ts}_3", "type": "Freeplay", "name": "Cooldown / Freeplay", "duration": 10, "courts": []},
        ]
    else:
        phases = []
    plan["timeline"] = phases
    return plan

@login_required
@user_passes_test(is_staff)
def session_detail(request, session_id):
    session = get_object_or_404(
        Session.objects.select_related('school_group', 'venue'),
        pk=session_id
    )

    # --- THIS IS THE NEW CORE LOGIC ---
    players_for_grouping = []
    all_players_for_display = []

    if session.school_group:
        all_players_in_group = list(session.school_group.players.filter(is_active=True).order_by('last_name', 'first_name'))
        player_ids = [p.id for p in all_players_in_group]

        # Ensure records exist for all players to avoid errors
        existing_player_ids = set(
            AttendanceTracking.objects.filter(session=session, player_id__in=player_ids).values_list('player_id', flat=True)
        )
        new_records = [
            AttendanceTracking(session=session, player_id=pid)
            for pid in player_ids if pid not in existing_player_ids
        ]
        if new_records:
            AttendanceTracking.objects.bulk_create(new_records)

        # Fetch all attendance records for the session
        attendance_records = AttendanceTracking.objects.filter(session=session, player_id__in=player_ids)
        attendance_map = {att.player_id: att for att in attendance_records}

        # Check if final attendance has been taken for ANY player in this session
        has_final_attendance = any(att.attended != AttendanceTracking.CoachAttended.UNSET for att in attendance_map.values())

        # Populate the two different player lists
        for player in all_players_in_group:
            record = attendance_map.get(player.id)
            
            # 1. This list is ONLY for display in the top "Attendance" section
            all_players_for_display.append({
                'id': player.id,
                'name': player.full_name,
                'status': record.parent_response if record else 'PENDING'
            })

            # 2. This list is for the "Form Player Groups" section
            if has_final_attendance:
                # If final attendance has started, ONLY include players marked as YES
                if record and record.attended == AttendanceTracking.CoachAttended.YES:
                    players_for_grouping.append({
                        'id': player.id,
                        'name': player.full_name,
                        'status': 'ATTENDING' # Status for JS must be ATTENDING
                    })
            else:
                # Before final attendance, include PENDING and ATTENDING players
                parent_status = record.parent_response if record else 'PENDING'
                if parent_status in ['ATTENDING', 'PENDING']:
                    players_for_grouping.append({
                        'id': player.id,
                        'name': player.full_name,
                        'status': parent_status
                    })

    # The rest of the view remains the same...
    drills_queryset = Drill.objects.prefetch_related('tags').all()
    drills_data = []
    for drill in drills_queryset:
        drills_data.append({
            'id': drill.id, 'name': drill.name, 'youtube_link': drill.youtube_link,
            'tag_ids': list(drill.tags.values_list('id', flat=True))
        })
    all_tags_data = list(DrillTag.objects.all().values('id', 'name'))
    plan_data = session.plan if isinstance(session.plan, dict) and 'timeline' in session.plan else _get_default_plan(session)
    display_name = f"{session.school_group.name} Session" if session.school_group else f"Custom Session on {session.session_date.strftime('%Y-%m-%d')}"

    context = {
        'session': session,
        'coaches': session.coaches_attending.all(),
        'all_players_for_display': all_players_for_display, # For the top attendance list
        'players_for_grouping': players_for_grouping, # For the JS planner
        'drills': drills_data,
        'all_tags': all_tags_data,
        'plan': plan_data,
        'page_title': f"Plan for {display_name}"
    }

    return render(request, 'scheduling/session_detail.html', context)


@login_required
@require_POST
@user_passes_test(is_staff)
def save_session_plan(request, session_id):
    try:
        session = get_object_or_404(Session, pk=session_id)
        data = json.loads(request.body)
        
        # Basic validation can be added here if needed
        # For now, we trust the frontend to send a valid structure
        session.plan = data
        session.save()
        return JsonResponse({'status': 'success', 'message': 'Plan saved successfully!'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_POST
@user_passes_test(is_staff)
def update_attendance_status(request, session_id):
    try:
        data = json.loads(request.body)
        player_id = data.get('player_id')
        new_status = data.get('status')

        if not all([player_id, new_status]):
            return JsonResponse({'status': 'error', 'message': 'Missing player_id or status.'}, status=400)
        
        # --- THIS IS THE FIX ---
        # Ensure the status from the planner UI is a valid ParentResponse choice
        if new_status not in AttendanceTracking.ParentResponse.values:
            return JsonResponse({'status': 'error', 'message': 'Invalid status provided.'}, status=400)

        # Use update_or_create to handle both new and existing records gracefully.
        # This will ONLY modify the 'parent_response' field.
        AttendanceTracking.objects.update_or_create(
            session_id=session_id,
            player_id=player_id,
            defaults={'parent_response': new_status}
        )
        return JsonResponse({'status': 'success', 'message': f'Attendance for player {player_id} set to {new_status}.'})
        
    except (json.JSONDecodeError, IntegrityError, Exception) as e:
        return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred.'}, status=500)

@login_required
def visual_attendance(request, session_id):
    session = get_object_or_404(Session.objects.select_related('school_group'), pk=session_id)
    
    if not session.school_group:
        messages.error(request, "This session is not linked to a school group.")
        return redirect('scheduling:session_calendar')

    players_in_group = session.school_group.players.filter(is_active=True).order_by('last_name', 'first_name')

    if request.method == 'POST':
        attending_player_ids = set(request.POST.getlist('attendees'))
        
        # --- THIS IS THE CORRECTED LOGIC ---
        # We will iterate through every player and ensure their record is handled correctly.
        for player in players_in_group:
            # Get or create the record in memory without saving it immediately.
            # This preserves the existing parent_response if the record already exists.
            record, created = AttendanceTracking.objects.get_or_create(
                session=session,
                player=player
            )

            # Now, ONLY set the coach-marked attendance status.
            if str(player.id) in attending_player_ids:
                record.attended = AttendanceTracking.CoachAttended.YES
            else:
                record.attended = AttendanceTracking.CoachAttended.NO
            
            # Save the record. If it was new, parent_response is the default 'PENDING'.
            # If it existed, parent_response is whatever it was before.
            record.save()
        
        messages.success(request, "Final attendance has been recorded successfully.")
        return redirect('scheduling:session_detail', session_id=session.id)

    # --- The GET request logic remains the same, as it was correct ---
    tracking_records = {
        record.player_id: record for record in
        AttendanceTracking.objects.filter(session=session, player__in=players_in_group)
    }

    player_list = []
    for player in players_in_group:
        record = tracking_records.get(player.id)
        is_attending = False

        if record:
            if record.attended != AttendanceTracking.CoachAttended.UNSET:
                is_attending = (record.attended == AttendanceTracking.CoachAttended.YES)
            else:
                is_attending = (record.parent_response == AttendanceTracking.ParentResponse.ATTENDING)
        
        player_list.append({
            'player': player,
            'is_attending': is_attending
        })

    context = {
        'session': session,
        'school_group': session.school_group,
        'player_list': player_list,
        'page_title': "Take Final Attendance"
    }
    return render(request, 'scheduling/visual_attendance.html', context)

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
        except Exception:
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
            Prefetch('coach_availabilities', queryset=CoachAvailability.objects.select_related('coach'))
        ).order_by('session_start_time')
        
        processed_sessions = []
        for session in sessions_for_day:
            availability_map = {avail.coach.id: avail for avail in session.coach_availabilities.all()}
            
            assigned_coaches_status = []
            has_pending = False
            has_declined = False
            
            for coach in session.coaches_attending.all():
                avail = availability_map.get(coach.id)
                status = "Pending"
                if avail:
                    if avail.last_action == 'CONFIRM':
                        status = "Confirmed"
                    elif avail.last_action == 'DECLINE':
                        status = "Declined"
                        has_declined = True
                else:
                    has_pending = True
                assigned_coaches_status.append({'coach': coach, 'status': status, 'notes': avail.notes if avail else ''})

            available_coaches = []
            for coach in all_active_coaches:
                if coach not in session.coaches_attending.all():
                    avail = availability_map.get(coach.id)
                    if avail and avail.is_available:
                        available_coaches.append({
                            'coach': coach,
                            'is_emergency': "emergency" in (avail.notes or "").lower()
                        })
            
            # ==================== NEW LOGIC TO CALCULATE COUNTS (ADDITIVE CHANGE) ====================
            total_players = session.school_group.players.filter(is_active=True).count() if session.school_group else 0
            confirmed_players = AttendanceTracking.objects.filter(session=session, status='ATTENDING').count()
            total_coaches = session.coaches_attending.count()
            confirmed_coaches = sum(1 for c in assigned_coaches_status if c['status'] == "Confirmed")
            # ================================== END OF NEW LOGIC ===================================

            processed_sessions.append({
                'session_obj': session,
                'assigned_coaches_with_status': assigned_coaches_status,
                'available_coaches_for_assignment': sorted(available_coaches, key=lambda x: x['is_emergency']),
                'has_pending_confirmations': has_pending,
                'has_declined_coaches': has_declined,
                # ==================== ADD NEW DATA TO CONTEXT (ADDITIVE CHANGE) ====================
                'total_players': total_players,
                'confirmed_players_count': confirmed_players,
                'total_coaches_assigned': total_coaches,
                'confirmed_coaches_count': confirmed_coaches,
                # ================================= END OF NEW DATA =================================
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
        
        # --- MODIFICATION ---
        # Update the parent_response field instead of the old status field
        if new_status in AttendanceTracking.ParentResponse.values:
            tracking_record.parent_response = new_status
            tracking_record.save()
            
            player_name = tracking_record.player.first_name
            session_date_str = tracking_record.session.session_date.strftime('%A, %d %B')
            
            if new_status == AttendanceTracking.ParentResponse.ATTENDING:
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
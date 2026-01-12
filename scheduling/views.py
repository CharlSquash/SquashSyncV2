# scheduling/views.py
# --- Start: Replace your existing imports with this block ---
import json
from datetime import timedelta, datetime

from collections import defaultdict

from django.core.signing import BadSignature, SignatureExpired
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.db.models import Prefetch, F, ExpressionWrapper, DateTimeField, Exists, OuterRef, Q
from django.db import IntegrityError, transaction
import time 

from django.contrib.auth import get_user_model

import calendar
from .utils import get_month_start_end, check_for_conflicts
from .forms import MonthYearFilterForm

# Import models from their new app locations
from .models import Session, CoachAvailability, Venue, ScheduledClass, AttendanceTracking, Drill, DrillTag, SessionCoach, Event
from .forms import SessionForm, SessionFilterForm, CoachAvailabilityForm, AttendanceForm
from players.models import Player, SchoolGroup, AttendanceDiscrepancy
from . import notifications
from .notifications import verify_confirmation_token, send_coach_decline_notification_email, verify_bulk_confirmation_token
from accounts.models import Coach
from assessments.models import SessionAssessment, GroupAssessment
from finance.models import CoachSessionCompletion
from awards.models import Prize
from .services import SessionService
from todo.models import Task
# --- End: Replacement block ---
User = get_user_model()


def is_staff(user):
    """
    Check if the user is a coach (staff) or a superuser.
    This will be used to protect the session detail page.
    """
    return user.is_staff


# scheduling/views.py
def _admin_dashboard(request):
    today = timezone.now().date()
    now = timezone.now()
    current_year = today.year

    # Initialize variables specific to admin
    upcoming_sessions_for_admin = None
    discrepancy_report = None
    all_coach_assessments = None
    recent_group_assessments = None
    unstaffed_session_count = 0
    unconfirmed_staffing_alerts = False

    two_weeks_from_now = today + timedelta(days=14)
    upcoming_sessions = Session.objects.filter(
        session_date__gte=today,
        session_date__lte=two_weeks_from_now,
        is_cancelled=False
    ).prefetch_related('coaches_attending', 'coach_availabilities')

    unstaffed_session_count = sum(1 for s in upcoming_sessions if not s.coaches_attending.exists())

    for session in upcoming_sessions:
        if any(avail.status == 'UNAVAILABLE' or avail.status == 'PENDING' for avail in session.coach_availabilities.all()):
            unconfirmed_staffing_alerts = True
            break

    upcoming_sessions_for_admin = Session.objects.filter(
        session_date__in=[today, today + timedelta(days=1)]
    ).order_by('session_date', 'session_start_time')

    recent_sessions = Session.objects.filter(
        session_date__gte=today - timedelta(days=1)
    ).select_related('school_group')

    finished_session_ids = [
        s.id for s in recent_sessions
        if s.end_datetime and s.end_datetime < now
    ]

    discrepancy_report = AttendanceDiscrepancy.objects.filter(
        session_id__in=finished_session_ids,
        admin_acknowledged=False,
        discrepancy_type__in=['NO_SHOW', 'UNEXPECTED']
    ).select_related('player', 'session__school_group')

    all_coach_assessments = SessionAssessment.objects.filter(
        superuser_reviewed=False
    ).select_related('player', 'session', 'submitted_by').order_by('-date_recorded')

    recent_group_assessments = GroupAssessment.objects.filter(
        superuser_reviewed=False
    ).select_related('session__school_group', 'assessing_coach__coach_profile').order_by('-assessment_datetime')

    context = {
        'page_title': 'Dashboard',
        'upcoming_sessions_for_admin': upcoming_sessions_for_admin,
        'unstaffed_session_count': unstaffed_session_count,
        'unconfirmed_staffing_alerts': unconfirmed_staffing_alerts,
        'discrepancy_report': discrepancy_report,
        'all_coach_assessments': all_coach_assessments,
        'recent_group_assessments': recent_group_assessments,
        'pending_tasks_count': Task.objects.filter(assigned_to=request.user, completed=False).count(),
    }
    return render(request, 'scheduling/homepage.html', context)


def _coach_dashboard(request):
    today = timezone.now().date()
    now = timezone.now()
    current_year = today.year

    # Initialize variables specific to coach
    recent_sessions_for_feedback = None
    sessions_for_coach_card = []
    show_bulk_availability_reminder = False
    availability_all_set = False
    prompt_month_name = ""
    bulk_availability_url = ""
    show_awards_voting_card = False
    pending_tasks_count = 0

    try:
        coach = request.user.coach_profile
        four_weeks_ago = today - timedelta(weeks=4)
        tomorrow = today + timedelta(days=1)

        # --- REVISED LOGIC FOR "My Availability" CARD ---
        this_month_start = today.replace(day=1)
        next_month_start = (this_month_start + timedelta(days=32)).replace(day=1)

        SET_STATUSES = [
            CoachAvailability.Status.AVAILABLE,
            CoachAvailability.Status.UNAVAILABLE,
            CoachAvailability.Status.EMERGENCY,
        ]

        # Check if current month needs availability
        # Logic: Sessions exist (from rule, not blocked) AND
        # (Coach has NO availability record OR status is not in SET_STATUSES)
        needs_availability_current_month = Session.objects.filter(
            session_date__year=this_month_start.year,
            session_date__month=this_month_start.month,
            generated_from_rule__isnull=False,
            is_cancelled=False
        ).exclude(
            coach_availabilities__coach=request.user,
            coach_availabilities__status__in=SET_STATUSES
        ).exists()
        
        # Check if next month needs availability
        needs_availability_next_month = Session.objects.filter(
            session_date__year=next_month_start.year,
            session_date__month=next_month_start.month,
            generated_from_rule__isnull=False,
            is_cancelled=False
        ).exclude(
            coach_availabilities__coach=request.user,
            coach_availabilities__status__in=SET_STATUSES
        ).exists()
        
        if needs_availability_current_month:
            show_bulk_availability_reminder = True
            prompt_month_name = this_month_start.strftime('%B')
            bulk_availability_url = f"{reverse('scheduling:set_bulk_availability')}?month={this_month_start.strftime('%Y-%m')}"
        elif needs_availability_next_month:
            show_bulk_availability_reminder = True
            prompt_month_name = next_month_start.strftime('%B')
            bulk_availability_url = f"{reverse('scheduling:set_bulk_availability')}?month={next_month_start.strftime('%Y-%m')}"
        else:
            availability_all_set = True

        # --- Logic for Upcoming Sessions Card (Today & Tomorrow) ---
        local_now = timezone.localtime(now)
        upcoming_coach_sessions = Session.objects.filter(
            Q(session_date=today, session_start_time__gte=local_now.time()) | Q(session_date=tomorrow),
            coaches_attending=coach,
            is_cancelled=False
        ).prefetch_related(
            Prefetch('coach_availabilities', queryset=CoachAvailability.objects.filter(coach=request.user), to_attr='my_availability'),
            Prefetch('sessioncoach_set', queryset=SessionCoach.objects.filter(coach=coach), to_attr='my_session_coach_assignment')
        ).select_related('school_group', 'venue').order_by('session_date', 'session_start_time')


        for session in upcoming_coach_sessions:
            availability = session.my_availability[0] if session.my_availability else None
            assignment = session.my_session_coach_assignment[0] if session.my_session_coach_assignment else None

            status = "PENDING"
            if availability and availability.last_action:
                status = availability.last_action

            show_actions = session.session_date <= (today + timedelta(days=1))

            sessions_for_coach_card.append({
                'session': session,
                'status': status,
                'show_actions': show_actions,
                'duration': assignment.coaching_duration_minutes if assignment else session.planned_duration_minutes,
            })

        # --- Pending assessment logic (remains the same) ---
        sessions_needing_feedback_qs = Session.objects.filter(
            coaches_attending=coach,
            session_date__gte=four_weeks_ago,
            session_date__lte=today,
            is_cancelled=False
        ).exclude(
            coach_completions__coach=coach,
            coach_completions__assessments_submitted=True
        ).order_by('-session_date', '-session_start_time')

        recent_sessions_for_feedback = [
            s for s in sessions_needing_feedback_qs
            if s.end_datetime and s.end_datetime < now
        ]

        # --- CORRECTED: Check if awards voting is open ---
        now_dt = timezone.now()
        show_awards_voting_card = Prize.objects.filter(
            Q(voting_opens__isnull=True) | Q(voting_opens__lte=now_dt),  # Positional Arg
            Q(voting_closes__isnull=True) | Q(voting_closes__gte=now_dt), # Positional Arg
            year=current_year,                                            # Keyword Arg
            status=Prize.PrizeStatus.VOTING                               # Keyword Arg
        ).exists()
        # --- END CORRECTION ---

        # --- TODO APP INTEGRATION ---
        pending_tasks_count = Task.objects.filter(assigned_to=request.user, completed=False).count()

    except Coach.DoesNotExist:
        pass

    context = {
        'page_title': 'Dashboard',
        'recent_sessions_for_feedback': recent_sessions_for_feedback,
        'sessions_for_coach_card': sessions_for_coach_card,
        'show_bulk_availability_reminder': show_bulk_availability_reminder,
        'availability_all_set': availability_all_set,
        'next_month_name': prompt_month_name,
        'bulk_availability_url': bulk_availability_url,
        'show_awards_voting_card': show_awards_voting_card,
        'pending_tasks_count': pending_tasks_count,
    }
    return render(request, 'scheduling/homepage.html', context)


@login_required
def homepage(request):
    if request.user.is_superuser:
        return _admin_dashboard(request)
    elif request.user.is_staff:
        return _coach_dashboard(request)
    else:
        # Fallback for non-staff users (render basic view with empty context)
        return render(request, 'scheduling/homepage.html', {'page_title': 'Dashboard'})

@login_required
@user_passes_test(is_staff)
def session_detail(request, session_id):
    session = get_object_or_404(
        Session.objects.select_related('school_group', 'venue'),
        pk=session_id
    )

    # We only need the display list for the attendance check
    all_players_for_display, _ = SessionService.get_session_player_lists(session)
    
    display_name = f"{session.school_group.name} Session" if session.school_group else f"Custom Session on {session.session_date.strftime('%Y-%m-%d')}"

    # --- Session History Logic ---
    past_sessions = []
    if session.school_group:
        current_year = session.session_date.year
        past_sessions_qs = Session.objects.filter(
            school_group=session.school_group,
            session_date__year=current_year,
            session_date__lt=session.session_date,
            plan__isnull=False
        ).exclude(pk=session.id).order_by('-session_date')

        for ps in past_sessions_qs:
            drill_names = []
            try:
                plan = ps.plan if isinstance(ps.plan, dict) else json.loads(ps.plan)
                # Handle New Format (courtPlans)
                if plan and 'courtPlans' in plan:
                    # Collect all unique drill names from all courts
                    seen_drills = set()
                    for court_blocks in plan.get('courtPlans', []):
                        for block in court_blocks:
                            if not block.get('isRest', False):
                                name = block.get('customName') or block.get('name')
                                if name and name not in seen_drills:
                                    seen_drills.add(name)
                                    drill_names.append(name)
                
                # Handle Old Format (timeline)
                elif plan and 'timeline' in plan:
                     # Gather from timeline -> active blocks
                     pass # Simple implementation for now: skip or basic parsing if needed 
                     # (Users are moving to new format, showing legacy history might be overkill complexity for now)
            except:
                pass
            
            # Extract Groupings
            groupings = []
            if plan and 'groups' in plan:
                for idx, group in enumerate(plan['groups']):
                    if group: # If group has players
                        # Extract names. The group is a list of player objects (dicts)
                        player_names = [p.get('name', f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()) for p in group]
                        groupings.append({
                            'court_name': f"Court {idx + 1}",
                            'players': player_names
                        })

            # Create a simple structure for the template
            past_sessions.append({
                'id': ps.id,
                'date': ps.session_date,
                'drill_summary': ", ".join(drill_names) if drill_names else "No drills recorded",
                'groupings': groupings
            })


    context = {
        'session': session,
        'coaches': session.coaches_attending.all(),
        'all_players_for_display': all_players_for_display, # For the top attendance list
        'page_title': f"Plan for {display_name}",
        'past_sessions': past_sessions,
    }

    return render(request, 'scheduling/session_detail.html', context)

@require_POST
@login_required
def dashboard_confirm(request, session_id):
    if not request.user.is_staff:
        return HttpResponseForbidden()
    session = get_object_or_404(Session, pk=session_id)
    CoachAvailability.objects.update_or_create(
        coach=request.user,
        session=session,
        defaults={
            'status': CoachAvailability.Status.AVAILABLE, # UPDATE
            'last_action': 'CONFIRM',
            'status_updated_at': timezone.now()
        }
    )
    messages.success(request, f"Confirmed attendance for session on {session.session_date.strftime('%d %b')}.")
    return redirect('homepage')

@require_POST
@login_required
def dashboard_decline(request, session_id):
    if not request.user.is_staff:
        return HttpResponseForbidden()
    session = get_object_or_404(Session, pk=session_id)
    reason = request.POST.get('reason', '').strip()
    
    if not reason:
        messages.error(request, "A reason is required to decline an assigned session.")
        return redirect('homepage')

    CoachAvailability.objects.update_or_create(
        coach=request.user,
        session=session,
        defaults={
            'status': CoachAvailability.Status.UNAVAILABLE, # UPDATE
            'last_action': 'DECLINE',
            'status_updated_at': timezone.now(),
            'notes': reason
        }
    )

    # --- ADMIN NOTIFICATION ---
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    if session.session_date in [today, tomorrow]:
        send_coach_decline_notification_email(request.user, session, reason)
    
    messages.warning(request, f"Declined attendance for session on {session.session_date.strftime('%d %b')}.")
    return redirect('homepage')
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
    redirect_target = request.GET.get('next', 'session_detail') # Default to session_detail

    if not session.school_group:
        messages.error(request, "This session is not linked to a school group.")
        return redirect('scheduling:session_calendar')

    players_in_group = session.school_group.players.filter(is_active=True).order_by('last_name', 'first_name')

    if request.method == 'POST':
        attending_player_ids = set(request.POST.getlist('attendees'))
        # Determine redirect target from hidden input, fallback to GET param check
        post_redirect_target = request.POST.get('redirect_next', 'session_detail')

        # --- (Keep the discrepancy logic as it is) ---
        for player in players_in_group:
            record, _ = AttendanceTracking.objects.get_or_create(session=session, player=player)
            final_attendance = AttendanceTracking.CoachAttended.YES if str(player.id) in attending_player_ids else AttendanceTracking.CoachAttended.NO
            if record.attended != final_attendance:
                record.attended = final_attendance
                record.save()
            parent_response = record.parent_response
            discrepancy_type = None
            if parent_response == 'ATTENDING' and final_attendance == 'NO':
                discrepancy_type = 'NO_SHOW'
            elif parent_response == 'NOT_ATTENDING' and final_attendance == 'YES':
                discrepancy_type = 'UNEXPECTED'
            elif parent_response == 'PENDING' and final_attendance == 'NO':
                discrepancy_type = 'NEVER_NOTIFIED'
            if discrepancy_type:
                AttendanceDiscrepancy.objects.update_or_create(
                    player=player, session=session,
                    defaults={'discrepancy_type': discrepancy_type, 'parent_response': parent_response, 'coach_marked_attendance': final_attendance}
                )
            else:
                AttendanceDiscrepancy.objects.filter(player=player, session=session).delete()
        # --- (End of discrepancy logic) ---

        messages.success(request, "Final attendance has been recorded successfully.")

        # --- UPDATED REDIRECT LOGIC ---
        if post_redirect_target == 'pending_assessments':
            return redirect('assessments:pending_assessments')
        else:
            # Default redirect back to the session planner/detail page
            return redirect('scheduling:session_detail', session_id=session.id)
        # --- END UPDATED REDIRECT LOGIC ---

    # --- GET request logic (remains mostly the same) ---
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
        player_list.append({'player': player, 'is_attending': is_attending})

    context = {
        'session': session,
        'school_group': session.school_group,
        'player_list': player_list,
        'page_title': "Take Final Attendance",
        'redirect_next': redirect_target # Pass the redirect target to the template
    }
    return render(request, 'scheduling/visual_attendance.html', context)

@login_required
def session_calendar(request):
    # Determine the view mode from URL (defaults to 'own')
    view_mode = request.GET.get('view', 'own')

    # Check if the user has the special permission
    can_view_all = request.user.has_perm('scheduling.can_view_all_sessions')

    sessions_qs = Session.objects.all()

    # Filter sessions based on user role and selected view mode
    if request.user.is_superuser:
        # Superuser always sees all sessions
        sessions = sessions_qs
    elif can_view_all and view_mode == 'all':
        # Permitted staff member has selected 'all'
        sessions = sessions_qs
    else:
        # Default for all other staff: only see their own sessions
        sessions = sessions_qs.filter(coaches_attending__user=request.user)

    # --- Subquery to check for attendance records ---
    attendance_taken_subquery = AttendanceTracking.objects.filter(
        session=OuterRef('pk'),
        attended__in=[AttendanceTracking.CoachAttended.YES, AttendanceTracking.CoachAttended.NO]
    )

    # Annotate the queryset with an 'attendance_taken' boolean field
    # *** FIX 1: Assign to a new variable and use it in the loop ***
    sessions_annotated = sessions.select_related('school_group', 'venue').prefetch_related('coaches_attending').annotate(
        attendance_taken=Exists(attendance_taken_subquery)
    )

    # Build the rich event data for FullCalendar
    events = []
    for session in sessions_annotated: # *** Iterate over the correct variable ***
        class_names = []
        if session.is_cancelled:
            class_names.append('cancelled-session')
        
        if session.attendance_taken:
            class_names.append('fc-event-attendance-taken')

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
            'classNames': class_names
        })

    # --- TASKS LAYER LOGIC ---
    tasks_qs = Task.objects.filter(
        assigned_to=request.user,
        completed=False,
        due_date__isnull=False
    )

    tasks_data = []
    for task in tasks_qs:
        tasks_data.append({
            'title': task.title,
            'start': task.due_date.isoformat(), # Output as ISO string YYYY-MM-DD
            'allDay': True,
            'url': reverse('todo:task_detail', args=[task.id]),
            'color': '#ffc107', # Bootstrap warning yellow
            'extendedProps': {
                'type': 'task'
            }
        })

    # --- SPECIAL EVENTS LAYER LOGIC ---
    special_events_qs = Event.objects.all()
    special_events_data = []
    for event in special_events_qs:
        special_events_data.append({
            'title': event.name,
            'start': event.event_date.isoformat(),
            'allDay': True,
            'id': event.id, # Added ID
            'color': '#17a2b8', # Info Teal
            'editable': request.user.is_superuser, # Only superusers can move events
            'extendedProps': {
                'type': 'event',
                'description': event.description,
                'event_type': event.get_event_type_display()
            }
        })

    # *** FIX 2: Add the necessary variables to the context for the template ***
    context = {
        'page_title': "Session Calendar",
        'events_json': json.dumps(events),
        'tasks_json': json.dumps(tasks_data), # Add tasks data
        'special_events_json': json.dumps(special_events_data), # Add special events data
        'can_view_all': can_view_all,
        'is_all_view': view_mode == 'all' and can_view_all,
        # DATA FOR MANAGEMENT MODE
        'all_school_groups': SchoolGroup.objects.filter(is_active=True).order_by('name'),
        'all_venues': Venue.objects.filter(is_active=True).order_by('name'),
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
        coach_profile = None

    if request.method == 'POST':
        updated_count = 0
        session_ids_in_form = [int(key.split('_')[-1]) for key in request.POST.keys() if key.startswith('availability_session_')]
        existing_records_qs = CoachAvailability.objects.filter(
            coach=request.user, 
            session_id__in=session_ids_in_form
        )
        existing_availabilities = {record.session_id: record for record in existing_records_qs}

        for key, value in request.POST.items():
            if key.startswith('availability_session_'):
                session_id = int(key.split('_')[-1])
                notes = request.POST.get(f'notes_session_{session_id}', '').strip()
                
                if value not in CoachAvailability.Status.values:
                    continue

                existing_record = existing_availabilities.get(session_id)
                current_status = existing_record.status if existing_record else CoachAvailability.Status.PENDING
                current_notes = existing_record.notes if existing_record else ""

                if value == current_status and notes == current_notes:
                    continue

                try:
                    session = Session.objects.get(pk=session_id)
                    CoachAvailability.objects.update_or_create(
                        coach=request.user, session=session,
                        defaults={'status': value, 'notes': notes}
                    )
                    updated_count += 1
                except Session.DoesNotExist:
                    messages.warning(request, f"Could not find session with ID {session_id}.")
        
        if updated_count > 0:
            messages.success(request, f"Successfully updated your availability for {updated_count} session(s).")
        else:
            messages.info(request, "No changes to your availability were saved.")
        
        return redirect(f"{reverse('scheduling:my_availability')}?week={request.GET.get('week', '0')}")

    # --- GET REQUEST LOGIC (THIS IS THE CORRECTED PART) ---
    now = timezone.now()
    today = now.date()
    
    try:
        week_offset = int(request.GET.get('week', '0'))
    except (ValueError, TypeError):
        week_offset = 0

    start_of_this_week = today - timedelta(days=today.weekday())
    target_week_start = start_of_this_week + timedelta(weeks=week_offset)
    target_week_end = target_week_start + timedelta(days=6)
    
    # --- START OF FIX ---
    
    # 1. Define the prefetch object we will use.
    my_availability_prefetch = Prefetch(
        'coach_availabilities', 
        queryset=CoachAvailability.objects.filter(coach=request.user), 
        to_attr='my_availability'
    )

    # 2. Build the base queryset with the prefetch applied only ONCE.
    upcoming_sessions_qs = Session.objects.filter(
        session_date__gte=target_week_start,
        session_date__lte=target_week_end,
        is_cancelled=False
    ).select_related('school_group').prefetch_related(
        'coaches_attending',
        my_availability_prefetch  # Use the pre-defined prefetch object
    ).order_by('session_date', 'session_start_time')

    # 3. Now, if we are a coach, we can safely iterate to create missing records.
    #    The queryset is already final, so there's no risk of re-applying the prefetch.
    if coach_profile:
        # This loop now operates on a queryset that is already correctly defined.
        for session in upcoming_sessions_qs:
            is_assigned = coach_profile in session.coaches_attending.all()
            # If assigned but no availability record exists, create one.
            if is_assigned and not session.my_availability:
                # Create the record. Note: This will NOT be reflected in the current
                # loop's 'session.my_availability' because the prefetch is already done.
                # The data will be correct on the next page load, which is acceptable.
                CoachAvailability.objects.get_or_create(
                    coach=request.user,
                    session=session,
                    defaults={'status': CoachAvailability.Status.PENDING} # Default to PENDING
                )
    
    # --- END OF FIX ---

    # The rest of the view logic for grouping and rendering remains the same.
    grouped_sessions = defaultdict(list)
    for session in upcoming_sessions_qs:
        # We need to re-fetch my_availability for the created records
        if not hasattr(session, 'my_availability') or not session.my_availability:
             # This is a fallback for the session where we just created an availability.
             availability_info_qs = CoachAvailability.objects.filter(coach=request.user, session=session)
             availability_info = availability_info_qs.first()
        else:
            availability_info = session.my_availability[0] if session.my_availability else None
        
        is_assigned = coach_profile in session.coaches_attending.all() if coach_profile else False
        is_confirmed = availability_info.last_action == 'CONFIRM' if availability_info else False
        is_imminent = session.session_date <= (today + timedelta(days=1))

        session_data = {
            'session_obj': session,
            'current_status': availability_info.status if availability_info else CoachAvailability.Status.PENDING,
            'is_assigned': is_assigned,
            'is_confirmed': is_confirmed,
            'is_imminent': is_imminent,
            'notes': availability_info.notes if availability_info else "", # Pass notes to template
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
            if not availability_status_str or availability_status_str == 'PENDING': # PENDING is the default, no change needed
                continue

            status_map = {
                'AVAILABLE': CoachAvailability.Status.AVAILABLE,
                'EMERGENCY': CoachAvailability.Status.EMERGENCY,
            }
            status_to_set = status_map.get(availability_status_str)
            if not status_to_set:
                continue

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
                    defaults={'status': status_to_set}
                )
                availability_updated_count += 1
        
        month_name = calendar.month_name[selected_month]
        messages.success(request, f"Your availability for {availability_updated_count} potential sessions in {month_name} {selected_year} has been updated.")
        return redirect(f"{reverse('scheduling:set_bulk_availability')}?month={selected_year}-{selected_month:02d}")

    # --- GET request handling ---
    now = timezone.now()
    this_month = now.date().replace(day=1)
    next_month_date = (this_month + timedelta(days=32)).replace(day=1)

    this_month_str = this_month.strftime('%Y-%m')
    next_month_str = next_month_date.strftime('%Y-%m')

    selected_month_str = request.GET.get('month', this_month_str)
    try:
        selected_year, selected_month = map(int, selected_month_str.split('-'))
    except ValueError:
        selected_year, selected_month = this_month.year, this_month.month

    
    scheduled_classes_qs = ScheduledClass.objects.filter(is_active=True).select_related('school_group').order_by('day_of_week', 'start_time')
    
    # --- NEW: Fetch existing availability statuses ---
    start_date, end_date = get_month_start_end(selected_year, selected_month)


    existing_availabilities = CoachAvailability.objects.filter(
        coach=request.user,
        session__generated_from_rule__in=scheduled_classes_qs,
        session__session_date__range=[start_date, end_date]
    ).values('session__generated_from_rule_id', 'status')

    # Create a map of rule_id to the most common status for that rule in the month
    rule_status_map = defaultdict(lambda: CoachAvailability.Status.PENDING)
    status_counts = defaultdict(lambda: defaultdict(int))
    for avail in existing_availabilities:
        rule_id = avail['session__generated_from_rule_id']
        status = avail['status']
        if rule_id:
            status_counts[rule_id][status] += 1

    for rule_id, counts in status_counts.items():
        # Find the status with the highest count for this rule
        most_common_status = max(counts, key=counts.get)
        rule_status_map[rule_id] = most_common_status
    
    grouped_classes = defaultdict(list)
    for rule in scheduled_classes_qs:
        rule.current_status = rule_status_map[rule.id] # Attach the status to the rule object
        day_name = rule.get_day_of_week_display()
        grouped_classes[day_name].append(rule)

    context = {
        'page_title': "Set Bulk Availability",
        'grouped_classes': dict(grouped_classes),
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_month_display': calendar.month_name[selected_month],
        'this_month_str': this_month_str,
        'next_month_str': next_month_str,
        'this_month_name': this_month.strftime('%B'),
        'next_month_name': next_month_date.strftime('%B'),
        'this_month_year': this_month.year,
        'next_month_year': next_month_date.year,
        'selected_month_str': selected_month_str,
    }
    return render(request, 'scheduling/set_bulk_availability.html', context)


@require_POST
@login_required
def update_event_date(request):
    """
    AJAX view to update the date of an Event (drag & drop).
    Only accessible by superusers.
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to edit events.")

    try:
        data = json.loads(request.body)
        event_id = data.get('event_id')
        new_start = data.get('start') # ISO format date string

        if not event_id or not new_start:
            return JsonResponse({'status': 'error', 'message': 'Missing event_id or start date.'}, status=400)

        event = get_object_or_404(Event, pk=event_id)
        
        # Parse the new date. FullCalendar sends ISO strings.
        # Since these are all-day events, we just need the date part usually, 
        # but the model field is DateTimeField.
        # FullCalendar might send 'YYYY-MM-DD' or 'YYYY-MM-DDT...'
        # We'll use dateutil or just basic parsing if it's simple.
        # Given it's allDay, it likely sends 'YYYY-MM-DD'.
        # Let's be robust.
        try:
            # If it's just a date string YYYY-MM-DD
            new_date = datetime.fromisoformat(new_start)
        except ValueError:
            # Handle cases where it might be just a date string if fromisoformat fails on older python or specific formats
            # But fromisoformat is quite good in recent python.
            # Fallback for simple date string if needed, or just assume it works for now.
             new_date = datetime.strptime(new_start, '%Y-%m-%d')

        # Update the event
        # We keep the time if we want, or reset it. 
        # Since the requirement says "allDay: True", the time is less relevant, 
        # but we should probably preserve the original time or set to default.
        # However, the user drags to a DATE. 
        # Let's just update the date part of the datetime, keeping time as is or 00:00.
        # The model has default=timezone.now.
        
        # Construct new datetime with same time as before, or just 00:00?
        # Let's go with 00:00 for all-day events to be clean, or preserve existing time.
        # Let's preserve existing time to be safe, but change the date.
        current_time = event.event_date.time()
        new_datetime = datetime.combine(new_date.date(), current_time)
        
        # Make it aware if needed
        if timezone.is_naive(new_datetime):
            new_datetime = timezone.make_aware(new_datetime)
            
        event.event_date = new_datetime
        event.save()

        return JsonResponse({'status': 'success', 'message': 'Event date updated.'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_POST
@login_required
def delete_event(request):
    """
    AJAX view to delete an Event.
    Only accessible by superusers.
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to delete events.")

    try:
        data = json.loads(request.body)
        event_id = data.get('event_id')

        if not event_id:
            return JsonResponse({'status': 'error', 'message': 'Missing event_id.'}, status=400)

        event = get_object_or_404(Event, pk=event_id)
        event.delete()

        return JsonResponse({'status': 'success', 'message': 'Event deleted successfully.'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def session_staffing(request):
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

    # Pre-fetch all session assignments for the week for all active coaches
    coach_sessions_for_week = {
        coach.id: list(Session.objects.filter(
            coaches_attending=coach,
            session_date__range=[target_week_start, target_week_end],
            is_cancelled=False
        ).select_related('school_group', 'venue'))
        for coach in all_active_coaches
    }

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    display_week = []

    for i in range(7):
        current_day = target_week_start + timedelta(days=i)
        
        sessions_for_day = Session.objects.filter(
            session_date=current_day,
            is_cancelled=False
        ).select_related('school_group', 'venue').prefetch_related(
            'sessioncoach_set__coach__user',
            'coach_availabilities'
        ).order_by('session_start_time')
        
        processed_sessions = []
        for session in sessions_for_day:
            availability_map = {avail.coach_id: avail for avail in session.coach_availabilities.all()}
            
            coach_conflict_map = {}
            for coach in all_active_coaches:
                conflict = check_for_conflicts(coach, session, coach_sessions_for_week.get(coach.id, []))
                if conflict:
                    coach_conflict_map[coach.id] = conflict

            assigned_coaches_status = []
            has_pending = False
            has_declined = False
            
            for session_coach in session.sessioncoach_set.all():
                coach = session_coach.coach
                avail = availability_map.get(coach.user.id)
                status = "Pending"
                if avail:
                    if avail.status == CoachAvailability.Status.UNAVAILABLE:
                        status = "Declined"
                        has_declined = True
                    elif avail.last_action == 'CONFIRM':
                        status = "Confirmed"
                else:
                    has_pending = True
                
                assigned_coaches_status.append({
                    'coach': coach,
                    'status': status,
                    'notes': avail.notes if avail else '',
                    'conflict_warning': coach_conflict_map.get(coach.id),
                    'coaching_duration': session_coach.coaching_duration_minutes,
                })

            available_coaches = []
            assigned_coach_ids = {sc.coach.id for sc in session.sessioncoach_set.all()}
            for coach in all_active_coaches:
                if coach.id not in assigned_coach_ids:
                    avail = availability_map.get(coach.user.id)
                    if avail and avail.status in [CoachAvailability.Status.AVAILABLE, CoachAvailability.Status.EMERGENCY]:
                        available_coaches.append({
                            'coach': coach,
                            'is_emergency': avail.status == CoachAvailability.Status.EMERGENCY,
                            'conflict_warning': coach_conflict_map.get(coach.id)
                        })
            
            total_players = session.school_group.players.filter(is_active=True).count() if session.school_group else 0
            confirmed_players = AttendanceTracking.objects.filter(
                session=session, 
                parent_response=AttendanceTracking.ParentResponse.ATTENDING
            ).count()
            total_coaches = len(assigned_coach_ids)
            confirmed_coaches = sum(1 for c in assigned_coaches_status if c['status'] == "Confirmed")

            processed_sessions.append({
                'session_obj': session,
                'coach_conflict_map': coach_conflict_map,
                'assigned_coaches_with_status': assigned_coaches_status,
                'available_coaches_for_assignment': sorted(available_coaches, key=lambda x: x['is_emergency']),
                'has_pending_confirmations': has_pending,
                'has_declined_coaches': has_declined,
                'total_players': total_players,
                'confirmed_players_count': confirmed_players,
                'total_coaches_assigned': total_coaches,
                'confirmed_coaches_count': confirmed_coaches,
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

@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def assign_coaches_ajax(request):
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        coach_ids = [int(cid) for cid in data.get('coach_ids', [])]

        if session_id is None:
            return JsonResponse({'status': 'error', 'message': 'Missing session_id.'}, status=400)

        session = get_object_or_404(Session, pk=session_id)

        # --- THIS IS THE FIX ---
        # Instead of session.coaches_attending.set(), we manually manage the through model
        with transaction.atomic():
            # 1. Remove all existing assignments for this session
            SessionCoach.objects.filter(session=session).delete()
            
            # 2. Create new assignments with the default duration
            new_assignments = [
                SessionCoach(
                    session=session,
                    coach_id=coach_id,
                    coaching_duration_minutes=session.planned_duration_minutes
                ) for coach_id in coach_ids
            ]
            SessionCoach.objects.bulk_create(new_assignments)
        # --- END OF FIX ---


        # Re-fetch data for the response
        all_active_coaches = list(Coach.objects.filter(is_active=True).select_related('user').order_by('name'))
        all_active_coaches_dict = {c.id: c for c in all_active_coaches}
        
        start_date_range = session.session_date - timedelta(days=3)
        end_date_range = session.session_date + timedelta(days=3)
        
        coach_sessions_for_week = {
            coach.id: list(Session.objects.filter(
                coaches_attending=coach,
                session_date__range=[start_date_range, end_date_range],
                is_cancelled=False
            )) for coach in all_active_coaches
        }

        availability_map = {avail.coach_id: avail for avail in session.coach_availabilities.all()}
        
        assigned_coaches_data = []
        has_pending = False
        has_declined = False

        for coach_id in coach_ids:
            coach = all_active_coaches_dict.get(coach_id)
            if not coach: continue

            avail = availability_map.get(coach.user.id)
            status = "Pending"
            if avail:
                if avail.status == CoachAvailability.Status.UNAVAILABLE:
                    status = "Declined"
                    has_declined = True
                elif avail.last_action == 'CONFIRM':
                    status = "Confirmed"
            else:
                has_pending = True

            assigned_coaches_data.append({
                'id': coach.id,
                'name': coach.name,
                'status': status,
                'notes': avail.notes if avail and avail.notes else '',
                'conflict_warning': check_for_conflicts(coach, session, coach_sessions_for_week.get(coach.id, [])),
                'coaching_duration': session.planned_duration_minutes, # Add default duration
            })
        
        available_coaches_data = []
        assigned_coach_id_set = set(coach_ids)
        for coach in all_active_coaches:
            if coach.id not in assigned_coach_id_set:
                avail = availability_map.get(coach.user.id)
                if avail and avail.status in [CoachAvailability.Status.AVAILABLE, CoachAvailability.Status.EMERGENCY]:
                    available_coaches_data.append({
                        'id': coach.id,
                        'name': coach.name,
                        'is_emergency': avail.status == CoachAvailability.Status.EMERGENCY,
                        'conflict_warning': check_for_conflicts(coach, session, coach_sessions_for_week.get(coach.id, []))
                    })
        
        available_coaches_data.sort(key=lambda x: x['is_emergency'])

        confirmed_coaches_count = sum(1 for c in assigned_coaches_data if c['status'] == 'Confirmed')

        return JsonResponse({
            'status': 'success',
            'message': 'Assignments updated.',
            'assigned_coaches': assigned_coaches_data,
            'available_coaches': available_coaches_data,
            'confirmed_coaches_count': confirmed_coaches_count,
            'total_coaches_assigned': len(coach_ids),
            'has_pending': has_pending,
            'has_declined': has_declined,
        })
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data provided.'}, status=400)
    except Session.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Session not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}, status=500)


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def update_coach_duration_ajax(request):
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        coach_id = data.get('coach_id')
        duration = data.get('duration')

        if not all([session_id, coach_id, duration]):
            return JsonResponse({'status': 'error', 'message': 'Missing data.'}, status=400)

        with transaction.atomic():
            session_coach = get_object_or_404(SessionCoach, session_id=session_id, coach_id=coach_id)
            session_coach.coaching_duration_minutes = int(duration)
            session_coach.save()

            # --- END OF FIX ---

        return JsonResponse({'status': 'success', 'message': 'Duration updated.'})
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid data.'}, status=400)
    except SessionCoach.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Assignment not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}, status=500)


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
            'status': CoachAvailability.Status.AVAILABLE, # UPDATE
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


def decline_attendance_reason(request, session_id, token):
    """
    Handles attendance decline from an email link, requiring a reason.
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

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, "A reason is required to decline.")
            return redirect(request.path) # Redirect back to the same page

        CoachAvailability.objects.update_or_create(
            coach=user,
            session=session,
            defaults={
                'status': CoachAvailability.Status.UNAVAILABLE, # UPDATE
                'last_action': 'DECLINE',
                'status_updated_at': timezone.now(),
                'notes': reason
            }
        )
        
        today = timezone.now().date()
        if session.session_date in [today, today + timedelta(days=1)]:
            notifications.send_coach_decline_notification_email(user, session, reason)

        context = {
            'message_type': 'warning',
            'message': f"Thank you, {user.first_name}. We have recorded that you are unavailable for the session on {session.session_date.strftime('%A, %d %B')}."
        }
        return render(request, 'scheduling/confirmation_response.html', context)

    context = {
        'session': session,
        'coach_name': user.first_name,
    }
    return render(request, 'scheduling/decline_reason_form.html', context)


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

def confirm_all_for_day(request, date_str, token):
    """ Handles bulk confirmation for all of a coach's sessions on a given day. """
    payload = verify_bulk_confirmation_token(token)
    try:
        user_id_from_token, token_date_str = payload.split(':')
        user_id = int(user_id_from_token)
        # Security check: ensure date in token matches URL
        if token_date_str != date_str:
            raise ValueError("Token-URL date mismatch.")
        session_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError, AttributeError):
        context = {
            'message_type': 'error',
            'message': 'This confirmation link is malformed or invalid.'
        }
        return render(request, 'scheduling/confirmation_response.html', context)

    user = get_object_or_404(User, pk=user_id)
    sessions_for_day = Session.objects.filter(
        coaches_attending__user=user,
        session_date=session_date,
        is_cancelled=False
    )

    for session in sessions_for_day:
        CoachAvailability.objects.update_or_create(
            coach=user,
            session=session,
            defaults={
                'status': CoachAvailability.Status.AVAILABLE,
                'last_action': 'CONFIRM',
                'status_updated_at': timezone.now()
            }
        )
    
    context = {
        'message_type': 'success',
        'message': f"Thank you, {user.first_name}! Your attendance for all sessions on {session_date.strftime('%A, %d %B')} is confirmed."
    }
    return render(request, 'scheduling/confirmation_response.html', context)


def decline_all_for_day_reason(request, date_str, token):
    """ Handles bulk decline for all of a coach's sessions on a given day. """
    payload = verify_bulk_confirmation_token(token)
    try:
        user_id_from_token, token_date_str = payload.split(':')
        user_id = int(user_id_from_token)
        if token_date_str != date_str:
            raise ValueError("Token-URL date mismatch.")
        session_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError, AttributeError):
        context = { 'message_type': 'error', 'message': 'This decline link is malformed or invalid.'}
        return render(request, 'scheduling/confirmation_response.html', context)
    
    user = get_object_or_404(User, pk=user_id)
    sessions_for_day = Session.objects.filter(
        coaches_attending__user=user,
        session_date=session_date,
        is_cancelled=False
    ).select_related('school_group')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, "A reason is required to decline.")
            # Re-render the form with the error
            return render(request, 'scheduling/decline_all_reason_form.html', {'sessions': sessions_for_day, 'coach_name': user.first_name, 'date_str': date_str, 'error': 'A reason is required.'})

        for session in sessions_for_day:
            CoachAvailability.objects.update_or_create(
                coach=user,
                session=session,
                defaults={
                    'status': CoachAvailability.Status.UNAVAILABLE,
                    'last_action': 'DECLINE',
                    'status_updated_at': timezone.now(),
                    'notes': reason
                }
            )
            # Notify admin for each session that is soon
            today = timezone.now().date()
            if session.session_date <= today + timedelta(days=1):
                send_coach_decline_notification_email(user, session, reason)
        
        context = {
            'message_type': 'warning',
            'message': f"Thank you, {user.first_name}. We have recorded that you are unavailable for all sessions on {session_date.strftime('%A, %d %B')}."
        }
        return render(request, 'scheduling/confirmation_response.html', context)

    context = {
        'sessions': sessions_for_day,
        'coach_name': user.first_name,
        'date_str': date_str,
    }
    return render(request, 'scheduling/decline_all_reason_form.html', context)

@login_required
@require_POST
@user_passes_test(lambda u: u.is_superuser)
def update_session_ajax(request):
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        start_time_str = data.get('start_time') # HH:MM
        date_str = data.get('session_date') # YYYY-MM-DD
        
        if not all([session_id, start_time_str, date_str]):
             return JsonResponse({'status': 'error', 'message': 'Missing required fields.'}, status=400)

        session = get_object_or_404(Session, pk=session_id)
        
        # Parse new values
        new_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        new_time = datetime.strptime(start_time_str, '%H:%M').time()
        
        # NOTE: We are intentionally NOT modifying the generated_from_rule link.
        # This session effectively becomes a "custom" instance of that rule for this specific date.
        
        session.session_date = new_date
        session.session_start_time = new_time
        session.save()
        
        return JsonResponse({'status': 'success', 'message': 'Session updated successfully.'})
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
@user_passes_test(lambda u: u.is_superuser)
def create_session_ajax(request):
    try:
        data = json.loads(request.body)
        school_group_id = data.get('school_group_id') # Can be None/null
        venue_id = data.get('venue_id')
        date_str = data.get('date')
        time_str = data.get('time')
        duration = data.get('duration', 60)
        notes = data.get('notes', '')
        
        if not all([date_str, time_str]):
             return JsonResponse({'status': 'error', 'message': 'Date and Time are required.'}, status=400)

        session_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        session_time = datetime.strptime(time_str, '%H:%M').time()
        
        # Basic Conflict Check (Optional - can be made stricter)
        # Using existing utility if available, or simple overlap check
        # For now, we will trust the superuser but maybe warn? 
        # Requirement said: "Ensure new sessions do not conflict... by reusing check_for_conflicts if applicable."
        # check_for_conflicts(date, start_time, duration, venue, exclude_session_id=None)
        
        venue = None
        if venue_id:
            venue = get_object_or_404(Venue, pk=venue_id)
            
            # --- VENUE CONFLICT CHECK ---
            # Calculate end time of the proposed session
            # We can't trust passed session object yet as it's not created.
            # We do logic on times.
            
            # Convert to datetime for comparison
            # Note: session_time is a time object, date is date object.
            
            # Helper to get start/end datetimes
            start_dt = datetime.combine(session_date, session_time)
            end_dt = start_dt + timedelta(minutes=int(duration))
            
            # Normalize to time if sessions are only within one day?
            # Session model supports efficient date querying.
            
            overlapping_sessions = Session.objects.filter(
                venue=venue,
                session_date=session_date,
                is_cancelled=False
            )
            
            conflicts = []
            for existing in overlapping_sessions:
                if not existing.session_start_time: continue
                
                existing_start = datetime.combine(existing.session_date, existing.session_start_time)
                existing_end = existing_start + timedelta(minutes=existing.planned_duration_minutes)
                
                # Check Overlap: A_start < B_end and A_end > B_start
                if start_dt < existing_end and end_dt > existing_start:
                    conflicts.append(f"{existing.school_group.name if existing.school_group else 'Session'} ({existing.session_start_time.strftime('%H:%M')})")
            
            if conflicts:
                 return JsonResponse({'status': 'error', 'message': 'Venue conflict detected with: ' + ", ".join(conflicts)}, status=409)

        school_group = None
        if school_group_id:
            school_group = get_object_or_404(SchoolGroup, pk=school_group_id)

        session = Session.objects.create(
            school_group=school_group,
            venue=venue,
            session_date=session_date,
            session_start_time=session_time,
            planned_duration_minutes=int(duration),
            notes=notes,
            status='active'
        )
        
        return JsonResponse({'status': 'success', 'session_id': session.id})
        
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_POST
@user_passes_test(lambda u: u.is_superuser)
def delete_session_ajax(request):
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        
        if not session_id:
            return JsonResponse({'status': 'error', 'message': 'Session ID is required.'}, status=400)
            
        session = get_object_or_404(Session, pk=session_id)
        session.delete()
        
        return JsonResponse({'status': 'success', 'message': 'Session deleted successfully.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

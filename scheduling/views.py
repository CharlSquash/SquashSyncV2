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
from django.db.models import Prefetch, F, ExpressionWrapper, DateTimeField
from django.db import IntegrityError
import time 

from django.contrib.auth import get_user_model

import calendar
from .utils import get_month_start_end, check_for_conflicts
from .forms import MonthYearFilterForm

# Import models from their new app locations
from .models import Session, CoachAvailability, Venue, ScheduledClass, AttendanceTracking, Drill, DrillTag
from .forms import SessionForm, SessionFilterForm, CoachAvailabilityForm, AttendanceForm
from players.models import Player, SchoolGroup, AttendanceDiscrepancy
from . import notifications
from .notifications import verify_confirmation_token, send_coach_decline_notification_email
from accounts.models import Coach
from assessments.models import SessionAssessment, GroupAssessment
from finance.models import CoachSessionCompletion
# --- End: Replacement block ---
User = get_user_model()

def is_staff(user):
    """
    Check if the user is a coach (staff) or a superuser.
    This will be used to protect the session detail page.
    """
    return user.is_staff


# scheduling/views.py

@login_required
def homepage(request):
    today = timezone.now().date()
    now = timezone.now()

    # Common context variables
    upcoming_sessions_for_admin = None
    discrepancy_report = None
    recent_sessions_for_feedback = None
    all_coach_assessments = None
    recent_group_assessments = None
    sessions_for_coach_card = []
    unstaffed_session_count = 0  # Initialize for superuser
    unconfirmed_staffing_alerts = False # Initialize for superuser

    # --- Variables for the availability card ---
    show_bulk_availability_reminder = False
    prompt_month_name = ""
    bulk_availability_url = ""

    if request.user.is_superuser:
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

    elif request.user.is_staff:
        try:
            coach = request.user.coach_profile
            four_weeks_ago = today - timedelta(weeks=4)

            # --- UPDATED Logic for "My Availability" card reminder ---
            month_to_check_date = None

            # From the 1st to the 15th, remind for the CURRENT month.
            if 1 <= today.day <= 15:
                month_to_check_date = today.replace(day=1)
                prompt_month_name = month_to_check_date.strftime('%B')
            # From the 24th onwards, remind for the NEXT month.
            elif today.day >= 24:
                month_to_check_date = (today + timedelta(days=32)).replace(day=1)
                prompt_month_name = month_to_check_date.strftime('%B')

            if month_to_check_date:
                bulk_availability_url = f"{reverse('scheduling:set_bulk_availability')}?month={month_to_check_date.strftime('%Y-%m')}"

                # Check if any availability has been set for the determined month
                has_set_availability = CoachAvailability.objects.filter(
                    coach=request.user,
                    session__session_date__year=month_to_check_date.year,
                    session__session_date__month=month_to_check_date.month
                ).exists()

                if not has_set_availability:
                    show_bulk_availability_reminder = True

            # --- Upcoming sessions logic (remains the same) ---
            upcoming_coach_sessions = Session.objects.filter(
                coaches_attending=coach,
                session_date__gte=today,
                is_cancelled=False
            ).prefetch_related(
                Prefetch('coach_availabilities', queryset=CoachAvailability.objects.filter(coach=request.user), to_attr='my_availability')
            ).select_related('school_group', 'venue').order_by('session_date', 'session_start_time')[:5]

            for session in upcoming_coach_sessions:
                availability = session.my_availability[0] if session.my_availability else None
                status = "PENDING"
                if availability and availability.last_action:
                    status = availability.last_action
                show_actions = session.session_date <= (today + timedelta(days=1))
                sessions_for_coach_card.append({
                    'session': session,
                    'status': status,
                    'show_actions': show_actions,
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

        except Coach.DoesNotExist:
            pass

    context = {
        'page_title': 'Dashboard',
        'upcoming_sessions_for_admin': upcoming_sessions_for_admin,
        'unstaffed_session_count': unstaffed_session_count,
        'unconfirmed_staffing_alerts': unconfirmed_staffing_alerts,
        'discrepancy_report': discrepancy_report,
        'recent_sessions_for_feedback': recent_sessions_for_feedback,
        'all_coach_assessments': all_coach_assessments,
        'recent_group_assessments': recent_group_assessments,
        'sessions_for_coach_card': sessions_for_coach_card,
        'show_bulk_availability_reminder': show_bulk_availability_reminder,
        'next_month_name': prompt_month_name,
        'bulk_availability_url': bulk_availability_url,
    }

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

    # --- FETCH PREVIOUS SESSION GROUPS ---
    previous_groups_data = None
    previous_session = Session.objects.filter(
        school_group=session.school_group,
        session_date__lt=session.session_date
    ).order_by('-session_date', '-session_start_time').first()

    if previous_session and previous_session.plan and isinstance(previous_session.plan, dict):
        previous_groups_data = previous_session.plan.get('playerGroups')
        # Add player names to the group data for easy display
        if previous_groups_data:
            all_players = {p.id: p.full_name for p in Player.objects.filter(school_groups=session.school_group)}
            for group in previous_groups_data:
                group['player_names'] = [all_players.get(pid, 'Unknown Player') for pid in group.get('player_ids', [])]

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
        'previous_groups': previous_groups_data, # Pass the new data
        'page_title': f"Plan for {display_name}"
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
    
    if not session.school_group:
        messages.error(request, "This session is not linked to a school group.")
        return redirect('scheduling:session_calendar')

    players_in_group = session.school_group.players.filter(is_active=True).order_by('last_name', 'first_name')

    if request.method == 'POST':
        attending_player_ids = set(request.POST.getlist('attendees'))
        
        # --- NEW DISCREPANCY LOGIC ---
        for player in players_in_group:
            record, _ = AttendanceTracking.objects.get_or_create(session=session, player=player)
            
            final_attendance = AttendanceTracking.CoachAttended.YES if str(player.id) in attending_player_ids else AttendanceTracking.CoachAttended.NO
            
            # Only update if changed
            if record.attended != final_attendance:
                record.attended = final_attendance
                record.save()

            # Check for discrepancies
            parent_response = record.parent_response
            discrepancy_type = None

            if parent_response == 'ATTENDING' and final_attendance == 'NO':
                discrepancy_type = 'NO_SHOW'
            elif parent_response == 'NOT_ATTENDING' and final_attendance == 'YES':
                discrepancy_type = 'UNEXPECTED'
            elif parent_response == 'PENDING' and final_attendance == 'NO':
                discrepancy_type = 'NEVER_NOTIFIED'

            # Create or update discrepancy record
            if discrepancy_type:
                AttendanceDiscrepancy.objects.update_or_create(
                    player=player,
                    session=session,
                    defaults={
                        'discrepancy_type': discrepancy_type,
                        'parent_response': parent_response,
                        'coach_marked_attendance': final_attendance,
                    }
                )
            else:
                # If there's no discrepancy, delete any existing record for this player/session
                AttendanceDiscrepancy.objects.filter(player=player, session=session).delete()

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
#... (rest of the file is unchanged)

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

login_required
def my_availability(request):
    # This view has been significantly updated
    try:
        coach_profile = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        if not request.user.is_superuser:
            messages.error(request, "Your user account is not linked to a Coach profile.")
            return redirect('homepage')
        coach_profile = None

    if request.method == 'POST':
        updated_count = 0
        
        # --- Start of the fix ---
        # Get all session IDs from the submitted form
        session_ids_in_form = [int(key.split('_')[-1]) for key in request.POST.keys() if key.startswith('availability_session_')]
        
        # Correctly fetch records and build a dictionary manually instead of using in_bulk
        existing_records_qs = CoachAvailability.objects.filter(
            coach=request.user, 
            session_id__in=session_ids_in_form
        )
        existing_availabilities = {record.session_id: record for record in existing_records_qs}
        # --- End of the fix ---

        for key, value in request.POST.items():
            if key.startswith('availability_session_'):
                session_id = int(key.split('_')[-1])
                notes = request.POST.get(f'notes_session_{session_id}', '').strip()
                
                if value not in CoachAvailability.Status.values:
                    continue

                # --- Comparison logic ---
                existing_record = existing_availabilities.get(session_id)
                current_status = existing_record.status if existing_record else CoachAvailability.Status.PENDING
                current_notes = existing_record.notes if existing_record else ""

                if value == current_status and notes == current_notes:
                    continue # Skip if nothing has changed

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

    # --- GET request handling (remains the same) ---
    now = timezone.now()
    today = now.date()
    
    try:
        week_offset = int(request.GET.get('week', '0'))
    except (ValueError, TypeError):
        week_offset = 0

    start_of_this_week = today - timedelta(days=today.weekday())
    target_week_start = start_of_this_week + timedelta(weeks=week_offset)
    target_week_end = target_week_start + timedelta(days=6)

    upcoming_sessions_qs = Session.objects.filter(
        session_date__gte=target_week_start,
        session_date__lte=target_week_end,
        is_cancelled=False
    ).select_related('school_group').prefetch_related(
        'coaches_attending',
        Prefetch('coach_availabilities', queryset=CoachAvailability.objects.filter(coach=request.user), to_attr='my_availability')
    ).order_by('session_date', 'session_start_time')

    if coach_profile:
        sessions_to_update_prefetch = []
        for session in upcoming_sessions_qs:
            is_assigned = coach_profile in session.coaches_attending.all()
            if is_assigned and not session.my_availability:
                CoachAvailability.objects.get_or_create(
                    coach=request.user,
                    session=session,
                    defaults={'status': CoachAvailability.Status.AVAILABLE}
                )
                sessions_to_update_prefetch.append(session.id)
        
        if sessions_to_update_prefetch:
            upcoming_sessions_qs = upcoming_sessions_qs.prefetch_related(
                Prefetch('coach_availabilities', queryset=CoachAvailability.objects.filter(coach=request.user), to_attr='my_availability')
            )

    grouped_sessions = defaultdict(list)
    for session in upcoming_sessions_qs:
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

@login_required
@user_passes_test(lambda u: u.is_superuser)
def session_staffing(request):
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
            'coaches_attending__user',
            Prefetch('coach_availabilities', queryset=CoachAvailability.objects.select_related('coach'))
        ).order_by('session_start_time')
        
        processed_sessions = []
        for session in sessions_for_day:
            availability_map = {avail.coach_id: avail for avail in session.coach_availabilities.all()}
            
            # Create a map of coach IDs to their conflict messages for this specific session
            coach_conflict_map = {}
            for coach in all_active_coaches:
                conflict = check_for_conflicts(coach, session, coach_sessions_for_week.get(coach.id, []))
                if conflict:
                    coach_conflict_map[coach.id] = conflict

            assigned_coaches_status = []
            has_pending = False
            has_declined = False
            
            for coach in session.coaches_attending.all():
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
                    'conflict_warning': coach_conflict_map.get(coach.id)
                })

            available_coaches = []
            for coach in all_active_coaches:
                if coach not in session.coaches_attending.all():
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
            total_coaches = session.coaches_attending.count()
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
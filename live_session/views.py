
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from live_session.models import Drill
from players.models import Player
import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from scheduling.models import Session, AttendanceTracking
from accounts.models import Coach

def find_current_phase(plan, elapsed_seconds):
    """Finds the current phase, its elapsed time, and its index in the timeline."""
    cumulative_duration = 0
    timeline = plan.get('timeline', [])
    for index, phase in enumerate(timeline):
        phase_duration = int(phase.get('duration', 0)) * 60
        if elapsed_seconds < cumulative_duration + phase_duration:
            return phase, elapsed_seconds - cumulative_duration, index
        cumulative_duration += phase_duration
    return None, 0, -1

def get_activity_details(phase, court_id, elapsed_in_phase, player_groups_map, players_map):
    """Finds the current activity, group, time left, and total duration for a court."""
    phase_type = phase.get('type')
    group_name = "N/A"
    activity_name = "Transitioning"
    time_left = (int(phase.get('duration', 0)) * 60) - elapsed_in_phase
    duration = int(phase.get('duration', 0)) * 60
    player_names = []

    if phase_type == 'Rotation':
        rotation_duration_min = phase.get('rotationDuration', 0)
        if rotation_duration_min > 0:
            rotation_duration_sec = rotation_duration_min * 60
            rotation_num = int(elapsed_in_phase // rotation_duration_sec)
            sub_blocks = phase.get('sub_blocks', [])
            if rotation_num < len(sub_blocks):
                current_assignments = sub_blocks[rotation_num].get('assignments', {})
                group_id = current_assignments.get(court_id)
                if group_id and group_id in player_groups_map:
                    group_name = player_groups_map[group_id].get('name', 'N/A')
                    player_ids = player_groups_map[group_id].get('player_ids', [])
                    player_names = [players_map.get(pid, "Unknown") for pid in player_ids]
                for c in phase.get('courts', []):
                    if c and c.get('assignedGroupIds', [None])[0] == group_id and c.get('activities'):
                        activity_name = c['activities'][0].get('name', 'Unnamed Drill')
                        break
            time_left = rotation_duration_sec - (elapsed_in_phase % rotation_duration_sec)
            duration = rotation_duration_sec
    else:
        court_info = next((c for c in phase.get('courts', []) if c and c.get('id') == court_id), None)
        if court_info:
            assigned_group_ids = court_info.get('assignedGroupIds', [])
            group_names = [player_groups_map.get(gid, {}).get('name') for gid in assigned_group_ids]
            group_name = ', '.join(filter(None, group_names)) or 'N/A'
            player_ids = [pid for gid in assigned_group_ids for pid in player_groups_map.get(gid, {}).get('player_ids', [])]
            player_names = [players_map.get(pid, "Unknown") for pid in player_ids]
            activities = court_info.get('activities', [])
            activity_name = activities[0].get('name', 'General Activities') if activities else "General Activities"

    return {"name": activity_name, "group": group_name, "timeLeft": time_left, "duration": duration, "players": sorted(player_names)}

def get_next_activity_for_court(plan, current_phase_index, court_name):
    """
    Finds the next activity by looking ahead in the timeline, matching by COURT NAME.
    """
    timeline = plan.get('timeline', [])
    next_phase_index = current_phase_index + 1
    if next_phase_index >= len(timeline):
        return None

    next_phase = timeline[next_phase_index]
    
    # Find the court in the next phase that has the same name (e.g., "Court 1")
    next_court_info = next((c for c in next_phase.get('courts', []) if c and c.get('name') == court_name), None)
    if not next_court_info:
        return None # This court does not exist in the next phase.

    # If the next phase is a Rotation, find the activity for the group that starts on that court.
    if next_phase.get('type') == 'Rotation':
        group_id_on_court = next_court_info.get('assignedGroupIds', [None])[0]
        if group_id_on_court:
            # The activity is defined in the court that "owns" the group initially.
            for court_def in next_phase.get('courts', []):
                if court_def and court_def.get('assignedGroupIds', [None])[0] == group_id_on_court:
                    activities = court_def.get('activities', [])
                    if activities:
                        return {"name": activities[0].get('name')}
    
    # For standard phases, just get the activity directly from the court object.
    else:
        activities = next_court_info.get('activities', [])
        if activities:
            return {"name": activities[0].get('name')}
        else:
            return {"name": "General Activities"}
            
    return None

@login_required
def live_session_display(request, session_id):
    """Renders the main page, allowing access for superusers or assigned coaches."""
    if request.user.is_superuser:
        session = get_object_or_404(Session, pk=session_id)
    else:
        coach_profile = get_object_or_404(Coach, user=request.user)
        session = get_object_or_404(Session, pk=session_id, coaches_attending=coach_profile)
    return render(request, 'live_session/live_session_display.html', {'session': session})

@login_required
def live_session_update_api(request, session_id):
    """API endpoint, allowing access for superusers or assigned coaches."""
    if request.user.is_superuser:
        session = get_object_or_404(Session, pk=session_id)
    else:
        coach_profile = get_object_or_404(Coach, user=request.user)
        session = get_object_or_404(Session.objects.prefetch_related('coaches_attending__user', 'attendees'), pk=session_id, coaches_attending=coach_profile)

    # --- NEW: Simplified Title Generation ---
    group_name = session.school_group.name if session.school_group else "General"
    start_time_str = session.session_start_time.strftime('%H:%M')
    end_time_str = (session.start_datetime + timezone.timedelta(minutes=session.planned_duration_minutes)).strftime('%H:%M')
    session_title = f"{group_name} : {start_time_str} - {end_time_str}"

    if session.status == 'pending' or not session.start_time:
        now = timezone.now()
        start_datetime = session.start_datetime
        if now < start_datetime:
            time_to_start = (start_datetime - now).total_seconds()
            
            # Fetch assigned coaches and confirmed attendees
            coaches = [coach.user.get_full_name() or coach.user.username for coach in session.coaches_attending.all()]
            
            # --- MODIFICATION ---
            # Prioritize coach-marked attendance. Fallback to parent-confirmed.
            coach_marked_qs = AttendanceTracking.objects.filter(session=session, attended=AttendanceTracking.CoachAttended.YES)
            
            if coach_marked_qs.exists():
                # Use players the coach marked as present
                attendee_pks = coach_marked_qs.values_list('player_id', flat=True)
            else:
                # Fallback to players whose parents confirmed they are attending
                attendee_pks = AttendanceTracking.objects.filter(session=session, parent_response=AttendanceTracking.ParentResponse.ATTENDING).values_list('player_id', flat=True)
            
            attendees = [
                player.full_name for player in
                Player.objects.filter(pk__in=attendee_pks)
            ]
            
            return JsonResponse({
                'sessionStatus': 'not_yet_started',
                'sessionTitle': session_title,
                'timeToStart': time_to_start,
                'coaches': sorted(coaches),
                'attendees': sorted(attendees),
            })
        else:
             # If the session was supposed to start but isn't active, treat it as pending
            return JsonResponse({'sessionStatus': 'pending', 'sessionTitle': session_title})

    if session.status == 'finished': 
        return JsonResponse({'sessionStatus': 'finished', 'sessionTitle': session_title})

    try:
        plan = session.plan if isinstance(session.plan, dict) else json.loads(session.plan)
        if not plan or 'timeline' not in plan:
            return JsonResponse({'status': 'error', 'message': 'Session plan is invalid.'}, status=400)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Could not parse session plan.'}, status=400)

    now = timezone.now()
    elapsed_seconds = int((now - session.start_time).total_seconds())
    total_duration_seconds = sum(int(p.get('duration', 0)) * 60 for p in plan.get('timeline', []))
    time_left_session = max(0, total_duration_seconds - elapsed_seconds)

    if total_duration_seconds > 0 and elapsed_seconds > total_duration_seconds:
        session.status = 'finished'; session.end_time = now; session.save()
        return JsonResponse({'sessionStatus': 'finished'})

    current_phase, elapsed_in_phase, current_phase_index = find_current_phase(plan, elapsed_seconds)
    if not current_phase: return JsonResponse({'sessionStatus': 'finished'})

    time_left_phase = max(0, (int(current_phase.get('duration', 0)) * 60) - elapsed_in_phase)
    all_player_ids = {pid for grp in plan.get('playerGroups', []) for pid in grp.get('player_ids', [])}
    players_map = {p.id: p.full_name for p in Player.objects.filter(id__in=all_player_ids)}
    player_groups_map = {g['id']: g for g in plan.get('playerGroups', [])}
    courts_data = []

    for court in current_phase.get('courts', []):
        court_id = court.get('id')
        court_name = court.get('name')
        activity_details = get_activity_details(current_phase, court_id, elapsed_in_phase, player_groups_map, players_map)
        next_activity = get_next_activity_for_court(plan, current_phase_index, court_name)
        
        if activity_details:
            courts_data.append({
                "courtName": court_name, "playerGroup": activity_details['group'],
                "players": activity_details['players'],
                "currentActivity": { "name": activity_details['name'], "timeLeft": activity_details['timeLeft'], "duration": activity_details['duration'] },
                "nextActivity": next_activity
            })

    response_data = {
        'sessionStatus': session.status, 'sessionTitle': session_title, 'totalTimeLeft': time_left_session}

def find_current_phase(plan, elapsed_seconds):
    """Finds the current phase, its elapsed time, and its index in the timeline."""
    cumulative_duration = 0
    timeline = plan.get('timeline', [])
    for index, phase in enumerate(timeline):
        phase_duration = int(phase.get('duration', 0)) * 60
        if elapsed_seconds < cumulative_duration + phase_duration:
            return phase, elapsed_seconds - cumulative_duration, index
        cumulative_duration += phase_duration
    return None, 0, -1

def get_activity_details(phase, court_id, elapsed_in_phase, player_groups_map, players_map):
    """Finds the current activity, group, time left, and total duration for a court."""
    phase_type = phase.get('type')
    group_name = "N/A"
    activity_name = "Transitioning"
    time_left = (int(phase.get('duration', 0)) * 60) - elapsed_in_phase
    duration = int(phase.get('duration', 0)) * 60
    player_names = []

    if phase_type == 'Rotation':
        rotation_duration_min = phase.get('rotationDuration', 0)
        if rotation_duration_min > 0:
            rotation_duration_sec = rotation_duration_min * 60
            rotation_num = int(elapsed_in_phase // rotation_duration_sec)
            sub_blocks = phase.get('sub_blocks', [])
            if rotation_num < len(sub_blocks):
                current_assignments = sub_blocks[rotation_num].get('assignments', {})
                group_id = current_assignments.get(court_id)
                if group_id and group_id in player_groups_map:
                    group_name = player_groups_map[group_id].get('name', 'N/A')
                    player_ids = player_groups_map[group_id].get('player_ids', [])
                    player_names = [players_map.get(pid, "Unknown") for pid in player_ids]
                for c in phase.get('courts', []):
                    if c and c.get('assignedGroupIds', [None])[0] == group_id and c.get('activities'):
                        activity_name = c['activities'][0].get('name', 'Unnamed Drill')
                        break
            time_left = rotation_duration_sec - (elapsed_in_phase % rotation_duration_sec)
            duration = rotation_duration_sec
    else:
        court_info = next((c for c in phase.get('courts', []) if c and c.get('id') == court_id), None)
        if court_info:
            assigned_group_ids = court_info.get('assignedGroupIds', [])
            group_names = [player_groups_map.get(gid, {}).get('name') for gid in assigned_group_ids]
            group_name = ', '.join(filter(None, group_names)) or 'N/A'
            player_ids = [pid for gid in assigned_group_ids for pid in player_groups_map.get(gid, {}).get('player_ids', [])]
            player_names = [players_map.get(pid, "Unknown") for pid in player_ids]
            activities = court_info.get('activities', [])
            activity_name = activities[0].get('name', 'General Activities') if activities else "General Activities"

    return {"name": activity_name, "group": group_name, "timeLeft": time_left, "duration": duration, "players": sorted(player_names)}

def get_next_activity_for_court(plan, current_phase_index, court_name):
    """
    Finds the next activity by looking ahead in the timeline, matching by COURT NAME.
    """
    timeline = plan.get('timeline', [])
    next_phase_index = current_phase_index + 1
    if next_phase_index >= len(timeline):
        return None

    next_phase = timeline[next_phase_index]
    
    # Find the court in the next phase that has the same name (e.g., "Court 1")
    next_court_info = next((c for c in next_phase.get('courts', []) if c and c.get('name') == court_name), None)
    if not next_court_info:
        return None # This court does not exist in the next phase.

    # If the next phase is a Rotation, find the activity for the group that starts on that court.
    if next_phase.get('type') == 'Rotation':
        group_id_on_court = next_court_info.get('assignedGroupIds', [None])[0]
        if group_id_on_court:
            # The activity is defined in the court that "owns" the group initially.
            for court_def in next_phase.get('courts', []):
                if court_def and court_def.get('assignedGroupIds', [None])[0] == group_id_on_court:
                    activities = court_def.get('activities', [])
                    if activities:
                        return {"name": activities[0].get('name')}
    
    # For standard phases, just get the activity directly from the court object.
    else:
        activities = next_court_info.get('activities', [])
        if activities:
            return {"name": activities[0].get('name')}
        else:
            return {"name": "General Activities"}
            
    return None

@login_required
def live_session_display(request, session_id):
    """Renders the main page, allowing access for superusers or assigned coaches."""
    if request.user.is_superuser:
        session = get_object_or_404(Session, pk=session_id)
    else:
        coach_profile = get_object_or_404(Coach, user=request.user)
        session = get_object_or_404(Session, pk=session_id, coaches_attending=coach_profile)
    return render(request, 'live_session/live_session_display.html', {'session': session})

@login_required
def live_session_update_api(request, session_id):
    """API endpoint, allowing access for superusers or assigned coaches."""
    if request.user.is_superuser:
        session = get_object_or_404(Session, pk=session_id)
    else:
        coach_profile = get_object_or_404(Coach, user=request.user)
        session = get_object_or_404(Session.objects.prefetch_related('coaches_attending__user', 'attendees'), pk=session_id, coaches_attending=coach_profile)

    # --- NEW: Simplified Title Generation ---
    group_name = session.school_group.name if session.school_group else "General"
    start_time_str = session.session_start_time.strftime('%H:%M')
    end_time_str = (session.start_datetime + timezone.timedelta(minutes=session.planned_duration_minutes)).strftime('%H:%M')
    session_title = f"{group_name} : {start_time_str} - {end_time_str}"

    if session.status == 'pending' or not session.start_time:
        now = timezone.now()
        start_datetime = session.start_datetime
        if now < start_datetime:
            time_to_start = (start_datetime - now).total_seconds()
            
            # Fetch assigned coaches and confirmed attendees
            coaches = [coach.user.get_full_name() or coach.user.username for coach in session.coaches_attending.all()]
            
            # --- MODIFICATION ---
            # Prioritize coach-marked attendance. Fallback to parent-confirmed.
            coach_marked_qs = AttendanceTracking.objects.filter(session=session, attended=AttendanceTracking.CoachAttended.YES)
            
            if coach_marked_qs.exists():
                # Use players the coach marked as present
                attendee_pks = coach_marked_qs.values_list('player_id', flat=True)
            else:
                # Fallback to players whose parents confirmed they are attending
                attendee_pks = AttendanceTracking.objects.filter(session=session, parent_response=AttendanceTracking.ParentResponse.ATTENDING).values_list('player_id', flat=True)
            
            attendees = [
                player.full_name for player in
                Player.objects.filter(pk__in=attendee_pks)
            ]
            
            return JsonResponse({
                'sessionStatus': 'not_yet_started',
                'sessionTitle': session_title,
                'timeToStart': time_to_start,
                'coaches': sorted(coaches),
                'attendees': sorted(attendees),
            })
        else:
             # If the session was supposed to start but isn't active, treat it as pending
            return JsonResponse({'sessionStatus': 'pending', 'sessionTitle': session_title})

    if session.status == 'finished': 
        return JsonResponse({'sessionStatus': 'finished', 'sessionTitle': session_title})

    try:
        plan = session.plan if isinstance(session.plan, dict) else json.loads(session.plan)
        if not plan or 'timeline' not in plan:
            return JsonResponse({'status': 'error', 'message': 'Session plan is invalid.'}, status=400)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Could not parse session plan.'}, status=400)

    now = timezone.now()
    elapsed_seconds = int((now - session.start_time).total_seconds())
    total_duration_seconds = sum(int(p.get('duration', 0)) * 60 for p in plan.get('timeline', []))
    time_left_session = max(0, total_duration_seconds - elapsed_seconds)

    if total_duration_seconds > 0 and elapsed_seconds > total_duration_seconds:
        session.status = 'finished'; session.end_time = now; session.save()
        return JsonResponse({'sessionStatus': 'finished'})

    current_phase, elapsed_in_phase, current_phase_index = find_current_phase(plan, elapsed_seconds)
    if not current_phase: return JsonResponse({'sessionStatus': 'finished'})

    time_left_phase = max(0, (int(current_phase.get('duration', 0)) * 60) - elapsed_in_phase)
    all_player_ids = {pid for grp in plan.get('playerGroups', []) for pid in grp.get('player_ids', [])}
    players_map = {p.id: p.full_name for p in Player.objects.filter(id__in=all_player_ids)}
    player_groups_map = {g['id']: g for g in plan.get('playerGroups', [])}
    courts_data = []

    for court in current_phase.get('courts', []):
        court_id = court.get('id')
        court_name = court.get('name')
        activity_details = get_activity_details(current_phase, court_id, elapsed_in_phase, player_groups_map, players_map)
        next_activity = get_next_activity_for_court(plan, current_phase_index, court_name)
        
        if activity_details:
            courts_data.append({
                "courtName": court_name, "playerGroup": activity_details['group'],
                "players": activity_details['players'],
                "currentActivity": { "name": activity_details['name'], "timeLeft": activity_details['timeLeft'], "duration": activity_details['duration'] },
                "nextActivity": next_activity
            })

    response_data = {
        'sessionStatus': session.status, 'sessionTitle': session_title, 'totalTimeLeft': time_left_session,
        'currentPhase': { 'name': current_phase.get('name', 'Unnamed Phase'), 'timeLeft': time_left_phase, 'duration': int(current_phase.get('duration', 0)) * 60 },
        'courts': courts_data
    }
    return JsonResponse(response_data)

@login_required
def experimental_planner(request, session_id):
    """
    Experimental view for the new React-based planner.
    Fetches all drills and players for the specific session to pass to the frontend.
    """
    session = get_object_or_404(Session, pk=session_id)
    
    # Fetch players: prioritize coach-marked attendance, then parent-confirmed, then all attendees
    coach_marked_qs = AttendanceTracking.objects.filter(session=session, attended=AttendanceTracking.CoachAttended.YES)
    if coach_marked_qs.exists():
        attendee_pks = coach_marked_qs.values_list('player_id', flat=True)
    else:
        # Fallback to players whose parents confirmed they are attending
        attendee_pks = AttendanceTracking.objects.filter(session=session, parent_response=AttendanceTracking.ParentResponse.ATTENDING).values_list('player_id', flat=True)
    
    # If no tracking data, fall back to the session's many-to-many attendees
    if not attendee_pks:
        players = session.attendees.all().values('id', 'first_name', 'last_name')
    else:
        players = Player.objects.filter(pk__in=attendee_pks).values('id', 'first_name', 'last_name')

    drills = Drill.objects.all().values('id', 'name', 'category', 'difficulty', 'description', 'duration_minutes')
    
    context = {
        'session_id': session.id,
        'drills_json': json.dumps(list(drills)),
        'players_json': json.dumps(list(players)),
    }
    return render(request, 'live_session/planner_v2.html', context)
import json
from datetime import datetime
from django.utils import timezone
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from scheduling.models import Session
from accounts.models import Coach

def find_current_phase(plan, elapsed_seconds):
    """Finds the current phase and its elapsed time."""
    cumulative_duration = 0
    timeline = plan.get('timeline', [])
    for phase in timeline:
        phase_duration = int(phase.get('duration', 0)) * 60
        if elapsed_seconds < cumulative_duration + phase_duration:
            return phase, elapsed_seconds - cumulative_duration
        cumulative_duration += phase_duration
    return None, 0

def get_activity_details(phase, court_id, elapsed_in_phase, player_groups_map):
    """
    Finds the current activity, group, time left, and total duration for a court.
    This version is tailored to your specific JSON structure.
    """
    phase_type = phase.get('type')
    group_name = "N/A"
    activity_name = "Transitioning"
    time_left = (int(phase.get('duration', 0)) * 60) - elapsed_in_phase
    duration = int(phase.get('duration', 0)) * 60

    if phase_type == 'Rotation':
        rotation_duration_min = phase.get('rotationDuration', 0)
        # Check if rotationDuration is present and not zero
        if rotation_duration_min > 0:
            rotation_duration_sec = rotation_duration_min * 60
            rotation_num = int(elapsed_in_phase // rotation_duration_sec)
            sub_blocks = phase.get('sub_blocks', [])
            
            if rotation_num < len(sub_blocks):
                current_assignments = sub_blocks[rotation_num].get('assignments', {})
                group_id = current_assignments.get(court_id)
                if group_id and group_id in player_groups_map:
                    group_name = player_groups_map[group_id].get('name', 'N/A')

                # Find the activity associated with the *currently rotating group*
                for c in phase.get('courts', []):
                    initial_group_for_court = c.get('assignedGroupIds', [None])[0]
                    if initial_group_for_court == group_id and c.get('activities'):
                        activity_name = c['activities'][0].get('name', 'Unnamed Drill')
                        break
            
            time_left = rotation_duration_sec - (elapsed_in_phase % rotation_duration_sec)
            duration = rotation_duration_sec
    else:
        # Standard phases like Warmup or Freeplay
        court_info = next((c for c in phase.get('courts', []) if c.get('id') == court_id), None)
        if court_info:
            assigned_group_ids = court_info.get('assignedGroupIds', [])
            # For Warmup, multiple groups can be on one court. We'll list them.
            group_names = [player_groups_map.get(gid, {}).get('name') for gid in assigned_group_ids]
            group_name = ', '.join(filter(None, group_names)) or 'N/A'

            activities = court_info.get('activities', [])
            if activities:
                # Assuming one main activity for the whole phase block
                activity = activities[0]
                activity_name = activity.get('name', 'Unnamed Activity')
                duration = int(phase.get('duration', 0)) * 60
                time_left = duration - elapsed_in_phase
            else:
                 activity_name = "Free Play"

    return {
        "name": activity_name,
        "group": group_name,
        "timeLeft": time_left,
        "duration": duration
    }

@login_required
def live_session_display(request, session_id):
    """Renders the main page for the live session display."""
    coach_profile = get_object_or_404(Coach, user=request.user)
    session = get_object_or_404(Session, pk=session_id, coaches_attending=coach_profile)
    return render(request, 'live_session/live_session_display.html', {'session': session})

@login_required
def live_session_update_api(request, session_id):
    """API endpoint that provides the real-time state of a session."""
    coach_profile = get_object_or_404(Coach, user=request.user)
    session = get_object_or_404(Session, pk=session_id, coaches_attending=coach_profile)

    if session.status == 'pending' or not session.start_time:
        return JsonResponse({'sessionStatus': 'pending'})

    if session.status == 'finished':
        return JsonResponse({'sessionStatus': 'finished'})

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

    current_phase, elapsed_in_phase = find_current_phase(plan, elapsed_seconds)
    if not current_phase:
        return JsonResponse({'sessionStatus': 'finished'})

    time_left_phase = max(0, (int(current_phase.get('duration', 0)) * 60) - elapsed_in_phase)
    player_groups_map = {g['id']: g for g in plan.get('playerGroups', [])}
    courts_data = []

    for court in current_phase.get('courts', []):
        court_id = court.get('id')
        activity_details = get_activity_details(current_phase, court_id, elapsed_in_phase, player_groups_map)
        
        if activity_details:
            courts_data.append({
                "courtName": court.get('name', 'Unknown Court'),
                "playerGroup": activity_details['group'],
                "currentActivity": { "name": activity_details['name'], "timeLeft": activity_details['timeLeft'], "duration": activity_details['duration'] },
                "nextActivity": None
            })

    response_data = {
        'sessionStatus': session.status, 'sessionTitle': str(session), 'totalTimeLeft': time_left_session,
        'currentPhase': { 'name': current_phase.get('name', 'Unnamed Phase'), 'timeLeft': time_left_phase, 'duration': int(current_phase.get('duration', 0)) * 60 },
        'courts': courts_data
    }
    return JsonResponse(response_data)
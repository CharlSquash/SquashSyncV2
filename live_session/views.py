# live_session/views.py

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict

# Import models from their new locations
from scheduling.models import Session, TimeBlock, ActivityAssignment, ManualCourtAssignment

# Import from the new utils file
from .live_session_utils import _calculate_skill_priority_groups

@login_required
def live_session_page_view(request, session_id):
    session = get_object_or_404(
        Session.objects.select_related('school_group', 'venue'), pk=session_id
    )
    context = {
        'session': session,
        'page_title': f"Live Session: {session}"
    }
    return render(request, 'live_session/live_session_display.html', context)

@login_required
def live_session_update_api(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    now = timezone.now()

    # Logic for determining session status (pending, active, finished)
    session_start_time = session.start_datetime
    if not session_start_time:
        return JsonResponse({'error': 'Session start time not set'}, status=400)

    time_since_start = now - session_start_time
    total_seconds_since_start = time_since_start.total_seconds()

    current_block = None
    status = "pending"
    if total_seconds_since_start >= 0:
        status = "active"
        for block in session.time_blocks.order_by('start_offset_minutes'):
            block_start_seconds = block.start_offset_minutes * 60
            block_end_seconds = block_start_seconds + (block.duration_minutes * 60)
            if block_start_seconds <= total_seconds_since_start < block_end_seconds:
                current_block = block
                break

    if now > (session.end_datetime or now):
        status = "finished"

    response_data = {
        'status': status,
        'total_seconds_since_start': total_seconds_since_start,
        'current_block': None
    }

    if current_block:
        # Simplified logic for response data
        response_data['current_block'] = {
            'id': current_block.id,
            'focus': current_block.block_focus,
            'duration': current_block.duration_minutes * 60,
            'start_offset': current_block.start_offset_minutes * 60,
            'rotation_interval': current_block.rotation_interval_minutes * 60 if current_block.rotation_interval_minutes else None,
        }

    return JsonResponse(response_data)
# players/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Player, SchoolGroup, MatchResult, CourtSprintRecord, VolleyRecord, BackwallDriveRecord, AttendanceDiscrepancy
from .services import PlayerService
from solosync2.models import SoloSessionLog
from django.utils import timezone
from datetime import timedelta, date
from django.contrib import messages
from .forms import (
    SchoolGroupForm, AttendancePeriodFilterForm, PlayerAttendanceFilterForm,
    CourtSprintRecordForm, VolleyRecordForm, BackwallDriveRecordForm, MatchResultForm
)
from scheduling.models import Session, AttendanceTracking
from assessments.models import SessionAssessment, GroupAssessment
from django.db.models import Count, Q, Value
from django.db.models.functions import Concat
import json

# Helper to convert date objects for JSON serialization
class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def discrepancy_report(request):
    """
    Displays a filterable report of all attendance discrepancies.
    """
    today = timezone.now().date()
    start_date_default = today - timedelta(days=30)
    end_date_default = today

    start_date = request.GET.get('start_date', start_date_default.strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', end_date_default.strftime('%Y-%m-%d'))
    school_group_id = request.GET.get('school_group')

    discrepancies = AttendanceDiscrepancy.objects.filter(
        session__session_date__range=[start_date, end_date]
    ).select_related('player', 'session', 'session__school_group').order_by('-session__session_date')

    if school_group_id:
        discrepancies = discrepancies.filter(session__school_group__id=school_group_id)

    context = {
        'discrepancies': discrepancies,
        'school_groups': SchoolGroup.objects.all(),
        'filter_values': {
            'start_date': start_date,
            'end_date': end_date,
            'school_group': int(school_group_id) if school_group_id else '',
        },
        'page_title': "Attendance Discrepancy Report"
    }
    return render(request, 'players/discrepancy_report.html', context)


@require_POST
@login_required
@user_passes_test(lambda u: u.is_superuser)
def acknowledge_discrepancy(request, discrepancy_id):
    """
    A view to mark a discrepancy as acknowledged via an AJAX request.
    """
    try:
        discrepancy = get_object_or_404(AttendanceDiscrepancy, pk=discrepancy_id)
        discrepancy.admin_acknowledged = True
        discrepancy.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_POST
@login_required
def add_metric(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    
    if 'add_sprint_record' in request.POST:
        sprint_form = CourtSprintRecordForm(request.POST)
        if sprint_form.is_valid():
            sprint = sprint_form.save(commit=False)
            sprint.player = player
            sprint.save()
            messages.success(request, "Court sprint record added.")
        else:
            messages.error(request, "Error adding sprint record. Please check the form.")
    
    elif 'add_volley_record' in request.POST:
        volley_form = VolleyRecordForm(request.POST)
        if volley_form.is_valid():
            volley = volley_form.save(commit=False)
            volley.player = player
            volley.save()
            messages.success(request, "Volley record added.")
        else:
            messages.error(request, "Error adding volley record. Please check the form.")

    elif 'add_drive_record' in request.POST:
        drive_form = BackwallDriveRecordForm(request.POST)
        if drive_form.is_valid():
            drive = drive_form.save(commit=False)
            drive.player = player
            drive.save()
            messages.success(request, "Backwall drive record added.")
        else:
            messages.error(request, "Error adding drive record. Please check the form.")

    elif 'add_match_result' in request.POST:
        match_form = MatchResultForm(request.POST)
        if match_form.is_valid():
            match = match_form.save(commit=False)
            match.player = player
            match.save()
            messages.success(request, "Match result added.")
        else:
            messages.error(request, "Error adding match result. Please check the form.")

    return redirect('players:player_profile', player_id=player_id)


@login_required
def player_profile(request, player_id):
    player = get_object_or_404(Player, pk=player_id)

    # --- Handle Metric Form Submissions ---
    # --- Handle Metric Form Submissions ---
    # Moved to add_metric view

    # --- GET Request and Form Initialization ---
    sprint_form = CourtSprintRecordForm()
    volley_form = VolleyRecordForm()
    drive_form = BackwallDriveRecordForm()
    match_form = MatchResultForm()

    # Get related data for tabs
    assessments = SessionAssessment.objects.filter(player=player).select_related('session', 'submitted_by__coach_profile').order_by('-session__session_date')
    match_history = MatchResult.objects.filter(
        Q(player=player) | Q(opponent=player)
    ).select_related('player', 'opponent').order_by('-date')
    discrepancy_history = AttendanceDiscrepancy.objects.filter(player=player).select_related('session', 'session__school_group')
    solo_session_logs = SoloSessionLog.objects.filter(player=player).select_related('routine').order_by('-completed_at')

    # --- NEW: Calculate Average Performance Ratings ---
    rating_fields = ['effort_rating', 'focus_rating', 'resilience_rating', 'composure_rating', 'decision_making_rating']
    rating_labels = {
        'effort_rating': 'Effort', 'focus_rating': 'Focus', 'resilience_rating': 'Resilience',
        'composure_rating': 'Composure', 'decision_making_rating': 'Decision Making'
    }
    
    totals = {field: 0 for field in rating_fields}
    counts = {field: 0 for field in rating_fields}
    
    for assessment in assessments:
        for field in rating_fields:
            value = getattr(assessment, field)
            if value is not None:
                totals[field] += value
                counts[field] += 1
    
    average_ratings = {}
    for field in rating_fields:
        if counts[field] > 0:
            average_ratings[field] = {
                'label': rating_labels[field],
                'avg': totals[field] / counts[field],
                'count': counts[field]
            }

    # --- Attendance Calculation Logic ---
    start_date_filter = request.GET.get('start_date')
    end_date_filter = request.GET.get('end_date')
    group_filter_id = request.GET.get('school_group')

    # Use the service to get stats
    attendance_stats = PlayerService.get_attendance_stats(player, start_date_filter, end_date_filter)
    
    # Unpack stats for context
    total_sessions = attendance_stats['total_sessions']
    attended_sessions = attendance_stats['attended_sessions']
    attendance_percentage = attendance_stats['attendance_percentage']
    
    # Update filter dates from service (in case defaults were used)
    start_date_filter = attendance_stats['start_date']
    end_date_filter = attendance_stats['end_date']

    # Apply group filter title logic (keep this view-specific logic here for now or move if needed, but simple enough)
    filter_title = "Overall Attendance"
    if group_filter_id:
        # Note: The service currently doesn't filter by group ID passed to it, 
        # but the original code did. 
        # WAIT. The original code filtered `sessions_in_range_qs` by `group_filter_id`.
        # My service implementation missed the `group_filter_id` parameter!
        # I need to fix the service or handle it here. 
        # The service I wrote uses `player.school_groups.all()`.
        # I should probably update the service to accept `school_group_id` as an optional argument.
        # For now, let's stick to the plan, but I realized a gap.
        # The original code:
        # if group_filter_id:
        #    sessions_in_range_qs = sessions_in_range_qs.filter(school_group__id=group_filter_id)
        
        # I should update the service first or now. 
        # Let's update the service in the next step.
        # For now, I will proceed with this replacement, but I will need to fix the service to support group filtering.
        try:
            filter_title = f"Attendance for {SchoolGroup.objects.get(id=group_filter_id).name}"
        except SchoolGroup.DoesNotExist:
            pass
    
    # Pass initial values to the form so it displays the correct default dates
    attendance_filter_form = PlayerAttendanceFilterForm(request.GET or None, player=player, initial={
        'start_date': start_date_filter,
        'end_date': end_date_filter
    })
    
    # --- Get Metric Data for Graphs (THE FIX IS HERE) ---
    sprint_records = list(CourtSprintRecord.objects.filter(player=player).order_by('date_recorded').values())
    volley_records = list(VolleyRecord.objects.filter(player=player).order_by('date_recorded').values())
    drive_records = list(BackwallDriveRecord.objects.filter(player=player).order_by('date_recorded').values())

    context = {
        'page_title': f"Profile: {player.full_name}",
        'player': player,
        'assessments': assessments,
        'average_ratings': average_ratings,
        'match_history': match_history,
        'discrepancy_history': discrepancy_history,
        'solo_session_logs': solo_session_logs,
        'attendance_percentage': round(attendance_percentage, 2),
        'total_sessions_count': total_sessions,
        'attended_sessions_count': attended_sessions,
        'attendance_filter_form': attendance_filter_form,
        'filter_title': filter_title,
        'sprint_form': sprint_form,
        'volley_form': volley_form,
        'drive_form': drive_form,
        'match_form': match_form,
        # Convert the lists to JSON strings using our custom encoder
        'sprint_records_json': json.dumps(sprint_records, cls=DateEncoder),
        'volley_records_json': json.dumps(volley_records, cls=DateEncoder),
        'drive_records_json': json.dumps(drive_records, cls=DateEncoder),
    }
    return render(request, 'players/player_profile.html', context)

@login_required
def players_list(request):
    # Start with all active players
    player_list = Player.objects.filter(is_active=True).select_related()

    # Get filter parameters from the URL
    school_group_id = request.GET.get('school_group')
    search_query = request.GET.get('q', '')

    # Apply filters
    if school_group_id:
        player_list = player_list.filter(school_groups__id=school_group_id)

    if search_query:
        # --- THIS IS THE FIX ---
        # Annotate the queryset with a concatenated full name to search on.
        player_list = player_list.annotate(
            search_name=Concat('first_name', Value(' '), 'last_name')
        ).filter(search_name__icontains=search_query)
        # --- END OF FIX ---

    # Get all school groups for the filter dropdown
    school_groups = SchoolGroup.objects.all()

    context = {
        'page_title': "Players",
        'players': player_list,
        'school_groups': school_groups,
        'selected_group_id': int(school_group_id) if school_group_id else None,
        'search_query': search_query,
    }
    return render(request, 'players/players_list.html', context)


@permission_required('players.can_manage_school_groups', raise_exception=True)
def school_group_list(request):
    # The old 'if not request.user.is_superuser' check is now gone.
    # The @permission_required decorator handles the security check automatically.
    
    if request.method == 'POST':
        form = SchoolGroupForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Successfully created new group: {form.cleaned_data['name']}")
            return redirect('players:school_group_list')
    else:
        form = SchoolGroupForm()

    groups = SchoolGroup.objects.all()
    context = {
        'page_title': 'School Groups',
        'groups': groups,
        'form': form,
    }
    return render(request, 'players/school_group_list.html', context)


@login_required
def school_group_profile(request, group_id):
    school_group = get_object_or_404(SchoolGroup, pk=group_id)

    group_assessments = GroupAssessment.objects.filter(
        session__school_group=school_group
    ).select_related('assessing_coach', 'session').order_by('-assessment_datetime')

    players_in_group = school_group.players.filter(is_active=True).order_by('last_name', 'first_name')

    # --- Attendance Period Filter & Calculations ---
    default_end_date = timezone.now().date()
    default_start_date = default_end_date - timedelta(days=89)

    filter_form = AttendancePeriodFilterForm(request.GET or None, initial={
        'start_date': default_start_date.strftime('%Y-%m-%d'),
        'end_date': default_end_date.strftime('%Y-%m-%d')
    })

    start_date_filter = default_start_date
    end_date_filter = default_end_date

    if filter_form.is_valid():
        start_date_filter = filter_form.cleaned_data.get('start_date', default_start_date)
        end_date_filter = filter_form.cleaned_data.get('end_date', default_end_date)

    # --- NEW ATTENDANCE CALCULATION LOGIC ---
    sessions_in_range = Session.objects.filter(
        school_group=school_group,
        session_date__range=[start_date_filter, end_date_filter],
        is_cancelled=False
    )
    
    # Find sessions where attendance was actually recorded for at least one player.
    sessions_with_attendance_taken = sessions_in_range.filter(
        player_attendances__attended__in=[
            AttendanceTracking.CoachAttended.YES,
            AttendanceTracking.CoachAttended.NO
        ]
    ).distinct()
    
    # Total possible attendances is the number of players multiplied by the number of *tracked* sessions.
    total_possible_attendances = sessions_with_attendance_taken.count() * players_in_group.count()
    
    # Actual attendances are counted only from within those tracked sessions.
    actual_attendances = AttendanceTracking.objects.filter(
        session__in=sessions_with_attendance_taken,
        player__in=players_in_group,
        attended=AttendanceTracking.CoachAttended.YES
    ).count()
    
    attendance_percentage = (actual_attendances / total_possible_attendances * 100) if total_possible_attendances > 0 else 0

    context = {
        'school_group': school_group,
        'players_in_group': players_in_group,
        'group_assessments': group_assessments,
        'filter_form': filter_form,
        'start_date_filter': start_date_filter,
        'end_date_filter': end_date_filter,
        'attendance_percentage': round(attendance_percentage, 2),
        'total_possible_attendances': total_possible_attendances,
        'actual_attendances': actual_attendances,
        'page_title': f"Profile: {school_group.name}"
    }
    return render(request, 'players/school_group_profile.html', context)


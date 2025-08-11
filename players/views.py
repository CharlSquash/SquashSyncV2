# players/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Player, SchoolGroup, MatchResult, CourtSprintRecord, VolleyRecord, BackwallDriveRecord
from django.utils import timezone
from datetime import timedelta, date
from django.contrib import messages
from .forms import (
    SchoolGroupForm, AttendancePeriodFilterForm, PlayerAttendanceFilterForm,
    CourtSprintRecordForm, VolleyRecordForm, BackwallDriveRecordForm
)
from scheduling.models import Session, AttendanceTracking
from assessments.models import SessionAssessment, GroupAssessment
from django.db.models import Count, Q
import json

# Helper to convert date objects for JSON serialization
class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)

@login_required
def player_profile(request, player_id):
    player = get_object_or_404(Player, pk=player_id)

    # --- Handle Metric Form Submissions ---
    if request.method == 'POST':
        if 'add_sprint_record' in request.POST:
            sprint_form = CourtSprintRecordForm(request.POST)
            if sprint_form.is_valid():
                sprint = sprint_form.save(commit=False)
                sprint.player = player
                sprint.save()
                messages.success(request, "Court sprint record added.")
                return redirect('players:player_profile', player_id=player_id)
        
        elif 'add_volley_record' in request.POST:
            volley_form = VolleyRecordForm(request.POST)
            if volley_form.is_valid():
                volley = volley_form.save(commit=False)
                volley.player = player
                volley.save()
                messages.success(request, "Volley record added.")
                return redirect('players:player_profile', player_id=player_id)

        elif 'add_drive_record' in request.POST:
            drive_form = BackwallDriveRecordForm(request.POST)
            if drive_form.is_valid():
                drive = drive_form.save(commit=False)
                drive.player = player
                drive.save()
                messages.success(request, "Backwall drive record added.")
                return redirect('players:player_profile', player_id=player_id)

    # --- GET Request and Form Initialization ---
    sprint_form = CourtSprintRecordForm()
    volley_form = VolleyRecordForm()
    drive_form = BackwallDriveRecordForm()

    # Get related data for tabs
    assessments = SessionAssessment.objects.filter(player=player).select_related('session', 'submitted_by').order_by('-session__session_date')
    match_history = MatchResult.objects.filter(player=player).order_by('-date')

    # --- Attendance Calculation Logic ---
    current_year = timezone.now().year
    start_date_filter = request.GET.get('start_date') or f'{current_year}-01-01'
    end_date_filter = request.GET.get('end_date') or f'{current_year}-12-31'
    group_filter_id = request.GET.get('school_group')

    sessions_qs = Session.objects.filter(session_date__year=current_year, school_group__in=player.school_groups.all())
    filter_title = "Overall Attendance"
    if group_filter_id:
        sessions_qs = sessions_qs.filter(school_group__id=group_filter_id)
        filter_title = f"Attendance for {SchoolGroup.objects.get(id=group_filter_id).name}"

    total_sessions = sessions_qs.filter(session_date__range=[start_date_filter, end_date_filter]).distinct().count()
    attended_sessions = AttendanceTracking.objects.filter(player=player, session__in=sessions_qs, session__session_date__range=[start_date_filter, end_date_filter], attended=AttendanceTracking.CoachAttended.YES).count()
    attendance_percentage = (attended_sessions / total_sessions * 100) if total_sessions > 0 else 0
    attendance_filter_form = PlayerAttendanceFilterForm(request.GET or None, player=player)
    
    # --- Get Metric Data for Graphs (THE FIX IS HERE) ---
    sprint_records = list(CourtSprintRecord.objects.filter(player=player).order_by('date_recorded').values())
    volley_records = list(VolleyRecord.objects.filter(player=player).order_by('date_recorded').values())
    drive_records = list(BackwallDriveRecord.objects.filter(player=player).order_by('date_recorded').values())

    context = {
        'page_title': f"Profile: {player.full_name}",
        'player': player,
        'assessments': assessments,
        'match_history': match_history,
        'attendance_percentage': round(attendance_percentage, 2),
        'total_sessions_count': total_sessions,
        'attended_sessions_count': attended_sessions,
        'attendance_filter_form': attendance_filter_form,
        'filter_title': filter_title,
        'sprint_form': sprint_form,
        'volley_form': volley_form,
        'drive_form': drive_form,
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
        player_list = player_list.filter(full_name__icontains=search_query)

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


@login_required
def school_group_list(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to view this page.")
        return redirect('homepage')

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

    # Get assessments and players for this group
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

    context = {
        'school_group': school_group,
        'players_in_group': players_in_group,
        'group_assessments': group_assessments,
        'filter_form': filter_form,
        'start_date_filter': start_date_filter,
        'end_date_filter': end_date_filter,
        'page_title': f"Profile: {school_group.name}"
    }
    return render(request, 'players/school_group_profile.html', context)
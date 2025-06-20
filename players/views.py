from django.shortcuts import render
from django.shortcuts import get_object_or_404

# Create your views here.
# players/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Player, SchoolGroup, MatchResult

from django.utils import timezone
from datetime import timedelta

from django.shortcuts import redirect
from django.contrib import messages
from .forms import SchoolGroupForm, AttendancePeriodFilterForm 


from scheduling.models import Session
from assessments.models import SessionAssessment, GroupAssessment

@login_required
def player_profile(request, player_id):
    player = get_object_or_404(Player, pk=player_id)

    # Get related data
    sessions_attended = player.attended_sessions.order_by('-session_date')
    assessments = SessionAssessment.objects.filter(player=player).select_related('session', 'submitted_by').order_by('-session__session_date')
    match_history = MatchResult.objects.filter(player=player).order_by('-date')

    # We will add metric records (sprints, volleys, etc.) and their forms later

    context = {
        'page_title': f"Profile: {player.full_name}",
        'player': player,
        'sessions_attended': sessions_attended,
        'assessments': assessments,
        'match_history': match_history,
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
    # For simplicity, we'll implement a basic version of the attendance calculation for now.
    # The complex historical calculation can be a future enhancement.
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
        # Note: The detailed attendance stats are complex and will be added back later.
    }
    return render(request, 'players/school_group_profile.html', context)
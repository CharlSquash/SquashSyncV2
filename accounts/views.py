# accounts/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import calendar

from .models import Coach
from .forms import MonthYearFilterForm
from scheduling.models import Session
from assessments.models import SessionAssessment, GroupAssessment
from finance.models import CoachSessionCompletion

def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser, login_url='scheduling:homepage')
def coach_list(request):
    """
    Displays a list of all active coaches for superuser administration.
    """
    coaches = Coach.objects.filter(is_active=True).select_related('user').order_by('user__first_name', 'user__last_name')
    context = {
        'coaches': coaches,
        'page_title': "Coach Profiles"
    }
    return render(request, 'accounts/coach_list.html', context)

@login_required
def coach_profile(request, coach_id=None):
    """
    Displays a profile for a coach.
    - If coach_id is provided, an admin is viewing a specific coach's profile.
    - If coach_id is None, the logged-in coach is viewing their own profile.
    """
    target_coach = None
    
    if coach_id:
        if not request.user.is_superuser:
            messages.error(request, "You are not authorized to view this profile.")
            return redirect('scheduling:homepage')
        target_coach = get_object_or_404(Coach, pk=coach_id)
    else:
        try:
            target_coach = request.user.coach_profile
        except Coach.DoesNotExist:
            messages.error(request, "Your user account is not linked to a Coach profile.")
            return redirect('scheduling:homepage')

    # --- UPDATED DATA FETCHING LOGIC ---
    completed_sessions = CoachSessionCompletion.objects.filter(
        coach=target_coach,
        assessments_submitted=True
    ).select_related(
        'session', 'session__school_group', 'session__venue'
    ).order_by('-session__session_date', '-session__session_start_time')
    
    sessions_attended = [comp.session for comp in completed_sessions]
    
    two_weeks_ago = timezone.now().date() - timedelta(weeks=2)
    
    player_assessments_made = SessionAssessment.objects.filter(
        submitted_by=target_coach.user
    ).select_related('player', 'session').order_by('-date_recorded')

    group_assessments_made = GroupAssessment.objects.filter(
        assessing_coach=target_coach.user
    ).select_related('session__school_group').order_by('-assessment_datetime')


    context = {
        'coach': target_coach,
        'viewing_own_profile': target_coach.user == request.user,
        'sessions_attended': sessions_attended,
        'player_assessments_made': player_assessments_made,
        'group_assessments_made': group_assessments_made,
        'two_weeks_ago': two_weeks_ago,
        'page_title': f"Coach Profile: {target_coach.user.get_full_name()}"
    }
    return render(request, 'accounts/coach_profile.html', context)
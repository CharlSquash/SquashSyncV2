# accounts/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
import calendar

from .models import Coach
from .forms import MonthYearFilterForm
from scheduling.models import Session
from assessments.models import SessionAssessment, GroupAssessment

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
        # Admin is viewing a specific coach's profile
        if not request.user.is_superuser:
            messages.error(request, "You are not authorized to view this profile.")
            return redirect('scheduling:homepage')
        target_coach = get_object_or_404(Coach, pk=coach_id)
    else:
        # A coach is viewing their own profile
        try:
            target_coach = request.user.coach_profile
        except Coach.DoesNotExist:
            messages.error(request, "Your user account is not linked to a Coach profile.")
            return redirect('scheduling:homepage')

    # Data gathering logic
    sessions_attended = Session.objects.filter(coaches_attending=target_coach).order_by('-session_date')[:10]
    assessments_made = SessionAssessment.objects.filter(submitted_by=target_coach.user).order_by('-date_recorded')[:5]

    context = {
        'coach': target_coach,
        'viewing_own_profile': target_coach.user == request.user,
        'sessions_attended': sessions_attended,
        'assessments_made': assessments_made,
        'page_title': f"Coach Profile: {target_coach.user.get_full_name()}"
    }
    return render(request, 'accounts/coach_profile.html', context)

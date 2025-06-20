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

@login_required
@user_passes_test(lambda u: u.is_superuser) # Only superusers can see the list
def coach_list_view(request):
    coaches = Coach.objects.filter(is_active=True).select_related('user').order_by('name')
    context = {
        'coaches': coaches,
        'page_title': "All Coaches"
    }
    return render(request, 'accounts/coach_list.html', context)

@login_required
def coach_profile_view(request, coach_id=None):
    target_coach_profile = None
    viewing_own_profile = False

    if coach_id:
        # An admin is viewing a specific coach's profile
        if not request.user.is_superuser:
            messages.error(request, "You are not authorized to view this profile.")
            return redirect('homepage')
        target_coach_profile = get_object_or_404(Coach, pk=coach_id)
    else:
        # A coach is viewing their own profile
        try:
            target_coach_profile = Coach.objects.get(user=request.user)
            viewing_own_profile = True
        except Coach.DoesNotExist:
            messages.error(request, "Your user account is not linked to a Coach profile.")
            return redirect('homepage')

    # --- Data gathering logic ---
    sessions_attended = Session.objects.filter(coaches_attending=target_coach_profile).order_by('-session_date')[:10]
    assessments_made = SessionAssessment.objects.filter(submitted_by=target_coach_profile.user).order_by('-date_recorded')[:5]

    context = {
        'coach': target_coach_profile,
        'viewing_own_profile': viewing_own_profile,
        'sessions_attended': sessions_attended,
        'assessments_made': assessments_made,
        'page_title': f"Coach Profile: {target_coach_profile.name}"
    }
    return render(request, 'accounts/coach_profile.html', context)
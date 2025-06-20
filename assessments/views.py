# assessments/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from players.models import Player
from datetime import timedelta
# Import models from their new app locations
from scheduling.models import Session
from .models import SessionAssessment, GroupAssessment

from .forms import SessionAssessmentForm, GroupAssessmentForm 

@login_required
def pending_assessments(request):
    """
    Shows a coach the sessions they have coached but not yet submitted
    player and/or group assessments for.
    """
    coach_user = request.user

    # Look at sessions in the last 14 days that the coach was assigned to.
    two_weeks_ago = timezone.now().date() - timedelta(days=14)
    coached_sessions = Session.objects.filter(
        coaches_attending__user=coach_user,
        session_date__gte=two_weeks_ago,
        is_cancelled=False
    ).prefetch_related('attendees')

    # Get IDs of sessions for which this coach has already submitted assessments
    submitted_player_assessments = SessionAssessment.objects.filter(
        submitted_by=coach_user
    ).values_list('session__id', flat=True).distinct()

    submitted_group_assessments = GroupAssessment.objects.filter(
        assessing_coach=coach_user
    ).values_list('session__id', flat=True).distinct()

    pending_list = []
    for session in coached_sessions:
        # Check if player assessments are needed
        player_assess_needed = False
        if session.id not in submitted_player_assessments and session.attendees.exists():
            player_assess_needed = True

        # Check if group assessment is needed
        group_assess_needed = False
        if session.id not in submitted_group_assessments:
            group_assess_needed = True

        if player_assess_needed or group_assess_needed:
            pending_list.append({
                'session': session,
                'player_assess_needed': player_assess_needed,
                'group_assess_needed': group_assess_needed
            })

    context = {
        'page_title': "My Pending Assessments",
        'pending_list': pending_list,
    }
    return render(request, 'assessments/pending_assessments.html', context)

@login_required
def assess_player_session(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    # Get players who attended the session
    players_to_assess = session.attendees.all()

    # Create a formset - one form for each player
    AssessmentFormSet = modelformset_factory(
        SessionAssessment,
        form=SessionAssessmentForm,
        extra=len(players_to_assess)
    )

    if request.method == 'POST':
        formset = AssessmentFormSet(request.POST)
        if formset.is_valid():
            assessments = formset.save(commit=False)
            for assessment, player in zip(assessments, players_to_assess):
                assessment.session = session
                assessment.player = player
                assessment.submitted_by = request.user
                assessment.save()

            messages.success(request, f"Assessments for session on {session.session_date} have been saved.")
            return redirect('assessments:pending_assessments')
    else:
        # Pre-populate existing assessments for editing
        initial_data = []
        for player in players_to_assess:
            assessment, created = SessionAssessment.objects.get_or_create(
                session=session,
                player=player,
                submitted_by=request.user
            )
            initial_data.append({'instance': assessment})

        formset = AssessmentFormSet(
            queryset=SessionAssessment.objects.filter(session=session, player__in=players_to_assess, submitted_by=request.user),
            initial=initial_data
        )

    # Pair up each form with its corresponding player
    player_form_pairs = zip(players_to_assess, formset.forms)

    context = {
        'page_title': 'Assess Player Performance',
        'session': session,
        'player_form_pairs': player_form_pairs,
        'formset': formset,
    }
    return render(request, 'assessments/assess_player_form.html', context)

@login_required
def add_edit_group_assessment(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    # Try to get an existing assessment for this user and session, or None
    assessment = GroupAssessment.objects.filter(session=session, assessing_coach=request.user).first()

    if request.method == 'POST':
        form = GroupAssessmentForm(request.POST, instance=assessment)
        if form.is_valid():
            new_assessment = form.save(commit=False)
            new_assessment.session = session
            new_assessment.assessing_coach = request.user
            new_assessment.save()
            messages.success(request, "Group assessment has been saved.")
            return redirect('assessments:pending_assessments')
    else:
        form = GroupAssessmentForm(instance=assessment)

    context = {
        'page_title': 'Group Session Assessment' if not assessment else 'Edit Group Session Assessment',
        'form': form,
        'session': session
    }
    return render(request, 'assessments/add_edit_group_assessment.html', context)
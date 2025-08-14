# assessments/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.db.models import Prefetch
from collections import defaultdict
from django.http import Http404, JsonResponse
from django.contrib.auth.models import User

from accounts.models import Coach
from scheduling.models import Session
from players.models import Player
from finance.models import CoachSessionCompletion
from .models import SessionAssessment, GroupAssessment
from .forms import SessionAssessmentForm, GroupAssessmentForm

def is_coach(user):
    return user.is_staff and not user.is_superuser

@login_required
@user_passes_test(is_coach, login_url='scheduling:homepage')
def pending_assessments(request):
    """
    Displays a list of past sessions for a coach that are pending either
    player assessments or a group assessment, using a robust multi-query approach.
    """
    try:
        coach = request.user.coach_profile
    except Coach.DoesNotExist:
        messages.error(request, "Your user account is not linked to a Coach profile.")
        return redirect('scheduling:homepage')

    date_limit_past = timezone.now().date() - timedelta(weeks=4)
    today = timezone.now().date()

    # --- Multi-Query Processing Approach ---
    sessions_qs = Session.objects.filter(
        coaches_attending=coach,
        session_date__gte=date_limit_past,
        session_date__lte=today,
        is_cancelled=False
    ).select_related('school_group', 'venue').order_by('-session_date', '-session_start_time')

    session_ids = [s.id for s in sessions_qs]
    player_assessments_done = set(
        CoachSessionCompletion.objects.filter(
            coach=coach, session_id__in=session_ids, assessments_submitted=True
        ).values_list('session_id', flat=True)
    )
    group_assessments_done = set(
        GroupAssessment.objects.filter(
            assessing_coach=request.user, session_id__in=session_ids
        ).values_list('session_id', flat=True)
    )
    session_attendees = Session.attendees.through.objects.filter(
        session_id__in=session_ids
    ).values_list('session_id', 'player_id')
    player_pks_to_fetch = {player_pk for _, player_pk in session_attendees}

    # FIX: Removing the failing .select_related('user') call.
    # We will rely on Django's default behavior to fetch the user when needed.
    players_by_pk = {
        p.pk: p for p in Player.objects.filter(pk__in=player_pks_to_fetch)
    }

    attendees_by_session = defaultdict(list)
    for session_id, player_pk in session_attendees:
        if player_pk in players_by_pk:
            attendees_by_session[session_id].append(players_by_pk[player_pk])

    assessments_by_coach = SessionAssessment.objects.filter(
        submitted_by=request.user, session_id__in=session_ids
    )
    assessments_by_session_id = defaultdict(list)
    for assessment in assessments_by_coach:
        assessments_by_session_id[assessment.session_id].append(assessment)

    pending_items_for_template = []
    for session in sessions_qs:
        is_player_assessment_done = session.id in player_assessments_done
        is_group_assessment_done = session.id in group_assessments_done
        if is_player_assessment_done and is_group_assessment_done:
            continue
        if session.end_datetime and session.end_datetime > timezone.now():
            continue
        players_in_session = attendees_by_session.get(session.id, [])
        assessments_for_this_session = assessments_by_session_id.get(session.id, [])
        assessed_player_pks = {a.player_id for a in assessments_for_this_session}
        players_to_assess = [p for p in players_in_session if p.pk not in assessed_player_pks]
        can_mark_complete = False
        if not is_player_assessment_done and players_in_session:
            if not players_to_assess or len(assessed_player_pks) > 0:
                can_mark_complete = True
        pending_items_for_template.append({
            'session': session,
            'players_to_assess': players_to_assess,
            'player_assessments_pending': not is_player_assessment_done,
            'group_assessment_pending': not is_group_assessment_done,
            'can_mark_player_assessments_complete': can_mark_complete,
        })
    context = {
        'pending_items': pending_items_for_template,
        'page_title': "My Pending Assessments"
    }
    return render(request, 'assessments/pending_assessments.html', context)


@login_required
@require_POST
@user_passes_test(is_coach, login_url='scheduling:homepage')
def mark_my_assessments_complete(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    coach = get_object_or_404(Coach, user=request.user)
    completion, created = CoachSessionCompletion.objects.get_or_create(coach=coach, session=session)
    if not completion.assessments_submitted:
        completion.assessments_submitted = True
        completion.save()
        messages.success(request, f"Player assessments for session on {session.session_date.strftime('%d %b')} marked as complete.")
    else:
        messages.info(request, "Player assessments for this session were already marked as complete.")
    return redirect('assessments:pending_assessments')

@login_required
@user_passes_test(is_coach, login_url='scheduling:homepage')
def assess_player(request, session_id, player_id):
    """
    Displays a form for a coach to assess a single player for a given session.
    """
    session = get_object_or_404(Session, id=session_id)

    # FIX: Reverting to the simplest possible way to get the player.
    # The template will use `player.full_name`, which handles accessing the user.
    player = get_object_or_404(Player, pk=player_id)

    assessment_instance = SessionAssessment.objects.filter(
        session=session, player=player, submitted_by=request.user
    ).first()

    if request.method == 'POST':
        form = SessionAssessmentForm(request.POST, instance=assessment_instance)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.session = session
            assessment.player = player
            assessment.submitted_by = request.user
            assessment.save()
            messages.success(request, f"Assessment for {player.full_name} has been saved.")
            return redirect('assessments:pending_assessments')
    else:
        form = SessionAssessmentForm(instance=assessment_instance)

    context = {
        'form': form,
        'session': session,
        'player': player,
        'page_title': f"Assess: {player.full_name}",
        'sub_title': f"For session on {session.session_date.strftime('%d %b %Y')}"
    }
    return render(request, 'assessments/assess_player_form.html', context)

@login_required
@user_passes_test(is_coach, login_url='scheduling:homepage')
def add_edit_group_assessment(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    if not session.coaches_attending.filter(user=request.user).exists():
        messages.error(request, "You are not authorized to assess this session.")
        return redirect('assessments:pending_assessments')
    assessment_instance = GroupAssessment.objects.filter(session=session, assessing_coach=request.user).first()
    if request.method == 'POST':
        form = GroupAssessmentForm(request.POST, instance=assessment_instance)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.session = session
            assessment.assessing_coach = request.user
            assessment.school_group = session.school_group
            assessment.save()
            messages.success(request, "Group assessment has been saved successfully.")
            return redirect('assessments:pending_assessments')
    else:
        form = GroupAssessmentForm(instance=assessment_instance)
    context = {
        'form': form, 'session': session,
        'page_title': "Group & Session Assessment",
        'sub_title': f"For session on {session.session_date.strftime('%d %b %Y')}"
    }
    return render(request, 'assessments/add_edit_group_assessment.html', context)


@require_POST
@login_required
@user_passes_test(lambda u: u.is_superuser)
def acknowledge_assessment(request, assessment_id):
    """
    Marks a player session assessment as reviewed by a superuser.
    """
    try:
        assessment = get_object_or_404(SessionAssessment, pk=assessment_id)
        assessment.superuser_reviewed = True
        assessment.save(update_fields=['superuser_reviewed'])
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# --- NEW VIEW ---
@require_POST
@login_required
@user_passes_test(lambda u: u.is_superuser)
def acknowledge_group_assessment(request, group_assessment_id):
    """
    Marks a group assessment as reviewed by a superuser.
    """
    try:
        assessment = get_object_or_404(GroupAssessment, pk=group_assessment_id)
        assessment.superuser_reviewed = True
        assessment.save(update_fields=['superuser_reviewed'])
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
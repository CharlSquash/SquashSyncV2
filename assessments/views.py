# assessments/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
from django.http import HttpResponseForbidden
from django.http import Http404, JsonResponse
from django.contrib.auth.models import User
from django.db import IntegrityError

from django.db.models import Exists, OuterRef, Count
import json # Make sure json is imported

from accounts.models import Coach
from scheduling.models import Session, AttendanceTracking
from players.models import Player, MatchResult
from finance.models import CoachSessionCompletion
from .models import SessionAssessment, GroupAssessment
from .forms import SessionAssessmentForm, GroupAssessmentForm
from players.forms import QuickMatchResultForm # Import the new form


def is_coach(user):
    return user.is_staff and not user.is_superuser

@login_required
@user_passes_test(is_coach, login_url='scheduling:homepage')
def pending_assessments(request):
    """
    Displays a list of past sessions for a coach that are pending assessments
    or were completed within the last week. Automatically confirms for payment
    once either a group assessment or one player assessment is submitted.
    Keeps the accordion open until ALL assessments for the session are done.
    """
    try:
        coach = request.user.coach_profile
    except Coach.DoesNotExist:
        messages.error(request, "Your user account is not linked to a Coach profile.")
        return redirect('scheduling:homepage')

    four_weeks_ago = timezone.now().date() - timedelta(weeks=4)
    one_week_ago = timezone.now().date() - timedelta(weeks=1)
    today = timezone.now().date()

    sessions_qs = Session.objects.filter(
        coaches_attending=coach,
        session_date__gte=four_weeks_ago,
        session_date__lte=today,
        is_cancelled=False
    ).select_related('school_group', 'venue').order_by('-session_date', '-session_start_time')

    session_ids = [s.id for s in sessions_qs]

    # Check which sessions have already been marked complete AND confirmed in the database
    assessments_submitted_ids = set(
        CoachSessionCompletion.objects.filter(
            coach=coach, session_id__in=session_ids,
            assessments_submitted=True,
            confirmed_for_payment=True
        ).values_list('session_id', flat=True)
    )

    group_assessments_done_ids = set(
        GroupAssessment.objects.filter(
            assessing_coach=request.user, session_id__in=session_ids
        ).values_list('session_id', flat=True)
    )

    player_assessments_started_ids = set(
        SessionAssessment.objects.filter(
            submitted_by=request.user, session_id__in=session_ids
        ).values_list('session_id', flat=True)
    )

    attendance_taken_subquery = AttendanceTracking.objects.filter(
        session=OuterRef('pk'),
        attended__in=[AttendanceTracking.CoachAttended.YES, AttendanceTracking.CoachAttended.NO]
    )
    attendance_taken_session_ids = set(
        Session.objects.filter(
            id__in=session_ids
        ).annotate(
            attendance_taken=Exists(attendance_taken_subquery)
        ).filter(
            attendance_taken=True
        ).values_list('id', flat=True)
    )

    session_attendees = AttendanceTracking.objects.filter(
        session_id__in=session_ids,
        attended=AttendanceTracking.CoachAttended.YES
    ).values_list('session_id', 'player_id')

    player_pks_to_fetch = {player_pk for _, player_pk in session_attendees}
    players_by_pk = {p.pk: p for p in Player.objects.filter(pk__in=player_pks_to_fetch)}

    attendees_by_session = defaultdict(list)
    for session_id, player_pk in session_attendees:
        if player_pk in players_by_pk:
            attendees_by_session[session_id].append(players_by_pk[player_pk])

    # NEW: Fetch existing group assessments to pre-fill forms
    group_assessments_by_session = {
        ga.session_id: ga 
        for ga in GroupAssessment.objects.filter(
            assessing_coach=request.user, 
            session_id__in=session_ids
        )
    }

    assessments_by_coach = SessionAssessment.objects.filter(
        submitted_by=request.user, session_id__in=session_ids
    )
    assessments_by_session_id = defaultdict(list)
    for assessment in assessments_by_coach:
        assessments_by_session_id[assessment.session_id].append(assessment)

    session_matches = MatchResult.objects.filter(
        session_id__in=session_ids
    ).select_related('player', 'opponent').order_by('-id')

    matches_by_session = defaultdict(list)
    for match in session_matches:
        matches_by_session[match.session_id].append(match)

    pending_items_for_template = []
    for session in sessions_qs:
        session_id = session.id
        # Check if it was already marked complete before this request
        is_marked_complete_for_payment = session_id in assessments_submitted_ids # Renamed for clarity

        # Skip old, completed sessions unless they are recent
        if is_marked_complete_for_payment and session.session_date < one_week_ago:
            continue

        # Don't show sessions that haven't technically ended yet
        if session.end_datetime and session.end_datetime > timezone.now():
            continue

        has_group_assessment = session_id in group_assessments_done_ids
        has_started_player_assessments = session_id in player_assessments_started_ids

        # --- Automatic Confirmation Logic (Remains the same) ---
        assessments_started_or_group_done = has_group_assessment or has_started_player_assessments

        # If not already marked complete FOR PAYMENT and the condition is met, mark it complete automatically
        if not is_marked_complete_for_payment and assessments_started_or_group_done:
            completion, created = CoachSessionCompletion.objects.get_or_create(
                coach=coach,
                session=session,
                defaults={'assessments_submitted': True, 'confirmed_for_payment': True}
            )
            if not created and (not completion.assessments_submitted or not completion.confirmed_for_payment):
                completion.assessments_submitted = True
                completion.confirmed_for_payment = True
                completion.save(update_fields=['assessments_submitted', 'confirmed_for_payment'])

            is_marked_complete_for_payment = True # Update flag

        # --- END Automatic Confirmation Logic ---

        players_in_session = attendees_by_session.get(session.id, [])
        assessments_for_this_session = assessments_by_session_id.get(session.id, [])
        assessed_player_pks = {a.player_id for a in assessments_for_this_session}
        players_to_assess = [p for p in players_in_session if p.pk not in assessed_player_pks]

        # --- NEW: Priority Sort & Pre-loading ---
        # 1. Get existing assessments for this session to pre-fill forms
        current_assessments_dict = {}
        for assessment in assessments_for_this_session:
            current_assessments_dict[assessment.player_id] = {
                'effort': assessment.effort_rating,
                'focus': assessment.focus_rating,
                'resilience': assessment.resilience_rating,
                'composure': assessment.composure_rating,
                'decision': assessment.decision_making_rating,
                'notes': assessment.coach_notes,
            }

        # 2. Annotate players with their TOTAL historical assessment count (Priority Sort)
        # We need to map the list of player objects to a queryset to use annotate more easily, 
        # or just do a separate query since we have the PKs.
        player_pks_in_session = [p.pk for p in players_in_session]
        
        # Fetch players again with the annotation to ensure we have the count
        # This is a bit redundant but ensures we have the "live" count efficiently
        players_with_counts = Player.objects.filter(pk__in=player_pks_in_session).annotate(
            total_assessments=Count('session_assessments_by_player')
        ).order_by('total_assessments', 'first_name')

        # Replace our list with this sorted list
        players_in_session = list(players_with_counts)

        attendance_has_been_taken = session_id in attendance_taken_session_ids

        # --- NEW: Determine if ALL assessments are truly done for accordion state ---
        all_players_assessed = not players_to_assess and players_in_session # Only true if list is empty AND there were players
        all_assessments_truly_complete = has_group_assessment and all_players_assessed
        # --- END NEW ---

        attendee_pks = [p.pk for p in players_in_session] if attendance_has_been_taken else []
        attendees_queryset = Player.objects.filter(pk__in=attendee_pks) if attendee_pks else Player.objects.none()
        match_form = QuickMatchResultForm(attendees_queryset=attendees_queryset)

        pending_items_for_template.append({
            'session': session,
            'players_to_assess': players_to_assess,
            'is_marked_complete': is_marked_complete_for_payment, # Flag for payment status icon
            'all_assessments_truly_complete': all_assessments_truly_complete, # NEW flag for accordion
            'group_assessment_pending': not has_group_assessment,
            'match_form': match_form,
            'session_matches': matches_by_session.get(session.id, []),
            'attendance_taken': attendance_has_been_taken,
            'current_assessments': current_assessments_dict,
            'all_players_in_session': players_in_session, # The sorted list of all attendees
            'group_form': GroupAssessmentForm(
                instance=group_assessments_by_session.get(session.id), 
                prefix='group_%s' % session.id
            ),
        })

    context = {
        'pending_items': pending_items_for_template,
        'page_title': "My Pending Assessments"
    }
    return render(request, 'assessments/pending_assessments.html', context)

@require_POST
@login_required
@user_passes_test(is_coach)
def update_player_assessment_api(request):
    """
    API endpoint to update a single field of a player assessment via AJAX.
    Expects data: { session_id, player_id, field, value }
    """
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        player_id = data.get('player_id')
        field = data.get('field')
        value = data.get('value')
        
        if not all([session_id, player_id, field]):
             return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)

        session = get_object_or_404(Session, id=session_id)
        player = get_object_or_404(Player, pk=player_id)
        
        # Get or Create Assessment
        assessment, created = SessionAssessment.objects.get_or_create(
            session=session,
            player=player,
            submitted_by=request.user,
            defaults={'date_recorded': session.session_date}
        )
        
        # Field Mapping
        # Frontend field names -> Model field names
        field_map = {
            'effort': 'effort_rating',
            'focus': 'focus_rating',
            'resilience': 'resilience_rating',
            'composure': 'composure_rating',
            'decision': 'decision_making_rating',
            'notes': 'coach_notes'
        }
        
        model_field = field_map.get(field)
        if not model_field:
             return JsonResponse({'status': 'error', 'message': f'Invalid field: {field}'}, status=400)
             
        # Update Value
        if field == 'notes':
            setattr(assessment, model_field, value)
        else:
            # Handle empty strings for ratings (clearing a rating)
            if value == "" or value is None:
                setattr(assessment, model_field, None)
            else:
                setattr(assessment, model_field, int(value))
            
        assessment.save()
        
        return JsonResponse({'status': 'success', 'field': field, 'value': value})
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



@require_POST
@login_required
@user_passes_test(is_coach)
def save_group_assessment_api(request):
    """
    API endpoint to save/update a GroupAssessment via AJAX.
    Expects JSON data: { session_id, general_notes, is_hidden_from_other_coaches }
    """
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        notes = data.get('general_notes', '')

        if not session_id:
             return JsonResponse({'status': 'error', 'message': 'Missing session ID'}, status=400)

        session = get_object_or_404(Session, id=session_id)
        
        # Get or Create Group Assessment
        assessment, created = GroupAssessment.objects.get_or_create(
            session=session,
            assessing_coach=request.user
        )
        
        assessment.general_notes = notes
        # We no longer update assessment.is_hidden_from_other_coaches based on user input here
        assessment.save()
        
        # --- Check for Session Completion (Payment Logic) ---
        coach = request.user.coach_profile
        
        # Check existing completion status
        completion, comp_created = CoachSessionCompletion.objects.get_or_create(
            coach=coach,
            session=session
        )
        
        if not completion.assessments_submitted or not completion.confirmed_for_payment:
            # Check if player assessments are needed/done
            attended_count = AttendanceTracking.objects.filter(
                session=session, attended=AttendanceTracking.CoachAttended.YES
            ).count()
            
            if attended_count == 0:
                all_done = True
            else:
                player_assess_count = SessionAssessment.objects.filter(
                    session=session, submitted_by=request.user
                ).count()
                all_done = player_assess_count >= attended_count
            
            if all_done:
                completion.assessments_submitted = True
                completion.confirmed_for_payment = True
                completion.save()
                return JsonResponse({'status': 'success', 'message': 'Saved', 'marked_complete': True})

        return JsonResponse({'status': 'success', 'message': 'Saved', 'marked_complete': False})
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
@user_passes_test(is_coach, login_url='scheduling:homepage')
def mark_my_assessments_complete(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    coach = get_object_or_404(Coach, user=request.user)
    
    # --- THIS IS THE MODIFIED LOGIC ---
    # get_or_create ensures a record exists if this is the first action.
    completion, created = CoachSessionCompletion.objects.get_or_create(
        coach=coach, 
        session=session
    )
    
    if not completion.assessments_submitted:
        completion.assessments_submitted = True
        completion.confirmed_for_payment = True # Automatically confirm for payment
        completion.save()
        messages.success(request, f"Assessments for session on {session.session_date.strftime('%d %b')} marked as complete and confirmed for payment.")
    else:
        messages.info(request, "Assessments for this session were already marked as complete.")
    # --- END OF MODIFICATION ---

    return redirect('assessments:pending_assessments')

@login_required
@user_passes_test(is_coach, login_url='scheduling:homepage')
def assess_player(request, session_id, player_id):
    """
    Displays a form for a coach to assess a single player for a given session.
    """
    session = get_object_or_404(Session, id=session_id)
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

@login_required
@require_POST
@user_passes_test(is_coach, login_url='scheduling:homepage')
def add_match_result(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    
    attendees_pks = AttendanceTracking.objects.filter(
        session=session,
        attended=AttendanceTracking.CoachAttended.YES
    ).values_list('player_id', flat=True)
    attendees_queryset = Player.objects.filter(pk__in=attendees_pks)

    form = QuickMatchResultForm(request.POST, attendees_queryset=attendees_queryset)

    if form.is_valid():
        match = form.save(commit=False)
        match.session = session
        match.date = session.session_date
        match.submitted_by_name = request.user.get_full_name() or request.user.username
        
        # If an opponent Player object is selected, clear the opponent_name text field
        if match.opponent:
            match.opponent_name = None 
            
        try:
            match.save()
            messages.success(request, f"Match result for {match.player.full_name} vs {match.opponent.full_name} saved.")
        except IntegrityError:
            messages.error(request, "A similar match result may already exist.")
            
    else:
        error_message = "Could not save match. " + " ".join([f"{field}: {error[0]}" for field, error in form.errors.items()])
        messages.error(request, error_message)

    return redirect('assessments:pending_assessments')

@login_required
@require_POST
def delete_match_result(request, match_id):
    """
    Deletes a match result record.
    Checks if the user is a superuser or a coach assigned to the session.
    """
    match = get_object_or_404(MatchResult.objects.select_related('session', 'player', 'opponent'), pk=match_id)
    
    # --- Permission Check ---
    is_authorized = False
    if request.user.is_superuser:
        is_authorized = True
    elif hasattr(request.user, 'coach_profile'):
        # Check if the user is one of the coaches assigned to the session where the match was recorded
        if match.session and request.user.coach_profile in match.session.coaches_attending.all():
            is_authorized = True

    if not is_authorized:
        messages.error(request, "You are not authorized to delete this match result.")
        # Redirect back to the page the user came from, or to the homepage as a fallback.
        return redirect(request.META.get('HTTP_REFERER', 'homepage'))

    # --- Deletion Logic ---
    winner_name = match.player.full_name
    # Handle both linked opponents and text-only opponents
    opponent_display_name = match.opponent.full_name if match.opponent else match.opponent_name
    
    match.delete()
    
    messages.success(request, f"Successfully deleted the match result between {winner_name} and {opponent_display_name}.")
    
    # Redirect back to the previous page (either the assessments page or a player profile)
    return redirect(request.META.get('HTTP_REFERER', 'homepage'))
# awards/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.db.models import Count, F, Q
from django.db import transaction
# --- FIX: Import ValidationError from the correct location ---
from django.core.exceptions import ValidationError
# --- END FIX ---
from django.utils import timezone
from django.contrib import messages
import json # Keep json import for the AJAX views

from .models import Prize, Vote, PrizeWinner
from players.models import Player
from django.contrib.auth import get_user_model

User = get_user_model()

# Helper function to check if the user is staff or superuser
def is_staff_or_superuser(user):
    return user.is_staff

@login_required
@user_passes_test(is_staff_or_superuser)
def prize_list(request):
    """
    Display a list of prizes, optionally filtered by year.
    If no year is specified, default to the current year.
    """
    current_year = timezone.now().year
    selected_year = request.GET.get('year', current_year)

    try:
        selected_year = int(selected_year)
    except (ValueError, TypeError):
        selected_year = current_year

    prizes = Prize.objects.filter(year=selected_year).select_related('category', 'winner', 'winner__player').order_by('category__name', 'name')
    available_years = Prize.objects.values_list('year', flat=True).distinct().order_by('-year')

    context = {
        'page_title': f'Prizes {selected_year}',
        'prizes': prizes,
        'selected_year': selected_year,
        'available_years': available_years,
    }
    return render(request, 'awards/prize_list.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def vote_prize(request, prize_id):
    """
    Display the voting page for a specific prize.
    Shows eligible players, current scores, and handles voting.
    """
    prize = get_object_or_404(Prize.objects.select_related('winner', 'winner__player'), id=prize_id)
    user = request.user

    voting_allowed = prize.is_voting_open_now()

    # Get all eligible players based on prize criteria
    eligible_players = prize.get_eligible_players()

    # Get current vote counts for all players in this prize
    vote_counts = Vote.objects.filter(prize=prize) \
        .values('player_id') \
        .annotate(score=Count('player_id')) \
        .order_by('-score')

    # Map player_id to score
    scores_map = {item['player_id']: item['score'] for item in vote_counts}

    # Get votes cast by the *current* user for *this* prize
    user_votes_for_this_prize = Vote.objects.filter(prize=prize, voter=user)
    user_vote_count = user_votes_for_this_prize.count()
    user_votes_player_ids = set(user_votes_for_this_prize.values_list('player_id', flat=True))

    # --- Prepare player data for the template ---
    current_results = [] # List of {'player': Player, 'score': int, 'voted_by_user': bool}
    eligible_not_voted_players = [] # List of {'player': Player, 'score': int, 'voted_by_user': bool}

    voted_player_ids_in_results = set(scores_map.keys())

    for player in eligible_players:
        player_data = {
            'player': player,
            'score': scores_map.get(player.id, 0),
            'voted_by_user': player.id in user_votes_player_ids
        }
        if player.id in voted_player_ids_in_results:
            current_results.append(player_data)
        else:
            eligible_not_voted_players.append(player_data)

    # Sort leaders by score (descending) then name (ascending)
    current_results.sort(key=lambda x: (-x['score'], x['player'].last_name, x['player'].first_name))

    # Sort other eligible players by name (ascending)
    eligible_not_voted_players.sort(key=lambda x: (x['player'].last_name, x['player'].first_name))

    # Check if admin confirm section should be shown
    show_admin_confirm_section = (
        user.is_superuser and
        prize.status != Prize.PrizeStatus.DECIDED and
        eligible_players.exists()
    )

    # Create the dictionary directly for json_script
    user_votes_data_dict = {str(pid): 1 for pid in user_votes_player_ids}

    context = {
        'page_title': f'Vote: {prize.name}',
        'prize': prize,
        'voting_allowed': voting_allowed,
        'current_results': current_results,
        'eligible_not_voted_players': eligible_not_voted_players,
        'user_votes_data_dict': user_votes_data_dict, # Pass the dictionary for json_script
        'user_vote_count': user_vote_count, # Pass initial count for display
        'winner': prize.winner,
        'show_admin_confirm_section': show_admin_confirm_section,
    }
    return render(request, 'awards/vote_prize.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def cast_vote_ajax(request, prize_id):
    """
    Handle AJAX vote casting/removal. Returns updated vote counts and status.
    """
    if not request.accepts('application/json'):
        return JsonResponse({'status': 'error', 'message': 'Requires JSON.'}, status=400)

    try:
        data = json.loads(request.body)
        player_id = int(data.get('player_id'))
        action_request = data.get('action_request') # 'cast' or 'remove'
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid request data.'}, status=400)

    prize = get_object_or_404(Prize, id=prize_id)
    player = get_object_or_404(Player, id=player_id)
    voter = request.user

    # --- Check Voting Status ---
    if not prize.is_voting_open_now():
        return JsonResponse({'status': 'error', 'message': 'Voting is currently closed.'}, status=403)

    # --- Check Eligibility ---
    if not prize.get_eligible_players().filter(id=player.id).exists():
        return JsonResponse({'status': 'error', 'message': 'This player is not eligible for this prize.'}, status=403)

    try:
        with transaction.atomic():
            current_user_votes = Vote.objects.filter(prize=prize, voter=voter)
            current_vote_count = current_user_votes.count()
            existing_vote_for_player = current_user_votes.filter(player=player).first()

            if action_request == 'remove':
                if existing_vote_for_player:
                    existing_vote_for_player.delete()
                    message = "Vote removed."
                else:
                    # Should ideally not happen if frontend state is correct
                    message = "You hadn't voted for this player."

            elif action_request == 'cast':
                if existing_vote_for_player:
                    # Should not happen if frontend is correct
                    message = "You already voted for this player."
                    # Re-send current state just in case
                elif current_vote_count >= 3:
                    # Vote limit reached
                    return JsonResponse({
                        'status': 'limit_reached',
                        'message': 'Vote limit (3) reached. Remove a vote first.',
                        'user_vote_count': current_vote_count, # Return current count
                    }, status=400) # Use 400 Bad Request for client error
                else:
                    # Create the new vote
                    Vote.objects.create(prize=prize, player=player, voter=voter)
                    message = "Vote cast!"
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid action specified.'}, status=400)

            # --- Recalculate scores and status AFTER changes ---
            new_player_score = Vote.objects.filter(prize=prize, player=player).count()
            final_user_vote_count = Vote.objects.filter(prize=prize, voter=voter).count()
            user_has_vote_now = Vote.objects.filter(prize=prize, voter=voter, player=player).exists()

        # --- Return comprehensive status ---
        return JsonResponse({
            'status': 'success',
            'message': message,
            'new_score': new_player_score,          # Score for the specific player clicked
            'user_vote_count': final_user_vote_count, # Total votes by the user for THIS prize
            'voted': user_has_vote_now,             # Does user now have a vote for THIS player?
            'player_id': player_id                  # ID of the player action was performed on
        })

    except ValidationError as e: # Catch model validation errors (like vote limit)
         return JsonResponse({'status': 'error', 'message': e.messages[0]}, status=400)
    except Exception as e:
        # Log the error e
        print(f"Error in cast_vote_ajax: {e}") # Basic logging
        return JsonResponse({'status': 'error', 'message': f'An unexpected server error occurred.'}, status=500)


@login_required
@user_passes_test(lambda u: u.is_superuser) # Only superusers can confirm
@require_POST
def confirm_winner(request, prize_id):
    """
    Admin action to confirm a winner for a prize.
    This closes voting and sets the prize status to Decided.
    """
    prize = get_object_or_404(Prize, id=prize_id)

    # Check if prize is already decided
    if prize.status == Prize.PrizeStatus.DECIDED:
        messages.warning(request, f"A winner has already been decided for {prize.name}.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    try:
        winner_player_id = int(request.POST.get('winner_player_id'))
        winner_player = get_object_or_404(Player, id=winner_player_id)
    except (TypeError, ValueError, AttributeError):
        messages.error(request, "Invalid player selection.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    # Check eligibility again for safety
    if not prize.get_eligible_players().filter(id=winner_player.id).exists():
        messages.error(request, f"{winner_player.full_name} is not eligible for this prize.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    try:
        with transaction.atomic():
            # Get final score just before confirming
            final_score = Vote.objects.filter(prize=prize, player=winner_player).count()

            # Create the winner record
            winner_record, created = PrizeWinner.objects.update_or_create(
                prize=prize, # Use prize as the unique identifier
                defaults={
                    'player': winner_player,
                    'year': prize.year, # Copy year from prize
                    'awarded_by': request.user,
                    'award_date': timezone.now().date(),
                    'final_score': final_score
                }
            )

            # Update prize status and link the winner
            prize.status = Prize.PrizeStatus.DECIDED
            prize.winner = winner_record # Link the winner record back to the prize
            prize.save()

            if created:
                messages.success(request, f"Confirmed {winner_player.full_name} as the winner for {prize.name}. Voting is now closed.")
            else:
                messages.info(request, f"Updated winner for {prize.name} to {winner_player.full_name}. Voting is now closed.")

    except Exception as e:
        # Log the error e
        print(f"Error in confirm_winner: {e}") # Basic logging
        messages.error(request, f"An error occurred while confirming the winner.")

    return redirect('awards:vote_prize', prize_id=prize.id)


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def clear_my_votes_ajax(request, prize_id):
    """
    Clears all votes for the current user for a specific prize via AJAX.
    """
    if not request.accepts('application/json'):
        return JsonResponse({'status': 'error', 'message': 'Requires JSON.'}, status=400)

    prize = get_object_or_404(Prize, id=prize_id)
    voter = request.user

    if not prize.is_voting_open_now():
        return JsonResponse({'status': 'error', 'message': 'Voting is currently closed.'}, status=403)

    try:
        with transaction.atomic():
            # Find all votes by this user for this prize
            user_votes = Vote.objects.filter(prize=prize, voter=voter)

            # Get the list of player IDs before deleting to update their scores later
            voted_player_ids = list(user_votes.values_list('player_id', flat=True))

            if not voted_player_ids:
                return JsonResponse({
                    'status': 'success',
                    'message': 'You had no votes to clear.',
                    'user_vote_count': 0,
                    'updated_scores': [] # Return empty list
                })

            # Delete all the votes
            deleted_count, _ = user_votes.delete() # Returns count and dict of deleted types

            # Recalculate scores for only the affected players
            updated_scores_data = []
            if voted_player_ids: # Only query if there were votes
                affected_players_qs = Player.objects.filter(id__in=voted_player_ids) \
                                           .annotate(new_score=Count('prize_votes', filter=Q(prize_votes__prize=prize)))

                updated_scores_data = [
                    {'player_id': player.id, 'new_score': player.new_score}
                    for player in affected_players_qs
                ]

        return JsonResponse({
            'status': 'success',
            'message': f'{deleted_count} vote(s) cleared.',
            'user_vote_count': 0, # Vote count is now zero
            'updated_scores': updated_scores_data # List of {'player_id': id, 'new_score': score}
        })

    except Exception as e:
        # Log the error e
        print(f"Error in clear_my_votes_ajax: {e}") # Basic logging
        return JsonResponse({'status': 'error', 'message': f'An unexpected server error occurred.'}, status=500)


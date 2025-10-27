import json
import logging # Import logging
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q, Prefetch, Count
from django.db import transaction
from django.views.decorators.http import require_POST
from collections import defaultdict
from players.models import Player # Correct specific import
# --- Corrected Import ---
from .models import Prize, PrizeCategory, Vote, PrizeWinner # Removed PrizeStatus

# --- Get Logger ---
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def is_admin(user):
    return user.is_superuser

def is_staff_or_admin(user):
    return user.is_staff

# --- Views ---
@login_required
@user_passes_test(is_admin)
def prize_list(request):
    current_year = timezone.now().year
    selected_year = request.GET.get('year', current_year)
    try:
        selected_year = int(selected_year)
    except (ValueError, TypeError):
        selected_year = current_year

    prizes = Prize.objects.filter(year=selected_year).select_related(
        'category', 'winner', 'winner__player'
    ).order_by('category__name', 'name')
    available_years = Prize.objects.values_list('year', flat=True).distinct().order_by('-year')

    context = {
        'prizes': prizes,
        'selected_year': selected_year,
        'available_years': available_years,
        'page_title': f"Awards & Prizes ({selected_year})",
    }
    return render(request, 'awards/prize_list.html', context)


@login_required
@user_passes_test(is_staff_or_admin)
def vote_prize(request, prize_id):
    prize = get_object_or_404(Prize.objects.select_related('winner', 'winner__player'), pk=prize_id)
    voting_allowed = prize.is_voting_open()
    winner_details = prize.winner

    current_results = prize.get_results() # Gets [{'player': Player, 'score': int}]

    # --- Query for user's votes for THIS prize ---
    user_votes_qs = Vote.objects.filter(prize=prize, voter=request.user)
    user_vote_count = user_votes_qs.count() # Get the count

    # --- MORE DEBUG LOGGING ---
    logger.debug(f"[Vote View] User '{request.user.username}' for Prize '{prize.name}' (ID: {prize_id}): Initial vote count from DB query = {user_vote_count}")
    # Log the actual IDs found by the query
    vote_ids_found = list(user_votes_qs.values_list('player_id', flat=True))
    logger.debug(f"[Vote View] Player IDs voted for by user (from DB query): {vote_ids_found}")
    # Check if count matches length of list - they SHOULD match!
    if user_vote_count != len(vote_ids_found):
         logger.error(f"[Vote View] MISMATCH! .count() gave {user_vote_count} but values_list has {len(vote_ids_found)} items!")
    # --- END DEBUG LOGGING ---


    eligible_players = prize.get_eligible_players()

    # Get IDs of players who already have votes (leaders)
    players_with_scores_ids = set(result['player'].id for result in current_results)

    # Get eligible players who DON'T have votes yet
    eligible_not_voted_players = eligible_players.exclude(
        id__in=players_with_scores_ids
    ).order_by('last_name', 'first_name')

    # Prepare data for JavaScript: { "player_id_as_string": 1 }
    user_votes_simple = {}
    user_votes_simple_json = json.dumps({}) # Default to empty
    try:
         # Ensure keys are strings for JSON compatibility using the list we already fetched
         user_votes_simple = { str(player_id): 1 for player_id in vote_ids_found }
         user_votes_simple_json = json.dumps(user_votes_simple)
         logger.debug(f"[Vote View] Generated user_votes_simple_json: {user_votes_simple_json}")
    except Exception as e:
        logger.error(f"[Vote View] Error creating JSON for user votes: {e}")
        # user_votes_simple_json remains empty dict

    # Calculate boolean flag for admin section visibility
    show_admin_confirm_section = (
        request.user.is_superuser and
        not winner_details and
        (current_results or eligible_not_voted_players.exists()) # Check if results OR other players exist
    )

    context = {
        'prize': prize,
        'voting_allowed': voting_allowed,
        'winner': winner_details,
        'current_results': current_results, # List of dicts
        'eligible_not_voted_players': eligible_not_voted_players, # QuerySet
        'user_vote_count': user_vote_count, # Initial count for display (Still potentially wrong if DB is weird)
        'user_votes_simple_json': user_votes_simple_json, # For JS init
        'show_admin_confirm_section': show_admin_confirm_section,
        'page_title': f"Vote for '{prize.name}' ({prize.year})",
    }
    return render(request, 'awards/vote_prize.html', context)


@require_POST
@login_required
@user_passes_test(is_staff_or_admin)
def cast_vote_ajax(request):
    try:
        data = json.loads(request.body)
        prize_id = int(data.get('prize_id'))
        player_id = int(data.get('player_id'))
        action_request = data.get('action', 'cast') # 'cast' or 'remove'

        prize = get_object_or_404(Prize, pk=prize_id)

        if not prize.is_voting_open():
            logger.warning(f"[Cast Vote] User '{request.user.username}' tried to vote on closed prize ID {prize_id}")
            return JsonResponse({'status': 'error', 'message': 'Voting is not open for this prize.'}, status=403)

        # Verify player is eligible for this prize
        try:
            player = get_object_or_404(prize.get_eligible_players(), pk=player_id)
        except Http404:
             logger.warning(f"[Cast Vote] User '{request.user.username}' tried to vote for ineligible player ID {player_id} on prize ID {prize_id}")
             return JsonResponse({'status': 'error', 'message': 'Player is not eligible for this prize.'}, status=400)

        # Use player's full_name property safely for messages
        player_display_name = getattr(player, 'full_name', f"{player.first_name} {player.last_name}")

        current_user_votes = Vote.objects.filter(prize=prize, voter=request.user)
        # --- Recalculate count *before* action ---
        current_vote_count = current_user_votes.count()
        already_voted_for_player = current_user_votes.filter(player=player).exists() # Check existence separately

        message = ""
        new_score = 0
        vote_status_changed = False # Flag to indicate if UI needs update
        action_taken = None # 'added' or 'removed'

        logger.debug(f"[Cast Vote] User '{request.user.username}', Prize ID {prize_id}, Player ID {player_id}, Action: {action_request}. Current votes (DB): {current_vote_count}, Already voted for player (DB): {already_voted_for_player}")

        with transaction.atomic():
            if action_request == 'remove':
                if already_voted_for_player:
                    # Target the specific vote to delete
                    deleted_count, _ = Vote.objects.filter(prize=prize, player=player, voter=request.user).delete()
                    if deleted_count > 0:
                        message = f"Removed vote for {player_display_name}."
                        vote_status_changed = True
                        action_taken = 'removed'
                        logger.info(f"[Cast Vote] Vote removed by '{request.user.username}' for player {player_id} on prize {prize_id}")
                    else:
                         # This case means already_voted_for_player was true, but delete failed? Very unlikely in transaction.
                         message = "Could not remove vote."
                         logger.error(f"[Cast Vote] Failed to delete existing vote for user '{request.user.username}', player {player_id}, prize {prize_id}")

                else:
                    message = "No vote found to remove." # User tried removing vote they didn't have
                    logger.warning(f"[Cast Vote] User '{request.user.username}' tried to remove non-existent vote for player {player_id} on prize {prize_id}")

            elif action_request == 'cast':
                if already_voted_for_player:
                    message = f"You have already voted for {player_display_name}."
                    # No status change, return existing state
                elif current_vote_count >= 3:
                    message = "You have already used all 3 votes for this prize."
                    logger.warning(f"[Cast Vote] User '{request.user.username}' hit vote limit ({current_vote_count}/3) on prize {prize_id}")
                    return JsonResponse({'status': 'limit_reached', 'message': message}, status=400) # Specific status
                else:
                    Vote.objects.create(
                        prize=prize,
                        player=player,
                        voter=request.user
                    )
                    message = f"Cast vote for {player_display_name}."
                    vote_status_changed = True
                    action_taken = 'added'
                    logger.info(f"[Cast Vote] Vote added by '{request.user.username}' for player {player_id} on prize {prize_id}")


            # Recalculate score for the specific player after potential changes
            new_score = Vote.objects.filter(prize=prize, player=player).count()

        # Get updated total vote count for the user AFTER the transaction
        # --- Use a fresh query AFTER transaction completes ---
        final_user_vote_count = Vote.objects.filter(prize=prize, voter=request.user).count()
        logger.debug(f"[Cast Vote] Final user vote count for prize {prize_id} (after TX) = {final_user_vote_count}")


        # Determine the final 'voted' status for this specific player AFTER transaction
        user_has_vote_now = Vote.objects.filter(prize=prize, player=player, voter=request.user).exists()
        logger.debug(f"[Cast Vote] User has vote now for player {player_id}? {user_has_vote_now}")


        response_data = {
            'status': 'success',
            'message': message,
            'player_id': player_id,
            'new_score': new_score,
            'user_vote_count': final_user_vote_count, # Send the accurate final count
            'voted': user_has_vote_now, # Send the accurate final state for this player
            'vote_status_changed': vote_status_changed, # True only if a vote was added/removed in *this* request
            'action': action_taken # 'added' or 'removed' or None
        }
        logger.debug(f"[Cast Vote] Response data: {response_data}")
        return JsonResponse(response_data)

    except json.JSONDecodeError:
        logger.error("[Cast Vote] Invalid JSON received.", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
    except (ValueError, TypeError, KeyError) as e:
         logger.error(f"[Cast Vote] Invalid or missing data: {e}", exc_info=True)
         return JsonResponse({'status': 'error', 'message': 'Invalid or missing data.'}, status=400)
    except Prize.DoesNotExist:
         logger.warning(f"[Cast Vote] Prize ID {locals().get('prize_id', 'unknown')} not found.")
         return JsonResponse({'status': 'error', 'message': 'Prize not found.'}, status=404)
    except Exception as e:
        player_name = getattr(locals().get('player'), 'full_name', 'unknown player')
        logger.exception(f"[Cast Vote] Unexpected error for player_id {locals().get('player_id', 'unknown')}, player {player_name}: {type(e).__name__} - {e}") # Log full traceback
        return JsonResponse({'status': 'error', 'message': 'An unexpected server error occurred.'}, status=500)


@require_POST
@login_required
@user_passes_test(is_admin)
def confirm_winner(request, prize_id):
    prize = get_object_or_404(Prize, pk=prize_id)

    # Use PrizeStatus enum defined in the model
    if prize.status == Prize.PrizeStatus.DECIDED or prize.status == Prize.PrizeStatus.ARCHIVED:
        messages.warning(request, f"A winner has already been decided for {prize.name}.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    winner_player_id = request.POST.get('winner_player_id')

    if not winner_player_id:
        messages.error(request, "No winner selected.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    try:
        winner_player_id = int(winner_player_id)
        # Ensure selected winner is actually eligible
        winner_player = get_object_or_404(prize.get_eligible_players(), pk=winner_player_id)
        # Use player's full_name property safely for messages
        winner_display_name = getattr(winner_player, 'full_name', f"{winner_player.first_name} {winner_player.last_name}")


        final_score = Vote.objects.filter(prize=prize, player=winner_player).count()

        with transaction.atomic():
            prize_winner_obj, created = PrizeWinner.objects.update_or_create(
                prize=prize,
                defaults={
                    'player': winner_player,
                    'year': prize.year,
                    'awarded_by': request.user,
                    'award_date': timezone.now().date(),
                    'final_score': final_score
                }
            )
            # Update the prize status and link the winner
            prize.status = Prize.PrizeStatus.DECIDED
            prize.winner = prize_winner_obj # Link directly to the winner object
            prize.save(update_fields=['status', 'winner'])
            logger.info(f"Winner confirmed for prize {prize_id}: Player {winner_player_id} by admin {request.user.username}")


        messages.success(request, f"{winner_display_name} confirmed as the winner for {prize.name} ({prize.year})!")

    except (ValueError, Player.DoesNotExist):
        logger.warning(f"Error confirming winner for prize {prize_id}: Invalid player ID {winner_player_id}", exc_info=True)
        messages.error(request, "Invalid winner selected or player not found/eligible.")
    except Exception as e:
        logger.exception(f"Unexpected error confirming winner for prize {prize_id}")
        messages.error(request, f"An error occurred while confirming winner: {e}")

    return redirect('awards:vote_prize', prize_id=prize.id)


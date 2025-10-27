import json
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

    current_results = prize.get_results()

    user_votes_qs = Vote.objects.filter(prize=prize, voter=request.user)
    user_voted_player_ids = set(user_votes_qs.values_list('player_id', flat=True))
    user_vote_count = len(user_voted_player_ids)

    eligible_players = prize.get_eligible_players()

    players_with_scores_ids = set()
    if current_results:
        # Check if the first item is a dictionary (expected)
        if isinstance(current_results[0], dict):
             players_with_scores_ids = set(result['player'].id for result in current_results)
        elif isinstance(current_results[0], Player): # Handle unexpected case
             print(f"WARNING: get_results returned Player objects for Prize ID {prize_id}")
             players_with_scores_ids = set(p.id for p in current_results)

    eligible_not_voted_players = eligible_players.exclude(id__in=players_with_scores_ids)

    user_votes_simple = { vote.player_id: 1 for vote in user_votes_qs }

    # Calculate boolean flag for admin section visibility
    show_admin_confirm_section = (
        request.user.is_superuser and
        not winner_details and
        (current_results or eligible_not_voted_players.exists()) # Check if queryset has items
    )

    context = {
        'prize': prize,
        'voting_allowed': voting_allowed,
        'winner': winner_details,
        'current_results': current_results,
        'eligible_not_voted_players': eligible_not_voted_players,
        'user_vote_count': user_vote_count,
        'user_votes_simple_json': json.dumps(user_votes_simple),
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
        action = data.get('action', 'cast') # 'cast' or 'remove'

        prize = get_object_or_404(Prize, pk=prize_id)

        if not prize.is_voting_open():
            return JsonResponse({'status': 'error', 'message': 'Voting is not open for this prize.'}, status=403)

        # Verify player is eligible for this prize
        try:
            player = get_object_or_404(prize.get_eligible_players(), pk=player_id)
        except Http404:
             return JsonResponse({'status': 'error', 'message': 'Player is not eligible for this prize.'}, status=400)


        current_user_votes = Vote.objects.filter(prize=prize, voter=request.user)
        current_vote_count = current_user_votes.count()
        already_voted_for_player = current_user_votes.filter(player=player).exists()

        message = ""
        new_score = 0
        vote_status_changed = False # Flag to indicate if UI needs update

        with transaction.atomic():
            if action == 'remove':
                if already_voted_for_player:
                    deleted_count, _ = Vote.objects.filter(prize=prize, player=player, voter=request.user).delete()
                    if deleted_count > 0:
                        message = f"Removed vote for {player.short_name}."
                        vote_status_changed = True
                else:
                    message = "No vote found to remove."

            elif action == 'cast':
                if already_voted_for_player:
                    message = f"You have already voted for {player.short_name}."
                elif current_vote_count >= 3:
                    message = "You have already used all 3 votes for this prize."
                    return JsonResponse({'status': 'limit_reached', 'message': message}, status=400) # Specific status
                else:
                    Vote.objects.create(
                        prize=prize,
                        player=player,
                        voter=request.user
                    )
                    message = f"Cast vote for {player.short_name}."
                    vote_status_changed = True

            # Recalculate score for the specific player after changes
            new_score = Vote.objects.filter(prize=prize, player=player).count()

        # Get updated total vote count for the user
        final_user_vote_count = Vote.objects.filter(prize=prize, voter=request.user).count()

        return JsonResponse({
            'status': 'success',
            'message': message,
            'player_id': player_id,
            'new_score': new_score,
            'user_vote_count': final_user_vote_count,
            'voted': (action == 'cast' and vote_status_changed) or (action == 'remove' and not vote_status_changed and already_voted_for_player) , # True if user now has a vote for this player
            'vote_status_changed': vote_status_changed,
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
    except (ValueError, TypeError, KeyError):
         return JsonResponse({'status': 'error', 'message': 'Invalid or missing data.'}, status=400)
    except Prize.DoesNotExist:
         return JsonResponse({'status': 'error', 'message': 'Prize not found.'}, status=404)
    except Exception as e:
        print(f"Error in cast_vote_ajax: {e}") # Basic logging
        return JsonResponse({'status': 'error', 'message': 'An unexpected server error occurred.'}, status=500)


@require_POST
@login_required
@user_passes_test(is_admin)
def confirm_winner(request, prize_id):
    prize = get_object_or_404(Prize, pk=prize_id)

    # --- Use Prize.PrizeStatus ---
    if prize.status == Prize.PrizeStatus.DECIDED or prize.status == Prize.PrizeStatus.ARCHIVED:
        messages.warning(request, f"A winner has already been decided for {prize.name}.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    winner_player_id = request.POST.get('winner_player_id')

    if not winner_player_id:
        messages.error(request, "No winner selected.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    try:
        winner_player_id = int(winner_player_id)
        winner_player = get_object_or_404(prize.get_eligible_players(), pk=winner_player_id)

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
            # --- Use Prize.PrizeStatus ---
            prize.status = Prize.PrizeStatus.DECIDED
            prize.winner = prize_winner_obj
            prize.save(update_fields=['status', 'winner'])

        messages.success(request, f"{winner_player.full_name} confirmed as the winner for {prize.name} ({prize.year})!")

    except (ValueError, Player.DoesNotExist):
        messages.error(request, "Invalid winner selected.")
    except Exception as e:
        messages.error(request, f"An error occurred: {e}")

    return redirect('awards:vote_prize', prize_id=prize.id)


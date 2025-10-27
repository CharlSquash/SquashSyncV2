# awards/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.db.models import Count, F, Q
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib import messages
import json
from collections import defaultdict # Import defaultdict

from .models import Prize, Vote, PrizeWinner
from players.models import Player
from django.contrib.auth import get_user_model

User = get_user_model()

# Helper function to check if the user is a superuser (for confirm_winner)
def is_superuser(user):
    return user.is_superuser

# --- Permissions Updated: Removed user_passes_test decorator ---
@login_required
# @user_passes_test(is_staff_or_superuser) # Removed staff check
def prize_list(request):
    """
    Display a list of prizes, optionally filtered by year.
    Now accessible to all logged-in users.
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

# --- Permissions Updated: Removed user_passes_test decorator ---
@login_required
# @user_passes_test(is_staff_or_superuser) # Removed staff check
def vote_prize(request, prize_id):
    """
    Display the voting page for a specific prize.
    Shows eligible players, current scores, handles voting, and shows voters to admins.
    Now accessible to all logged-in users for viewing.
    """
    prize = get_object_or_404(Prize.objects.select_related('winner', 'winner__player'), id=prize_id)
    user = request.user

    voting_allowed = prize.is_voting_open_now()

    eligible_players = prize.get_eligible_players()

    vote_counts = Vote.objects.filter(prize=prize) \
        .values('player_id') \
        .annotate(score=Count('player_id')) \
        .order_by('-score')

    scores_map = {item['player_id']: item['score'] for item in vote_counts}

    user_votes_for_this_prize = Vote.objects.filter(prize=prize, voter=user)
    user_vote_count = user_votes_for_this_prize.count()
    user_votes_player_ids = set(user_votes_for_this_prize.values_list('player_id', flat=True))

    # --- Fetch and process voter details (for admin display) ---
    voters_by_player_id = defaultdict(list)
    if user.is_superuser: # Only fetch if the viewer is a superuser
        all_votes = Vote.objects.filter(prize=prize).select_related('voter').order_by('voter__last_name', 'voter__first_name')
        for vote in all_votes:
            voter_name = vote.voter.get_full_name() or vote.voter.username
            voters_by_player_id[vote.player_id].append(voter_name)
    # --- End voter details fetching ---

    current_results = []
    eligible_not_voted_players = []
    voted_player_ids_in_results = set(scores_map.keys())

    for player in eligible_players:
        player_data = {
            'player': player,
            'score': scores_map.get(player.id, 0),
            'voted_by_user': player.id in user_votes_player_ids,
            # Add voter list (will be empty if not superuser or no votes)
            'voters': voters_by_player_id.get(player.id, [])
        }
        if player.id in voted_player_ids_in_results:
            current_results.append(player_data)
        else:
            eligible_not_voted_players.append(player_data)

    current_results.sort(key=lambda x: (-x['score'], x['player'].last_name, x['player'].first_name))
    eligible_not_voted_players.sort(key=lambda x: (x['player'].last_name, x['player'].first_name))

    show_admin_confirm_section = (
        user.is_superuser and
        prize.status != Prize.PrizeStatus.DECIDED and
        eligible_players.exists()
    )

    user_votes_data_dict = {str(pid): 1 for pid in user_votes_player_ids}

    context = {
        'page_title': f'Vote: {prize.name}',
        'prize': prize,
        'voting_allowed': voting_allowed,
        'current_results': current_results,
        'eligible_not_voted_players': eligible_not_voted_players,
        'user_votes_data_dict': user_votes_data_dict,
        'user_vote_count': user_vote_count,
        'winner': prize.winner,
        'show_admin_confirm_section': show_admin_confirm_section,
    }
    return render(request, 'awards/vote_prize.html', context)


# --- Permissions Updated: Removed user_passes_test decorator ---
@login_required
# @user_passes_test(is_staff_or_superuser) # Removed staff check
@require_POST
def cast_vote_ajax(request, prize_id):
    """
    Handle AJAX vote casting/removal. Returns updated vote counts and status.
    Now accessible to all logged-in users.
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

    if not prize.is_voting_open_now():
        return JsonResponse({'status': 'error', 'message': 'Voting is currently closed.'}, status=403)

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
                    message = "You hadn't voted for this player."

            elif action_request == 'cast':
                if existing_vote_for_player:
                    message = "You already voted for this player."
                elif current_vote_count >= 3:
                    return JsonResponse({
                        'status': 'limit_reached',
                        'message': 'Vote limit (3) reached. Remove a vote first.',
                        'user_vote_count': current_vote_count,
                    }, status=400)
                else:
                    Vote.objects.create(prize=prize, player=player, voter=voter)
                    message = "Vote cast!"
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid action specified.'}, status=400)

            new_player_score = Vote.objects.filter(prize=prize, player=player).count()
            final_user_vote_count = Vote.objects.filter(prize=prize, voter=voter).count()
            user_has_vote_now = Vote.objects.filter(prize=prize, voter=voter, player=player).exists()

        return JsonResponse({
            'status': 'success',
            'message': message,
            'new_score': new_player_score,
            'user_vote_count': final_user_vote_count,
            'voted': user_has_vote_now,
            'player_id': player_id
        })

    except ValidationError as e:
         return JsonResponse({'status': 'error', 'message': e.messages[0]}, status=400)
    except Exception as e:
        print(f"Error in cast_vote_ajax: {e}")
        return JsonResponse({'status': 'error', 'message': f'An unexpected server error occurred.'}, status=500)


# --- Permissions UNCHANGED: Only superusers can confirm ---
@login_required
@user_passes_test(is_superuser) # Keep superuser check
@require_POST
def confirm_winner(request, prize_id):
    """
    Admin action to confirm a winner for a prize.
    Remains restricted to superusers.
    """
    prize = get_object_or_404(Prize, id=prize_id)

    if prize.status == Prize.PrizeStatus.DECIDED:
        messages.warning(request, f"A winner has already been decided for {prize.name}.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    try:
        winner_player_id = int(request.POST.get('winner_player_id'))
        winner_player = get_object_or_404(Player, id=winner_player_id)
    except (TypeError, ValueError, AttributeError):
        messages.error(request, "Invalid player selection.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    if not prize.get_eligible_players().filter(id=winner_player.id).exists():
        messages.error(request, f"{winner_player.full_name} is not eligible for this prize.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    try:
        with transaction.atomic():
            final_score = Vote.objects.filter(prize=prize, player=winner_player).count()
            winner_record, created = PrizeWinner.objects.update_or_create(
                prize=prize,
                defaults={
                    'player': winner_player, 'year': prize.year,
                    'awarded_by': request.user, 'award_date': timezone.now().date(),
                    'final_score': final_score
                }
            )
            prize.status = Prize.PrizeStatus.DECIDED
            prize.winner = winner_record
            prize.save()
            if created:
                messages.success(request, f"Confirmed {winner_player.full_name} as the winner for {prize.name}. Voting is now closed.")
            else:
                messages.info(request, f"Updated winner for {prize.name} to {winner_player.full_name}. Voting is now closed.")
    except Exception as e:
        print(f"Error in confirm_winner: {e}")
        messages.error(request, f"An error occurred while confirming the winner.")

    return redirect('awards:vote_prize', prize_id=prize.id)

# --- Permissions Updated: Removed user_passes_test decorator ---
@login_required
# @user_passes_test(is_staff_or_superuser) # Removed staff check
@require_POST
def clear_my_votes_ajax(request, prize_id):
    """
    Clears all votes for the current logged-in user for a specific prize via AJAX.
    Now accessible to all logged-in users.
    """
    if not request.accepts('application/json'):
        return JsonResponse({'status': 'error', 'message': 'Requires JSON.'}, status=400)

    prize = get_object_or_404(Prize, id=prize_id)
    voter = request.user # Action applies only to the logged-in user

    if not prize.is_voting_open_now():
        return JsonResponse({'status': 'error', 'message': 'Voting is currently closed.'}, status=403)

    try:
        with transaction.atomic():
            user_votes = Vote.objects.filter(prize=prize, voter=voter)
            voted_player_ids = list(user_votes.values_list('player_id', flat=True))

            if not voted_player_ids:
                return JsonResponse({
                    'status': 'success',
                    'message': 'You had no votes to clear.',
                    'user_vote_count': 0,
                    'updated_scores': []
                })

            deleted_count, _ = user_votes.delete()

            updated_scores_data = []
            if voted_player_ids:
                affected_players_qs = Player.objects.filter(id__in=voted_player_ids) \
                                           .annotate(new_score=Count('prize_votes', filter=Q(prize_votes__prize=prize)))
                updated_scores_data = [
                    {'player_id': player.id, 'new_score': player.new_score}
                    for player in affected_players_qs
                ]

        return JsonResponse({
            'status': 'success',
            'message': f'{deleted_count} vote(s) cleared.',
            'user_vote_count': 0,
            'updated_scores': updated_scores_data
        })

    except Exception as e:
        print(f"Error in clear_my_votes_ajax: {e}")
        return JsonResponse({'status': 'error', 'message': f'An unexpected server error occurred.'}, status=500)


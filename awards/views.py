from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.db.models import Count, F
from django.db import transaction
from django.utils import timezone
from django.contrib import messages
import json

from .models import Prize, Vote, PrizeWinner
from players.models import Player
from accounts.models import Coach # Assuming Coach is in accounts.models

# ... (other views like prize_list) ...

@login_required
def prize_list(request):
    """
    Display a list of prizes, optionally filtered by year.
    If no year is specified, default to the current year.
    """
    current_year = timezone.now().year
    selected_year = request.GET.get('year', current_year)
    
    try:
        selected_year = int(selected_year)
    except ValueError:
        selected_year = current_year

    prizes = Prize.objects.filter(year=selected_year).order_by('name')
    available_years = Prize.objects.values_list('year', flat=True).distinct().order_by('-year')

    context = {
        'page_title': f'Prizes {selected_year}',
        'prizes': prizes,
        'selected_year': selected_year,
        'available_years': available_years,
    }
    return render(request, 'awards/prize_list.html', context)


@login_required
def vote_prize(request, prize_id):
    """
    Display the voting page for a specific prize.
    Shows current leaders and other eligible players.
    """
    prize = get_object_or_404(Prize, id=prize_id)
    user = request.user
    
    # Determine voting status
    now = timezone.now()
    voting_allowed = (
        (prize.voting_opens is None or prize.voting_opens <= now) and
        (prize.voting_closes is None or prize.voting_closes >= now) and
        prize.status == Prize.VOTING_OPEN
    )

    # Get all eligible players based on prize criteria
    eligible_players = Player.objects.filter(
        player_grade__gte=prize.min_grade,
        player_grade__lte=prize.max_grade,
        # is_active=True # Consider if only active players should be eligible
    ).distinct()

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
    
    # --- THIS IS THE MAIN FIX ---
    # Create the dictionary of player IDs the user has voted for
    # Pass this *dictionary* directly to the template
    user_votes_data = {str(vote.player_id): 1 for vote in user_votes_for_this_prize}
    # --- END OF FIX ---


    # Separate players into leaders (voted) and others (not voted)
    current_results = [] # List of {'player': Player, 'score': int}
    eligible_not_voted_players = [] # List of Player objects
    
    voted_player_ids = set(scores_map.keys())
    
    for player in eligible_players:
        if player.id in voted_player_ids:
            current_results.append({
                'player': player,
                'score': scores_map.get(player.id, 0)
            })
        else:
            eligible_not_voted_players.append(player)

    # Sort leaders by score (descending) then name (ascending)
    current_results.sort(key=lambda x: (-x['score'], x['player'].full_name))
    
    # Sort other eligible players by name (ascending)
    eligible_not_voted_players.sort(key=lambda x: x.full_name)


    # Check for winner
    winner = PrizeWinner.objects.filter(prize=prize).first() # Get the winner, if any

    # Check if admin confirm section should be shown
    # Simple check: user is staff and prize is not yet decided
    show_admin_confirm_section = (
        user.is_staff and 
        prize.status != Prize.DECIDED and
        (eligible_players.exists()) # Only show if there are players
    )
    
    context = {
        'page_title': f'Vote: {prize.name}',
        'prize': prize,
        'voting_allowed': voting_allowed,
        'current_results': current_results,
        'eligible_not_voted_players': eligible_not_voted_players, # Pass this list
        
        # --- PASS THE DICTIONARY ---
        'user_votes_data': user_votes_data, # Pass the raw dictionary
        # --- END ---
        
        'user_vote_count': user_vote_count, # Pass the initial count
        'winner': winner,
        'show_admin_confirm_section': show_admin_confirm_section,
    }
    return render(request, 'awards/vote_prize.html', context)


@login_required
@require_POST
def cast_vote_ajax(request, prize_id):
    """
    Handle AJAX vote casting/removal.
    """
    try:
        data = json.loads(request.body)
        player_id = int(data.get('player_id'))
        action_request = data.get('action_request') # 'cast' or 'remove'
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid request.'}, status=400)

    prize = get_object_or_404(Prize, id=prize_id)
    player = get_object_or_404(Player, id=player_id)
    voter = request.user

    # Check if voting is open
    now = timezone.now()
    voting_allowed = (
        (prize.voting_opens is None or prize.voting_opens <= now) and
        (prize.voting_closes is None or prize.voting_closes >= now) and
        prize.status == Prize.VOTING_OPEN
    )
    if not voting_allowed:
        return JsonResponse({'status': 'error', 'message': 'Voting is currently closed.'}, status=403)

    # Check player eligibility
    if not (prize.min_grade <= player.player_grade <= prize.max_grade):
        return JsonResponse({'status': 'error', 'message': 'This player is not eligible for this prize.'}, status=403)

    try:
        with transaction.atomic():
            # Get current vote status *before* making changes
            current_user_votes = Vote.objects.filter(prize=prize, voter=voter)
            current_vote_count = current_user_votes.count()
            already_voted_for_player = current_user_votes.filter(player=player).exists()

            if action_request == 'remove':
                if already_voted_for_player:
                    # Find and delete the vote
                    vote_to_remove = Vote.objects.get(prize=prize, voter=voter, player=player)
                    vote_to_remove.delete()
                    message = "Vote removed."
                else:
                    # This shouldn't happen if frontend is correct, but handle it
                    message = "You had not voted for this player."

            elif action_request == 'cast':
                if already_voted_for_player:
                    # This also shouldn't happen if frontend is correct
                    return JsonResponse({'status': 'success', 'message': 'You have already voted for this player.'})

                if current_vote_count >= 3:
                    # Check limit
                    return JsonResponse({
                        'status': 'limit_reached',
                        'message': 'Vote limit (3) reached. Remove a vote first.',
                        'user_vote_count': current_vote_count, # Return current count
                    }, status=403) # 403 Forbidden is appropriate for limit

                # Create the new vote
                Vote.objects.create(prize=prize, player=player, voter=voter)
                message = "Vote cast!"
            
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid action.'}, status=400)

            # Recalculate scores *after* transaction
            new_score = Vote.objects.filter(prize=prize, player=player).count()
            final_user_vote_count = Vote.objects.filter(prize=prize, voter=voter).count()
            # Check if user *now* has a vote for this player
            user_has_vote_now = Vote.objects.filter(prize=prize, voter=voter, player=player).exists()

        return JsonResponse({
            'status': 'success',
            'message': message,
            'new_score': new_score,
            'user_vote_count': final_user_vote_count,
            'voted': user_has_vote_now, # Tell frontend the *new* vote state for this player
            'player_id': player_id
        })

    except Exception as e:
        # Log the error e
        return JsonResponse({'status': 'error', 'message': f'An unexpected error occurred: {e}'}, status=500)


@login_required
@require_POST
def confirm_winner(request, prize_id):
    """
    Admin action to confirm a winner for a prize.
    This closes voting and sets the prize status to Decided.
    """
    prize = get_object_or_404(Prize, id=prize_id)
    
    # Security check: Only staff can do this
    if not request.user.is_staff:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    # Check if prize is already decided
    if prize.status == Prize.DECIDED:
        messages.warning(request, f"A winner has already been decided for {prize.name}.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    try:
        winner_player_id = int(request.POST.get('winner_player_id'))
        winner_player = get_object_or_404(Player, id=winner_player_id)
    except (TypeError, ValueError):
        messages.error(request, "Invalid player selected.")
        return redirect('awards:vote_prize', prize_id=prize.id)
    
    # Check eligibility just in case
    if not (prize.min_grade <= winner_player.player_grade <= prize.max_grade):
        messages.error(request, f"{winner_player.full_name} is not eligible for this prize.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    try:
        with transaction.atomic():
            # Get final score
            final_score = Vote.objects.filter(prize=prize, player=winner_player).count()
            
            # Create the winner record
            # Use update_or_create to prevent duplicates if this is re-run
            winner_record, created = PrizeWinner.objects.update_or_create(
                prize=prize,
                defaults={
                    'player': winner_player,
                    'award_date': timezone.now().date(),
                    'awarded_by': request.user,
                    'final_score': final_score
                }
            )
            
            # Update prize status
            prize.status = Prize.DECIDED
            prize.save()
            
            if created:
                messages.success(request, f"Confirmed {winner_player.full_name} as the winner for {prize.name}.")
            else:
                messages.info(request, f"Updated winner for {prize.name} to {winner_player.full_name}.")

    except Exception as e:
        # Log the error e
        messages.error(request, f"An error occurred while confirming the winner: {e}")

    return redirect('awards:vote_prize', prize_id=prize.id)

# Remove the 'nominate_prize' view if it's no longer used
# ...

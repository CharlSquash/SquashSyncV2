import json
from collections import defaultdict
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q, Prefetch
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from .models import Prize, PrizeCategory, Nomination, Vote, PrizeWinner # Added PrizeWinner
from players.models import Player

# --- Permission Helper Functions ---
def is_admin(user):
    """Check if the user is a superuser."""
    return user.is_superuser

def is_staff_or_admin(user):
    """Check if the user is staff or superuser."""
    return user.is_staff

# --- View Functions ---

@login_required
@user_passes_test(is_admin) # Only admins see the main list initially
def prize_list(request):
    """Displays a list of prizes, filterable by year."""
    current_year = timezone.now().year
    selected_year = request.GET.get('year', current_year)

    try:
        selected_year = int(selected_year)
    except (ValueError, TypeError):
        selected_year = current_year

    prizes = Prize.objects.filter(year=selected_year).select_related('category').order_by('category__name', 'name')
    available_years = Prize.objects.values_list('year', flat=True).distinct().order_by('-year')

    context = {
        'prizes': prizes,
        'selected_year': selected_year,
        'available_years': available_years,
        'page_title': f"Awards & Prizes ({selected_year})",
    }
    return render(request, 'awards/prize_list.html', context)


@login_required
@user_passes_test(is_admin) # Only admins can nominate
def nominate_prize(request, prize_id):
    """Handles viewing eligible players and nominating them for a prize."""
    prize = get_object_or_404(Prize, pk=prize_id)

    # Base queryset for eligible players
    eligible_players_qs = Player.objects.filter(is_active=True)
    if prize.min_grade is not None:
        eligible_players_qs = eligible_players_qs.filter(grade__gte=prize.min_grade)
    if prize.max_grade is not None:
        eligible_players_qs = eligible_players_qs.filter(grade__lte=prize.max_grade)

    eligible_players = list(eligible_players_qs.order_by('last_name', 'first_name'))

    # Get current nominations for this prize
    current_nominations = Nomination.objects.filter(prize=prize).select_related('player')
    nominated_player_ids = set(nom.player_id for nom in current_nominations)

    if request.method == 'POST':
        # Handle nomination submission
        selected_player_ids = set(map(int, request.POST.getlist('nominees')))
        justifications = {int(k.split('_')[1]): v.strip() for k, v in request.POST.items() if k.startswith('justification_') and v.strip()}

        # Players to add
        players_to_nominate_ids = selected_player_ids - nominated_player_ids
        # Nominations to remove
        nominations_to_remove_ids = nominated_player_ids - selected_player_ids

        if nominations_to_remove_ids:
            Nomination.objects.filter(prize=prize, player_id__in=nominations_to_remove_ids).delete()
            messages.success(request, f"Removed {len(nominations_to_remove_ids)} nomination(s).")

        added_count = 0
        for player_id in players_to_nominate_ids:
            Nomination.objects.create(
                prize=prize,
                player_id=player_id,
                nominated_by=request.user,
                justification=justifications.get(player_id, '')
            )
            added_count += 1
        if added_count > 0:
            messages.success(request, f"Added {added_count} new nomination(s).")

        # Update justifications for existing nominations if changed
        updated_justification_count = 0
        for nom in current_nominations:
            if nom.player_id in selected_player_ids: # Only update those still selected
                new_justification = justifications.get(nom.player_id, '')
                if nom.justification != new_justification:
                    nom.justification = new_justification
                    nom.save(update_fields=['justification'])
                    updated_justification_count += 1
        if updated_justification_count > 0:
             messages.info(request, f"Updated justification for {updated_justification_count} nomination(s).")

        return redirect('awards:nominate_prize', prize_id=prize.id) # Redirect back

    # Prepare player data for template (GET request)
    player_list_for_template = []
    for player in eligible_players:
        is_nominated = player.id in nominated_player_ids
        justification = ''
        if is_nominated:
            # Find the existing justification
            nomination = next((nom for nom in current_nominations if nom.player_id == player.id), None)
            if nomination:
                justification = nomination.justification or ''

        player_list_for_template.append({
            'player': player,
            'is_nominated': is_nominated,
            'justification': justification,
        })

    context = {
        'prize': prize,
        'player_list': player_list_for_template,
        'current_nominations': current_nominations,
        'page_title': f"Nominate Players for '{prize.name}' ({prize.year})",
    }
    return render(request, 'awards/nominate_prize.html', context)


@login_required
@user_passes_test(is_staff_or_admin) # Allow staff and admins to view/vote
def vote_prize(request, prize_id):
    """Displays nominees and allows interactive voting via AJAX."""
    prize = get_object_or_404(Prize.objects.prefetch_related('winners__player'), pk=prize_id) # Prefetch winner
    now_date = timezone.now().date()
    voting_allowed = prize.is_voting_open()

    nominations = Nomination.objects.filter(prize=prize).select_related(
        'player'
    ).prefetch_related(
        Prefetch('votes', queryset=Vote.objects.select_related('voter'))
    ).order_by('-total_vote_score', 'player__last_name')

    user_votes_details = Vote.objects.filter(nomination__prize=prize, voter=request.user).select_related('nomination')
    # Store comment along with nomination_id for JS
    user_votes = { vote.rank: {'nomination_id': vote.nomination_id, 'comment': vote.comment or ''} for vote in user_votes_details }
    has_voted = bool(user_votes)

    nominations_with_votes = []
    for nom in nominations:
        votes_for_nom = defaultdict(list)
        for vote in nom.votes.all():
            votes_for_nom[vote.rank].append({
                'voter': vote.voter.get_full_name() or vote.voter.username,
                'comment': vote.comment
            })
        nominations_with_votes.append({
            'nomination': nom,
            'votes_by_rank': dict(votes_for_nom)
        })

    context = {
        'prize': prize,
        'nominations_with_votes': nominations_with_votes,
        'voting_allowed': voting_allowed,
        'has_voted': has_voted,
        'user_votes_json': json.dumps(user_votes), # Pass votes as JSON for easier JS access
        'page_title': f"Vote for '{prize.name}' ({prize.year})",
    }
    return render(request, 'awards/vote_prize.html', context)


@require_POST
@login_required
@user_passes_test(is_staff_or_admin)
def cast_vote_ajax(request):
    """Handles AJAX requests to cast or remove a single ranked vote."""
    try:
        data = json.loads(request.body)
        nomination_id = int(data.get('nomination_id'))
        rank = int(data.get('rank'))
        comment = data.get('comment', '').strip()
        action = data.get('action', 'cast') # 'cast' or 'remove'

        nomination = get_object_or_404(Nomination.objects.select_related('prize'), pk=nomination_id)
        prize = nomination.prize

        if not prize.is_voting_open():
            return JsonResponse({'status': 'error', 'message': 'Voting is not open for this prize.'}, status=403)

        if rank not in [1, 2, 3]:
             return JsonResponse({'status': 'error', 'message': 'Invalid rank provided.'}, status=400)

        with transaction.atomic():
            # Check if user already voted for this RANK for this PRIZE (on a different nominee)
            existing_vote_for_rank = Vote.objects.filter(
                nomination__prize=prize,
                voter=request.user,
                rank=rank
            ).exclude(nomination_id=nomination_id).first()

            if existing_vote_for_rank:
                 # Silently remove the old vote for this rank if it's for a different nominee
                existing_vote_for_rank.delete()

            # Get the vote for the CURRENT nomination and voter (if it exists)
            current_vote_for_nominee = Vote.objects.filter(
                nomination=nomination,
                voter=request.user
            ).first()

            message = ""
            if action == 'remove':
                if current_vote_for_nominee and current_vote_for_nominee.rank == rank:
                    current_vote_for_nominee.delete()
                    message = f"Removed {rank}{'st' if rank==1 else 'nd' if rank==2 else 'rd'} choice vote."
                else:
                    # Trying to remove a rank not assigned, do nothing but maybe send info back
                    message = "No vote found to remove for this rank."

            elif action == 'cast':
                if current_vote_for_nominee:
                    # User is changing rank or comment for this nominee
                    if current_vote_for_nominee.rank != rank or current_vote_for_nominee.comment != comment:
                        current_vote_for_nominee.rank = rank
                        current_vote_for_nominee.comment = comment
                        current_vote_for_nominee.save()
                        message = f"Updated vote to {rank}{'st' if rank==1 else 'nd' if rank==2 else 'rd'} choice."
                    else:
                        message = "Vote unchanged." # No actual change needed
                else:
                    # User is casting a new vote for this nominee
                    Vote.objects.create(
                        nomination=nomination,
                        voter=request.user,
                        rank=rank,
                        comment=comment
                    )
                    message = f"Cast vote as {rank}{'st' if rank==1 else 'nd' if rank==2 else 'rd'} choice."

        # Fetch updated score *after* transaction completes
        # Need to refresh the instance to get the score updated by the signal/save method
        nomination.refresh_from_db()

        return JsonResponse({
            'status': 'success',
            'message': message,
            'nomination_id': nomination_id,
            'new_score': nomination.total_vote_score
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
    except (ValueError, TypeError):
         return JsonResponse({'status': 'error', 'message': 'Invalid data format.'}, status=400)
    except Nomination.DoesNotExist:
         return JsonResponse({'status': 'error', 'message': 'Nomination not found.'}, status=404)
    except Exception as e:
        # Log the error e for debugging
        print(f"Error in cast_vote_ajax: {e}") # Basic logging
        return JsonResponse({'status': 'error', 'message': 'An unexpected server error occurred.'}, status=500)


@require_POST # Ensure this view only accepts POST requests
@login_required
@user_passes_test(is_admin) # Only superusers can confirm winners
def confirm_winner(request, prize_id):
    """Handles the POST request from admin to confirm the winner."""
    prize = get_object_or_404(Prize, pk=prize_id)

    # Check if already decided
    if prize.status == Prize.PrizeStatus.DECIDED or prize.status == Prize.PrizeStatus.ARCHIVED:
        messages.warning(request, f"A winner has already been decided for {prize.name} ({prize.year}).")
        return redirect('awards:vote_prize', prize_id=prize.id)

    winner_nomination_id = request.POST.get('winner_nomination_id')

    if not winner_nomination_id:
        messages.error(request, "No winner was selected.")
        return redirect('awards:vote_prize', prize_id=prize.id)

    try:
        # Ensure the selected nomination belongs to the correct prize
        winner_nomination = get_object_or_404(Nomination.objects.select_related('player'), pk=int(winner_nomination_id), prize=prize)
        winner_player = winner_nomination.player

        with transaction.atomic():
            # Create or update the PrizeWinner entry
            # Using update_or_create handles potential race conditions or re-submissions
            prize_winner, created = PrizeWinner.objects.update_or_create(
                prize=prize,
                year=prize.year, # Ensure we use the prize's year
                defaults={
                    'player': winner_player,
                    'awarded_by': request.user,
                    'award_date': timezone.now().date() # Use current date as award date
                }
            )

            # Update the prize status
            prize.status = Prize.PrizeStatus.DECIDED
            prize.save(update_fields=['status'])

        messages.success(request, f"Confirmed {winner_player.full_name} as the winner for {prize.name} ({prize.year}). Voting is now closed.")

    except (ValueError, TypeError):
        messages.error(request, "Invalid nomination ID format.")
    except Nomination.DoesNotExist:
        messages.error(request, "Invalid selection for winner (Nomination not found or does not belong to this prize).")
    except Exception as e:
        # Log the error e for debugging
        print(f"Error in confirm_winner: {e}") # Basic logging
        messages.error(request, f"An unexpected error occurred while confirming the winner.")

    return redirect('awards:vote_prize', prize_id=prize.id) # Redirect back to the voting page


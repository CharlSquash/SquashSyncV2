from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Count, Q, F
from collections import defaultdict
from players.models import Player # Correct import for Player

User = settings.AUTH_USER_MODEL

class PrizeCategory(models.Model):
    # ... (PrizeCategory code remains the same) ...
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Prize Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

class Prize(models.Model):
    # ... (Prize fields remain the same) ...
    class PrizeStatus(models.TextChoices):
        VOTING = 'VOTING', 'Voting Open'
        DECIDED = 'DECIDED', 'Decided'
        ARCHIVED = 'ARCHIVED', 'Archived'

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(PrizeCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='prizes')
    year = models.PositiveIntegerField(default=timezone.now().year, help_text="The year this prize instance is for.")
    min_grade = models.IntegerField(choices=Player.GradeLevel.choices, null=True, blank=True, help_text="Minimum grade to be eligible (inclusive).")
    max_grade = models.IntegerField(choices=Player.GradeLevel.choices, null=True, blank=True, help_text="Maximum grade to be eligible (inclusive).")
    voting_start_date = models.DateField(null=True, blank=True)
    voting_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=PrizeStatus.choices, default=PrizeStatus.VOTING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    winner = models.ForeignKey(
        'PrizeWinner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_prize_direct'
    )

    class Meta:
        ordering = ['-year', 'category__name', 'name']
        unique_together = ('name', 'year')

    def __str__(self):
        return f"{self.name} ({self.year})"

    def is_voting_open(self):
        now = timezone.now().date()
        return (self.status == self.PrizeStatus.VOTING and
                (not self.voting_start_date or self.voting_start_date <= now) and
                (not self.voting_end_date or self.voting_end_date >= now))

    def get_eligible_players(self):
        # ... (get_eligible_players code remains the same) ...
        qs = Player.objects.filter(is_active=True)
        if self.min_grade is not None:
            qs = qs.filter(grade__gte=self.min_grade)
        if self.max_grade is not None:
            qs = qs.filter(grade__lte=self.max_grade)
        return qs.order_by('last_name', 'first_name')

    # --- CORRECTED get_results method ---
    def get_results(self):
        """Calculates simple vote count scores and returns sorted results as a list of dictionaries."""
        eligible_player_ids = self.get_eligible_players().values_list('id', flat=True)

        # Query players who are eligible AND have received votes for this prize
        players_with_votes = Player.objects.filter(
            id__in=eligible_player_ids,
            prize_votes__prize=self # Ensure votes are for this specific prize
        ).annotate(
            score=Count('prize_votes') # Count votes specifically for this player/prize combination
        ).filter(score__gt=0).prefetch_related(
             models.Prefetch(
                'prize_votes',
                queryset=Vote.objects.filter(prize=self).select_related('voter'),
                to_attr='votes_for_this_prize'
            )
        ).order_by('-score', 'last_name', 'first_name').distinct() # Add distinct to be safe

        results = [] # Initialize the list to store dictionaries
        for player in players_with_votes:
            votes_details = defaultdict(list)
            # Ensure votes_for_this_prize attribute exists before iterating
            if hasattr(player, 'votes_for_this_prize'):
                for vote in player.votes_for_this_prize:
                     votes_details['voters'].append({
                         'voter': vote.voter.get_full_name() or vote.voter.username,
                     })

            # Append a dictionary for each player to the results list
            results.append({
                'player': player,
                'score': player.score,
                'vote_count': player.score,
                'votes_by_voter': dict(votes_details)
            })

        # Ensure the list of dictionaries is returned
        return results
    # --- END CORRECTION ---

# ... (Vote and PrizeWinner models remain the same) ...
class Vote(models.Model):
    """ Records a simple vote (1 point) by a staff member for a Player in a Prize."""
    prize = models.ForeignKey(Prize, on_delete=models.CASCADE, related_name='votes')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='prize_votes')
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cast_prize_votes', limit_choices_to={'is_staff': True})
    voted_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['prize', 'player', 'voter', 'voted_at']
        unique_together = ('prize', 'player', 'voter')

    def __str__(self):
        return f"{self.voter.username}'s vote for {self.player.short_name} in {self.prize}"


class PrizeWinner(models.Model):
    """ Stores the history of prize winners. """
    prize = models.OneToOneField(Prize, on_delete=models.CASCADE, related_name='winner_details')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='prizes_won')
    year = models.PositiveIntegerField(
        default=timezone.now().year,
        help_text="The year the prize was awarded.",
        editable=False
    )
    awarded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='awarded_prizes', limit_choices_to={'is_superuser': True})
    award_date = models.DateField(default=timezone.now)
    final_score = models.IntegerField(null=True, blank=True, help_text="The winner's final vote count at time of awarding.")

    class Meta:
        ordering = ['-year', 'prize__category__name', 'prize__name']
        unique_together = ('prize', 'year')

    def save(self, *args, **kwargs):
        if self.prize:
            self.year = self.prize.year
        super().save(*args, **kwargs)
        if self.prize and getattr(self.prize, 'winner', None) != self:
             self.prize.winner = self
             self.prize.save(update_fields=['winner'])

    def __str__(self):
        return f"{self.player.full_name} - Winner of {self.prize} ({self.year})"


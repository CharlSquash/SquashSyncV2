from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, F, Window
from django.db.models.functions import Rank
from players.models import Player # Explicit import from players app

User = get_user_model()

class PrizeCategory(models.Model):
    """ Category for grouping prizes (e.g., Performance, Sportsmanship). """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Prize Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

class Prize(models.Model):
    """ Represents an award that can be voted on. """
    class PrizeStatus(models.TextChoices):
        # Removed NOMINATION status as it wasn't used
        PENDING = 'PENDING', 'Pending' # Before voting starts
        VOTING = 'VOTING', 'Voting Open'
        DECIDED = 'DECIDED', 'Winner Decided'
        ARCHIVED = 'ARCHIVED', 'Archived'

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    year = models.PositiveIntegerField(default=timezone.now().year)
    category = models.ForeignKey(PrizeCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='prizes')

    status = models.CharField(
        max_length=10,
        choices=PrizeStatus.choices,
        default=PrizeStatus.PENDING,
        db_index=True
    )

    # Simplified voting period
    voting_opens = models.DateTimeField(null=True, blank=True, help_text="When voting becomes available.")
    voting_closes = models.DateTimeField(null=True, blank=True, help_text="When voting ends.")

    # Eligibility criteria (optional)
    min_grade = models.PositiveIntegerField(null=True, blank=True, help_text="Minimum grade (e.g., 8) to be eligible.")
    max_grade = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum grade (e.g., 12) to be eligible.")

    winner = models.OneToOneField(
        'PrizeWinner',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='won_prize', # Allows PrizeWinner.won_prize access
        help_text="The confirmed winner for this prize."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['year', 'category__name', 'name']
        unique_together = ('name', 'year') # Ensure prize names are unique within a year

    def __str__(self):
        return f"{self.name} ({self.year})"

    def is_voting_open(self):
        """ Check if voting is currently allowed based on status and dates. """
        now = timezone.now()
        # --- Adjusted Logic: Voting is open IF status is VOTING *and* within dates (if set) ---
        if self.status != self.PrizeStatus.VOTING:
            return False

        starts_ok = self.voting_opens is None or now >= self.voting_opens
        ends_ok = self.voting_closes is None or now <= self.voting_closes
        return starts_ok and ends_ok

    def get_eligible_players(self):
        """ Returns a queryset of players eligible for this prize based on grade. """
        players = Player.objects.filter(is_active=True) # Start with active players
        if self.min_grade is not None:
            players = players.filter(grade__gte=self.min_grade)
        if self.max_grade is not None:
            players = players.filter(grade__lte=self.max_grade)
        return players

    def get_results(self):
        """
        Calculates the current voting results for this prize.
        Returns a list of dictionaries: [{'player': Player, 'score': int}]
        ordered by score descending, then player name.
        Only includes players with at least one vote.
        """
        eligible_player_ids = self.get_eligible_players().values_list('id', flat=True)

        results_qs = Player.objects.filter(
            id__in=eligible_player_ids # Only consider eligible players
        ).annotate(
            score=Count('prize_votes', filter=Q(prize_votes__prize=self)) # Count votes ONLY for this specific prize
        ).filter(
            score__gt=0 # Only include players who have received at least one vote
        # --- FIX: Order by actual database fields ---
        ).order_by('-score', 'last_name', 'first_name') # Order by score desc, then name asc

        # Convert queryset to the desired list of dictionaries format
        results = [
            {'player': player, 'score': player.score}
            for player in results_qs
        ]
        return results


class Vote(models.Model):
    """ Records a simple vote (1 point) by a staff member for a Player in a Prize."""
    prize = models.ForeignKey(Prize, on_delete=models.CASCADE, related_name='prize_votes')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='prize_votes')
    # Limit voter choices to staff members in the model definition
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cast_prize_votes', limit_choices_to={'is_staff': True})
    voted_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-voted_at']
        # Ensure a user can only vote once per player per prize
        unique_together = ('prize', 'player', 'voter')

    def __str__(self):
        # Use player's full_name property if available, otherwise fallback
        player_name = getattr(self.player, 'full_name', f"{self.player.first_name} {self.player.last_name}") if self.player else "Unknown Player"
        voter_name = self.voter.username if self.voter else "Unknown Voter"
        prize_name = str(self.prize) if self.prize else "Unknown Prize"
        return f"{voter_name}'s vote for {player_name} in {prize_name}"


class PrizeWinner(models.Model):
    """ Stores the confirmed winner of a specific prize for a given year. """
    prize = models.OneToOneField(Prize, on_delete=models.CASCADE, related_name='prize_winner_details') # Changed related name
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='won_prizes')
    year = models.PositiveIntegerField() # Store year directly for easier filtering/indexing
    final_score = models.PositiveIntegerField(null=True, blank=True, help_text="The vote score the player had when confirmed.")
    awarded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='awarded_prizes')
    award_date = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['-year', 'prize__category__name', 'prize__name']
        unique_together = ('prize',) # Only one winner per prize instance

    def __str__(self):
        player_name = getattr(self.player, 'full_name', f"{self.player.first_name} {self.player.last_name}") if self.player else "Unknown Player"
        prize_name = self.prize.name if self.prize else "Unknown Prize"
        return f"{player_name} - Winner of {prize_name} ({self.year})"


# awards/models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, F

# Explicit import from players app, including GenderChoices
from players.models import Player, GenderChoices

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
        PENDING = 'PENDING', 'Pending' # Before voting starts
        VOTING = 'VOTING', 'Voting Open'
        DECIDED = 'DECIDED', 'Winner Decided'
        ARCHIVED = 'ARCHIVED', 'Archived'

    # NEW: Gender Eligibility Choices
    class GenderEligibility(models.TextChoices):
        ANY = 'A', 'Any Gender'
        MALE_ONLY = 'M', 'Male Only'
        FEMALE_ONLY = 'F', 'Female Only'

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

    voting_opens = models.DateTimeField(null=True, blank=True, help_text="Optional: When voting becomes available.")
    voting_closes = models.DateTimeField(null=True, blank=True, help_text="Optional: When voting ends.")

    # Eligibility criteria (optional)
    min_grade = models.PositiveIntegerField(
        null=True, blank=True,
        choices=Player.GradeLevel.choices,
        help_text="Minimum grade (inclusive) to be eligible."
    )
    max_grade = models.PositiveIntegerField(
        null=True, blank=True,
        choices=Player.GradeLevel.choices,
        help_text="Maximum grade (inclusive) to be eligible."
    )
    # NEW: Gender Eligibility Field
    gender_eligibility = models.CharField(
        max_length=1,
        choices=GenderEligibility.choices,
        default=GenderEligibility.ANY,
        help_text="Which gender(s) are eligible for this prize?"
    )

    # Link to the winner record (can be null before decided)
    winner = models.OneToOneField(
        'PrizeWinner',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='won_prize',
        help_text="The confirmed winner for this prize."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', 'category__name', 'name']
        unique_together = ('name', 'year') # Ensure prize names are unique within a year

    def __str__(self):
        return f"{self.name} ({self.year})"

    def is_voting_open_now(self):
        """ Check if voting is currently allowed based on status and dates. """
        if self.status != self.PrizeStatus.VOTING:
            return False
        now = timezone.now()
        starts_ok = self.voting_opens is None or now >= self.voting_opens
        ends_ok = self.voting_closes is None or now <= self.voting_closes
        return starts_ok and ends_ok

    # UPDATED: get_eligible_players method
    def get_eligible_players(self):
        """ Returns a queryset of players eligible for this prize based on grade AND gender. """
        players = Player.objects.filter(is_active=True)
        if self.min_grade is not None:
            players = players.filter(grade__gte=self.min_grade)
        if self.max_grade is not None:
            players = players.filter(grade__lte=self.max_grade)

        # Add gender filtering using GenderChoices from players.models
        if self.gender_eligibility == self.GenderEligibility.MALE_ONLY:
            players = players.filter(gender=GenderChoices.MALE)
        elif self.gender_eligibility == self.GenderEligibility.FEMALE_ONLY:
            players = players.filter(gender=GenderChoices.FEMALE)
        # No filter needed for 'ANY'

        return players.order_by('last_name', 'first_name')

    def get_results(self):
        """
        Calculates the current voting results for this prize.
        Returns a list of dictionaries: [{'player': Player, 'score': int}]
        ordered by score descending, then player name.
        Only includes players with at least one vote.
        """
        eligible_player_ids = self.get_eligible_players().values_list('id', flat=True)

        results_qs = Player.objects.filter(
            id__in=eligible_player_ids
        ).annotate(
            score=Count('prize_votes', filter=Q(prize_votes__prize=self))
        ).filter(
            score__gt=0
        ).order_by('-score', 'last_name', 'first_name')

        results = [{'player': player, 'score': player.score} for player in results_qs]
        return results

class Vote(models.Model):
    """ Records a simple vote (1 point) by a staff member for a Player in a Prize."""
    prize = models.ForeignKey(Prize, on_delete=models.CASCADE, related_name='prize_votes')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='prize_votes')
    voter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cast_prize_votes',
        limit_choices_to={'is_staff': True} # Keep this if only staff can vote
    )
    voted_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-voted_at']
        unique_together = ('prize', 'player', 'voter')

    def __str__(self):
        player_name = getattr(self.player, 'full_name', 'Unknown Player')
        voter_name = getattr(self.voter, 'username', 'Unknown Voter')
        prize_name = str(self.prize) if self.prize else "Unknown Prize"
        return f"{voter_name}'s vote for {player_name} in {prize_name}"

    def clean(self):
        # Check eligibility on save (now includes gender check implicitly via prize.get_eligible_players)
        if self.prize and self.player:
             # Use the updated get_eligible_players method which includes gender check
            if not self.prize.get_eligible_players().filter(pk=self.player.pk).exists():
                 raise ValidationError(f"{self.player.full_name} is not eligible for this prize based on grade or gender criteria.")

        # Check vote limit
        if self.pk is None: # Only check on creation
            current_votes = Vote.objects.filter(prize=self.prize, voter=self.voter).count()
            if current_votes >= 3:
                raise ValidationError("Vote limit (3) reached for this prize.")

class PrizeWinner(models.Model):
    """ Stores the confirmed winner of a specific prize instance. """
    prize = models.OneToOneField(
        Prize,
        on_delete=models.CASCADE,
        related_name='prize_winner_details' # Allows Prize.prize_winner_details
    )
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='won_prizes')
    # Store year directly for easier filtering/indexing (copied from Prize)
    year = models.PositiveIntegerField(editable=False)
    final_score = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="The vote score the player had when confirmed."
    )
    awarded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='awarded_prizes'
    )
    award_date = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['-year', 'prize__category__name', 'prize__name']
        unique_together = ('prize',) # Only one winner per prize instance

    def __str__(self):
        player_name = getattr(self.player, 'full_name', 'Unknown Player')
        prize_name = getattr(self.prize, 'name', 'Unknown Prize')
        return f"{player_name} - Winner of {prize_name} ({self.year})"

    def save(self, *args, **kwargs):
        # Ensure the year matches the prize's year
        if self.prize:
            self.year = self.prize.year
        super().save(*args, **kwargs)
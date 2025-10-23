# awards/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from players.models import Player, Player

User = settings.AUTH_USER_MODEL

class PrizeCategory(models.Model):
    """
    Optional category to group prizes (e.g., Junior Awards, Senior Awards).
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Prize Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

class Prize(models.Model):
    """
    Defines an award, its criteria, and its status.
    """
    class PrizeStatus(models.TextChoices):
        NOMINATING = 'NOMINATING', 'Nominating'
        VOTING = 'VOTING', 'Voting Open'
        DECIDED = 'DECIDED', 'Decided'
        ARCHIVED = 'ARCHIVED', 'Archived' # For past years

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(PrizeCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='prizes')
    year = models.PositiveIntegerField(default=timezone.now().year, help_text="The year this prize instance is for.")

    # Eligibility Criteria
    min_grade = models.IntegerField(choices=Player.GradeLevel.choices, null=True, blank=True, help_text="Minimum grade to be eligible (inclusive).")
    max_grade = models.IntegerField(choices=Player.GradeLevel.choices, null=True, blank=True, help_text="Maximum grade to be eligible (inclusive).")
    # Add other criteria fields here if needed later (e.g., specific SchoolGroup ForeignKey)

    # Voting Period & Status
    voting_start_date = models.DateField(null=True, blank=True)
    voting_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=PrizeStatus.choices, default=PrizeStatus.NOMINATING)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', 'category__name', 'name']
        unique_together = ('name', 'year') # Ensure prize names are unique per year

    def __str__(self):
        return f"{self.name} ({self.year})"

    def is_voting_open(self):
        now = timezone.now().date()
        return (self.status == self.PrizeStatus.VOTING and
                (not self.voting_start_date or self.voting_start_date <= now) and
                (not self.voting_end_date or self.voting_end_date >= now))

class Nomination(models.Model):
    """
    Links a Player to a Prize for which they are nominated.
    """
    prize = models.ForeignKey(Prize, on_delete=models.CASCADE, related_name='nominations')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='nominations')
    nominated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='made_nominations', limit_choices_to={'is_superuser': True})
    nomination_date = models.DateTimeField(auto_now_add=True)
    justification = models.TextField(blank=True, null=True, help_text="Optional reason for nomination.")

    # Denormalized field for sorting by vote score
    total_vote_score = models.IntegerField(default=0, db_index=True)

    class Meta:
        ordering = ['prize', '-total_vote_score', 'player__last_name', 'player__first_name']
        unique_together = ('prize', 'player') # A player can only be nominated once per prize per year

    def __str__(self):
        return f"{self.player.full_name} nominated for {self.prize}"

    def calculate_vote_score(self):
        """Calculates the total score based on received votes."""
        score = 0
        for vote in self.votes.all():
            if vote.rank == 1:
                score += 3
            elif vote.rank == 2:
                score += 2
            elif vote.rank == 3:
                score += 1
        return score

    def update_vote_score(self):
        """Updates and saves the denormalized score."""
        self.total_vote_score = self.calculate_vote_score()
        self.save(update_fields=['total_vote_score'])


class Vote(models.Model):
    """
    Records a ranked vote by a staff member for a nomination.
    """
    nomination = models.ForeignKey(Nomination, on_delete=models.CASCADE, related_name='votes')
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cast_votes', limit_choices_to={'is_staff': True})
    rank = models.PositiveSmallIntegerField(choices=[(1, '1st Choice'), (2, '2nd Choice'), (3, '3rd Choice')])
    comment = models.TextField(blank=True, null=True, help_text="Optional comment explaining the vote.")
    voted_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nomination', 'rank', 'voted_at']
        # Ensures one user gets only one vote of a specific rank per prize
        unique_together = ('nomination__prize', 'voter', 'rank')
        # Also ensures a voter doesn't vote for the same nominee multiple times with different ranks
        unique_together = ('nomination', 'voter')

    def __str__(self):
        return f"{self.voter.username}'s {self.get_rank_display()} vote for {self.nomination}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update the nomination's score whenever a vote is saved or deleted
        self.nomination.update_vote_score()

    def delete(self, *args, **kwargs):
        nomination = self.nomination # Store nomination before deleting self
        super().delete(*args, **kwargs)
        # Update score after deletion
        nomination.update_vote_score()


class PrizeWinner(models.Model):
    """
    Stores the history of prize winners.
    """
    prize = models.ForeignKey(Prize, on_delete=models.CASCADE, related_name='winners')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='prizes_won')
    year = models.PositiveIntegerField(help_text="The year the prize was awarded.")
    awarded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='awarded_prizes', limit_choices_to={'is_superuser': True})
    award_date = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['-year', 'prize__category__name', 'prize__name']
        unique_together = ('prize', 'year') # Only one winner per prize per year

    def __str__(self):
        return f"{self.player.full_name} - Winner of {self.prize} ({self.year})"
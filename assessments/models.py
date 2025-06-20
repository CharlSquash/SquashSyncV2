# assessments/models.py
from django.db import models
from django.utils import timezone
from django.conf import settings

User = settings.AUTH_USER_MODEL

# --- MODEL: SessionAssessment (Individual Player Assessment for a Session) ---
class SessionAssessment(models.Model):
    class Rating(models.IntegerChoices):
        POOR = 1, 'Poor'
        BELOW_AVERAGE = 2, 'Below Average'
        AVERAGE = 3, 'Average'
        GOOD = 4, 'Good'
        EXCELLENT = 5, 'Excellent'

    # IMPORTANT: Updated FKs
    session = models.ForeignKey('scheduling.Session', on_delete=models.CASCADE, related_name='session_assessments')
    player = models.ForeignKey('players.Player', on_delete=models.CASCADE, related_name='session_assessments_by_player')
    
    date_recorded = models.DateField(default=timezone.now)
    effort_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    focus_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    resilience_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    composure_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    decision_making_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    coach_notes = models.TextField(blank=True)
    
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='submitted_player_assessments',
        limit_choices_to={'is_staff': True}
    )
    is_hidden = models.BooleanField(default=False, help_text="If true, this assessment is hidden from player/parent view.")
    superuser_reviewed = models.BooleanField(default=False, db_index=True, help_text="Superuser has reviewed this assessment.")

    def __str__(self):
        submitter_name = self.submitted_by.username if self.submitted_by else "Unknown"
        return f"Assessment for {self.player} in {self.session} by {submitter_name}"
        
    class Meta:
        unique_together = ('session', 'player', 'submitted_by')
        ordering = ['-date_recorded', 'player__last_name']

# --- MODEL: GroupAssessment ---
class GroupAssessment(models.Model):
    session = models.ForeignKey('scheduling.Session', on_delete=models.CASCADE, related_name='group_assessments')
    assessing_coach = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_group_assessments',
        limit_choices_to={'is_staff': True},
    )
    assessment_datetime = models.DateTimeField(default=timezone.now)
    general_notes = models.TextField(blank=True, help_text="Coach's notes for the group/session.")
    is_hidden_from_other_coaches = models.BooleanField(default=False, help_text="Hide from other coaches.")
    superuser_reviewed = models.BooleanField(default=False, db_index=True, help_text="Superuser has reviewed this.")

    def __str__(self):
        coach_name = self.assessing_coach.username if self.assessing_coach else "Unknown"
        group_name = self.session.school_group.name if self.session and self.session.school_group else "N/A Group"
        return f"Group Assessment for {group_name} by {coach_name}"

    class Meta:
        ordering = ['-assessment_datetime', 'session']
        unique_together = ('session', 'assessing_coach')
        verbose_name = "Group Assessment"
        verbose_name_plural = "Group Assessments"

# --- MODEL: CoachFeedback (General Player Feedback, not session specific) ---
class CoachFeedback(models.Model):
    player = models.ForeignKey('players.Player', on_delete=models.CASCADE, related_name='feedback_entries')
    session = models.ForeignKey('scheduling.Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='feedback_entries')
    date_recorded = models.DateTimeField(default=timezone.now)
    strengths_observed = models.TextField(blank=True, verbose_name="Strengths Observed")
    areas_for_development = models.TextField(blank=True, verbose_name="Areas for Development")
    suggested_focus = models.TextField(blank=True, verbose_name="Suggested Focus/Next Steps")
    general_notes = models.TextField(blank=True, verbose_name="General Notes")

    class Meta:
        ordering = ['-date_recorded', 'player__last_name']
        verbose_name = "Coach Feedback"
        verbose_name_plural = "Coach Feedback Entries"

    def __str__(self):
        return f"Feedback for {self.player.full_name} on {self.date_recorded.strftime('%Y-%m-%d')}"
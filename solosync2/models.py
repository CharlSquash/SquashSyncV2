# solosync2/models.py
from django.db import models
from django.utils import timezone
from players.models import Player
from scheduling.models import Drill 

class Routine(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, help_text="Inactive routines won't be shown to players.")

    drills = models.ManyToManyField(
        Drill,
        through='RoutineDrill',
        related_name='routines'
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class RoutineDrill(models.Model):
    """
    This is a "through" model that connects a Routine to a Drill.
    It allows us to specify the order and duration of each drill within a routine.
    """
    routine = models.ForeignKey(Routine, on_delete=models.CASCADE, related_name='drills_in_routine')
    drill = models.ForeignKey(Drill, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(help_text="The order of the drill in the routine (e.g., 1, 2, 3...).")
    duration_minutes = models.PositiveIntegerField(
        help_text="Duration in minutes for this drill within this specific routine.",
        null=True, blank=True
    )
    # --- ADD THIS NEW FIELD ---
    rest_duration_seconds = models.PositiveIntegerField(
        default=30,
        help_text="Rest time in seconds after this drill is completed."
    )

    class Meta:
        ordering = ['routine', 'order']
        unique_together = ('routine', 'drill', 'order')

    def __str__(self):
        return f"{self.routine.name} - {self.order}: {self.drill.name}"

class SoloSessionLog(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='solo_sessions')
    routine = models.ForeignKey(Routine, on_delete=models.SET_NULL, null=True, blank=True, related_name='solo_sessions')
    completed_at = models.DateTimeField(default=timezone.now)
    difficulty_rating = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Player's perceived difficulty (1-5).")
    likelihood_rating = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Player's likelihood to repeat the routine (1-5).")
    notes = models.TextField(blank=True, null=True, help_text="Player's personal notes on the session.")

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        return f"Solo Session for {self.player.full_name} on {self.completed_at.strftime('%Y-%m-%d')}"
from django.db import models
from django.core.validators import MinValueValidator

# Create your models here.

class Drill(models.Model):
    CATEGORY_CHOICES = [
        ('Conditioning', 'Conditioning'),
        ('Warmups', 'Warmups'),
        ('Hand-Eye Coordination', 'Hand-Eye Coordination'),
        ('Fun Games', 'Fun Games'),
        ('Ghosting', 'Ghosting'),
        ('Drills - Racketwork', 'Drills - Racketwork'),
        ('Feeding Drills', 'Feeding Drills'),
        ('Condition Games', 'Condition Games'),
        ('Fitness', 'Fitness'),
        ('Movement', 'Movement'),
        ('Circuits (Score/Time)', 'Circuits (Score/Time)'),
        ('Squash Basics', 'Squash Basics'),
    ]

    DIFFICULTY_CHOICES = [
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
    ]

    created_by = models.ForeignKey('accounts.Coach', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_drills', help_text="The coach who created this custom drill.")
    is_approved = models.BooleanField(default=False, help_text="If False, only the creator can see this drill.")

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='Beginner')
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=10, help_text="Duration in minutes")
    default_duration = models.PositiveIntegerField(default=180, help_text="Duration in seconds (deprecated)")
    video_url = models.URLField(blank=True, null=True)
    equipment = models.CharField(max_length=200, blank=True, help_text="Equipment needed for this drill (e.g. 'Cones', 'Target Board')")
    resource_text = models.TextField(blank=True, help_text="Text content for rules, marking guides, etc.")
    resource_url = models.URLField(blank=True, null=True, help_text="Link to external document (e.g., Google Drive)")

    def __str__(self):
        return self.name

class SessionPlan(models.Model):
    session = models.ForeignKey('scheduling.Session', on_delete=models.CASCADE, related_name='plans')
    plan_data = models.JSONField(help_text="JSON structure of the session plan")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Plan for {self.session}"

class PlanTemplate(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey('accounts.Coach', on_delete=models.SET_NULL, null=True, blank=True)
    is_public = models.BooleanField(default=False, help_text="Visible to all coaches")
    court_count = models.PositiveIntegerField(default=3, help_text="Number of courts this plan was designed for")
    plan_data = models.JSONField(help_text="The full courtPlans JSON structure")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.created_by})"

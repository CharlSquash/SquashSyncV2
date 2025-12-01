from django.db import models
from django.core.validators import MinValueValidator

# Create your models here.

class Drill(models.Model):
    CATEGORY_CHOICES = [
        ('Technical', 'Technical'),
        ('Conditioning', 'Conditioning'),
    ]

    DIFFICULTY_CHOICES = [
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
    ]

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='Beginner')
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=10, help_text="Duration in minutes")
    default_duration = models.PositiveIntegerField(default=180, help_text="Duration in seconds (deprecated)")
    video_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name

class SessionPlan(models.Model):
    session = models.ForeignKey('scheduling.Session', on_delete=models.CASCADE, related_name='plans')
    plan_data = models.JSONField(help_text="JSON structure of the session plan")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Plan for {self.session}"

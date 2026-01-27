# players/models.py
import io
import re
import os
from PIL import Image, ImageOps

from django.db import models
from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings
from core.utils import process_profile_image

# --- MODEL: SchoolGroup ---
class SchoolGroup(models.Model):
    name = models.CharField(max_length=100) # Removed unique=True
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    year = models.IntegerField(null=True, blank=True)
    attendance_form_url = models.URLField(
        max_length=1024, blank=True, null=True, verbose_name="Attendance Form URL",
        help_text="Link to the external Google Form or attendance sheet for this group."
    )
    def __str__(self):
        return self.name
    class Meta:
        ordering = ['-is_active', 'name']
        permissions = [
            ("can_manage_school_groups", "Can manage school groups"),
        ]

class GenderChoices(models.TextChoices):
    MALE = 'M', 'Male'
    FEMALE = 'F', 'Female'
    OTHER = 'O', 'Other / Prefer not to say'
    UNSPECIFIED = 'U', 'Unspecified' # Default
# --- MODEL: Player ---
class Player(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='player_profile',
        null=True,
        blank=True
    )
    
    class GradeLevel(models.IntegerChoices):
        GRADE_R = 0, 'Grade R'
        GRADE_1 = 1, 'Grade 1'
        GRADE_2 = 2, 'Grade 2'
        GRADE_3 = 3, 'Grade 3'
        GRADE_4 = 4, 'Grade 4'
        GRADE_5 = 5, 'Grade 5'
        GRADE_6 = 6, 'Grade 6'
        GRADE_7 = 7, 'Grade 7'
        GRADE_8 = 8, 'Grade 8'
        GRADE_9 = 9, 'Grade 9'
        GRADE_10 = 10, 'Grade 10'
        GRADE_11 = 11, 'Grade 11'
        GRADE_12 = 12, 'Grade 12 (Matric)'
        OTHER = 99, 'Other / Not Applicable'

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    gender = models.CharField(
        max_length=1,
        choices=GenderChoices.choices,
        default=GenderChoices.UNSPECIFIED,
        null=True, # Allows existing records to be null initially
        blank=True, # Allows the field to be blank in forms/admin
        verbose_name="Gender"
    )
    school = models.CharField(max_length=100, blank=True, help_text="The school the player attends.")
    grade = models.IntegerField(
        choices=GradeLevel.choices,
        null=True,
        blank=True,
        verbose_name="School Grade"
    )
    
    school_groups = models.ManyToManyField('SchoolGroup', related_name='players', blank=True)
    contact_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Player Contact Number",
        help_text="Enter number including country code if outside SA (e.g., +44... or 082...)"
    )
    parent_contact_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Primary Guardian Contact Number",
        help_text="Primary contact for session reminders. Enter number including country code if outside SA (e.g., +44... or 082...)"
    )
    parent_email = models.EmailField(
        max_length=254, 
        blank=True, 
        null=True, 
        verbose_name="Primary Guardian Email",
        help_text="The primary email for parent communication and session reminders."
    )

    # Secondary Guardian
    guardian_2_name = models.CharField(max_length=100, blank=True, verbose_name="Secondary Guardian Name")
    guardian_2_contact_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Secondary Guardian Contact Number",
        help_text="Enter number including country code."
    )
    guardian_2_email = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
        verbose_name="Secondary Guardian Email"
    )

    # Health & Safety
    medical_aid_number = models.CharField(max_length=100, blank=True, verbose_name="Medical Aid Number")
    health_information = models.TextField(
        blank=True, 
        verbose_name="Health Information",
        help_text="Allergies, illnesses, or specific medical conditions."
    )
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    photo = models.ImageField(upload_to='player_photos/', null=True, blank=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def active_groups(self):
        """
        Returns a list of active school groups.
        Uses prefetched data if available (via to_attr='_active_groups_cache').
        """
        if hasattr(self, '_active_groups_cache'):
            return self._active_groups_cache
        return self.school_groups.filter(is_active=True)

    @property
    def past_groups(self):
        """
        Returns a list of inactive school groups, ordered by year (descending).
        Uses prefetched data if available (via to_attr='_past_groups_cache').
        """
        if hasattr(self, '_past_groups_cache'):
            return self._past_groups_cache
        return self.school_groups.filter(is_active=False).order_by('-year')

    def _format_for_whatsapp(self, number_str):
        if not number_str:
            return None
        cleaned_number = re.sub(r'[+\s\-\(\)]', '', number_str)
        if cleaned_number.startswith('0'):
            cleaned_number = '27' + cleaned_number[1:]
        if re.match(r'^\d{10,15}$', cleaned_number):
            return cleaned_number
        return None

    @property
    def whatsapp_number(self):
        return self._format_for_whatsapp(self.contact_number)

    @property
    def parent_whatsapp_number(self):
        return self._format_for_whatsapp(self.parent_contact_number)

    @property
    def guardian_2_whatsapp_number(self):
        return self._format_for_whatsapp(self.guardian_2_contact_number)

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        original_filename = None
        process_image = False

        if self.pk:
            try:
                old_instance = Player.objects.get(pk=self.pk)
                if self.photo and old_instance.photo != self.photo:
                    process_image = True
                    if hasattr(self.photo, 'name') and self.photo.name:
                        original_filename = self.photo.name
                elif not self.photo and old_instance.photo:
                    pass
            except Player.DoesNotExist:
                if self.photo:
                    process_image = True
                    if hasattr(self.photo, 'name') and self.photo.name:
                        original_filename = self.photo.name
        elif self.photo:
            process_image = True
            if hasattr(self.photo, 'name') and self.photo.name:
                original_filename = self.photo.name

        super().save(*args, **kwargs)

        if process_image and self.photo and hasattr(self.photo, 'path') and self.photo.path:
            try:
                filename_to_save, resized_image = process_profile_image(self.photo, original_filename)

                current_photo_name = self.photo.name

                self.photo.save(filename_to_save, resized_image, save=False)

                if current_photo_name != self.photo.name or kwargs.get('force_insert', False):
                    super().save(update_fields=['photo'])

            except FileNotFoundError:
                print(f"File not found for player photo {self.full_name}: {getattr(self.photo, 'path', 'No path')}")
            except Exception as e:
                print(f"Error processing player photo for {self.full_name}: {e}")

    class Meta:
        ordering = ['last_name', 'first_name']

class AttendanceDiscrepancy(models.Model):
    class DiscrepancyType(models.TextChoices):
        NO_SHOW = 'NO_SHOW', 'No-Show'
        UNEXPECTED = 'UNEXPECTED', 'Unexpected'
        NEVER_NOTIFIED = 'NEVER_NOTIFIED', 'Never Notified'

    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='attendance_discrepancies')
    session = models.ForeignKey('scheduling.Session', on_delete=models.CASCADE, related_name='attendance_discrepancies')
    discrepancy_type = models.CharField(max_length=20, choices=DiscrepancyType.choices)
    parent_response = models.CharField(max_length=20)
    coach_marked_attendance = models.CharField(max_length=10)
    admin_acknowledged = models.BooleanField(default=False)
    recorded_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_discrepancy_type_display()} for {self.player.full_name} on {self.session.session_date}"

    class Meta:
        ordering = ['-recorded_at']
        unique_together = ('player', 'session')

# --- METRIC MODELS ---

class CourtSprintRecord(models.Model):
    class DurationChoice(models.TextChoices):
        THREE_MIN = '3m', '3 Minutes'
        FIVE_MIN = '5m', '5 Minutes'
        TEN_MIN = '10m', '10 Minutes'
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='sprint_records')
    date_recorded = models.DateField(default=timezone.now)
    duration_choice = models.CharField(max_length=3, choices=DurationChoice.choices)
    score = models.PositiveIntegerField(help_text="Number of full court lengths completed.")
    # IMPORTANT: Updated ForeignKey to point to the new 'scheduling' app
    session = models.ForeignKey('scheduling.Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='sprint_tests_conducted', help_text="Optional: Link to session where this test was conducted.")
    def __str__(self):
        return f"Sprint ({self.get_duration_choice_display()}) for {self.player} on {self.date_recorded}: {self.score}"
    class Meta:
        ordering = ['-date_recorded', 'duration_choice']

class VolleyRecord(models.Model):
    class ShotType(models.TextChoices):
        FOREHAND = 'FH', 'Forehand'
        BACKHAND = 'BH', 'Backhand'
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='volley_records')
    date_recorded = models.DateField(default=timezone.now)
    shot_type = models.CharField(max_length=2, choices=ShotType.choices)
    consecutive_count = models.PositiveIntegerField()
    # IMPORTANT: Updated ForeignKey to point to the new 'scheduling' app
    session = models.ForeignKey('scheduling.Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='volley_tests_conducted', help_text="Optional: Link to session where this test was conducted.")
    def __str__(self):
        return f"{self.get_shot_type_display()} Volley for {self.player} on {self.date_recorded}: {self.consecutive_count}"
    class Meta:
        ordering = ['-date_recorded', 'shot_type']

class BackwallDriveRecord(models.Model):
    class ShotType(models.TextChoices):
        FOREHAND = 'FH', 'Forehand'
        BACKHAND = 'BH', 'Backhand'
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='drive_records')
    date_recorded = models.DateField(default=timezone.now)
    shot_type = models.CharField(max_length=2, choices=ShotType.choices)
    consecutive_count = models.PositiveIntegerField()
    # IMPORTANT: Updated ForeignKey to point to the new 'scheduling' app
    session = models.ForeignKey('scheduling.Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='drive_tests_conducted', help_text="Optional: Link to session where this test was conducted.")
    def __str__(self):
        return f"{self.get_shot_type_display()} Drive for {self.player} on {self.date_recorded}: {self.consecutive_count}"
    class Meta:
        ordering = ['-date_recorded', 'shot_type']

class MatchResult(models.Model):
    class MatchStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        REJECTED = 'REJECTED', 'Rejected'

    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='won_matches') # Renamed related_name for clarity
    
    # --- ADD THIS NEW FIELD ---
    opponent = models.ForeignKey(
        'Player',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lost_matches',
        help_text="The player who was the opponent. Null if the opponent is not a registered player."
    )
    # --- END OF ADDITION ---

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_matches')
    sets_data = models.JSONField(null=True, blank=True, help_text="List of set scores, e.g. [{'p1': 11, 'p2': 9}, ...]")
    
    date = models.DateField(default=timezone.now)
    opponent_name = models.CharField(max_length=100, blank=True, null=True, help_text="Use this if the opponent is not a registered player.") # Help text updated
    player_score_str = models.CharField(max_length=50, help_text="Player's score, e.g., '3-1' or '11-9, 11-5, 11-7'")
    opponent_score_str = models.CharField(max_length=50, blank=True, null=True, help_text="Opponent's score if different from player's perspective")
    is_competitive = models.BooleanField(default=False, help_text="Was this an official league/tournament match?")
    match_notes = models.TextField(blank=True, null=True)
    session = models.ForeignKey('scheduling.Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='matches_played', help_text="Optional: Link to session if this match was part of it.")
    
    status = models.CharField(max_length=20, choices=MatchStatus.choices, default=MatchStatus.PENDING)
    submitted_by_name = models.CharField(max_length=100, blank=True, help_text="Name of the person who submitted the score from the app.")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_matches')
    confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        match_type = "Competitive" if self.is_competitive else "Practice"
        opponent_display = self.opponent.full_name if self.opponent else self.opponent_name
        return f"{match_type} Match for {self.player} vs {opponent_display} on {self.date}"

    class Meta:
        ordering = ['-date', 'player__last_name']



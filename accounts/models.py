# accounts/models.py
import io
import os
import uuid
from datetime import timedelta
from PIL import Image, ImageOps

from django.db import models
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from core.utils import process_profile_image

class Coach(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coach_profile', null=True, blank=True )
    name = models.CharField(max_length=100, unique=True) # Ensure this is not redundant if user.get_full_name() is primary
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    hourly_rate = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Coach's hourly rate for payment.")
    
    whatsapp_phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="WhatsApp enabled phone number in E.164 format (e.g., +14155238886)."
    )
    # whatsapp_opt_in removed as per requirements
    receive_weekly_schedule_email = models.BooleanField(
        default=True,
        verbose_name="Receive Weekly Schedule Email",
        help_text="If checked, this coach will receive the weekly schedule summary email every Sunday."
    )

    profile_photo = models.ImageField(
        upload_to='coach_photos/',
        null=True,
        blank=True,
        verbose_name="Profile Photo"
    )
    experience_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Coaching Experience",
        help_text="Brief notes on coaching experience, specializations, etc."
    )

    class QualificationLevel(models.TextChoices):
        NONE = 'NONE', 'None / Not Applicable'
        LEVEL_1 = 'L1', 'Level 1'
        LEVEL_2 = 'L2', 'Level 2'
        LEVEL_3 = 'L3', 'Level 3'
        OTHER = 'OTH', 'Other'

    qualification_wsf_level = models.CharField(
        max_length=5,
        choices=QualificationLevel.choices,
        default=QualificationLevel.NONE,
        blank=True,
        verbose_name="WSF Qualification Level",
        help_text="World Squash Federation coaching qualification level."
    )
    qualification_ssa_level = models.CharField(
        max_length=5,
        choices=QualificationLevel.choices,
        default=QualificationLevel.NONE,
        blank=True,
        verbose_name="SSA Qualification Level",
        help_text="Squash South Africa coaching qualification level."
    )

    # --- Personal Details ---
    physical_address = models.TextField(blank=True, verbose_name="Physical Address")
    id_number = models.CharField(max_length=20, blank=True, verbose_name="ID Number / DOB")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Date of Birth")
    # Note: 'phone' already exists in the model.

    # --- Logistics (Car) ---
    car_registration_numbers = models.CharField(max_length=255, blank=True, help_text="If multiple, separate with commas.", verbose_name="Car Registration Number(s)")
    car_make_model = models.CharField(max_length=100, blank=True, verbose_name="Car Make & Model", help_text="e.g. Kia Picanto")
    car_color = models.CharField(max_length=50, blank=True, verbose_name="Car Color")

    # --- Medical Information (SENSITIVE) ---
    medical_aid_name = models.CharField(max_length=100, blank=True, verbose_name="Medical Aid Name")
    medical_aid_number = models.CharField(max_length=100, blank=True, verbose_name="Medical Aid Number")
    medical_conditions = models.TextField(blank=True, verbose_name="Medical Conditions", help_text="Any conditions we should be aware of (optional).")
    emergency_contact_name = models.CharField(max_length=100, blank=True, verbose_name="Emergency Contact Person & Relationship")
    emergency_contact_number = models.CharField(max_length=20, blank=True, verbose_name="Emergency Contact Number")
    
    class BloodType(models.TextChoices):
        A_POS = 'A+', 'A+'
        A_NEG = 'A-', 'A-'
        B_POS = 'B+', 'B+'
        B_NEG = 'B-', 'B-'
        O_POS = 'O+', 'O+'
        O_NEG = 'O-', 'O-'
        AB_POS = 'AB+', 'AB+'
        AB_NEG = 'AB-', 'AB-'
        UNKNOWN = 'UNK', 'Unknown'

    blood_type = models.CharField(max_length=5, choices=BloodType.choices, default=BloodType.UNKNOWN, blank=True, verbose_name="Blood Type")

    # --- Clothing / Kit ---
    class ShirtPreference(models.TextChoices):
        GOLF = 'GOLF', 'Golf Shirt'
        TSHIRT = 'TEE', 'T-Shirt'
        NONE = 'NONE', 'No Preference'
    
    class ShirtSize(models.TextChoices):
        L_XS = 'L_XS', 'Ladies XS'
        L_S = 'L_S', 'Ladies S'
        L_M = 'L_M', 'Ladies M'
        L_L = 'L_L', 'Ladies L'
        L_XL = 'L_XL', 'Ladies XL'
        M_S = 'M_S', 'Mens S'
        M_M = 'M_M', 'Mens M'
        M_L = 'M_L', 'Mens L'
        M_XL = 'M_XL', 'Mens XL'
        M_XXL = 'M_XXL', 'Mens XXL'

    shirt_preference = models.CharField(max_length=10, choices=ShirtPreference.choices, default=ShirtPreference.NONE, blank=True, verbose_name="T-Shirt Preference")
    shirt_size = models.CharField(max_length=10, choices=ShirtSize.choices, blank=True, verbose_name="T-Shirt Size")

    # --- Professional / Bio ---
    occupation = models.CharField(max_length=255, blank=True, verbose_name="Occupation", help_text="What kind of work do you do and in what area?")
    academic_credentials = models.TextField(blank=True, verbose_name="Academic & Professional Credentials")
    currently_studying = models.CharField(max_length=255, blank=True, verbose_name="Current Studies", help_text="If student, what are you studying?")
    highest_ranking = models.CharField(max_length=255, blank=True, verbose_name="Highest Squash Ranking", help_text="World, Provincial, or Club ranking")
    league_participation = models.CharField(max_length=255, blank=True, verbose_name="League Participation", help_text="e.g. Men's League at [Club Name]")

    # --- Coaching Preferences ---
    accepts_private_coaching = models.BooleanField(default=False, verbose_name="Available for One-on-One Coaching?")
    private_coaching_preferences = models.TextField(blank=True, verbose_name="Private Coaching Preferences", help_text="Preferred age group or skill level.")
    private_coaching_area = models.TextField(blank=True, verbose_name="Private Coaching Area", help_text="Preferred area or club.")


    def __str__(self):
        if self.user and (self.user.get_full_name() or self.user.username):
            return self.user.get_full_name() or self.user.username
        return self.name

    def save(self, *args, **kwargs):
        original_filename = None
        process_image = False

        if self.pk:
            try:
                old_instance = Coach.objects.get(pk=self.pk)
                if self.profile_photo and old_instance.profile_photo != self.profile_photo:
                    process_image = True
                    if hasattr(self.profile_photo, 'name') and self.profile_photo.name:
                        original_filename = self.profile_photo.name
                elif not self.profile_photo and old_instance.profile_photo:
                    pass
            except Coach.DoesNotExist:
                if self.profile_photo:
                    process_image = True
                    if hasattr(self.profile_photo, 'name') and self.profile_photo.name:
                        original_filename = self.profile_photo.name
        elif self.profile_photo:
            process_image = True
            if hasattr(self.profile_photo, 'name') and self.profile_photo.name:
                original_filename = self.profile_photo.name

        super().save(*args, **kwargs)

        if process_image and self.profile_photo and hasattr(self.profile_photo, 'path') and self.profile_photo.path:
            try:
                filename_to_save, resized_image = process_profile_image(self.profile_photo, original_filename)

                current_photo_name = self.profile_photo.name
                self.profile_photo.save(filename_to_save, resized_image, save=False)

                if current_photo_name != self.profile_photo.name or kwargs.get('force_insert', False):
                    super().save(update_fields=['profile_photo'])
            except FileNotFoundError:
                print(f"File not found for coach photo {self.name}: {getattr(self.profile_photo, 'path', 'No path')}")
            except Exception as e:
                print(f"Error processing coach photo for {self.name}: {e}")

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Coaches"


def default_expires_at():
    return timezone.now() + timedelta(days=7)

class CoachInvitation(models.Model):
    email = models.EmailField(unique=True)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expires_at)
    is_accepted = models.BooleanField(default=False)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sent_invitations')

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Invitation for {self.email}"
# Create your models here.

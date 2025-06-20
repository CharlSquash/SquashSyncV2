# accounts/models.py
import io
import os
from PIL import Image, ImageOps

from django.db import models
from django.conf import settings
from django.core.files.base import ContentFile

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
    whatsapp_opt_in = models.BooleanField(
        default=False,
        help_text="Has the coach opted-in to receive WhatsApp notifications?"
    )
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
                filename_to_save = os.path.basename(original_filename if original_filename else self.profile_photo.name)
                img = Image.open(self.profile_photo.path)
                img = ImageOps.exif_transpose(img)

                max_size = (300, 300)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)

                img_format = img.format if img.format else 'JPEG'
                buffer = io.BytesIO()
                save_kwargs = {'format': img_format, 'optimize': True}

                if img.mode in ("RGBA", "P") and img_format.upper() != 'PNG':
                    img = img.convert("RGB")
                    img_format = 'JPEG'
                    filename_to_save = os.path.splitext(filename_to_save)[0] + '.jpg'
                    save_kwargs['format'] = 'JPEG'

                if img_format.upper() == 'JPEG':
                    save_kwargs['quality'] = 85

                img.save(buffer, **save_kwargs)
                resized_image = ContentFile(buffer.getvalue())

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

# Create your models here.

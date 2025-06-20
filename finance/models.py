# finance/models.py
import os
from django.db import models
from django.conf import settings

# --- MODEL: CoachSessionCompletion ---
class CoachSessionCompletion(models.Model):
    # IMPORTANT: Updated FKs
    coach = models.ForeignKey('accounts.Coach', on_delete=models.CASCADE, related_name='session_completions')
    session = models.ForeignKey('scheduling.Session', on_delete=models.CASCADE, related_name='coach_completions')
    
    assessments_submitted = models.BooleanField(default=False, help_text="Coach has submitted all required player assessments.")
    confirmed_for_payment = models.BooleanField(default=False, help_text="Admin has verified and confirmed for payment.")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('coach', 'session')
        ordering = ['session__session_date', 'session__session_start_time', 'coach__name']
        verbose_name = "Coach Session Completion"
        verbose_name_plural = "Coach Session Completions"

    def __str__(self):
        status = "Payment Confirmed" if self.confirmed_for_payment else "Duties Complete"
        return f"{self.coach.name} - {status} for session on {self.session.session_date}"

# --- MODEL: Payslip ---
class Payslip(models.Model):
    coach = models.ForeignKey('accounts.Coach', on_delete=models.PROTECT, related_name='payslips')
    month = models.PositiveIntegerField()
    year = models.PositiveIntegerField()
    file = models.FileField(upload_to='payslips/%Y/%m/')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='payslips_initiated_by'
    )
    class Meta:
        unique_together = ('coach', 'month', 'year')
        ordering = ['-year', '-month', 'coach__name']

    def __str__(self):
        return f"Payslip for {self.coach} - {self.month:02}/{self.year}"

    @property
    def filename(self):
        if self.file:
            return os.path.basename(self.file.name)
        return None
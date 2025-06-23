# finance/forms.py
from django import forms
from django.utils import timezone
import calendar

class PayslipGenerationForm(forms.Form):
    month = forms.ChoiceField(choices=[(i, calendar.month_name[i]) for i in range(1, 13)], initial=timezone.now().month)
    year = forms.ChoiceField(choices=[(y, y) for y in range(timezone.now().year - 2, timezone.now().year + 2)], initial=timezone.now().year)
    force_regeneration = forms.BooleanField(required=False, label="Force Regeneration", help_text="If checked, existing payslips for the selected period will be deleted and recreated.")
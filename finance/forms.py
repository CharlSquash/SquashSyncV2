# finance/forms.py
from django import forms
from django.utils import timezone
import calendar

class PayslipGenerationForm(forms.Form):
    # Remove initial= and dynamic choices from here
    month = forms.ChoiceField(choices=[(i, calendar.month_name[i]) for i in range(1, 13)])
    year = forms.ChoiceField() # We will set choices dynamically
    force_regeneration = forms.BooleanField(required=False, label="Force Regeneration", help_text="If checked, existing payslips for the selected period will be deleted and recreated.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        now = timezone.now()
        
        # Dynamically set the year choices
        year_choices = [(y, y) for y in range(now.year - 2, now.year + 2)]
        self.fields['year'].choices = year_choices
        
        # Set initial values *only if* no data was passed to the form
        if not self.data: # self.data is None on GET, a dict on POST
            self.initial['month'] = now.month
            self.initial['year'] = now.year
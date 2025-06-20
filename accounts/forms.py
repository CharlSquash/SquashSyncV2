# accounts/forms.py
from django import forms
from django.utils import timezone
from datetime import date

class MonthYearFilterForm(forms.Form):
    # Dynamically create choices to stay up-to-date
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        year_choices = [(year, str(year)) for year in range(current_year - 2, current_year + 2)]
        month_choices = [(i, date(2000, i, 1).strftime('%B')) for i in range(1, 13)]

        self.fields['year'] = forms.ChoiceField(choices=year_choices, initial=current_year)
        self.fields['month'] = forms.ChoiceField(choices=month_choices, initial=timezone.now().month)
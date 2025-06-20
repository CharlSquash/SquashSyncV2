# scheduling/forms.py
from django import forms

import calendar

# Import models from their correct new apps
from .models import Session, CoachAvailability, Venue
from accounts.models import Coach
from players.models import SchoolGroup, Player
from django.utils import timezone
from datetime import timedelta

class MonthYearFilterForm(forms.Form):
    """A form for selecting a month and year."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        now = timezone.now()
        year_choices = [(y, y) for y in range(now.year - 1, now.year + 2)]
        month_choices = [(m, calendar.month_name[m]) for m in range(1, 13)]
        self.fields['year'] = forms.ChoiceField(choices=year_choices, initial=now.year)
        self.fields['month'] = forms.ChoiceField(choices=month_choices, initial=now.month)

class SessionForm(forms.ModelForm):
    class Meta: 
        model = Session
        fields = [
            'school_group', 'session_date', 'session_start_time',
            'planned_duration_minutes', 'venue', 'coaches_attending',
            'notes', 'is_cancelled'
        ]
        widgets = {
            'session_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'session_start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'school_group': forms.Select(attrs={'class': 'form-select'}),
            'venue': forms.Select(attrs={'class': 'form-select'}),
            'coaches_attending': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
            'planned_duration_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_cancelled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class CoachAvailabilityForm(forms.ModelForm):
    class Meta:
        model = CoachAvailability
        fields = ['is_available', 'notes']
        widgets = {
            'is_available': forms.RadioSelect(choices=[
                (True, 'Yes, I am available'),
                (False, 'No, I am unavailable')
            ]),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional: Reason for unavailability, etc.'}),
        }
        labels = {
            'is_available': 'Are you available for this session?'
        }

class SessionFilterForm(forms.Form):
    school_group = forms.ModelChoiceField(queryset=SchoolGroup.objects.all(), required=False, label="Group")
    coach = forms.ModelChoiceField(queryset=Coach.objects.filter(is_active=True), required=False, label="Coach")
    venue = forms.ModelChoiceField(queryset=Venue.objects.filter(is_active=True), required=False, label="Venue")

class GenerateSessionsForm(forms.Form):
    start_date = forms.DateField(
        label="Start Date",
        initial=timezone.now().date,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    end_date = forms.DateField(
        label="End Date",
        initial=lambda: timezone.now().date() + timedelta(days=30),
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    overwrite_clashing_manual_sessions = forms.BooleanField(
        label="Overwrite clashing manual sessions?",
        required=False,
        initial=False,
        help_text="If checked, any manually created session that clashes will be linked to the generating rule."
    )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")
        if start and end and end < start:
            raise forms.ValidationError("End date cannot be before start date.")
        return cleaned_data

class AttendanceForm(forms.Form):
    attendees = forms.ModelMultipleChoiceField(
        queryset=Player.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    def __init__(self, *args, **kwargs):
        school_group = kwargs.pop('school_group', None)
        super().__init__(*args, **kwargs)
        if school_group:
            self.fields['attendees'].queryset = Player.objects.filter(
                school_groups=school_group, is_active=True
            ).order_by('last_name', 'first_name')
        else:
            self.fields['attendees'].queryset = Player.objects.filter(is_active=True).order_by('last_name', 'first_name')

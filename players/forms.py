# players/forms.py
from django import forms
from .models import SchoolGroup, CourtSprintRecord, VolleyRecord, BackwallDriveRecord
from django.utils import timezone

class SchoolGroupForm(forms.ModelForm):
    class Meta:
        model = SchoolGroup
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class AttendancePeriodFilterForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)

class PlayerAttendanceFilterForm(forms.Form):
    school_group = forms.ModelChoiceField(
        queryset=SchoolGroup.objects.none(),
        required=False,
        label="Filter by Group",
        empty_label="All Groups",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)

    def __init__(self, *args, **kwargs):
        player = kwargs.pop('player', None)
        super().__init__(*args, **kwargs)
        if player:
            self.fields['school_group'].queryset = player.school_groups.all()

# --- NEW METRIC FORMS ---

class CourtSprintRecordForm(forms.ModelForm):
    date_recorded = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=timezone.now)
    class Meta:
        model = CourtSprintRecord
        fields = ['date_recorded', 'duration_choice', 'score']
        labels = { 'score': 'Number of Lengths' }


class VolleyRecordForm(forms.ModelForm):
    date_recorded = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=timezone.now)
    class Meta:
        model = VolleyRecord
        fields = ['date_recorded', 'shot_type', 'consecutive_count']
        labels = { 'consecutive_count': 'Consecutive Volleys' }

class BackwallDriveRecordForm(forms.ModelForm):
    date_recorded = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=timezone.now)
    class Meta:
        model = BackwallDriveRecord
        fields = ['date_recorded', 'shot_type', 'consecutive_count']
        labels = { 'consecutive_count': 'Consecutive Drives' }
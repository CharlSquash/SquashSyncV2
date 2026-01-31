from django import forms
from .models import SchoolGroup, Player, CourtSprintRecord, VolleyRecord, BackwallDriveRecord, MatchResult
from django.forms import DateInput

class SchoolGroupForm(forms.ModelForm):
    class Meta:
        model = SchoolGroup
        fields = ['name', 'description', 'year', 'attendance_form_url', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class AttendancePeriodFilterForm(forms.Form):
    start_date = forms.DateField(
        widget=DateInput(attrs={'type': 'date'}),
        required=False
    )
    end_date = forms.DateField(
        widget=DateInput(attrs={'type': 'date'}),
        required=False
    )

class PlayerAttendanceFilterForm(AttendancePeriodFilterForm):
    # Inherits start/end date
    def __init__(self, *args, **kwargs):
        self.player = kwargs.pop('player', None)
        super().__init__(*args, **kwargs)

class CourtSprintRecordForm(forms.ModelForm):
    class Meta:
        model = CourtSprintRecord
        fields = ['date_recorded', 'duration_choice', 'score', 'session']
        widgets = {
            'date_recorded': DateInput(attrs={'type': 'date'}),
        }

class VolleyRecordForm(forms.ModelForm):
    class Meta:
        model = VolleyRecord
        fields = ['date_recorded', 'shot_type', 'consecutive_count', 'session']
        widgets = {
            'date_recorded': DateInput(attrs={'type': 'date'}),
        }

class BackwallDriveRecordForm(forms.ModelForm):
    class Meta:
        model = BackwallDriveRecord
        fields = ['date_recorded', 'shot_type', 'consecutive_count', 'session']
        widgets = {
            'date_recorded': DateInput(attrs={'type': 'date'}),
        }

class MatchResultForm(forms.ModelForm):
    # Extra fields for the logic in views.py
    winner = forms.ChoiceField(
        choices=[('me', 'Me'), ('opponent', 'Opponent')],
        widget=forms.RadioSelect,
        initial='me'
    )
    
    # We'll use a hidden field for the JSON sets data, populated by JS
    sets_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = MatchResult
        fields = [
            'date', 
            'opponent', 
            'opponent_name', 
            'is_competitive', 
            'match_notes',
            # 'sets_data', # We handle this manually via the extra field
            # 'player_score_str', # Calculated
            # 'opponent_score_str', # Calculated
        ]
        widgets = {
            'date': DateInput(attrs={'type': 'date'}),
            'match_notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.player = kwargs.pop('player', None)
        super().__init__(*args, **kwargs)
        
        # Filter opponents to exclude self
        if self.player:
            self.fields['opponent'].queryset = Player.objects.filter(is_active=True).exclude(id=self.player.id).order_by('first_name')



class QuickMatchResultForm(forms.ModelForm):
    """
    Simplified match result form for quick entry during assessment sessions.
    """
    winner = forms.ChoiceField(
        choices=[('me', 'Me'), ('opponent', 'Opponent')],
        widget=forms.RadioSelect,
        initial='me'
    )

    class Meta:
        model = MatchResult
        fields = ['opponent', 'opponent_name', 'match_notes'] # Reduced fields
        widgets = {
            'match_notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional notes...'}),
        }

    def __init__(self, *args, **kwargs):
        self.player = kwargs.pop('player', None)
        attendees_queryset = kwargs.pop('attendees_queryset', None)
        super().__init__(*args, **kwargs)

        if attendees_queryset is not None:
            self.fields['opponent'].queryset = attendees_queryset
        elif self.player:
            self.fields['opponent'].queryset = Player.objects.filter(is_active=True).exclude(id=self.player.id).order_by('first_name')
        
        self.fields['opponent'].required = False
        self.fields['opponent_name'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        opponent = cleaned_data.get('opponent')
        opponent_name = cleaned_data.get('opponent_name')
        
        if not opponent and not opponent_name:
            raise forms.ValidationError("You must specify either an existing opponent or an opponent name.")
        return cleaned_data

class PlayerSearchForm(forms.Form):
    name_search = forms.CharField(
        label="Search by Name",
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Enter first or last name', 'class': 'form-control'})
    )

class PlayerEmailForm(forms.Form):
    email = forms.EmailField(
        label="Notification Email",
        widget=forms.EmailInput(attrs={'placeholder': 'parent@example.com', 'class': 'form-control'})
    )

# players/forms.py
from django import forms
from .models import SchoolGroup, CourtSprintRecord, VolleyRecord, BackwallDriveRecord, MatchResult, Player
from django.db.models import Prefetch
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

class PlayerGroupLabelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        group_names = ", ".join([g.name for g in obj.active_groups])
        if group_names:
            return f"{obj.full_name} ({group_names})"
        return obj.full_name

class MatchResultForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=timezone.now)
    opponent = PlayerGroupLabelChoiceField(

        queryset=Player.objects.none(),
        required=False,
        label="Select Opponent (Database)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = MatchResult
        fields = ['date', 'opponent', 'opponent_name', 'player_score_str', 'is_competitive', 'match_notes']
        labels = {
            'opponent_name': "Opponent's Name (if not in list)",
            'player_score_str': "Score",
            'is_competitive': 'Competitive Match',
            'match_notes': 'Notes'
        }

    def __init__(self, *args, **kwargs):
        player = kwargs.pop('player', None)
        super().__init__(*args, **kwargs)
        
        # Default queryset if no player context (though view should provide it)
        self.fields['opponent'].queryset = Player.objects.filter(is_active=True).prefetch_related(
            Prefetch('school_groups', queryset=SchoolGroup.objects.filter(is_active=True), to_attr='_active_groups_cache')
        )

        if player:
            self.fields['opponent'].queryset = Player.objects.filter(is_active=True).exclude(id=player.id).prefetch_related(
                Prefetch('school_groups', queryset=SchoolGroup.objects.filter(is_active=True), to_attr='_active_groups_cache')
            )

    def clean(self):
        cleaned_data = super().clean()
        opponent = cleaned_data.get('opponent')
        opponent_name = cleaned_data.get('opponent_name')

        if not opponent and not opponent_name:
            raise forms.ValidationError("Please select an opponent from the list OR enter a name manually.")
        return cleaned_data

class QuickMatchResultForm(forms.ModelForm):
    player_score_str = forms.CharField(label="Score", widget=forms.TextInput(attrs={'placeholder': '', 'class': 'form-control'}))
    opponent_score_str = forms.CharField(label="Score", widget=forms.TextInput(attrs={'placeholder': '', 'class': 'form-control'}))

    class Meta:
        model = MatchResult
        fields = ['player', 'player_score_str', 'opponent', 'opponent_score_str']
        labels = {
            'player': 'Winner',
            'opponent': 'Loser',
        }

    def __init__(self, *args, **kwargs):
        attendees = kwargs.pop('attendees_queryset', None)
        super().__init__(*args, **kwargs)
        
        if attendees is not None:
            self.fields['player'].queryset = attendees
            self.fields['opponent'].queryset = attendees
        
        self.fields['player'].widget.attrs.update({'class': 'form-select'})
        self.fields['opponent'].widget.attrs.update({'class': 'form-select'})

    def clean(self):
        cleaned_data = super().clean()
        winner = cleaned_data.get("player")
        loser = cleaned_data.get("opponent")

        if winner and loser and winner == loser:
            raise forms.ValidationError("The winner and loser cannot be the same player.")

        return cleaned_data


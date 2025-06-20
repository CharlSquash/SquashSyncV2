# assessments/forms.py
from django import forms
from .models import SessionAssessment, GroupAssessment

class SessionAssessmentForm(forms.ModelForm):
    class Meta:
        model = SessionAssessment
        fields = [
            'effort_rating', 'focus_rating', 'resilience_rating',
            'composure_rating', 'decision_making_rating', 'coach_notes'
        ]
        widgets = {
            'coach_notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Enter notes...'}),
        }

# We will also add the GroupAssessmentForm here for the next step
class GroupAssessmentForm(forms.ModelForm):
    class Meta:
        model = GroupAssessment
        fields = ['general_notes', 'is_hidden_from_other_coaches']
        labels = {
            'general_notes': "Overall Notes (Group energy, venue issues, parent interactions, etc.)",
            'is_hidden_from_other_coaches': "Hide my notes from other coaches"
        }
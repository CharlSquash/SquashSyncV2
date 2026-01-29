from django import forms
from .models import SessionAssessment, GroupAssessment, AssessmentComment

class SessionAssessmentForm(forms.ModelForm):
    """
    Form for a coach to submit their assessment of a player for a specific session.
    """
    class Meta:
        model = SessionAssessment
        fields = [
            'effort_rating',
            'focus_rating',
            'resilience_rating',
            'composure_rating',
            'decision_making_rating',
            'coach_notes'
        ]
        widgets = {
            # Using radio selects for a better user experience than a simple number input.
            'effort_rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'focus_rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'resilience_rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'composure_rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'decision_making_rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'coach_notes': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'effort_rating': 'Effort / Work Rate',
            'focus_rating': 'Focus / Engagement',
            'resilience_rating': 'Resilience (handling pressure/setbacks)',
            'composure_rating': 'Composure (emotional control)',
            'decision_making_rating': 'Decision Making (shot selection, positioning)',
            'coach_notes': 'General Notes / Comments',
        }
        help_texts = {
            'coach_notes': 'Provide specific feedback or observations about the player\'s performance in this session.'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add styling and structure to the form fields for better rendering
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.RadioSelect):
                # This makes the radio buttons appear inline
                field.widget.attrs['class'] = 'd-flex justify-content-around'

# We will also add the GroupAssessmentForm here for the next step
class GroupAssessmentForm(forms.ModelForm):
    """
    A simple form for a coach to provide general notes about a session/group.
    """
    class Meta:
        model = GroupAssessment
        fields = ['general_notes']
        widgets = {
            'general_notes': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': "Log specific operational or venue issues (e.g. Bus late, Lights flickering). Leave blank if none."
            }),
        }
        labels = {
            'general_notes': 'Session Logistics & Incident Report',
        }
        help_texts = {
            'general_notes': 'Log specific operational issues. Leave blank if the session ran smoothly.'
        }

class AssessmentCommentForm(forms.ModelForm):
    """
    Form for adding a comment to an assessment.
    """
    class Meta:
        model = AssessmentComment
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Add a comment...'
            }),
        }
        labels = {
            'comment': ''
        }

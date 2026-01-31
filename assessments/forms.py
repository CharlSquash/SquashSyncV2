from django import forms
from .models import SessionAssessment, GroupAssessment, AssessmentComment

class SessionAssessmentForm(forms.ModelForm):
    """
    Form for a coach to submit their assessment of a player for a specific session.
    """
    class Meta:
        model = SessionAssessment
        fields = [
            'effort_enthusiasm_rating',
            'skill_technique_rating',
            'sportsmanship_attitude_rating',
            'tactical_mental_rating',
            'fitness_perseverance_rating',
            'coach_notes'
        ]
        widgets = {
            # Using radio selects for a better user experience than a simple number input.
            'effort_enthusiasm_rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'skill_technique_rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'sportsmanship_attitude_rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'tactical_mental_rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'fitness_perseverance_rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'coach_notes': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'effort_enthusiasm_rating': 'Effort / Enthusiasm',
            'skill_technique_rating': 'Skill / Technique',
            'sportsmanship_attitude_rating': 'Sportsmanship / Attitude',
            'tactical_mental_rating': 'Tactical / Mental',
            'fitness_perseverance_rating': 'Fitness / Perseverance',
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
                'placeholder': "General feedback about the group, session dynamics, or any operational notes."
            }),
        }
        labels = {
            'general_notes': 'Group Feedback & Session Notes',
        }
        help_texts = {
            'general_notes': 'Provide feedback on the group as a whole and any other relevant session details.'
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

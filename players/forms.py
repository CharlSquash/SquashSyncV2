# players/forms.py
from django import forms
from .models import SchoolGroup

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
        empty_label="All Groups",  # THIS IS THE FIX
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)

    def __init__(self, *args, **kwargs):
        player = kwargs.pop('player', None)
        super().__init__(*args, **kwargs)
        if player:
            self.fields['school_group'].queryset = player.school_groups.all()
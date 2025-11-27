from django import forms
from django.db.models import Q
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from todo.models import TaskList
from todo.forms import AddTaskListForm as OriginalAddListForm, AddEditTaskForm

User = get_user_model()

class AddListWithMembersForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(groups__name='Coaches'), # Filter to Coaches initially
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select coaches to add to this list's group."
    )

    class Meta:
        model = TaskList
        fields = ['name']


class ManageMembersForm(forms.Form):
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(groups__name='Coaches'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select coaches to be in this group."
    )

    def __init__(self, *args, **kwargs):
        group = kwargs.pop('group', None)
        super().__init__(*args, **kwargs)
        if group:
            self.fields['members'].initial = group.user_set.all()


class CustomModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.first_name} {obj.last_name} ({obj.username})"


class CustomAddEditTaskForm(AddEditTaskForm):
    assigned_to = CustomModelChoiceField(
        queryset=User.objects.filter(Q(groups__name='Coaches') | Q(is_superuser=True), is_active=True).distinct(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['assigned_to'].queryset = User.objects.filter(
            Q(groups__name='Coaches') | Q(is_superuser=True), 
            is_active=True
        ).distinct()

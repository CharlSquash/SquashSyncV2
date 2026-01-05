from django import forms
from django.db.models import Q
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from todo.models import TaskList
from todo.forms import AddTaskListForm as OriginalAddListForm, AddEditTaskForm

User = get_user_model()




class AddProjectForm(forms.ModelForm):
    class Meta:
        model = TaskList
        fields = ['name']
        labels = {
            'name': 'Project Name'
        }


class CustomModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.first_name} {obj.last_name} ({obj.username})"


class CustomAddEditTaskForm(AddEditTaskForm):
    assigned_to = CustomModelChoiceField(
        queryset=User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True)),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        
        self.fields['assigned_to'].queryset = User.objects.filter(
            is_active=True
        ).filter(
            Q(is_staff=True) | Q(is_superuser=True)
        )

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
    assignees = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True)),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Assigned To"
    )

    def __init__(self, user, *args, **kwargs):
        # Initialize parent first
        super().__init__(user, *args, **kwargs)
        
        # Remove original assigned_to field if it exists to avoid confusion/conflict
        if 'assigned_to' in self.fields:
            del self.fields['assigned_to']

        task_list = self.initial.get('task_list')
        if not task_list and self.instance and hasattr(self.instance, 'task_list'):
            task_list = self.instance.task_list

        # If we are editing an existing task (instance is present and has a pk)
        if self.instance and self.instance.pk and self.instance.assigned_to:
            # Set the initial value for assignees to the current assignee
            self.initial['assignees'] = [self.instance.assigned_to]

        filters = Q(is_staff=True) | Q(is_superuser=True)
        if task_list and task_list.group:
            filters |= Q(groups__in=[task_list.group])

        self.fields['assignees'].queryset = User.objects.filter(
            is_active=True
        ).filter(filters).distinct()

        # Modernize widgets
        self.fields['note'].widget.attrs['rows'] = 3
        
        for field_name in ['title', 'due_date', 'note', 'priority']:
            if field_name in self.fields:
                existing_class = self.fields[field_name].widget.attrs.get('class', '')
                if 'form-control' not in existing_class:
                    self.fields[field_name].widget.attrs['class'] = (existing_class + ' form-control').strip()

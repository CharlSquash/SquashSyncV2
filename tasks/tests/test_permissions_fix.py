from django.test import TestCase
from django.contrib.auth.models import User, Group
from todo.models import TaskList
from tasks.forms import CustomAddEditTaskForm

class CustomAddEditTaskFormPermissionsTest(TestCase):
    def setUp(self):
        # Create a user who is NOT a superuser and NOT in 'Coaches'
        self.staff_user = User.objects.create_user(username='staffmember', password='password', is_staff=True)
        
        # Create a 'Coaches' group and a coach user
        self.coaches_group = Group.objects.create(name='Coaches')
        self.coach_user = User.objects.create_user(username='coach', password='password', is_staff=True)
        self.coach_user.groups.add(self.coaches_group)
        
        # Create a TaskList and its associated group
        self.list_group = Group.objects.create(name='Project Team')
        self.task_list = TaskList.objects.create(name='Project Alpha', group=self.list_group)
        
        # Add the staff user to the list's group
        self.staff_user.groups.add(self.list_group)

    def test_assigned_to_queryset_includes_list_members(self):
        # Initialize the form with the task_list in initial data
        form = CustomAddEditTaskForm(user=self.coach_user, initial={'task_list': self.task_list})
        
        queryset = form.fields['assigned_to'].queryset
        
        # The coach should be in the queryset (because they are in 'Coaches')
        self.assertIn(self.coach_user, queryset)
        
        # The staff user SHOULD be in the queryset (because they are in the list's group)
        # This assertion is expected to FAIL before the fix
        self.assertIn(self.staff_user, queryset)

    def test_assigned_to_queryset_excludes_unrelated_users(self):
        # Create a random user
        random_user = User.objects.create_user(username='random', password='password')
        
        form = CustomAddEditTaskForm(user=self.coach_user, initial={'task_list': self.task_list})
        queryset = form.fields['assigned_to'].queryset
        
        self.assertNotIn(random_user, queryset)

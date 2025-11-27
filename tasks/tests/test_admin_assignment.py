from django.test import TestCase
from django.contrib.auth import get_user_model
from tasks.forms import CustomAddEditTaskForm

User = get_user_model()

class AdminAssignmentTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(username='admin', password='password', email='admin@example.com')
        self.coach = User.objects.create_user(username='coach', password='password')
        from django.contrib.auth.models import Group
        self.group = Group.objects.create(name='Coaches')
        self.coach.groups.add(self.group)
        
    def test_admin_in_assignment_list(self):
        from todo.models import TaskList
        task_list = TaskList.objects.create(name="Test List", slug="test-list", group=self.coach.groups.first())
        
        form = CustomAddEditTaskForm(user=self.superuser, initial={'task_list': task_list})
        queryset = form.fields['assigned_to'].queryset
        
        # Verify admin is in the queryset
        self.assertIn(self.superuser, queryset)
        self.assertIn(self.coach, queryset)

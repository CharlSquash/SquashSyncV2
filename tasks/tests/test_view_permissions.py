from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from todo.models import TaskList, Task
from django.urls import reverse
from django.utils import timezone

class TaskPermissionVerificationTest(TestCase):
    def setUp(self):
        # Create an admin/owner user and group
        self.owner_user = User.objects.create_user(username='owner', password='password', is_superuser=True)
        self.admin_group = Group.objects.create(name='Admins')
        self.owner_user.groups.add(self.admin_group)

        # Create a TaskList owned by Admins
        self.task_list = TaskList.objects.create(name='Admin Project', group=self.admin_group, slug='admin-project')

        # Create a staff user who is NOT in Admins
        self.staff_user = User.objects.create_user(username='staff', password='password', is_staff=True)

        # Create a task assigned to the staff user
        self.task = Task.objects.create(
            title='Staff Task',
            task_list=self.task_list,
            created_by=self.owner_user,
            assigned_to=self.staff_user,
            due_date=timezone.now()
        )

        self.client = Client()

    def test_staff_user_can_view_assigned_task_detail(self):
        self.client.force_login(self.staff_user)
        url = reverse('todo:task_detail', kwargs={'task_id': self.task.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_staff_user_can_toggle_done(self):
        self.client.force_login(self.staff_user)
        # Using the custom url name for toggle done or the one we intercepted
        url = reverse('custom_task_toggle_done_v2', kwargs={'task_id': self.task.id})
        
        # Initial state: not completed
        self.assertFalse(self.task.completed)

        response = self.client.post(url, {'toggle_done': '1'}, follow=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Refresh task from db
        self.task.refresh_from_db()
        self.assertTrue(self.task.completed)

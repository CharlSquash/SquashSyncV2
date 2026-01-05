from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.urls import reverse
from todo.models import TaskList, Task

class TaskTogglePermissionTest(TestCase):
    def setUp(self):
        # Create a staff user who is not a superuser and not in the task list's group
        self.staff_user = User.objects.create_user(username='staff_user', password='password', is_staff=True)
        
        # Create another user for assignment/group membership
        self.other_user = User.objects.create_user(username='other_user', password='password')
        
        # Create a TaskList and a private group
        self.group = Group.objects.create(name='Private Group')
        self.task_list = TaskList.objects.create(name='Private List', group=self.group, slug='private-list')
        self.other_user.groups.add(self.group)
        
        # Create a task assigned to other_user
        self.task = Task.objects.create(
            title="Test Task",
            task_list=self.task_list,
            created_by=self.other_user,
            assigned_to=self.other_user
        )

    def test_staff_can_toggle_task_done(self):
        # Log in as the staff user
        self.client.login(username='staff_user', password='password')
        
        # Ensure task is initially not completed
        self.assertFalse(self.task.completed)
        
        # Attempt to POST to the task_toggle_done URL
        # We need to hit the CUSTOM view which has the name 'custom_task_toggle_done'
        url = reverse('custom_task_toggle_done', kwargs={'task_id': self.task.id})
        
        response = self.client.post(url)
        
        # Assert is redirect (302)
        self.assertEqual(response.status_code, 302)
        
        # Verify the task status is updated
        self.task.refresh_from_db()
        self.assertTrue(self.task.completed)

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from accounts.models import Coach
from todo.models import Task, TaskList

User = get_user_model()

class TodoIntegrationTest(TestCase):
    def setUp(self):
        # 1. Setup: Create User, Coach profile, and "Coaches" Group
        self.user = User.objects.create_user(
            username='coach_test',
            email='coach@example.com',
            password='password123',
            is_staff=True  # Ensure staff status for dashboard access
        )
        self.coach = Coach.objects.create(
            user=self.user,
            name='Test Coach',
            email='coach@example.com'
        )
        
        self.group, created = Group.objects.get_or_create(name='Coaches')
        self.user.groups.add(self.group)
        
        # Create a TaskList for the group (required by django-todo)
        self.task_list = TaskList.objects.create(
            name="General Duties",
            slug="general-duties",
            group=self.group
        )
        
        # Create 1 assigned Task
        self.task = Task.objects.create(
            title="Test Integration Task",
            task_list=self.task_list,
            assigned_to=self.user,
            created_by=self.user,
            priority=1
        )
        
        self.client = Client()

    def test_coach_todo_workflow(self):
        # 2. Dashboard Check
        login_success = self.client.login(username='coach_test', password='password123')
        self.assertTrue(login_success, "Failed to login as coach")
        
        response = self.client.get(reverse('homepage'))
        self.assertEqual(response.status_code, 200)
        
        # Assert pending_tasks_count is present and equals 1
        self.assertIn('pending_tasks_count', response.context)
        self.assertEqual(response.context['pending_tasks_count'], 1)
        
        # 3. View Access: GET todo:mine
        # Note: Assuming 'todo:mine' is the correct URL name based on standard django-todo or project config
        # If it fails, I will check urls.py
        try:
            url = reverse('todo:mine')
        except:
            # Fallback or fail if URL name is different
            url = '/todo/mine/' 
            
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, f"Failed to access {url}. Status: {response.status_code}")
        
        # 4. Interaction: Mark task as done
        # We need to post to the toggle completion URL. 
        # Usually django-todo uses 'todo:task_toggle_done' with task_id
        toggle_url = reverse('todo:task_toggle_done', kwargs={'task_id': self.task.id})
        
        # The view usually expects a POST, sometimes AJAX. 
        # Let's try a standard POST.
        response = self.client.post(toggle_url)
        
        # Depending on implementation, it might redirect or return JSON.
        # If it redirects, status code is 302. If JSON, 200.
        self.assertIn(response.status_code, [200, 302], "Failed to toggle task completion")
        
        # Refresh task from DB
        self.task.refresh_from_db()
        self.assertTrue(self.task.completed, "Task was not marked as completed")
        
        # 5. Re-Verification: GET homepage again
        response = self.client.get(reverse('homepage'))
        self.assertEqual(response.context['pending_tasks_count'], 0, "Pending task count did not update to 0")


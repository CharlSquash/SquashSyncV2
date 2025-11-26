from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from todo.models import TaskList

User = get_user_model()

class ListCreationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='password123',
            is_staff=True # Needed for some checks potentially
        )
        self.client = Client()
        self.client.login(username='testuser', password='password123')

    def test_creator_added_to_group(self):
        # 1. Create a new list via the custom view
        url = reverse('add_list_custom')
        data = {
            'name': 'My New List',
            'members': [] # No other members initially
        }
        response = self.client.post(url, data)
        
        # 2. Assert redirect to list detail (success)
        self.assertEqual(response.status_code, 302)
        
        # 3. Get the created list
        task_list = TaskList.objects.get(name='My New List')
        
        # 4. Assert the user is in the group
        self.assertTrue(task_list.group.user_set.filter(id=self.user.id).exists(), 
                        "Creator was not added to the list's group")
        
        # 5. Assert the user can access the list detail
        detail_url = reverse('todo:list_detail', kwargs={'list_id': task_list.id, 'list_slug': task_list.slug})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200, "Creator cannot access the list detail page")

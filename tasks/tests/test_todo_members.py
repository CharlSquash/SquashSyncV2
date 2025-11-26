from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from todo.models import TaskList

class TodoMemberTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password', is_staff=True)
        self.coach1 = User.objects.create_user(username='coach1', password='password')
        self.coach2 = User.objects.create_user(username='coach2', password='password')
        
        # Ensure 'Coaches' group exists and coaches are in it
        self.coaches_group, _ = Group.objects.get_or_create(name='Coaches')
        self.coach1.groups.add(self.coaches_group)
        self.coach2.groups.add(self.coaches_group)
        
        self.client.login(username='testuser', password='password')

    def test_add_list_with_members(self):
        url = reverse('add_list_custom')
        data = {
            'name': 'New Team List',
            'slug': 'new-team-list',
            'members': [self.coach1.id, self.coach2.id]
        }
        response = self.client.post(url, data)
        
        # Check redirection
        self.assertEqual(response.status_code, 302)
        
        # Check List created
        task_list = TaskList.objects.get(name='New Team List')
        self.assertIsNotNone(task_list)
        
        # Check Group created
        group = task_list.group
        self.assertEqual(group.name, 'New Team List Group')
        
        # Check members
        self.assertIn(self.coach1, group.user_set.all())
        self.assertIn(self.coach2, group.user_set.all())

    def test_manage_members(self):
        # Create initial list and group
        group = Group.objects.create(name='Existing Group')
        group.user_set.add(self.coach1)
        task_list = TaskList.objects.create(name='Existing List', slug='existing-list', group=group)
        
        url = reverse('manage_list_members', args=[task_list.id])
        
        # Remove coach1, add coach2
        data = {
            'members': [self.coach2.id]
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 302)
        
        # Refresh group
        group.refresh_from_db()
        self.assertNotIn(self.coach1, group.user_set.all())
        self.assertIn(self.coach2, group.user_set.all())

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from .models import PlanTemplate
from accounts.models import Coach
import json

User = get_user_model()

class PlanTemplateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='coachuser', password='password')
        self.coach = Coach.objects.create(user=self.user, name="Test Coach")
        self.client.login(username='coachuser', password='password')
        
        self.other_user = User.objects.create_user(username='othercoach', password='password')
        self.other_coach = Coach.objects.create(user=self.other_user, name="Other Coach")

    def test_save_template(self):
        data = {
            'name': 'My Template',
            'description': 'Test Description',
            'is_public': False,
            'court_count': 3,
            'plan_data': [{'court1': []}, {'court2': []}]
        }
        response = self.client.post('/live-session/api/templates/save/', data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlanTemplate.objects.count(), 1)
        template = PlanTemplate.objects.first()
        self.assertEqual(template.name, 'My Template')
        self.assertEqual(template.created_by, self.coach)

    def test_list_templates(self):
        # Create private template for self
        PlanTemplate.objects.create(name="My Private", created_by=self.coach, is_public=False, plan_data={})
        # Create public template by other
        PlanTemplate.objects.create(name="Other Public", created_by=self.other_coach, is_public=True, plan_data={})
        # Create private template by other
        PlanTemplate.objects.create(name="Other Private", created_by=self.other_coach, is_public=False, plan_data={})

        response = self.client.get('/live-session/api/templates/list/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(len(data['templates']), 2) # My Private + Other Public

    def test_delete_template(self):
        t = PlanTemplate.objects.create(name="To Delete", created_by=self.coach, is_public=False, plan_data={})
        
        response = self.client.post(f'/live-session/api/templates/delete/{t.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlanTemplate.objects.filter(id=t.id).count(), 0)

    def test_delete_others_template_denied(self):
        t = PlanTemplate.objects.create(name="Other's Template", created_by=self.other_coach, is_public=True, plan_data={})
        
        response = self.client.post(f'/live-session/api/templates/delete/{t.id}/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(PlanTemplate.objects.filter(id=t.id).count(), 1)

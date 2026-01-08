from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from live_session.views import experimental_planner
from scheduling.models import Session
from live_session.models import Drill
from players.models import Player
from accounts.models import Coach
from django.utils import timezone
from django.urls import reverse
import datetime
import json

class ExperimentalPlannerTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser('admin', 'admin@test.com', 'password')
        self.session = Session.objects.create(
            # session_type="M",
            school_group=None, # Optional
            session_date=timezone.now().date(),
            session_start_time=timezone.now().time(),
            planned_duration_minutes=60
        )
        self.drill = Drill.objects.create(name="Test Drill", duration_minutes=10, is_approved=True)
        self.player = Player.objects.create(first_name="John", last_name="Doe")

    def test_experimental_planner_context_types(self):
        request = self.factory.get(f'/live-session/planner-v2/{self.session.id}/')
        request.user = self.user
        
        response = experimental_planner(request, self.session.id)
        
        # Check that response is successful
        self.assertEqual(response.status_code, 200)
        
    def test_experimental_planner_with_client(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/live-session/planner-v2/{self.session.id}/')
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        
        # Verify the types of the context variables
        self.assertIsInstance(context['drills_json'], list)
        self.assertIsInstance(context['players_json'], list)
        self.assertIsInstance(context['csrf_token'], str)
        
        # Verify content
        self.assertEqual(len(context['drills_json']), 1)
        self.assertEqual(context['drills_json'][0]['name'], "Test Drill")

class DrillCreationTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin_drill', 'admin@test.com', 'password')
        self.regular_user = User.objects.create_user('regular', 'reg@test.com', 'password')
        self.coach_user = User.objects.create_user('coach', 'coach@test.com', 'password')
        self.coach = Coach.objects.create(user=self.coach_user, name="Test Coach")
        self.url = reverse('live_session:create_custom_drill')

    def test_admin_create_drill_no_coach(self):
        self.client.force_login(self.admin_user)
        data = {
            'name': 'Admin Drill',
            'category': 'Conditioning',
            'difficulty': 'Beginner',
            'description': 'Test',
            'duration': 10
        }
        response = self.client.post(self.url, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # There might be drills from other tests if data isn't cleared? TestCase runs in transaction, so it should be clean or reset.
        drill = Drill.objects.get(name='Admin Drill')
        self.assertIsNone(drill.created_by)
        self.assertTrue(drill.is_approved)

    def test_regular_user_create_drill_fail(self):
        self.client.force_login(self.regular_user)
        data = {'name': 'Regular Drill'}
        response = self.client.post(self.url, data, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_coach_create_drill_success(self):
        self.client.force_login(self.coach_user)
        data = {
            'name': 'Coach Drill',
            'duration': 15
        }
        response = self.client.post(self.url, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        drill = Drill.objects.get(name='Coach Drill')
        self.assertEqual(drill.created_by, self.coach)
        self.assertFalse(drill.is_approved)

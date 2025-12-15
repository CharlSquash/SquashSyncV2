from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from live_session.views import experimental_planner
from scheduling.models import Session
from live_session.models import Drill
from players.models import Player
from django.utils import timezone
import datetime

class ExperimentalPlannerTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser('admin', 'admin@test.com', 'password')
        self.session = Session.objects.create(
            # session_type="M", # Note: session_type was not in the model definition I saw, removing it to be safe or checking if it was just missed. 
            # Looking at the model definition provided in previous turn step 37, there is NO session_type field.
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

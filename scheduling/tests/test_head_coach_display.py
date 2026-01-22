from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from accounts.models import Coach
from scheduling.models import Session, SessionCoach, CoachAvailability

User = get_user_model()

class HeadCoachDisplayTest(TestCase):
    def setUp(self):
        # Create Users
        self.head_user = User.objects.create_user(
            username='headcoach', 
            password='password123', 
            is_staff=True,
            first_name="Head",
            last_name="Coach"
        )
        self.assist_user = User.objects.create_user(
            username='assistcoach', 
            password='password123', 
            is_staff=True,
            first_name="Assistant",
            last_name="Coach"
        )
        
        # Create Coach Profiles
        self.head_coach = Coach.objects.create(user=self.head_user, name="Head Coach Profile")
        self.assist_coach = Coach.objects.create(user=self.assist_user, name="Assistant Coach Profile")
        
        # Create Session for Today
        self.session = Session.objects.create(
            session_date=timezone.now().date(),
            session_start_time=timezone.now().time(),
            planned_duration_minutes=60
        )
        
        # Assign Coaches
        # Head Coach assignment (Explicit is_head_coach=True)
        SessionCoach.objects.create(
            session=self.session,
            coach=self.head_coach,
            coaching_duration_minutes=60,
            is_head_coach=True
        )
        
        # Assistant Coach assignment
        SessionCoach.objects.create(
            session=self.session,
            coach=self.assist_coach,
            coaching_duration_minutes=60,
            is_head_coach=False
        )
        
        # Confirm Availability (to ensure they appear in "confirmed_coaches")
        CoachAvailability.objects.create(
            coach=self.head_user,
            session=self.session,
            status=CoachAvailability.Status.AVAILABLE,
            last_action='CONFIRM'
        )
        
        CoachAvailability.objects.create(
            coach=self.assist_user,
            session=self.session,
            status=CoachAvailability.Status.AVAILABLE,
            last_action='CONFIRM'
        )

        self.client = Client()

    def test_assistant_sees_head_coach_star_data(self):
        """
        Verify that the view context provides the correct dictionary structure 
        identifying the Head Coach.
        """
        self.client.login(username='assistcoach', password='password123')
        
        response = self.client.get(reverse('homepage'))
        self.assertEqual(response.status_code, 200)
        
        # Get the first session in the list (sessions_for_coach_card)
        sessions_list = response.context['sessions_for_coach_card']
        self.assertTrue(len(sessions_list) > 0)
        
        session_data = sessions_list[0]
        confirmed_coaches = session_data['confirmed_coaches']
        
        # Find the Head Coach entry in the list
        head_coach_entry = next((c for c in confirmed_coaches if c['name'] == 'Head'), None)
        self.assertIsNotNone(head_coach_entry, "Head Coach not found in confirmed list")
        self.assertTrue(head_coach_entry['is_head_coach'], "Head Coach flag should be True for Head Coach")
        
        # Find the Assistant Coach entry
        assist_coach_entry = next((c for c in confirmed_coaches if c['name'] == 'Assistant'), None)
        self.assertIsNotNone(assist_coach_entry, "Assistant Coach not found in confirmed list")
        self.assertFalse(assist_coach_entry['is_head_coach'], "Head Coach flag should be False for Assistant")

    def test_rendering_contains_logic(self):
        """
        Since we can't easily parse the specific star icon without more complex HTML parsing,
        we rely on the context data being correct (tested above).
        However, we can check basic string presence if the template renders the names.
        """
        self.client.login(username='assistcoach', password='password123')
        response = self.client.get(reverse('homepage'))
        self.assertContains(response, "Head")
        self.assertContains(response, "Assistant")

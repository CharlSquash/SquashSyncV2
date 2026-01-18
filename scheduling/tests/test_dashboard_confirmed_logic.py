from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from scheduling.models import Session, Venue, CoachAvailability
from accounts.models import Coach

User = get_user_model()

class CoachDashboardLogicTest(TestCase):
    def setUp(self):
        # Create venue
        self.venue = Venue.objects.create(name="Test Court")
        
        # Create two coaches
        self.coach_user_a = User.objects.create_user(username='coach_a', password='password', is_staff=True, first_name="Coach A")
        self.coach_a = Coach.objects.create(user=self.coach_user_a, name="Coach A")
        
        self.coach_user_b = User.objects.create_user(username='coach_b', password='password', is_staff=True, first_name="Coach B")
        self.coach_b = Coach.objects.create(user=self.coach_user_b, name="Coach B")
        
        # Create a session for tomorrow
        tomorrow = timezone.now().date() + timedelta(days=1)
        self.session = Session.objects.create(
            session_date=tomorrow,
            session_start_time=timezone.now().time(),
            venue=self.venue,
            planned_duration_minutes=60
        )
        
        # Assign ONLY Coach A to the session
        # Note: Assigning via the M2M through model usually requires using the related manager or creating the through object
        # Using the helper or standard add if through model defaults allow, but here we have a custom through model with duration
        from scheduling.models import SessionCoach
        SessionCoach.objects.create(session=self.session, coach=self.coach_a, coaching_duration_minutes=60)
        
        # Set Availability for BOTH coaches
        # Coach A (Assigned) -> AVAILABLE
        CoachAvailability.objects.create(
            coach=self.coach_user_a,
            session=self.session,
            status=CoachAvailability.Status.AVAILABLE
        )
        
        # Coach B (NOT Assigned) -> AVAILABLE (e.g. via bulk tool)
        CoachAvailability.objects.create(
            coach=self.coach_user_b,
            session=self.session,
            status=CoachAvailability.Status.AVAILABLE
        )
        
        # Login as Coach A to view the dashboard
        self.client = Client()
        self.client.login(username='coach_a', password='password')

    def test_confirmed_coaches_list_only_shows_assigned_coaches(self):
        """
        Verify that only coaches who are BOTH assigned AND available appear in the confirmed list.
        """
        from django.urls import reverse
        response = self.client.get(reverse('homepage')) # Correctly points to _coach_dashboard
        
        # Check if response is successful
        self.assertEqual(response.status_code, 200)
        
        # Inspect the context
        # We need to find the session card for our specific session
        sessions_card = response.context.get('sessions_for_coach_card')
        self.assertIsNotNone(sessions_card)
        
        target_card = None
        for card in sessions_card:
            if card['session'].id == self.session.id:
                target_card = card
                break
        
        self.assertIsNotNone(target_card, "Target session not found in dashboard context")
        
        confirmed_names = target_card['confirmed_coaches']
        
        # Coach A should be in the list
        self.assertIn("Coach A", confirmed_names if "Coach A" in confirmed_names else [self.coach_user_a.username]) # Fallback check based on name logic
        
        # Coach B should NOT be in the list
        self.assertNotIn("Coach B", confirmed_names)
        self.assertNotIn("coach_b", confirmed_names)

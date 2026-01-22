
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core import mail
from scheduling.models import Session, Venue, SessionCoach, CoachAvailability
from players.models import SchoolGroup
from accounts.models import Coach
from scheduling.notifications import send_consolidated_session_reminder_email
from datetime import timedelta
import json

User = get_user_model()

class StaffingWorkflowTest(TestCase):
    def setUp(self):
        # Create Users
        self.admin_user = User.objects.create_superuser(username='admin', email='admin@example.com', password='password')
        self.coach_user = User.objects.create_user(username='coach', email='coach@example.com', password='password', is_staff=True)
        self.coach_profile = Coach.objects.create(user=self.coach_user, name='Test Coach')
        
        # Create Data
        self.venue = Venue.objects.create(name="Test Venue")
        self.group = SchoolGroup.objects.create(name="Test Group")
        
        self.today = timezone.now().date()
        self.session = Session.objects.create(
            session_date=self.today + timedelta(days=1),
            session_start_time='10:00',
            venue=self.venue,
            school_group=self.group,
            planned_duration_minutes=60
        )

    def test_staffing_view_loads(self):
        """Test that the staffing view loads for admin users."""
        self.client.force_login(self.admin_user)
        url = reverse('scheduling:session_staffing')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'scheduling/session_staffing.html')

    def test_assign_coach(self):
        """Test assigning a coach to a session via the AJAX endpoint."""
        self.client.force_login(self.admin_user)
        url = reverse('scheduling:assign_coaches_ajax')
        
        data = {
            'session_id': self.session.id,
            'coach_ids': [self.coach_profile.id]
        }
        
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        # Verify DB
        self.assertTrue(SessionCoach.objects.filter(session=self.session, coach=self.coach_profile).exists())
        self.assertTrue(self.session.coaches_attending.filter(id=self.coach_profile.id).exists())

    def test_assign_head_coach(self):
        """Test designating a head coach during assignment."""
        self.client.force_login(self.admin_user)
        url = reverse('scheduling:assign_coaches_ajax')
        
        data = {
            'session_id': self.session.id,
            'coach_ids': [self.coach_profile.id],
            'head_coach_id': self.coach_profile.id
        }
        
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        # Verify DB
        sc = SessionCoach.objects.get(session=self.session, coach=self.coach_profile)
        self.assertTrue(sc.is_head_coach)
        
        # Verify method on session (if applicable)
        self.assertEqual(self.session.get_head_coach(), self.coach_profile)

    def test_send_consolidated_reminder(self):
        """Test the logic for sending a session reminder."""
        # Assign coach first
        SessionCoach.objects.create(session=self.session, coach=self.coach_profile, coaching_duration_minutes=60)
        
        # Mock the sessions map expected by the function
        sessions_by_day = {self.session.session_date: [self.session]}
        
        sent = send_consolidated_session_reminder_email(self.coach_user, sessions_by_day, is_reminder=True)
        self.assertTrue(sent)
        
        # Verify email
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Reminder", mail.outbox[0].subject)
        # Check HTML content
        html_content = mail.outbox[0].alternatives[0][0]
        self.assertIn(self.session.school_group.name, html_content)

    def test_homepage_shows_assignment(self):
        """Test that the assigned session appears on the coach's homepage."""
        # 1. Assign Coach
        SessionCoach.objects.create(session=self.session, coach=self.coach_profile, coaching_duration_minutes=60)
        
        # 2. Login as Coach
        self.client.force_login(self.coach_user)
        
        # 3. Check Homepage
        response = self.client.get(reverse('homepage'))
        self.assertEqual(response.status_code, 200)
        
        # Check context
        sessions_card = response.context.get('sessions_for_coach_card')
        self.assertIsNotNone(sessions_card)
        
        # Find our session in the card list
        found = False
        for item in sessions_card:
            if item['session'].id == self.session.id:
                found = True
                break
        self.assertTrue(found, "Assigned session not found in coach's homepage card.")

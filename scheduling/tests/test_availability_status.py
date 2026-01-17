from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from scheduling.models import Session, Venue, ScheduledClass, CoachAvailability, SessionCoach
from players.models import SchoolGroup
from accounts.models import Coach
from datetime import timedelta, date
import calendar

User = get_user_model()

class AvailabilityStatusColorTest(TestCase):
    def setUp(self):
        self.password = 'password123'
        self.user = User.objects.create_user(username='coachuser', password=self.password, is_staff=True)
        self.coach = Coach.objects.create(user=self.user, name='Coach User')
        self.client.login(username='coachuser', password=self.password)

        self.venue = Venue.objects.create(name="Test Court")
        self.group = SchoolGroup.objects.create(name="Test Group")
        
        # Setup dates
        self.today = timezone.now().date()
        self.next_week = self.today + timedelta(days=7)
        
    def test_my_availability_unassigned_unavailable_is_pending(self):
        """
        If a coach marks unavailable but is NOT assigned, status should be PENDING (Grey), not UNAVAILABLE (Red/Declined).
        """
        session = Session.objects.create(
            session_date=self.next_week,
            session_start_time='10:00',
            venue=self.venue,
            school_group=self.group
        )
        
        # Mark unavailable
        CoachAvailability.objects.create(
            coach=self.user,
            session=session,
            status=CoachAvailability.Status.UNAVAILABLE
        )
        
        # Determine week offset
        week_start = self.next_week - timedelta(days=self.next_week.weekday())
        today_start = self.today - timedelta(days=self.today.weekday())
        week_offset = int((week_start - today_start).days / 7)
        
        response = self.client.get(reverse('scheduling:my_availability') + f'?week={week_offset}')
        self.assertEqual(response.status_code, 200)
        
        # Find session in context
        found_session = None
        for day in response.context['display_week']:
            for s in day['sessions']:
                if s['session_obj'] == session:
                    found_session = s
                    break
        
        self.assertIsNotNone(found_session)
        # Verify it is NOT assigned
        self.assertFalse(found_session['is_assigned'])
        
        # CRITICAL ASSERTION: The view should override UNAVAILABLE to PENDING for display
        # Currently failing (expected), will pass after fix
        self.assertEqual(found_session['current_status'], CoachAvailability.Status.PENDING)

    def test_my_availability_assigned_unavailable_is_unavailable(self):
        """
        If a coach is assigned and unavailable, it SHOULD remain UNAVAILABLE (Red/Declined).
        """
        session = Session.objects.create(
            session_date=self.next_week,
            session_start_time='12:00',
            venue=self.venue,
            school_group=self.group
        )
        
        # Assign coach using SessionCoach explicitly
        SessionCoach.objects.create(
            session=session,
            coach=self.coach,
            coaching_duration_minutes=60
        )
        
        # Mark unavailable
        CoachAvailability.objects.create(
            coach=self.user,
            session=session,
            status=CoachAvailability.Status.UNAVAILABLE
        )
        
        week_start = self.next_week - timedelta(days=self.next_week.weekday())
        today_start = self.today - timedelta(days=self.today.weekday())
        week_offset = int((week_start - today_start).days / 7)
        
        response = self.client.get(reverse('scheduling:my_availability') + f'?week={week_offset}')
        found_session = None
        for day in response.context['display_week']:
            for s in day['sessions']:
                if s['session_obj'] == session:
                    found_session = s
                    break
                    
        self.assertTrue(found_session['is_assigned'])
        self.assertEqual(found_session['current_status'], CoachAvailability.Status.UNAVAILABLE)

    def test_bulk_availability_all_unavailable_is_pending(self):
        """
        In bulk view, if ALL sessions are unavailable, it should show as PENDING (Grey), not UNAVAILABLE (Red).
        """
        # Create a rule for this month
        rule = ScheduledClass.objects.create(
            school_group=self.group,
            day_of_week=self.today.weekday(),
            start_time='14:00',
            default_venue=self.venue,
            is_active=True
        )
        
        # Create sessions for this rule in current month
        # Simplification: just create one session for today (which is this month)
        session = Session.objects.create(
            session_date=self.today,
            session_start_time='14:00',
            venue=self.venue,
            school_group=self.group,
            generated_from_rule=rule
        )
        
        # Mark unavailable
        CoachAvailability.objects.create(
            coach=self.user,
            session=session,
            status=CoachAvailability.Status.UNAVAILABLE
        )
        
        url = reverse('scheduling:set_bulk_availability')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Find the rule in context
        grouped = response.context['grouped_classes']
        day_name = self.today.strftime('%A')
        rules_list = grouped.get(day_name, [])
        
        found_rule = None
        for r in rules_list:
            if r.id == rule.id:
                found_rule = r
                break
        
        self.assertIsNotNone(found_rule)
        
        # CRITICAL ASSERTION: The view should override UNAVAILABLE to PENDING
        self.assertEqual(found_rule.current_status, CoachAvailability.Status.PENDING)

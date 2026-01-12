from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from scheduling.models import Session, ScheduledClass, CoachAvailability
from players.models import SchoolGroup
from accounts.models import Coach

User = get_user_model()

class CoachDashboardAvailabilityTest(TestCase):
    def setUp(self):
        # Create a user and coach profile
        self.password = 'password123'
        self.user = User.objects.create_user(username='coachuser', password=self.password, is_staff=True)
        self.coach = Coach.objects.create(user=self.user, name='Coach User')
        self.client.login(username='coachuser', password=self.password)

        # Create a school group (needed for scheduled class)
        self.group = SchoolGroup.objects.create(name="Test Group")

        # Create a ScheduledClass rule (needed to mark sessions as generated from rule)
        self.rule = ScheduledClass.objects.create(
            school_group=self.group,
            day_of_week=0, # Monday
            start_time='10:00:00'
        )
        
        self.dashboard_url = reverse('homepage')
        self.now = timezone.now()
        self.current_month_start = self.now.date().replace(day=1)
        # Handle December edge case for next month
        if self.current_month_start.month == 12:
            self.next_month_start = self.current_month_start.replace(year=self.current_month_start.year + 1, month=1)
        else:
            self.next_month_start = self.current_month_start.replace(month=self.current_month_start.month + 1)

    def test_no_sessions_no_prompt(self):
        """If there are no generated sessions, no prompt should be shown."""
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['show_bulk_availability_reminder'])

    def test_current_month_session_unfilled_prompts_current(self):
        """If current month has sessions and no availability set, prompt for current month."""
        # Create a session in current month
        Session.objects.create(
            session_date=self.current_month_start, # 1st of current month
            session_start_time='10:00:00',
            generated_from_rule=self.rule,
            school_group=self.group
        )

        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_bulk_availability_reminder'])
        self.assertEqual(response.context['next_month_name'], self.current_month_start.strftime('%B'))

    def test_current_month_session_filled_prompts_nothing_if_no_next_session(self):
        """If current month is filled and no next month session, show nothing."""
        s = Session.objects.create(
            session_date=self.current_month_start,
            session_start_time='10:00:00',
            generated_from_rule=self.rule,
            school_group=self.group
        )
        # Set availability
        CoachAvailability.objects.create(
            coach=self.user,
            session=s,
            status=CoachAvailability.Status.AVAILABLE
        )

        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['show_bulk_availability_reminder'])

    def test_current_filled_next_exists_prompts_next(self):
        """If current is filled but next exists (unfilled), prompt next."""
        # Current month session (filled)
        s1 = Session.objects.create(
            session_date=self.current_month_start,
            session_start_time='10:00:00',
            generated_from_rule=self.rule,
            school_group=self.group
        )
        CoachAvailability.objects.create(
            coach=self.user,
            session=s1,
            status=CoachAvailability.Status.AVAILABLE
        )

        # Next month session (unfilled)
        Session.objects.create(
            session_date=self.next_month_start,
            session_start_time='10:00:00',
            generated_from_rule=self.rule,
            school_group=self.group
        )

        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_bulk_availability_reminder'])
        self.assertEqual(response.context['next_month_name'], self.next_month_start.strftime('%B'))

    def test_only_next_exists_prompts_next(self):
        """If only next month has sessions (none in current), prompt next immediately."""
        Session.objects.create(
            session_date=self.next_month_start,
            session_start_time='10:00:00',
            generated_from_rule=self.rule,
            school_group=self.group
        )

        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_bulk_availability_reminder'])
        self.assertEqual(response.context['next_month_name'], self.next_month_start.strftime('%B'))

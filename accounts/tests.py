from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from accounts.models import Coach
from scheduling.models import Session, CoachAvailability, Venue
from players.models import SchoolGroup # Assuming this is needed for Session creation

class AdminAvailabilityInsightsTest(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        # Create Superuser
        self.admin_user = self.user_model.objects.create_superuser(
            username='admin', email='admin@example.com', password='password'
        )
        # Create Coach User and Coach Profile
        self.coach_user = self.user_model.objects.create_user(
            username='coach', email='coach@example.com', password='password', is_staff=True
        )
        self.coach = Coach.objects.create(
            user=self.coach_user,
            name="Test Coach",
            email="coach@example.com",
            is_active=True
        )
        
        # Create Venue (required for session)
        self.venue = Venue.objects.create(name="Test Venue")
        
        # Create SchoolGroup (required for session - nullable? model says nullable but good to have)
        # Assuming SchoolGroup model exists in players app. If not sure, check step 9 models.
        # Session.school_group is nullable.
        
        self.client = Client()

    def test_admin_availability_metrics(self):
        self.client.login(username='admin', password='password')
        
        now = timezone.now()
        
        # 1. Create a session tommorow (Next 7 Days) - AVAILABLE
        s1 = Session.objects.create(
            session_date=now.date() + timedelta(days=1),
            session_start_time=timezone.now().time(),
            venue=self.venue
        )
        CoachAvailability.objects.create(
            coach=self.coach_user,
            session=s1,
            status=CoachAvailability.Status.AVAILABLE
        )
        
        # 2. Create a session in 3 days (Next 7 Days) - UNAVAILABLE
        s2 = Session.objects.create(
            session_date=now.date() + timedelta(days=3),
            session_start_time=timezone.now().time(),
            venue=self.venue
        )
        CoachAvailability.objects.create(
            coach=self.coach_user,
            session=s2,
            status=CoachAvailability.Status.UNAVAILABLE
        )

        # 3. Create a session in 8 days (Outside 7 Days) - AVAILABLE
        # Should NOT count for 7-day metric
        # BUT should count for Monthly metric if within same month
        # Let's handle month boundary edge cases? 
        # For simplicity, assume test runs mid-month or we force dates.
        # But `timezone.now()` is dynamic.
        # Let's explicitly set dates.
        
        # Force 'now' to be 1st of current month to allow enough room?
        # Or just use the logic as is.
        # If today is 29th, +8 days is next month.
        # To test monthly %, we need sessions IN THE SELECTED MONTH.
        # Default selected month is current month.
        
        # Let's rely on the fact that +1 day is definitely this month or next.
        # If +1 day is next month (e.g. today is 31st), then s1 is in next month.
        # If today is 31 Jan, s1 (1 Feb) is in session_date.
        # Default view logic uses 'now' month.
        # So s1 might NOT be in the default view month if today is month‐end.
        
        # Strategy: Pass explicit year/month to the view to match our sessions.
        target_date = now.date() + timedelta(days=1)
        target_year = target_date.year
        target_month = target_date.month
        
        # 4. Create another session in the SAME target month - PENDING (no avail record or status pending)
        s3 = Session.objects.create(
            session_date=target_date, 
            session_start_time=(timezone.now() + timedelta(hours=2)).time(),
            venue=self.venue
        )
        # No availability record = Unset/Missing
        
        # Total sessions in target month: 
        # If s1 and s3 are in target month. 
        # s2 (target + 2 days) is also likely in target month unless target was end of month.
        # s2 is +3 days from NOW.
        # if target is +1 days. s2 is +2 days from target.
        # verify s2 month.
        
        s2_date = now.date() + timedelta(days=3)
        s2_is_in_target_month = (s2_date.year == target_year and s2_date.month == target_month)
        
        expected_total = 2 # s1, s3
        if s2_is_in_target_month:
            expected_total += 1
            
        # Metric 1: 7 Day Available Count
        # s1 is AVAILABLE and within 7 days.
        # s2 is UNAVAILABLE and within 7 days.
        # s3 is NO RECORD.
        # Expected: 1
        
        # Metric 2: Monthly %
        # Available in target month: s1 (1).
        # Total in target month: expected_total.
        # % = (1 / expected_total) * 100
        
        url = f"/accounts/coaches/{self.coach.id}/?year={target_year}&month={target_month}"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('admin_7day_avail_count', response.context)
        self.assertEqual(response.context['admin_7day_avail_count'], 1)
        
        self.assertIn('admin_month_percentage', response.context)
        expected_pct = (1 / expected_total) * 100
        self.assertAlmostEqual(response.context['admin_month_percentage'], expected_pct, places=1)
        
        # Check list
        # User requested filtering: ONLY Available and Emergency status should be in the list
        self.assertIn('admin_month_sessions', response.context)
        
        # In this setup:
        # s1: AVAILABLE -> Should be in list
        # s2: UNAVAILABLE -> Should NOT be in list
        # s3: Missing/Pending -> Should NOT be in list
        
        expected_list_count = 1 # Only s1
        
        self.assertEqual(len(response.context['admin_month_sessions']), expected_list_count)
        
        # Verify s1 status in the list
        sessions_list = list(response.context['admin_month_sessions'])
        # find s1
        s1_in_ctx = next(s for s in sessions_list if s.id == s1.id)
        # Check prefetched attribute
        self.assertTrue(hasattr(s1_in_ctx, 'this_coach_availability_list'))
        self.assertEqual(len(s1_in_ctx.this_coach_availability_list), 1)
        self.assertEqual(s1_in_ctx.this_coach_availability_list[0].status, CoachAvailability.Status.AVAILABLE)

        # Verify s2 and s3 are NOT in list
        s2_ids = [s.id for s in sessions_list]
        self.assertNotIn(s2.id, s2_ids)
        self.assertNotIn(s3.id, s2_ids)


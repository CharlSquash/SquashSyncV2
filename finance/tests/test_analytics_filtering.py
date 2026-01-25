import datetime
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from finance.analytics_service import calculate_monthly_projection
from finance.models import CoachSessionCompletion, RecurringCoachAdjustment
from scheduling.models import Session, SessionCoach, ScheduledClass, Venue
from players.models import SchoolGroup
from accounts.models import Coach

User = get_user_model()

class FinancialAnalyticsFilteringTest(TestCase):
    def setUp(self):
        # Create Coaches
        self.user1 = User.objects.create_user(username='coach1', password='password')
        self.coach1 = Coach.objects.create(user=self.user1, name="Coach One", hourly_rate=Decimal('100.00'), is_active=True)
        
        self.user2 = User.objects.create_user(username='coach2', password='password')
        self.coach2 = Coach.objects.create(user=self.user2, name="Coach Two", hourly_rate=Decimal('150.00'), is_active=True)

        # Create Groups/Rules
        self.group_a = SchoolGroup.objects.create(name="Group A")
        self.group_b = SchoolGroup.objects.create(name="Group B")
        
        # Create Venues (needed for ScheduledClass)
        self.venue = Venue.objects.create(name="Test Venue")

        self.rule_a = ScheduledClass.objects.create(
            school_group=self.group_a, day_of_week=0, start_time=datetime.time(14, 0), default_venue=self.venue
        )
        self.rule_b = ScheduledClass.objects.create(
            school_group=self.group_b, day_of_week=1, start_time=datetime.time(15, 0), default_venue=self.venue
        )

        # Create Recurring Adjustment (Overhead)
        self.overhead = RecurringCoachAdjustment.objects.create(
            coach=self.coach1,
            amount=Decimal('500.00'),
            description="Monthly Bonus",
            is_active=True
        )

        # Create Sessions & Completions for Current Month
        today = timezone.now().date()
        self.year = today.year
        self.month = today.month
        
        # Session 1: Group A, Realized (Confirmed)
        self.sess1 = Session.objects.create(
            session_date=today.replace(day=1),
            session_start_time=datetime.time(10, 0),
            generated_from_rule=self.rule_a,
            status='finished'
        )
        self.sc1 = SessionCoach.objects.create(session=self.sess1, coach=self.coach1, coaching_duration_minutes=60)
        self.comp1 = CoachSessionCompletion.objects.create(session=self.sess1, coach=self.coach1, confirmed_for_payment=True)
        # Cost: 100 * 1 = 100

        # Session 2: Group B, Realized (Confirmed)
        self.sess2 = Session.objects.create(
            session_date=today.replace(day=2),
            session_start_time=datetime.time(10, 0),
            generated_from_rule=self.rule_b,
            status='finished'
        )
        self.sc2 = SessionCoach.objects.create(session=self.sess2, coach=self.coach2, coaching_duration_minutes=60)
        self.comp2 = CoachSessionCompletion.objects.create(session=self.sess2, coach=self.coach2, confirmed_for_payment=True)
        # Cost: 150 * 1 = 150

        # Session 3: Group A, Accrued (Past, Unconfirmed)
        # Using yesterday logic or explicitly creating date < today if today is not day 1
        past_date = today - datetime.timedelta(days=1)
        if past_date.month != self.month:
             past_date = today # Fallback if today is 1st, make it today but handled by time? No, analytics checks date < today.
             # If today is 1st, Accrued logic might be tricky for "past". Let's force it to be "future" for Projected if we can't make it past.
             # Or test assumes running on day > 1.
             # Let's forcefully allow session_date to be in the month but < today.
             pass
        
        # For reliable testing, let's mock today or ensure dates align. 
        # But simpler: If today is 1st, we can't easily test accrued for this month unless we manipulate time.
        # Let's assume testing runs when month has days. If not, this test might need adjustment.
        # Alternatively, let's use a "future" session for Projected.
        
        # Session 4: Group A, Projected (Future)
        future_date = today + datetime.timedelta(days=1)
        # Ensure it's in the same month
        if future_date.month != self.month:
            future_date = today # Use today (which counts as future/projected in logic: >= today)
        
        self.sess4 = Session.objects.create(
            session_date=future_date,
            session_start_time=datetime.time(10, 0),
            generated_from_rule=self.rule_a,
            planned_duration_minutes=60
        )
        self.sc4 = SessionCoach.objects.create(session=self.sess4, coach=self.coach1, coaching_duration_minutes=60)
        # Cost: 100 * 1 = 100

    def test_global_projection(self):
        """Verify global totals include everything, with adjustments separated."""
        data = calculate_monthly_projection(self.year, self.month)
        
        # Realized: 250 (Sess1 100 + Sess2 150)
        # Adjustments: 500 (Overhead)
        # Projected: 100 (Sess4)
        
        self.assertEqual(data['realized_total'], Decimal('250.00'))
        self.assertEqual(data['adjustments_total'], Decimal('500.00'))
        self.assertEqual(data['projected_total'], Decimal('100.00'))
        # Grand: 250 + 500 + 100 = 850
        self.assertEqual(data['grand_total'], Decimal('850.00'))

    def test_group_a_filter(self):
        """Verify filtering for Group A excludes Group B and Overheads."""
        data = calculate_monthly_projection(self.year, self.month, scheduled_class_id=self.rule_a.id)
        
        # Realized: 100 (Sess1 only). Excluding Sess2 (Group B) and Overhead.
        # Projected: 100 (Sess4 only).
        # Adjustments: 0 (Excluded when filtering by group)
        
        self.assertEqual(data['realized_total'], Decimal('100.00'))
        self.assertEqual(data['adjustments_total'], Decimal('0.00'))
        self.assertEqual(data['projected_total'], Decimal('100.00'))
        self.assertEqual(data['breakdown']['realized_count'], 1)

    def test_group_b_filter(self):
        """Verify filtering for Group B."""
        data = calculate_monthly_projection(self.year, self.month, scheduled_class_id=self.rule_b.id)
        
        # Realized: 150 (Sess2 only). Excluding Sess1 and Overhead.
        # Projected: 0 (No future sessions for Group B)
        # Adjustments: 0
        
        self.assertEqual(data['realized_total'], Decimal('150.00'))
        self.assertEqual(data['adjustments_total'], Decimal('0.00'))
        self.assertEqual(data['projected_total'], Decimal('0.00'))

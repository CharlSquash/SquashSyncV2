from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from finance.views import financial_projection_ajax
from finance.models import RecurringCoachAdjustment
from accounts.models import Coach
from scheduling.models import ScheduledClass, Venue
from players.models import SchoolGroup
import json
import datetime
from decimal import Decimal

User = get_user_model()

class FinancialViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(username='admin', password='password')
        
        # Setup data to checking filtering
        self.coach = Coach.objects.create(user=self.user, name="Coach Test", hourly_rate=Decimal('100.00'))
        
        # Create overhead - this should be visible globally but hidden when filtered
        RecurringCoachAdjustment.objects.create(
            coach=self.coach, amount=Decimal('500.00'), description="Overhead", is_active=True
        )
        
        self.group = SchoolGroup.objects.create(name="Group A")
        self.venue = Venue.objects.create(name="Venue")
        self.rule = ScheduledClass.objects.create(
            school_group=self.group, day_of_week=0, start_time=datetime.time(10,0), default_venue=self.venue
        )

    def test_view_global(self):
        """Test global view includes overhead."""
        request = self.factory.get('/finance/reports/financial-projection/', {'year': 2026, 'month': 1})
        request.user = self.user
        
        response = financial_projection_ajax(request)
        content = json.loads(response.content)
        
        # We can't easily parse specific numbers from HTML string without BS4, 
        # but we can check if data was passed to context if we mocked render_to_string, 
        # or we can check the analytics_service logic implicitly by the total.
        # But financial_projection_ajax returns HTML. 
        # For this debug, I just want to ensure `scheduled_class_id` is parsed.
        
        # Let's mock calculate_monthly_projection to verify arguments? 
        # Or easier: assert that the HTML contains the overhead amount if global, and not if filtered.
        # The overhead is 500. Global total should include 500 (Realized).
        
        self.assertIn('500.00', content['html'])

    def test_view_filtered(self):
        """Test filtered view excludes overhead."""
        request = self.factory.get('/finance/reports/financial-projection/', {
            'year': 2026, 
            'month': 1, 
            'scheduled_class_id': self.rule.id
        })
        request.user = self.user
        
        response = financial_projection_ajax(request)
        content = json.loads(response.content)
        
        # 500.00 should NOT be there as overheads are excluded.
        # (Assuming no other costs match).
        self.assertNotIn('500.00', content['html'])

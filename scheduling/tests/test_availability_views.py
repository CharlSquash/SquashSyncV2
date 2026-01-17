
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from scheduling.models import Session, Venue, ScheduledClass
from players.models import SchoolGroup
from accounts.models import Coach
from datetime import timedelta

User = get_user_model()

class AvailabilityViewSortingTest(TestCase):
    def setUp(self):
        self.password = 'password123'
        self.user = User.objects.create_user(username='coachuser', password=self.password, is_staff=True)
        self.coach = Coach.objects.create(user=self.user, name='Coach User')
        self.client.login(username='coachuser', password=self.password)

        self.venue1 = Venue.objects.create(name="Alpha Court")
        self.venue2 = Venue.objects.create(name="Beta Court")
        self.group = SchoolGroup.objects.create(name="Test Group")
        
    def test_my_availability_sorting(self):
        """
        Verify that sessions on the same day are sorted by venue name, then time.
        """
        today = timezone.now().date()
        # Ensure we are testing a future date to be visible in default week view
        test_date = today + timedelta(days=1) 
        
        # Create sessions mixed up
        s1 = Session.objects.create(
            session_date=test_date,
            session_start_time='10:00',
            venue=self.venue2, # Beta
            school_group=self.group
        )
        s2 = Session.objects.create(
            session_date=test_date,
            session_start_time='09:00',
            venue=self.venue1, # Alpha
            school_group=self.group
        )
        s3 = Session.objects.create(
            session_date=test_date,
            session_start_time='11:00',
            venue=self.venue1, # Alpha
            school_group=self.group
        )
        
        url = reverse('scheduling:my_availability')
        # We might need to adjust week offset if test_date falls in next week, 
        # but +1 day is usually in current view unless it's Sunday->Monday edge case.
        # Let's just fetch default view.
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Find the day in context
        display_week = response.context['display_week']
        day_data = None
        for day in display_week:
            if day['date'] == test_date:
                day_data = day
                break
        
        self.assertIsNotNone(day_data)
        sessions_list = day_data['sessions']
        self.assertEqual(len(sessions_list), 3)
        
        # Expected order: 
        # 1. Alpha @ 09:00 (s2)
        # 2. Alpha @ 11:00 (s3)
        # 3. Beta @ 10:00 (s1)
        
        self.assertEqual(sessions_list[0]['session_obj'], s2)
        self.assertEqual(sessions_list[1]['session_obj'], s3)
        self.assertEqual(sessions_list[2]['session_obj'], s1)
        
    def test_bulk_availability_sorting(self):
        """
        Verify that scheduled classes are sorted by venue name, then start time.
        """
        # Create rules
        # Use Monday (0)
        r1 = ScheduledClass.objects.create(
            school_group=self.group,
            day_of_week=0,
            start_time='10:00',
            default_venue=self.venue2 # Beta
        )
        r2 = ScheduledClass.objects.create(
            school_group=self.group,
            day_of_week=0,
            start_time='09:00',
            default_venue=self.venue1 # Alpha
        )
        r3 = ScheduledClass.objects.create(
            school_group=self.group,
            day_of_week=0,
            start_time='11:00',
            default_venue=self.venue1 # Alpha
        )
        
        url = reverse('scheduling:set_bulk_availability')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        grouped_classes = response.context['grouped_classes']
        monday_classes = grouped_classes.get('Monday', [])
        
        self.assertEqual(len(monday_classes), 3)
        
        # Expected order: Alpha 09:00, Alpha 11:00, Beta 10:00
        self.assertEqual(monday_classes[0], r2)
        self.assertEqual(monday_classes[1], r3)
        self.assertEqual(monday_classes[2], r1)

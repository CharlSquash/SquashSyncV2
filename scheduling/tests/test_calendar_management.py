from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from scheduling.models import Session, Venue
import json
from datetime import date, time

User = get_user_model()

class CalendarManagementTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.venue = Venue.objects.create(name="Test Venue")
        self.session = Session.objects.create(
            session_date=date(2026, 1, 1),
            session_start_time=time(10, 0),
            venue=self.venue,
            planned_duration_minutes=60
        )

    def test_create_session_ajax(self):
        self.client.force_login(self.superuser)
        url = reverse('scheduling:create_session_ajax')
        data = {
            'date': '2026-02-01',
            'time': '14:00',
            'venue_id': self.venue.id,
            'duration': 90,
            'notes': 'Test create'
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Session.objects.filter(notes='Test create').exists())

    def test_update_session_ajax(self):
        self.client.force_login(self.superuser)
        url = reverse('scheduling:update_session_ajax')
        data = {
            'session_id': self.session.id,
            'session_date': '2026-01-02',
            'start_time': '11:00'
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        self.session.refresh_from_db()
        self.assertEqual(self.session.session_date, date(2026, 1, 2))
        self.assertEqual(self.session.session_start_time, time(11, 0))

    def test_delete_session_ajax(self):
        self.client.force_login(self.superuser)
        url = reverse('scheduling:delete_session_ajax')
        data = {'session_id': self.session.id}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Session.objects.filter(pk=self.session.id).exists())

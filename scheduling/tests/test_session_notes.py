from django.test import TestCase, Client
from django.contrib.auth.models import User
from scheduling.models import Session, SessionNote
from accounts.models import Coach
from django.utils import timezone
from django.urls import reverse
import json

class SessionNotesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser('admin', 'admin@test.com', 'password')
        self.coach_user = User.objects.create_user('coach', 'coach@test.com', 'password')
        self.coach = Coach.objects.create(user=self.coach_user, name="Test Coach")
        self.regular_user = User.objects.create_user('user', 'user@test.com', 'password')
        
        self.session = Session.objects.create(
             session_date=timezone.now().date(),
             session_start_time=timezone.now().time(),
             planned_duration_minutes=60
        )
        self.url = reverse('live_session:add_session_note', args=[self.session.id])

    def test_create_note_superuser(self):
        self.client.force_login(self.superuser)
        data = {'text': 'Superuser Note'}
        response = self.client.post(self.url, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        self.assertEqual(SessionNote.objects.count(), 1)
        note = SessionNote.objects.first()
        self.assertEqual(note.text, 'Superuser Note')
        self.assertEqual(note.author, self.superuser)

    def test_create_note_coach(self):
        self.client.force_login(self.coach_user)
        data = {'text': 'Coach Note'}
        response = self.client.post(self.url, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        note = SessionNote.objects.latest('created_at')
        self.assertEqual(note.text, 'Coach Note')
        self.assertEqual(note.author, self.coach_user)
        
    def test_create_note_unauthorized(self):
        self.client.force_login(self.regular_user)
        data = {'text': 'Hacker Note'}
        response = self.client.post(self.url, data, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SessionNote.objects.count(), 0)

    def test_create_note_empty(self):
        self.client.force_login(self.coach_user)
        data = {'text': '   '}
        response = self.client.post(self.url, data, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SessionNote.objects.count(), 0)

    def test_planner_view_context(self):
        # Create a note first
        SessionNote.objects.create(session=self.session, author=self.coach_user, text="Existing Note")
        
        self.client.force_login(self.coach_user)
        url = reverse('live_session:planner_v2', args=[self.session.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        context_notes = response.context['notes_json']
        self.assertEqual(len(context_notes), 1)
        self.assertEqual(context_notes[0]['text'], "Existing Note")
        self.assertEqual(context_notes[0]['author_name'], "coach")
        # Actually Coach model has a name field but I link to User. 
        # My code: `author_name = note.author.get_full_name() or note.author.username`
        # Using self.coach_user logic... it will be 'coach'.
        
        # Let's fix expectation or fix code. The code uses `note.author` which is a User instance.
        # If I want the Coach's name I should try to fetch the coach profile. 
        # But for now, user.username is 'coach'.
        self.assertEqual(context_notes[0]['author_name'], "coach")

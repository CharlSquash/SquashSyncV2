from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from players.views import players_list
from players.models import Player
from django.urls import reverse

class PlayersListFilterTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password')
        # Create an unassigned player
        Player.objects.create(first_name='Unassigned', last_name='Player', is_active=True)

    def test_players_list_with_school_group_none(self):
        # Simulate request with ?school_group=None
        request = self.factory.get(reverse('players:players_list'), {'school_group': 'None'})
        request.user = self.user
        
        response = players_list(request)
        
        self.assertEqual(response.status_code, 200)

from django.test import TestCase
from players.models import Player, SchoolGroup
from django.contrib.auth import get_user_model

User = get_user_model()

class PlayerGroupSeparationTest(TestCase):
    def setUp(self):
        # Create a player
        self.user = User.objects.create_user(username='testuser', password='password')
        self.player = Player.objects.create(
            user=self.user,
            first_name='Test',
            last_name='Player'
        )

        # Create active groups
        self.active_group1 = SchoolGroup.objects.create(name='Active Group 1', is_active=True)
        self.active_group2 = SchoolGroup.objects.create(name='Active Group 2', is_active=True)

        # Create past groups
        self.past_group1 = SchoolGroup.objects.create(name='Past Group 2023', is_active=False, year=2023)
        self.past_group2 = SchoolGroup.objects.create(name='Past Group 2022', is_active=False, year=2022)

        # Assign groups
        self.player.school_groups.add(self.active_group1, self.active_group2, self.past_group1, self.past_group2)

    def test_active_groups_property(self):
        """Verify active_groups returns only active groups."""
        active_groups = self.player.active_groups
        self.assertEqual(active_groups.count(), 2)
        self.assertIn(self.active_group1, active_groups)
        self.assertIn(self.active_group2, active_groups)
        self.assertNotIn(self.past_group1, active_groups)

    def test_past_groups_property(self):
        """Verify past_groups returns only inactive groups, ordered by year desc."""
        past_groups = self.player.past_groups
        self.assertEqual(past_groups.count(), 2)
        self.assertIn(self.past_group1, past_groups)
        self.assertIn(self.past_group2, past_groups)
        self.assertNotIn(self.active_group1, past_groups)
        
        # Check ordering: 2023 before 2022
        self.assertEqual(past_groups[0], self.past_group1)
        self.assertEqual(past_groups[1], self.past_group2)

    def test_prefetch_caching(self):
        """Verify that prefetching sets the cache attributes."""
        # This simulates what the view does
        from django.db.models import Prefetch
        
        queryset = Player.objects.filter(pk=self.player.pk).prefetch_related(
            Prefetch('school_groups', queryset=SchoolGroup.objects.filter(is_active=True), to_attr='_active_groups_cache'),
            Prefetch('school_groups', queryset=SchoolGroup.objects.filter(is_active=False).order_by('-year'), to_attr='_past_groups_cache')
        )
        
        player = queryset.first()
        
        # Check if cache attributes exist
        self.assertTrue(hasattr(player, '_active_groups_cache'))
        self.assertTrue(hasattr(player, '_past_groups_cache'))
        
        # Check values in cache
        self.assertEqual(len(player._active_groups_cache), 2)
        self.assertEqual(len(player._past_groups_cache), 2)
        
        # Access properties and ensure they return the cached lists (which are lists, not QuerySets)
        self.assertIsInstance(player.active_groups, list)
        self.assertIsInstance(player.past_groups, list)
        
        # Verify content
        self.assertEqual(player.active_groups[0].name, 'Active Group 1' if player.active_groups[0].name < player.active_groups[1].name else 'Active Group 2')
        self.assertEqual(player.past_groups[0].year, 2023) 

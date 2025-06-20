# live_session/live_session_utils.py

from datetime import timedelta
from collections import defaultdict

# Import models from their new app locations
from players.models import Player
from scheduling.models import ManualCourtAssignment

def _calculate_skill_priority_groups(players_qs, num_courts):
    """
    Sorts players by skill level and distributes them across the available courts.
    """
    if not players_qs:
        return {}

    # Sort players: Advanced > Intermediate > Beginner, then alphabetically
    player_list = sorted(list(players_qs), key=lambda p: (
        {'ADV': 0, 'INT': 1, 'BEG': 2}.get(p.skill_level, 3), p.last_name, p.first_name
    ))

    assignments = defaultdict(list)
    player_count = len(player_list)

    if player_count == 0 or num_courts == 0:
        return {}

    # Assign players to courts in a round-robin fashion
    for i, player in enumerate(player_list):
        court_index = i % num_courts
        assignments[court_index + 1].append(player)

    return dict(assignments)
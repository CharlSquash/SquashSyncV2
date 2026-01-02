
import os
import django
from rapidfuzz import fuzz

# Setup Django standalone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from players.models import Player
from players.management.commands.activate_registered_players import Command

def test_sibling_matching():
    print("--- Setting up Test Data ---")
    
    # 1. Clear existing test data (if any checks conflict, but effectively we are just mocking the logic or using in-memory objects if possible, 
    # but the command uses ORM queries. So we will create temporary DB records.)
    
    # Create "Luca Kock" in DB
    p1, created = Player.objects.get_or_create(
        first_name="Luca", 
        last_name="Kock", 
        defaults={
            'parent_email': "parent@example.com",
            'contact_number': "0821111111"
        }
    )
    if not created:
        p1.parent_email = "parent@example.com"
        p1.save()
        
    print(f"Created/Found Player in DB: {p1.first_name} {p1.last_name} (Email: {p1.parent_email})")

    # 2. Simulate CSV Data for "Cayden Kock" (Sibling)
    csv_row_data = {
        'first_name': 'Cayden',
        'last_name': 'Kock',
        'email': 'parent@example.com', # Same email
        'contact_1': '0829999999',
        'contact_2': '0821111111', # Example: maybe they share a phone or have different one
        'grade_raw': 'Grade 8',
    }
    
    print(f"Incoming CSV Data: {csv_row_data['first_name']} {csv_row_data['last_name']} (Email: {csv_row_data['email']})")

    # 3. initialize command
    cmd = Command()
    all_players = [p1] # Simulate passing the list from the DB

    # 4. Run matching logic
    print("\n--- Running find_match ---")
    match_type, player, score = cmd.find_match(csv_row_data, all_players)

    print(f"Result: Match Type: {match_type}, Player: {player}, Score: {score}")

    # 5. Assertions
    if player == p1:
        print("\n[FAIL] Incorrectly matched Sibling to existing player! This reproduces the bug.")
    else:
        print("\n[SUCCESS] Correctly identified as NO match (or match to correct self if we added him).")

if __name__ == "__main__":
    test_sibling_matching()

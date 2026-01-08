
import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from live_session.models import Drill

def populate():
    print("Populating drills...")

    # Clear existing drills (optional, commented out to avoid data loss on production if run accidentally, 
    # though user asked for this because DB is empty)
    # Drill.objects.all().delete() 

    categories = [
        ('Technical', [
            'Forehand Drive Technique',
            'Backhand Drop Efficiency',
            'Volley Accuracy',
            'Lob Control'
        ]),
        ('Conditioning', [
            'Court Sprints',
            'Lunges Series',
            'Star Drill',
            'Endurance Runs'
        ]),
        ('Warmups', [
            'Dynamic Stretching',
            'Light Jogging',
            'Joint Rotations',
            'Shadow Swings'
        ]),
        ('Hand-Eye Coordination', [
            'Ball Bouncing',
            'Racket Edge Balance',
            'Two Ball Juggle',
            'Reaction Wall'
        ]),
        ('Fun Games', [
            'King of the Court',
            'Around the World',
            'Target Practice',
            'Squash Tennis'
        ]),
        ('Ghosting', [
            '6 Point Ghosting',
            'Front Corners Ghosting',
            'Back Corners Ghosting',
            'Random Ghosting'
        ]),
        ('Drills - Racketwork', [
            'Figure 8 Volleys',
            'Wrist Snap Practice',
            'Short Volleys',
            'Solo Feeds'
        ]),
        ('Feeding Drills', [
            'Boast and Drive',
            'Drop and Drive',
            'Volley Feed',
            'Cross Court Feeding'
        ]),
        ('Condition Games', [
            'Length Only Game',
            'Above Tin Game',
            'Quarter Court Game',
            'Handicap Scoring'
        ]),
        ('Fitness', [
            'Burpees',
            'Box Jumps',
            'Plank Variations',
            'Medicine Ball Throws'
        ]),
        ('Movement', [
            'Split Step Timing',
            'T Movement',
            'Recovery Steps',
            'Change of Direction'
        ]),
        ('Circuits (Score/Time)', [
            'Circuit A - High Intensity',
            'Circuit B - Strength Focus',
            'Circuit C - Agility',
            'Circuit D - Mixed'
        ]),
    ]

    difficulties = ['Beginner', 'Intermediate', 'Advanced']
    
    # Generic stock squash/sports videos (using some placeholders or real looking generic youtube IDs)
    # I'll use a few different ones so they don't all look identical if previewed
    video_urls = [
         "https://www.youtube.com/watch?v=dQw4w9WgXcQ", # Classic placeholder
         "https://www.youtube.com/watch?v=lT6HX1g2tIY",
         "https://www.youtube.com/watch?v=jNQXAC9IVRw",
         "https://www.youtube.com/watch?v=L_jWHffIx5E",
    ]

    count = 0
    for cat, drill_names in categories:
        for name in drill_names:
            # Check if exists to avoid duplicates if run multiple times
            if not Drill.objects.filter(name=name, category=cat).exists():
                Drill.objects.create(
                    name=name,
                    category=cat,
                    difficulty=random.choice(difficulties),
                    description=f"This is a sample description for {name}. Focus on consistency and movement.",
                    duration_minutes=random.randint(5, 20),
                    video_url=random.choice(video_urls),
                    is_approved=True 
                )
                print(f"Created: {name} ({cat})")
                count += 1
            else:
                print(f"Skipped: {name} (Already exists)")
    
    print(f"Done. Created {count} new drills.")

if __name__ == '__main__':
    populate()


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
    
    # NEW: Specific video URL requested by user
    target_video_url = "https://www.youtube.com/shorts/Iw5M2ICIvuk"

    count = 0
    updated_count = 0
    
    # 1. Ensure all drills exist
    for cat, drill_names in categories:
        for name in drill_names:
            drill, created = Drill.objects.get_or_create(
                name=name,
                category=cat,
                defaults={
                    'difficulty': random.choice(difficulties),
                    'description': f"This is a sample description for {name}. Focus on consistency and movement.",
                    'duration_minutes': random.randint(5, 20),
                    'video_url': target_video_url,
                    'is_approved': True
                }
            )
            
            if created:
                print(f"Created: {name} ({cat})")
                count += 1
            else:
                # Update existing if needed (optional based on requirement "just like they are currently" 
                # but we definitely need to update the URL)
                if drill.video_url != target_video_url:
                    drill.video_url = target_video_url
                    drill.save()
                    updated_count += 1
                    print(f"Updated URL: {name}")

    # 2. Update ALL drills in the database to have this URL (even those not in the list above, if any)
    # The requirement is "add this url to all the drills's video url"
    # This covers any drills that might have been created manually or exist from before.
    total_updated = Drill.objects.update(video_url=target_video_url)
    
    print(f"Done. Created {count} new drills.")
    print(f"Ensured video URL is set for {total_updated} drills.")

if __name__ == '__main__':
    populate()

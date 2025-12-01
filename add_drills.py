import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from live_session.models import Drill

def add_drills():
    drills = [
        {
            "name": "Forehand Drive",
            "category": "Technique",
            "difficulty": "Beginner",
            "description": "Practice hitting straight drives on the forehand side.",
            "duration_minutes": 10
        },
        {
            "name": "Backhand Volley",
            "category": "Technique",
            "difficulty": "Intermediate",
            "description": "Practice hitting volleys on the backhand side.",
            "duration_minutes": 15
        },
        {
            "name": "Boast and Drive",
            "category": "Conditioned Game",
            "difficulty": "Intermediate",
            "description": "One player boasts, the other drives.",
            "duration_minutes": 20
        },
        {
            "name": "Ghosting",
            "category": "Fitness",
            "difficulty": "Advanced",
            "description": "Movement practice without a ball.",
            "duration_minutes": 15
        },
        {
            "name": "3-Corner Drill",
            "category": "Tactical",
            "difficulty": "Advanced",
            "description": "Random feeding to 3 corners.",
            "duration_minutes": 12
        }
    ]

    for drill_data in drills:
        drill, created = Drill.objects.get_or_create(name=drill_data['name'], defaults=drill_data)
        if created:
            print(f"Created drill: {drill.name}")
        else:
            print(f"Drill already exists: {drill.name}")

if __name__ == '__main__':
    add_drills()

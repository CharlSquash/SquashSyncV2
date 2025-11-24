import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Coach

User = get_user_model()

def create_coach_user():
    username = 'test_coach'
    email = 'coach@example.com'
    password = 'password123'
    
    if User.objects.filter(username=username).exists():
        print(f"User {username} already exists.")
        user = User.objects.get(username=username)
    else:
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_staff = True
        user.save()
        print(f"Created user {username}")

    if not hasattr(user, 'coach_profile'):
        Coach.objects.create(user=user, name="Test Coach", email=email)
        print(f"Created coach profile for {username}")
    else:
        print(f"Coach profile already exists for {username}")

if __name__ == '__main__':
    create_coach_user()

import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'password123')
    print("Superuser created.")
else:
    u = User.objects.get(username='admin')
    u.set_password('password123')
    u.save()
    print("Superuser password reset.")

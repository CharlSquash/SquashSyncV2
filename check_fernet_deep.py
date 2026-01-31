
import os
import django
from django.utils.encoding import force_str

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from accounts.models import Coach

print(f"force_str(b'test'): {repr(force_str(b'test'))}")

# Create a fresh coach to test exact flow
from django.contrib.auth import get_user_model
User = get_user_model()
try:
    u = User.objects.create(username='debug_fernet', email='debug@example.com')
except:
    u = User.objects.get(username='debug_fernet')

# Create coach
Coach.objects.filter(user=u).delete()
c = Coach.objects.create(user=u, name='Debug Coach', account_number='123456789')

print(f"Fresh Coach Created with '123456789'")
c.refresh_from_db()
print(f"Retrieved: {repr(c.account_number)}")
print(f"Type: {type(c.account_number)}")

# Test update
c.account_number = "987654321"
c.save()
c.refresh_from_db()
print(f"Updated to '987654321', Retrieved: {repr(c.account_number)}")


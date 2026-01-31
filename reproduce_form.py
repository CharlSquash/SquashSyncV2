
import os
import django
from django.utils.encoding import force_str

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from accounts.models import Coach
from accounts.forms import CoachProfileUpdateForm
from django.contrib.auth import get_user_model

User = get_user_model()
u, _ = User.objects.get_or_create(username='form_debug', email='form@example.com')
Coach.objects.filter(user=u).delete()
c = Coach.objects.create(user=u, name='Form Debug Coach')

# Simulate form submission
form_data = {
    'phone': '0821234567',
    'bank_name': 'Test Bank',
    'account_number': '123456',
    'branch_code': '999999',
    'account_type': 'Current'
}

form = CoachProfileUpdateForm(data=form_data, instance=c)
if form.is_valid():
    print("Form is valid")
    c_saved = form.save()
    print(f"Saved Account Number: {repr(c_saved.account_number)}")
    
    # Reload from DB
    c_saved.refresh_from_db()
    print(f"Reloaded Account Number: {repr(c_saved.account_number)}")
else:
    print(f"Form errors: {form.errors}")

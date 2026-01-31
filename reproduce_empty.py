
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from accounts.models import Coach
from accounts.forms import CoachProfileUpdateForm
from django.contrib.auth import get_user_model

User = get_user_model()
u, _ = User.objects.get_or_create(username='empty_debug', email='empty@example.com')
Coach.objects.filter(user=u).delete()
c = Coach.objects.create(user=u, name='Empty Debug Coach')

# Simulate initial empty state check
print(f"Initial Account Number: {repr(c.account_number)}")

# Simulate form submission with EMPTY values
form_data = {
    'phone': '0821234567',
    'bank_name': '',
    'account_number': '',
    'branch_code': '',
    'account_type': 'Current'
}

form = CoachProfileUpdateForm(data=form_data, instance=c)
if form.is_valid():
    print("Form is valid")
    c_saved = form.save()
    print(f"Saved Empty Account Number: {repr(c_saved.account_number)}")
    
    # Reload from DB
    c_saved.refresh_from_db()
    print(f"Reloaded Empty Account Number: {repr(c_saved.account_number)}")
else:
    print(f"Form errors: {form.errors}")

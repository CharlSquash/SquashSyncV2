
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from accounts.models import Coach
from accounts.forms import CoachProfileUpdateForm
from django.contrib.auth import get_user_model

User = get_user_model()
u, _ = User.objects.get_or_create(username='commit_debug', email='commit@example.com')
Coach.objects.filter(user=u).delete()
c = Coach.objects.create(user=u, name='Commit Debug Coach')

# Simulate POST data
form_data = {
    'phone': '0821234567',
    'bank_name': 'Commit Bank',
    'account_number': '111222',
    'branch_code': '333444',
    'account_type': 'Savings'
}

print("--- Testing save(commit=False) ---")
form = CoachProfileUpdateForm(data=form_data, instance=c)
if form.is_valid():
    print("Form is valid")
    # Simulate the view logic EXACTLY
    coach_instance = form.save(commit=False)
    coach_instance.whatsapp_phone_number = coach_instance.phone
    coach_instance.save()
    
    print(f"InMemory Instance Bank: {coach_instance.bank_name}")
    print(f"InMemory Instance Acc: {coach_instance.account_number}")
    
    # Reload from DB
    c_reloaded = Coach.objects.get(pk=c.pk)
    print(f"DB Instance Bank: {c_reloaded.bank_name}")
    print(f"DB Instance Acc: {c_reloaded.account_number}")
    
    if c_reloaded.bank_name == 'Commit Bank':
        print("SUCCESS: Data persisted correctly.")
    else:
        print("FAILURE: Data lost.")
else:
    print(f"Form errors: {form.errors}")

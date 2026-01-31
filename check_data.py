
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from accounts.models import Coach

print(f"{'Coach Name':<30} | {'User':<20} | {'Bank Name':<20} | {'Account No':<15}")
print("-" * 90)

for coach in Coach.objects.all():
    user_str = coach.user.username if coach.user else "No User"
    bank = coach.bank_name if coach.bank_name else "(Empty)"
    acc = coach.account_number if coach.account_number else "(Empty)"
    print(f"{coach.name:<30} | {user_str:<20} | {bank:<20} | {acc:<15}")

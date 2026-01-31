
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from accounts.models import Coach

# Create a dummy coach or get one
try:
    c = Coach.objects.first()
    if not c:
        print("No coach found, creating one.")
        from django.contrib.auth import get_user_model
        User = get_user_model()
        u = User.objects.create(username='test_fernet', email='test@example.com')
        c = Coach.objects.create(user=u, name='Test Fernet', account_number='123456', branch_code='123456')
    else:
        # Update with some values if empty
        if not c.account_number:
            c.account_number = '123456789'
            c.branch_code = '000000'
            c.save()
            c.refresh_from_db()

    print(f"Account Number Type: {type(c.account_number)}")
    print(f"Account Number Value: {c.account_number}")
    print(f"Branch Code Type: {type(c.branch_code)}")
    print(f"Branch Code Value: {c.branch_code}")
    
    # Check what happens when casting to str
    print(f"Str(Account Number): {str(c.account_number)}")

except Exception as e:
    print(f"Error: {e}")

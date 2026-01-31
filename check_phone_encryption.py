
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from accounts.models import Coach
from django.db import connection

# Check Charlie's phone
try:
    charlie = Coach.objects.get(name__iexact='charlie clanner') # Derived from check_data output
    print(f"Coach: {charlie.name}")
    print(f"Phone: '{charlie.phone}'")
    
    # Check regex validity
    import re
    regex = r'^0\d{9}$'
    if re.match(regex, charlie.phone):
        print("Phone is VALID.")
    else:
        print("Phone is INVALID (Regex mismatch).")
        
except Coach.DoesNotExist:
    print("Coach Charlie not found.")

# Verify Encryption in DB
# We know 'Form Debug Coach' has '123456'.
# Let's inspect the RAW DB value to see if it's encrypted.
print("\n--- Raw DB Value Check ---")
with connection.cursor() as cursor:
    cursor.execute("SELECT account_number FROM accounts_coach WHERE name = 'Form Debug Coach'")
    row = cursor.fetchone()
    if row:
        raw_val = row[0]
        print(f"Raw DB Encrypted Value: {raw_val}")
        print(f"Raw Length: {len(raw_val)}")
    else:
        print("Form Debug Coach not found in DB.")

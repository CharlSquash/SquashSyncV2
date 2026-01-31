
import os
import django
# from fernet_fields import EncryptedCharField # Moved down
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from fernet_fields import EncryptedCharField

f = EncryptedCharField(max_length=100)
# Mocking strict enforcement usually happens at DB level or Model clean.
# But let's check the length of the string produced.

# Simulate getting the encrypted value
# We can use the underlying fernet wrapper if possible, or just create a model instance and access the field.
# But SecureEncryptedCharField converts it back to string on access.
# We need to see what is trying to be SAVED.

from accounts.models import SecureEncryptedCharField
from django.db import connection

# Let's use the field's get_prep_value to see what goes into the DB
field = SecureEncryptedCharField(max_length=100)
plaintext = "1234567890" # 10 chars
encrypted = field.get_prep_value(plaintext)
print(f"Plaintext (10 chars): {plaintext}")
print(f"Encrypted Length: {len(encrypted)}")
print(f"Encrypted Value: {encrypted}")

plaintext_long = "12345678901234567890" # 20 chars
encrypted_long = field.get_prep_value(plaintext_long)
print(f"Plaintext (20 chars): {plaintext_long}")
print(f"Encrypted Length: {len(encrypted_long)}")

# Branch code checks
plaintext_branch = "123456" # 6 chars
encrypted_branch = field.get_prep_value(plaintext_branch)
print(f"Branch (6 chars) Encrypted Length: {len(encrypted_branch)}")



import os
import django
from django.template import Template, Context
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

# Minimal template snippet to test logic
template_code = """
{% if viewing_own_profile or user.is_superuser %}
    VISIBLE
{% else %}
    HIDDEN
{% endif %}
"""

from django.contrib.auth import get_user_model
User = get_user_model()

print("--- Test 1: Superuser ---")
admin = User(is_superuser=True, username='admin')
t = Template(template_code)
c = Context({'viewing_own_profile': False, 'user': admin})
print(t.render(c).strip())

print("--- Test 2: Owner (Not Superuser) ---")
owner = User(is_superuser=False, username='owner')
c = Context({'viewing_own_profile': True, 'user': owner})
print(t.render(c).strip())

print("--- Test 3: Other User (Not Superuser) ---")
other = User(is_superuser=False, username='other')
c = Context({'viewing_own_profile': False, 'user': other})
print(t.render(c).strip())

# Now let's try to parse the ACTUAL file
from django.template.loader import render_to_string
# We can't easily render the full template because of extends and missing context vars, 
# but we can try to render a simplified version of it or just check the file content confirms the logic.

print("--- Checking File Content ---")
with open('accounts/templates/accounts/coach_profile.html', 'r') as f:
    content = f.read()
    if 'Banking Details' in content:
        print("FOUND 'Banking Details' string in file.")
    else:
        print("NOT FOUND 'Banking Details' string in file.")
        
    start_idx = content.find('Sub-Group: Banking Details')
    if start_idx != -1:
        snippet = content[start_idx:start_idx+300]
        print(f"Snippet:\n{snippet}")

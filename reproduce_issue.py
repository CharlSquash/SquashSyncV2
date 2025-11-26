import os
import django
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

from tasks.forms import AddListWithMembersForm
from django.contrib.auth import get_user_model
import inspect

User = get_user_model()

print(f"AddListWithMembersForm: {AddListWithMembersForm}")
print(f"AddListWithMembersForm bases: {AddListWithMembersForm.__bases__}")
print(f"__init__ signature: {inspect.signature(AddListWithMembersForm.__init__)}")

# Try to instantiate it as in the view
try:
    print("Attempting: form = AddListWithMembersForm()")
    form = AddListWithMembersForm()
    print(f"Form instantiated successfully.")
    print(f"Data: {form.data}")
    print(f"Is bound: {form.is_bound}")
    
    # Check if we can access errors
    print("Accessing errors...")
    print(form.errors)
    print("Errors accessed.")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

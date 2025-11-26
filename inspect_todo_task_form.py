
import os
import django
import inspect
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

import todo.forms
import todo.views
import todo.urls

print("=== Forms in todo.forms ===")
for name, obj in inspect.getmembers(todo.forms):
    if inspect.isclass(obj) and issubclass(obj, django.forms.Form):
        print(name)

print("\n=== AddEditTaskForm Source ===")
try:
    print(inspect.getsource(todo.forms.AddEditTaskForm))
except AttributeError:
    print("AddEditTaskForm not found.")

print("\n=== list_detail View Source ===")
try:
    # Check if list_detail is a function or class
    if hasattr(todo.views, 'list_detail'):
        print(inspect.getsource(todo.views.list_detail))
    else:
        print("list_detail view not found in todo.views")
except Exception as e:
    print(f"Error inspecting list_detail: {e}")


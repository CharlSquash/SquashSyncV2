
import os
import django
import inspect
from django.conf import settings
from django.urls import get_resolver

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

import todo.forms
import todo.urls

print("=== AddEditTaskForm Source ===")
try:
    print(inspect.getsource(todo.forms.AddEditTaskForm))
except AttributeError:
    print("AddEditTaskForm not found.")

print("\n=== todo.urls Patterns ===")
try:
    for pattern in todo.urls.urlpatterns:
        print(pattern)
except Exception as e:
    print(f"Error inspecting todo.urls: {e}")

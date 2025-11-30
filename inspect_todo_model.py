import inspect
import os
import sys
import django
from django.conf import settings

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

from todo.models import TaskList

print("TaskList fields:")
for field in TaskList._meta.get_fields():
    print(f"- {field.name} ({field.__class__.__name__})")

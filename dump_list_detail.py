
import os
import django
import inspect
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

import todo.views

try:
    print(inspect.getsource(todo.views.list_detail))
except Exception as e:
    print(f"Error: {e}")

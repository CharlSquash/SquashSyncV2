
import os
import django
import inspect
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

import todo.utils

print("=== todo.utils members ===")
print(dir(todo.utils))

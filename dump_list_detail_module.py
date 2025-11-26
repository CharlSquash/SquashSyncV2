
import os
import django
import inspect
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

import todo.views.list_detail

try:
    with open("list_detail_source.py", "w") as f:
        f.write(inspect.getsource(todo.views.list_detail))
    print("Source written to list_detail_source.py")
except Exception as e:
    print(f"Error: {e}")

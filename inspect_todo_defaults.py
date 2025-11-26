import os
import django
import inspect

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

try:
    from todo.utils import defaults
    print("Source of defaults:")
    print(inspect.getsource(defaults))
except Exception as e:
    print(f"Error: {e}")

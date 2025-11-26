import os
import django
import inspect

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

try:
    from todo.views import add_list
    print("Source of add_list view:")
    print(inspect.getsource(add_list.add_list))
except Exception as e:
    print(f"Error: {e}")

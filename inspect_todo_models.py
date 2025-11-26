import os
import django
import inspect

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

try:
    from todo import models
    print("Source of TaskList model:")
    if hasattr(models, 'TaskList'):
        print(inspect.getsource(models.TaskList))
    else:
        print("TaskList not found in models")
except Exception as e:
    print(f"Error: {e}")

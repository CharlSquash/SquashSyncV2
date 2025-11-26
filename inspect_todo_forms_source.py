import os
import django
import inspect

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

try:
    from todo.forms import AddTaskListForm
    print("Source of AddTaskListForm:")
    print(inspect.getsource(AddTaskListForm))
except Exception as e:
    print(f"Error: {e}")


import os
import django
import inspect

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

import todo.forms
import inspect
print(inspect.signature(todo.forms.AddTaskListForm.__init__))


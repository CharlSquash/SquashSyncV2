
import os
import django
import inspect

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

import todo
from todo import views, models, forms

print(f"Todo package path: {os.path.dirname(todo.__file__)}")
# print("Views:", dir(views))
# print("Models:", dir(models))
# print("Forms:", dir(forms))

# Check AddList view signature or base class
if hasattr(views, 'AddList'):
    print("AddList view found")
    print(inspect.getmro(views.AddList))
else:
    print("AddList view NOT found")

# Check TaskList model
if hasattr(models, 'TaskList'):
    print("TaskList model found")
    print([f.name for f in models.TaskList._meta.get_fields()])

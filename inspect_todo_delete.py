import inspect
import os
import sys
import django
from django.conf import settings

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

try:
    from todo import views
    if hasattr(views, 'del_list'):
        print("Found del_list view.")
        print(inspect.getsource(views.del_list))
    else:
        print("del_list view not found in todo.views.")
        # List available attributes
        print("Available attributes in todo.views:", dir(views))
except Exception as e:
    print(f"Error: {e}")

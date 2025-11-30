import inspect
import os
import sys
import django
from django.conf import settings

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

from todo import utils
print(inspect.getsource(utils.staff_check))

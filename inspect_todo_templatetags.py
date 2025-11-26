import os
import django
import inspect
import pkgutil
import importlib

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coach_project.settings")
django.setup()

try:
    import todo.templatetags
    print(f"Todo templatetags path: {os.path.dirname(todo.templatetags.__file__)}")
    
    for loader, module_name, is_pkg in pkgutil.iter_modules(todo.templatetags.__path__):
        print(f"Found module: {module_name}")
        module = importlib.import_module(f"todo.templatetags.{module_name}")
        
        # Inspect functions in the module
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj):
                source = inspect.getsource(obj)
                if '.get(' in source:
                    print(f"--- Function {name} in {module_name} uses .get() ---")
                    print(source)
                    print("------------------------------------------------")

except Exception as e:
    print(f"Error: {e}")

import os
import todo
import pkgutil

print(f"Todo package path: {os.path.dirname(todo.__file__)}")

package_path = os.path.dirname(todo.__file__)
for root, dirs, files in os.walk(package_path):
    rel_path = os.path.relpath(root, package_path)
    print(f"Directory: {rel_path}")
    for f in files:
        print(f"  {f}")

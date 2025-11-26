import os
import todo

package_path = os.path.dirname(todo.__file__)
print(f"Searching in {package_path}")

for root, dirs, files in os.walk(package_path):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f):
                    if 'user.get(' in line or 'request.user.get(' in line:
                        print(f"{path}:{i+1}: {line.strip()}")

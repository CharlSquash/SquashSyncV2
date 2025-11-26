import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from django.contrib.auth.models import Group, User

def check_and_fix_groups():
    # Check if Coaches group exists
    coaches_group, created = Group.objects.get_or_create(name='Coaches')
    if created:
        print("Created 'Coaches' group.")
    else:
        print("'Coaches' group already exists.")

    # Check if admin is in the group
    try:
        admin = User.objects.get(username='admin')
        if not admin.groups.filter(name='Coaches').exists():
            admin.groups.add(coaches_group)
            print("Added 'admin' to 'Coaches' group.")
        else:
            print("'admin' is already in 'Coaches' group.")
    except User.DoesNotExist:
        print("Admin user not found.")

if __name__ == '__main__':
    check_and_fix_groups()

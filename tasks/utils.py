from django.contrib.auth.models import Group
from .models import TaskNotification

def create_admin_notifications(task, actor, notification_type):
    """
    Create TaskNotification records for all users in 'Admins' group.
    """
    try:
        admins_group = Group.objects.get(name="Admins")
        admins = admins_group.user_set.all()
    except Group.DoesNotExist:
        return

    notifications = []
    for admin in admins:
        # Don't notify the actor if they are an admin
        if admin == actor:
            continue
            
        notifications.append(TaskNotification(
            task=task,
            recipient=admin,
            actor=actor,
            notification_type=notification_type
        ))
    
    if notifications:
        TaskNotification.objects.bulk_create(notifications)

from django.db import models
from django.conf import settings
from todo.models import Task

class TaskNotification(models.Model):
    NOTIFICATION_TYPES = (
        ('comment', 'New Comment'),
        ('complete', 'Task Completed'),
    )

    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='task_notifications', on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='caused_task_notifications', on_delete=models.SET_NULL, null=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.task.title}"

from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from accounts.models import Coach
from todo.models import TaskList, Task
from django.utils import timezone
from django.utils.text import slugify
import datetime

class Command(BaseCommand):
    help = 'Populates django-todo with test data for verification'

    def handle(self, *args, **options):
        self.stdout.write("Starting setup of todo test data...")

        # 1. Prerequisites Setup
        # Ensure Site object with ID=1 exists
        site, created = Site.objects.get_or_create(id=1, defaults={'domain': 'example.com', 'name': 'example.com'})
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created Site: {site}"))
        else:
            self.stdout.write(f"Site {site} already exists.")

        # Create "Coaches" group
        coaches_group, created = Group.objects.get_or_create(name="Coaches")
        if created:
            self.stdout.write(self.style.SUCCESS('Created "Coaches" group.'))
        else:
            self.stdout.write('"Coaches" group already exists.')

        # Add all Coach users to "Coaches" group
        coaches = Coach.objects.all()
        if not coaches.exists():
            self.stdout.write(self.style.WARNING("No Coach profiles found. Please create some coaches first."))
            return

        for coach in coaches:
            if coach.user:
                coach.user.groups.add(coaches_group)
                self.stdout.write(f"Added {coach.user.username} to Coaches group.")
            else:
                self.stdout.write(self.style.WARNING(f"Coach {coach.name} has no associated user."))

        # 2. List Creation
        # Create TaskList "General Duties" assigned to "Coaches" group
        task_list, created = TaskList.objects.get_or_create(
            name="General Duties",
            defaults={
                'group': coaches_group,
                'slug': slugify("General Duties")
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created TaskList: "{task_list.name}"'))
        else:
            # Ensure it's assigned to the group if it already existed
            updated = False
            if task_list.group != coaches_group:
                task_list.group = coaches_group
                updated = True
            
            if not task_list.slug:
                task_list.slug = slugify(task_list.name)
                updated = True

            if updated:
                task_list.save()
                self.stdout.write(f'Updated TaskList "{task_list.name}" with correct group/slug.')
            else:
                self.stdout.write(f'TaskList "{task_list.name}" already exists.')

        # 3. Task Generation
        User = get_user_model()
        
        # Find a creator (superuser or first coach)
        creator = User.objects.filter(is_superuser=True).first()
        if not creator:
            creator = coaches.first().user if coaches.first() and coaches.first().user else None
        
        if not creator:
             self.stdout.write(self.style.ERROR("Could not find a valid user to be the creator of tasks."))
             return

        # Find an assignee (first coach user)
        first_coach = coaches.first()
        assignee = first_coach.user if first_coach else None

        if not assignee:
             self.stdout.write(self.style.ERROR("Could not find a valid coach user to assign tasks to."))
             return

        sample_tasks = [
            "Update membership fees",
            "Clean Court 3",
            "Submit monthly report",
            "Organize junior tournament",
            "Check equipment inventory"
        ]

        created_count = 0
        for i, title in enumerate(sample_tasks):
            # Ensure at least 3 are not completed
            is_completed = False
            if i >= 3: # The last 2 will be completed (indices 3 and 4) - wait, requirement says "Ensure at least 3 tasks are marked as completed=False"
                # So indices 0, 1, 2 are False. 3, 4 can be True.
                is_completed = True
            
            task, created = Task.objects.get_or_create(
                title=title,
                task_list=task_list,
                defaults={
                    'created_by': creator,
                    'assigned_to': assignee,
                    'completed': is_completed,
                    'priority': 1,
                }
            )
            if created:
                created_count += 1
                status = "Completed" if is_completed else "Pending"
                self.stdout.write(f'Created Task: "{title}" ({status})')

        self.stdout.write(self.style.SUCCESS(f"Successfully created {created_count} new tasks."))

        # 4. Verification Output
        self.stdout.write(self.style.SUCCESS(f"Tasks assigned to: {assignee.username} ({assignee.email})"))
        
        pending_count = Task.objects.filter(task_list=task_list, assigned_to=assignee, completed=False).count()
        self.stdout.write(self.style.SUCCESS(f"Log in as {assignee.username} to see {pending_count} pending tasks on the dashboard."))

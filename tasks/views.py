from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils.text import slugify
from django.db import IntegrityError

from todo.models import TaskList
from .forms import CustomAddEditTaskForm, AddProjectForm
from todo.utils import staff_check
from todo.models import TaskList, Task
from django.utils import timezone
from django.core.exceptions import PermissionDenied
import datetime
import os
import bleach
from django import forms
from django.conf import settings
from django.urls import reverse
from todo.defaults import defaults
from todo.features import HAS_TASK_MERGE
from todo.forms import AddEditTaskForm
from todo.models import Attachment, Comment, Task
from todo.utils import (
    send_email_to_thread_participants,
    staff_check,
    toggle_task_completed,
    user_can_read_task,
)
from .forms import CustomAddEditTaskForm
from .utils import create_admin_notifications
from .models import TaskNotification
from django.views.decorators.http import require_POST
from django.http import JsonResponse

if HAS_TASK_MERGE:
    from dal import autocomplete


def handle_add_comment(request, task):
    if not request.POST.get("add_comment"):
        return

    Comment.objects.create(
        author=request.user, task=task, body=bleach.clean(request.POST["comment-body"], strip=True)
    )

    send_email_to_thread_participants(
        task,
        request.POST["comment-body"],
        request.user,
        subject='New comment posted on task "{}"'.format(task.title),
    )

    messages.success(request, "Comment posted. Notification email sent to thread participants.")
    
    # Create dashboard notification for admins
    create_admin_notifications(task, request.user, 'comment')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_project(request):
    if request.method == "POST":
        form = AddProjectForm(request.POST)
        if form.is_valid():
            try:
                new_list = form.save(commit=False)
                
                # Get or create "Admins" group
                admins_group, created = Group.objects.get_or_create(name="Admins")
                
                # Ensure the current user (creator) is in the "Admins" group
                admins_group.user_set.add(request.user)
                
                # Assign "Admins" group to the new list
                new_list.group = admins_group
                new_list.slug = slugify(new_list.name)
                new_list.save()
                
                messages.success(request, f"Project '{new_list.name}' created and assigned to 'Admins' group.")
                return redirect("todo:list_detail", list_id=new_list.id, list_slug=new_list.slug)
                
            except IntegrityError:
                messages.error(request, "A list with this name already exists.")
    else:
        form = AddProjectForm()

    return render(request, "todo/add_project.html", {"form": form})


@login_required
@user_passes_test(staff_check)
def custom_list_detail(request, list_id=None, list_slug=None, view_completed=False):
    """Display and manage tasks in a todo list with custom form."""
    from django.http import HttpResponse
    from django.core.exceptions import PermissionDenied
    from todo.models import Task
    from todo.utils import send_notify_mail
    from .forms import CustomAddEditTaskForm
    import bleach
    
    # Defaults
    task_list = None
    form = None

    # Which tasks to show on this list view?
    if list_slug == "mine":
        tasks = Task.objects.filter(assigned_to=request.user).order_by('created_date')

    else:
        # Show a specific list, ensuring permissions.
        task_list = get_object_or_404(TaskList, id=list_id)
        # Non-superusers cannot access specific lists unless in the group
        if not request.user.is_superuser:
            if task_list.group not in request.user.groups.all():
                return redirect("todo_mine_custom")
        tasks = Task.objects.filter(task_list=task_list.id).order_by('created_date')

    # Additional filtering
    if view_completed:
        tasks = tasks.filter(completed=True)
    else:
        tasks = tasks.filter(completed=False)

    # ######################
    #  Add New Task Form
    # ######################

    if request.POST.getlist("add_edit_task"):
        if not request.user.is_superuser:
            raise PermissionDenied
        
        form = CustomAddEditTaskForm(
            request.user,
            request.POST,
            initial={"assigned_to": request.user.id, "priority": 999, "task_list": task_list},
        )

        if form.is_valid():
            assignees = form.cleaned_data.get('assignees', [])
            
            # If no assignees, we create one task with no assignee (or current user as default if logic dictates, 
            # but form defaults usually handle that. Here we assume we just create one unassigned task).
            # However, the form might still have 'assigned_to' in cleaned_data if we didn't fully rip it out?
            # Actually, we removed it from the form fields.
            
            if not assignees:
                # Create single unassigned task
                new_task = form.save(commit=False)
                new_task.created_by = request.user
                new_task.note = bleach.clean(form.cleaned_data["note"], strip=True)
                new_task.assigned_to = None 
                new_task.save()
                messages.success(request, 'New task "{t}" has been added.'.format(t=new_task.title))
                
            else:
                # Create a task for EACH assignee
                for assignee in assignees:
                    new_task = form.save(commit=False)
                    new_task.pk = None # Reset PK to ensure new instance
                    new_task.created_by = request.user
                    new_task.note = bleach.clean(form.cleaned_data["note"], strip=True)
                    new_task.assigned_to = assignee
                    new_task.save()
                    
                    # Notify logic
                    if (
                        "notify" in request.POST
                        and new_task.assigned_to
                        and new_task.assigned_to != request.user
                    ):
                        send_notify_mail(new_task)

                if len(assignees) == 1:
                     messages.success(request, 'New task "{t}" has been added.'.format(t=new_task.title))
                else:
                    messages.success(request, '{n} tasks have been added for "{t}".'.format(n=len(assignees), t=new_task.title))

            return redirect(request.path)
    else:
        # Don't allow adding new tasks on some views
        if list_slug not in ["mine", "recent-add", "recent-complete"] and request.user.is_superuser:
            form = CustomAddEditTaskForm(
                request.user,
                initial={"assigned_to": request.user.id, "priority": 999, "task_list": task_list},
            )

    context = {
        "list_id": list_id,
        "list_slug": list_slug,
        "task_list": task_list,
        "form": form,
        "tasks": tasks,
        "view_completed": view_completed,
    }

    return render(request, "todo/list_detail.html", context)


@login_required
@user_passes_test(staff_check)
def task_toggle_done(request, task_id):
    if request.method == "POST":
        task = get_object_or_404(Task, id=task_id)

        # Allow if superuser OR user in group OR user is assignee
        if not (request.user.is_superuser or request.user.is_staff or task.task_list.group in request.user.groups.all() or task.assigned_to == request.user):
            raise PermissionDenied

        task.completed = not task.completed
        if task.completed:
            task.completed_date = timezone.now()
        else:
            task.completed_date = None
            
        task.save()
        
        status_msg = "done" if task.completed else "not done"
        messages.success(request, f"Task '{task.title}' marked as {status_msg}.")

        if task.completed:
            create_admin_notifications(task, request.user, 'complete')

        if request.user.is_superuser:
            return redirect("todo:list_detail", list_id=task.task_list.id, list_slug=task.task_list.slug)
        else:
            return redirect("todo_mine_custom")
        

    else:
        raise PermissionDenied


@login_required
@user_passes_test(staff_check)
def task_detail(request, task_id: int) -> HttpResponse:
    """View task details. Allow task details to be edited. Process new comments on task.
    Custimized to allow assigned users to view task.
    """

    task = get_object_or_404(Task, pk=task_id)
    comment_list = Comment.objects.filter(task=task_id).order_by("-date")

    # Ensure user has permission to view task. Superusers can view all tasks.
    # Get the group this task belongs to, and check whether current user is a member of that group.
    
    # Custom Permission Check:
    # Allow if superuser OR user in group OR user is assignee OR user is staff
    if not (request.user.is_superuser or request.user.is_staff or task.task_list.group in request.user.groups.all() or task.assigned_to == request.user):
        raise PermissionDenied

    # Determine if user can edit the task details
    # Assignees generally can READ/COMMENT/COMPLETE but NOT EDIT task details unless they have other privileges.
    can_edit_task = request.user.is_superuser

    # Handle task merging
    if not HAS_TASK_MERGE:
        merge_form = None
    else:

        class MergeForm(forms.Form):
            merge_target = forms.ModelChoiceField(
                queryset=Task.objects.all(),
                widget=autocomplete.ModelSelect2(
                    url=reverse("todo:task_autocomplete", kwargs={"task_id": task_id})
                ),
            )

        # Handle task merging
        if not request.POST.get("merge_task_into"):
            merge_form = MergeForm()
        else:
            merge_form = MergeForm(request.POST)
            if merge_form.is_valid():
                merge_target = merge_form.cleaned_data["merge_target"]
            if not user_can_read_task(merge_target, request.user):
                raise PermissionDenied

            task.merge_into(merge_target)
            return redirect(reverse("todo:task_detail", kwargs={"task_id": merge_target.pk}))

    # Save submitted comments
    handle_add_comment(request, task)

    # Save task edits
    if not request.POST.get("add_edit_task"):
        form = CustomAddEditTaskForm(request.user, instance=task, initial={"task_list": task.task_list})
    else:
        # Only allow saving if user has edit permission
        if not can_edit_task:
            raise PermissionDenied

        form = CustomAddEditTaskForm(
            request.user, request.POST, instance=task, initial={"task_list": task.task_list}
        )

        if form.is_valid():
            # Save the primary task changes first
            item = form.save(commit=False)
            item.note = bleach.clean(form.cleaned_data["note"], strip=True)
            item.title = bleach.clean(form.cleaned_data["title"], strip=True)
            
            assignees = form.cleaned_data.get('assignees', [])
            original_assignee = task.assigned_to
            
            if assignees:
                remaining_assignees = list(assignees)
                
                # If original assignee is still in the list, keep this task for them
                if original_assignee in remaining_assignees:
                    remaining_assignees.remove(original_assignee)
                    # item.assigned_to is already set/preserved by form.save if we didn't touch it, 
                    # but CustomAddEditTaskForm removes 'assigned_to' field, so we must ensure it stays.
                    item.assigned_to = original_assignee
                else:
                    # Original assignee removed, reassign this task to the first new person
                    new_primary = remaining_assignees.pop(0)
                    item.assigned_to = new_primary

                item.save()

                # Create clones for remaining assignees
                clones_created = 0
                for assignee in remaining_assignees:
                    clone = item
                    clone.pk = None # Reset PK to create new
                    clone.assigned_to = assignee
                    clone.save()
                    clones_created += 1
                
                if clones_created > 0:
                     messages.success(request, f"The task has been edited and assigned to {item.assigned_to}. {clones_created} copies created for other assignees.")
                else:
                     messages.success(request, f"The task has been edited and assigned to {item.assigned_to}.")

            else:
                 # No assignees selected? Keep as is or handle unassignment? 
                 # Current logic usually keeps it or sets to None?
                 item.save()
                 messages.success(request, "The task has been edited.")

            return redirect(
                "todo:list_detail", list_id=task.task_list.id, list_slug=task.task_list.slug
            )

    # Mark complete
    if request.POST.get("toggle_done"):
        results_changed = toggle_task_completed(task.id)
        if results_changed:
            messages.success(request, f"Changed completion status for task {task.id}")

        return redirect("todo:task_detail", task_id=task.id)

    if task.due_date:
        thedate = task.due_date
    else:
        thedate = datetime.datetime.now()

    # Handle uploaded files
    if request.FILES.get("attachment_file_input"):
        file = request.FILES.get("attachment_file_input")

        if file.size > defaults("TODO_MAXIMUM_ATTACHMENT_SIZE"):
            messages.error(request, f"File exceeds maximum attachment size.")
            return redirect("todo:task_detail", task_id=task.id)

        name, extension = os.path.splitext(file.name)

        if extension not in defaults("TODO_LIMIT_FILE_ATTACHMENTS"):
            messages.error(request, f"This site does not allow upload of {extension} files.")
            return redirect("todo:task_detail", task_id=task.id)

        Attachment.objects.create(
            task=task, added_by=request.user, timestamp=datetime.datetime.now(), file=file
        )
        messages.success(request, f"File attached successfully")
        return redirect("todo:task_detail", task_id=task.id)

    context = {
        "task": task,
        "comment_list": comment_list,
        "form": form,
        "merge_form": merge_form,
        "thedate": thedate,
        "comment_classes": defaults("TODO_COMMENT_CLASSES"),
        "attachments_enabled": defaults("TODO_ALLOW_FILE_ATTACHMENTS"),
        "can_edit_task": can_edit_task,
    }

    return render(request, "todo/task_detail.html", context)

@login_required
@require_POST
def acknowledge_notification(request, notification_id):
    try:
        notification = TaskNotification.objects.get(id=notification_id, recipient=request.user)
        notification.read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    except TaskNotification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)


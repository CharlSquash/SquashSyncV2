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
        tasks = Task.objects.filter(assigned_to=request.user)

    else:
        # Show a specific list, ensuring permissions.
        task_list = get_object_or_404(TaskList, id=list_id)
        if task_list.group not in request.user.groups.all() and not request.user.is_superuser:
            raise PermissionDenied
        tasks = Task.objects.filter(task_list=task_list.id)

    # Additional filtering
    if view_completed:
        tasks = tasks.filter(completed=True)
    else:
        tasks = tasks.filter(completed=False)

    # ######################
    #  Add New Task Form
    # ######################

    if request.POST.getlist("add_edit_task"):
        form = CustomAddEditTaskForm(
            request.user,
            request.POST,
            initial={"assigned_to": request.user.id, "priority": 999, "task_list": task_list},
        )

        if form.is_valid():
            new_task = form.save(commit=False)
            new_task.created_by = request.user
            new_task.note = bleach.clean(form.cleaned_data["note"], strip=True)
            form.save()

            # Send email alert only if Notify checkbox is checked AND assignee is not same as the submitter
            if (
                "notify" in request.POST
                and new_task.assigned_to
                and new_task.assigned_to != request.user
            ):
                send_notify_mail(new_task)

            messages.success(request, 'New task "{t}" has been added.'.format(t=new_task.title))
            return redirect(request.path)
    else:
        # Don't allow adding new tasks on some views
        if list_slug not in ["mine", "recent-add", "recent-complete"]:
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

        return redirect("todo:list_detail", list_id=task.task_list.id, list_slug=task.task_list.slug)
        
    else:
        raise PermissionDenied

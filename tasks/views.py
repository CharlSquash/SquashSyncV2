from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils.text import slugify
from django.db import IntegrityError

from todo.models import TaskList
from .forms import AddListWithMembersForm, ManageMembersForm
from todo.utils import staff_check

@login_required
@user_passes_test(staff_check)
def add_list_with_users(request):
    if request.method == "POST":
        print(f"DEBUG: POST request to add_list_with_users. POST data: {request.POST}")
        form = AddListWithMembersForm(request.POST)
        if form.is_valid():
            try:
                new_list = form.save(commit=False)
                
                # Create a new group for this list
                group_name = f"{new_list.name} Group"
                # Ensure unique group name
                base_name = group_name
                counter = 1
                while Group.objects.filter(name=group_name).exists():
                    group_name = f"{base_name} {counter}"
                    counter += 1
                
                new_group = Group.objects.create(name=group_name)
                
                # Add selected members to the group
                members = form.cleaned_data.get('members')
                if members:
                    new_group.user_set.set(members)
                
                # Always add the creator to the group so they can see the list
                new_group.user_set.add(request.user)
                
                # Assign group to list
                new_list.group = new_group
                new_list.slug = slugify(new_list.name)
                new_list.save()
                
                messages.success(request, f"List '{new_list.name}' created with group '{new_group.name}'.")
                return redirect("todo:list_detail", list_id=new_list.id, list_slug=new_list.slug)
                
            except IntegrityError:
                messages.error(request, "A list with this name already exists.")
    else:
        print("DEBUG: GET request to add_list_with_users. Instantiating empty form.")
        form = AddListWithMembersForm(data=None)

    print(f"DEBUG: Form errors: {form.errors}")
    return render(request, "todo/add_list.html", {"form": form})

@login_required
@user_passes_test(staff_check)
def manage_list_members(request, list_id):
    task_list = get_object_or_404(TaskList, id=list_id)
    group = task_list.group
    
    if request.method == "POST":
        form = ManageMembersForm(request.POST, group=group)
        if form.is_valid():
            members = form.cleaned_data['members']
            group.user_set.set(members)
            messages.success(request, f"Members updated for list '{task_list.name}'.")
            return redirect("todo:list_detail", list_id=task_list.id, list_slug=task_list.slug)
    else:
        form = ManageMembersForm(group=group)

    return render(request, "todo/manage_members.html", {"task_list": task_list, "form": form})


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

# coach_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from scheduling.views import homepage
from tasks import views as task_views

#// solosync imports

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # THIS IS THE CRUCIAL CHANGE:
    # We now point /accounts/ to our own app's urls.py file.
    path('accounts/', include('accounts.urls')),

    #password reset
    path('accounts/', include('django.contrib.auth.urls')),

    # --- The rest of your app includes ---
    path('', homepage, name='homepage'),
    path('players/', include('players.urls')),
    path('schedule/', include('scheduling.urls')),
    path('live-session/', include('live_session.urls')),
    path('assessments/', include('assessments.urls')),
    path('finance/', include('finance.urls')),
    path('awards/', include('awards.urls')),
    path('todo/add_list/', task_views.add_project, name='add_list_custom'), # Custom add list view
    # path('todo/manage_members/<int:list_id>/', task_views.manage_list_members, name='manage_list_members'), # REMOVED
    path('todo/mine/', task_views.custom_list_detail, {'list_slug': 'mine'}, name='todo_mine_custom'),
    path('todo/mine/completed/', task_views.custom_list_detail, {'list_slug': 'mine', 'view_completed': True}, name='todo_mine_completed'),
    path('todo/<int:list_id>/<str:list_slug>/', task_views.custom_list_detail, name='todo_list_detail'),
    path('todo/<int:list_id>/<str:list_slug>/completed/', task_views.custom_list_detail, {'view_completed': True}, name='todo_list_detail_completed'),
    path('todo/toggle/<int:task_id>/', task_views.task_toggle_done, name='custom_task_toggle_done'),
    
    # Custom Task Detail to fix permissions
    path('todo/task/<int:task_id>/', task_views.task_detail, name="custom_task_detail"),
    path('todo/toggle_done/<int:task_id>/', task_views.task_toggle_done, name="custom_task_toggle_done_v2"),

    path('todo/', include('todo.urls', namespace="todo")),

    #// solosync2 urls
    path('api/solosync2/', include('solosync2.urls')),

    #// ADD THESE TWO URLS for getting and refreshing tokens
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),


    


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

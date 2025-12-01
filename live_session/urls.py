# live_session/urls.py
from django.urls import path
from . import views

app_name = 'live_session'

urlpatterns = [
    path('session/<int:session_id>/', views.live_session_display, name='live_session_display'),
    path('api/session/<int:session_id>/update/', views.live_session_update_api, name='live_session_update_api'),
    path('planner-v2/<int:session_id>/', views.experimental_planner, name='planner_v2'),
]
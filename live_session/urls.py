# live_session/urls.py
from django.urls import path
from . import views

app_name = 'live_session'

urlpatterns = [
    path('planner-v2/<int:session_id>/', views.experimental_planner, name='planner_v2'),
    path('create-custom-drill/', views.create_custom_drill, name='create_custom_drill'),
    path('add-session-note/<int:session_id>/', views.add_session_note, name='add_session_note'),
]
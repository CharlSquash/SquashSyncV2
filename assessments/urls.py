# Example for one of the new urls.py files
from django.urls import path
from . import views

app_name = 'assessments' # Replace with 'players', 'scheduling', etc.
urlpatterns = [
    # We will add our app-specific URLs here later.
    path('pending/', views.pending_assessments, name='pending_assessments'),
    path('session/<int:session_id>/assess-players/', views.assess_player_session, name='assess_player_session'),
    path('session/<int:session_id>/assess-group/', views.add_edit_group_assessment, name='add_edit_group_assessment'),
]
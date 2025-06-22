# Example for one of the new urls.py files
from django.urls import path
from . import views

app_name = 'assessments' # Replace with 'players', 'scheduling', etc.
urlpatterns = [
    # We will add our app-specific URLs here later.
    path('pending/', views.pending_assessments, name='pending_assessments'),
    path('session/<int:session_id>/player/<int:player_id>/', views.assess_player, name='assess_player'),
    path('session/<int:session_id>/assess-group/', views.add_edit_group_assessment, name='add_edit_group_assessment'),
    path('session/<int:session_id>/mark-complete/', views.mark_my_assessments_complete, name='mark_player_assessments_complete'),
]
# assessments/urls.py
from django.urls import path
from . import views

app_name = 'assessments'
urlpatterns = [
    path('pending/', views.pending_assessments, name='pending_assessments'),
    path('session/<int:session_id>/player/<int:player_id>/', views.assess_player, name='assess_player'),
    path('session/<int:session_id>/assess-group/', views.add_edit_group_assessment, name='add_edit_group_assessment'),
    path('session/<int:session_id>/mark-complete/', views.mark_my_assessments_complete, name='mark_player_assessments_complete'),
    path('assessment/<int:assessment_id>/acknowledge/', views.acknowledge_assessment, name='acknowledge_assessment'),

    # --- NEW URL ---
    path('group-assessment/<int:group_assessment_id>/acknowledge/', views.acknowledge_group_assessment, name='acknowledge_group_assessment'),

    path('session/<int:session_id>/add_match/', views.add_match_result, name='add_match_result'),
    path('match/<int:match_id>/delete/', views.delete_match_result, name='delete_match_result'),
]
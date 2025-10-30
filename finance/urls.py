from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    # URL for the coach completion report page
    path('reports/completion/', views.completion_report, name='completion_report'),
    
    # URL for the background AJAX request to confirm/un-confirm
    path('completion/<int:completion_id>/toggle-confirmation/', views.toggle_confirmation_ajax, name='toggle_confirmation_ajax'),

    # NEW: URL for the background AJAX request to update duration
    path('session-coach/<int:session_coach_id>/update-duration/', views.update_duration_ajax, name='update_duration_ajax'),

    # --- NEW URLS FOR RECURRING ADJUSTMENTS ---
    path('adjustments/manage/', views.manage_adjustment_ajax, name='add_adjustment_ajax'),
    path('adjustments/manage/<int:adj_id>/', views.manage_adjustment_ajax, name='update_adjustment_ajax'),
    path('adjustments/<int:adj_id>/toggle/', views.toggle_adjustment_ajax, name='toggle_adjustment_ajax'),
    path('adjustments/<int:adj_id>/delete/', views.delete_adjustment_ajax, name='delete_adjustment_ajax'),
]


# Example for one of the new urls.py files
from django.urls import path
from . import views

app_name = 'scheduling' # Replace with 'players', 'scheduling', etc.
urlpatterns = [
    path('calendar/', views.session_calendar, name='session_calendar'),
    # We will add our app-specific URLs here later.
    path('staffing/', views.session_staffing, name='session_staffing'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),

    path('api/session/<int:session_id>/save_plan/', views.save_session_plan, name='save_session_plan'),

    path('my-availability/', views.my_availability, name='my_availability'),
    path('session/<int:session_id>/attendance/', views.visual_attendance, name='visual_attendance'),

    path('bulk-availability/', views.set_bulk_availability_view, name='set_bulk_availability'),

    path('confirm/<int:session_id>/<str:token>/', views.confirm_attendance, name='confirm_attendance'),
    path('decline/<int:session_id>/<str:token>/', views.decline_attendance, name='decline_attendance'),

    path('player-response/<str:token>/', views.player_attendance_response, name='player_attendance_response'),

    path('api/session/<int:session_id>/update_attendance/', views.update_attendance_status, name='update_attendance_status'),
]
# Example for one of the new urls.py files
from django.urls import path
from . import views

app_name = 'scheduling' # Replace with 'players', 'scheduling', etc.
urlpatterns = [
    path('calendar/', views.session_calendar, name='session_calendar'),
    # We will add our app-specific URLs here later.
    path('staffing/', views.session_staffing, name='session_staffing'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),

    path('my-availability/', views.my_availability, name='my_availability'),
    path('session/<int:session_id>/attendance/', views.visual_attendance_view, name='visual_attendance'),

    path('bulk-availability/', views.set_bulk_availability_view, name='set_bulk_availability'),
]
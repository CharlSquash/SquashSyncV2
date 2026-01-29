# squashsyncv2/scheduling/urls.py
from django.urls import path, include
from . import views, feeds

app_name = 'scheduling'
urlpatterns = [
    path('calendar/', views.session_calendar, name='session_calendar'),
    path('staffing/', views.session_staffing, name='session_staffing'),
    path('api/assign-coaches/', views.assign_coaches_ajax, name='assign_coaches_ajax'),
    path('api/update-coach-duration/', views.update_coach_duration_ajax, name='update_coach_duration_ajax'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),
    path('api/session/<int:session_id>/save_plan/', views.save_session_plan, name='save_session_plan'),
    path('my-availability/', views.my_availability, name='my_availability'),
    path('session/<int:session_id>/attendance/', views.visual_attendance, name='visual_attendance'),
    path('bulk-availability/', views.set_bulk_availability_view, name='set_bulk_availability'),
    path('confirm/<int:session_id>/<str:token>/', views.confirm_attendance, name='confirm_attendance'),
    path('decline-with-reason/<int:session_id>/<str:token>/', views.decline_attendance_reason, name='decline_attendance_reason'),
    path('confirm-all/<str:date_str>/<str:token>/', views.confirm_all_for_day, name='confirm_all_for_day'),
    path('decline-all-with-reason/<str:date_str>/<str:token>/', views.decline_all_for_day_reason, name='decline_all_for_day_reason'),
    path('dashboard/confirm/<int:session_id>/', views.dashboard_confirm, name='dashboard_confirm'),
    path('dashboard/decline/<int:session_id>/', views.dashboard_decline, name='dashboard_decline'),
    path('player-response/<str:token>/', views.player_attendance_response, name='player_attendance_response'),
    path('api/session/<int:session_id>/update_attendance/', views.update_attendance_status, name='update_attendance_status'),
    path('api/update-event-date/', views.update_event_date, name='update_event_date'),
    path('api/delete-event/', views.delete_event, name='delete_event'),
    # Management API
    path('api/session/update/', views.update_session_ajax, name='update_session_ajax'),
    path('api/session/create/', views.create_session_ajax, name='create_session_ajax'),
    path('api/session/delete/', views.delete_session_ajax, name='delete_session_ajax'),
    # Feeds
    path('feed/calendar/<str:token>/', feeds.coach_calendar_feed, name='coach_calendar_feed'),
    path('email-preview/', views.preview_head_coach_email, name='preview_head_coach_email'),
    path('staffing-overview-modal/', views.staffing_overview_modal, name='staffing_overview_modal'),
]

# live_session/urls.py
from django.urls import path
from . import views

app_name = 'live_session'
urlpatterns = [
    # URL for the main display page
    path('<int:session_id>/', views.live_session_page_view, name='live_session_display'),

    # URL for the API that provides real-time updates
    path('api/<int:session_id>/update/', views.live_session_update_api, name='live_session_update_api'),
]
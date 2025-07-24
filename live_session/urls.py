# live_session/urls.py
from django.urls import path
from . import views

app_name = 'live_session'

urlpatterns = [
    # URL for the main display page
    path('<int:session_id>/', views.live_session_display, name='live_session_display'),

    # CORRECTED URL: The API endpoint that the JavaScript will call
    path('api/update/<int:session_id>/', views.live_session_update_api, name='live_session_update_api'),
]
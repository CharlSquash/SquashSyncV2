# accounts/urls.py
from django.urls import path, include
from . import views

app_name = 'accounts'

urlpatterns = [
    # Our custom views
    path('coaches/', views.coach_list_view, name='coach_list'),
    path('profile/', views.coach_profile_view, name='my_profile'),
    path('coaches/<int:coach_id>/', views.coach_profile_view, name='coach_profile_detail'),

    # Now, include Django's built-in authentication URLs from within our app.
    # This will handle login, logout, password resets, etc.
    path('', include('django.contrib.auth.urls')),
]
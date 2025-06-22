# accounts/urls.py
from django.urls import path, include
from . import views

app_name = 'accounts'

urlpatterns = [
    path('coaches/', views.coach_list, name='coach_list'),
    
    # e.g., /accounts/profile/ (For a coach to view their own profile)
    # This path calls the 'coach_profile' view without a coach_id.
    path('profile/', views.coach_profile, name='my_profile'),
    
    # e.g., /accounts/coaches/5/ (For an admin to view a specific coach)
    # This path is named 'coach_profile' to match the template tag.
    # It calls the same 'coach_profile' view but passes the coach_id.
    path('coaches/<int:coach_id>/', views.coach_profile, name='coach_profile'),
    # This will handle login, logout, password resets, etc.
    path('', include('django.contrib.auth.urls')),
]
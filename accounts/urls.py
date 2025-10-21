# accounts/urls.py
from django.urls import path, include
from . import views

app_name = 'accounts'

urlpatterns = [
    path('coaches/', views.coach_list, name='coach_list'),
    
    path('profile/', views.coach_profile, name='my_profile'),
    
    path('coaches/<int:coach_id>/', views.coach_profile, name='coach_profile'),

    path('accept-invitation/<uuid:token>/', views.accept_invitation, name='accept_invitation'),
    
 
]
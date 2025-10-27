from django.urls import path
from . import views

app_name = 'awards'

urlpatterns = [
    path('', views.prize_list, name='prize_list'),
    # path('prize/<int:prize_id>/nominate/', views.nominate_prize, name='nominate_prize'), # Kept commented out
    path('prize/<int:prize_id>/vote/', views.vote_prize, name='vote_prize'),
    
    # --- ADDED LINE ---
    # Add the path for confirming the winner
    path('prize/<int:prize_id>/confirm_winner/', views.confirm_winner, name='confirm_winner'),
    
    # API / AJAX
    path('api/cast_vote/<int:prize_id>/', views.cast_vote_ajax, name='cast_vote_ajax'),
]


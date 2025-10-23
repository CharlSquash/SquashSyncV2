# awards/urls.py
from django.urls import path
from . import views

app_name = 'awards'
urlpatterns = [
    path('', views.prize_list, name='prize_list'),
    path('prize/<int:prize_id>/nominate/', views.nominate_prize, name='nominate_prize'),
    path('prize/<int:prize_id>/vote/', views.vote_prize, name='vote_prize'),
    # Add this new line for the AJAX voting endpoint:
    path('api/cast_vote/', views.cast_vote_ajax, name='cast_vote_ajax'),
    path('prize/<int:prize_id>/confirm_winner/', views.confirm_winner, name='confirm_winner'),
]
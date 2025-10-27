# awards/urls.py
from django.urls import path
from . import views

app_name = 'awards'

urlpatterns = [
    # Page Views
    path('', views.prize_list, name='prize_list'),
    path('prize/<int:prize_id>/vote/', views.vote_prize, name='vote_prize'),

    # Action Endpoints (Admin/Superuser only for confirm)
    path('prize/<int:prize_id>/confirm_winner/', views.confirm_winner, name='confirm_winner'),

    # API / AJAX Endpoints (Staff/Superuser)
    path('api/cast_vote/<int:prize_id>/', views.cast_vote_ajax, name='cast_vote_ajax'),
    path('api/clear_my_votes/<int:prize_id>/', views.clear_my_votes_ajax, name='clear_my_votes_ajax'),
]

# players/urls.py
from django.urls import path
from . import views

app_name = 'players'
urlpatterns = [
    path('', views.players_list, name='players_list'),
    # We will add our app-specific URLs here later.
    path('groups/', views.school_group_list, name='school_group_list'),
    path('<int:player_id>/', views.player_profile, name='player_profile'),

    path('groups/<int:group_id>/', views.school_group_profile, name='school_group_profile'),
    path('reports/discrepancy/', views.discrepancy_report, name='discrepancy_report'),

    path('discrepancy/<int:discrepancy_id>/acknowledge/', views.acknowledge_discrepancy, name='acknowledge_discrepancy'),
]
# players/urls.py
from django.urls import path, include
from . import views
from .webhook_views import GravityFormWebhookView



app_name = 'players'
urlpatterns = [
    path('', views.players_list, name='players_list'),
    # We will add our app-specific URLs here later.

    path('groups/', views.school_group_list, name='school_group_list'),
    path('groups/manage/', views.manage_school_groups, name='manage_school_groups'), # New visual manager
    path('api/update-group-membership/', views.update_player_group_membership, name='update_player_group_membership'),

    path('<int:player_id>/', views.player_profile, name='player_profile'),
    path('player/<int:player_id>/add-metric/', views.add_metric, name='add_metric'),

    path('groups/<int:group_id>/', views.school_group_profile, name='school_group_profile'),
    path('reports/discrepancy/', views.discrepancy_report, name='discrepancy_report'),

    path('discrepancy/<int:discrepancy_id>/acknowledge/', views.acknowledge_discrepancy, name='acknowledge_discrepancy'),
    path('webhook/registration/', GravityFormWebhookView.as_view(), name='webhook_registration'),
    path('assign-group/<int:player_id>/', views.quick_assign_group, name='quick_assign_group'),

    #SoloSync path
    
]
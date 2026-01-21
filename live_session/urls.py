# live_session/urls.py
from django.urls import path
from . import views

app_name = 'live_session'

urlpatterns = [
    path('planner-v2/<int:session_id>/', views.experimental_planner, name='planner_v2'),
    path('create-custom-drill/', views.create_custom_drill, name='create_custom_drill'),
    path('add-session-note/<int:session_id>/', views.add_session_note, name='add_session_note'),
    
    # Template APIs
    path('api/templates/save/', views.save_template_api, name='save_template_api'),
    path('api/templates/list/', views.list_templates_api, name='list_templates_api'),
    path('api/templates/delete/<int:template_id>/', views.delete_template_api, name='delete_template_api'),
]
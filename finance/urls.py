from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    # URL for the coach completion report
    path('reports/completion/', views.completion_report, name='completion_report'),
    
    # Add other finance-related URLs here in the future
]

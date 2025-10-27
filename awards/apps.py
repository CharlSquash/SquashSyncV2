from django.apps import AppConfig

class AwardsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'awards'
    # Add this line to change display name and order in admin
    verbose_name = "ZZ-Awards Management"

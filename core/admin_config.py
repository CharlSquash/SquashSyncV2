from django.contrib.admin.apps import AdminConfig

class SquashSyncAdminConfig(AdminConfig):
    default_site = 'core.admin.SquashSyncAdminSite'

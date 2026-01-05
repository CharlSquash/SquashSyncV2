from django.contrib import admin

class SquashSyncAdminSite(admin.AdminSite):
    site_header = "SquashSync Administration"
    site_title = "SquashSync Portal"
    index_title = "Academy Management"

    def get_app_list(self, request):
        """
        Return a sorted list of all the installed apps that have been
        registered in this site.
        """
        app_list = super().get_app_list(request)

        # Define specific order for key apps
        app_ordering = {
            'scheduling': 1,
            'players': 2,
            'accounts': 3,
            'todo': 4,
        }

        def get_sort_key(app_dict):
            # Default to 100 for apps not specifically ordered
            return app_ordering.get(app_dict['app_label'], 100)

        app_list.sort(key=get_sort_key)
        return app_list

# Register your models here.

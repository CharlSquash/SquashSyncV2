# players/admin.py
from django.contrib import admin
from .models import (
    SchoolGroup, Player, CourtSprintRecord, VolleyRecord,
    BackwallDriveRecord, MatchResult
)

@admin.register(SchoolGroup)
class SchoolGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'contact_number', 'parent_contact_number', 'skill_level', 'is_active')
    list_filter = ('skill_level', 'is_active', 'school_groups')
    search_fields = ('first_name', 'last_name')
    filter_horizontal = ('school_groups',)

# Register the metric models so they appear in the admin
admin.site.register(CourtSprintRecord)
admin.site.register(VolleyRecord)
admin.site.register(BackwallDriveRecord)
admin.site.register(MatchResult)
# solosync2/admin.py
from django.contrib import admin
from .models import Routine, RoutineDrill, SoloSessionLog

class RoutineDrillInline(admin.TabularInline):
    """
    Allows editing Drills directly within the Routine admin page.
    """
    model = RoutineDrill
    extra = 1  # Show 1 empty slot for a new drill by default
    autocomplete_fields = ['drill'] # Makes selecting drills easier
    fields = ('order', 'drill', 'duration_minutes', 'rest_duration_seconds')

@admin.register(Routine)
class RoutineAdmin(admin.ModelAdmin):
    """
    Admin view for Routines.
    """
    list_display = ('name', 'description', 'is_active')
    inlines = [RoutineDrillInline]
    search_fields = ['name']

@admin.register(SoloSessionLog)
class SoloSessionLogAdmin(admin.ModelAdmin):
    """
    Admin view for SoloSessionLogs.
    """
    list_display = ('player', 'routine', 'completed_at', 'duration_minutes')
    list_filter = ('completed_at', 'player', 'routine')
    date_hierarchy = 'completed_at'

# Note: We don't need a separate admin for RoutineDrill because it's handled "inline" by the RoutineAdmin.
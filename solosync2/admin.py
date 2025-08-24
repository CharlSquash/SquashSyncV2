# solosync2/admin.py
from django.contrib import admin
from .models import Routine, RoutineDrill, SoloSessionLog

class RoutineDrillInline(admin.TabularInline):
    model = RoutineDrill
    extra = 1
    autocomplete_fields = ['drill']

@admin.register(Routine)
class RoutineAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    inlines = [RoutineDrillInline]

@admin.register(SoloSessionLog)
class SoloSessionLogAdmin(admin.ModelAdmin):
    list_display = ('player', 'routine', 'completed_at', 'difficulty_rating', 'likelihood_rating')
    list_filter = ('player', 'routine', 'completed_at')
    search_fields = ('player__first_name', 'player__last_name', 'routine__name', 'notes')
    readonly_fields = ('completed_at',)

    fieldsets = (
        (None, {
            'fields': ('player', 'routine', 'completed_at')
        }),
        ('Feedback', {
            'fields': ('difficulty_rating', 'likelihood_rating', 'notes')
        }),
    )
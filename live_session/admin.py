from django.contrib import admin
from .models import Drill, SessionPlan, PlanTemplate

# Register your models here.
@admin.register(Drill)
class DrillAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'default_duration')
    list_filter = ('category',)
    search_fields = ('name',)

@admin.register(SessionPlan)
class SessionPlanAdmin(admin.ModelAdmin):
    list_display = ('session', 'created_at', 'updated_at')
    list_filter = ('created_at',)

@admin.register(PlanTemplate)
class PlanTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'is_public', 'created_at')
    list_filter = ('is_public', 'created_at')
    search_fields = ('name',)

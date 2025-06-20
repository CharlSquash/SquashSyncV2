# assessments/admin.py
from django.contrib import admin
from .models import SessionAssessment, GroupAssessment, CoachFeedback

@admin.register(SessionAssessment)
class SessionAssessmentAdmin(admin.ModelAdmin):
    list_display = ('player', 'session', 'submitted_by', 'effort_rating', 'focus_rating', 'is_hidden')
    list_filter = ('session__session_date', 'player', 'submitted_by', 'is_hidden')
    search_fields = ('player__first_name', 'player__last_name', 'coach_notes')
    raw_id_fields = ('player', 'session', 'submitted_by')

@admin.register(GroupAssessment)
class GroupAssessmentAdmin(admin.ModelAdmin):
    list_display = ('session', 'assessing_coach', 'assessment_datetime')
    list_filter = ('assessment_datetime', 'assessing_coach')
    search_fields = ('general_notes',)
    raw_id_fields = ('session', 'assessing_coach')

admin.site.register(CoachFeedback)
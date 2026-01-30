# assessments/admin.py
from django.contrib import admin
from .models import SessionAssessment, GroupAssessment, CoachFeedback, AssessmentComment

@admin.register(SessionAssessment)
class SessionAssessmentAdmin(admin.ModelAdmin):
    list_display = ('player', 'session', 'submitted_by', 'effort_enthusiasm_rating', 'skill_technique_rating', 'is_hidden')
    list_filter = ('session__session_date', 'player', 'submitted_by', 'is_hidden')
    search_fields = ('player__first_name', 'player__last_name', 'coach_notes')
    raw_id_fields = ('player', 'session', 'submitted_by')

@admin.register(GroupAssessment)
class GroupAssessmentAdmin(admin.ModelAdmin):
    list_display = ('session', 'assessing_coach', 'assessment_datetime')
    list_filter = ('assessment_datetime', 'assessing_coach')
    search_fields = ('general_notes',)
    raw_id_fields = ('session', 'assessing_coach')

@admin.register(AssessmentComment)
class AssessmentCommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'created_at', 'get_assessment_type')
    list_filter = ('created_at', 'author')
    search_fields = ('comment',)
    raw_id_fields = ('author', 'session_assessment', 'group_assessment')

    def get_assessment_type(self, obj):
        if obj.session_assessment:
            return f"Player: {obj.session_assessment.player}"
        if obj.group_assessment:
            return f"Group: {obj.group_assessment.session.school_group}"
        return "N/A"
    get_assessment_type.short_description = 'Assessment'


admin.site.register(CoachFeedback)

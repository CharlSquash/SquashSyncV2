# finance/migrations/0003_add_actual_duration.py
from django.db import migrations, models

def populate_actual_duration(apps, schema_editor):
    """
    Populates the new 'actual_duration_minutes' field with a sensible default.
    """
    CoachSessionCompletion = apps.get_model('finance', 'CoachSessionCompletion')
    SessionCoach = apps.get_model('scheduling', 'SessionCoach')

    # Iterate through all completion records that need the new value
    for completion in CoachSessionCompletion.objects.filter(actual_duration_minutes__isnull=True).select_related('session', 'coach'):
        # Find the corresponding planned duration from the new SessionCoach table
        session_coach_entry = SessionCoach.objects.filter(
            session=completion.session,
            coach=completion.coach
        ).first()

        if session_coach_entry:
            completion.actual_duration_minutes = session_coach_entry.coaching_duration_minutes
        else:
            # Fallback to the session's overall planned duration if no specific entry exists
            # This handles cases where a coach might have been removed from a session after completion was logged.
            completion.actual_duration_minutes = completion.session.planned_duration_minutes
        
        completion.save(update_fields=['actual_duration_minutes'])

class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0002_initial'),
        ('scheduling', '0003_rebuild_session_coach_relation'), # This dependency is key
    ]

    operations = [
        migrations.AddField(
            model_name='coachsessioncompletion',
            name='actual_duration_minutes',
            field=models.PositiveIntegerField(
                blank=True,
                help_text="The final, confirmed duration in minutes the coach worked for this session.",
                null=True
            ),
        ),
        migrations.RunPython(populate_actual_duration, migrations.RunPython.noop),
    ]

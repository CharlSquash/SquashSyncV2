# scheduling/migrations/0003_rebuild_session_coach_relation.py
from django.db import migrations, models
import django.db.models.deletion

def transfer_coaches_to_sessioncoach(apps, schema_editor):
    """
    Copies data from the old implicit M2M table to the new explicit SessionCoach table.
    """
    Session = apps.get_model('scheduling', 'Session')
    SessionCoach = apps.get_model('scheduling', 'SessionCoach')
    
    # At this point in the migration, the old M2M field still exists, so we can query it.
    for session in Session.objects.prefetch_related('coaches_attending').all():
        for coach in session.coaches_attending.all():
            SessionCoach.objects.get_or_create(
                session=session,
                coach=coach,
                defaults={'coaching_duration_minutes': session.planned_duration_minutes}
            )

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('scheduling', '0002_alter_session_options'),
    ]

    operations = [
        # Step 1: Create the new 'through' model that will hold the duration.
        migrations.CreateModel(
            name='SessionCoach',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('coaching_duration_minutes', models.PositiveIntegerField(default=60, help_text="The coach's planned duration for this specific session.")),
                ('coach', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.coach')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheduling.session')),
            ],
            options={
                'unique_together': {('session', 'coach')},
            },
        ),

        # Step 2: A custom operation to transfer data from the old M2M table to the new one.
        migrations.RunPython(transfer_coaches_to_sessioncoach, migrations.RunPython.noop),

        # Step 3: Remove the old, simple ManyToManyField.
        migrations.RemoveField(
            model_name='session',
            name='coaches_attending',
        ),

        # Step 4: Add the ManyToManyField back, but this time pointing to our new 'through' model.
        migrations.AddField(
            model_name='session',
            name='coaches_attending',
            field=models.ManyToManyField(
                blank=True,
                related_name='coached_sessions',
                through='scheduling.SessionCoach',
                to='accounts.coach'
            ),
        ),
    ]

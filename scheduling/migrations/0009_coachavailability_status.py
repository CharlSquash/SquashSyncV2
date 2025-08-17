# scheduling/migrations/0009_coachavailability_status.py

from django.db import migrations, models

def migrate_availability_data(apps, schema_editor):
    """
    Converts data from the old `is_available` boolean field to the new `status` char field.
    """
    CoachAvailability = apps.get_model('scheduling', 'CoachAvailability')
    for record in CoachAvailability.objects.all():
        if record.is_available is True:
            if 'emergency' in (record.notes or '').lower():
                record.status = 'EMERGENCY'
            else:
                record.status = 'AVAILABLE'
        elif record.is_available is False:
            record.status = 'UNAVAILABLE'
        else: # is_available is None
            record.status = 'PENDING'
        record.save(update_fields=['status'])


def reverse_migrate_availability_data(apps, schema_editor):
    """
    Reverts data from the `status` field back to the `is_available` boolean field.
    """
    CoachAvailability = apps.get_model('scheduling', 'CoachAvailability')
    for record in CoachAvailability.objects.all():
        if record.status == 'AVAILABLE' or record.status == 'EMERGENCY':
            record.is_available = True
        elif record.status == 'UNAVAILABLE':
            record.is_available = False
        else: # PENDING
            record.is_available = None
        record.save(update_fields=['is_available'])


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0008_remove_attendancetracking_status_and_more'),
    ]

    operations = [
        # 1. Add the new 'status' field
        migrations.AddField(
            model_name='coachavailability',
            name='status',
            field=models.CharField(
                choices=[('PENDING', 'Pending'), ('AVAILABLE', 'Available'), ('UNAVAILABLE', 'Unavailable'), ('EMERGENCY', 'Emergency Only')],
                default='PENDING',
                help_text="Coach's availability status for this session.",
                max_length=12
            ),
        ),
        # 2. Run the data migration to populate the new field from the old one
        migrations.RunPython(migrate_availability_data, reverse_code=reverse_migrate_availability_data),

        # 3. Remove the old 'is_available' field
        migrations.RemoveField(
            model_name='coachavailability',
            name='is_available',
        ),
    ]

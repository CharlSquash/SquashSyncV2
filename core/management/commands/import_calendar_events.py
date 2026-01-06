import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from scheduling.models import Event

class Command(BaseCommand):
    help = 'Imports events from 2026_events.csv in project root'

    def handle(self, *args, **options):
        file_path = os.path.join(settings.BASE_DIR, '2026_events.csv')

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        # Map string types to model choices
        TYPE_MAPPING = {
            'SOCIAL': Event.EventType.SOCIAL,
            'TOURNMT': Event.EventType.TOURNAMENT,
            'SCHOOL': Event.EventType.SCHOOL,
            'CEREMONY': Event.EventType.CEREMONY,
            'MEETING': Event.EventType.MEETING,
            'WORKSHOP': Event.EventType.WORKSHOP,
            'OTHER': Event.EventType.OTHER,
        }

        created_count = 0
        updated_count = 0

        with open(file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';')
            
            for row in reader:
                date_str = row['Date']
                name = row['Event Name']
                type_str = row['Type']

                try:
                    # Parse date (assuming YYYY-MM-DD)
                    event_date = datetime.strptime(date_str, '%Y-%m-%d')
                    # Make it timezone aware (defaulting to midnight)
                    event_date = timezone.make_aware(event_date)
                    
                    event_type = TYPE_MAPPING.get(type_str, Event.EventType.OTHER)

                    # Update or Create based on Name and Date
                    event, created = Event.objects.update_or_create(
                        name=name,
                        event_date=event_date,
                        defaults={
                            'event_type': event_type,
                            'description': f"Imported from 2026 Calendar. Type: {type_str}"
                        }
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                except ValueError as e:
                    self.stdout.write(self.style.WARNING(f"Skipping row {name}: Invalid date {date_str}"))

        self.stdout.write(self.style.SUCCESS(f"Import Complete. Created: {created_count}, Updated: {updated_count}"))
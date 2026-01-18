import csv
import datetime
from django.core.management.base import BaseCommand
from scheduling.models import CoachAvailability

class Command(BaseCommand):
    help = 'Exports CoachAvailability data to a CSV file.'

    def handle(self, *args, **options):
        # Generate a filename with a timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"coach_availabilities_backup_{timestamp}.csv"

        # Define the headers for your CSV
        headers = [
            'Coach Username',
            'Coach Full Name',
            'Session Date',
            'Session Start Time',
            'School Group',
            'Venue',
            'Status',
            'Last Action',
            'Notes',
            'Updated At'
        ]

        self.stdout.write(f"Starting export to {filename}...")

        try:
            with open(filename, mode='w', newline='', encoding='utf-8') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(headers)

                # Fetch all availabilities, using select_related to minimize database queries
                availabilities = CoachAvailability.objects.select_related(
                    'coach', 
                    'session', 
                    'session__school_group', 
                    'session__venue'
                ).all()

                count = 0
                for av in availabilities:
                    # Handle potential None values safely
                    group_name = av.session.school_group.name if av.session.school_group else "No Group"
                    venue_name = av.session.venue.name if av.session.venue else "No Venue"
                    coach_full_name = f"{av.coach.first_name} {av.coach.last_name}"
                    
                    row = [
                        av.coach.username,
                        coach_full_name,
                        av.session.session_date,
                        av.session.session_start_time,
                        group_name,
                        venue_name,
                        av.get_status_display(),       # Gets the human-readable label (e.g., "Available")
                        av.get_last_action_display(),  # Gets "Confirmed" or "Declined"
                        av.notes,
                        av.status_updated_at
                    ]
                    writer.writerow(row)
                    count += 1

            self.stdout.write(self.style.SUCCESS(f"Successfully exported {count} records to {filename}"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error exporting data: {str(e)}"))

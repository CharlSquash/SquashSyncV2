from django.core.management.base import BaseCommand
from django.utils import timezone
from players.models import SchoolGroup
from scheduling.models import ScheduledClass

class Command(BaseCommand):
    help = 'Archives active SchoolGroups for a specific year and deactivates them.'

    def add_arguments(self, parser):
        parser.add_argument('year', type=int, help='The year to archive the groups for (e.g., 2024)')
        parser.add_argument('--dry-run', action='store_true', help='Simulate the archiving process without making changes')

    def handle(self, *args, **options):
        year = options['year']
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.MIGRATE_HEADING(f"Starting archiving process for year: {year}"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE: No changes will be saved."))

        # Filter for all currently active SchoolGroups
        active_groups = SchoolGroup.objects.filter(is_active=True)
        
        if not active_groups.exists():
            self.stdout.write(self.style.WARNING("No active SchoolGroups found to archive."))
            return

        for group in active_groups:
            original_name = group.name
            new_name = f"{original_name} {year}"
            
            self.stdout.write(f"Processing group: {original_name}")
            
            if not dry_run:
                # Rename and Archive
                group.name = new_name
                group.year = year
                group.is_active = False
                group.save()
                self.stdout.write(self.style.SUCCESS(f"  -> Renamed to '{new_name}', set year={year}, deactivated."))
            else:
                self.stdout.write(f"  -> [DRY RUN] Would rename to '{new_name}', set year={year}, deactivate.")

            # Deactivate linked ScheduledClass objects
            linked_classes = ScheduledClass.objects.filter(school_group=group, is_active=True)
            count = linked_classes.count()
            
            if count > 0:
                self.stdout.write(f"  -> Found {count} active ScheduledClass rules.")
                if not dry_run:
                    linked_classes.update(is_active=False)
                    self.stdout.write(self.style.SUCCESS(f"  -> Deactivated {count} linked ScheduledClass rules."))
                else:
                    self.stdout.write(f"  -> [DRY RUN] Would deactivate {count} linked ScheduledClass rules.")
            else:
                 self.stdout.write("  -> No active ScheduledClass rules found.")

        self.stdout.write(self.style.MIGRATE_HEADING("Archiving process complete."))

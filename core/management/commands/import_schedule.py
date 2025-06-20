# core/management/commands/import_schedule.py

import csv
import os
import re
from datetime import time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction

# Import models from their new app locations
from players.models import Player, SchoolGroup
from scheduling.models import ScheduledClass

# Import the utility function from its new location
from core.utils import parse_grade_from_string

class Command(BaseCommand):
    help = 'Imports player, group, and schedule data from the new, standardized CSV file format.'

    @transaction.atomic
    def handle(self, *args, **options):
        import_dir = os.path.join(settings.BASE_DIR, 'data_imports')
        if not os.path.isdir(import_dir):
            self.stdout.write(self.style.ERROR(f"Import directory not found: {import_dir}"))
            self.stdout.write(self.style.WARNING("Please create a 'data_imports' directory in your project root."))
            return

        day_mapping = {
            'Mondays.csv': 0, 'Tuesdays.csv': 1, 'Wednesdays.csv': 2,
            'Thursdays.csv': 3, 'Fridays.csv': 4,
        }

        stats = {
            'groups_created': 0, 'players_created': 0, 'players_updated': 0,
            'schedules_created': 0, 'schedules_updated': 0, 'players_added_to_groups': 0,
            'rows_skipped': 0
        }

        for file_name, day_of_week in day_mapping.items():
            file_path = os.path.join(import_dir, file_name)
            if not os.path.exists(file_path):
                continue

            self.stdout.write(f"--- Processing file: {file_name} ---")
            
            with open(file_path, mode='r', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                
                for row_num, row in enumerate(reader, start=2):
                    group_name = row.get('school_group_name', '').strip()
                    time_str = row.get('session_start_time', '').strip()
                    full_name = row.get('player_first_name', '').strip()
                    grade_str = row.get('player_grade', '').strip()

                    if not (group_name and time_str and full_name):
                        self.stdout.write(self.style.WARNING(f"  Skipping row {row_num} due to missing data."))
                        stats['rows_skipped'] += 1
                        continue

                    # --- Process School Group ---
                    school_group_obj, created = SchoolGroup.objects.get_or_create(name=group_name)
                    if created:
                        stats['groups_created'] += 1

                    # --- Process Player ---
                    name_parts = full_name.split(' ', 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
                    grade_val = parse_grade_from_string(grade_str)

                    player_obj, created = Player.objects.get_or_create(
                        first_name__iexact=first_name,
                        last_name__iexact=last_name,
                        defaults={'first_name': first_name, 'last_name': last_name, 'grade': grade_val}
                    )
                    
                    if created:
                        stats['players_created'] += 1
                    else:
                        if grade_val is not None and player_obj.grade != grade_val:
                            player_obj.grade = grade_val
                            player_obj.save()
                            stats['players_updated'] += 1
                    
                    # --- Link Player to Group ---
                    if not player_obj.school_groups.filter(pk=school_group_obj.pk).exists():
                        player_obj.school_groups.add(school_group_obj)
                        stats['players_added_to_groups'] += 1

                    # --- Process Scheduled Class ---
                    try:
                        hour, minute = map(int, time_str.split(':'))
                        start_time_obj = time(hour, minute)
                        
                        schedule, created = ScheduledClass.objects.update_or_create(
                            school_group=school_group_obj,
                            day_of_week=day_of_week,
                            start_time=start_time_obj,
                            defaults={'default_duration_minutes': 60}
                        )
                        if created:
                            stats['schedules_created'] += 1
                        else:
                            stats['schedules_updated'] += 1
                    except ValueError:
                        self.stdout.write(self.style.WARNING(f"  Skipping schedule for row {row_num} due to invalid time: '{time_str}'"))

        self.stdout.write(self.style.SUCCESS('\n--- Import Complete ---'))
        for key, value in stats.items():
            self.stdout.write(f"{key.replace('_', ' ').title()}: {value}")


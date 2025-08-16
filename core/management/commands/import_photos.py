# charlsquash/squashsyncv2/SquashSyncV2-e542b77ea8a99e1934cf4d0cfe06ed8a1fc648fc/core/management/commands/import_photos.py

import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files import File
from players.models import Player

class Command(BaseCommand):
    help = 'Imports player photos from the data_imports/player_photos directory.'

    def handle(self, *args, **options):
        # Correctly locate the photo import directory
        photo_dir = os.path.join(settings.BASE_DIR, 'data_imports', 'player_photos')

        if not os.path.isdir(photo_dir):
            self.stdout.write(self.style.ERROR(f"Photo import directory not found: {photo_dir}"))
            self.stdout.write(self.style.WARNING("Please create a 'data_imports/player_photos' directory in your project root."))
            return

        self.stdout.write(self.style.SUCCESS(f"--- Starting photo import from: {photo_dir} ---"))

        stats = {
            'photos_found': 0,
            'photos_imported': 0,
            'photos_skipped': 0,
            'unmatched_photos': []
        }

        # List all files in the directory
        for filename in os.listdir(photo_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                stats['photos_found'] += 1
                
                # Parse the name from the filename
                name_part = os.path.splitext(filename)[0]
                # Replace underscores or hyphens with a space
                name_part = re.sub(r'[_|-]', ' ', name_part)
                name_parts = name_part.split(' ', 1)

                if len(name_parts) < 2:
                    stats['unmatched_photos'].append(filename)
                    continue

                first_name, last_name = name_parts
                
                # Try to find a matching player
                try:
                    player_to_update = Player.objects.get(
                        first_name__iexact=first_name,
                        last_name__iexact=last_name
                    )

                    # Check if the player already has a photo
                    if player_to_update.photo:
                        self.stdout.write(self.style.WARNING(f"  Skipping '{filename}': Player {player_to_update.full_name} already has a photo."))
                        stats['photos_skipped'] += 1
                        continue

                    # Assign the photo to the player
                    photo_path = os.path.join(photo_dir, filename)
                    with open(photo_path, 'rb') as f:
                        player_to_update.photo.save(filename, File(f), save=True)
                    
                    self.stdout.write(self.style.SUCCESS(f"  Successfully imported photo for {player_to_update.full_name}."))
                    stats['photos_imported'] += 1

                except Player.DoesNotExist:
                    stats['unmatched_photos'].append(filename)
                except Player.MultipleObjectsReturned:
                    self.stdout.write(self.style.ERROR(f"  Could not import '{filename}': Multiple players found for '{first_name} {last_name}'."))
                    stats['unmatched_photos'].append(filename)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  An unexpected error occurred for '{filename}': {e}"))
                    stats['unmatched_photos'].append(filename)


        self.stdout.write(self.style.SUCCESS('\n--- Photo Import Complete ---'))
        self.stdout.write(f"Photos Found: {stats['photos_found']}")
        self.stdout.write(f"Successfully Imported: {stats['photos_imported']}")
        self.stdout.write(f"Skipped (already have photo): {stats['photos_skipped']}")
        
        if stats['unmatched_photos']:
            self.stdout.write(self.style.WARNING("\n--- Unmatched Photos ---"))
            for name in stats['unmatched_photos']:
                self.stdout.write(f"  - {name}")
        else:
            self.stdout.write(self.style.SUCCESS("\nAll photos were successfully matched!"))
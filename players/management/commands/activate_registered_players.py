import csv
import io
import re
from rapidfuzz import fuzz
from django.core.management.base import BaseCommand
from django.db import transaction
from players.models import Player, SchoolGroup

class Command(BaseCommand):
    help = 'Activates registered players from a CSV file and updates their information.'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file', 
            nargs='?', 
            default='registrations.csv', 
            type=str, 
            help='Path to the CSV file (defaults to "registrations.csv" in root).'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the script without making changes to the database.',
        )

    def normalize_phone(self, phone):
        if not phone:
            return ''
        # Remove non-digits
        digits = re.sub(r'\D', '', str(phone))
        # Handle SA numbers (start with 0 -> 27)
        if digits.startswith('0') and len(digits) == 10:
            return '27' + digits[1:]
        # Handle already 27...
        if digits.startswith('27') and len(digits) == 11:
            return digits
        return digits

    def parse_name(self, full_name):
        """
        Splits a full name string into first_name and last_name.
        Assumes the last word is the surname if multiple words exist.
        """
        full_name = full_name.strip()
        if not full_name:
            return '', ''
        
        parts = full_name.rsplit(' ', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return full_name, '' # Only one name provided

    def extract_row_data(self, row):
        """
        Normalizes row data from the CSV into a standard dictionary.
        """
        name_field = row.get('Name and Surname of Player', '')
        first_name, last_name = self.parse_name(name_field)

        return {
            'first_name': first_name,
            'last_name': last_name,
            'email': row.get('Parent/Guardian 1 Email', '').strip().lower(),
            'contact_1': self.normalize_phone(row.get('Parent/Guardian 1 cell phone', '')),
            'contact_2': self.normalize_phone(row.get('Player Cell Phone', '')),
            'grade_raw': row.get('Grade in 2026', ''),
            'school': row.get('School', ''), # Assuming School column still exists or is not in mapping list provided but good to keep safe default
            'guardian_2_name': row.get('Guardian 2 Name', ''), # Not in new mapping, keeping safe default
            'guardian_2_contact': row.get('Guardian 2 Contact Number', ''), # Not in new mapping
            'guardian_2_email': row.get('Guardian 2 Email', ''), # Not in new mapping
            'medical_aid': row.get('Medical aid number', ''),
            'health_info': row.get('Illnesses and/or allergies', ''),
            'gender_raw': row.get('Gender', '') # Not specified in mapping, assuming might be there or defaults
        }

    def find_match(self, data, all_players):
        """
        Attempts to find a matching player using multi-step verification.
        Returns: (match_type, player, score)
        match_type: 'EMAIL', 'PHONE', 'FUZZY', or None
        """
        email = data['email']
        contact_1 = data['contact_1']
        contact_2 = data['contact_2']
        
        full_name = f"{data['first_name']} {data['last_name']}".lower().strip()

        # Step 1: Email Match with Name Verification
        if email:
            for player in all_players:
                if player.parent_email and player.parent_email.strip().lower() == email:
                    # Verify Name Similarity to avoid merging siblings
                    player_full_name = f"{player.first_name} {player.last_name}".lower()
                    name_score = fuzz.token_sort_ratio(full_name, player_full_name)
                    
                    if name_score > 75:
                        return 'EMAIL', player, name_score
                    else:
                        self.stdout.write(f"  [INFO] Found matching email for '{full_name}' but name mismatch with '{player.full_name}' (Score: {name_score}). Treating as different player.")

        # Step 2: Phone Match with Name Verification
        phone_contacts = [c for c in [contact_1, contact_2] if c]
        
        if phone_contacts:
            for player in all_players:
                p_parent_contact = self.normalize_phone(player.parent_contact_number)
                p_contact = self.normalize_phone(player.contact_number)
                
                for search_num in phone_contacts:
                    if (p_parent_contact and search_num == p_parent_contact) or \
                       (p_contact and search_num == p_contact):
                        
                        # Verify Name Similarity
                        player_full_name = f"{player.first_name} {player.last_name}".lower()
                        name_score = fuzz.token_sort_ratio(full_name, player_full_name)
                        
                        if name_score > 75:
                            return 'PHONE', player, name_score

        # Step 3: Fuzzy Name Match
        best_match = None
        best_score = 0
        
        for player in all_players:
            player_full_name = f"{player.first_name} {player.last_name}".lower()
            ratio = fuzz.ratio(full_name, player_full_name)
            
            if ratio > best_score:
                best_score = ratio
                best_match = player

        if best_score >= 90:
            return 'FUZZY', best_match, best_score
        
        return None, None, 0

    def clean_grade(self, grade_str):
        if not grade_str:
            return None
        grade_str = str(grade_str).lower().strip()
        
        # Extract number if present
        match = re.search(r'\d+', grade_str)
        if match:
            grade_num = int(match.group())
            if 1 <= grade_num <= 12:
                return grade_num
        
        if 'r' in grade_str:
            return 0 # Grade R
        if 'matric' in grade_str:
            return 12
            
        return 99 # Other

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING("--- DRY RUN MODE: No changes will be saved ---"))

        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as f:
                # UPDATED: using semicolon delimiter
                reader = csv.DictReader(f, delimiter=';')
                rows = list(reader)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error reading CSV file: {e}"))
            return

        all_players = list(Player.objects.all())
        players_to_activate_ids = set()
        
        stats = {'updated': 0, 'created': 0, 'new_matches': 0, 'warnings': 0}

        for row in rows:
            data = self.extract_row_data(row)
            
            if not data['first_name'] and not data['last_name']:
                self.stdout.write(self.style.WARNING(f"Skipping row with missing name: {row}"))
                continue

            match_type, player, score = self.find_match(data, all_players)

            if player:
                players_to_activate_ids.add(player.id)
                status_msg = f"CONFIRMED ({match_type} match)"
                if match_type == 'FUZZY':
                    status_msg += f" (Score: {score})"
                    
                self.stdout.write(f"[{status_msg}] {data['first_name']} {data['last_name']} -> {player.full_name} (ID: {player.id})")
                
                if not dry_run:
                    self.update_player(player, data)
                    stats['updated'] += 1
            else:
                self.stdout.write(self.style.SUCCESS(f"[NEW] Creating new player: {data['first_name']} {data['last_name']}"))
                if not dry_run:
                    self.create_player(data)
                    stats['created'] += 1

        # Deactivation Logic
        if not dry_run:
            players_to_deactivate = Player.objects.exclude(id__in=players_to_activate_ids).filter(is_active=True)
            count = players_to_deactivate.count()
            players_to_deactivate.update(is_active=False)
            self.stdout.write(self.style.WARNING(f"Deactivated {count} players not in the CSV."))
        else:
            # In dry run, calculation finding
            active_ids = {p.id for p in all_players if p.is_active}
            deactivate_count = len(active_ids - players_to_activate_ids)
            self.stdout.write(self.style.WARNING(f"[DRY RUN] Would deactivate {deactivate_count} players."))

        self.stdout.write(self.style.SUCCESS(f"Done! Updated: {stats['updated']}, Created: {stats['created']}"))

    def update_player(self, player, data):
        player.grade = self.clean_grade(data['grade_raw'])
        player.school = data['school']
        player.parent_email = data['email']
        player.parent_contact_number = data['contact_1']
        player.contact_number = data['contact_2']
        
        # Sec Guardian (Fields not in mapped list, keeping generic from previous extraction)
        # player.guardian_2_name = data['guardian_2_name']
        # player.guardian_2_contact_number = data['guardian_2_contact']
        # player.guardian_2_email = data['guardian_2_email']
        
        # Medical
        player.medical_aid_number = data['medical_aid']
        player.health_information = data['health_info']

        # Gender
        # gender_raw = data['gender_raw'].strip().lower()
        # if gender_raw.startswith('m'):
        #     player.gender = 'M'
        # elif gender_raw.startswith('f'):
        #     player.gender = 'F'
        
        player.is_active = True
        
        # Update names if they were blank (e.g. creating new player)
        # Note: We generally don't overwrite names for existing players to avoid overwriting preferred spellings,
        # but for new players we must set them.
        if not player.id: 
            player.first_name = data['first_name']
            player.last_name = data['last_name']

        player.save()

    def create_player(self, data):
        # Basic creation
        p = Player(
            first_name=data['first_name'],
            last_name=data['last_name'],
            is_active=True
        )
        self.update_player(p, data) # Reuse update logic to set fields and save

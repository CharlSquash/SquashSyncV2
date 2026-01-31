import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from scheduling.models import Session
from scheduling.notifications import build_player_attendance_email
from django.db.models import Q
from django.core.mail import get_connection
import time

class Command(BaseCommand):
    help = 'Sends attendance reminder emails to parents for sessions occurring today and tomorrow.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the command without actually sending emails. Lists who would receive them.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)
        
        mode_str = "[DRY RUN] " if dry_run else ""
        self.stdout.write(f"{mode_str}[{now:%Y-%m-%d %H:%M}] --- Starting player attendance reminders for {today:%Y-%m-%d} and {tomorrow:%Y-%m-%d} ---")

        # Query for sessions happening today from the current time onwards, OR any time tomorrow.
        sessions_to_notify = Session.objects.filter(
            Q(
                session_date=today,
                session_start_time__gte=now.time()
            ) | 
            Q(
                session_date=tomorrow
            ),
            is_cancelled=False
        ).select_related('school_group').prefetch_related('school_group__players')

        if not sessions_to_notify.exists():
            self.stdout.write(self.style.SUCCESS(f"{mode_str}No upcoming sessions for today or tomorrow. Exiting."))
            return

        sent_count = 0
        total_players = 0
        messages = []

        # Open a single persistent connection
        with get_connection() as connection:
            for session in sessions_to_notify:
                if not session.school_group:
                    continue

                self.stdout.write(f"Processing session: {session} for group '{session.school_group.name}'...")
                
                # STRICTLY filter only players with a set notification_email
                players_to_notify = session.school_group.players.filter(
                    is_active=True,
                    notification_email__isnull=False
                ).exclude(notification_email='')

                for player in players_to_notify:
                    total_players += 1
                    
                    if dry_run:
                        self.stdout.write(f"  [DRY RUN] Would send to: {player.full_name} <{player.notification_email}>")
                        sent_count += 1
                    else:
                        email_msg = build_player_attendance_email(player, session)
                        if email_msg:
                            messages.append(email_msg)
                            
                            # Batch send if we have enough messages
                            if len(messages) >= 20:
                                count = connection.send_messages(messages)
                                sent_count += count
                                messages = [] # Clear the list
                                self.stdout.write(f"  Sent batch of {count} emails. Sleeping...")
                                time.sleep(1) # Rate limiting
            
            # Send any remaining messages
            if messages and not dry_run:
                count = connection.send_messages(messages)
                sent_count += count
                self.stdout.write(f"  Sent final batch of {count} emails.")
                
        self.stdout.write(self.style.SUCCESS(f"--- {mode_str}Process Complete ---"))
        action_verb = "would be sent" if dry_run else "sent"
        self.stdout.write(f"Processed {total_players} verified players. Emails {action_verb}: {sent_count}.")
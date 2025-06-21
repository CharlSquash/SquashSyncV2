# In squashsync_v2/scheduling/management/commands/send_player_reminders.py

import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from scheduling.models import Session
from scheduling.notifications import send_player_attendance_email

class Command(BaseCommand):
    help = 'Sends attendance reminder emails to parents for sessions occurring the next day.'

    def handle(self, *args, **options):
        tomorrow = timezone.now().date() + datetime.timedelta(days=1)
        self.stdout.write(f"[{timezone.now():%Y-%m-%d %H:%M}] --- Starting player attendance reminders for {tomorrow:%Y-%m-%d} ---")

        sessions_for_tomorrow = Session.objects.filter(
            session_date=tomorrow,
            is_cancelled=False
        ).select_related('school_group').prefetch_related('school_group__players')

        if not sessions_for_tomorrow.exists():
            self.stdout.write(self.style.SUCCESS("No sessions for tomorrow. Exiting."))
            return

        sent_count = 0
        total_players = 0

        for session in sessions_for_tomorrow:
            if not session.school_group:
                continue

            self.stdout.write(f"Processing session: {session} for group '{session.school_group.name}'...")
            
            players_to_notify = session.school_group.players.filter(is_active=True)

            for player in players_to_notify:
                total_players += 1
                if send_player_attendance_email(player, session):
                    sent_count += 1
        
        self.stdout.write(self.style.SUCCESS(f"--- Process Complete ---"))
        self.stdout.write(f"Processed {total_players} players and sent {sent_count} emails.")
# In squashsync_v2/scheduling/management/commands/send_player_reminders.py

import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from scheduling.models import Session
from scheduling.notifications import send_player_attendance_email
from django.db.models import Q

class Command(BaseCommand):
    help = 'Sends attendance reminder emails to parents for sessions occurring today and tomorrow.'

    def handle(self, *args, **options):
        now = timezone.now()
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)
        
        self.stdout.write(f"[{now:%Y-%m-%d %H:%M}] --- Starting player attendance reminders for {today:%Y-%m-%d} and {tomorrow:%Y-%m-%d} ---")

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
            self.stdout.write(self.style.SUCCESS("No upcoming sessions for today or tomorrow. Exiting."))
            return

        sent_count = 0
        total_players = 0

        for session in sessions_to_notify:
            if not session.school_group:
                continue

            self.stdout.write(f"Processing session: {session} for group '{session.school_group.name}'...")
            
            players_to_notify = session.school_group.players.filter(
                is_active=True,
                notification_email__isnull=False
            ).exclude(notification_email='')

            for player in players_to_notify:
                total_players += 1
                if send_player_attendance_email(player, session):
                    sent_count += 1
        
        self.stdout.write(self.style.SUCCESS(f"--- Process Complete ---"))
        self.stdout.write(f"Processed {total_players} players and sent {sent_count} emails.")
# core/management/commands/send_session_reminders.py

import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from collections import defaultdict

from scheduling.models import Session, CoachAvailability
from scheduling.notifications import send_consolidated_session_reminder_email
from accounts.models import Coach

class Command(BaseCommand):
    help = 'Sends consolidated attendance reminder emails to coaches for sessions occurring today and the next day.'

    def handle(self, *args, **options):
        now = timezone.now()
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)
        
        self.stdout.write(f"[{now:%Y-%m-%d %H:%M}] Running send_session_reminders for sessions on: {today} and {tomorrow}")

        # Query for sessions happening today from the current time onwards, OR any time tomorrow.
        sessions_to_notify_qs = Session.objects.filter(
            Q(
                session_date=today,
                session_start_time__gte=now.time()
            ) | 
            Q(
                session_date=tomorrow
            ),
            is_cancelled=False
        ).prefetch_related('coaches_attending__user')

        # Group sessions by coach
        sessions_by_coach = defaultdict(list)
        for session in sessions_to_notify_qs:
            for coach_profile in session.coaches_attending.all():
                if coach_profile.user:
                    sessions_by_coach[coach_profile.user].append(session)
        
        if not sessions_by_coach:
            self.stdout.write(self.style.SUCCESS("No upcoming sessions with assigned coaches found. Exiting."))
            return

        sent_count = 0
        for coach_user, sessions in sessions_by_coach.items():
            
            # Check if the coach has ALREADY explicitly confirmed or declined ALL their sessions for the period
            unresponded_sessions = []
            for session in sessions:
                 if not CoachAvailability.objects.filter(
                    coach=coach_user,
                    session=session,
                    last_action__in=['CONFIRM', 'DECLINE']
                ).exists():
                    unresponded_sessions.append(session)
            
            if not unresponded_sessions:
                self.stdout.write(f"  Skipping email for {coach_user.username}, all sessions already responded to.")
                continue

            # Group unresponded sessions by day
            sessions_by_day = defaultdict(list)
            for session in unresponded_sessions:
                sessions_by_day[session.session_date].append(session)

            if send_consolidated_session_reminder_email(coach_user, sessions_by_day, is_reminder=True):
                sent_count += 1
        
        self.stdout.write(self.style.SUCCESS(f"--- Process Complete ---"))
        self.stdout.write(f"Sent {sent_count} consolidated reminder emails.")

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

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Send all generated emails to this address instead of the actual coaches for testing.',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)
        test_email = options['email']
        
        if test_email:
            self.stdout.write(self.style.WARNING(f"--- RUNNING IN TEST MODE ---"))
            self.stdout.write(self.style.WARNING(f"All emails will be sent to: {test_email}"))
        
        self.stdout.write(f"[{now:%Y-%m-%d %H:%M}] Running send_session_reminders for sessions on: {today} and {tomorrow}")

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

            sessions_by_day = defaultdict(list)
            for session in unresponded_sessions:
                sessions_by_day[session.session_date].append(session)

            # Override the recipient if in test mode
            original_email = coach_user.email
            if test_email:
                coach_user.email = test_email

            if send_consolidated_session_reminder_email(coach_user, sessions_by_day, is_reminder=True):
                sent_count += 1
            
            # IMPORTANT: Restore the original email after sending
            if test_email:
                coach_user.email = original_email
        
        self.stdout.write(self.style.SUCCESS(f"--- Process Complete ---"))
        self.stdout.write(f"Sent {sent_count} consolidated reminder emails.")


# core/management/commands/send_session_reminders.py

import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from scheduling.models import Session, CoachAvailability
from scheduling.notifications import send_session_confirmation_email
from accounts.models import Coach

class Command(BaseCommand):
    help = 'Sends session confirmation email reminders to coaches for sessions occurring today and the next day.'

    def handle(self, *args, **options):
        now = timezone.now()
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)
        
        self.stdout.write(f"[{now:%Y-%m-%d %H:%M}] Running send_session_reminders for sessions on: {today} and {tomorrow}")

        # --- THIS IS THE FIX ---
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
        ).prefetch_related('coaches_attending__user')

        if not sessions_to_notify.exists():
            self.stdout.write(self.style.SUCCESS("No upcoming sessions for today or tomorrow."))
            return

        sent_count = 0
        for session in sessions_to_notify:
            for coach_profile in session.coaches_attending.all():
                coach_user = coach_profile.user
                if not coach_user or not coach_user.email:
                    continue

                # Check if the coach has ALREADY explicitly confirmed or declined
                already_responded = CoachAvailability.objects.filter(
                    coach=coach_user,
                    session=session,
                    last_action__in=['CONFIRM', 'DECLINE']
                ).exists()

                if not already_responded:
                    if send_session_confirmation_email(coach_user, session, is_reminder=True):
                        sent_count += 1
        
        self.stdout.write(self.style.SUCCESS(f"Finished. Sent {sent_count} notification emails."))
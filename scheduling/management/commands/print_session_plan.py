import json
from django.core.management.base import BaseCommand, CommandError
from scheduling.models import Session

class Command(BaseCommand):
    help = 'Prints the JSON plan for a specific session ID.'

    def add_arguments(self, parser):
        parser.add_argument('session_id', type=int, help='The ID of the session to inspect.')

    def handle(self, *args, **options):
        session_id = options['session_id']
        try:
            session = Session.objects.get(pk=session_id)
            self.stdout.write(self.style.SUCCESS(f"--- Plan for Session ID: {session_id} ---"))
            
            if session.plan:
                # Pretty-print the JSON to make it readable
                plan_data = session.plan if isinstance(session.plan, dict) else json.loads(session.plan)
                self.stdout.write(json.dumps(plan_data, indent=2))
            else:
                self.stdout.write(self.style.WARNING("This session has no plan data."))

        except Session.DoesNotExist:
            raise CommandError(f'Session with ID "{session_id}" does not exist.')
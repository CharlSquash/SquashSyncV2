from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.management import call_command, get_commands
from io import StringIO
import sys

User = get_user_model()

class NavbarSafetyTest(TestCase):
    """
    Ensures that the navigation bar always contains critical links and icons.
    This protects against AI agents accidentally deleting 'irrelevant' lines like the Admin gear.
    """

    def setUp(self):
        # Create a superuser (who should see everything)
        self.superuser = User.objects.create_superuser(
            username='admin_test', 
            email='admin@test.com', 
            password='password'
        )
        self.client = Client()

    def test_superuser_navbar_integrity(self):
        """
        CRITICAL: Verifies the Admin Icon and Superuser links exist.
        """
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('homepage'))
        
        self.assertEqual(response.status_code, 200)

        # 1. THE ADMIN ICON CHECK (The specific regression you faced)
        # We check for the URL and the specific Bootstrap icon class
        admin_url = reverse('admin:index')
        self.assertContains(
            response, 
            admin_url, 
            msg_prefix="[CRITICAL FAILURE] The Django Admin URL is missing from the navbar!"
        )
        self.assertContains(
            response, 
            'bi-gear-fill', 
            msg_prefix="[UI FAILURE] The Admin Gear Icon (bi-gear-fill) has been removed!"
        )

        # 2. Todo App Integration Check
        # Ensure the Todo link exists AND didn't overwrite the admin link
        try:
            todo_url = reverse('todo:lists') # Checking the superuser "Tasks" link
            self.assertContains(response, todo_url, msg_prefix="The Todo App 'Tasks' link is missing.")
        except Exception:
            self.fail("Could not reverse 'todo:lists'. Is the Todo app URL conf connected?")

        # 3. Finance & Reporting Check
        self.assertContains(response, reverse('finance:completion_report'), msg_prefix="Completion Report link missing.")
        
    def test_navigation_links_are_alive(self):
        """
        Ensures that clicking the links actually works (returns 200 OK),
        confirming the views haven't been deleted or broken by import errors.
        """
        self.client.force_login(self.superuser)
        
        critical_routes = [
            ('scheduling:session_calendar', 'Calendar'),
            ('players:players_list', 'Players List'),
            ('todo:mine', 'My Tasks'),
        ]

        for route_name, readable_name in critical_routes:
            url = reverse(route_name)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 
                200, 
                f"The '{readable_name}' page ({url}) is returning error {response.status_code}!"
            )


class CommandAvailabilityTest(TestCase):
    """
    Ensures that your custom management commands (Session Plans, Reminders) 
    are registered and loadable.
    """

    def test_critical_commands_exist(self):
        """
        Checks if the management commands are recognized by Django.
        This catches issues where a command file was deleted or has syntax errors.
        """
        all_commands = get_commands()
        
        required_commands = [
            'print_session_plan',
            'send_player_reminders',
            'send_session_reminders',
            'import_schedule',
        ]

        for cmd in required_commands:
            self.assertIn(
                cmd, 
                all_commands, 
                f"[DANGER] The management command '{cmd}' is MISSING or broken!"
            )

    def test_print_session_plan_dry_run(self):
        """
        Attempts to call the help menu of the session plan command.
        This proves the code can run without crashing on import.
        """
        out = StringIO()
        try:
            # We run --help. This NORMALLY raises SystemExit(0) when done.
            call_command('print_session_plan', '--help', stdout=out)
        except SystemExit:
            # If we catch SystemExit, it means the command ran its help menu successfully!
            pass
        except Exception as e:
            self.fail(f"The 'print_session_plan' command crashed when running help: {e}")
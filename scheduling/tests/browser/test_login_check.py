import pytest
from playwright.sync_api import Page, expect

from scheduling.tests.browser.browser_utils import login_user

# Mark as a django_db test so we can access database if needed (though we are logging in as existing admin mostly)
# If using existing server (LiveserverTestCase style), we might need different setup. 
# But assuming standard pytest-django or pytest-playwright flow where we might need to recreate user if transactional.
# However, the user provided a specific hardcoded admin password, implying it's a persistent DB or pre-seeded.
# We'll use the credentials provided in the prompt.

@pytest.mark.django_db
def test_login_successful(page: Page, live_server):
    """
    Test that the robust login helper works.
    User provided credentials: admin / Dudi7771996
    """
    from django.contrib.auth.models import User
    # Verify user exists or create for test (best practice is to ensure it exists)
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@example.com", "Dudi7771996")
    
    # Use the live_server.url from pytest-django
    login_user(page, live_server.url, username="admin", password="Dudi7771996")

    # Double check we are on dashboard
    # live_session/templates/live_session/home.html or similar usually title "Dashboard" or "SquashSync"
    expect(page).to_have_title("Dashboard - SquashSync")

from playwright.sync_api import Page, expect

def login_user(page: Page, base_url: str, username: str = "admin", password: str = "Dudi7771996"):
    """
    Robust login function for SquashSync.
    Waits for elements, fills credentials, and ensures successful redirect.
    """
    login_url = f"{base_url}/accounts/login/"
    page.goto(login_url)

    # Wait for the login form to be visible to ensure we aren't seeing a fast failure page
    page.wait_for_selector('input[name="username"]', state="visible")

    # Explicitly clear and fill - helps if browser has cached values interacting weirdly
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)

    # Click login
    page.click('button[type="submit"]')

    # Wait for a unique element on the dashboard/home page to verify login.
    # We'll check for the "Logout" button or link commonly found in the navbar.
    # Adjust selector if your specific navbar is different (e.g. text="Logout")
    # Using a generic text locator is often robust for Django admin/standard auth templates.
    # We can also wait for url to not be login
    
    # Expect URL to change from login
    expect(page).not_to_have_url(login_url)
    
    # Optional: wait for something that confirms dashboard loaded
    # page.wait_for_selector(".dashboard-container", timeout=10000) 

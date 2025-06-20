# scheduling/notifications.py

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.core.signing import Signer, BadSignature, SignatureExpired
from datetime import timedelta

# Create a signer for generating secure tokens
signer = Signer()

def create_confirmation_token(user_id, session_id):
    """Creates a signed, timestamped token for a user and session."""
    value = f"{user_id}:{session_id}"
    return signer.sign(value)

def verify_confirmation_token(token, max_age_days=7):
    """Verifies a token. Returns the original value or None if invalid/expired."""
    try:
        # max_age is in seconds
        original_value = signer.unsign(token, max_age=timedelta(days=max_age_days).total_seconds())
        return original_value
    except (BadSignature, SignatureExpired):
        return None

def send_session_confirmation_email(user, session):
    """Sends a confirmation email to a coach for a specific session."""

    # Create unique tokens for confirm and decline actions
    confirm_token = create_confirmation_token(user.id, session.id)
    decline_token = create_confirmation_token(user.id, session.id) # Can use the same token logic

    # Build absolute URLs for the email links
    confirm_url = settings.APP_SITE_URL + reverse('scheduling:confirm_attendance', args=[session.id, confirm_token])
    decline_url = settings.APP_SITE_URL + reverse('scheduling:decline_attendance', args=[session.id, decline_token])

    context = {
        'user': user,
        'session': session,
        'confirm_url': confirm_url,
        'decline_url': decline_url,
    }

    subject = f"Please Confirm Attendance: Squash Session on {session.session_date.strftime('%a, %d %b')}"
    html_message = render_to_string('scheduling/emails/session_confirmation_email.html', context)

    send_mail(
        subject=subject,
        message='', # Plain text version can be left blank if sending HTML
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False
    )

import os
import django
import sys
from django.utils import timezone
import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from scheduling.models import Session, ScheduledClass

def check_january_sessions():
    now = timezone.now()
    january_start = datetime.date(2026, 1, 1)
    january_end = datetime.date(2026, 1, 31)

    print(f"Checking sessions between {january_start} and {january_end}...")

    sessions = Session.objects.filter(
        session_date__gte=january_start,
        session_date__lte=january_end
    )


    from scheduling.models import CoachAvailability


    

    # Replicate View Logic exactly
    today = timezone.now().date()
    print(f"DEBUG: today={today}")
    
    this_month_start = today.replace(day=1)
    print(f"DEBUG: this_month_start={this_month_start}")
    
    print("Executing exact view query for Current Month...")
    sessions_exist_current_month = Session.objects.filter(
        session_date__year=this_month_start.year,
        session_date__month=this_month_start.month,
        generated_from_rule__isnull=False,
        is_cancelled=False
    ).exists()
    
    print(f"RESULT: sessions_exist_current_month = {sessions_exist_current_month}")


    # Verify New Logic
    print("\n--- Verifying NEW Logic ---")
    
    # 1. Get a coach user
    from django.contrib.auth import get_user_model
    User = get_user_model()
    # Try to find a user who is a coach (has coach_profile)
    coach_user = User.objects.filter(coach_profile__isnull=False).first()
    
    if not coach_user:
        print("No coach user found to test with.")
    else:
        print(f"Testing with coach user: {coach_user.username}")
        
        SET_STATUSES = [
            CoachAvailability.Status.AVAILABLE,
            CoachAvailability.Status.UNAVAILABLE,
            CoachAvailability.Status.EMERGENCY,
        ]

        needs_avail = Session.objects.filter(
            session_date__year=this_month_start.year,
            session_date__month=this_month_start.month,
            generated_from_rule__isnull=False,
            is_cancelled=False
        ).exclude(
            coach_availabilities__coach=coach_user,
            coach_availabilities__status__in=SET_STATUSES
        ).exists()
        
        print(f"NEW LOGIC Result (needs_availability_current_month): {needs_avail}")





if __name__ == "__main__":
    check_january_sessions()

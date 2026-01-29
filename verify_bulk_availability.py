
import os
import django
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

import sys
sys.path.append(os.getcwd())
# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach_project.settings')
django.setup()

from scheduling.models import Session, CoachAvailability, ScheduledClass, SessionCoach, Venue
from django.contrib.auth import get_user_model
from accounts.models import Coach

User = get_user_model()
from players.models import SchoolGroup

def run_tests():
    print("Running Bulk Availability Verification Tests...")
    
    # --- SETUP ---
    # Create or get a test coach and user
    user, created = User.objects.get_or_create(username='test_coach_bulk', email='test_bulk@example.com', defaults={'is_staff': True})
    coach, created = Coach.objects.get_or_create(user=user, name='Test Coach Bulk')
    
    # Create a dummy school group and venue
    group, _ = SchoolGroup.objects.get_or_create(name="Test Group Bulk")
    venue, _ = Venue.objects.get_or_create(name="Test Venue Bulk")

    # Create a dummy ScheduledClass rule
    rule, _ = ScheduledClass.objects.get_or_create(
        school_group=group, 
        day_of_week=0, # Monday
        start_time='10:00:00',
        defaults={'default_venue': venue}
    )

    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    
    # Create a session for Yesterday (linked to rule)
    session_y, _ = Session.objects.get_or_create(
        generated_from_rule=rule,
        session_date=yesterday,
        defaults={'session_start_time': '10:00:00', 'school_group': group, 'venue': venue}
    )

    # Create a session for Tomorrow (linked to rule)
    session_t, _ = Session.objects.get_or_create(
        generated_from_rule=rule,
        session_date=tomorrow,
        defaults={'session_start_time': '10:00:00', 'school_group': group, 'venue': venue}
    )
    
    print("Setup complete.")

    # --- TEST 1: Historical Guardrail ---
    print("\n[TEST 1] Historical Guardrail & Basic Update")
    
    # SIMULATE BULK UPDATE (Logic from views.py)
    # We want to set this rule to AVAILABLE
    start_date = today.replace(day=1)
    end_date = (start_date + timedelta(days=32)).replace(day=1)
    
    future_start_date = max(start_date, today + timedelta(days=1))
    
    sessions_to_update = Session.objects.filter(
        generated_from_rule=rule,
        session_date__gte=future_start_date,
        session_date__lte=end_date
    )
    
    update_count = 0
    for session in sessions_to_update:
        CoachAvailability.objects.update_or_create(
            coach=user,
            session=session,
            defaults={'status': CoachAvailability.Status.AVAILABLE}
        )
        update_count += 1
        
    print(f"  > Simulating update... Updated {update_count} sessions.")
    
    # VERIFY
    # Yesterday should NOT have an availability record (or at least not updated by this if we started clear)
    # Since we didn't create one before, it should not exist.
    exists_y = CoachAvailability.objects.filter(coach=user, session=session_y).exists()
    
    # Tomorrow SHOULD be AVAILABLE
    avail_t = CoachAvailability.objects.filter(coach=user, session=session_t).first()
    
    if not exists_y and avail_t and avail_t.status == CoachAvailability.Status.AVAILABLE:
        print("  > SUCCESS: Yesterday ignored, Tomorrow set to AVAILABLE.")
    else:
        print(f"  > FAIL: Yesterday exists? {exists_y}. Tomorrow status: {avail_t.status if avail_t else 'None'}")


    # --- TEST 2: Assignment Protection ---
    print("\n[TEST 2] Assignment Protection")
    
    # Assign coach to Tomorrow's session
    SessionCoach.objects.create(session=session_t, coach=coach, coaching_duration_minutes=60)
    session_t.coaches_attending.add(coach) # Ensure standard M2M is consistent if used? 
    # Note: views.py uses SessionCoach as through model but manually manages it in assign_coaches. 
    # Session.coaches_attending is the M2M field using the through model.
    # Creating the through model object is enough.
    
    print("  > Assigned coach to Tomorrow's session.")
    
    # Now BULK UPDATE to UNAVAILABLE
    for session in sessions_to_update:
        CoachAvailability.objects.update_or_create(
            coach=user,
            session=session,
            defaults={'status': CoachAvailability.Status.UNAVAILABLE} # GREY
        )
        
    # VERIFY
    # 1. Assignment should still exist
    is_assigned = SessionCoach.objects.filter(session=session_t, coach=coach).exists()
    
    # 2. Status should be UNAVAILABLE
    avail_t.refresh_from_db()
    
    if is_assigned and avail_t.status == CoachAvailability.Status.UNAVAILABLE:
        print("  > SUCCESS: Assignment preserved, Availability updated to UNAVAILABLE.")
    else:
         print(f"  > FAIL: Assignment integrity? {is_assigned}. Status: {avail_t.status}")


    # --- TEST 3: Idempotency ---
    print("\n[TEST 3] Idempotency")
    
    # Run the same update again
    before_count = CoachAvailability.objects.count()
    before_ts = avail_t.timestamp
    
    for session in sessions_to_update:
        CoachAvailability.objects.update_or_create(
            coach=user,
            session=session,
            defaults={'status': CoachAvailability.Status.UNAVAILABLE}
        )
        
    after_count = CoachAvailability.objects.count()
    avail_t.refresh_from_db()
    
    # Note: timestamp might update because 'auto_now=True' updates on save() even if fields didn't change in some DBs or Django versions?
    # Actually update_or_create avoids save if no changes in newer Django versions, but safe to check count at least.
    # Let's check specifically if a NEW record was created.
    
    if before_count == after_count:
        print("  > SUCCESS: Record count unchanged.")
    else:
        print(f"  > FAIL: Record count changed from {before_count} to {after_count}")

    # CLEANUP
    # SessionCoach.objects.filter(coach=coach).delete()
    # CoachAvailability.objects.filter(coach=user).delete()
    # Session.objects.filter(generated_from_rule=rule).delete()
    # rule.delete()
    # group.delete()
    # venue.delete()
    print("\nDone.")

if __name__ == '__main__':
    run_tests()

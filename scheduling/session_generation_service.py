# scheduling/session_generation_service.py

from datetime import date, timedelta
from django.db import transaction

# Import models from their correct new app locations
from .models import ScheduledClass, Session
from players.models import Player
from accounts.models import Coach

def generate_sessions_for_rules(
    scheduled_classes_qs,
    period_start_date: date,
    period_end_date: date,
    overwrite_existing_non_generated: bool = False
):
    """
    Generates Session instances based on ScheduledClass rules for a given date range.
    """
    sessions_created_count = 0
    sessions_skipped_exists_count = 0
    errors_count = 0
    action_details = []

    if period_start_date > period_end_date:
        action_details.append(f"Error: Start date ({period_start_date}) cannot be after end date ({period_end_date}).")
        return {'created': 0, 'skipped_exists': 0, 'errors': 1, 'details': action_details}

    current_date = period_start_date
    
    with transaction.atomic():
        while current_date <= period_end_date:
            current_day_of_week = current_date.weekday()

            for rule in scheduled_classes_qs.filter(is_active=True):
                if rule.day_of_week == current_day_of_week:
                    # Check if a session from this rule already exists
                    if Session.objects.filter(generated_from_rule=rule, session_date=current_date).exists():
                        sessions_skipped_exists_count += 1
                        continue

                    # Check for a manual session clashing
                    clashing_manual_session = Session.objects.filter(
                        school_group=rule.school_group,
                        session_date=current_date,
                        session_start_time=rule.start_time,
                        generated_from_rule__isnull=True
                    ).first()

                    if clashing_manual_session:
                        if overwrite_existing_non_generated:
                            # Link the manual session to the rule
                            clashing_manual_session.generated_from_rule = rule
                            clashing_manual_session.save()
                            sessions_created_count += 1
                            action_details.append(f"Updated and linked manual session for '{rule.school_group}' on {current_date}.")
                        else:
                            sessions_skipped_exists_count += 1
                        continue

                    # Create a new session
                    try:
                        new_session = Session.objects.create(
                            school_group=rule.school_group,
                            session_date=current_date,
                            session_start_time=rule.start_time,
                            planned_duration_minutes=rule.default_duration_minutes,
                            venue=rule.default_venue,
                            notes=f"Generated from rule: {rule}",
                            generated_from_rule=rule
                        )
                        if rule.default_coaches.exists():
                            new_session.coaches_attending.set(rule.default_coaches.all())
                        
                        if rule.school_group:
                            active_players = Player.objects.filter(school_groups=rule.school_group, is_active=True)
                            if active_players.exists():
                                new_session.attendees.set(active_players)
                        
                        sessions_created_count += 1
                    except Exception as e:
                        errors_count += 1
                        action_details.append(f"Error creating session for '{rule}' on {current_date}: {e}")

            current_date += timedelta(days=1)

    return {
        'created': sessions_created_count,
        'skipped_exists': sessions_skipped_exists_count,
        'errors': errors_count,
        'details': action_details
    }
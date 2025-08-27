# scheduling/utils.py

import calendar
from datetime import date, timedelta

def get_month_start_end(year, month):
    """Returns the first and last day of a given month and year."""
    _, num_days = calendar.monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, num_days)
    return start_date, end_date

def check_for_conflicts(coach, session_to_check, all_coach_sessions, travel_time_minutes=30):
    """
    Checks for scheduling conflicts for a coach.

    Args:
        coach: The Coach object.
        session_to_check: The Session object being considered for assignment.
        all_coach_sessions: A queryset of all other sessions the coach is assigned to in the period.
        travel_time_minutes: The assumed travel time in minutes between different venues.

    Returns:
        A string with a conflict message, or None if no conflict.
    """
    if not session_to_check.start_datetime or not session_to_check.end_datetime:
        return None  # Cannot check a session without start/end times

    travel_delta = timedelta(minutes=travel_time_minutes)

    for other_session in all_coach_sessions:
        if other_session.id == session_to_check.id:
            continue

        if not other_session.start_datetime or not other_session.end_datetime:
            continue

        # Check for direct time overlap
        if max(session_to_check.start_datetime, other_session.start_datetime) < min(session_to_check.end_datetime, other_session.end_datetime):
            return f"Time overlap with {other_session.school_group.name} at {other_session.session_start_time.strftime('%H:%M')}"

        # Check for travel time conflicts if venues are different
        if other_session.venue and session_to_check.venue and other_session.venue.id != session_to_check.venue.id:
            if session_to_check.end_datetime > other_session.start_datetime - travel_delta and session_to_check.start_datetime < other_session.start_datetime:
                return f"Insufficient travel time from {other_session.school_group.name} at {other_session.venue.name}"
            if other_session.end_datetime > session_to_check.start_datetime - travel_delta and other_session.start_datetime < session_to_check.start_datetime:
                return f"Insufficient travel time to {other_session.school_group.name} at {other_session.venue.name}"

    return None
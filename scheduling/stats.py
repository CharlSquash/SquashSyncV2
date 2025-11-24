from django.utils import timezone
from datetime import date
from scheduling.models import Session, AttendanceTracking
from players.models import SchoolGroup

def calculate_player_attendance_stats(player, start_date=None, end_date=None, school_group_id=None):
    """
    Calculates attendance statistics for a given player within a date range.
    """
    today = timezone.now().date()
    current_year_start = date(today.year, 1, 1)

    # Set defaults if not provided
    if not start_date:
        start_date = current_year_start.strftime('%Y-%m-%d')
    if not end_date:
        end_date = today.strftime('%Y-%m-%d')

    # Base queryset for all sessions within the selected filter range
    sessions_in_range_qs = Session.objects.filter(
        school_group__in=player.school_groups.all(),
        session_date__range=[start_date, end_date],
        is_cancelled=False
    )

    if school_group_id:
        sessions_in_range_qs = sessions_in_range_qs.filter(school_group__id=school_group_id)

    # Find only the sessions in the date range where any attendance was marked.
    sessions_with_attendance_taken = sessions_in_range_qs.filter(
        session_date__lte=today,
        player_attendances__attended__in=[
            AttendanceTracking.CoachAttended.YES,
            AttendanceTracking.CoachAttended.NO
        ]
    ).distinct()

    # The total number of sessions is the count of this filtered set.
    total_sessions = sessions_with_attendance_taken.count()

    # Count attended sessions only from within the sessions where attendance was taken.
    attended_sessions = AttendanceTracking.objects.filter(
        player=player,
        session__in=sessions_with_attendance_taken,
        attended=AttendanceTracking.CoachAttended.YES
    ).count()

    attendance_percentage = (attended_sessions / total_sessions * 100) if total_sessions > 0 else 0

    return {
        'percentage': attendance_percentage,
        'total_sessions': total_sessions,
        'attended_sessions': attended_sessions,
        'start_date': start_date,
        'end_date': end_date
    }

def calculate_group_attendance_stats(school_group, start_date, end_date):
    """
    Calculates attendance statistics for a school group within a date range.
    """
    sessions_in_range = Session.objects.filter(
        school_group=school_group,
        session_date__range=[start_date, end_date],
        is_cancelled=False
    )
    
    players_in_group = school_group.players.filter(is_active=True)

    # Find sessions where attendance was actually recorded for at least one player.
    sessions_with_attendance_taken = sessions_in_range.filter(
        player_attendances__attended__in=[
            AttendanceTracking.CoachAttended.YES,
            AttendanceTracking.CoachAttended.NO
        ]
    ).distinct()
    
    # Total possible attendances is the number of players multiplied by the number of *tracked* sessions.
    total_possible_attendances = sessions_with_attendance_taken.count() * players_in_group.count()
    
    # Actual attendances are counted only from within those tracked sessions.
    actual_attendances = AttendanceTracking.objects.filter(
        session__in=sessions_with_attendance_taken,
        player__in=players_in_group,
        attended=AttendanceTracking.CoachAttended.YES
    ).count()
    
    attendance_percentage = (actual_attendances / total_possible_attendances * 100) if total_possible_attendances > 0 else 0

    return {
        'percentage': attendance_percentage,
        'total_possible': total_possible_attendances,
        'actual_attendances': actual_attendances
    }

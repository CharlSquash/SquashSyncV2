from django.utils import timezone
from datetime import date
from scheduling.models import Session, AttendanceTracking
from .models import SchoolGroup

class PlayerService:
    @staticmethod
    def get_attendance_stats(player, start_date=None, end_date=None, school_group_id=None):
        """
        Deprecated: Use scheduling.stats.calculate_player_attendance_stats instead.
        """
        from scheduling.stats import calculate_player_attendance_stats
        stats = calculate_player_attendance_stats(player, start_date, end_date, school_group_id)
        # Map new keys to old keys for backward compatibility if any other code uses this
        stats['attendance_percentage'] = stats['percentage']
        return stats

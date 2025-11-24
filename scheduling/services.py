from .models import Session, AttendanceTracking
from players.models import Player

class SessionService:
    @staticmethod
    def get_previous_session_groups(session):
        """
        Fetches the previous session for the same school group and extracts group data.
        Returns a list of groups with player names or None.
        """
        previous_groups_data = None
        previous_session = Session.objects.filter(
            school_group=session.school_group,
            session_date__lt=session.session_date
        ).order_by('-session_date', '-session_start_time').first()

        if previous_session and previous_session.plan and isinstance(previous_session.plan, dict):
            previous_groups_data = previous_session.plan.get('playerGroups')
            # Add player names to the group data for easy display
            if previous_groups_data:
                all_players = {p.id: p.full_name for p in Player.objects.filter(school_groups=session.school_group)}
                for group in previous_groups_data:
                    group['player_names'] = [all_players.get(pid, 'Unknown Player') for pid in group.get('player_ids', [])]
        
        return previous_groups_data

    @staticmethod
    def get_session_player_lists(session):
        """
        Initializes AttendanceTracking records and builds player lists for display and grouping.
        Returns a tuple: (all_players_for_display, players_for_grouping)
        """
        players_for_grouping = []
        all_players_for_display = []

        if session.school_group:
            all_players_in_group = list(session.school_group.players.filter(is_active=True).order_by('last_name', 'first_name'))
            player_ids = [p.id for p in all_players_in_group]

            # Ensure records exist for all players to avoid errors
            existing_player_ids = set(
                AttendanceTracking.objects.filter(session=session, player_id__in=player_ids).values_list('player_id', flat=True)
            )
            new_records = [
                AttendanceTracking(session=session, player_id=pid)
                for pid in player_ids if pid not in existing_player_ids
            ]
            if new_records:
                AttendanceTracking.objects.bulk_create(new_records)

            # Fetch all attendance records for the session
            attendance_records = AttendanceTracking.objects.filter(session=session, player_id__in=player_ids)
            attendance_map = {att.player_id: att for att in attendance_records}

            # Check if final attendance has been taken for ANY player in this session
            has_final_attendance = any(att.attended != AttendanceTracking.CoachAttended.UNSET for att in attendance_map.values())

            # Populate the two different player lists
            for player in all_players_in_group:
                record = attendance_map.get(player.id)
                
                # 1. This list is ONLY for display in the top "Attendance" section
                all_players_for_display.append({
                    'id': player.id,
                    'name': player.full_name,
                    'status': record.parent_response if record else 'PENDING'
                })

                # 2. This list is for the "Form Player Groups" section
                if has_final_attendance:
                    # If final attendance has started, ONLY include players marked as YES
                    if record and record.attended == AttendanceTracking.CoachAttended.YES:
                        players_for_grouping.append({
                            'id': player.id,
                            'name': player.full_name,
                            'status': 'ATTENDING' # Status for JS must be ATTENDING
                        })
                else:
                    # Before final attendance, include PENDING and ATTENDING players
                    parent_status = record.parent_response if record else 'PENDING'
                    if parent_status in ['ATTENDING', 'PENDING']:
                        players_for_grouping.append({
                            'id': player.id,
                            'name': player.full_name,
                            'status': parent_status
                        })
            
            all_players_for_display.sort(key=lambda p: p['name'])
            
        return all_players_for_display, players_for_grouping

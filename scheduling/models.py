# scheduling/models.py
import datetime
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.conf import settings


# --- MODEL: Venue ---
class Venue(models.Model):
    name = models.CharField(max_length=150, unique=True, help_text="Name of the venue (e.g., Midstream College Main Courts, Uitsig Court 1).")
    address = models.TextField(blank=True, null=True, help_text="Optional: Full address of the venue.")
    notes = models.TextField(blank=True, null=True, help_text="Optional: Any notes about the venue (e.g., access instructions, number of courts).")
    is_active = models.BooleanField(default=True, help_text="Is this venue currently in use?")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Venue"
        verbose_name_plural = "Venues"


class DrillTag(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="A category or tag for a drill (e.g., Fitness, Forehand, Fun Games).")

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
# --- MODEL: Drill ---
class Drill(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    duration_minutes_default = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1)], help_text="Default duration in minutes for this drill.")
    PLAYER_COUNT_CHOICES = [
        (1, '1 Player'),
        (2, '2 Players'),
        (3, '3 Players'),
        (4, '4+ Players'),
    ]
    ideal_num_players = models.IntegerField(choices=PLAYER_COUNT_CHOICES, null=True, blank=True, help_text="Ideal number of players for this drill.")
    suitable_for_any = models.BooleanField(default=False, help_text="Check if this drill works well regardless of specific group skill level or size (within reason).")

    youtube_link = models.URLField(
        max_length=1024,
        blank=True,
        null=True,
        verbose_name="YouTube Link",
        help_text="Optional: A link to a YouTube video demonstrating the drill."
    )

    tags = models.ManyToManyField(DrillTag, blank=True, related_name="drills")

    def __str__(self):
        return self.name
    class Meta:
        ordering = ['name']




# --- MODEL: ScheduledClass ---
class ScheduledClass(models.Model):
    DAY_OF_WEEK_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
        (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
    ]
    # IMPORTANT: Updated FK relationship
    school_group = models.ForeignKey('players.SchoolGroup', on_delete=models.CASCADE, related_name='scheduled_classes')
    day_of_week = models.IntegerField(choices=DAY_OF_WEEK_CHOICES)
    start_time = models.TimeField()
    default_duration_minutes = models.PositiveIntegerField(default=60, validators=[MinValueValidator(1)])
    # We can use a direct reference 'Venue' as it is in the same app
    default_venue = models.ForeignKey('Venue', on_delete=models.SET_NULL, null=True, blank=True, help_text="Default venue for this recurring class.")
    # IMPORTANT: Updated M2M relationship
    default_coaches = models.ManyToManyField('accounts.Coach', blank=True, related_name='default_scheduled_classes')
    is_active = models.BooleanField(default=True, help_text="If unchecked, new sessions will not be generated from this rule.")
    notes_for_rule = models.TextField(blank=True, null=True, help_text="Internal notes about this recurring schedule rule.")

    def __str__(self):
        day_name = self.get_day_of_week_display()
        venue_name_str = f" at {self.default_venue.name}" if self.default_venue else ""
        return f"{self.school_group.name} - {day_name}s @ {self.start_time.strftime('%H:%M')}{venue_name_str}"
    class Meta:
        ordering = ['school_group__name', 'day_of_week', 'start_time']
        verbose_name = "Scheduled Class Rule"
        verbose_name_plural = "Scheduled Class Rules"
        unique_together = ('school_group', 'day_of_week', 'start_time')


# --- MODEL: Session ---
class Session(models.Model):
    # *** ADDED: Status choices are now defined inside the class ***
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('finished', 'Finished'),
    ]

    session_date = models.DateField(default=timezone.now)
    session_start_time = models.TimeField(default=timezone.now)
    planned_duration_minutes = models.PositiveIntegerField(default=60, validators=[MinValueValidator(1)])
    # IMPORTANT: Updated FK relationships
    school_group = models.ForeignKey('players.SchoolGroup', on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    attendees = models.ManyToManyField('players.Player', related_name='attended_sessions', blank=True)
    coaches_attending = models.ManyToManyField('accounts.Coach', related_name='coached_sessions', blank=True)
    venue = models.ForeignKey('Venue', on_delete=models.SET_NULL, null=True, blank=True, help_text="Venue where the session takes place.")
    generated_from_rule = models.ForeignKey('ScheduledClass', on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_sessions', help_text="Link to the recurring schedule rule, if this session was auto-generated.")
    
    is_cancelled = models.BooleanField(default=False, help_text="Mark as true if the session has been cancelled.")
    notes = models.TextField(blank=True, help_text="Optional objectives or notes for the session.")

    plan = models.JSONField(
        null=True, 
        blank=True, 
        help_text="Stores the detailed lesson plan including timeline, groups, and activities."
    )
    
    # *** ADDED: Fields for the live session view to use ***
    start_time = models.DateTimeField(null=True, blank=True, help_text="The actual start time when a coach begins the session.")
    end_time = models.DateTimeField(null=True, blank=True, help_text="The actual end time when a session is finished.")
    
    # *** ADDED: The status field now works correctly ***
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    @property
    def start_datetime(self):
        if self.session_date and self.session_start_time:
            return timezone.make_aware(datetime.datetime.combine(self.session_date, self.session_start_time))
        return None

    @property
    def end_datetime(self):
        start = self.start_datetime
        if start and self.planned_duration_minutes:
            return start + datetime.timedelta(minutes=self.planned_duration_minutes)
        return None

    def __str__(self):
        group_name = self.school_group.name if self.school_group else "General"
        start_time_str = self.session_start_time.strftime('%H:%M')
        date_str = self.session_date.strftime('%Y-%m-%d')
        venue_str = f" at {self.venue.name}" if self.venue else ""
        return f"{group_name} Session on {date_str} at {start_time_str}{venue_str}"

    class Meta:
        ordering = ['-session_date', '-session_start_time']


# --- MODEL: CoachAvailability ---
class CoachAvailability(models.Model):
    # --- NEW: Status field to replace is_available boolean ---
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        AVAILABLE = 'AVAILABLE', 'Available'
        UNAVAILABLE = 'UNAVAILABLE', 'Unavailable'
        EMERGENCY = 'EMERGENCY', 'Emergency Only'

    coach = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='session_availabilities', limit_choices_to={'is_staff': True})
    session = models.ForeignKey('Session', on_delete=models.CASCADE, related_name='coach_availabilities')
    
    # REMOVED: is_available = models.BooleanField(null=True, help_text="True=Available, False=Unavailable, Null=Pending")
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Coach's availability status for this session."
    )
    
    notes = models.TextField(blank=True, help_text="Optional notes (e.g., reason for unavailability).")
    timestamp = models.DateTimeField(auto_now=True)
    
    ACTION_CHOICES = [('CONFIRM', 'Confirmed'), ('DECLINE', 'Declined')]
    last_action = models.CharField(max_length=10, choices=ACTION_CHOICES, null=True, blank=True, help_text="The last explicit action taken by the coach.")
    status_updated_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of when the status was explicitly confirmed or declined.")

    class Meta:
        unique_together = ('coach', 'session')
        ordering = ['session__session_date', 'session__session_start_time', 'coach__username']
        verbose_name = "Coach Availability"
        verbose_name_plural = "Coach Availabilities"

    def __str__(self):
        return f"{self.coach.username} - {self.get_status_display()} for {self.session.session_date}"

# --- MODEL: Event ---
# This model was found in your old models.py. It seems to fit best here in scheduling.
class Event(models.Model):
    class EventType(models.TextChoices):
        SOCIAL = 'SOCIAL', 'Social Event'
        TOURNAMENT = 'TOURNMT', 'Tournament Support'
        SCHOOL = 'SCHOOL', 'School Function'
        CEREMONY = 'CEREMONY', 'Capping/Awards Ceremony'
        MEETING = 'MEETING', 'Coach/Staff Meeting'
        WORKSHOP = 'WORKSHOP', 'Workshop/Training'
        OTHER = 'OTHER', 'Other Event'

    name = models.CharField(max_length=200, help_text="Name of the event.")
    event_type = models.CharField(max_length=10, choices=EventType.choices, default=EventType.OTHER)
    event_date = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True, null=True)
    # IMPORTANT: Updated M2M relationship
    attending_coaches = models.ManyToManyField('accounts.Coach', related_name='attended_events', blank=True)

    def __str__(self):
        return f"{self.name} ({self.get_event_type_display()}) on {self.event_date.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-event_date', 'name']
        verbose_name = "Event"
        verbose_name_plural = "Events"

class AttendanceTracking(models.Model):
    """ Tracks a player's attendance status for a specific session. """
    class ParentResponse(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ATTENDING = 'ATTENDING', 'Attending'
        NOT_ATTENDING = 'NOT_ATTENDING', 'Not Attending'

    class CoachAttended(models.TextChoices):
        UNSET = 'UNSET', 'Unset'
        YES = 'YES', 'Yes'
        NO = 'NO', 'No'

    session = models.ForeignKey('Session', on_delete=models.CASCADE, related_name="player_attendances")
    player = models.ForeignKey('players.Player', on_delete=models.CASCADE, related_name="attendance_records")
    
    # This field is for the parent's response from email links
    parent_response = models.CharField(
        max_length=20,
        choices=ParentResponse.choices,
        default=ParentResponse.PENDING,
        verbose_name="Parent's Response"
    )
    
    # This new field is for the coach's final attendance marking
    attended = models.CharField(
        max_length=10,
        choices=CoachAttended.choices,
        default=CoachAttended.UNSET,
        verbose_name="Coach-Marked Attendance"
    )

    recorded_at = models.DateTimeField(auto_now=True, help_text="Timestamp of the last update.")

    class Meta:
        unique_together = ('session', 'player')
        verbose_name = "Player Attendance Tracking"

    def __str__(self):
        return f"{self.player.full_name} - {self.session.session_date} - Parent: {self.get_parent_response_display()}, Coach: {self.get_attended_display()}"


#// SOLOSYNC ROUTINE AND DRILL

class Routine(models.Model):
    """
    Represents a pre-defined practice routine that players can follow.
    """
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, help_text="Inactive routines won't be shown to players.")
    
    drills = models.ManyToManyField(
        'Drill',
        through='RoutineDrill',
        related_name='routines'
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class RoutineDrill(models.Model):
    """
    This is a "through" model that connects a Routine to a Drill.
    It allows us to specify the order and duration of each drill within a routine.
    """
    routine = models.ForeignKey(Routine, on_delete=models.CASCADE)
    drill = models.ForeignKey(Drill, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(help_text="The order of the drill in the routine (e.g., 1, 2, 3...).")
    duration_minutes = models.PositiveIntegerField(
        help_text="Duration in minutes for this drill within this specific routine.",
        null=True, blank=True # Make it optional for now
    )

    class Meta:
        ordering = ['routine', 'order']
        unique_together = ('routine', 'drill', 'order')

    def __str__(self):
        return f"{self.routine.name} - {self.order}: {self.drill.name}"

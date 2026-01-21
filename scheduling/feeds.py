from django.shortcuts import get_object_or_404
from django.http import HttpResponse, Http404
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.utils import timezone
from .models import Session
from datetime import timedelta
from django.conf import settings
from django.urls import reverse
import icalendar

def coach_calendar_feed(request, token):
    signer = TimestampSigner()
    try:
        # Validate the token. We can set a max_age if we want tokens to expire, 
        # but for a calendar feed subscription, we usually want it to last indefinitely or a long time.
        # However, the user said "Use TimestampSigner to validate the token", implying we verify it was signed by us.
        # If we want it to be valid indefinitely, we just use unsign without max_age (except to check signature validity).
        # But `unsign` checks signature.
        user_id = signer.unsign(token)
    except (BadSignature, SignatureExpired):
        raise Http404("Invalid calendar token")

    # Get the sessions
    now = timezone.now()
    cutoff_past = now - timedelta(days=90) # Last 3 months

    # Query Sessions
    # User is in coaches_attending.
    # Future OR past 3 months.
    sessions = Session.objects.filter(
        coaches_attending__user__id=user_id,
        session_date__gte=cutoff_past.date()
    ).select_related('venue', 'school_group')

    cal = icalendar.Calendar()
    cal.add('prodid', '-//SquashSync//squashsync.com//EN')
    cal.add('version', '2.0')
    cal.add('X-WR-CALNAME', 'SquashSync Schedule')
    cal.add('X-WR-TIMEZONE', settings.TIME_ZONE) # Good practice to add timezone

    for session in sessions:
        event = icalendar.Event()
        
        # Summary
        group_name = session.school_group.name if session.school_group else 'Session'
        summary = f"{group_name} Session"
        if session.is_cancelled:
            summary = f"CANCELLED: {summary}"
        event.add('summary', summary)
        
        # DTSTART / DTEND
        # Combine date and time
        start_dt = timezone.datetime.combine(session.session_date, session.session_start_time)
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt)
            
        end_dt = start_dt + timedelta(minutes=session.planned_duration_minutes)

        event.add('dtstart', start_dt)
        event.add('dtend', end_dt)
        event.add('dtstamp', now)
        
        # Location
        if session.venue:
            event.add('location', session.venue.name)

        # Description
        try:
            path = reverse('scheduling:session_detail', args=[session.id])
            full_url = request.build_absolute_uri(path)
            event.add('description', f"View plan: {full_url}")
        except Exception:
            pass 

        # UID
        # CRITICAL: Must be stable so updates overwrite previous events
        event.add('uid', f"session_{session.id}@squashsync.com")
        
        # SEQUENCE
        # Ideally we track updates, but defaulting to 0 as requested if not possible.
        event.add('sequence', 0) 

        cal.add_component(event)

    response = HttpResponse(cal.to_ical(), content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'inline; filename=coach_schedule.ics'
    return response

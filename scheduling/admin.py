# scheduling/admin.py
from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render
from django.http import HttpResponseRedirect
from .forms import GenerateSessionsForm
from .session_generation_service import generate_sessions_for_rules

from .models import (
    Venue, Drill, DrillTag, Session, ScheduledClass,
    CoachAvailability, Event,
    Routine, RoutineDrill
)

@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'address', 'notes')

@admin.register(DrillTag)
class DrillTagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Drill)
class DrillAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_minutes_default', 'ideal_num_players', 'suitable_for_any')
    list_filter = ('tags', 'suitable_for_any',)
    search_fields = ('name', 'description', 'tags__name')
    filter_horizontal = ('tags',)

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'session_date', 'session_start_time', 'school_group', 'venue', 'is_cancelled', 'status')
    list_filter = ('session_date', 'is_cancelled', 'venue', 'school_group', 'status')
    search_fields = ('notes', 'school_group__name', 'venue__name')
    date_hierarchy = 'session_date'
    filter_horizontal = ('coaches_attending', 'attendees',)
    autocomplete_fields = ['venue', 'school_group']
    actions = ['start_session_now']
    
    exclude = ('plan',)

    @admin.action(description="Start selected sessions now")
    def start_session_now(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select only one session to start at a time.",
                level=messages.WARNING,
            )
            return

        session = queryset.first()
        
        if not session.plan:
            self.message_user(
                request,
                f"Session '{str(session)}' cannot be started because it does not have a session plan.",
                level=messages.ERROR,
            )
            return

        session.start_time = timezone.now()
        session.status = 'active'
        session.save()

        self.message_user(
            request,
            f"Session '{str(session)}' has been started successfully.",
            level=messages.SUCCESS,
        )

admin.site.register(Event)
admin.site.register(CoachAvailability)

@admin.register(ScheduledClass)
class ScheduledClassAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'day_of_week', 'start_time', 'is_active')
    list_filter = ('school_group', 'day_of_week', 'is_active')
    filter_horizontal = ('default_coaches',)
    actions = ['generate_sessions_action']

    def generate_sessions_action(self, request, queryset):
        form = GenerateSessionsForm(request.POST or None)

        if 'generate' in request.POST:
            if form.is_valid():
                start_date = form.cleaned_data['start_date']
                end_date = form.cleaned_data['end_date']
                overwrite = form.cleaned_data['overwrite_clashing_manual_sessions']

                results = generate_sessions_for_rules(queryset, start_date, end_date, overwrite)

                messages.success(request, f"Session Generation Complete: {results['created']} created, {results['skipped_exists']} skipped, {results['errors']} errors.")
                for detail in results['details']:
                    messages.info(request, detail)

                return HttpResponseRedirect(request.get_full_path())

        context = {
            **self.admin_site.each_context(request),
            'title': 'Generate Sessions',
            'queryset': queryset,
            'form': form,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        }
        return render(request, 'admin/scheduling/scheduledclass/generate_sessions.html', context)

    generate_sessions_action.short_description = "Generate Sessions for selected rules"


# --- UPDATED ADMIN CONFIGURATION FOR ROUTINES ---

class RoutineDrillInline(admin.TabularInline):
    """
    Allows editing the RoutineDrill (the ordered list of drills)
    directly within the Routine admin page.
    """
    model = RoutineDrill
    extra = 1
    autocomplete_fields = ['drill']
    # ADD THIS LINE to show the duration field
    fields = ('order', 'drill', 'duration_minutes')


@admin.register(Routine)
class RoutineAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Routine model.
    """
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    inlines = [RoutineDrillInline]

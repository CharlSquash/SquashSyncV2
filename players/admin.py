# players/admin.py
from django.contrib import admin
from django import forms
from .models import (
    SchoolGroup, Player, CourtSprintRecord, VolleyRecord,
    BackwallDriveRecord, MatchResult
)

# Custom form to allow managing the reverse M2M relationship with a filter_horizontal-like widget
class SchoolGroupAdminForm(forms.ModelForm):
    players = forms.ModelMultipleChoiceField(
        queryset=Player.objects.all().order_by('first_name', 'last_name'),
        required=False,
        widget=admin.widgets.FilteredSelectMultiple(
            verbose_name='Players',
            is_stacked=False
        )
    )

    class Meta:
        model = SchoolGroup
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['players'].initial = self.instance.players.all()

@admin.register(SchoolGroup)
class SchoolGroupAdmin(admin.ModelAdmin):
    form = SchoolGroupAdminForm
    list_display = ('name', 'description')
    search_fields = ('name',)

    def save_model(self, request, obj, form, change):
        # Save the SchoolGroup instance first
        super().save_model(request, obj, form, change)
        # Now, save the many-to-many relationship for players from the form
        obj.players.set(form.cleaned_data.get('players'))

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    # Add 'gender' to list_display, list_editable, list_filter
    list_display = ('get_full_name', 'grade', 'gender', 'school', 'is_active')
    list_editable = ('grade', 'gender', 'school', 'is_active') # Add gender here
    list_filter = ('is_active', 'school_groups', 'grade', 'gender') # Add gender here
    search_fields = ('first_name', 'last_name', 'school') # Add school here
    filter_horizontal = ('school_groups',)
    list_per_page = 50 # Show more players per page for easier bulk editing
    change_list_template = "admin/players/player/change_list.html"
    ordering = ('-is_active', 'first_name', 'last_name')

    def get_full_name(self, obj):
        return obj.full_name
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'first_name'

    def changelist_view(self, request, extra_context=None):
        if extra_context is None:
            extra_context = {}
        
        # Calculate active players count
        active_count = Player.objects.filter(is_active=True).count()
        extra_context['active_count'] = active_count
        
        return super().changelist_view(request, extra_context=extra_context)

# Register the metric models so they appear in the admin
admin.site.register(CourtSprintRecord)
admin.site.register(VolleyRecord)
admin.site.register(BackwallDriveRecord)
admin.site.register(MatchResult)

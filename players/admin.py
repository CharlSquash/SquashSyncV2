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
        queryset=Player.objects.all(),
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
    list_display = ('full_name', 'contact_number', 'parent_contact_number', 'is_active')
    list_filter = ('is_active', 'school_groups')
    search_fields = ('first_name', 'last_name')
    filter_horizontal = ('school_groups',)

# Register the metric models so they appear in the admin
admin.site.register(CourtSprintRecord)
admin.site.register(VolleyRecord)
admin.site.register(BackwallDriveRecord)
admin.site.register(MatchResult)


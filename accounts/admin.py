
# accounts/admin.py
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Coach

@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'profile_photo_thumbnail',
        'user_link',
        'email',
        'phone',
        'is_active',
    )
    search_fields = ('name', 'email', 'user__username')
    list_filter = ('is_active', 'user__is_staff')
    readonly_fields = ('profile_photo_thumbnail',)
    raw_id_fields = ('user',)

    @admin.display(description='Photo')
    def profile_photo_thumbnail(self, obj):
        if obj.profile_photo:
            return format_html('<img src="{}" style="width: 45px; height: 45px; border-radius: 50%; object-fit: cover;" />', obj.profile_photo.url)
        return "No photo"

    @admin.display(description='Linked User Account')
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return "-"
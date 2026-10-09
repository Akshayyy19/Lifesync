# ==============================================================================
# File: accounts/admin.py
# Description: Django Admin customization for User Profiles with approval actions.
# ==============================================================================

from django.contrib import admin
from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'status_label',
        'is_approved',
        'is_restricted',
        'city',
        'theme_preference',
        'created_at',
    )
    list_filter = ('is_approved', 'is_restricted', 'theme_preference', 'created_at')
    search_fields = ('user__username', 'user__email', 'city', 'restriction_reason')
    actions = ['approve_selected', 'restrict_selected', 'unrestrict_selected']

    @admin.action(description='Approve selected user accounts')
    def approve_selected(self, request, queryset):
        queryset.update(is_approved=True, is_restricted=False)

    @admin.action(description='Restrict selected user accounts')
    def restrict_selected(self, request, queryset):
        queryset.update(is_restricted=True)

    @admin.action(description='Unrestrict selected user accounts')
    def unrestrict_selected(self, request, queryset):
        queryset.update(is_restricted=False, restriction_reason='')

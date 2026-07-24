from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'city', 'theme_preference', 'created_at')
    list_filter = ('theme_preference',)
    search_fields = ('user__username', 'city')

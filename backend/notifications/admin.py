from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'notif_type', 'for_date', 'is_read', 'created_at')
    list_filter = ('notif_type', 'is_read')
    search_fields = ('message', 'user__username')

from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'date', 'time', 'is_recurring_yearly')
    list_filter = ('category', 'is_recurring_yearly', 'date')
    search_fields = ('title', 'description', 'user__username')
    date_hierarchy = 'date'

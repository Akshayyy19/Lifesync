from django.contrib import admin

from .models import DiaryEntry


@admin.register(DiaryEntry)
class DiaryEntryAdmin(admin.ModelAdmin):
    list_display = ('display_title', 'user', 'date', 'mood', 'created_at')
    list_filter = ('mood', 'date')
    search_fields = ('title', 'content', 'user__username')
    date_hierarchy = 'date'

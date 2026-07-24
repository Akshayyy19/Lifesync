from django.contrib.auth.models import User
from django.db import models


class Event(models.Model):
    """A single calendar item. Covers events, birthdays and reminders through
    the `category` field so the whole calendar can be queried in one go."""

    CATEGORY_CHOICES = [
        ('event', 'Event'),
        ('birthday', 'Birthday'),
        ('reminder', 'Reminder'),
    ]

    REMINDER_CHOICES = [
        (0, 'At the scheduled time'),
        (5, '5 minutes before'),
        (15, '15 minutes before'),
        (30, '30 minutes before'),
        (60, '1 hour before'),
        (1440, '1 day before'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='event')
    date = models.DateField()
    time = models.TimeField(null=True, blank=True, help_text='Leave blank for an all-day item.')
    location = models.CharField(max_length=200, blank=True)
    is_recurring_yearly = models.BooleanField(
        default=False,
        help_text='Repeats every year on this month/day (always on for birthdays).',
    )
    remind_before_minutes = models.PositiveIntegerField(
        choices=REMINDER_CHOICES, null=True, blank=True,
        help_text='Leave blank for no reminder notification.',
    )
    weather_temp = models.IntegerField(null=True, blank=True)
    weather_condition = models.CharField(max_length=100, blank=True)
    weather_icon = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'time']

    def __str__(self):
        return f'{self.title} ({self.get_category_display()}) — {self.date}'

    def save(self, *args, **kwargs):
        if self.category == 'birthday':
            self.is_recurring_yearly = True
        super().save(*args, **kwargs)

    @property
    def badge_class(self):
        """CSS class used to colour-code this item on the calendar/dashboard."""
        return {
            'event': 'chip-event',
            'birthday': 'chip-birthday',
            'reminder': 'chip-reminder',
        }.get(self.category, 'chip-event')

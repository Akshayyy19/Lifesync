# ==============================================================================
# File: planner/models.py
# Description: Calendar Event, Birthday, and Reminder model definitions.
# ==============================================================================

# Import Django's User model to associate events with specific user accounts
from django.contrib.auth.models import User

# Import base models module from Django to define database tables
from django.db import models


# ------------------------------------------------------------------------------
# Model: Event
# Purpose: Unified calendar item covering events, birthdays, and reminders.
# ------------------------------------------------------------------------------
class Event(models.Model):
    """
    A single calendar item. Covers events, birthdays and reminders through
    the `category` field so the whole calendar can be queried in one go.
    """

    # Choice tuples for category: (stored_in_db, human_readable_display_label)
    CATEGORY_CHOICES = [
        ('event', 'Event'),
        ('birthday', 'Birthday'),
        ('reminder', 'Reminder'),
    ]

    # Venue type choices: describes the physical setting of the event
    VENUE_TYPE_CHOICES = [
        ('', 'No venue type'),
        ('indoor', 'Indoor'),
        ('outdoor', 'Outdoor'),
        ('stadium', 'Stadium / Arena'),
        ('hotel', 'Hotel / Resort'),
        ('restaurant', 'Restaurant / Cafe'),
        ('office', 'Office / Conference'),
        ('school', 'School / University'),
        ('home', 'Home / Private'),
        ('park', 'Park / Garden'),
        ('virtual', 'Virtual / Online'),
        ('other', 'Other'),
    ]

    # Pre-defined minutes before an event to trigger a reminder notification
    REMINDER_CHOICES = [
        (0, 'At the scheduled time'),
        (5, '5 minutes before'),
        (15, '15 minutes before'),
        (30, '30 minutes before'),
        (60, '1 hour before'),
        (1440, '1 day before'),
    ]

    # Foreign key relationship: links each event to its owner user
    # on_delete=models.CASCADE removes all user events if the user account is deleted
    # related_name='events' allows querying user events via: request.user.events.all()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')

    # Title or name of the calendar item (required, up to 200 characters)
    title = models.CharField(max_length=200)

    # Optional detailed notes or description about the event
    description = models.TextField(blank=True)

    # Item category; defaults to 'event'
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='event')

    # Date when the event occurs (YYYY-MM-DD)
    date = models.DateField()

    # Specific time for the event; null/blank means an all-day event
    time = models.TimeField(null=True, blank=True, help_text='Leave blank for an all-day item.')

    # Optional physical or virtual location of the event
    location = models.CharField(max_length=200, blank=True)

    # Venue type: describes the kind of place the event is held
    venue_type = models.CharField(
        max_length=20, choices=VENUE_TYPE_CHOICES, blank=True, default='',
        help_text='The kind of venue where the event takes place.',
    )

    # Boolean flag indicating if this event recurs on this day every year (always True for birthdays)
    is_recurring_yearly = models.BooleanField(
        default=False,
        help_text='Repeats every year on this month/day (always on for birthdays).',
    )

    # Number of minutes before the event to generate an alert notification
    remind_before_minutes = models.PositiveIntegerField(
        choices=REMINDER_CHOICES, null=True, blank=True,
        help_text='Leave blank for no reminder notification.',
    )

    # Best-effort weather temperature snapshot for that event date
    weather_temp = models.IntegerField(null=True, blank=True)

    # Human-readable weather condition (e.g. "Sunny", "Rainy")
    weather_condition = models.CharField(max_length=100, blank=True)

    # Weather icon identifier code (e.g. "01d", "10n")
    weather_icon = models.CharField(max_length=20, blank=True)

    # Automatically set to the current date and time when the record is created
    created_at = models.DateTimeField(auto_now_add=True)

    # Automatically updated with the current timestamp every time the record is saved
    updated_at = models.DateTimeField(auto_now=True)

    # Meta class provides database-level options and default ordering
    class Meta:
        # Sort events chronologically by date first, then by time
        ordering = ['date', 'time']

    # Returns string representation of the model for debugging and admin panel
    def __str__(self):
        return f'{self.title} ({self.get_category_display()}) — {self.date}'

    # Overridden save method to apply business logic before writing to the database
    def save(self, *args, **kwargs):
        # Enforce that all birthday items automatically have annual recurrence enabled
        if self.category == 'birthday':
            self.is_recurring_yearly = True
        # Call the parent class save() method to commit the changes to the database
        super().save(*args, **kwargs)

    # Property method to return the corresponding CSS badge class for UI styling
    @property
    def badge_class(self):
        """CSS class used to colour-code this item on the calendar/dashboard."""
        return {
            'event': 'chip-event',        # Blue badge for general events
            'birthday': 'chip-birthday',  # Purple badge for birthdays
            'reminder': 'chip-reminder',  # Amber badge for reminders
        }.get(self.category, 'chip-event') # Fallback to 'chip-event'

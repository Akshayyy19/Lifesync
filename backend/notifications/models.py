# ==============================================================================
# File: notifications/models.py
# Description: Notification model for alerts (events, birthdays, reminders).
# ==============================================================================

# Import Django's default User model to associate notifications with users
from django.contrib.auth.models import User

# Import base models module from Django to define database tables and columns
from django.db import models


# ------------------------------------------------------------------------------
# Model: Notification
# Purpose: Stores generated alerts and unread reminders for a user.
# ------------------------------------------------------------------------------
class Notification(models.Model):
    # Available notification types: (stored_db_value, human_readable_label)
    TYPE_CHOICES = [
        ('event', 'Event'),
        ('birthday', 'Birthday'),
        ('reminder', 'Reminder'),
        ('system', 'System'),
    ]

    # Foreign key linking notification to recipient user; deletes notification if user is deleted
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')

    # Optional foreign key linking notification to the specific Event that triggered it
    # Uses lazy string reference 'planner.Event' to prevent circular import issues
    event = models.ForeignKey(
        'planner.Event', on_delete=models.CASCADE, null=True, blank=True,
        related_name='notifications',
    )

    # Classification type of notification
    notif_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='system')

    # Human-readable message text displayed in the user interface (e.g. "🎉 Today is Alice's birthday!")
    message = models.CharField(max_length=255)

    # Status flag indicating if the user has viewed/dismissed the notification
    is_read = models.BooleanField(default=False)

    # Timestamp when the notification was generated
    created_at = models.DateTimeField(auto_now_add=True)

    # The calendar date this notification was generated for. Combined with
    # `event` in `unique_together`, this prevents duplicate notifications
    # from being inserted on the same day when visiting the dashboard.
    for_date = models.DateField()

    # Meta class for database constraints and default query ordering
    class Meta:
        # Show newest notifications first
        ordering = ['-created_at']
        # Composite unique constraint preventing duplicate notification rows for same event/date
        unique_together = ('user', 'event', 'for_date')

    # String representation method returning notification message
    def __str__(self):
        return self.message

    # Property returning the corresponding Bootstrap icon class for UI rendering
    @property
    def icon_class(self):
        return {
            'event': 'bi-calendar-event',  # Calendar icon for events
            'birthday': 'bi-gift',          # Gift icon for birthdays
            'reminder': 'bi-bell',          # Bell icon for reminders
            'system': 'bi-info-circle',     # Info icon for general system alerts
        }.get(self.notif_type, 'bi-bell')

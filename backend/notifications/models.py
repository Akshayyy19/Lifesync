from django.contrib.auth.models import User
from django.db import models


class Notification(models.Model):
    TYPE_CHOICES = [
        ('event', 'Event'),
        ('birthday', 'Birthday'),
        ('reminder', 'Reminder'),
        ('system', 'System'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    event = models.ForeignKey(
        'planner.Event', on_delete=models.CASCADE, null=True, blank=True,
        related_name='notifications',
    )
    notif_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='system')
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # The calendar date this notification was generated for. Combined with
    # `event`, this stops the same reminder from being created twice on
    # the same day even though generate_notifications() runs on every visit.
    for_date = models.DateField()

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'event', 'for_date')

    def __str__(self):
        return self.message

    @property
    def icon_class(self):
        return {
            'event': 'bi-calendar-event',
            'birthday': 'bi-gift',
            'reminder': 'bi-bell',
            'system': 'bi-info-circle',
        }.get(self.notif_type, 'bi-bell')

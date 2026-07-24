from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    """Extra per-user settings that the built-in User model doesn't have."""

    THEME_CHOICES = [
        ('auto', 'Automatic (follows local time)'),
        ('day', 'Always day'),
        ('night', 'Always night'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    city = models.CharField(
        max_length=100,
        default='Chennai',
        help_text='Used to show weather on your dashboard and calendar.',
    )
    theme_preference = models.CharField(max_length=10, choices=THEME_CHOICES, default='auto')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

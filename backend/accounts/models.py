# ==============================================================================
# File: accounts/models.py
# Description: Custom user profile model extending Django's built-in User model.
# ==============================================================================

# Import Django's default User model which handles username, password, email, and authentication
from django.contrib.auth.models import User

# Import the base models module from Django to define database tables via Python classes
from django.db import models


# ------------------------------------------------------------------------------
# Model: Profile
# Purpose: Extends User with app-specific settings (preferred city, theme mode).
# ------------------------------------------------------------------------------
class Profile(models.Model):
    """
    Extra per-user settings that the built-in Django User model doesn't provide.
    Each user gets exactly one Profile instance linked through a OneToOneField.
    """

    # Define selectable options for the theme preference field as (database_value, human_readable_label)
    THEME_CHOICES = [
        ('auto', 'Automatic (follows timeline: Day / Night)'),  # Shifts theme between day and night based on time
        ('day', 'Light Theme (Always day)'),                   # Forces light UI theme permanently
        ('night', 'Dark Theme (Always night)'),                 # Forces dark UI theme permanently
    ]

    # One-to-one relationship with Django's built-in User.
    # on_delete=models.CASCADE means deleting the user also deletes their profile record.
    # related_name='profile' allows accessing this profile from a user object: request.user.profile
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # The user's default city for fetching weather forecasts and local times
    city = models.CharField(
        max_length=100,                                                     # Maximum character length
        default='Chennai',                                                  # Default value if not specified
        help_text='Used to show weather on your dashboard and calendar.',   # Guidance text shown in admin and forms
    )

    # User's chosen theme appearance mode ('auto', 'day', or 'night')
    theme_preference = models.CharField(
        max_length=10,              # Field length
        choices=THEME_CHOICES,      # Restrict input to pre-defined choices list
        default='auto'              # Default to automatic theme switching
    )

    # Selectable weather effect options allowing user to experience all weather animations
    WEATHER_EFFECT_CHOICES = [
        ('auto', 'Automatic (Live Local Weather)'),
        ('sunny', '☀️ Sunny Day'),
        ('hot-summer', '🔥 Hot Summer Day'),
        ('sun-rain-mix', '🌦️ Sun & Rain Mix (Rainbow)'),
        ('cloudy', '⛅ Cloudy Sky'),
        ('rainy', '🌧️ Rainy Storm'),
        ('thunderstorm', '⛈️ Thunderstorm & Lightning'),
        ('snowy', '❄️ Snowy Winter'),
        ('misty', '🌫️ Misty / Foggy'),
        ('clear-night', '🌙 Clear Starlit Night'),
        ('hot-summer-night', '🌌 Warm Summer Night'),
    ]

    weather_effect_override = models.CharField(
        max_length=20,
        choices=WEATHER_EFFECT_CHOICES,
        default='auto',
        help_text='Choose a sky weather effect to experience or leave on Automatic for live weather.'
    )

    # Admin approval and traffic control
    is_approved = models.BooleanField(
        default=True,
        help_text='Whether this user account is approved by admin to access LifeSync.'
    )
    is_restricted = models.BooleanField(
        default=False,
        help_text='Whether this user account is restricted/suspended by an administrator.'
    )
    restriction_reason = models.TextField(
        blank=True,
        default='',
        help_text='Admin note/reason explaining why the user was restricted.'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_profiles'
    )

    # Timestamp recording when this profile was initially created; set automatically upon creation
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def status(self):
        """Returns the primary account status: 'restricted', 'pending', or 'active'."""
        if self.is_restricted:
            return 'restricted'
        if not self.is_approved:
            return 'pending'
        return 'active'

    @property
    def status_label(self):
        """Human-readable account status badge label."""
        if self.is_restricted:
            return 'Restricted'
        if not self.is_approved:
            return 'Pending Approval'
        return 'Active'

    @property
    def status_badge_class(self):
        """Bootstrap badge styling for UI display."""
        if self.is_restricted:
            return 'badge bg-danger'
        if not self.is_approved:
            return 'badge bg-warning text-dark'
        return 'badge bg-success'

    # String representation method for developer readability in Django shell and Admin dashboard
    def __str__(self):
        # Returns e.g. "john_doe's profile"
        return f"{self.user.username}'s profile"


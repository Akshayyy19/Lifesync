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

    # Timestamp recording when this profile was initially created; set automatically upon creation
    created_at = models.DateTimeField(auto_now_add=True)

    # String representation method for developer readability in Django shell and Admin dashboard
    def __str__(self):
        # Returns e.g. "john_doe's profile"
        return f"{self.user.username}'s profile"

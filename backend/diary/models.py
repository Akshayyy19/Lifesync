# ==============================================================================
# File: diary/models.py
# Description: DiaryEntry model for personal journaling, mood, and weather logging.
# ==============================================================================

# Import Django's default User model to associate journal entries with user accounts
from django.contrib.auth.models import User

# Import base models module from Django to define database fields and relationships
from django.db import models

# Import Django's timezone utility to set default entry dates according to current time
from django.utils import timezone


# ------------------------------------------------------------------------------
# Model: DiaryEntry
# Purpose: Stores personal daily journal entries with mood and weather tags.
# ------------------------------------------------------------------------------
class DiaryEntry(models.Model):
    """
    A single diary/journal entry created by a user.
    Includes emotional mood tracking and automatic snapshots of the weather.
    """

    # List of available mood choices: (database_value, display_label_with_emoji)
    MOOD_CHOICES = [
        ('happy', '😊 Happy'),
        ('excited', '🤩 Excited'),
        ('neutral', '😐 Neutral'),
        ('sad', '😢 Sad'),
        ('anxious', '😰 Anxious'),
        ('angry', '😠 Angry'),
    ]

    # Foreign key linking entry to author user; deleting user deletes all their diary entries
    # related_name='diary_entries' enables: request.user.diary_entries.all()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='diary_entries')

    # Optional short title or headline for the journal entry
    title = models.CharField(max_length=200, blank=True)

    # The main body text of the diary note (supports multi-line writing)
    content = models.TextField()

    # User's selected mood for this day/entry
    mood = models.CharField(max_length=10, choices=MOOD_CHOICES, blank=True)

    # Date of the entry; defaults to current local date
    date = models.DateField(default=timezone.localdate)

    # Temperature snapshot recorded at the time the diary entry was written
    weather_temp = models.FloatField(null=True, blank=True)

    # Weather condition description snapshot (e.g. "Clear sky", "Light rain")
    weather_condition = models.CharField(max_length=100, blank=True)

    # Timestamp set once when the record is initially created
    created_at = models.DateTimeField(auto_now_add=True)

    # Timestamp updated automatically every time the entry is edited and saved
    updated_at = models.DateTimeField(auto_now=True)

    # Metadata configurations for the database model
    class Meta:
        # Default ordering: newest date first, then newest creation timestamp first
        ordering = ['-date', '-created_at']
        # Plural display name in Django admin
        verbose_name_plural = 'Diary entries'

    # String representation for admin and shell display
    def __str__(self):
        return self.title or f'Entry on {self.date}'

    # Helper method to get a displayable title, falling back to a formatted date string
    def display_title(self):
        # E.g. "My Sunday Trip" or "Sunday, 05 September 2026"
        return self.title or self.date.strftime('%A, %d %B %Y')

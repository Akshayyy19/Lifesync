from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class DiaryEntry(models.Model):
    MOOD_CHOICES = [
        ('happy', '😊 Happy'),
        ('excited', '🤩 Excited'),
        ('neutral', '😐 Neutral'),
        ('sad', '😢 Sad'),
        ('anxious', '😰 Anxious'),
        ('angry', '😠 Angry'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='diary_entries')
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    mood = models.CharField(max_length=10, choices=MOOD_CHOICES, blank=True)
    date = models.DateField(default=timezone.localdate)

    # Best-effort snapshot of the weather when the entry was written —
    # ties the diary feature back into the weather integration.
    weather_temp = models.FloatField(null=True, blank=True)
    weather_condition = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name_plural = 'Diary entries'

    def __str__(self):
        return self.title or f'Entry on {self.date}'

    def display_title(self):
        return self.title or self.date.strftime('%A, %d %B %Y')

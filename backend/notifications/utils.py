# ==============================================================================
# File: notifications/utils.py
# Description: Automated notification generator for calendar events and birthdays.
# ==============================================================================

# Import timedelta to compute date offsets (e.g. tomorrow = today + 1 day)
from datetime import timedelta

# Import timezone module to work with local calendar dates
from django.utils import timezone

# Import Event model to inspect upcoming calendar items
from planner.models import Event

# Import Notification model to create new notification records
from .models import Notification


# ------------------------------------------------------------------------------
# Function: generate_notifications
# Purpose: Scans a user's calendar and generates Notification records for events
#          or birthdays occurring today or tomorrow.
# ------------------------------------------------------------------------------
def generate_notifications(user):
    """
    Looks at everything on the user's calendar and makes sure a
    Notification exists for anything happening today or tomorrow.

    Safe to call on every page load — get_or_create() combined with
    unique_together constraint means an event already notified about
    today will never create a duplicate row.
    """
    # Calculate today's date in user's timezone
    today = timezone.localdate()

    # Calculate tomorrow's date
    tomorrow = today + timedelta(days=1)

    # Query ordinary events & reminders scheduled for today or tomorrow (excluding birthdays)
    upcoming = Event.objects.filter(
        user=user, date__gte=today, date__lte=tomorrow,
    ).exclude(category='birthday')

    # Iterate through each upcoming event/reminder
    for item in upcoming:
        # Determine temporal phrasing ('today' or 'tomorrow')
        when = 'today' if item.date == today else 'tomorrow'
        # Select appropriate emoji icon based on category
        icon = '⏰' if item.category == 'reminder' else '📅'
        # Construct human-readable notification text
        message = f'{icon} "{item.title}" is {when} ({item.date.strftime("%d %b")}).'
        
        # Safely create notification record only if one doesn't already exist for this date
        Notification.objects.get_or_create(
            user=user,
            event=item,
            for_date=today,
            defaults={
                'notif_type': 'reminder' if item.category == 'reminder' else 'event',
                'message': message,
            },
        )

    # Birthdays recur every year, so we query all birthdays for this user and match month/day
    birthdays = Event.objects.filter(user=user, category='birthday')
    for item in birthdays:
        try:
            # Shift the birthday date to the current year for comparison
            this_year_date = item.date.replace(year=today.year)
        except ValueError:
            # Handle February 29 on non-leap years by falling back to February 28
            this_year_date = item.date.replace(year=today.year, day=28)

        # Check if the birthday occurs today
        if this_year_date == today:
            message = f'🎉 Today is {item.title}\'s birthday!'
        # Check if the birthday occurs tomorrow
        elif this_year_date == tomorrow:
            message = f'🎂 {item.title}\'s birthday is tomorrow!'
        else:
            # Birthday is neither today nor tomorrow; skip to next item
            continue

        # Safely create birthday notification avoiding duplicates
        Notification.objects.get_or_create(
            user=user,
            event=item,
            for_date=today,
            defaults={'notif_type': 'birthday', 'message': message},
        )

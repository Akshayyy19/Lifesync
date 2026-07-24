from datetime import timedelta

from django.utils import timezone

from planner.models import Event

from .models import Notification


def generate_notifications(user):
    """Looks at everything on the user's calendar and makes sure a
    Notification exists for anything happening today or tomorrow.

    Safe to call on every page load — get_or_create() means an event
    already notified about today will never create a duplicate row.
    """
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)

    # Ordinary events & reminders due today or tomorrow.
    upcoming = Event.objects.filter(
        user=user, date__gte=today, date__lte=tomorrow,
    ).exclude(category='birthday')

    for item in upcoming:
        when = 'today' if item.date == today else 'tomorrow'
        icon = '⏰' if item.category == 'reminder' else '📅'
        message = f'{icon} "{item.title}" is {when} ({item.date.strftime("%d %b")}).'
        Notification.objects.get_or_create(
            user=user, event=item, for_date=today,
            defaults={
                'notif_type': 'reminder' if item.category == 'reminder' else 'event',
                'message': message,
            },
        )

    # Birthdays recur every year, so compare month/day only.
    birthdays = Event.objects.filter(user=user, category='birthday')
    for item in birthdays:
        try:
            this_year_date = item.date.replace(year=today.year)
        except ValueError:
            # 29 Feb in a non-leap year — treat it as 28 Feb.
            this_year_date = item.date.replace(year=today.year, day=28)

        if this_year_date == today:
            message = f'🎉 Today is {item.title}\'s birthday!'
        elif this_year_date == tomorrow:
            message = f'🎂 {item.title}\'s birthday is tomorrow!'
        else:
            continue

        Notification.objects.get_or_create(
            user=user, event=item, for_date=today,
            defaults={'notif_type': 'birthday', 'message': message},
        )

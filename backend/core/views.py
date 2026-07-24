from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from diary.models import DiaryEntry
from notifications.models import Notification
from notifications.utils import generate_notifications
from planner.models import Event
from weather.services import get_current_weather


def home(request):
    """Public landing page. Signed-in users go straight to their dashboard."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return render(request, 'core/home.html')


@login_required
def dashboard(request):
    today = timezone.localdate()
    city = getattr(request.user.profile, 'city', None) or 'Chennai'
    weather = get_current_weather(city)

    todays_events = Event.objects.filter(user=request.user, date=today).exclude(category='birthday')
    todays_birthdays = Event.objects.filter(
        user=request.user, category='birthday', date__month=today.month, date__day=today.day,
    )
    upcoming_events = Event.objects.filter(
        user=request.user, date__gt=today, date__lte=today + timedelta(days=7),
    ).exclude(category='birthday').order_by('date')[:5]

    latest_entry = DiaryEntry.objects.filter(user=request.user).order_by('-date', '-created_at').first()
    has_entry_today = DiaryEntry.objects.filter(user=request.user, date=today).exists()

    generate_notifications(request.user)
    recent_notifications = Notification.objects.filter(user=request.user, is_read=False)[:5]

    context = {
        'today': today,
        'weather': weather,
        'todays_events': todays_events,
        'todays_birthdays': todays_birthdays,
        'upcoming_events': upcoming_events,
        'latest_entry': latest_entry,
        'has_entry_today': has_entry_today,
        'recent_notifications': recent_notifications,
    }
    return render(request, 'core/dashboard.html', context)

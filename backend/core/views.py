# ==============================================================================
# File: core/views.py
# Description: Handles main landing page and user dashboard views for LifeSync.
# ==============================================================================

# Import timedelta to calculate future date intervals (e.g. next 7 days)
from datetime import timedelta

# Import login_required decorator to restrict dashboard access to authenticated users only
from django.contrib.auth.decorators import login_required

# Import redirect (to send user to another URL) and render (to load HTML templates with context data)
from django.shortcuts import redirect, render

# Import Django timezone utility to get current local date respecting project timezone
from django.utils import timezone

# Import DiaryEntry model to fetch user diary records
from diary.models import DiaryEntry

# Import Notification model to display unread user reminders/alerts
from notifications.models import Notification

# Import helper function that inspects events/birthdays and generates needed notifications
from notifications.utils import generate_notifications

# Import Event model to query calendar items, birthdays, and reminders
from planner.models import Event

# Import helper service to fetch live weather data for the user's city
from weather.services import get_current_weather


# ------------------------------------------------------------------------------
# View: home
# Purpose: Serves as the public landing page for visitors.
# ------------------------------------------------------------------------------
def home(request):
    """
    Public landing page.
    If the visitor is already logged in, redirect them directly to their personal dashboard.
    Otherwise, render the public welcome/landing page.
    """
    # Check if the user making the request is already authenticated
    if request.user.is_authenticated:
        # Redirect authenticated users straight to the dashboard route in the 'core' app namespace
        return redirect('core:dashboard')
    
    # Render the public landing template ('core/home.html') for unauthenticated guests
    return render(request, 'core/home.html')


# ------------------------------------------------------------------------------
# View: dashboard
# Purpose: Primary user control center showing weather, schedule, diary, and alerts.
# ------------------------------------------------------------------------------
@login_required  # Ensures only logged-in users can access the dashboard; redirects guests to login page
def dashboard(request):
    # Get today's local date based on user/server timezone settings
    today = timezone.localdate()

    # Retrieve user's configured city from their profile model; fallback to 'Chennai' if not set
    city = getattr(request.user.profile, 'city', None) or 'Chennai'

    # Fetch live weather information (temperature, condition, icons) for the city
    weather = get_current_weather(city)

    # Query events/reminders scheduled specifically for today, excluding birthdays
    todays_events = Event.objects.filter(
        user=request.user,      # Belongs to the currently logged-in user
        date=today              # Scheduled for today's exact date
    ).exclude(category='birthday')  # Exclude birthdays as they are handled separately

    # Query birthdays that match today's month and day (recurring annually)
    todays_birthdays = Event.objects.filter(
        user=request.user,          # Belongs to current user
        category='birthday',        # Category is 'birthday'
        date__month=today.month,    # Same month as today
        date__day=today.day,        # Same day of the month as today
    )

    # Query upcoming events within the next 7 days, excluding birthdays, ordered by date
    upcoming_events = Event.objects.filter(
        user=request.user,                              # Belongs to current user
        date__gt=today,                                 # Date is strictly greater than today (future)
        date__lte=today + timedelta(days=7),           # Date is within the next 7 calendar days
    ).exclude(category='birthday').order_by('date')[:5] # Order chronologically and limit to top 5

    # Fetch the most recently created or dated diary entry for this user
    latest_entry = DiaryEntry.objects.filter(
        user=request.user
    ).order_by('-date', '-created_at').first()  # Sort by newest date first, then newest creation timestamp

    # Check boolean flag: has the user written a journal entry for today yet?
    has_entry_today = DiaryEntry.objects.filter(user=request.user, date=today).exists()

    # Automatically check for upcoming calendar items and generate notifications if not already generated
    generate_notifications(request.user)

    # Query the 5 most recent unread notifications to display on the dashboard header/widget
    recent_notifications = Notification.objects.filter(
        user=request.user,  # Belongs to current user
        is_read=False       # Notification has not yet been marked as read
    )[:5]                   # Slice top 5 records

    # Bundle all processed data into a context dictionary passed to the template
    context = {
        'today': today,                               # Current date object
        'weather': weather,                           # Weather dictionary from weather service
        'todays_events': todays_events,               # Queryset of today's events
        'todays_birthdays': todays_birthdays,         # Queryset of today's birthdays
        'upcoming_events': upcoming_events,           # Queryset of next 7 days' events
        'latest_entry': latest_entry,                 # Most recent DiaryEntry object or None
        'has_entry_today': has_entry_today,           # True/False flag for today's journal status
        'recent_notifications': recent_notifications, # Queryset of recent unread notifications
    }

    # Render and return the HTML response using the 'core/dashboard.html' template
    return render(request, 'core/dashboard.html', context)

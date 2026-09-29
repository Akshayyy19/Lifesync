# ==============================================================================
# File: planner/views.py
# Description: Calendar views, event CRUD operations, and calendar JSON APIs.
# ==============================================================================

# Import Python's built-in calendar library to calculate months, leap years, and day grids
import calendar as pycalendar

# Import defaultdict to group calendar events by day number without manual key initialization
from collections import defaultdict

# Import date class for constructing and comparing specific calendar dates
from datetime import date

# Import time as min_time to use the earliest time possible (00:00:00) when sorting events without a time
from datetime import time as min_time

# Import messages framework to display user-facing alert notifications (e.g. success, error)
from django.contrib import messages

# Import login_required decorator to enforce authenticated user access
from django.contrib.auth.decorators import login_required

# Import JsonResponse for API endpoints returning data in JSON format for frontend widgets
from django.http import JsonResponse

# Import get_object_or_404 for clean error handling, redirect, and render shortcuts
from django.shortcuts import get_object_or_404, redirect, render

# Import timezone to retrieve current localized date and time
from django.utils import timezone

# Import weather helper functions to fetch live conditions, day timeline, and historical/forecasted weather
from weather.services import (
    get_current_weather,
    get_day_weather_timeline,
    get_weather_for_date,
)

# Import the ModelForm for Event creation/updates
from .forms import EventForm

# Import the Event model representing calendar items
from .models import Event

# List of standard weekday header labels used to render calendar column headers
WEEKDAY_HEADERS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


# ------------------------------------------------------------------------------
# Helper Function: _attach_weather_snapshot
# Purpose: Automatically queries weather for an event's date and stores it in the model.
# ------------------------------------------------------------------------------
def _attach_weather_snapshot(event, user):
    """Best-effort: fetch predicted/actual weather for event date and snapshot it."""
    try:
        # Get user's preferred city or fallback to 'Chennai'
        city = getattr(user.profile, 'city', None) or 'Chennai'
        # Fetch weather data for the specific event date
        weather = get_weather_for_date(city, event.date)
        if weather:
            # Assign temperature, description, and icon from weather response to the event record
            event.weather_temp = weather.get('temp')
            event.weather_condition = weather.get('description')
            event.weather_icon = weather.get('icon')
    except Exception:
        # If the weather API fails or network is unavailable, fail silently without blocking event creation
        pass


# ------------------------------------------------------------------------------
# View: calendar_view
# Purpose: Main interactive calendar supporting Month, Week, Day, and Year views.
# ------------------------------------------------------------------------------
@login_required
def calendar_view(request, year=None, month=None, day=None):
    # Retrieve current local date
    today = timezone.localdate()

    # Cast year parameter to int if passed in URL; default to current year
    year = int(year) if year else today.year

    # Cast month parameter to int if passed in URL; default to current month
    month = int(month) if month else today.month
    
    # If an explicit day is provided in URL, parse it; otherwise default to today if viewing current month
    if day:
        raw_day = int(day)
    elif year == today.year and month == today.month:
        raw_day = today.day
    else:
        raw_day = 1

    # Clamp raw_day to max days in target month (e.g. prevent Feb 31 or Aug 31 -> Sept 30 bugs)
    max_days = pycalendar.monthrange(year, month)[1]
    day_num = min(raw_day, max_days)
    
    # Check the requested view mode from GET query parameters (month, week, day, year)
    view_mode = request.GET.get('view', 'month')

    # Configure Monday as the first day of the week in Python's calendar
    pycalendar.setfirstweekday(pycalendar.MONDAY)

    # Generate a matrix of weeks representing the month grid (days outside the month are marked 0)
    month_grid = pycalendar.monthcalendar(year, month)

    # Query all events and reminders for this specific month belonging to the logged-in user
    events_qs = Event.objects.filter(
        user=request.user, date__year=year, date__month=month,
    ).exclude(category='birthday')

    # Query birthdays for this month (birthdays ignore the year because they recur annually)
    birthdays_qs = Event.objects.filter(
        user=request.user, category='birthday', date__month=month,
    )

    # Group all items by their day of the month using a defaultdict of lists
    events_by_day = defaultdict(list)
    for item in list(events_qs) + list(birthdays_qs):
        events_by_day[item.date.day].append(item)

    # Construct the formatted weeks data structure to pass to the HTML template
    weeks = []
    for week in month_grid:
        week_data = []
        for d in week:
            if d == 0:
                # 0 indicates empty padding days belonging to previous or next month
                week_data.append(None)
            else:
                # Construct date object for the day
                day_date = date(year, month, d)
                # Sort items on this day by scheduled time (all-day items placed first)
                day_items = sorted(events_by_day.get(d, []), key=lambda e: e.time or min_time.min)

                # Find the first valid weather snapshot on this day, if available
                weather_icon = None
                weather_temp = None
                for item in day_items:
                    if item.weather_icon:
                        weather_icon = item.weather_icon
                        weather_temp = item.weather_temp
                        break
                        
                # Append formatted dictionary representing this day cell in the calendar grid
                week_data.append({
                    'day': d,
                    'date': day_date,
                    'items': day_items,
                    'is_today': day_date == today,
                    'weather_icon': weather_icon,
                    'weather_temp': weather_temp,
                })
        weeks.append(week_data)

    # Calculate previous and next month/year pointers for calendar navigation arrows
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    
    # Yearly view data: build 12 mini month calendars if the user switched to 'year' view
    yearly_months = []
    if view_mode == 'year':
        for m in range(1, 13):
            grid = pycalendar.monthcalendar(year, m)
            yearly_months.append({
                'month_name': pycalendar.month_name[m],
                'grid': grid
            })
            
    # Weekly view data: build a 7-day timeline view if the user selected 'week' view
    current_week = []
    if view_mode == 'week':
        today_date = date(year, month, day_num)
        pycalendar.setfirstweekday(pycalendar.MONDAY)
        cal_obj = pycalendar.Calendar(firstweekday=pycalendar.MONDAY)
        # Iterate through calendar weeks until we find the one containing today_date
        for week_dates in cal_obj.monthdatescalendar(year, month):
            if today_date in week_dates:
                # Build day objects for every date in this week
                for d in week_dates:
                    d_events = Event.objects.filter(user=request.user, date=d).exclude(category='birthday')
                    d_birthdays = Event.objects.filter(
                        user=request.user, category='birthday',
                        date__month=d.month, date__day=d.day
                    )
                    day_items = sorted(list(d_events) + list(d_birthdays),
                                       key=lambda e: e.time or min_time.min)
                    wx_icon = next((e.weather_icon for e in day_items if e.weather_icon), None)
                    wx_temp = next((e.weather_temp  for e in day_items if e.weather_icon), None)
                    current_week.append({
                        'day': d.day,
                        'date': d,
                        'items': day_items,
                        'is_today': d == today,
                        'weather_icon': wx_icon,
                        'weather_temp': wx_temp,
                        'other_month': d.month != month,
                    })
                break

    # Daily view data: group events into hourly slots (00:00 to 23:00) if 'day' view is active
    current_day = None
    if view_mode == 'day':
        current_day = date(year, month, day_num)
        events_today = Event.objects.filter(user=request.user, date=current_day).exclude(category='birthday')
        birthdays_today = Event.objects.filter(
            user=request.user, category='birthday', date__month=current_day.month, date__day=current_day.day
        )
        
        events_by_hour = defaultdict(list)
        all_day_events = []
        for e in list(events_today) + list(birthdays_today):
            if e.time:
                events_by_hour[e.time.hour].append(e)
            else:
                all_day_events.append(e)
        
        # Build 24-hour array representing the daily schedule breakdown
        hours = []
        for h in range(24):
            hours.append({
                'hour': h,
                'label': f"{h:02d}:00",
                'events': events_by_hour[h]
            })
            
        context_day = {
            'all_day_events': all_day_events,
            'hours': hours,
            'current_day': current_day
        }
    else:
        context_day = {}

    # Fetch today's live weather to show a badge in the calendar header
    city = getattr(request.user.profile, 'city', None) or 'Chennai'
    try:
        today_weather = get_current_weather(city)
    except Exception:
        today_weather = None

    # Bundle all calendar variables into the context dictionary
    context = {
        'weeks': weeks,
        'weekday_headers': WEEKDAY_HEADERS,
        'month_name': pycalendar.month_name[month],
        'year': year,
        'month': month,
        'day': day_num,
        'today': today,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'is_current_month': (year == today.year and month == today.month),
        'view_mode': view_mode,
        'yearly_months': yearly_months,
        'current_week': current_week,
        'today_weather': today_weather,
        'city': city,
        **context_day
    }
    # Render the interactive calendar template
    return render(request, 'planner/calendar.html', context)


# ------------------------------------------------------------------------------
# View: day_detail
# Purpose: Detailed single-day breakdown showing events, birthdays, and weather.
# ------------------------------------------------------------------------------
@login_required
def day_detail(request, year, month, day):
    # Construct date object from URL segments
    day_date = date(int(year), int(month), int(day))

    # Query events for this specific date
    events = Event.objects.filter(user=request.user, date=day_date).exclude(category='birthday')

    # Query birthdays recurring on this month and day
    birthdays = Event.objects.filter(
        user=request.user, category='birthday',
        date__month=day_date.month, date__day=day_date.day,
    )

    # Get user city and fetch detailed weather metrics & hourly timeline for this day
    city = getattr(request.user.profile, 'city', None) or 'Chennai'
    day_weather = get_weather_for_date(city, day_date)
    day_timeline = get_day_weather_timeline(city, day_date)

    context = {
        'date': day_date,
        'events': events,
        'birthdays': birthdays,
        'day_weather': day_weather,
        'day_timeline': day_timeline,
        'city': city,
    }
    return render(request, 'planner/day_detail.html', context)


# ------------------------------------------------------------------------------
# View: event_create
# Purpose: Create a new calendar event, birthday, or reminder.
# ------------------------------------------------------------------------------
@login_required
def event_create(request):
    if request.method == 'POST':
        # Bind submitted POST data to EventForm
        form = EventForm(request.POST)
        if form.is_valid():
            # Create model instance without committing to database yet
            event = form.save(commit=False)
            # Assign current user as owner
            event.user = request.user
            # Attach weather snapshot for this event's date
            _attach_weather_snapshot(event, request.user)
            # Save event to database
            event.save()
            # Show success message
            messages.success(request, f'"{event.title}" was added to your calendar.')
            # Redirect to the day detail view of the event's date
            return redirect('planner:day_detail', year=event.date.year, month=event.date.month, day=event.date.day)
    else:
        # Populate initial form values from GET parameters (e.g. pre-fill date or category)
        initial = {}
        date_param = request.GET.get('date')
        category_param = request.GET.get('category')
        if date_param:
            initial['date'] = date_param
        if category_param:
            initial['category'] = category_param
        form = EventForm(initial=initial)

    # Fetch predicted weather for the chosen target date to show a preview while creating
    target_date_str = form.initial.get('date') or timezone.localdate().strftime('%Y-%m-%d')
    city = getattr(request.user.profile, 'city', None) or 'Chennai'
    predicted_weather = get_weather_for_date(city, target_date_str)

    return render(request, 'planner/event_form.html', {
        'form': form,
        'action': 'Add',
        'predicted_weather': predicted_weather,
        'target_date': target_date_str,
    })


# ------------------------------------------------------------------------------
# View: event_update
# Purpose: Edit an existing calendar event.
# ------------------------------------------------------------------------------
@login_required
def event_update(request, pk):
    # Fetch the event by primary key, verifying that it belongs to the current user
    event = get_object_or_404(Event, pk=pk, user=request.user)

    if request.method == 'POST':
        # Bind POST data to the existing event instance
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            updated_event = form.save(commit=False)
            # Update weather snapshot if date changed
            _attach_weather_snapshot(updated_event, request.user)
            updated_event.save()
            messages.success(request, f'"{updated_event.title}" was updated.')
            return redirect('planner:day_detail', year=updated_event.date.year, month=updated_event.date.month, day=updated_event.date.day)
    else:
        # Pre-populate form with existing event attributes
        form = EventForm(instance=event)

    city = getattr(request.user.profile, 'city', None) or 'Chennai'
    predicted_weather = get_weather_for_date(city, event.date)

    return render(request, 'planner/event_form.html', {
        'form': form,
        'action': 'Edit',
        'event': event,
        'predicted_weather': predicted_weather,
        'target_date': event.date,
    })


# ------------------------------------------------------------------------------
# View: event_delete
# Purpose: Delete an existing calendar event after user confirmation.
# ------------------------------------------------------------------------------
@login_required
def event_delete(request, pk):
    # Fetch the event ensuring it belongs to the requesting user
    event = get_object_or_404(Event, pk=pk, user=request.user)

    if request.method == 'POST':
        # Save date attributes before deleting so we can redirect to that day
        title, year, month, day = event.title, event.date.year, event.date.month, event.date.day
        # Delete the event from database
        event.delete()
        messages.success(request, f'"{title}" was deleted.')
        return redirect('planner:day_detail', year=year, month=month, day=day)

    # Show confirmation prompt template
    return render(request, 'planner/event_confirm_delete.html', {'event': event})


# ------------------------------------------------------------------------------
# API View: calendar_events_api
# Purpose: Returns JSON array of calendar events for frontend JavaScript calendar libraries.
# ------------------------------------------------------------------------------
@login_required
def calendar_events_api(request):
    """Returns JSON array of events for FullCalendar."""
    # Extract optional date range filter parameters from GET request
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    
    # Query all events belonging to the current user
    qs = Event.objects.filter(user=request.user)
    
    # Filter queryset by date range if provided
    if start_str and end_str:
        start_date = start_str[:10]
        end_date = end_str[:10]
        qs = qs.filter(date__range=[start_date, end_date])
    
    # Format events into JSON-friendly dictionary objects
    events_data = []
    for e in qs:
        # Set color badge based on event category
        color = '#3b82f6' # Blue for standard events
        if e.category == 'birthday': 
            color = '#f472b6' # Pink for birthdays
        elif e.category == 'reminder': 
            color = '#34d399' # Green for reminders

        start_time = f"T{e.time.strftime('%H:%M:%S')}" if e.time else ""
        
        events_data.append({
            'id': e.id,
            'title': e.title,
            'start': f"{e.date}{start_time}",
            'allDay': e.time is None,
            'backgroundColor': color,
            'borderColor': 'transparent',
            'extendedProps': {
                'category': e.category,
                'location': getattr(e, 'location', ''),
            }
        })
        
    return JsonResponse(events_data, safe=False)


# ------------------------------------------------------------------------------
# API View: weather_api
# Purpose: Returns JSON weather metrics for a specified date query.
# ------------------------------------------------------------------------------
@login_required
def weather_api(request):
    """Returns JSON weather for a given date."""
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'error': 'date required'}, status=400)
    
    city = getattr(request.user.profile, 'city', None) or 'Chennai'
    try:
        from weather.services import get_weather_for_date
        weather = get_weather_for_date(city, date_str)
        if weather:
            return JsonResponse(weather)
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

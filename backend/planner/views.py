import calendar as pycalendar
from collections import defaultdict
from datetime import date
from datetime import time as min_time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from weather.services import get_day_weather_timeline, get_weather_for_date

from .forms import EventForm
from .models import Event

WEEKDAY_HEADERS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def _attach_weather_snapshot(event, user):
    """Best-effort: fetch predicted/actual weather for event date and snapshot it."""
    try:
        city = getattr(user.profile, 'city', None) or 'Chennai'
        weather = get_weather_for_date(city, event.date)
        if weather:
            event.weather_temp = weather.get('temp')
            event.weather_condition = weather.get('description')
            event.weather_icon = weather.get('icon')
    except Exception:
        pass


@login_required
def calendar_view(request, year=None, month=None):
    today = timezone.localdate()
    year = int(year) if year else today.year
    month = int(month) if month else today.month

    pycalendar.setfirstweekday(pycalendar.MONDAY)
    month_grid = pycalendar.monthcalendar(year, month)

    # Ordinary events + reminders: match the exact year/month.
    events_qs = Event.objects.filter(
        user=request.user, date__year=year, date__month=month,
    ).exclude(category='birthday')

    # Birthdays recur every year, so match on month only (ignore the stored year).
    birthdays_qs = Event.objects.filter(
        user=request.user, category='birthday', date__month=month,
    )

    events_by_day = defaultdict(list)
    for item in list(events_qs) + list(birthdays_qs):
        events_by_day[item.date.day].append(item)

    weeks = []
    for week in month_grid:
        week_data = []
        for day in week:
            if day == 0:
                week_data.append(None)
            else:
                day_date = date(year, month, day)
                week_data.append({
                    'day': day,
                    'date': day_date,
                    'items': sorted(events_by_day.get(day, []), key=lambda e: e.time or min_time.min),
                    'is_today': day_date == today,
                })
        weeks.append(week_data)

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    context = {
        'weeks': weeks,
        'weekday_headers': WEEKDAY_HEADERS,
        'month_name': pycalendar.month_name[month],
        'year': year,
        'month': month,
        'today': today,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'is_current_month': (year == today.year and month == today.month),
    }
    return render(request, 'planner/calendar.html', context)


@login_required
def day_detail(request, year, month, day):
    day_date = date(int(year), int(month), int(day))

    events = Event.objects.filter(user=request.user, date=day_date).exclude(category='birthday')
    birthdays = Event.objects.filter(
        user=request.user, category='birthday',
        date__month=day_date.month, date__day=day_date.day,
    )

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


@login_required
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.user = request.user
            _attach_weather_snapshot(event, request.user)
            event.save()
            messages.success(request, f'"{event.title}" was added to your calendar.')
            return redirect('planner:day_detail', year=event.date.year, month=event.date.month, day=event.date.day)
    else:
        initial = {}
        date_param = request.GET.get('date')
        category_param = request.GET.get('category')
        if date_param:
            initial['date'] = date_param
        if category_param:
            initial['category'] = category_param
        form = EventForm(initial=initial)

    target_date_str = form.initial.get('date') or timezone.localdate().strftime('%Y-%m-%d')
    city = getattr(request.user.profile, 'city', None) or 'Chennai'
    predicted_weather = get_weather_for_date(city, target_date_str)

    return render(request, 'planner/event_form.html', {
        'form': form,
        'action': 'Add',
        'predicted_weather': predicted_weather,
        'target_date': target_date_str,
    })


@login_required
def event_update(request, pk):
    event = get_object_or_404(Event, pk=pk, user=request.user)

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            updated_event = form.save(commit=False)
            _attach_weather_snapshot(updated_event, request.user)
            updated_event.save()
            messages.success(request, f'"{updated_event.title}" was updated.')
            return redirect('planner:day_detail', year=updated_event.date.year, month=updated_event.date.month, day=updated_event.date.day)
    else:
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


@login_required
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk, user=request.user)

    if request.method == 'POST':
        title, year, month, day = event.title, event.date.year, event.date.month, event.date.day
        event.delete()
        messages.success(request, f'"{title}" was deleted.')
        return redirect('planner:day_detail', year=year, month=month, day=day)

    return render(request, 'planner/event_confirm_delete.html', {'event': event})

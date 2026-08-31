import calendar as pycalendar
from collections import defaultdict
from datetime import date
from datetime import time as min_time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from weather.services import get_current_weather, get_day_weather_timeline, get_weather_for_date

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
def calendar_view(request, year=None, month=None, day=None):
    today = timezone.localdate()
    year = int(year) if year else today.year
    month = int(month) if month else today.month
    
    # If explicit day is provided, use it; if viewing current month, default to today.day; else default to day 1
    if day:
        raw_day = int(day)
    elif year == today.year and month == today.month:
        raw_day = today.day
    else:
        raw_day = 1

    # Clamp raw_day to max days in target month (e.g. Aug 31 -> Sept 30, or Feb 28)
    max_days = pycalendar.monthrange(year, month)[1]
    day_num = min(raw_day, max_days)
    
    view_mode = request.GET.get('view', 'month')


    pycalendar.setfirstweekday(pycalendar.MONDAY)
    month_grid = pycalendar.monthcalendar(year, month)

    events_qs = Event.objects.filter(
        user=request.user, date__year=year, date__month=month,
    ).exclude(category='birthday')

    birthdays_qs = Event.objects.filter(
        user=request.user, category='birthday', date__month=month,
    )

    events_by_day = defaultdict(list)
    for item in list(events_qs) + list(birthdays_qs):
        events_by_day[item.date.day].append(item)

    weeks = []
    for week in month_grid:
        week_data = []
        for d in week:
            if d == 0:
                week_data.append(None)
            else:
                day_date = date(year, month, d)
                day_items = sorted(events_by_day.get(d, []), key=lambda e: e.time or min_time.min)
                # Find the first valid weather icon for this day, if any
                weather_icon = None
                weather_temp = None
                for item in day_items:
                    if item.weather_icon:
                        weather_icon = item.weather_icon
                        weather_temp = item.weather_temp
                        break
                        
                week_data.append({
                    'day': d,
                    'date': day_date,
                    'items': day_items,
                    'is_today': day_date == today,
                    'weather_icon': weather_icon,
                    'weather_temp': weather_temp,
                })
        weeks.append(week_data)

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    
    # Yearly data
    yearly_months = []
    if view_mode == 'year':
        for m in range(1, 13):
            grid = pycalendar.monthcalendar(year, m)
            yearly_months.append({
                'month_name': pycalendar.month_name[m],
                'grid': grid
            })
            
    # Weekly data — use monthdatescalendar so we get real dates even for adjacent-month days
    current_week = []
    if view_mode == 'week':
        today_date = date(year, month, day_num)
        pycalendar.setfirstweekday(pycalendar.MONDAY)
        cal_obj = pycalendar.Calendar(firstweekday=pycalendar.MONDAY)
        for week_dates in cal_obj.monthdatescalendar(year, month):
            if today_date in week_dates:
                # Build a full day-object for every date in this week
                for d in week_dates:
                    d_events = Event.objects.filter(user=request.user, date=d).exclude(category='birthday')
                    d_birthdays = Event.objects.filter(user=request.user, category='birthday',
                                                       date__month=d.month, date__day=d.day)
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

            
    # Daily data
    current_day = None
    if view_mode == 'day':
        current_day = date(year, month, day_num)
        events_today = Event.objects.filter(user=request.user, date=current_day).exclude(category='birthday')
        birthdays_today = Event.objects.filter(user=request.user, category='birthday', date__month=current_day.month, date__day=current_day.day)
        
        events_by_hour = defaultdict(list)
        all_day_events = []
        for e in list(events_today) + list(birthdays_today):
            if e.time:
                events_by_hour[e.time.hour].append(e)
            else:
                all_day_events.append(e)
        
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

    # Fetch today's LIVE weather for the calendar header badge
    city = getattr(request.user.profile, 'city', None) or 'Chennai'
    try:
        today_weather = get_current_weather(city)
    except Exception:
        today_weather = None

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

from django.http import JsonResponse

@login_required
def calendar_events_api(request):
    """Returns JSON array of events for FullCalendar."""
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    
    qs = Event.objects.filter(user=request.user)
    
    if start_str and end_str:
        start_date = start_str[:10]
        end_date = end_str[:10]
        qs = qs.filter(date__range=[start_date, end_date])
    
    events_data = []
    for e in qs:
        color = '#3b82f6' # default event
        if e.category == 'birthday': color = '#f472b6'
        elif e.category == 'reminder': color = '#34d399'

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


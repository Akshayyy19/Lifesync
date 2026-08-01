from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .services import (
    get_8_day_cards,
    get_air_quality_for_date,
    get_current_weather,
    get_day_weather_timeline,
    get_forecast,
)


@login_required
def weather_index(request):
    default_city = getattr(request.user.profile, 'city', None) or 'Chennai'
    city = request.GET.get('city', '').strip() or default_city
    date_str = request.GET.get('date', '').strip() or timezone.localdate().strftime('%Y-%m-%d')
    active_tab = request.GET.get('tab', 'overview').lower().strip()
    active_unit = request.GET.get('unit', 'C').upper().strip()

    current = get_current_weather(city)
    day_timeline = get_day_weather_timeline(city, date_str) if current else None
    air_quality = get_air_quality_for_date(city, date_str) if current else None
    cards_strip = get_8_day_cards(city, date_str) if current else []

    error = None
    if current is None:
        error = f'Could not find weather for "{city}". Check the spelling or network connection and try again.'

    context = {
        'current': current,
        'day_timeline': day_timeline,
        'air_quality': air_quality,
        'cards_strip': cards_strip,
        'timeline_data': day_timeline['timeline'] if day_timeline else [],
        'aqi_data': air_quality['timeline'] if air_quality else [],
        'city_query': city,
        'date_query': date_str,
        'active_tab': active_tab,
        'active_unit': active_unit,
        'default_city': default_city,
        'error': error,
    }
    return render(request, 'weather/weather.html', context)

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .services import (
    get_8_day_cards,
    get_air_quality_for_date,
    get_current_weather,
    get_day_weather_timeline,
    get_forecast,
    search_city_suggestions,
)


@login_required
def weather_index(request):
    default_city = getattr(request.user.profile, 'city', None) or 'Chennai'

    # Retrieve saved location buttons from session
    saved_cities = request.session.get('saved_weather_cities', [])

    # Handle removing a location button
    remove_city = request.GET.get('remove_city', '').strip()
    if remove_city:
        saved_cities = [c for c in saved_cities if c.lower() != remove_city.lower()]
        request.session['saved_weather_cities'] = saved_cities
        date_str = request.GET.get('date', '').strip()
        tab_str = request.GET.get('tab', 'overview').strip()
        unit_str = request.GET.get('unit', 'C').strip()
        return redirect(f"{request.path}?city={default_city}&date={date_str}&tab={tab_str}&unit={unit_str}")

    is_adding_location = bool(request.GET.get('add_location'))
    city = request.GET.get('city', '').strip() or default_city
    date_str = request.GET.get('date', '').strip() or timezone.localdate().strftime('%Y-%m-%d')
    active_tab = request.GET.get('tab', 'overview').lower().strip()
    active_unit = request.GET.get('unit', 'C').upper().strip()

    current = get_current_weather(city)

    error = None
    if current and current.get('is_country'):
        error = f'"{city}" is a country, not a city. Please search for a specific city (e.g. New Delhi, Mumbai, London, Paris).'
        current = None
        day_timeline = None
        air_quality = None
        cards_strip = []
    else:
        day_timeline = get_day_weather_timeline(city, date_str) if current else None
        air_quality = get_air_quality_for_date(city, date_str) if current else None
        cards_strip = get_8_day_cards(city, date_str) if current else []

    if current is None and not error:
        error = f'Could not find weather for "{city}". Check the spelling or network connection and try again.'

    # ONLY add location button if user explicitly added via Add Location modal AND saved_cities < 3
    if is_adding_location and current and not current.get('is_country') and city.lower() != default_city.lower():
        if len(saved_cities) < 3:
            city_display_name = current.get('city') or city.title()
            if not any(c.lower() == city_display_name.lower() for c in saved_cities):
                saved_cities.append(city_display_name)
                request.session['saved_weather_cities'] = saved_cities

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
        'saved_cities': saved_cities,
        'is_default': (city.lower() == default_city.lower()),
        'error': error,
    }
    return render(request, 'weather/weather.html', context)


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
        'saved_cities': saved_cities,
        'is_default': (city.lower() == default_city.lower()),
        'error': error,
    }
    return render(request, 'weather/weather.html', context)



@login_required
def city_suggestions_api(request):
    """Returns JSON array of location recommendations for autocomplete."""
    query = request.GET.get('q', '').strip()
    suggestions = search_city_suggestions(query)
    return JsonResponse({'results': suggestions})


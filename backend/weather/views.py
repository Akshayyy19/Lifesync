# ==============================================================================
# File: weather/views.py
# Description: Views handling the weather dashboard, city search, and timelines.
# ==============================================================================

# Import messages framework for user flash notices
from django.contrib import messages

# Import login_required decorator to ensure only authenticated users access weather
from django.contrib.auth.decorators import login_required

# Import JsonResponse for delivering autocomplete search results as JSON
from django.http import JsonResponse

# Import redirect and render helper functions
from django.shortcuts import redirect, render

# Import timezone module to work with local calendar dates
from django.utils import timezone

# Import weather backend services that interface with OpenWeatherMap and Open-Meteo
from .services import (
    get_8_day_cards,            # Fetches 15-day multi-day weather cards
    get_air_quality_for_date,   # Fetches AQI, PM2.5, PM10, ozone, and CO metrics
    get_current_weather,        # Fetches current temperature, humidity, wind, and sky condition
    get_day_weather_timeline,   # Fetches hourly breakdown of temperature and precipitation for a date
    get_forecast,               # Fetches multi-day general forecast
    search_city_suggestions,    # Geocoding search autocomplete for cities worldwide
)


# ------------------------------------------------------------------------------
# View: weather_index
# Purpose: Main weather dashboard displaying current weather, hourly timeline, 
#          air quality metrics, and multi-day cards.
# ------------------------------------------------------------------------------
@login_required
def weather_index(request):
    # Fetch user's home/default city from their Profile model; fallback to 'Chennai'
    default_city = getattr(getattr(request.user, 'profile', None), 'city', None) or 'Chennai'

    # Retrieve previously saved city quick-buttons stored in the user's session
    saved_cities = request.session.get('saved_weather_cities', [])

    # Check if the user clicked the 'remove' button on one of their saved location tags
    remove_city = request.GET.get('remove_city', '').strip()
    if remove_city:
        # Filter out the removed city name from the session list
        saved_cities = [c for c in saved_cities if c.lower() != remove_city.lower()]
        request.session['saved_weather_cities'] = saved_cities
        # Maintain current view parameters while removing the query tag
        date_str = request.GET.get('date', '').strip()
        tab_str = request.GET.get('tab', 'overview').strip()
        unit_str = request.GET.get('unit', 'C').strip()
        return redirect(f"{request.path}?city={default_city}&date={date_str}&tab={tab_str}&unit={unit_str}")

    # Flag determining whether the user clicked "Add Location" to bookmark a city
    is_adding_location = bool(request.GET.get('add_location'))

    # Extract target city from GET parameters, defaulting to the user's saved default city
    city = request.GET.get('city', '').strip() or default_city

    # Extract target date parameter or default to today's local date (YYYY-MM-DD)
    date_str = request.GET.get('date', '').strip() or timezone.localdate().strftime('%Y-%m-%d')

    # Extract active UI tab: overview, precipitation, wind, aqi, humidity, uv, etc.
    active_tab = request.GET.get('tab', 'overview').lower().strip()

    # Temperature unit preference: Celsius ('C') or Fahrenheit ('F')
    active_unit = request.GET.get('unit', 'C').upper().strip()

    # Query current weather data from our service layer
    current = get_current_weather(city)

    # Validate that the entered search term isn't a whole country (e.g. searching "India" instead of a city)
    error = None
    if current and current.get('is_country'):
        error = f'"{city}" is a country, not a city. Please search for a specific city (e.g. New Delhi, Mumbai, London, Paris).'
        current = None
        day_timeline = None
        air_quality = None
        cards_strip = []
    else:
        # Fetch detailed hourly timeline for the chosen date
        day_timeline = get_day_weather_timeline(city, date_str) if current else None
        # Fetch detailed air quality data for the chosen date
        air_quality = get_air_quality_for_date(city, date_str) if current else None
        # Fetch 15-day scrollable weather cards strip centered on the chosen date
        cards_strip = get_8_day_cards(city, date_str) if current else []

    # Display an error message if the weather service could not find the city
    if current is None and not error:
        error = f'Could not find weather for "{city}". Check the spelling or network connection and try again.'

    # Handle bookmarking location into session if requested and quota (< 3 cities) is respected
    if is_adding_location and current and not current.get('is_country') and city.lower() != default_city.lower():
        if len(saved_cities) < 3:
            city_display_name = current.get('city') or city.title()
            if not any(c.lower() == city_display_name.lower() for c in saved_cities):
                saved_cities.append(city_display_name)
                request.session['saved_weather_cities'] = saved_cities

    # Prepare template context payload
    context = {
        'current': current,                                             # Current weather data dictionary
        'weather': current,                                             # Used by base.html sky header & theme
        'day_timeline': day_timeline,                                   # Day timeline dictionary
        'air_quality': air_quality,                                     # Air quality metrics dictionary
        'cards_strip': cards_strip,                                     # List of multi-day forecast cards
        'timeline_data': day_timeline['timeline'] if day_timeline else [], # Hourly timeline array
        'aqi_data': air_quality['timeline'] if air_quality else [],       # Hourly AQI array
        'city_query': city,                                             # The currently queried city
        'date_query': date_str,                                         # The currently queried date
        'active_tab': active_tab,                                       # Active UI tab
        'active_unit': active_unit,                                     # Active temperature unit ('C' or 'F')
        'default_city': default_city,                                   # User's primary default city
        'saved_cities': saved_cities,                                   # List of user's bookmarked cities
        'is_default': (city.lower() == default_city.lower()),          # Flag whether viewing default city
        'error': error,                                                 # Error message string if any
    }
    # Render the weather dashboard template
    return render(request, 'weather/weather.html', context)


# ------------------------------------------------------------------------------
# API View: city_suggestions_api
# Purpose: Provides real-time autocomplete suggestions as the user types a city name.
# ------------------------------------------------------------------------------
@login_required
def city_suggestions_api(request):
    """Returns JSON array of location recommendations for autocomplete."""
    # Extract search query string 'q' from GET request
    query = request.GET.get('q', '').strip()
    # Search for matching cities using Open-Meteo geocoding service
    suggestions = search_city_suggestions(query)
    # Return JSON response containing the list of matching city objects
    return JsonResponse({'results': suggestions})

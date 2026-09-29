"""
Weather service with dual provider support & Open-Meteo Air Quality integration.
Provides MSN-Weather style multi-tab metrics: Overview, Precipitation, Wind,
Air Quality, Humidity, Pressure, UV, and Visibility with zero-lag batching & caching.
"""
# Import the Python requests library to execute HTTP GET requests to external weather APIs
import requests

# Import datetime and timedelta to parse dates and calculate forecast offsets
from datetime import datetime, timedelta, timezone as dt_timezone

# Import Django settings to access OPENWEATHERMAP_API_KEY from environment/.env
from django.conf import settings

# Import timezone module to ensure server operations follow localized dates
from django.utils import timezone

# Base endpoint for OpenWeatherMap API v2.5
BASE_URL_OWM = 'https://api.openweathermap.org/data/2.5'

# Geocoding endpoint to convert human-readable city names into latitude/longitude coordinates
GEO_URL_OPENMETEO = 'https://geocoding-api.open-meteo.com/v1/search'

# Note: api.open-meteo.com and archive-api.open-meteo.com may be blocked on some networks.
# historical-forecast-api.open-meteo.com serves both historical and forecast data and is accessible.
FORECAST_URL_OPENMETEO = 'https://historical-forecast-api.open-meteo.com/v1/forecast'
ARCHIVE_URL_OPENMETEO = 'https://historical-forecast-api.open-meteo.com/v1/forecast'

# Endpoint for real-time and forecasted air quality metrics (AQI, particulate matter)
AIR_QUALITY_URL_OPENMETEO = 'https://air-quality-api.open-meteo.com/v1/air-quality'

# Maximum seconds to wait for an API HTTP response before timing out
REQUEST_TIMEOUT = 10

# In-memory dictionary caches to store API responses and guarantee 0ms latency for repeated requests
GEO_CACHE = {}         # Caches {city_name: {lat, lon, country, ...}}
TIMELINE_CACHE = {}    # Caches {city_date: hourly_timeline_data}
AQI_CACHE = {}         # Caches {city_date: air_quality_metrics}
CARDS_CACHE = {}       # Caches {city_date_15: multi_day_cards}

# World Meteorological Organization (WMO) weather code mapping:
# code: (human_readable_description, internal_condition_name, default_icon_code)
WMO_WEATHER_CODES = {
    0: ("Clear sky", "sunny", "01"),
    1: ("Mainly clear", "sunny", "01"),
    2: ("Partly cloudy", "cloudy", "02"),
    3: ("Overcast", "cloudy", "04"),
    45: ("Foggy", "misty", "50"),
    48: ("Rime fog", "misty", "50"),
    51: ("Light drizzle", "rainy", "09"),
    53: ("Moderate drizzle", "rainy", "09"),
    55: ("Dense drizzle", "rainy", "09"),
    56: ("Freezing drizzle", "snowy", "13"),
    57: ("Dense freezing drizzle", "snowy", "13"),
    61: ("Slight rain", "rainy", "10"),
    63: ("Moderate rain", "rainy", "10"),
    65: ("Heavy rain", "rainy", "10"),
    66: ("Freezing rain", "snowy", "13"),
    67: ("Heavy freezing rain", "snowy", "13"),
    71: ("Slight snow", "snowy", "13"),
    73: ("Moderate snow", "snowy", "13"),
    75: ("Heavy snow", "snowy", "13"),
    77: ("Snow grains", "snowy", "13"),
    80: ("Slight rain showers", "rainy", "09"),
    81: ("Moderate rain showers", "rainy", "09"),
    82: ("Violent rain showers", "rainy", "09"),
    85: ("Slight snow showers", "snowy", "13"),
    86: ("Heavy snow showers", "snowy", "13"),
    95: ("Thunderstorm", "thunderstorm", "11"),
    96: ("Thunderstorm with hail", "thunderstorm", "11"),
    99: ("Thunderstorm with heavy hail", "thunderstorm", "11"),
}


def _icon_to_condition(icon_code):
    """Maps an icon code prefix into a simplified UI condition category."""
    if not icon_code:
        return 'cloudy'
    code = icon_code[:2]
    is_day = icon_code.endswith('d')
    mapping = {
        '01': 'sunny' if is_day else 'clear-night',
        '02': 'cloudy', '03': 'cloudy', '04': 'cloudy',
        '09': 'rainy', '10': 'rainy',
        '11': 'thunderstorm',
        '13': 'snowy',
        '50': 'misty',
    }
    return mapping.get(code, 'cloudy')


def _resolve_condition(base_cond, is_day, temp=20, feels_like=None, precipitation=0.0, weather_code=None):
    """
    Intelligently maps weather metrics to exact UI theme condition keys:
    - 'hot-summer': Hot clear or sunny day (>= 29°C), or negligible drizzle during hot summer sun.
    - 'sun-rain-mix': Daytime sun and rain mixed together (sunshower: drizzle / light rain / showers with sun).
    - 'rainy': Moderate or heavy rain.
    - 'cloudy': Overcast or mostly cloudy skies.
    - 'sunny': Pleasant clear daytime (< 29°C).
    - 'clear-night': Clear starry night.
    - 'thunderstorm': Thunder, lightning and heavy showers.
    - 'snowy': Snow or freezing precipitation.
    - 'misty': Fog, mist, or haze.
    """
    effective_temp = temp if temp is not None else 20
    effective_feels = feels_like if feels_like is not None else effective_temp
    precip = float(precipitation) if precipitation is not None else 0.0

    if base_cond in ('thunderstorm', 'snowy', 'misty'):
        return base_cond

    if is_day:
        is_rain_code = (base_cond == 'rainy') or (weather_code in (51, 53, 55, 61, 63, 65, 80, 81, 82))
        if is_rain_code:
            # If precipitation is tiny/trace (<= 0.2mm) and temp is hot (temp >= 29 or feels_like >= 31),
            # this is a normal hot summer day where tropical radar/forecast models report trace humidity.
            if precip <= 0.2 and (effective_temp >= 29 or effective_feels >= 31):
                return 'hot-summer'
            # If light drizzle / light showers during the day (< 2.0 mm or codes 51/53/80), it's a sun & rain mix!
            if precip < 2.0 or weather_code in (51, 53, 80):
                return 'sun-rain-mix'
            # Moderate to heavy rain
            return 'rainy'

        if base_cond in ('sunny', 'clear'):
            if effective_temp >= 29 or effective_feels >= 31:
                return 'hot-summer'
            return 'sunny'

        if base_cond == 'cloudy':
            if weather_code in (1, 2) and (effective_temp >= 31 or effective_feels >= 34):
                return 'hot-summer'
            return 'cloudy'

        return 'sunny'
    else:
        # Night
        is_rain_code = (base_cond == 'rainy') or (weather_code in (51, 53, 55, 61, 63, 65, 80, 81, 82))
        if is_rain_code:
            if precip <= 0.2 and effective_temp >= 28:
                return 'clear-night'
            return 'rainy'
        if base_cond == 'cloudy':
            return 'cloudy'
        return 'clear-night'


def _format_time_12h(dt):
    """Format a datetime as '6:15 AM' without strftime's platform-specific '%-I'
    (that directive raises ValueError on Windows, which is what this project is developed on)."""
    hour12 = dt.hour % 12 or 12
    ampm = 'AM' if dt.hour < 12 else 'PM'
    return f'{hour12}:{dt.minute:02d} {ampm}'


# ------------------------------------------------------------------------------
# Primary Function: get_current_weather
# Strategy: Dual-provider fallback. Tries OpenWeatherMap first if API key exists;
#           falls back to Open-Meteo if key is missing or request fails.
# ------------------------------------------------------------------------------
def get_current_weather(city):
    # Return None immediately if city argument is empty or blank
    if not city or not city.strip():
        return None

    # Clean whitespace from city query
    city = city.strip()
    # Read API key from settings (configured in .env)
    api_key = getattr(settings, 'OPENWEATHERMAP_API_KEY', None)

    # If an API key is available, attempt fetching from OpenWeatherMap first
    if api_key:
        result = _get_current_weather_owm(city, api_key)
        if result:
            return result

    # Fallback to Open-Meteo (keyless free weather service)
    return _get_current_weather_openmeteo(city)


# ------------------------------------------------------------------------------
# Primary Function: get_forecast
# Strategy: Dual-provider fallback for multi-day forecast.
# ------------------------------------------------------------------------------
def get_forecast(city, days=5):
    # Validate input
    if not city or not city.strip():
        return None

    city = city.strip()
    api_key = getattr(settings, 'OPENWEATHERMAP_API_KEY', None)

    # Try OpenWeatherMap 5-day forecast first if key is present
    if api_key:
        result = _get_forecast_owm(city, api_key, days=days)
        if result:
            return result

    # Fallback to Open-Meteo forecast API
    return _get_forecast_openmeteo(city, days=days)


# Feature codes returned by geocoding APIs that signify a country rather than a city
COUNTRY_FEATURE_CODES = {'PCLI', 'PCLD', 'PCL', 'PCLS', 'TERR', 'CONT'}


def _geocode_openmeteo(city):
    """Fast geocoding: check memory cache -> Open-Meteo -> Nominatim (only if needed)."""
    if not city:
        return None

    cache_key = city.lower().strip()
    if cache_key in GEO_CACHE:
        return GEO_CACHE[cache_key]

    clean_name = city.split(',')[0].strip()

    # Fast Open-Meteo Geocoding (~80ms)
    try:
        response = requests.get(
            GEO_URL_OPENMETEO,
            params={'name': clean_name, 'count': 5, 'language': 'en', 'format': 'json'},
            timeout=3,
        )
        if response.status_code == 200:
            data = response.json()
            results = data.get('results') or []
            if results:
                loc = results[0]
                feature_code = loc.get('feature_code', '')

                # If top result is a country entity (e.g., India, Japan, France)
                if feature_code in COUNTRY_FEATURE_CODES:

                    if loc.get('name', '').lower() == clean_name.lower() or loc.get('country', '').lower() == clean_name.lower():
                        res = {
                            'name': loc.get('name', clean_name),
                            'country': loc.get('country', loc.get('country_code', '')),
                            'lat': loc.get('latitude'),
                            'lon': loc.get('longitude'),
                            'is_country': True,
                        }
                        GEO_CACHE[cache_key] = res
                        return res

                    # Otherwise try to find a matching city/populated place
                    city_match = next((r for r in results if r.get('feature_code', '') not in COUNTRY_FEATURE_CODES), None)
                    if city_match:
                        loc = city_match
                    else:
                        res = {
                            'name': loc.get('name', clean_name),
                            'country': loc.get('country', loc.get('country_code', '')),
                            'lat': loc.get('latitude'),
                            'lon': loc.get('longitude'),
                            'is_country': True,
                        }
                        GEO_CACHE[cache_key] = res
                        return res


                res = {
                    'name': loc.get('name', clean_name),
                    'country': loc.get('country', loc.get('country_code', '')),
                    'lat': loc.get('latitude'),
                    'lon': loc.get('longitude'),
                    'is_country': False,
                }
                GEO_CACHE[cache_key] = res
                return res
    except Exception:
        pass

    # Fallback to OpenStreetMap Nominatim
    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': city, 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'LifeSyncApp/1.0'},
            timeout=3,
        )
        if response.status_code == 200:
            results = response.json()
            if results:
                loc = results[0]
                display_parts = loc.get('display_name', '').split(',')
                country_name = display_parts[-1].strip() if display_parts else ''
                res = {
                    'name': loc.get('name', clean_name).title(),
                    'country': country_name,
                    'lat': float(loc.get('lat')),
                    'lon': float(loc.get('lon')),
                    'is_country': False,
                }
                GEO_CACHE[cache_key] = res
                return res
    except Exception:
        pass

    return None


def search_city_suggestions(query):
    """Search for city recommendations based on query string using Open-Meteo Geocoding."""
    if not query or len(query.strip()) < 2:
        return []

    clean_query = query.strip()
    try:
        response = requests.get(
            GEO_URL_OPENMETEO,
            params={'name': clean_query, 'count': 10, 'language': 'en', 'format': 'json'},
            timeout=3,
        )
        if response.status_code == 200:
            results = response.json().get('results') or []
            suggestions = []
            seen = set()
            for item in results:
                feature_code = item.get('feature_code', '')
                if feature_code in COUNTRY_FEATURE_CODES:
                    continue  # Exclude country entities from city recommendations

                name = item.get('name', '')
                admin1 = item.get('admin1', '')
                country = item.get('country', '')

                parts = [p for p in [name, admin1, country] if p]
                display_name = ", ".join(parts)

                if display_name.lower() not in seen:
                    seen.add(display_name.lower())
                    suggestions.append({
                        'name': name,
                        'display': display_name,
                        'country': country,
                        'admin1': admin1,
                    })
            return suggestions
    except Exception:
        pass

    return []



def get_day_weather_timeline(city, target_date):
    """Returns detailed hourly timeline and daily summary for any date with 16+ weather metrics."""
    if not city or not target_date:
        return None

    if hasattr(target_date, 'strftime'):
        target_date_str = target_date.strftime('%Y-%m-%d')
    else:
        target_date_str = str(target_date)

    cache_key = f"{city.lower().strip()}_{target_date_str}"
    if cache_key in TIMELINE_CACHE:
        return TIMELINE_CACHE[cache_key]

    today = timezone.localdate()
    today_str = today.strftime('%Y-%m-%d')

    geo = _geocode_openmeteo(city)
    if not geo or geo.get('lat') is None or geo.get('lon') is None:
        return None

    is_past = target_date_str < today_str
    is_today = target_date_str == today_str
    is_future = target_date_str > today_str

    url = ARCHIVE_URL_OPENMETEO if is_past else FORECAST_URL_OPENMETEO

    try:
        response = requests.get(
            url,
            params={
                'latitude': geo['lat'],
                'longitude': geo['lon'],
                'start_date': target_date_str,
                'end_date': target_date_str,
                'hourly': (
                    'temperature_2m,apparent_temperature,precipitation_probability,precipitation,'
                    'rain,showers,snowfall,weather_code,surface_pressure,relative_humidity_2m,'
                    'wind_speed_10m,wind_direction_10m,wind_gusts_10m,uv_index,visibility,dew_point_2m,is_day'
                ),
                'wind_speed_unit': 'kmh',
                'timezone': 'auto',
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    hourly = data.get('hourly', {})
    times = hourly.get('time', [])
    temps = hourly.get('temperature_2m', [])
    feels = hourly.get('apparent_temperature', [])
    precip_probs = hourly.get('precipitation_probability', [])
    precips = hourly.get('precipitation', [])
    codes = hourly.get('weather_code', [])
    pressures = hourly.get('surface_pressure', [])
    humidities = hourly.get('relative_humidity_2m', [])
    winds = hourly.get('wind_speed_10m', [])
    dirs = hourly.get('wind_direction_10m', [])
    gusts = hourly.get('wind_gusts_10m', [])
    uvs = hourly.get('uv_index', [])
    visibilities = hourly.get('visibility', [])
    dew_points = hourly.get('dew_point_2m', [])
    is_days = hourly.get('is_day', [])

    if not times:
        return None

    tz_offset_sec = data.get('utc_offset_seconds') or 0
    now_local = datetime.now(dt_timezone.utc) + timedelta(seconds=tz_offset_sec)
    current_hour = now_local.hour if is_today else -1

    timeline = []
    for i in range(len(times)):
        t_str = times[i]
        time_part = t_str.split('T')[1][:5] if 'T' in t_str else t_str
        try:
            hour = int(time_part.split(':')[0])
        except ValueError:
            hour = i

        code = codes[i] if i < len(codes) else 0
        is_day_flag = bool(is_days[i]) if (i < len(is_days) and is_days[i] is not None) else (6 <= hour <= 19)

        desc, base_cond, base_icon = WMO_WEATHER_CODES.get(code, ("Cloudy", "cloudy", "02"))
        t_temp = round(temps[i]) if (i < len(temps) and temps[i] is not None) else 0
        t_feels = round(feels[i]) if (i < len(feels) and feels[i] is not None) else t_temp
        t_precip = precips[i] if (i < len(precips) and precips[i] is not None) else 0.0

        condition = _resolve_condition(base_cond, is_day_flag, temp=t_temp, feels_like=t_feels, precipitation=t_precip, weather_code=code)
        if condition == 'hot-summer':
            desc = "Hot & Sunny" if is_day_flag else desc
            icon = '01d' if is_day_flag else '01n'
        elif condition == 'sun-rain-mix':
            desc = "Sun & Showers"
            icon = '10d'
        elif condition == 'clear-night':
            icon = base_icon + 'n'
        else:
            icon = base_icon + ('d' if is_day_flag else 'n')

        if hour == 0:
            time_display = '12 AM'
        elif hour == 12:
            time_display = '12 PM'
        elif hour > 12:
            time_display = f'{hour - 12} PM'
        else:
            time_display = f'{hour} AM'

        timeline.append({
            'raw_time': time_part,
            'time': time_display,
            'hour': hour,
            'is_current_hour': is_today and (hour == current_hour),
            'temp': round(temps[i]) if (i < len(temps) and temps[i] is not None) else 0,
            'feels_like': round(feels[i]) if (i < len(feels) and feels[i] is not None) else 0,
            'precip_prob': precip_probs[i] if (i < len(precip_probs) and precip_probs[i] is not None) else 0,
            'precip_cm': round((precips[i] or 0) / 10.0, 2),
            'precip_mm': round(precips[i], 1) if (i < len(precips) and precips[i] is not None) else 0,
            'pressure': round(pressures[i]) if (i < len(pressures) and pressures[i] is not None) else 1013,
            'humidity': round(humidities[i]) if (i < len(humidities) and humidities[i] is not None) else 50,
            'wind_speed': round(winds[i]) if (i < len(winds) and winds[i] is not None) else 0,
            'wind_gust': round(gusts[i]) if (i < len(gusts) and gusts[i] is not None) else 0,
            'wind_dir': dirs[i] if (i < len(dirs) and dirs[i] is not None) else 0,
            'uv': round(uvs[i], 1) if (i < len(uvs) and uvs[i] is not None) else 0,
            'visibility_km': round((visibilities[i] or 10000) / 1000.0, 1),
            'dew_point': round(dew_points[i]) if (i < len(dew_points) and dew_points[i] is not None) else 15,
            'description': desc,
            'condition': condition,
            'icon': icon,
        })

    valid_temps = [t['temp'] for t in timeline]
    valid_precips = [t['precip_cm'] for t in timeline]
    valid_winds = [t['wind_speed'] for t in timeline]
    valid_gusts = [t['wind_gust'] for t in timeline]

    mid_entry = min(timeline, key=lambda x: abs(x['hour'] - 12)) if timeline else {}

    res = {
        'city': geo['name'],
        'country': geo['country'],
        'date': target_date_str,
        'is_past': is_past,
        'is_today': is_today,
        'is_future': is_future,
        'temp_avg': round(sum(valid_temps) / len(valid_temps)) if valid_temps else 0,
        'temp_min': min(valid_temps) if valid_temps else 0,
        'temp_max': max(valid_temps) if valid_temps else 0,
        'total_precip_cm': round(sum(valid_precips), 2),
        'max_precip_prob': max([t['precip_prob'] for t in timeline]) if timeline else 0,
        'avg_wind': round(sum(valid_winds) / len(valid_winds)) if valid_winds else 0,
        'max_gust': max(valid_gusts) if valid_gusts else 0,
        'avg_humidity': round(sum([t['humidity'] for t in timeline]) / len(timeline)) if timeline else 50,
        'avg_pressure': round(sum([t['pressure'] for t in timeline]) / len(timeline)) if timeline else 1013,
        'max_uv': max([t['uv'] for t in timeline]) if timeline else 0,
        'avg_visibility': round(sum([t['visibility_km'] for t in timeline]) / len(timeline), 1) if timeline else 10.0,
        'description': mid_entry.get('description', 'Cloudy'),
        'condition': mid_entry.get('condition', 'cloudy'),
        'icon': mid_entry.get('icon', '02d'),
        'current_local_time': _format_time_12h(now_local) if is_today else None,
        'current_hour': current_hour,
        'timezone': data.get('timezone', ''),
        'utc_offset_seconds': tz_offset_sec,
        'timeline': timeline,
    }
    TIMELINE_CACHE[cache_key] = res
    return res


def get_air_quality_for_date(city, target_date):
    """Retrieves Air Quality metrics (AQI, PM2.5, PM10, O3, NO2, SO2, CO) with caching."""
    if not city or not target_date:
        return None

    if hasattr(target_date, 'strftime'):
        target_date_str = target_date.strftime('%Y-%m-%d')
    else:
        target_date_str = str(target_date)

    cache_key = f"{city.lower().strip()}_{target_date_str}"
    if cache_key in AQI_CACHE:
        return AQI_CACHE[cache_key]

    geo = _geocode_openmeteo(city)
    if not geo or geo.get('lat') is None or geo.get('lon') is None:
        return None

    try:
        response = requests.get(
            AIR_QUALITY_URL_OPENMETEO,
            params={
                'latitude': geo['lat'],
                'longitude': geo['lon'],
                'start_date': target_date_str,
                'end_date': target_date_str,
                'hourly': 'us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone',
                'timezone': 'auto',
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    hourly = data.get('hourly', {})
    times = hourly.get('time', [])
    aqis = hourly.get('us_aqi', [])
    pm25s = hourly.get('pm2_5', [])
    pm10s = hourly.get('pm10', [])
    o3s = hourly.get('ozone', [])
    no2s = hourly.get('nitrogen_dioxide', [])
    so2s = hourly.get('sulphur_dioxide', [])
    cos = hourly.get('carbon_monoxide', [])

    if not times:
        return None

    timeline = []
    for i in range(len(times)):
        t_str = times[i]
        time_part = t_str.split('T')[1][:5] if 'T' in t_str else t_str
        try:
            hour = int(time_part.split(':')[0])
        except ValueError:
            hour = i

        if hour == 0:
            time_display = '12 AM'
        elif hour == 12:
            time_display = '12 PM'
        elif hour > 12:
            time_display = f'{hour - 12} PM'
        else:
            time_display = f'{hour} AM'

        aqi_val = round(aqis[i]) if (i < len(aqis) and aqis[i] is not None) else 50
        status, color = _aqi_status_and_color(aqi_val)

        timeline.append({
            'time': time_display,
            'hour': hour,
            'aqi': aqi_val,
            'status': status,
            'color': color,
            'pm2_5': round(pm25s[i], 1) if (i < len(pm25s) and pm25s[i] is not None) else 0,
            'pm10': round(pm10s[i], 1) if (i < len(pm10s) and pm10s[i] is not None) else 0,
            'o3': round(o3s[i], 1) if (i < len(o3s) and o3s[i] is not None) else 0,
            'no2': round(no2s[i], 1) if (i < len(no2s) and no2s[i] is not None) else 0,
            'so2': round(so2s[i], 1) if (i < len(so2s) and so2s[i] is not None) else 0,
            'co': round(cos[i], 1) if (i < len(cos) and cos[i] is not None) else 0,
        })

    valid_aqis = [t['aqi'] for t in timeline]
    avg_aqi = round(sum(valid_aqis) / len(valid_aqis)) if valid_aqis else 50
    avg_status, avg_color = _aqi_status_and_color(avg_aqi)

    res = {
        'avg_aqi': avg_aqi,
        'status': avg_status,
        'color': avg_color,
        'timeline': timeline,
    }
    AQI_CACHE[cache_key] = res
    return res


def _aqi_status_and_color(aqi):
    if aqi <= 50:
        return 'Good', '#28a745'
    elif aqi <= 100:
        return 'Satisfactory', '#ffc107'
    elif aqi <= 150:
        return 'Moderate pollution', '#fd7e14'
    elif aqi <= 200:
        return 'Poor', '#dc3545'
    elif aqi <= 300:
        return 'Very poor', '#6f42c1'
    else:
        return 'Severe', '#842029'


def get_8_day_cards(city, center_date=None):
    """Generates 15 daily summary cards (-7 past days, Today/Center Date, +7 future days) in ONE SINGLE BATCH HTTP request to Open-Meteo."""
    if not city:
        return []

    if not center_date:
        center_date = timezone.localdate()
    elif isinstance(center_date, str):
        try:
            center_date = datetime.strptime(center_date, '%Y-%m-%d').date()
        except ValueError:
            center_date = timezone.localdate()

    cache_key = f"{city.lower().strip()}_{center_date.strftime('%Y-%m-%d')}_15"
    if cache_key in CARDS_CACHE:
        return CARDS_CACHE[cache_key]

    geo = _geocode_openmeteo(city)
    if not geo or geo.get('lat') is None or geo.get('lon') is None:
        return []

    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    start_d = center_date - timedelta(days=7)
    end_d = center_date + timedelta(days=7)
    start_str = start_d.strftime('%Y-%m-%d')
    end_str = end_d.strftime('%Y-%m-%d')

    try:
        response = requests.get(
            FORECAST_URL_OPENMETEO,
            params={
                'latitude': geo['lat'],
                'longitude': geo['lon'],
                'start_date': start_str,
                'end_date': end_str,
                'daily': (
                    'weather_code,temperature_2m_max,temperature_2m_min,'
                    'precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,'
                    'uv_index_max,relative_humidity_2m_mean'
                ),
                'wind_speed_unit': 'kmh',
                'timezone': 'auto',
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        data = {}

    daily = data.get('daily', {})
    dates = daily.get('time', [])
    codes = daily.get('weather_code', [])
    t_maxs = daily.get('temperature_2m_max', [])
    t_mins = daily.get('temperature_2m_min', [])
    precip_sums = daily.get('precipitation_sum', [])
    precip_probs = daily.get('precipitation_probability_max', [])
    wind_speeds = daily.get('wind_speed_10m_max', [])
    wind_gusts = daily.get('wind_gusts_10m_max', [])
    uv_maxes = daily.get('uv_index_max', [])
    humidity_means = daily.get('relative_humidity_2m_mean', [])

    cards = []
    for i in range(len(dates)):
        d_str = dates[i]
        try:
            d = datetime.strptime(d_str, '%Y-%m-%d').date()
        except ValueError:
            continue

        if d == today:
            label = 'Today'
        elif d == yesterday:
            label = 'Yesterday'
        elif d == tomorrow:
            label = 'Tomorrow'
        else:
            label = d.strftime('%a, %b %d')

        code = codes[i] if i < len(codes) else 0
        desc, base_cond, base_icon = WMO_WEATHER_CODES.get(code, ("Cloudy", "cloudy", "02"))

        t_max = round(t_maxs[i]) if (i < len(t_maxs) and t_maxs[i] is not None) else 30
        t_min = round(t_mins[i]) if (i < len(t_mins) and t_mins[i] is not None) else 24
        t_avg = round((t_max + t_min) / 2.0)
        c_precip = (precip_sums[i] or 0) if i < len(precip_sums) else 0

        condition = _resolve_condition(base_cond, True, temp=t_max, feels_like=t_max, precipitation=c_precip, weather_code=code)
        if condition == 'hot-summer':
            desc = "Hot & Sunny"
            icon = '01d'
        elif condition == 'sun-rain-mix':
            desc = "Sun & Showers"
            icon = '10d'
        else:
            icon = base_icon + 'd'

        cards.append({
            'date': d_str,
            'day_num': d.day,
            'month_name': d.strftime('%b'),
            'label': label,
            'is_past': d < today,
            'is_today': d == today,
            'is_future': d > today,
            'temp_high': t_max,
            'temp_low': t_min,
            'temp_avg': t_avg,
            'precip_cm': round(c_precip / 10.0, 2),
            'precip_prob': precip_probs[i] if (i < len(precip_probs) and precip_probs[i] is not None) else 0,
            'wind_speed': round(wind_speeds[i]) if (i < len(wind_speeds) and wind_speeds[i] is not None) else 12,
            'wind_gust': round(wind_gusts[i]) if (i < len(wind_gusts) and wind_gusts[i] is not None) else 30,
            'humidity': round(humidity_means[i]) if (i < len(humidity_means) and humidity_means[i] is not None) else None,
            'uv': round(uv_maxes[i], 1) if (i < len(uv_maxes) and uv_maxes[i] is not None) else None,
            'description': desc,
            'condition': condition,
            'icon': icon,
            'is_selected': d_str == center_date.strftime('%Y-%m-%d'),
        })

    CARDS_CACHE[cache_key] = cards
    return cards


def get_weather_for_date(city, target_date):
    tl = get_day_weather_timeline(city, target_date)
    if not tl:
        return None
    return {
        'date': tl['date'],
        'temp': tl['temp_avg'],
        'temp_min': tl['temp_min'],
        'temp_max': tl['temp_max'],
        'description': tl['description'],
        'main': tl['description'],
        'icon': tl['icon'],
        'condition': tl['condition'],
    }


def _get_current_weather_owm(city, api_key):
    try:
        response = requests.get(
            f'{BASE_URL_OWM}/weather',
            params={'q': city, 'appid': api_key, 'units': 'metric'},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    weather_block = (data.get('weather') or [{}])[0]
    icon = weather_block.get('icon', '01d')
    weather_id = weather_block.get('id', 800)
    is_day_flag = icon.endswith('d')
    tz_offset = data.get('timezone', 0)  # seconds offset from UTC, provided by OWM
    sunrise_ts = data.get('sys', {}).get('sunrise')
    sunset_ts = data.get('sys', {}).get('sunset')
    sunrise = _format_time_12h(datetime.utcfromtimestamp(sunrise_ts + tz_offset)) if sunrise_ts else None
    sunset = _format_time_12h(datetime.utcfromtimestamp(sunset_ts + tz_offset)) if sunset_ts else None

    # Calculate exact local time and date for the city
    dt_now = datetime.utcfromtimestamp(int(datetime.utcnow().timestamp()) + tz_offset)
    local_time = _format_time_12h(dt_now)
    local_time_24 = dt_now.strftime('%H:%M')
    local_date = dt_now.strftime('%A, %b %d, %Y')
    offset_h = tz_offset // 3600
    offset_m = abs(tz_offset % 3600) // 60
    tz_label = f"UTC{'+' if tz_offset >= 0 else ''}{offset_h:+03d}:{offset_m:02d}" if tz_offset else "UTC"

    temp = round(data.get('main', {}).get('temp', 0))
    feels_like = round(data.get('main', {}).get('feels_like', 0))
    rain_obj = data.get('rain', {})
    precip = rain_obj.get('1h', 0.0) if isinstance(rain_obj, dict) else 0.0

    base_cond = _icon_to_condition(icon)
    condition = _resolve_condition(base_cond, is_day_flag, temp=temp, feels_like=feels_like, precipitation=precip, weather_code=weather_id)

    desc = weather_block.get('description', '').title()
    if condition == 'hot-summer':
        desc = "Hot & Sunny" if is_day_flag else desc
        icon = '01d' if is_day_flag else '01n'
    elif condition == 'sun-rain-mix':
        desc = "Sun & Passing Showers"
        icon = '10d'

    return {
        'city': data.get('name') or city,
        'country': data.get('sys', {}).get('country', ''),
        'temp': temp,
        'feels_like': feels_like,
        'temp_min': round(data.get('main', {}).get('temp_min', 0)),
        'temp_max': round(data.get('main', {}).get('temp_max', 0)),
        'humidity': data.get('main', {}).get('humidity'),
        'pressure': data.get('main', {}).get('pressure'),
        'wind_speed': round(data.get('wind', {}).get('speed', 0) * 3.6, 1),  # OWM metric units = m/s; convert to km/h
        'description': desc,
        'main': weather_block.get('main', ''),
        'icon': icon,
        'condition': condition,
        'is_day': is_day_flag,
        'precipitation': precip,
        'sunrise': sunrise,
        'sunset': sunset,
        'local_time': local_time,
        'local_time_24': local_time_24,
        'local_date': local_date,
        'timezone': tz_label,
        'utc_offset_seconds': tz_offset,
    }


def _get_forecast_owm(city, api_key, days=5):
    try:
        response = requests.get(
            f'{BASE_URL_OWM}/forecast',
            params={'q': city, 'appid': api_key, 'units': 'metric'},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    entries = data.get('list', [])
    if not entries:
        return None

    by_date = {}
    for entry in entries:
        dt_txt = entry.get('dt_txt', '')
        if not dt_txt or ' ' not in dt_txt:
            continue
        day_str, time_str = dt_txt.split(' ')
        try:
            hour = int(time_str.split(':')[0])
        except ValueError:
            hour = 12
        if day_str not in by_date:
            by_date[day_str] = []
        by_date[day_str].append((abs(hour - 12), entry))

    daily = []
    for day_str in sorted(by_date.keys()):
        best_entry = min(by_date[day_str], key=lambda x: x[0])[1]
        daily.append(_forecast_entry_owm(day_str, best_entry))

    return daily[:days]


def _forecast_entry_owm(day_str, entry):
    weather_block = (entry.get('weather') or [{}])[0]
    icon = weather_block.get('icon', '01d')
    return {
        'date': day_str,
        'temp': round(entry.get('main', {}).get('temp', 0)),
        'temp_min': round(entry.get('main', {}).get('temp_min', 0)),
        'temp_max': round(entry.get('main', {}).get('temp_max', 0)),
        'description': weather_block.get('description', '').title(),
        'main': weather_block.get('main', ''),
        'icon': icon,
        'condition': _icon_to_condition(icon),
    }


def _get_current_weather_openmeteo(city):
    geo = _geocode_openmeteo(city)
    if not geo or geo.get('lat') is None or geo.get('lon') is None:
        return None

    try:
        response = requests.get(
            FORECAST_URL_OPENMETEO,
            params={
                'latitude': geo['lat'],
                'longitude': geo['lon'],
                'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,wind_speed_10m,weather_code,is_day,precipitation,rain',
                'daily': 'weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset',
                'wind_speed_unit': 'kmh',
                'timezone': 'auto',
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    current = data.get('current', {})
    daily = data.get('daily', {})

    code = current.get('weather_code', 0)
    is_day_flag = bool(current.get('is_day', 1))
    precip = float(current.get('precipitation') or current.get('rain') or 0.0)
    temp = round(current.get('temperature_2m', 0))
    feels_like = round(current.get('apparent_temperature', 0))

    desc, base_cond, base_icon = WMO_WEATHER_CODES.get(code, ("Cloudy", "cloudy", "02"))

    condition = _resolve_condition(base_cond, is_day_flag, temp=temp, feels_like=feels_like, precipitation=precip, weather_code=code)

    if condition == 'hot-summer':
        desc = "Hot & Sunny" if is_day_flag else desc
        icon = '01d' if is_day_flag else '01n'
    elif condition == 'sun-rain-mix':
        desc = "Sun & Passing Showers"
        icon = '10d'
    elif condition == 'clear-night':
        icon = base_icon + 'n'
    else:
        icon = base_icon + ('d' if is_day_flag else 'n')

    temp_max_list = daily.get('temperature_2m_max') or []
    temp_min_list = daily.get('temperature_2m_min') or []
    temp_max = temp_max_list[0] if temp_max_list else temp
    temp_min = temp_min_list[0] if temp_min_list else temp

    sunrise_list = daily.get('sunrise') or []
    sunset_list = daily.get('sunset') or []
    sunrise = None
    sunset = None
    if sunrise_list:
        try:
            sunrise = _format_time_12h(datetime.fromisoformat(sunrise_list[0]))
        except ValueError:
            sunrise = None
    if sunset_list:
        try:
            sunset = _format_time_12h(datetime.fromisoformat(sunset_list[0]))
        except ValueError:
            sunset = None

    tz_name = data.get('timezone') or ''
    tz_offset_sec = data.get('utc_offset_seconds') or 0

    # Calculate exact current local time and date for the city
    now_utc = datetime.now(dt_timezone.utc)
    local_dt = now_utc + timedelta(seconds=tz_offset_sec)
    local_time = _format_time_12h(local_dt)
    local_time_24 = local_dt.strftime('%H:%M')
    local_date = local_dt.strftime('%A, %b %d, %Y')

    return {
        'city': geo['name'],
        'country': geo['country'],
        'temp': temp,
        'feels_like': feels_like,
        'temp_min': round(temp_min),
        'temp_max': round(temp_max),
        'humidity': current.get('relative_humidity_2m'),
        'pressure': round(current.get('surface_pressure', 1013)),
        'wind_speed': round(current.get('wind_speed_10m', 0), 1),
        'description': desc,
        'main': desc,
        'icon': icon,
        'condition': condition,
        'is_day': is_day_flag,
        'precipitation': precip,
        'is_country': geo.get('is_country', False),
        'sunrise': sunrise,
        'sunset': sunset,
        'local_time': local_time,
        'local_time_24': local_time_24,
        'local_date': local_date,
        'timezone': tz_name,
        'utc_offset_seconds': tz_offset_sec,
    }


def _get_forecast_openmeteo(city, days=5):
    geo = _geocode_openmeteo(city)
    if not geo or geo.get('lat') is None or geo.get('lon') is None:
        return None

    try:
        response = requests.get(
            FORECAST_URL_OPENMETEO,
            params={
                'latitude': geo['lat'],
                'longitude': geo['lon'],
                'daily': 'weather_code,temperature_2m_max,temperature_2m_min',
                'timezone': 'auto',
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    daily_data = data.get('daily', {})
    dates = daily_data.get('time', [])
    codes = daily_data.get('weather_code', [])
    max_temps = daily_data.get('temperature_2m_max', [])
    min_temps = daily_data.get('temperature_2m_min', [])

    forecast = []
    for i in range(min(len(dates), days)):
        dt_str = dates[i]
        code = codes[i] if i < len(codes) else 0
        t_max = max_temps[i] if i < len(max_temps) else 0
        t_min = min_temps[i] if i < len(min_temps) else 0
        t_avg = (t_max + t_min) / 2.0

        desc, condition, base_icon = WMO_WEATHER_CODES.get(code, ("Cloudy", "cloudy", "02"))
        icon = base_icon + 'd'

        forecast.append({
            'date': dt_str,
            'temp': round(t_avg),
            'temp_min': round(t_min),
            'temp_max': round(t_max),
            'description': desc,
            'main': desc,
            'icon': icon,
            'condition': condition,
        })

    return forecast

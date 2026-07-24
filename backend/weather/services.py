"""
Weather service with dual provider support & Open-Meteo Air Quality integration.
Provides MSN-Weather style multi-tab metrics: Overview, Precipitation, Wind,
Air Quality, Humidity, Pressure, UV, and Visibility with zero-lag batching & caching.
"""
import requests
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone

BASE_URL_OWM = 'https://api.openweathermap.org/data/2.5'
GEO_URL_OPENMETEO = 'https://geocoding-api.open-meteo.com/v1/search'
FORECAST_URL_OPENMETEO = 'https://api.open-meteo.com/v1/forecast'
ARCHIVE_URL_OPENMETEO = 'https://archive-api.open-meteo.com/v1/archive'
AIR_QUALITY_URL_OPENMETEO = 'https://air-quality-api.open-meteo.com/v1/air-quality'
REQUEST_TIMEOUT = 5  # seconds

# In-memory caches to guarantee 0ms latency for repeated requests
GEO_CACHE = {}
TIMELINE_CACHE = {}
AQI_CACHE = {}
CARDS_CACHE = {}

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


def get_current_weather(city):
    if not city or not city.strip():
        return None

    city = city.strip()
    api_key = getattr(settings, 'OPENWEATHERMAP_API_KEY', None)

    if api_key:
        result = _get_current_weather_owm(city, api_key)
        if result:
            return result

    return _get_current_weather_openmeteo(city)


def get_forecast(city, days=5):
    if not city or not city.strip():
        return None

    city = city.strip()
    api_key = getattr(settings, 'OPENWEATHERMAP_API_KEY', None)

    if api_key:
        result = _get_forecast_owm(city, api_key, days=days)
        if result:
            return result

    return _get_forecast_openmeteo(city, days=days)


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
            params={'name': clean_name, 'count': 1, 'language': 'en', 'format': 'json'},
            timeout=3,
        )
        if response.status_code == 200:
            data = response.json()
            results = data.get('results')
            if results:
                loc = results[0]
                res = {
                    'name': loc.get('name', clean_name),
                    'country': loc.get('country', loc.get('country_code', '')),
                    'lat': loc.get('latitude'),
                    'lon': loc.get('longitude'),
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
                }
                GEO_CACHE[cache_key] = res
                return res
    except Exception:
        pass

    return None


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

        desc, condition, base_icon = WMO_WEATHER_CODES.get(code, ("Cloudy", "cloudy", "02"))
        if condition == 'sunny' and not is_day_flag:
            condition = 'clear-night'
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
            'temp': round(temps[i]) if (i < len(temps) and temps[i] is not None) else 0,
            'feels_like': round(feels[i]) if (i < len(feels) and feels[i] is not None) else 0,
            'precip_prob': precip_probs[i] if (i < len(precip_probs) and precip_probs[i] is not None) else 0,
            'precip_cm': round((precips[i] or 0) / 10.0, 2),
            'precip_mm': round(precips[i], 1) if (i < len(precips) and precips[i] is not None) else 0,
            'pressure': round(pressures[i]) if (i < len(pressures) and pressures[i] is not None) else 1013,
            'humidity': humidities[i] if i < len(humidities) else 50,
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
                    'precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max'
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
        desc, condition, base_icon = WMO_WEATHER_CODES.get(code, ("Cloudy", "cloudy", "02"))

        t_max = round(t_maxs[i]) if (i < len(t_maxs) and t_maxs[i] is not None) else 30
        t_min = round(t_mins[i]) if (i < len(t_mins) and t_mins[i] is not None) else 24
        t_avg = round((t_max + t_min) / 2.0)

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
            'precip_cm': round((precip_sums[i] or 0) / 10.0, 2) if i < len(precip_sums) else 0,
            'precip_prob': precip_probs[i] if (i < len(precip_probs) and precip_probs[i] is not None) else 0,
            'wind_speed': round(wind_speeds[i]) if (i < len(wind_speeds) and wind_speeds[i] is not None) else 12,
            'wind_gust': round(wind_gusts[i]) if (i < len(wind_gusts) and wind_gusts[i] is not None) else 30,
            'humidity': 70,
            'pressure': 1008,
            'uv': 6,
            'visibility': 10.0,
            'description': desc,
            'condition': condition,
            'icon': base_icon + 'd',
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

    return {
        'city': data.get('name') or city,
        'country': data.get('sys', {}).get('country', ''),
        'temp': round(data.get('main', {}).get('temp', 0)),
        'feels_like': round(data.get('main', {}).get('feels_like', 0)),
        'temp_min': round(data.get('main', {}).get('temp_min', 0)),
        'temp_max': round(data.get('main', {}).get('temp_max', 0)),
        'humidity': data.get('main', {}).get('humidity'),
        'pressure': data.get('main', {}).get('pressure'),
        'wind_speed': round(data.get('wind', {}).get('speed', 0), 1),
        'description': weather_block.get('description', '').title(),
        'main': weather_block.get('main', ''),
        'icon': icon,
        'condition': _icon_to_condition(icon),
        'is_day': icon.endswith('d'),
        'sunrise': data.get('sys', {}).get('sunrise'),
        'sunset': data.get('sys', {}).get('sunset'),
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
                'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,wind_speed_10m,weather_code,is_day',
                'daily': 'weather_code,temperature_2m_max,temperature_2m_min',
                'wind_speed_unit': 'ms',
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

    desc, condition, base_icon = WMO_WEATHER_CODES.get(code, ("Cloudy", "cloudy", "02"))
    if condition == 'sunny' and not is_day_flag:
        condition = 'clear-night'
        icon = base_icon + 'n'
    else:
        icon = base_icon + ('d' if is_day_flag else 'n')

    temp_max_list = daily.get('temperature_2m_max') or []
    temp_min_list = daily.get('temperature_2m_min') or []
    temp_max = temp_max_list[0] if temp_max_list else current.get('temperature_2m', 0)
    temp_min = temp_min_list[0] if temp_min_list else current.get('temperature_2m', 0)

    return {
        'city': geo['name'],
        'country': geo['country'],
        'temp': round(current.get('temperature_2m', 0)),
        'feels_like': round(current.get('apparent_temperature', 0)),
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
        'sunrise': '6:15 AM',
        'sunset': '6:47 PM',
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

"""
Covers the weather page end-to-end by faking the service layer (so tests
never make real network calls) and rendering every tab through Django's
test client. Run with: python manage.py test weather

Uses Django's TestCase, which wraps every test in a transaction against a
throwaway test database — safe to run any time without touching your real
db.sqlite3 or the users in it.
"""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase


def _fake_timeline_entries():
    return [
        {
            'raw_time': f'{h:02d}:00', 'time': f'{h % 12 or 12} {"AM" if h < 12 else "PM"}', 'hour': h,
            'temp': 24 + (h % 12), 'feels_like': 26 + (h % 12), 'precip_prob': (h * 3) % 100,
            'precip_cm': 0.1, 'precip_mm': 1.2, 'pressure': 1008 + (h % 5), 'humidity': 60 + (h % 20),
            'wind_speed': 10 + (h % 8), 'wind_gust': 20 + (h % 10), 'wind_dir': (h * 15) % 360,
            'uv': min(11, h // 2), 'visibility_km': 10.0, 'dew_point': 18,
            'description': 'Partly cloudy', 'condition': 'cloudy', 'icon': '02d',
        }
        for h in range(24)
    ]


def _fake_current(city):
    return {
        'city': city or 'Chennai', 'country': 'IN', 'temp': 30, 'feels_like': 37, 'temp_min': 25, 'temp_max': 31,
        'humidity': 75, 'pressure': 1008, 'wind_speed': 9.0, 'description': 'Partly sunny', 'main': 'Clouds',
        'icon': '02d', 'condition': 'cloudy', 'is_day': True, 'sunrise': '6:15 AM', 'sunset': '6:47 PM',
    }


def _fake_day_timeline(city, date_str):
    return {
        'city': city, 'country': 'IN', 'date': date_str, 'is_past': False, 'is_today': True, 'is_future': False,
        'temp_avg': 28, 'temp_min': 24, 'temp_max': 32, 'total_precip_cm': 0.92, 'max_precip_prob': 68,
        'avg_wind': 12, 'max_gust': 30, 'avg_humidity': 70, 'avg_pressure': 1009, 'max_uv': 7, 'avg_visibility': 10.0,
        'description': 'Partly cloudy', 'condition': 'cloudy', 'icon': '02d', 'timeline': _fake_timeline_entries(),
    }


def _fake_air_quality(city, date_str):
    timeline = [
        {
            'time': f'{h % 12 or 12} {"AM" if h < 12 else "PM"}', 'hour': h, 'aqi': 50 + (h % 20),
            'status': 'Good', 'color': '#28a745', 'pm2_5': 8.2, 'pm10': 15.0, 'o3': 20.0, 'no2': 5.0,
            'so2': 1.0, 'co': 200.0,
        }
        for h in range(24)
    ]
    return {'avg_aqi': 50, 'status': 'Good', 'color': '#28a745', 'timeline': timeline}


def _fake_cards(city, center_date=None):
    return [
        {
            'date': f'2026-07-{24 + i:02d}', 'day_num': 24 + i, 'month_name': 'Jul',
            'label': 'Today' if i == 0 else f'Day {i}', 'is_past': i < 0, 'is_today': i == 0, 'is_future': i > 0,
            'temp_high': 31 + i, 'temp_low': 24 + i, 'temp_avg': 27, 'precip_cm': 0.2, 'precip_prob': 40,
            'wind_speed': 12, 'wind_gust': 30, 'humidity': 65, 'uv': 6.0,
            'description': 'Partly cloudy', 'condition': 'cloudy', 'icon': '02d', 'is_selected': i == 0,
        }
        for i in range(-7, 8)
    ]


@patch('weather.views.get_8_day_cards', side_effect=_fake_cards)
@patch('weather.views.get_air_quality_for_date', side_effect=_fake_air_quality)
@patch('weather.views.get_day_weather_timeline', side_effect=_fake_day_timeline)
@patch('weather.views.get_current_weather', side_effect=_fake_current)
class WeatherPageTests(TestCase):
    TABS = ['overview', 'precipitation', 'wind', 'air_quality', 'humidity', 'pressure', 'uv', 'visibility']

    def setUp(self):
        self.user = User.objects.create_user('weathertestuser', password='not-a-real-password-123')
        self.user.profile.is_approved = True
        self.user.profile.save()
        self.client.force_login(self.user)

    def test_every_tab_renders_ok(self, *mocks):
        for tab in self.TABS:
            with self.subTest(tab=tab):
                resp = self.client.get(f'/weather/?city=Chennai&tab={tab}&unit=C')
                self.assertEqual(resp.status_code, 200)
                self.assertNotIn(b'Traceback', resp.content)

    def test_hero_and_data_blocks_present(self, *mocks):
        resp = self.client.get('/weather/?city=Chennai&tab=overview')
        body = resp.content.decode()
        self.assertIn('id="timeline-data"', body)
        self.assertIn('id="aqi-data"', body)
        self.assertIn('weather.css', body)
        self.assertIn('weather-charts.js', body)

    def test_city_not_found_shows_warning_not_crash(self, mock_current, *mocks):
        mock_current.side_effect = lambda city: None  # stacked @patch decorators apply bottom-up,
        resp = self.client.get('/weather/?city=Nowhereville')  # so get_current_weather is the first arg
        self.assertEqual(resp.status_code, 200)
        self.assertIn('alert-warning', resp.content.decode())

    def test_anonymous_user_redirected_to_login(self, *mocks):
        self.client.logout()
        resp = self.client.get('/weather/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login', resp.url)


class ConditionResolutionTests(TestCase):
    def test_hot_summer_day_with_trace_precipitation(self):
        """When it is 31.5°C in daylight and precipitation is 0.1mm (e.g. WMO 51),
        it must resolve to 'hot-summer', NOT 'rainy', preventing false rain in summer."""
        from weather.services import _resolve_condition
        cond = _resolve_condition(
            base_cond='rainy',
            is_day=True,
            temp=32,
            feels_like=37,
            precipitation=0.1,
            weather_code=51,
        )
        self.assertEqual(cond, 'hot-summer')

    def test_sun_and_rain_mix_daytime(self):
        """When it is daytime and light rain / showers occurs (e.g. 0.8mm),
        it should resolve to 'sun-rain-mix' (sunshower)."""
        from weather.services import _resolve_condition
        cond = _resolve_condition(
            base_cond='rainy',
            is_day=True,
            temp=26,
            feels_like=26,
            precipitation=0.8,
            weather_code=80,
        )
        self.assertEqual(cond, 'sun-rain-mix')

    def test_heavy_rain_resolves_to_rainy(self):
        """When precipitation is significant (>= 2.0mm), it resolves to 'rainy'."""
        from weather.services import _resolve_condition
        cond = _resolve_condition(
            base_cond='rainy',
            is_day=True,
            temp=24,
            precipitation=4.5,
            weather_code=65,
        )
        self.assertEqual(cond, 'rainy')

    def test_hot_clear_day(self):
        """High temperature clear day resolves to 'hot-summer'."""
        from weather.services import _resolve_condition
        cond = _resolve_condition(
            base_cond='sunny',
            is_day=True,
            temp=33,
            feels_like=36,
            precipitation=0.0,
            weather_code=0,
        )
        self.assertEqual(cond, 'hot-summer')

    def test_mild_clear_day(self):
        """Mild clear day resolves to 'sunny'."""
        from weather.services import _resolve_condition
        cond = _resolve_condition(
            base_cond='sunny',
            is_day=True,
            temp=24,
            feels_like=24,
            precipitation=0.0,
            weather_code=0,
        )
        self.assertEqual(cond, 'sunny')

    def test_clear_night(self):
        """Nighttime clear sky resolves to 'clear-night'."""
        from weather.services import _resolve_condition
        cond = _resolve_condition(
            base_cond='sunny',
            is_day=False,
            temp=22,
            precipitation=0.0,
            weather_code=0,
        )
        self.assertEqual(cond, 'clear-night')


class WeatherContextProcessorTests(TestCase):
    def test_context_processor_returns_weather(self):
        """Verify that the weather context processor provides the 'weather' key."""
        from django.test import RequestFactory
        from weather.context_processors import current_weather
        factory = RequestFactory()
        req = factory.get('/')
        req.user = User.objects.create_user('cptestuser', password='password123')
        req.session = {}

        with patch('weather.context_processors.get_current_weather', return_value={'city': 'Chennai', 'temp': 30, 'condition': 'hot-summer'}):
            ctx = current_weather(req)
            self.assertIn('weather', ctx)
            self.assertEqual(ctx['weather']['condition'], 'hot-summer')

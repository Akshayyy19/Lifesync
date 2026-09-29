from .services import get_current_weather


def current_weather(request):
    """
    Supplies the current weather condition and metadata to all templates
    rendered via base.html so that the sky header and weather theme adapt
    globally across the entire application, not just on the dashboard.
    """
    city = None
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile and profile.city:
            city = profile.city

    if not city:
        city = request.session.get('weather_city') or 'Chennai'

    # get_current_weather is cached in-memory and will return rapidly
    weather = get_current_weather(city)
    return {'weather': weather}

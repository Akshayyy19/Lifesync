from django import template

register = template.Library()

CONDITION_ICONS = {
    'sunny': 'bi-brightness-high-fill',
    'clear-night': 'bi-moon-stars-fill',
    'cloudy': 'bi-clouds-fill',
    'rainy': 'bi-cloud-rain-fill',
    'snowy': 'bi-cloud-snow-fill',
    'thunderstorm': 'bi-cloud-lightning-rain-fill',
    'misty': 'bi-cloud-fog2-fill',
}


@register.filter
def condition_icon(condition):
    """Maps a weather `condition` string (sunny/rainy/snowy/...) to a
    Bootstrap Icons class, so the forecast strip actually looks different
    on a rainy day vs. a sunny one instead of always showing the same icon."""
    return CONDITION_ICONS.get(condition, 'bi-clouds-fill')

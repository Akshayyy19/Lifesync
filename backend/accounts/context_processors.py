# ==============================================================================
# File: accounts/context_processors.py
# Description: Global template context processor for user traffic alerts.
# ==============================================================================

from .models import Profile


def user_traffic_context(request):
    """
    Exposes `pending_users_count` to templates so that admin / staff users
    always have an immediate notification indicator in the top navbar.
    """
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        pending_count = Profile.objects.filter(is_approved=False).count()
        return {'pending_users_count': pending_count}
    return {'pending_users_count': 0}

# ==============================================================================
# File: accounts/middleware.py
# Description: Real-time user access control and traffic restriction middleware.
# ==============================================================================

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect


class SecurityNoCacheMiddleware:
    """
    Prevents browsers and intermediate proxies from caching dynamic HTML and API responses.
    This eliminates Back-Forward Cache (bfcache) retention of privileged pages (e.g. Admin Hub,
    user dashboards, notifications) after logging out or switching accounts.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Do not alter static assets (CSS, JS, images, fonts)
        static_url = getattr(settings, 'STATIC_URL', '/static/')
        if static_url and request.path.startswith(static_url):
            return response

        # Enforce strict no-cache directives on all dynamic responses
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


class UserAccessControlMiddleware:
    """
    Enforces active user restrictions and approval checks in real-time on every
    authenticated request. If an admin restricts a logged-in user or revokes
    approval, the user's active session is immediately terminated.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not (request.user.is_superuser or request.user.is_staff):
            profile = getattr(request.user, 'profile', None)
            if profile:
                # Check if restricted/suspended
                if profile.is_restricted:
                    reason = profile.restriction_reason.strip() or "No specific reason provided."
                    logout(request)
                    request.session.flush()
                    messages.error(
                        request,
                        f"Your account has been restricted by an administrator. Reason: {reason}. Please contact support."
                    )
                    redirect_resp = redirect('accounts:login')
                    redirect_resp['Cache-Control'] = 'no-cache, no-store, must-revalidate, private, max-age=0'
                    redirect_resp['Pragma'] = 'no-cache'
                    redirect_resp['Expires'] = '0'
                    return redirect_resp

                # Check if approval was revoked
                if not profile.is_approved:
                    logout(request)
                    request.session.flush()
                    messages.warning(
                        request,
                        "Your account registration is currently pending administrator approval."
                    )
                    redirect_resp = redirect('accounts:login')
                    redirect_resp['Cache-Control'] = 'no-cache, no-store, must-revalidate, private, max-age=0'
                    redirect_resp['Pragma'] = 'no-cache'
                    redirect_resp['Expires'] = '0'
                    return redirect_resp

        response = self.get_response(request)
        return response

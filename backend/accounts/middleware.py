# ==============================================================================
# File: accounts/middleware.py
# Description: Real-time user access control and traffic restriction middleware.
# ==============================================================================

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect


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
            if hasattr(request.user, 'profile'):
                profile = request.user.profile

                # Check if restricted/suspended
                if profile.is_restricted:
                    reason = profile.restriction_reason.strip() or "No specific reason provided."
                    logout(request)
                    messages.error(
                        request,
                        f"Your account has been restricted by an administrator. Reason: {reason}. Please contact support."
                    )
                    return redirect('accounts:login')

                # Check if approval was revoked
                if not profile.is_approved:
                    logout(request)
                    messages.warning(
                        request,
                        "Your account registration is currently pending administrator approval."
                    )
                    return redirect('accounts:login')

        response = self.get_response(request)
        return response

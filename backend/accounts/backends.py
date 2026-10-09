# ==============================================================================
# File: accounts/backends.py
# Description: Custom authentication backend supporting login via Username or Email.
# ==============================================================================

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """
    Allows users to authenticate using either their registered username
    OR their registered email address (case-insensitively).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or not password:
            return None

        # Search for a matching user by username OR email (case-insensitive)
        user = UserModel.objects.filter(
            Q(username__iexact=username) | Q(email__iexact=username)
        ).first()

        if user and user.check_password(password):
            return user
        return None

# ==============================================================================
# File: accounts/forms.py
# Description: Form definitions for user authentication, registration, recovery,
#              profile customization, and admin user traffic control.
# ==============================================================================

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    UserCreationForm,
)
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import Profile


# ------------------------------------------------------------------------------
# Form: LoginForm
# Purpose: Authenticates users using Username OR Email with real-time status checks.
# ------------------------------------------------------------------------------
class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Enter username or email',
                'autofocus': True,
                'autocomplete': 'username',
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Enter your password',
                'autocomplete': 'current-password',
                'id': 'passwordInput',
            }
        ),
    )

    def clean(self):
        username_or_email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username_or_email and password:
            # Query user by username OR email (case-insensitive)
            user_obj = User.objects.filter(
                Q(username__iexact=username_or_email) | Q(email__iexact=username_or_email)
            ).first()

            if user_obj:
                # Verify password validity
                if user_obj.check_password(password):
                    # Check profile restrictions & approval
                    if hasattr(user_obj, 'profile'):
                        profile = user_obj.profile
                        if profile.is_restricted:
                            reason = (
                                profile.restriction_reason.strip()
                                or "No specific reason provided."
                            )
                            raise ValidationError(
                                f"Access Restricted: Your account has been suspended by an administrator. Reason: {reason}. Please contact support.",
                                code='restricted',
                            )

                        if not profile.is_approved:
                            raise ValidationError(
                                "Account Pending Approval: Your registration is currently awaiting administrator review. You will be able to log in once an admin accepts your request.",
                                code='pending_approval',
                            )

                    if not user_obj.is_active:
                        raise ValidationError(
                            "Account Inactive: This account has been deactivated. Please contact an administrator.",
                            code='inactive',
                        )

                    # Authenticate through backend using canonical username
                    self.user_cache = authenticate(
                        self.request, username=user_obj.username, password=password
                    )
                    if self.user_cache is None:
                        raise ValidationError(
                            self.error_messages['invalid_login'],
                            code='invalid_login',
                        )
                    return self.cleaned_data
                else:
                    raise ValidationError(
                        "Incorrect password. If you forgot your password, use the reset link below.",
                        code='invalid_login',
                    )
            else:
                raise ValidationError(
                    "No account found with that username or email address. Please check your credentials or create an account.",
                    code='invalid_login',
                )

        return super().clean()


# ------------------------------------------------------------------------------
# Form: RegisterForm
# Purpose: User registration with email uniqueness check and profile initialization.
# ------------------------------------------------------------------------------
class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={'class': 'form-control', 'placeholder': 'you@example.com'}
        ),
    )
    city = forms.CharField(
        required=False,
        initial='Chennai',
        help_text='Used for weather forecasts on your dashboard. Can be changed anytime.',
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'e.g. Chennai, London, New York'}
        ),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update(
            {'class': 'form-control', 'placeholder': 'Choose a username'}
        )
        self.fields['password1'].widget.attrs.update(
            {'class': 'form-control', 'placeholder': 'Create a secure password'}
        )
        self.fields['password2'].widget.attrs.update(
            {'class': 'form-control', 'placeholder': 'Confirm your password'}
        )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                "An account with this email address already exists. Please log in or reset your password."
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            city = self.cleaned_data.get('city') or 'Chennai'
            approval_required = getattr(settings, 'ACCOUNT_APPROVAL_REQUIRED', True)
            is_approved = not approval_required if not (user.is_superuser or user.is_staff) else True

            profile, _ = Profile.objects.get_or_create(user=user)
            profile.city = city
            profile.is_approved = is_approved
            profile.save()
        return user


# ------------------------------------------------------------------------------
# Form: ForgotUsernameForm
# Purpose: Recovers forgotten username using registered email.
# ------------------------------------------------------------------------------
class ForgotUsernameForm(forms.Form):
    email = forms.EmailField(
        label="Registered Email Address",
        widget=forms.EmailInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Enter your registered email address',
                'autofocus': True,
            }
        ),
    )


# ------------------------------------------------------------------------------
# Form: CustomPasswordResetForm
# Purpose: Extends standard PasswordResetForm to allow resetting by Username OR Email.
# ------------------------------------------------------------------------------
class CustomPasswordResetForm(PasswordResetForm):
    email = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Enter your username or email',
                'autofocus': True,
            }
        ),
    )

    def get_users(self, email):
        """
        Accepts either an email address or username and finds matching active users.
        """
        UserModel = User
        users = UserModel.objects.filter(
            Q(email__iexact=email) | Q(username__iexact=email)
        )
        return (u for u in users if u.is_active and u.has_usable_password())


# ------------------------------------------------------------------------------
# Form: ProfileForm
# Purpose: User profile settings (city, theme, weather override).
# ------------------------------------------------------------------------------
class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['city', 'theme_preference', 'weather_effect_override']
        widgets = {
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'theme_preference': forms.Select(attrs={'class': 'form-select'}),
            'weather_effect_override': forms.Select(
                attrs={'class': 'form-select', 'id': 'weatherEffectSelect'}
            ),
        }

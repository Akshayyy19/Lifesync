from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Profile


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username', 'autofocus': True})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'you@example.com'}),
    )
    city = forms.CharField(
        required=False,
        initial='Chennai',
        help_text='We use this to show weather on your dashboard. You can change it later.',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Chennai'}),
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
            {'class': 'form-control', 'placeholder': 'Create a password'}
        )
        self.fields['password2'].widget.attrs.update(
            {'class': 'form-control', 'placeholder': 'Confirm password'}
        )

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            city = self.cleaned_data.get('city') or 'Chennai'
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.city = city
            profile.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['city', 'theme_preference', 'weather_effect_override']
        widgets = {
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'theme_preference': forms.Select(attrs={'class': 'form-select'}),
            'weather_effect_override': forms.Select(attrs={'class': 'form-select', 'id': 'weatherEffectSelect'}),
        }

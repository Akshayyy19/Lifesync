# ==============================================================================
# File: accounts/urls.py
# Description: URL routing configuration for accounts, authentication, recovery,
#              and admin user management.
# ==============================================================================

from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import LoginForm

app_name = 'accounts'

urlpatterns = [
    # Registration & Approval
    path('register/', views.register, name='register'),
    path('pending-approval/<str:username>/', views.pending_approval, name='pending_approval'),

    # Authentication
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        authentication_form=LoginForm,
    ), name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Profile & Theme
    path('profile/', views.profile, name='profile'),
    path('toggle-theme/', views.toggle_theme, name='toggle_theme'),

    # Admin User Traffic & Access Control Hub
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/users/<int:user_id>/action/', views.admin_user_action, name='admin_user_action'),

    # Account Recovery (Forgot Username)
    path('forgot-username/', views.forgot_username, name='forgot_username'),

    # Account Recovery (Forgot / Reset Password)
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html',
        success_url=reverse_lazy('accounts:password_reset_complete')
    ), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),
]

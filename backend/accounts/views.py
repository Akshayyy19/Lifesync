# ==============================================================================
# File: accounts/views.py
# Description: Handles user authentication, registration, password recovery,
#              profile settings, and admin user traffic control.
# ==============================================================================

from functools import wraps
import json
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_POST

from notifications.models import Notification
from .forms import (
    CustomPasswordResetForm,
    ForgotUsernameForm,
    LoginForm,
    ProfileForm,
    RegisterForm,
)
from .models import Profile


# ------------------------------------------------------------------------------
# Decorator: admin_required
# Purpose: Strictly restricts view access to staff and superuser administrators.
#          Redirects non-admin members safely to their dashboard with clear feedback
#          to prevent login loops or cached admin leakage.
# ------------------------------------------------------------------------------
def admin_required(view_func):
    """
    Decorator for views requiring administrator (staff or superuser) privileges.
    - If user is not authenticated: redirects to login with ?next=<path>.
    - If user is authenticated as regular member (non-admin):
      immediately redirects to 'core:dashboard' with an 'Access Denied' error message,
      preventing redirect loops, login page confusion, and back-button leakage.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse_lazy('accounts:login')}?next={request.path}")
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(
                request,
                "Access Denied: You do not have administrator permissions to access that page."
            )
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# ------------------------------------------------------------------------------
# View: CustomLoginView
# Purpose: Enhanced login view with dual-account session isolation & auto-redirect.
# ------------------------------------------------------------------------------
class CustomLoginView(auth_views.LoginView):
    """
    Enhanced LoginView:
    1. Sets redirect_authenticated_user = True:
       If a user is already authenticated (admin or member) and visits or backs into
       the login page, they are immediately redirected to their dashboard,
       preventing stale login forms or unintentional dual-session submissions.
    2. Flushes the session on valid authentication:
       Clears all previous session variables, tokens, and cookies before creating
       the new authenticated session to prevent cross-account pollution.
    """
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        # Explicitly flush previous session to prevent cross-account data leakage
        self.request.session.flush()
        return super().form_valid(form)


# ------------------------------------------------------------------------------
# View: register
# Purpose: Handles new user registration with admin approval workflow.
# ------------------------------------------------------------------------------
def register(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile = user.profile
            approval_required = getattr(settings, 'ACCOUNT_APPROVAL_REQUIRED', True)

            # Notify all staff members about the new registration
            today = timezone.localdate()
            admin_users = User.objects.filter(is_staff=True)
            for admin_u in admin_users:
                Notification.objects.create(
                    user=admin_u,
                    notif_type='system',
                    message=f"New user registration: @{user.username} ({user.email}) is awaiting review.",
                    for_date=today,
                )

            # If approval is required and account is not auto-approved
            if approval_required and not profile.is_approved:
                messages.info(
                    request,
                    f"Welcome, {user.username}! Your account was created and is currently pending administrator approval.",
                )
                return redirect('accounts:pending_approval', username=user.username)
            else:
                login(request, user, backend='accounts.backends.EmailOrUsernameBackend')
                messages.success(
                    request,
                    f"Welcome to LifeSync, {user.username}! Your account is ready.",
                )
                return redirect('core:dashboard')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


# ------------------------------------------------------------------------------
# View: pending_approval
# Purpose: Informational waiting screen for newly registered unapproved users.
# ------------------------------------------------------------------------------
def pending_approval(request, username):
    user_obj = User.objects.filter(username=username).first()
    is_approved = False
    if user_obj and hasattr(user_obj, 'profile'):
        is_approved = user_obj.profile.is_approved

    return render(
        request,
        'accounts/pending_approval.html',
        {
            'pending_username': username,
            'user_obj': user_obj,
            'is_approved': is_approved,
        },
    )


# ------------------------------------------------------------------------------
# View: forgot_username
# Purpose: Allows users to retrieve their forgotten username using their email.
# ------------------------------------------------------------------------------
def forgot_username(request):
    found_users = None
    searched_email = None

    if request.method == 'POST':
        form = ForgotUsernameForm(request.POST)
        if form.is_valid():
            searched_email = form.cleaned_data['email'].strip()
            found_users = list(User.objects.filter(email__iexact=searched_email))
            if not found_users:
                messages.error(
                    request,
                    f"No LifeSync account was found associated with '{searched_email}'.",
                )
            else:
                login_url = request.build_absolute_uri(reverse_lazy('accounts:login'))
                reset_url = request.build_absolute_uri(reverse_lazy('accounts:password_reset'))
                
                # Send email notification for each found user
                for user_item in found_users:
                    context = {
                        'user': user_item,
                        'searched_email': searched_email,
                        'login_url': login_url,
                        'reset_url': reset_url,
                    }
                    text_content = render_to_string('accounts/forgot_username_email.txt', context)
                    html_content = render_to_string('accounts/forgot_username_email.html', context)
                    subject = "LifeSync - Your Username Recovery"
                    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'LifeSync <noreply@lifesync.local>')

                    msg = EmailMultiAlternatives(subject, text_content, from_email, [searched_email])
                    msg.attach_alternative(html_content, "text/html")
                    try:
                        msg.send(fail_silently=False)
                    except Exception:
                        pass
                
                messages.success(
                    request,
                    f"We found account(s) linked to '{searched_email}' and sent the username details to your email."
                )
    else:
        form = ForgotUsernameForm()

    return render(
        request,
        'accounts/forgot_username.html',
        {
            'form': form,
            'found_users': found_users,
            'searched_email': searched_email,
        },
    )


# ------------------------------------------------------------------------------
# View: CustomPasswordResetView
# Purpose: Initiates password reset via username or email with dev helper support.
# ------------------------------------------------------------------------------
class CustomPasswordResetView(auth_views.PasswordResetView):
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.txt'
    html_email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    form_class = CustomPasswordResetForm
    success_url = reverse_lazy('accounts:password_reset_done')

    def form_valid(self, form):
        # In debug mode, capture the reset link into session for immediate testing
        if settings.DEBUG:
            email_or_user = form.cleaned_data.get('email')
            user = (
                User.objects.filter(
                    Q(email__iexact=email_or_user) | Q(username__iexact=email_or_user)
                )
                .filter(is_active=True)
                .first()
            )
            if user:
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(str(user.pk).encode('utf-8'))
                self.request.session['dev_reset_uid'] = uid
                self.request.session['dev_reset_token'] = token
                self.request.session['dev_reset_username'] = user.username
        return super().form_valid(form)


# ------------------------------------------------------------------------------
# View: CustomPasswordResetDoneView
# Purpose: Notifies user that reset instructions have been dispatched.
# ------------------------------------------------------------------------------
class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if settings.DEBUG and 'dev_reset_token' in self.request.session:
            ctx['dev_uid'] = self.request.session.get('dev_reset_uid')
            ctx['dev_token'] = self.request.session.get('dev_reset_token')
            ctx['dev_username'] = self.request.session.get('dev_reset_username')
        return ctx


# ------------------------------------------------------------------------------
# View: admin_users (User Traffic & Access Control Dashboard)
# Purpose: Gives admins complete control over user approvals, restrictions & traffic.
# ------------------------------------------------------------------------------
@admin_required
def admin_users(request):
    status_filter = request.GET.get('status', 'all').lower()
    search_query = request.GET.get('q', '').strip()

    # Base queryset with related profile and activity annotations
    users_qs = User.objects.select_related('profile').prefetch_related(
        'events', 'diary_entries'
    ).order_by('-date_joined')

    # Apply search filter
    if search_query:
        users_qs = users_qs.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(profile__city__icontains=search_query)
        )

    # Compute aggregate traffic and user status metrics
    total_count = User.objects.count()
    pending_count = Profile.objects.filter(is_approved=False).count()
    active_count = Profile.objects.filter(is_approved=True, is_restricted=False).count()
    restricted_count = Profile.objects.filter(is_restricted=True).count()
    staff_count = User.objects.filter(is_staff=True).count()

    # Apply status tabs
    if status_filter == 'pending':
        users_qs = users_qs.filter(profile__is_approved=False)
    elif status_filter == 'active':
        users_qs = users_qs.filter(profile__is_approved=True, profile__is_restricted=False)
    elif status_filter == 'restricted':
        users_qs = users_qs.filter(profile__is_restricted=True)
    elif status_filter == 'staff':
        users_qs = users_qs.filter(is_staff=True)

    # Attach event and diary counts for traffic monitoring
    user_list = []
    for u in users_qs:
        event_count = u.events.count()
        diary_count = u.diary_entries.count()
        user_list.append({
            'user': u,
            'profile': getattr(u, 'profile', None),
            'event_count': event_count,
            'diary_count': diary_count,
        })

    context = {
        'user_list': user_list,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_count': total_count,
        'pending_count': pending_count,
        'active_count': active_count,
        'restricted_count': restricted_count,
        'staff_count': staff_count,
    }
    return render(request, 'accounts/admin_users.html', context)


# ------------------------------------------------------------------------------
# View: admin_user_action
# Purpose: Executes user acceptance, restriction, unrestriction, role toggle, or deletion.
# ------------------------------------------------------------------------------
@admin_required
@require_POST
def admin_user_action(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    profile = getattr(target_user, 'profile', None)
    if not profile:
        profile = Profile.objects.create(user=target_user)

    action = request.POST.get('action')

    # Action 1: Accept / Approve user
    if action == 'approve':
        profile.is_approved = True
        profile.is_restricted = False
        profile.approved_at = timezone.now()
        profile.approved_by = request.user
        profile.save()

        # Send in-app notification to approved user
        Notification.objects.create(
            user=target_user,
            notif_type='system',
            message="🎉 Welcome to LifeSync! Your account has been accepted and approved by the administrator.",
            for_date=timezone.localdate(),
        )

        messages.success(
            request, f"User @{target_user.username} has been approved and granted access."
        )

    # Action 2: Restrict / Suspend user
    elif action == 'restrict':
        if target_user == request.user:
            messages.error(request, "You cannot restrict your own account.")
            return redirect('accounts:admin_users')

        if target_user.is_superuser and not request.user.is_superuser:
            messages.error(request, "Only a superuser can restrict another superuser.")
            return redirect('accounts:admin_users')

        reason = request.POST.get('reason', '').strip() or "Restricted by administrator."
        profile.is_restricted = True
        profile.restriction_reason = reason
        profile.save()

        messages.warning(
            request, f"User @{target_user.username} has been restricted. Reason: {reason}"
        )

    # Action 3: Unrestrict / Reactivate user
    elif action == 'unrestrict':
        profile.is_restricted = False
        profile.restriction_reason = ''
        profile.is_approved = True
        profile.save()

        messages.success(
            request, f"Restriction lifted. User @{target_user.username} is now active."
        )

    # Action 4: Delete user
    elif action == 'delete':
        if target_user == request.user:
            messages.error(request, "Security check: You cannot delete your own account.")
            return redirect('accounts:admin_users')

        if target_user.is_superuser and not request.user.is_superuser:
            messages.error(
                request, "Permission denied: Only a superuser can delete a superuser account."
            )
            return redirect('accounts:admin_users')

        deleted_username = target_user.username
        target_user.delete()
        messages.success(
            request, f"User @{deleted_username} and all associated data have been permanently deleted."
        )

    # Action 5: Toggle Admin / Staff privilege
    elif action == 'toggle_staff':
        if not request.user.is_superuser:
            messages.error(request, "Only superusers can grant or revoke admin staff privileges.")
            return redirect('accounts:admin_users')

        if target_user == request.user:
            messages.error(request, "You cannot modify your own staff privileges.")
            return redirect('accounts:admin_users')

        target_user.is_staff = not target_user.is_staff
        target_user.save()
        status_text = "Staff Admin" if target_user.is_staff else "Regular Member"
        messages.info(
            request, f"Role updated: @{target_user.username} is now a {status_text}."
        )

    return redirect('accounts:admin_users')


# ------------------------------------------------------------------------------
# View: profile
# Purpose: Allows logged-in users to update their profile settings (city, theme).
# ------------------------------------------------------------------------------
@login_required
def profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=profile_obj)

    return render(request, 'accounts/profile.html', {'form': form})


# ------------------------------------------------------------------------------
# View: toggle_theme
# Purpose: Quick AJAX endpoint to update the user's theme preference.
# ------------------------------------------------------------------------------
@login_required
@require_POST
def toggle_theme(request):
    try:
        body = json.loads(request.body.decode('utf-8'))
        theme = body.get('theme')
    except Exception:
        theme = request.POST.get('theme')

    if theme in ('day', 'night', 'auto'):
        profile_obj, _ = Profile.objects.get_or_create(user=request.user)
        profile_obj.theme_preference = theme
        profile_obj.save(update_fields=['theme_preference'])
        return JsonResponse({'status': 'ok', 'theme_preference': theme})

    return JsonResponse({'status': 'error', 'message': 'Invalid theme value.'}, status=400)


# ------------------------------------------------------------------------------
# View: logout_view
# Purpose: Logs out the user and redirects to login page with feedback.
#          Accepts both GET and POST requests for seamless exit from admin and navbar.
#          Flushes the session completely and applies strict no-cache headers.
# ------------------------------------------------------------------------------
def logout_view(request):
    if request.user.is_authenticated:
        username = request.user.username
        logout(request)
        messages.info(request, f"You have been safely logged out, @{username}.")
    else:
        logout(request)
    request.session.flush()
    response = redirect('accounts:login')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

# ==============================================================================
# File: accounts/views.py
# Description: Handles user registration and profile management views.
# ==============================================================================

# Import Django's messages framework to display one-time feedback alerts (success, error) to users
from django.contrib import messages

# Import Django's login function to establish a session for newly registered users
from django.contrib.auth import login

# Import login_required decorator to ensure views can only be viewed by authenticated users
from django.contrib.auth.decorators import login_required

# Import redirect (for URL redirection after form actions) and render (to render HTML templates)
from django.shortcuts import redirect, render

# Import custom form classes for user profile editing and registration
from .forms import ProfileForm, RegisterForm


# ------------------------------------------------------------------------------
# View: register
# Purpose: Handles new user registration via GET (display form) and POST (submit data).
# ------------------------------------------------------------------------------
def register(request):
    # If the user is already logged in, they don't need to register; redirect to dashboard
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    # Check if the HTTP request is submitting form data (POST)
    if request.method == 'POST':
        # Instantiate the registration form bound with the submitted POST data
        form = RegisterForm(request.POST)

        # Validate form inputs (e.g. check username availability, password rules and confirmation)
        if form.is_valid():
            # Save the new user instance to the database
            user = form.save()

            # Log the user into the current session immediately after registration
            login(request, user)

            # Flash a welcoming success message to be displayed on the next page
            messages.success(request, f'Welcome to LifeSync, {user.username}! Your account is ready.')

            # Redirect user directly to their personal dashboard
            return redirect('core:dashboard')
    else:
        # If the request method is GET, instantiate an empty, unbound registration form
        form = RegisterForm()

    # Render registration page template, passing the form object into the context
    return render(request, 'accounts/register.html', {'form': form})


# ------------------------------------------------------------------------------
# View: profile
# Purpose: Allows logged-in users to update their profile settings (city, theme).
# ------------------------------------------------------------------------------
@login_required  # Restrict access so only authenticated users can edit profile settings
def profile(request):
    # Retrieve the Profile instance associated with the currently logged-in user
    profile_obj = request.user.profile

    # Check if the user is submitting updated profile data
    if request.method == 'POST':
        # Bind the submitted POST data to the existing Profile model instance
        form = ProfileForm(request.POST, instance=profile_obj)

        # Check if the submitted data meets all model validation constraints
        if form.is_valid():
            # Save updated fields (e.g. city, theme_preference) to the database
            form.save()

            # Display a success alert confirming the changes have been saved
            messages.success(request, 'Your profile has been updated.')

            # Redirect back to profile page to avoid duplicate form submission on page refresh
            return redirect('accounts:profile')
    else:
        # For GET requests, pre-populate the form with the current user's saved profile values
        form = ProfileForm(instance=profile_obj)

    # Render the profile template with the populated form
    return render(request, 'accounts/profile.html', {'form': form})

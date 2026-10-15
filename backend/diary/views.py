# ==============================================================================
# File: diary/views.py
# Description: Views handling CRUD operations for personal diary entries.
# ==============================================================================

# Import messages framework to display feedback notifications (success, error)
from django.contrib import messages

# Import login_required decorator to restrict view access to authenticated users only
from django.contrib.auth.decorators import login_required

# Import shortcuts: get_object_or_404 (safely retrieve model or return HTTP 404), redirect, render
from django.shortcuts import get_object_or_404, redirect, render

# Import timezone module to fetch the current local date
from django.utils import timezone

# Import weather helper to query current temperature and conditions for the user's city
from weather.services import get_current_weather

# Import ModelForm for DiaryEntry
from .forms import DiaryEntryForm

# Import DiaryEntry database model
from .models import DiaryEntry


# ------------------------------------------------------------------------------
# Helper Function: _attach_weather_snapshot
# Purpose: Automatically captures current weather when a diary entry is recorded.
# ------------------------------------------------------------------------------
def _attach_weather_snapshot(entry, user):
    """Best-effort: silently skip if the API/profile isn't available."""
    try:
        # Retrieve user's configured city from their profile with safe fallback
        profile = getattr(user, 'profile', None)
        city = getattr(profile, 'city', None) or 'Chennai'
        # Query current live weather data for this city
        weather = get_current_weather(city)
        if weather:
            # Assign current temperature and weather description to the diary model instance
            entry.weather_temp = weather.get('temp')
            entry.weather_condition = weather.get('description')
    except Exception:
        # Catch network/API errors and fail silently so diary saving is never blocked
        pass


# ------------------------------------------------------------------------------
# View: diary_list
# Purpose: Lists all diary entries written by the current user.
# ------------------------------------------------------------------------------
@login_required
def diary_list(request):
    # Fetch all diary entries belonging to the logged-in user (ordered by date desc via Model Meta)
    entries = DiaryEntry.objects.filter(user=request.user)
    # Render the diary listing template
    return render(request, 'diary/diary_list.html', {'entries': entries})


# ------------------------------------------------------------------------------
# View: diary_detail
# Purpose: Shows the full content, mood, and weather details of a single entry.
# ------------------------------------------------------------------------------
@login_required
def diary_detail(request, pk):
    # Retrieve specific entry by primary key, verifying that it belongs to the current user
    entry = get_object_or_404(DiaryEntry, pk=pk, user=request.user)
    # Render the detailed view template
    return render(request, 'diary/diary_detail.html', {'entry': entry})


# ------------------------------------------------------------------------------
# View: diary_create
# Purpose: Creates a new diary entry, capturing date, mood, content, and weather.
# ------------------------------------------------------------------------------
@login_required
def diary_create(request):
    # Check if form was submitted
    if request.method == 'POST':
        # Bind submitted POST data to DiaryEntryForm
        form = DiaryEntryForm(request.POST)
        if form.is_valid():
            # Create instance in memory without saving to database yet
            entry = form.save(commit=False)
            # Set current user as author
            entry.user = request.user
            # Attach weather snapshot
            _attach_weather_snapshot(entry, request.user)
            # Save record to database
            entry.save()
            # Flash success message
            messages.success(request, 'Your diary entry was saved.')
            # Redirect to newly created entry's detail page
            return redirect('diary:detail', pk=entry.pk)
    else:
        # For GET requests, initialize form with today's date pre-filled
        form = DiaryEntryForm(initial={'date': timezone.localdate()})

    # Render diary creation form template
    return render(request, 'diary/diary_form.html', {'form': form, 'action': 'New'})


# ------------------------------------------------------------------------------
# View: diary_update
# Purpose: Edit an existing diary entry.
# ------------------------------------------------------------------------------
@login_required
def diary_update(request, pk):
    # Fetch entry verifying ownership
    entry = get_object_or_404(DiaryEntry, pk=pk, user=request.user)

    if request.method == 'POST':
        # Bind submitted data to existing entry instance
        form = DiaryEntryForm(request.POST, instance=entry)
        if form.is_valid():
            # Save updated fields to database
            form.save()
            messages.success(request, 'Your diary entry was updated.')
            return redirect('diary:detail', pk=entry.pk)
    else:
        # Pre-populate form with existing entry data
        form = DiaryEntryForm(instance=entry)

    # Render edit form template
    return render(request, 'diary/diary_form.html', {'form': form, 'action': 'Edit', 'entry': entry})


# ------------------------------------------------------------------------------
# View: diary_delete
# Purpose: Delete an existing diary entry upon confirmation.
# ------------------------------------------------------------------------------
@login_required
def diary_delete(request, pk):
    # Fetch entry verifying ownership
    entry = get_object_or_404(DiaryEntry, pk=pk, user=request.user)

    if request.method == 'POST':
        # Delete entry from database
        entry.delete()
        messages.success(request, 'Diary entry deleted.')
        # Redirect back to diary entries list
        return redirect('diary:list')

    # Render confirmation prompt template
    return render(request, 'diary/diary_confirm_delete.html', {'entry': entry})

# ==============================================================================
# File: notifications/views.py
# Description: Views for viewing and acknowledging user notifications.
# ==============================================================================

# Import login_required decorator to enforce user authentication
from django.contrib.auth.decorators import login_required

# Import shortcut functions for retrieval, redirection, and HTML template rendering
from django.shortcuts import get_object_or_404, redirect, render

# Import Notification model
from .models import Notification

# Import utility function to generate any missing notifications for upcoming events
from .utils import generate_notifications


# ------------------------------------------------------------------------------
# View: notifications_list
# Purpose: Displays all notifications for the logged-in user.
# ------------------------------------------------------------------------------
@login_required
def notifications_list(request):
    # Ensure all notifications for today/tomorrow are generated before rendering list
    generate_notifications(request.user)

    # Fetch all notifications belonging to the current user (ordered by -created_at)
    notifications = Notification.objects.filter(user=request.user)

    # Render notifications listing template
    return render(request, 'notifications/notifications_list.html', {'notifications': notifications})


# ------------------------------------------------------------------------------
# View: mark_read
# Purpose: Marks a single notification as read.
# ------------------------------------------------------------------------------
@login_required
def mark_read(request, pk):
    # Fetch notification ensuring ownership by the requesting user
    notification = get_object_or_404(Notification, pk=pk, user=request.user)

    # Update read status to True
    notification.is_read = True

    # Save changes to database
    notification.save()

    # Redirect back to the notification list page
    return redirect('notifications:list')


# ------------------------------------------------------------------------------
# View: mark_all_read
# Purpose: Bulk marks all unread notifications as read for the user.
# ------------------------------------------------------------------------------
@login_required
def mark_all_read(request):
    # Bulk update all unread notifications for this user in a single SQL query
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    # Redirect back to the notifications list
    return redirect('notifications:list')

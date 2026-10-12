# ==============================================================================
# File: lifesync/urls.py
# Description: Root URL routing configuration for the LifeSync project.
# ==============================================================================

# Import Django admin site routing handler
from django.contrib import admin

# Import path (for defining route patterns) and include (for including sub-app URL configurations)
from django.urls import path, include

# Import project settings to check DEBUG flag and locate static file paths
from django.conf import settings

# Import static helper to serve static media files during local development
from django.conf.urls.static import static

# Master URL patterns list that dispatches incoming web requests to respective apps
urlpatterns = [
    # Route for Django's built-in Admin management panel
    path('admin/', admin.site.urls),

    # Root route ('/') routed to the 'core' app (home page and main dashboard)
    path('', include('core.urls')),

    # User authentication routes ('/accounts/login/', '/accounts/register/', etc.)
    path('accounts/', include('accounts.urls')),

    # Calendar, event scheduling, and reminder routes ('/planner/')
    path('planner/', include('planner.urls')),

    # Personal diary and journaling routes ('/diary/')
    path('diary/', include('diary.urls')),

    # Real-time weather forecasting and timeline routes ('/weather/')
    path('weather/', include('weather.urls')),

    # In-app user notifications and alerts routes ('/notifications/')
    path('notifications/', include('notifications.urls')),
]

# During local development (DEBUG=True), configure Django to serve static files directly
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

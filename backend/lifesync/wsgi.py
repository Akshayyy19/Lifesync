"""WSGI config for the LifeSync project."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lifesync.settings')

application = get_wsgi_application()

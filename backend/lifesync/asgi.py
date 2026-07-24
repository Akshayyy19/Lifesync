"""ASGI config for the LifeSync project."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lifesync.settings')

application = get_asgi_application()

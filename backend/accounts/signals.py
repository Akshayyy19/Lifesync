from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=User)
def create_or_save_profile(sender, instance, created, **kwargs):
    """Every User automatically gets a matching Profile the moment they register."""
    if created:
        approval_required = getattr(settings, 'ACCOUNT_APPROVAL_REQUIRED', True)
        # Superusers and staff are automatically approved; regular members require approval if enabled
        is_approved = not approval_required if not (instance.is_superuser or instance.is_staff) else True
        Profile.objects.create(user=instance, is_approved=is_approved)
    else:
        Profile.objects.get_or_create(user=instance)


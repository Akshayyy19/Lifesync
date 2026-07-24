from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from notifications.utils import generate_notifications


class Command(BaseCommand):
    help = 'Generates notifications for every user based on their upcoming events, birthdays and reminders.'

    def handle(self, *args, **options):
        count = 0
        for user in User.objects.all():
            generate_notifications(user)
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Notifications generated for {count} user(s).'))

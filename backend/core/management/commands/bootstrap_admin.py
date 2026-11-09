import os

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Create the initial WASELNI admin account"

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.getenv("BOOTSTRAP_ADMIN_USERNAME")
        email = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")

        if not all([username, email, password]):
            raise CommandError("Missing admin environment variables.")

        if User.objects.filter(username=username).exists():
            self.stdout.write("Admin account already exists.")
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )

        self.stdout.write(
            self.style.SUCCESS("WASELNI admin created successfully.")
        )
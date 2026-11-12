import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Cree le compte proprietaire unique (variables KPS_ADMIN_* ou options)."

    def add_arguments(self, parser):
        parser.add_argument("--username")
        parser.add_argument("--email", default=None)

    def handle(self, *args, **opts):
        User = get_user_model()
        username = opts["username"] or os.environ.get("KPS_ADMIN_USERNAME")
        password = os.environ.get("KPS_ADMIN_PASSWORD")
        email = opts["email"] or os.environ.get("KPS_ADMIN_EMAIL", "")
        if not username or not password:
            raise CommandError("KPS_ADMIN_USERNAME et KPS_ADMIN_PASSWORD sont requis.")
        if User.objects.filter(username=username).exists():
            self.stdout.write("Le proprietaire existe deja : rien a faire.")
            return
        try:
            validate_password(password)
        except ValidationError as e:
            raise CommandError("; ".join(e.messages))
        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Proprietaire '{username}' cree."))

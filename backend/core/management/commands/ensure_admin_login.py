import getpass
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from backend.core.models import Giocatore
from backend.core.security import get_or_create_giocatore_for_user


class Command(BaseCommand):
    help = "Garantisce che esista almeno un amministratore con una password utilizzabile."

    def handle(self, *args, **options):
        User = get_user_model()
        usable_admin = next(
            (
                user
                for user in User.objects.filter(is_active=True, is_superuser=True).order_by("id")
                if user.has_usable_password()
            ),
            None,
        )
        if usable_admin is not None:
            self.stdout.write(f"Accesso amministratore disponibile: {usable_admin.get_username()}")
            return

        username = os.environ.get("REDJANGO_ADMIN_USERNAME", "").strip()
        password = os.environ.get("REDJANGO_ADMIN_PASSWORD", "")
        game_role = os.environ.get(
            "REDJANGO_ADMIN_GAME_ROLE",
            Giocatore.ROLE_ADMIN,
        ).strip().lower()
        if game_role not in Giocatore.ROLE_RANKS:
            raise CommandError("REDJANGO_ADMIN_GAME_ROLE deve essere user, master oppure admin.")
        if not username:
            if not os.isatty(0):
                raise CommandError(
                    "Nessun amministratore configurato. Imposta REDJANGO_ADMIN_USERNAME e "
                    "REDJANGO_ADMIN_PASSWORD oppure esegui manage.py createsuperuser."
                )
            username = input("Nome del primo amministratore [redjango_admin]: ").strip() or "redjango_admin"
        if not password:
            if not os.isatty(0):
                raise CommandError(
                    "Imposta REDJANGO_ADMIN_PASSWORD oppure esegui manage.py createsuperuser."
                )
            password = getpass.getpass("Password: ")
            confirmation = getpass.getpass("Ripeti password: ")
            if password != confirmation:
                raise CommandError("Le password non coincidono.")

        existing = User.objects.filter(username=username).first()
        candidate = existing or User(username=username)
        try:
            validate_password(password, user=candidate)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error

        if existing is None:
            user = User.objects.create_superuser(username=username, password=password)
        else:
            user = existing
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save(update_fields=["is_active", "is_staff", "is_superuser", "password"])

        giocatore = get_or_create_giocatore_for_user(user)
        if giocatore.role != game_role:
            giocatore.role = game_role
            giocatore.save(update_fields=["role", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"Amministratore configurato: {username}"))

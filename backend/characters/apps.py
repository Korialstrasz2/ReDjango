from django.apps import AppConfig


class CharactersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.characters"
    verbose_name = "Personaggi"

    def ready(self):
        from . import signals  # noqa: F401

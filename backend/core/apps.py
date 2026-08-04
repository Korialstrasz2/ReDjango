from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.core"
    verbose_name = "Nucleo ReDjango"

    def ready(self) -> None:
        from .theme_reveal_patch import install

        install()

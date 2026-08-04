from django.apps import AppConfig


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.ai"
    verbose_name = "Intelligenza artificiale"

    def ready(self) -> None:
        from .master_runtime import install

        install()

from django.apps import AppConfig


class LoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.lore"
    label = "lore"
    verbose_name = "Lore di campagna"

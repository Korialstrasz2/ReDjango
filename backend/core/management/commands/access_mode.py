from django.core.management.base import BaseCommand, CommandError

from backend.core.access import (
    ACCESS_MODES,
    ACCESS_MODE_ONLINE,
    ACCESS_MODE_SETTING_KEY,
    normalize_access_mode,
    online_configuration_errors,
    persist_access_mode,
)
from backend.core.models import SettingDefinition


class Command(BaseCommand):
    help = "Legge o imposta la modalità globale di accesso usata dal launcher."

    def add_arguments(self, parser):
        parser.add_argument("--set", dest="new_mode", choices=ACCESS_MODES)

    def handle(self, *args, **options):
        setting = SettingDefinition.objects.filter(key=ACCESS_MODE_SETTING_KEY).first()
        if setting is None:
            raise CommandError("Esegui prima migrate e seed_minimum_data.")

        if options["new_mode"]:
            if options["new_mode"] == ACCESS_MODE_ONLINE:
                missing = online_configuration_errors()
                if missing:
                    raise CommandError(
                        "Configura prima " + " e ".join(missing) + " nell'ambiente del launcher."
                    )
            setting.value = options["new_mode"]
            setting.save(update_fields=["value", "updated_at"])
            persist_access_mode(options["new_mode"])

        self.stdout.write(normalize_access_mode(setting.base_value))

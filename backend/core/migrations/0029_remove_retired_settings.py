from django.db import migrations


RETIRED_SETTING_KEYS = (
    "dice.color",
    "master.confirm_dangerous_actions",
    "master.show_master_tools",
    "branding.app_name",
    "branding.subtitle",
)


def remove_retired_settings(apps, schema_editor):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    SettingDefinition.objects.filter(key__in=RETIRED_SETTING_KEYS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0028_timeline_chronological_order"),
    ]

    operations = [
        migrations.RunPython(remove_retired_settings, migrations.RunPython.noop),
    ]

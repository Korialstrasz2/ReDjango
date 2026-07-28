from django.db import migrations


def remove_character_shortcut(apps, schema_editor):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    SettingDefinition.objects.filter(key="shortcuts.characters").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0034_daticampagna_monete_condivise"),
    ]

    operations = [
        migrations.RunPython(remove_character_shortcut, migrations.RunPython.noop),
    ]

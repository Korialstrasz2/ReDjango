from django.db import migrations


# Companion to core.0036: the same two dead ratios are stored per character in
# Personaggio.tot and have to disappear from there too.
DEAD_KEYS = ("en_per_mana", "pa_per_mana")


def drop_dead_totals(apps, schema_editor):
    Personaggio = apps.get_model("characters", "Personaggio")
    for personaggio in Personaggio.objects.all().only("id", "tot"):
        totals = personaggio.tot
        if not isinstance(totals, dict):
            continue
        remaining = {key: value for key, value in totals.items() if key not in DEAD_KEYS}
        if len(remaining) != len(totals):
            personaggio.tot = remaining
            personaggio.save(update_fields=["tot"])


class Migration(migrations.Migration):

    dependencies = [
        ("characters", "0024_personaggio_impostazioni_combat"),
        ("core", "0036_drop_dead_mana_ratio_keys"),
    ]

    operations = [
        migrations.RunPython(drop_dead_totals, migrations.RunPython.noop),
    ]

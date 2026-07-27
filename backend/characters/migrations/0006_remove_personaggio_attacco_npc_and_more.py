from django.db import migrations


NEW_TOT_KEYS = [
    "mod_forza",
    "mod_resistenza",
    "mod_velocita",
    "mod_agilita",
    "mod_intelligenza",
    "mod_concentrazione",
    "mod_personalita",
    "mod_saggezza",
    "mod_fortuna",
    "malus_carico",
]

NPC_FIELD_TO_TOT_KEY = [
    ("attacco_npc", "attacco"),
    ("difesa_npc", "difesa"),
]


def _zero_if_none(value):
    return 0 if value is None else value


def _is_non_zero(value):
    return value not in (None, 0, 0.0)


def move_npc_fields_into_tot(apps, schema_editor):
    Personaggio = apps.get_model("characters", "Personaggio")

    for personaggio in Personaggio.objects.all().only("id", "tot", "attacco_npc", "difesa_npc").iterator():
        tot = dict(personaggio.tot or {})
        changed = False

        for key in NEW_TOT_KEYS:
            if key not in tot:
                tot[key] = 0
                changed = True

        for field_name, key in NPC_FIELD_TO_TOT_KEY:
            value = getattr(personaggio, field_name)
            if _is_non_zero(value):
                tot[key] = value
                changed = True

        if changed:
            personaggio.tot = tot
            personaggio.save(update_fields=["tot"])


def restore_npc_fields_from_tot(apps, schema_editor):
    Personaggio = apps.get_model("characters", "Personaggio")

    for personaggio in Personaggio.objects.all().only("id", "tot", "attacco_npc", "difesa_npc").iterator():
        tot = personaggio.tot or {}
        update_fields = []

        for field_name, key in NPC_FIELD_TO_TOT_KEY:
            value = _zero_if_none(tot.get(key))
            if getattr(personaggio, field_name) != value:
                setattr(personaggio, field_name, value)
                update_fields.append(field_name)

        if update_fields:
            personaggio.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('characters', '0005_delete_character'),
    ]

    operations = [
        migrations.RunPython(move_npc_fields_into_tot, restore_npc_fields_from_tot),
        migrations.RemoveField(
            model_name='personaggio',
            name='attacco_npc',
        ),
        migrations.RemoveField(
            model_name='personaggio',
            name='difesa_npc',
        ),
    ]

"""Il modificatore generale non è un malus "a tutto".

"Tick Giallo" toglie 1 a ogni competenza, quindi ora punta ai bersagli
``competenza.*``. "Spasmi" vale su ogni tiro di dado, che nessun bersaglio sa
esprimere: torna descrittivo invece di fingere una matematica sbagliata.
"""

from django.db import migrations

RETARGETED = ("Tick Giallo", "Spasmi")


def retarget(apps, schema_editor):
    from backend.characters.effect_preset_defaults import DEFAULT_EFFECT_PRESETS

    EffettoPreset = apps.get_model("characters", "EffettoPreset")
    wanted = {definition["name"]: definition for definition in DEFAULT_EFFECT_PRESETS}
    for name in RETARGETED:
        EffettoPreset.objects.filter(nome=name).update(operazioni=wanted[name]["operations"])


def restore_general_modifier(apps, schema_editor):
    EffettoPreset = apps.get_model("characters", "EffettoPreset")
    EffettoPreset.objects.filter(nome__in=RETARGETED).update(
        operazioni=[{"target": "modificatore_generale", "operation": "subtract", "value": "1", "condition": ""}]
    )


class Migration(migrations.Migration):
    dependencies = [("characters", "0027_seed_effect_presets")]

    operations = [migrations.RunPython(retarget, restore_general_modifier)]

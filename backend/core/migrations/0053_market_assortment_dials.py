"""Teach the saved Mercato rules to stock an assortment instead of a stack.

The generator rolled a template's weight fresh on every draw, so the handful of
heavy templates in a shop's top rank took the roll again and again until the
copy cap stopped them: a shop with sixty items on the shelf was routinely
fifteen different things. Adding the dials to the code is not enough, because
``validate_generator_rules`` merges its defaults *under* the stored value only
for keys the value does not have - a saved dict simply carries on without them.

``quantityScale`` moves only when it still holds the old neutral 1, so an
administrator who already tuned shop size keeps their number.
"""

from django.db import migrations


SETTING_KEY = "mercato.generator_rules"
ASSORTMENT_DIALS = {"varietyBias": .35, "levelSpread": 1, "levelSpreadWeight": .5}
PREVIOUS_QUANTITY_SCALE = 1
QUANTITY_SCALE = 1.4


def _patch(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    changed = False
    for key, value in ASSORTMENT_DIALS.items():
        if key not in payload:
            payload[key] = value
            changed = True
    if payload.get("quantityScale", PREVIOUS_QUANTITY_SCALE) == PREVIOUS_QUANTITY_SCALE:
        payload["quantityScale"] = QUANTITY_SCALE
        changed = True
    return changed


def _strip(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    changed = False
    for key in ASSORTMENT_DIALS:
        changed = payload.pop(key, None) is not None or changed
    if payload.get("quantityScale") == QUANTITY_SCALE:
        payload["quantityScale"] = PREVIOUS_QUANTITY_SCALE
        changed = True
    return changed


def _apply(patch):
    def run(apps, _schema_editor):
        SettingDefinition = apps.get_model("core", "SettingDefinition")
        for setting in SettingDefinition.objects.filter(key=SETTING_KEY):
            fields = [field for field in ("value", "default_value") if patch(getattr(setting, field))]
            if fields:
                setting.save(update_fields=[*fields, "updated_at"])

    return run


class Migration(migrations.Migration):

    dependencies = [("core", "0052_curate_shop_rarities")]

    operations = [migrations.RunPython(_apply(_patch), _apply(_strip))]

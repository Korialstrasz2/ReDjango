"""Give rarity 5 a share in every saved Mercato generation profile.

The profile editor and both validators only ever knew rarities 1-4, so items
with rarity 5 could not be drawn by any shop, at any level, under any profile.
Adding the rarity to the code is not enough: profiles already saved in the
database would normalise the new key to 0 and stay exactly as unreachable.

Each missing rarity therefore receives half the share of the rarity just below
it - rarer than its neighbour, which is the only assumption the data supports -
and the whole distribution is rescaled back to 1. Administrators can retune the
numbers afterwards from Gestione Negozi; the point here is that the bucket is no
longer empty.
"""

from django.db import migrations


SETTING_KEYS = ("mercato.generation_profiles", "mercato.generator_rules")
# Historical snapshot of the rollable rarities: Oggetto.Rarita without Unico,
# which is assigned by hand and never generated.
ROLLABLE_RARITIES = ("1", "2", "3", "4", "5")


def _with_missing_rarities(probabilities: dict) -> dict | None:
    """Return a rescaled distribution, or None when nothing was missing."""
    missing = [rarity for rarity in ROLLABLE_RARITIES if rarity not in probabilities]
    if not missing:
        return None
    values = {}
    for rarity in ROLLABLE_RARITIES:
        if rarity in probabilities:
            try:
                values[rarity] = float(probabilities[rarity] or 0)
            except (TypeError, ValueError):
                return None
        else:
            index = ROLLABLE_RARITIES.index(rarity)
            previous = values.get(ROLLABLE_RARITIES[index - 1], 0) if index else 0
            values[rarity] = previous / 2
    total = sum(values.values())
    if total <= 0:
        return None
    scaled = {rarity: round(value / total, 4) for rarity, value in values.items()}
    # Rounding leaves a few ten-thousandths; park them on the commonest rarity
    # so the distribution still sums to exactly 1.
    scaled[ROLLABLE_RARITIES[0]] = round(
        scaled[ROLLABLE_RARITIES[0]] + (1 - sum(scaled.values())), 4
    )
    return scaled


def _patch_container(container: dict) -> bool:
    probabilities = container.get("rarityProbabilities")
    if not isinstance(probabilities, dict) or not probabilities:
        return False
    patched = _with_missing_rarities(probabilities)
    if patched is None:
        return False
    container["rarityProbabilities"] = patched
    return True


def _patch_payload(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    changed = _patch_container(payload)
    for profile in payload.get("profiles") or []:
        if isinstance(profile, dict):
            changed = _patch_container(profile) or changed
    return changed


def add_rarity_five(apps, _schema_editor):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    for setting in SettingDefinition.objects.filter(key__in=SETTING_KEYS):
        fields = [field for field in ("value", "default_value") if _patch_payload(getattr(setting, field))]
        if fields:
            setting.save(update_fields=[*fields, "updated_at"])


class Migration(migrations.Migration):

    dependencies = [("core", "0038_spell_costs_single_source")]

    operations = [migrations.RunPython(add_rarity_five, migrations.RunPython.noop)]

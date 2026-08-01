"""Restore the 27 item types Elder ranked but the Mercato port dropped.

Elder's `django_slim/negozio.py` ranked 78 `tipo_1` values across all 11 shop
types; ReDjango's `mercato.shop_types` only carried 52 across. The 26 missing
ones are the "cultural" weapon subtypes (katana, kriss, rapier, tonfa, ...),
plus `grimorio` and `altareincantamento` — every one of them a real, stocked
`tipo_1` in the imported catalogue, and every one unreachable by the generator
because `itemTypeRanks` had no key for it.

The ranks below are Elder's own values, read straight out of
`oggetti_per_negozio`, not re-derived. One correction is applied: Elder spelt
the lockpick set `setscassinamneto`, so its five catalogue items (`tipo_1`
`setscassinamento`) never matched a rank key there either. The typo is fixed
here rather than reproduced.

Only ranks below 5 are written: rank 5 means "never stocked", which is exactly
what an absent key already means, and the live config stores it that way.

The saved setting still held the pre-rank `itemWeights` shape, which
`validate_shop_types` converts on every read. New ranks cannot be expressed as
weights without inventing magnitudes, so this migration first normalises each
type to `itemTypeRanks` using that validator's own thresholds — the value the
service already computed at runtime — and then merges Elder's ranks in.
"""

from django.db import migrations

SETTING_KEY = "mercato.shop_types"

# shop key -> {tipo_1: Elder rank}, ranks 0-4 only.
ELDER_RANKS: dict[str, dict[str, int]] = {
    "generale": {
        "accetta": 2, "accettadalancio": 4, "altareincantamento": 4, "armblade": 4,
        "asciaaduemani": 4, "balestraaripetizione": 4, "bastone": 1, "bastoneconpesi": 3,
        "beccodicorvo": 4, "chukonu": 4, "coltellodalancio": 4, "estoc": 4, "fioretto": 4,
        "grimorio": 3, "katana": 4, "kriss": 4, "kusarigama": 4, "mazzafrusta": 4,
        "nunchaku": 3, "picca": 4, "rapier": 4, "sciabola": 3, "setscassinamento": 4,
        "shiv": 4, "shuriken": 4, "stiletto": 3, "tirapugni": 3, "tonfa": 4, "zweihander": 4,
    },
    "fabbro": {
        "accetta": 2, "accettadalancio": 3, "armblade": 4, "bastone": 4, "chukonu": 4,
        "coltellodalancio": 3, "estoc": 3, "fioretto": 3, "katana": 3, "kriss": 4,
        "kusarigama": 4, "mazzafrusta": 3, "nunchaku": 3, "picca": 4, "rapier": 3,
        "sciabola": 3, "setscassinamento": 4, "shiv": 3, "shuriken": 4, "stiletto": 3,
        "tirapugni": 3, "tonfa": 4, "zweihander": 4,
    },
    "armaiolo": {"tirapugni": 4},
    "fabbricante-armi": {
        "accetta": 0, "accettadalancio": 0, "armblade": 1, "asciaaduemani": 0,
        "balestraaripetizione": 0, "bastone": 0, "bastoneconpesi": 0, "beccodicorvo": 0,
        "chukonu": 1, "coltellodalancio": 0, "estoc": 0, "fioretto": 0, "katana": 1,
        "kriss": 1, "kusarigama": 2, "mazzafrusta": 0, "nunchaku": 1, "picca": 0,
        "rapier": 0, "sciabola": 0, "shiv": 1, "shuriken": 1, "stiletto": 1,
        "tirapugni": 0, "tonfa": 1, "zweihander": 0,
    },
    "arcieria": {
        "accettadalancio": 4, "balestraaripetizione": 1, "chukonu": 1,
        "coltellodalancio": 4, "kriss": 4, "shuriken": 4, "tirapugni": 4,
    },
    "alchimista": {"grimorio": 4},
    "oggetti-magici": {"altareincantamento": 4, "grimorio": 0},
    "contenitori": {
        "asciaaduemani": 3, "bastoneconpesi": 4, "beccodicorvo": 3, "grimorio": 4,
    },
    "taverna": {"bastone": 4, "setscassinamento": 4, "shiv": 4, "tirapugni": 4},
    "carovana-khajiit": {
        key: 1
        for key in (
            "accetta", "accettadalancio", "altareincantamento", "armblade", "asciaaduemani",
            "balestraaripetizione", "bastone", "bastoneconpesi", "beccodicorvo", "chukonu",
            "coltellodalancio", "estoc", "fioretto", "grimorio", "katana", "kriss",
            "kusarigama", "mazzafrusta", "nunchaku", "picca", "rapier", "sciabola",
            "setscassinamento", "shiv", "shuriken", "stiletto", "tirapugni", "tonfa",
            "zweihander",
        )
    },
}


def _ranks_from_weights(weights: dict) -> dict[str, int]:
    """Mirror `validate_shop_types`'s legacy conversion, thresholds included."""
    try:
        values = {str(item_type): float(weight) for item_type, weight in weights.items()}
    except (TypeError, ValueError):
        return {}
    maximum = max(values.values(), default=0)
    return {
        item_type: 0 if weight >= maximum * .8 else 1 if weight >= maximum * .6 else 2 if weight >= maximum * .4 else 3
        for item_type, weight in values.items()
    }


def _apply(container: dict, adding: bool) -> bool:
    types = container.get("types")
    if not isinstance(types, list):
        return False
    changed = False
    for shop_type in types:
        if not isinstance(shop_type, dict):
            continue
        ranks = shop_type.get("itemTypeRanks")
        if not isinstance(ranks, dict) or not ranks:
            # Legacy `itemWeights` shape: normalise to the rank contract first,
            # otherwise there is nothing for the new keys to join.
            weights = shop_type.get("itemWeights")
            if adding and isinstance(weights, dict) and weights:
                ranks = _ranks_from_weights(weights)
                if not ranks:
                    continue
                shop_type["itemTypeRanks"] = ranks
                shop_type.pop("itemWeights", None)
                changed = True
            else:
                continue
        wanted = ELDER_RANKS.get(shop_type.get("key"))
        if not wanted:
            continue
        for item_type, rank in wanted.items():
            if adding:
                # Never clobber a rank a master already tuned by hand.
                if item_type not in ranks:
                    ranks[item_type] = rank
                    changed = True
            elif ranks.get(item_type) == rank:
                del ranks[item_type]
                changed = True
    return changed


def _migrate(apps, adding: bool):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    setting = SettingDefinition.objects.filter(key=SETTING_KEY).first()
    if setting is None:
        return
    fields = []
    for field in ("value", "default_value"):
        container = getattr(setting, field)
        if isinstance(container, dict) and _apply(container, adding):
            fields.append(field)
    if fields:
        setting.save(update_fields=fields)


def add_ranks(apps, schema_editor):
    _migrate(apps, adding=True)


def remove_ranks(apps, schema_editor):
    """Drop the added ranks again.

    The `itemWeights` -> `itemTypeRanks` normalisation is deliberately not
    undone: both shapes resolve to the same ranks through `validate_shop_types`,
    so restoring the legacy key would only reintroduce the ambiguity.
    """
    _migrate(apps, adding=False)


class Migration(migrations.Migration):
    dependencies = [("core", "0045_nomirazzeinfo_clip_femminile_and_more")]

    operations = [migrations.RunPython(add_ranks, remove_ranks)]

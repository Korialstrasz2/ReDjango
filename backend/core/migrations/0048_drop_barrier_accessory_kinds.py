from django.db import migrations


# Gli oggetti "barriera fisica" e "barriera magica" sono archiviati su tutti e
# sette gli slot, quindi i due tipi non pescano piu nulla dal catalogo: restavano
# solo come voci morte nei pool dei profili accessorio. Il generatore le saltava
# gia in silenzio, ma tenerle qui faceva sembrare la meccanica ancora viva.
RETIRED_ACCESSORY_KINDS = ("barr_fis_item", "barr_mag_item")


def _strip_retired_kinds(rules):
    if not isinstance(rules, dict):
        return rules, False
    pools = rules.get("variantPools")
    if not isinstance(pools, list):
        return rules, False
    changed = False
    cleaned_pools = []
    for pool in pools:
        if not isinstance(pool, list):
            cleaned_pools.append(pool)
            continue
        cleaned = [kind for kind in pool if kind not in RETIRED_ACCESSORY_KINDS]
        changed = changed or len(cleaned) != len(pool)
        cleaned_pools.append(cleaned)
    if not changed:
        return rules, False
    return {**rules, "variantPools": cleaned_pools}, True


def drop_retired_kinds(apps, schema_editor):
    AccessoryProfile = apps.get_model("core", "AccessoryProfile")
    for profile in AccessoryProfile.objects.all():
        rules, changed = _strip_retired_kinds(profile.rules)
        if not changed:
            continue
        profile.rules = rules
        profile.save(update_fields=["rules", "updated_at"])


def restore_retired_kinds(apps, schema_editor):
    # I pool sono ricostruibili solo dai default correnti, che non contengono
    # piu i tipi ritirati: la rimozione non e reversibile in modo fedele.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0047_drop_market_generation_profiles"),
    ]

    operations = [
        migrations.RunPython(drop_retired_kinds, restore_retired_kinds),
    ]

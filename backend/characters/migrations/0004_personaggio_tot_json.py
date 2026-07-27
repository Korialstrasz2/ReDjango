import backend.characters.models
from django.db import migrations, models


TOT_FIELD_TO_KEY = [
    ("stanchezza_tot", "stanchezza"),
    ("modificatore_generale_tot", "modificatore_generale"),
    ("fortuna_tot", "fortuna"),
    ("forza_tot", "forza"),
    ("resistenza_tot", "resistenza"),
    ("velocita_tot", "velocita"),
    ("agilita_tot", "agilita"),
    ("intelligenza_tot", "intelligenza"),
    ("concentrazione_tot", "concentrazione"),
    ("personalita_tot", "personalita"),
    ("saggezza_tot", "saggezza"),
    ("pf_tot", "pf"),
    ("mana_tot", "mana"),
    ("energia_tot", "energia"),
    ("potere_tot", "potere"),
    ("pa_tot", "pa"),
    ("attacco_tot", "attacco"),
    ("difesa_tot", "difesa"),
    ("rd_fis_tot", "rd_fis"),
    ("res_contundente_tot", "res_contundente"),
    ("res_taglio_tot", "res_taglio"),
    ("res_perforante_tot", "res_perforante"),
    ("res_fuoco_tot", "res_fuoco"),
    ("res_gelo_tot", "res_gelo"),
    ("res_elettro_tot", "res_elettro"),
    ("rd_fuoco_tot", "rd_fuoco"),
    ("rd_gelo_tot", "rd_gelo"),
    ("rd_elettro_tot", "rd_elettro"),
    ("ap_tot", "ap"),
    ("ap_percento_tot", "ap_percento"),
    ("slot_magici_tot", "slot_magici"),
    ("slot_non_magici_tot", "slot_non_magici"),
    ("monete_per_slot_tot", "monete_per_slot"),
    ("tier_tot", "tier"),
    ("sifone_di_mana_tot", "sifone_di_mana"),
    ("en_per_mana_tot", "en_per_mana"),
    ("pa_per_mana_tot", "pa_per_mana"),
    ("ogni_en_x_mana_tot", "ogni_en_x_mana"),
    ("ogni_pa_x_mana_tot", "ogni_pa_x_mana"),
    ("sconto_mana_per_potere_tot", "sconto_mana_per_potere"),
    ("sconto_pa_per_potere_tot", "sconto_pa_per_potere"),
    ("mod_carico_tot", "mod_carico"),
    ("mod_peso_equip_tot", "mod_peso_equip"),
    ("orecchini_max_tot", "orecchini_max"),
    ("anelli_max_tot", "anelli_max"),
    ("sacchi_max_tot", "sacchi_max"),
    ("atk_skill_taglio_tot", "atk_skill_taglio"),
    ("atk_skill_contundente_tot", "atk_skill_contundente"),
    ("atk_skill_perforante_tot", "atk_skill_perforante"),
]


def _zero_if_none(value):
    return 0 if value is None else value


def pack_tot_fields(apps, schema_editor):
    Personaggio = apps.get_model("characters", "Personaggio")
    field_names = [field_name for field_name, _key in TOT_FIELD_TO_KEY]

    for personaggio in Personaggio.objects.all().only("id", "tot", *field_names).iterator():
        tot = dict(personaggio.tot or {})
        changed = False

        for field_name, key in TOT_FIELD_TO_KEY:
            value = _zero_if_none(getattr(personaggio, field_name))
            if tot.get(key) != value:
                tot[key] = value
                changed = True

        if changed:
            personaggio.tot = tot
            personaggio.save(update_fields=["tot"])


def unpack_tot_fields(apps, schema_editor):
    Personaggio = apps.get_model("characters", "Personaggio")
    field_names = [field_name for field_name, _key in TOT_FIELD_TO_KEY]

    for personaggio in Personaggio.objects.all().only("id", "tot", *field_names).iterator():
        tot = personaggio.tot or {}
        update_fields = []

        for field_name, key in TOT_FIELD_TO_KEY:
            value = _zero_if_none(tot.get(key))
            if getattr(personaggio, field_name) != value:
                setattr(personaggio, field_name, value)
                update_fields.append(field_name)

        if update_fields:
            personaggio.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("characters", "0003_merge_mana_conversion_totals"),
    ]

    operations = [
        migrations.AddField(
            model_name="personaggio",
            name="tot",
            field=models.JSONField(
                blank=True,
                default=backend.characters.models.default_personaggio_tot,
            ),
        ),
        migrations.RunPython(pack_tot_fields, unpack_tot_fields),
        *[
            migrations.RemoveField(
                model_name="personaggio",
                name=field_name,
            )
            for field_name, _key in TOT_FIELD_TO_KEY
        ],
    ]

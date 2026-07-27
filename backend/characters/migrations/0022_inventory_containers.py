import re

import django.db.models.deletion
from django.db import migrations, models


def normalize_stock_key(value):
    key = str(value or "").strip().lower().replace(" ", "_")
    direct = re.fullmatch(r"([rvb])([1-4])", key)
    if direct:
        return direct.group(0)
    verbose = re.fullmatch(
        r"(?:ingredienti?_)?(rossi?|verdi?|blu)_?(?:livello_?)?([1-4])",
        key,
    )
    if not verbose:
        return None
    raw_color = verbose.group(1)
    short = "r" if raw_color.startswith("ross") else "v" if raw_color.startswith("verd") else "b"
    return f"{short}{verbose.group(2)}"


def create_existing_containers(apps, schema_editor):
    Personaggio = apps.get_model("characters", "Personaggio")
    DatiCampagna = apps.get_model("core", "DatiCampagna")
    Contenitore = apps.get_model("characters", "ContenitoreInventario")
    Voce = apps.get_model("characters", "VoceContenitoreInventario")

    for character in Personaggio.objects.select_related("borsa_reagenti").iterator():
        container = Contenitore.objects.create(
            nome=f"Alchimia&Contenitori · {character.nome}"[:160],
            scope="personal",
            personaggio=character,
            capacita=15,
            senza_peso=True,
        )
        quantities = {}
        ingredients = character.borsa_reagenti.ingredienti if character.borsa_reagenti_id else {}
        if isinstance(ingredients, dict):
            for raw_key, raw_value in ingredients.items():
                key = normalize_stock_key(raw_key)
                if not key:
                    continue
                try:
                    quantity = max(0, int(raw_value))
                except (TypeError, ValueError):
                    quantity = 0
                quantities[key] = quantities.get(key, 0) + quantity
        for slot, (key, quantity) in enumerate(
            sorted((entry for entry in quantities.items() if entry[1] > 0)),
            start=1,
        ):
            Voce.objects.create(
                contenitore=container,
                slot=slot,
                reagent_stock_key=key,
                quantita=quantity,
            )

    for campaign in DatiCampagna.objects.all().iterator():
        Contenitore.objects.create(
            nome=f"Risorse gruppo · {campaign.nome}"[:160],
            scope="campaign",
            campagna=campaign,
            capacita=30,
            senza_peso=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("characters", "0021_personaggio_campagna_personaggio_portrait_and_more"),
        ("core", "0025_elder_quick_stat_fixed_adjustments"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContenitoreInventario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("nome", models.CharField(max_length=160)),
                ("scope", models.CharField(choices=[("personal", "Personale"), ("campaign", "Campagna")], max_length=16)),
                ("capacita", models.PositiveSmallIntegerField(default=15)),
                ("senza_peso", models.BooleanField(default=True)),
                ("campagna", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="contenitori_inventario", to="core.daticampagna")),
                ("personaggio", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="contenitori_inventario", to="characters.personaggio")),
            ],
            options={"ordering": ["scope", "nome"]},
        ),
        migrations.CreateModel(
            name="VoceContenitoreInventario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("slot", models.PositiveSmallIntegerField()),
                ("reagent_stock_key", models.CharField(blank=True, max_length=8)),
                ("quantita", models.PositiveIntegerField(default=1)),
                ("contenitore", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="voci", to="characters.contenitoreinventario")),
                ("oggetto", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="voci_contenitore", to="core.oggetto")),
            ],
            options={"ordering": ["slot"]},
        ),
        migrations.AddConstraint(
            model_name="contenitoreinventario",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("campagna__isnull", True), ("personaggio__isnull", False), ("scope", "personal")), models.Q(("campagna__isnull", False), ("personaggio__isnull", True), ("scope", "campaign")), _connector="OR"), name="inventory_container_owner_matches_scope"),
        ),
        migrations.AddConstraint(
            model_name="contenitoreinventario",
            constraint=models.UniqueConstraint(condition=models.Q(("scope", "personal")), fields=("personaggio",), name="one_personal_inventory_container"),
        ),
        migrations.AddConstraint(
            model_name="contenitoreinventario",
            constraint=models.UniqueConstraint(condition=models.Q(("scope", "campaign")), fields=("campagna",), name="one_campaign_inventory_container"),
        ),
        migrations.AddConstraint(
            model_name="vocecontenitoreinventario",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("oggetto__isnull", False), ("reagent_stock_key", "")), models.Q(("oggetto__isnull", True), models.Q(("reagent_stock_key", ""), _negated=True)), _connector="OR"), name="inventory_entry_has_one_content"),
        ),
        migrations.AddConstraint(
            model_name="vocecontenitoreinventario",
            constraint=models.CheckConstraint(condition=models.Q(("quantita__gte", 1)), name="inventory_entry_quantity_positive"),
        ),
        migrations.AddConstraint(
            model_name="vocecontenitoreinventario",
            constraint=models.UniqueConstraint(fields=("contenitore", "slot"), name="unique_inventory_entry_slot"),
        ),
        migrations.AddConstraint(
            model_name="vocecontenitoreinventario",
            constraint=models.UniqueConstraint(condition=models.Q(("oggetto__isnull", False)), fields=("contenitore", "oggetto"), name="unique_item_stack_per_inventory_container"),
        ),
        migrations.AddConstraint(
            model_name="vocecontenitoreinventario",
            constraint=models.UniqueConstraint(condition=models.Q(("reagent_stock_key", ""), _negated=True), fields=("contenitore", "reagent_stock_key"), name="unique_reagent_stack_per_inventory_container"),
        ),
        migrations.RunPython(create_existing_containers, migrations.RunPython.noop),
    ]

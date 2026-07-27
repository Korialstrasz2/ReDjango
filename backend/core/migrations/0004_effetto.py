from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_merge_mana_modifier_keys"),
    ]

    operations = [
        migrations.CreateModel(
            name="Effetto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("tipo", models.CharField(blank=True, max_length=80)),
                ("nome", models.CharField(max_length=180, unique=True)),
                ("descrizione", models.TextField(blank=True)),
                ("effect_payload", models.JSONField(blank=True, default=dict)),
                ("durata_turni", models.IntegerField(blank=True, null=True)),
                ("stacking_rule", models.CharField(blank=True, max_length=80)),
                ("icona", models.CharField(blank=True, max_length=160)),
                ("origine_tipo", models.CharField(blank=True, max_length=80)),
                ("origine_nome", models.CharField(blank=True, max_length=180)),
                ("notes", models.TextField(blank=True)),
            ],
            options={
                "ordering": ["tipo", "nome"],
                "indexes": [
                    models.Index(fields=["tipo", "nome"], name="core_effett_tipo_99a74b_idx"),
                    models.Index(fields=["origine_tipo", "origine_nome"], name="core_effett_origine_d19c7a_idx"),
                ],
            },
        ),
    ]

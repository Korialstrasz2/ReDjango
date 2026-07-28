import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("characters", "0023_remove_reagent_bag"),
        ("core", "0029_remove_retired_settings"),
        ("dice_tools", "0002_dicetexture"),
    ]

    operations = [
        migrations.CreateModel(
            name="DiceRollRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("player_name", models.CharField(max_length=120, verbose_name="nome giocatore")),
                ("character_name", models.CharField(blank=True, max_length=160, verbose_name="nome personaggio")),
                (
                    "source",
                    models.CharField(
                        choices=[("quick", "Dadi"), ("competence", "Competenza")],
                        max_length=24,
                        verbose_name="origine",
                    ),
                ),
                ("label", models.CharField(blank=True, max_length=180, verbose_name="contesto")),
                ("notation", models.CharField(max_length=80, verbose_name="notazione")),
                ("rolls", models.JSONField(default=list, verbose_name="risultati dei dadi")),
                ("modifier", models.IntegerField(default=0, verbose_name="modificatore")),
                ("total", models.IntegerField(verbose_name="totale")),
                ("dice_set_name", models.CharField(blank=True, max_length=120, verbose_name="set di dadi")),
                (
                    "giocatore",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dice_roll_records",
                        to="core.giocatore",
                        verbose_name="giocatore",
                    ),
                ),
                (
                    "personaggio",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dice_roll_records",
                        to="characters.personaggio",
                        verbose_name="personaggio",
                    ),
                ),
            ],
            options={
                "verbose_name": "tiro di dado registrato",
                "verbose_name_plural": "tiri di dado registrati",
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["created_at"], name="dice_roll_created_idx"),
                    models.Index(fields=["giocatore", "created_at"], name="dice_roll_player_idx"),
                    models.Index(fields=["personaggio", "created_at"], name="dice_roll_character_idx"),
                ],
            },
        ),
    ]

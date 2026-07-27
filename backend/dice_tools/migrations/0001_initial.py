# Generated manually for the ReDjango dice-set catalogue.
from django.db import migrations, models

import backend.core.models
import backend.dice_tools.models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="DiceSet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("slug", models.SlugField(max_length=80, unique=True, verbose_name="identificatore")),
                ("name", models.CharField(max_length=120, verbose_name="nome")),
                ("description", models.TextField(blank=True, verbose_name="descrizione")),
                ("dice", models.JSONField(default=list, validators=[backend.dice_tools.models.validate_dice_sides], verbose_name="dadi disponibili")),
                ("surface_color", models.CharField(default="#7f2434", max_length=7, validators=[backend.core.models.HEX_COLOR_VALIDATOR], verbose_name="colore dado")),
                ("accent_color", models.CharField(default="#d0a95b", max_length=7, validators=[backend.core.models.HEX_COLOR_VALIDATOR], verbose_name="colore bordo")),
                ("text_color", models.CharField(default="#fff4d6", max_length=7, validators=[backend.core.models.HEX_COLOR_VALIDATOR], verbose_name="colore simboli")),
                ("is_active", models.BooleanField(default=True, verbose_name="attivo")),
                ("is_default", models.BooleanField(default=False, verbose_name="predefinito")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="ordine")),
            ],
            options={"verbose_name": "set di dadi", "verbose_name_plural": "set di dadi", "ordering": ["order", "name"]},
        ),
        migrations.AddIndex(model_name="diceset", index=models.Index(fields=["is_active", "order", "name"], name="dice_set_active_order_idx")),
    ]

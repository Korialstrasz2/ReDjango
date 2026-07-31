"""Gli sfondi dei temi passano da dieci colonne a una riga per superficie.

Con una superficie per pagina, modale e strumento rapido le colonne sarebbero
diventate decine: ThemeBackground le sostituisce con righe (tema, superficie,
immagine) e l'elenco delle superfici vive in core/theme_surfaces.py.

La colonna «characters_background» non viene trasferita: la rotta /characters
rimanda alla Sala principale, quindi quello sfondo non era più raggiungibile.
Le immagini restano nell'Archivio e possono essere riassegnate dall'editor.
"""

import django.db.models.deletion
from django.db import migrations, models

from backend.core.theme_surfaces import LEGACY_BACKGROUND_COLUMNS


def copy_backgrounds_to_rows(apps, schema_editor):
    Theme = apps.get_model("core", "Theme")
    ThemeBackground = apps.get_model("core", "ThemeBackground")
    rows = []
    for theme in Theme.objects.all():
        for column, surface_key in LEGACY_BACKGROUND_COLUMNS.items():
            image_id = getattr(theme, f"{column}_id", None)
            if image_id:
                rows.append(ThemeBackground(theme=theme, surface_key=surface_key, image_id=image_id))
    ThemeBackground.objects.bulk_create(rows, ignore_conflicts=True)


def restore_backgrounds_to_columns(apps, schema_editor):
    Theme = apps.get_model("core", "Theme")
    ThemeBackground = apps.get_model("core", "ThemeBackground")
    surface_to_column = {surface: column for column, surface in LEGACY_BACKGROUND_COLUMNS.items()}
    for row in ThemeBackground.objects.select_related("theme"):
        column = surface_to_column.get(row.surface_key)
        if column:
            setattr(row.theme, f"{column}_id", row.image_id)
            row.theme.save(update_fields=[f"{column}_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0043_oggetto_regole_speciali"),
        ("media_library", "0006_audiofile_tags"),
    ]

    operations = [
        migrations.CreateModel(
            name="ThemeBackground",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "surface_key",
                    models.CharField(max_length=64, verbose_name="superficie"),
                ),
                (
                    "image",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="theme_backgrounds",
                        to="media_library.uploadedimage",
                        verbose_name="immagine",
                    ),
                ),
                (
                    "theme",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="backgrounds",
                        to="core.theme",
                        verbose_name="tema",
                    ),
                ),
            ],
            options={
                "verbose_name": "sfondo del tema",
                "verbose_name_plural": "sfondi dei temi",
                "ordering": ["theme__order", "surface_key"],
                "indexes": [
                    models.Index(
                        fields=["theme", "surface_key"],
                        name="core_themebg_theme_surf_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("theme", "surface_key"),
                        name="one_background_per_theme_surface",
                    )
                ],
            },
        ),
        migrations.RunPython(copy_backgrounds_to_rows, restore_backgrounds_to_columns),
        migrations.RemoveField(
            model_name="theme",
            name="characters_background",
        ),
        migrations.RemoveField(
            model_name="theme",
            name="dashboard_background",
        ),
        migrations.RemoveField(
            model_name="theme",
            name="dice_background",
        ),
        migrations.RemoveField(
            model_name="theme",
            name="guide_background",
        ),
        migrations.RemoveField(
            model_name="theme",
            name="journal_background",
        ),
        migrations.RemoveField(
            model_name="theme",
            name="lore_background",
        ),
        migrations.RemoveField(
            model_name="theme",
            name="market_background",
        ),
        migrations.RemoveField(
            model_name="theme",
            name="media_background",
        ),
        migrations.RemoveField(
            model_name="theme",
            name="personaggio_background",
        ),
        migrations.RemoveField(
            model_name="theme",
            name="settings_background",
        ),
    ]

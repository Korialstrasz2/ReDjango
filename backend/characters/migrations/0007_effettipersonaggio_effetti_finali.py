import django.db.models.deletion
from django.db import migrations, models


def _effect_slot_fields():
    return [
        (
            f"effetto_{index}",
            models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="core.effetto",
            ),
        )
        for index in range(1, 51)
    ]


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_effetto"),
        ("characters", "0006_remove_personaggio_attacco_npc_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="EffettiPersonaggio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("nome", models.CharField(max_length=160)),
                *_effect_slot_fields(),
            ],
            options={
                "ordering": ["nome"],
            },
        ),
        migrations.RenameField(
            model_name="personaggio",
            old_name="act",
            new_name="effetti_finali",
        ),
        migrations.AddField(
            model_name="personaggio",
            name="effetti",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="personaggi",
                to="characters.effettipersonaggio",
            ),
        ),
    ]

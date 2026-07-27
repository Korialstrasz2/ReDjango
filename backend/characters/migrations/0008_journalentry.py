from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def backfill_journal(apps, schema_editor):
    Note = apps.get_model("characters", "Note")
    JournalEntry = apps.get_model("characters", "JournalEntry")
    mapping = (
        ("background", "background", "Background"),
        ("appunti", "general", "Appunti"),
        ("crafting", "crafting", "Crafting"),
        ("note_combat", "combat", "Combattimento"),
        ("note_skill", "skills", "Competenze"),
    )
    for note in Note.objects.all().iterator():
        for field, category, label in mapping:
            raw = getattr(note, field, None)
            values = []
            if isinstance(raw, str) and raw.strip():
                values.append((label, raw.strip()))
            elif isinstance(raw, dict):
                for key, value in raw.items():
                    if key == "seed" or not isinstance(value, str) or not value.strip():
                        continue
                    values.append((str(key).replace("_", " ").title(), value.strip()))
            for index, (title, body) in enumerate(values):
                JournalEntry.objects.get_or_create(
                    note=note,
                    category=category,
                    title=title[:160],
                    defaults={"body": body, "sort_order": index, "metadata": {"migrated_from": field}},
                )


class Migration(migrations.Migration):
    dependencies = [("characters", "0007_effettipersonaggio_effetti_finali")]
    operations = [
        migrations.CreateModel(
            name="JournalEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("title", models.CharField(max_length=160, verbose_name="titolo")),
                ("body", models.TextField(blank=True, verbose_name="testo")),
                ("category", models.CharField(choices=[("general", "Appunti"), ("inventory", "Zaino"), ("crafting", "Crafting"), ("travel", "Viaggio"), ("quests", "Missioni"), ("background", "Background"), ("combat", "Combattimento"), ("skills", "Competenze")], default="general", max_length=40, verbose_name="sezione")),
                ("entry_date", models.DateField(default=django.utils.timezone.localdate, verbose_name="data")),
                ("tags", models.JSONField(blank=True, default=list, verbose_name="etichette")),
                ("is_pinned", models.BooleanField(default=False, verbose_name="in evidenza")),
                ("is_completed", models.BooleanField(default=False, verbose_name="completata")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="ordine")),
                ("note", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="journal_entries", to="characters.note")),
            ],
            options={"verbose_name": "voce del diario", "verbose_name_plural": "voci del diario", "ordering": ["-is_pinned", "sort_order", "-entry_date", "-updated_at", "-id"]},
        ),
        migrations.AddIndex(model_name="journalentry", index=models.Index(fields=["note", "category", "archived_at"], name="journal_note_category_idx")),
        migrations.AddIndex(model_name="journalentry", index=models.Index(fields=["note", "entry_date"], name="journal_note_date_idx")),
        migrations.RunPython(backfill_journal, migrations.RunPython.noop),
    ]

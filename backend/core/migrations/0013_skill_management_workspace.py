from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


DEFAULT_GROUPS = [
    ("Generali", 0),
    ("Religioni", 10),
    ("Scuole di Magia", 20),
    ("Classi", 30),
    ("Perk", 40),
]


def create_groups(apps, schema_editor):
    Family = apps.get_model("core", "FamigliaSkill")
    Group = apps.get_model("core", "GruppoFamiglieSkill")
    ordered_names = list(DEFAULT_GROUPS)
    known = {name for name, _order in ordered_names}
    for name in Family.objects.filter(archived_at__isnull=True).values_list("gruppo", flat=True).distinct():
        if name and name not in known:
            ordered_names.append((name, 100 + len(ordered_names) * 10))
            known.add(name)
    used_slugs = set()
    groups = {}
    for name, order in ordered_names:
        base = slugify(name) or "gruppo"
        candidate = base
        suffix = 2
        while candidate in used_slugs:
            candidate = f"{base}-{suffix}"
            suffix += 1
        used_slugs.add(candidate)
        groups[name] = Group.objects.create(nome=name, slug=candidate, ordine=order)
    for family in Family.objects.all():
        if family.gruppo not in groups:
            base = slugify(family.gruppo) or "gruppo"
            candidate = base
            suffix = 2
            while candidate in used_slugs:
                candidate = f"{base}-{suffix}"
                suffix += 1
            used_slugs.add(candidate)
            groups[family.gruppo] = Group.objects.create(
                nome=family.gruppo,
                slug=candidate,
                ordine=100 + len(groups) * 10,
                archived_at=family.archived_at,
            )
        family.gruppo_riferimento_id = groups[family.gruppo].id
        family.save(update_fields=["gruppo_riferimento"])


def restore_group_names(apps, schema_editor):
    Family = apps.get_model("core", "FamigliaSkill")
    for family in Family.objects.select_related("gruppo_riferimento"):
        family.gruppo = family.gruppo_riferimento.nome
        family.save(update_fields=["gruppo"])


class Migration(migrations.Migration):
    dependencies = [("core", "0012_seed_skill_pricing_config")]

    operations = [
        migrations.CreateModel(
            name="GruppoFamiglieSkill",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("nome", models.CharField(max_length=80, unique=True)),
                ("slug", models.SlugField(max_length=100, unique=True)),
                ("ordine", models.IntegerField(default=0)),
                ("note", models.TextField(blank=True)),
            ],
            options={"ordering": ["ordine", "nome"]},
        ),
        migrations.CreateModel(
            name="SkillMigrationReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("source_project", models.CharField(max_length=120)),
                ("source_id", models.PositiveIntegerField()),
                ("nome", models.CharField(max_length=180)),
                ("severity", models.CharField(choices=[("blocked", "Bloccante"), ("warning", "Avviso")], default="blocked", max_length=24)),
                ("decision", models.CharField(default="needs_review", max_length=40)),
                ("status", models.CharField(choices=[("open", "Da rivedere"), ("imported", "Importata"), ("ignored", "Ignorata")], default="open", max_length=24)),
                ("blockers", models.JSONField(blank=True, default=list)),
                ("warnings", models.JSONField(blank=True, default=list)),
                ("suggested_values", models.JSONField(blank=True, default=dict)),
                ("working_values", models.JSONField(blank=True, default=dict)),
                ("source_snapshot", models.JSONField(blank=True, default=dict)),
                ("edited", models.BooleanField(default=False)),
                ("resolution_notes", models.TextField(blank=True)),
                ("resolved_skill", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="migration_reviews", to="core.skill")),
            ],
            options={
                "ordering": ["status", "severity", "nome", "source_id"],
                "indexes": [
                    models.Index(fields=["status", "severity"], name="core_skillm_status_6f92d9_idx"),
                    models.Index(fields=["source_project", "source_id"], name="core_skillm_source__6f8556_idx"),
                ],
                "constraints": [models.UniqueConstraint(fields=("source_project", "source_id"), name="unique_skill_migration_review_source")],
            },
        ),
        migrations.AddField(
            model_name="famigliaskill",
            name="gruppo_riferimento",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="famiglie", to="core.gruppofamiglieskill"),
        ),
        migrations.RunPython(create_groups, restore_group_names),
        migrations.RemoveField(model_name="famigliaskill", name="gruppo"),
        migrations.RenameField(model_name="famigliaskill", old_name="gruppo_riferimento", new_name="gruppo"),
        migrations.AlterField(
            model_name="famigliaskill",
            name="gruppo",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="famiglie", to="core.gruppofamiglieskill"),
        ),
    ]

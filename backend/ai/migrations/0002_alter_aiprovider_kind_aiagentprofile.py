from django.db import migrations, models
import django.db.models.deletion


def upgrade_seeded_ai(apps, schema_editor):
    Provider = apps.get_model("ai", "AIProvider")
    Agent = apps.get_model("ai", "AIAgentProfile")
    openai = Provider.objects.filter(slug="openai").first()
    if openai:
        options = dict(openai.options or {})
        options.update(
            {
                "description": "OpenAI Responses API, adatta a ragionamento, strumenti e flussi agentici.",
                "suggestedModels": ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
            }
        )
        if openai.kind == "openai_compatible" and openai.model == "gpt-5.2":
            openai.kind = "openai_responses"
            openai.model = "gpt-5.6-sol"
        openai.options = options
        openai.save()
    image = Provider.objects.filter(slug="openai-immagini", model="gpt-image-1").first()
    if image:
        image.model = "gpt-image-2"
        options = dict(image.options or {})
        options["suggestedModels"] = ["gpt-image-2", "gpt-image-1"]
        options["description"] = "Generazione immagini OpenAI. La modifica da immagine resta in lavorazione."
        image.options = options
        image.save()
    Agent.objects.get_or_create(
        slug="assistente-campagna",
        defaults={
            "name": "Assistente campagna",
            "description": "Ricerca e spiega dati della campagna usando soltanto strumenti di lettura.",
            "instructions": "Aiuta giocatori e Master a capire personaggi, oggetti, regole e stato della campagna. Indica in modo naturale quali dati hai consultato.",
            "minimum_role": "user",
            "provider": None,
            "allowed_tools": [
                "cerca_oggetti", "scheda_personaggio", "cerca_abilita", "competenze_personaggio",
                "lore_campagna", "mercato", "guide_regole", "variabili_gioco",
            ],
            "max_iterations": 6,
            "is_enabled": True,
            "is_default": True,
            "metadata": {"seed_kind": "ai_agent"},
        },
    )


class Migration(migrations.Migration):
    dependencies = [("ai", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="aiprovider",
            name="kind",
            field=models.CharField(
                choices=[
                    ("anthropic", "Anthropic Messages"),
                    ("openai_responses", "OpenAI Responses"),
                    ("openai_compatible", "Compatibile OpenAI"),
                    ("openai_image", "Immagini OpenAI"),
                    ("stable_diffusion", "Stable Diffusion locale"),
                ],
                default="anthropic",
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="AIAgentProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                ("instructions", models.TextField(blank=True)),
                (
                    "minimum_role",
                    models.CharField(
                        choices=[("user", "Giocatore"), ("master", "Master"), ("admin", "Amministratore")],
                        default="user",
                        max_length=20,
                    ),
                ),
                ("allowed_tools", models.JSONField(blank=True, default=list)),
                ("max_iterations", models.PositiveSmallIntegerField(default=6)),
                ("is_enabled", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "provider",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"purpose": "chat"},
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="agent_profiles",
                        to="ai.aiprovider",
                    ),
                ),
            ],
            options={
                "verbose_name": "profilo agente AI",
                "verbose_name_plural": "profili agente AI",
                "ordering": ["order", "name"],
                "indexes": [models.Index(fields=["is_enabled", "minimum_role", "order"], name="ai_aiagentp_is_enab_9967da_idx")],
            },
        ),
        migrations.RunPython(upgrade_seeded_ai, migrations.RunPython.noop),
    ]

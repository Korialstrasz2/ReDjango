import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def normalize_defaults(apps, schema_editor):
    Provider = apps.get_model("ai", "AIProvider")
    Agent = apps.get_model("ai", "AIAgentProfile")
    Provider.objects.filter(is_default=True, is_enabled=False).update(is_default=False)
    Agent.objects.filter(is_default=True, is_enabled=False).update(is_default=False)
    for purpose in ("chat", "image"):
        defaults = list(
            Provider.objects.filter(purpose=purpose, is_default=True, archived_at__isnull=True)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )
        if len(defaults) > 1:
            Provider.objects.filter(id__in=defaults[1:]).update(is_default=False)
    agent_defaults = list(
        Agent.objects.filter(is_default=True, archived_at__isnull=True)
        .order_by("order", "id")
        .values_list("id", flat=True)
    )
    if len(agent_defaults) > 1:
        Agent.objects.filter(id__in=agent_defaults[1:]).update(is_default=False)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ai", "0007_aiagentprofile_routing_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiprovider",
            name="model_catalog",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="aiprovider",
            name="model_catalog_refreshed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(normalize_defaults, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="aiprovider",
            constraint=models.UniqueConstraint(
                condition=Q(is_default=True, archived_at__isnull=True),
                fields=("purpose", "is_default"),
                name="ai_one_default_provider_per_purpose",
            ),
        ),
        migrations.AddConstraint(
            model_name="aiagentprofile",
            constraint=models.UniqueConstraint(
                condition=Q(is_default=True, archived_at__isnull=True),
                fields=("is_default",),
                name="ai_one_default_agent",
            ),
        ),
        migrations.CreateModel(
            name="AIConversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("title", models.CharField(max_length=120)),
                ("history", models.JSONField(blank=True, default=list)),
                ("transcript", models.JSONField(blank=True, default=list)),
                ("agent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="conversations", to="ai.aiagentprofile")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ai_conversations", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "conversazione AI",
                "verbose_name_plural": "conversazioni AI",
                "ordering": ["-updated_at", "-id"],
                "indexes": [models.Index(fields=["user", "-updated_at"], name="ai_aiconver_user_id_fe4cc7_idx")],
            },
        ),
        migrations.CreateModel(
            name="AIExecutionRun",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("chat", "Chat"), ("image", "Immagine")], max_length=12)),
                ("status", models.CharField(choices=[("queued", "In coda"), ("running", "In esecuzione"), ("completed", "Completata"), ("failed", "Non riuscita"), ("cancelled", "Annullata")], default="queued", max_length=16)),
                ("progress", models.CharField(blank=True, max_length=180)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("error", models.JSONField(blank=True, default=dict)),
                ("cancel_requested", models.BooleanField(default=False)),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("tool_calls", models.PositiveSmallIntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("agent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="runs", to="ai.aiagentprofile")),
                ("conversation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="runs", to="ai.aiconversation")),
                ("provider", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="runs", to="ai.aiprovider")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ai_execution_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "esecuzione AI",
                "verbose_name_plural": "esecuzioni AI",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["user", "status", "-created_at"], name="ai_aiexecut_user_id_4aa6d2_idx"),
                    models.Index(fields=["status", "created_at"], name="ai_aiexecut_status_c77994_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=Q(status__in=["queued", "running"], archived_at__isnull=True),
                        fields=("user",),
                        name="ai_one_active_run_per_user",
                    ),
                ],
            },
        ),
    ]

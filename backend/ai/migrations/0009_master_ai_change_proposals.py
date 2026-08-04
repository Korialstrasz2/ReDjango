import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ai", "0008_provider_catalog_conversations_and_runs"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiagentprofile",
            name="mode",
            field=models.CharField(
                choices=[
                    ("read_only", "Sola lettura"),
                    ("proposer", "Proposte di modifica"),
                ],
                default="read_only",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="AIChangeSet",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("draft", "Bozza"), ("ready", "Pronta"), ("applied", "Applicata"), ("discarded", "Scartata"), ("expired", "Scaduta")], default="draft", max_length=16)),
                ("title", models.CharField(blank=True, max_length=160)),
                ("request_text", models.TextField(blank=True)),
                ("context", models.JSONField(blank=True, default=dict)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("validation_summary", models.JSONField(blank=True, default=dict)),
                ("validation_token", models.TextField(blank=True)),
                ("validated_at", models.DateTimeField(blank=True, null=True)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("discarded_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("agent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="change_sets", to="ai.aiagentprofile")),
                ("applied_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="applied_ai_change_sets", to=settings.AUTH_USER_MODEL)),
                ("conversation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="change_sets", to="ai.aiconversation")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ai_change_sets", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "proposta AI",
                "verbose_name_plural": "proposte AI",
                "ordering": ["-updated_at"],
                "indexes": [
                    models.Index(fields=["user", "status", "-updated_at"], name="ai_changeset_user_status_idx"),
                    models.Index(fields=["conversation", "status"], name="ai_changeset_conversation_idx"),
                    models.Index(fields=["status", "expires_at"], name="ai_changeset_expiry_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AIChangeOperation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("entity_type", models.CharField(max_length=32)),
                ("action", models.CharField(choices=[("create", "Crea"), ("update", "Modifica"), ("archive", "Archivia")], max_length=16)),
                ("target_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("source_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("display_label", models.CharField(blank=True, max_length=200)),
                ("selected", models.BooleanField(default=True)),
                ("status", models.CharField(choices=[("proposed", "Proposta"), ("valid", "Valida"), ("invalid", "Non valida"), ("applied", "Applicata"), ("skipped", "Saltata")], default="proposed", max_length=16)),
                ("original_snapshot", models.JSONField(blank=True, default=dict)),
                ("proposed_values", models.JSONField(blank=True, default=dict)),
                ("edited_values", models.JSONField(blank=True, default=dict)),
                ("field_schema", models.JSONField(blank=True, default=list)),
                ("base_updated_at", models.DateTimeField(blank=True, null=True)),
                ("base_digest", models.CharField(blank=True, max_length=64)),
                ("validation_errors", models.JSONField(blank=True, default=list)),
                ("validation_warnings", models.JSONField(blank=True, default=list)),
                ("application_result", models.JSONField(blank=True, default=dict)),
                ("change_set", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="operations", to="ai.aichangeset")),
            ],
            options={
                "verbose_name": "operazione proposta AI",
                "verbose_name_plural": "operazioni proposte AI",
                "ordering": ["position", "id"],
                "constraints": [
                    models.UniqueConstraint(fields=("change_set", "position"), name="ai_change_operation_unique_position"),
                    models.CheckConstraint(condition=Q(action__in=["create", "update", "archive"]), name="ai_change_operation_valid_action"),
                    models.CheckConstraint(condition=(Q(action="create", target_id__isnull=True) | Q(action__in=["update", "archive"], target_id__isnull=False)), name="ai_change_operation_target_shape"),
                ],
            },
        ),
    ]

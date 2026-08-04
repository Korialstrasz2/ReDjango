import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from backend.core.api import ApiError
from backend.core.item_services import create_item
from backend.core.models import Giocatore, Oggetto

from .changes.cleanup import cleanup_abandoned_change_sets
from .changes.context import validate_change_context
from .changes.services import MAX_OPERATIONS, add_change_operation, create_change_set
from .models import AIChangeOperation, AIChangeSet


def envelope(action: str, payload: dict) -> str:
    return json.dumps(
        {
            "action": action,
            "requestId": "master-ai-hardening",
            "context": {"screen": "master-ai"},
            "payload": payload,
            "meta": {"clientVersion": "test"},
        }
    )


class MasterAIContextHardeningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.master_user = user_model.objects.create_user(username="context_master")
        cls.master = Giocatore.objects.create(user=cls.master_user, nome="context_master", role=Giocatore.ROLE_MASTER)
        cls.admin_user = user_model.objects.create_user(username="context_admin")
        cls.admin = Giocatore.objects.create(user=cls.admin_user, nome="context_admin", role=Giocatore.ROLE_ADMIN)
        cls.item = create_item(cls.master_user, cls.master, {"nome": "Contesto sicuro"})

    def test_item_target_context_is_sanitized_and_access_checked(self):
        context = validate_change_context(
            self.master_user,
            self.master,
            {
                "entityType": " ITEM ",
                "targetId": str(self.item.id),
                "sourceSurface": "item-management",
            },
        )
        self.assertEqual(
            context,
            {"entityType": "item", "targetId": self.item.id, "sourceSurface": "item-management"},
        )

    def test_unknown_context_fields_fail_closed(self):
        with self.assertRaises(ApiError) as captured:
            validate_change_context(
                self.master_user,
                self.master,
                {"entityType": "item", "targetId": self.item.id, "modelName": "backend.core.Oggetto"},
            )
        self.assertEqual(captured.exception.code, "ai.change_context_field_unknown")

    def test_target_and_source_cannot_be_combined(self):
        with self.assertRaises(ApiError) as captured:
            validate_change_context(
                self.master_user,
                self.master,
                {"entityType": "item", "targetId": self.item.id, "sourceId": self.item.id},
            )
        self.assertEqual(captured.exception.code, "ai.change_context_target_source_conflict")

    def test_master_cannot_use_theme_context_hint(self):
        with self.assertRaises(ApiError) as captured:
            validate_change_context(
                self.master_user,
                self.master,
                {"entityType": "theme", "sourceSurface": "theme-management"},
            )
        self.assertEqual(captured.exception.status, 403)

    def test_context_target_must_exist(self):
        with self.assertRaises(ApiError) as captured:
            validate_change_context(
                self.admin_user,
                self.admin,
                {"entityType": "item", "targetId": 999999, "sourceSurface": "item-management"},
            )
        self.assertEqual(captured.exception.status, 404)

    def test_raw_api_context_injection_is_rejected(self):
        self.client.force_login(self.master_user)
        response = self.client.post(
            "/api/ai/change-sets/",
            data=envelope(
                "ai.changeSet.create",
                {
                    "title": "Injected context",
                    "context": {
                        "entityType": "item",
                        "targetId": self.item.id,
                        "modelName": "backend.core.Oggetto",
                    },
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["code"], "ai.change_context_field_unknown")
        self.assertFalse(AIChangeSet.objects.filter(title="Injected context").exists())

    def test_operation_limit_fails_without_domain_mutation(self):
        change_set = create_change_set(self.master_user, self.master, title="Operation cap")
        for index in range(MAX_OPERATIONS):
            add_change_operation(
                self.master_user,
                self.master,
                change_set.id,
                entity_type="item",
                action="create",
                values={"nome": f"Proposta limite {index}"},
            )
        with self.assertRaises(ApiError) as captured:
            add_change_operation(
                self.master_user,
                self.master,
                change_set.id,
                entity_type="item",
                action="create",
                values={"nome": "Oltre limite"},
            )
        self.assertEqual(captured.exception.code, "ai.change_operation_limit")
        self.assertEqual(change_set.operations.count(), MAX_OPERATIONS)
        self.assertFalse(Oggetto.objects.filter(nome__startswith="Proposta limite").exists())


class MasterAICleanupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(username="cleanup_master")
        cls.giocatore = Giocatore.objects.create(user=cls.user, nome="cleanup_master", role=Giocatore.ROLE_MASTER)

    def age(self, change_set: AIChangeSet, days: int) -> None:
        AIChangeSet.objects.filter(pk=change_set.pk).update(updated_at=timezone.now() - timedelta(days=days))

    def test_cleanup_deletes_only_old_empty_drafts_and_expires_reviewable_sets(self):
        empty = create_change_set(self.user, self.giocatore, title="empty")
        populated = create_change_set(self.user, self.giocatore, title="populated")
        AIChangeOperation.objects.create(
            change_set=populated,
            position=0,
            entity_type="item",
            action=AIChangeOperation.ACTION_CREATE,
            proposed_values={"nome": "Audit"},
        )
        retained = create_change_set(self.user, self.giocatore, title="recent")
        applied = create_change_set(self.user, self.giocatore, title="applied")
        applied.status = AIChangeSet.STATUS_APPLIED
        applied.save(update_fields=["status", "updated_at"])
        self.age(empty, 3)
        self.age(populated, 20)
        self.age(retained, 1)
        self.age(applied, 30)

        result = cleanup_abandoned_change_sets(review_days=14, empty_days=2)

        self.assertEqual(result, {"deletedEmptyDrafts": 1, "expiredProposals": 1})
        self.assertFalse(AIChangeSet.objects.filter(pk=empty.pk).exists())
        populated.refresh_from_db()
        self.assertEqual(populated.status, AIChangeSet.STATUS_EXPIRED)
        self.assertEqual(populated.validation_token, "")
        self.assertTrue(AIChangeSet.objects.filter(pk=retained.pk).exists())
        applied.refresh_from_db()
        self.assertEqual(applied.status, AIChangeSet.STATUS_APPLIED)

    def test_cleanup_dry_run_writes_nothing(self):
        empty = create_change_set(self.user, self.giocatore, title="empty dry")
        self.age(empty, 5)
        result = cleanup_abandoned_change_sets(review_days=14, empty_days=2, dry_run=True)
        self.assertEqual(result["deletedEmptyDrafts"], 1)
        self.assertTrue(AIChangeSet.objects.filter(pk=empty.pk).exists())

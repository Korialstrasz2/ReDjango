import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.core.api import ApiError
from backend.core.item_services import create_item, update_item
from backend.core.models import Giocatore, Oggetto, OpzioneTipoOggetto, TipoArma

from .changes.registry import get_change_handler
from .changes.serializers import serialize_change_set
from .changes.services import (
    add_change_operation,
    apply_change_set,
    create_change_set,
    discard_change_set,
    get_change_set_for_user,
    update_change_operation,
    validate_change_set,
)
from .models import AIAgentProfile, AIChangeOperation, AIChangeSet, AIConversation


def envelope(action: str, payload: dict) -> str:
    return json.dumps(
        {
            "action": action,
            "requestId": "master-ai-test",
            "context": {"screen": "master-ai"},
            "payload": payload,
            "meta": {"clientVersion": "test"},
        }
    )


class MasterAIChangeSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.master_user = user_model.objects.create_user(username="proposal_master")
        cls.master = Giocatore.objects.create(user=cls.master_user, nome="proposal_master", role=Giocatore.ROLE_MASTER)
        cls.admin_user = user_model.objects.create_user(username="proposal_admin")
        cls.admin = Giocatore.objects.create(user=cls.admin_user, nome="proposal_admin", role=Giocatore.ROLE_ADMIN)
        cls.player_user = user_model.objects.create_user(username="proposal_player")
        cls.player = Giocatore.objects.create(user=cls.player_user, nome="proposal_player", role=Giocatore.ROLE_USER)
        OpzioneTipoOggetto.objects.create(posizione=1, valore="arma", etichetta="Arma", attiva=True)
        OpzioneTipoOggetto.objects.create(posizione=1, valore="inattivo", etichetta="Inattivo", attiva=False)
        cls.weapon_type = TipoArma.objects.create(nome="Spada")

    def create_set(self, *, title="Test"):
        return create_change_set(self.master_user, self.master, title=title)

    def test_agent_mode_defaults_to_read_only(self):
        agent = AIAgentProfile.objects.create(name="Base", slug="base")
        self.assertEqual(agent.mode, AIAgentProfile.MODE_READ_ONLY)

    def test_player_cannot_create_change_set(self):
        with self.assertRaises(ApiError) as captured:
            create_change_set(self.player_user, self.player, title="No")
        self.assertEqual(captured.exception.status, 403)

    def test_user_cannot_fetch_another_users_set(self):
        change_set = self.create_set()
        with self.assertRaises(ApiError) as captured:
            get_change_set_for_user(self.admin_user, change_set.id)
        self.assertEqual(captured.exception.status, 404)

    def test_conversation_deletion_preserves_change_set(self):
        conversation = AIConversation.objects.create(user=self.master_user, title="Conversation")
        change_set = create_change_set(self.master_user, self.master, title="Conversation proposal", conversation=conversation)
        conversation.delete()
        change_set.refresh_from_db()
        self.assertIsNone(change_set.conversation_id)

    def test_item_schema_uses_server_choices_and_excludes_internal_fields(self):
        schema = get_change_handler("item").field_schema(self.master_user, self.master, action="create")
        by_name = {field["name"]: field for field in schema}
        self.assertEqual(by_name["tipo_1"]["choices"], [{"value": "arma", "label": "Arma"}])
        self.assertEqual(by_name["rarita"]["choices"], [{"value": value, "label": label} for value, label in Oggetto.Rarita.choices])
        self.assertIn({"value": self.weapon_type.id, "label": "Spada"}, by_name["tipoArmaId"]["choices"])
        self.assertNotIn("metadata", by_name)
        self.assertNotIn("archived_at", by_name)
        self.assertNotIn("archiviato", by_name)
        self.assertNotIn("weapon_profile", by_name)

    def test_item_create_validates_and_applies_once(self):
        change_set = self.create_set(title="Create item")
        add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="item",
            action="create",
            values={"nome": "Spada proposta", "tipo_1": "arma", "tipoArmaId": self.weapon_type.id},
        )
        ready = validate_change_set(self.master_user, self.master, change_set.id)
        self.assertEqual(ready.status, AIChangeSet.STATUS_READY)
        token = ready.validation_token
        applied = apply_change_set(self.master_user, self.master, change_set.id, token)
        self.assertEqual(applied.status, AIChangeSet.STATUS_APPLIED)
        self.assertEqual(Oggetto.objects.filter(nome="Spada proposta").count(), 1)
        with self.assertRaises(ApiError):
            apply_change_set(self.master_user, self.master, change_set.id, token)

    def test_duplicate_name_fails_before_apply(self):
        create_item(self.master_user, self.master, {"nome": "Duplicato"})
        change_set = self.create_set()
        with self.assertRaises(ApiError) as captured:
            add_change_operation(
                self.master_user,
                self.master,
                change_set.id,
                entity_type="item",
                action="create",
                values={"nome": "duplicato"},
            )
        self.assertEqual(captured.exception.code, "items.duplicate_name")
        self.assertEqual(change_set.operations.count(), 0)

    def test_clone_copies_allowed_fields_and_requires_new_identity(self):
        source = create_item(
            self.master_user,
            self.master,
            {
                "nome": "Sorgente",
                "descrizione": "Testo sorgente",
                "tipo_1": "arma",
                "tipoArmaId": self.weapon_type.id,
                "metadata": {"secret": "not copied"},
            },
        )
        change_set = self.create_set()
        operation = add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="item",
            action="create",
            source_id=source.id,
            values={"nome": "Clone sicuro"},
        )
        self.assertEqual(operation.proposed_values["descrizione"], "Testo sorgente")
        self.assertEqual(operation.proposed_values["nome"], "Clone sicuro")
        self.assertNotIn("metadata", operation.proposed_values)
        self.assertEqual(operation.source_id, source.id)

    def test_update_diff_and_human_values_override_proposal(self):
        item = create_item(self.master_user, self.master, {"nome": "Peso", "peso": 4})
        change_set = self.create_set()
        operation = add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="item",
            action="update",
            target_id=item.id,
            values={"peso": 3.5},
        )
        update_change_operation(self.master_user, change_set.id, operation.id, {"editedValues": {"peso": 2.5}})
        ready = validate_change_set(self.master_user, self.master, change_set.id)
        operation_payload = serialize_change_set(ready)["operations"][0]
        peso_diff = next(entry for entry in operation_payload["diff"] if entry["field"] == "peso")
        self.assertEqual(peso_diff["before"], 4)
        self.assertEqual(peso_diff["after"], 2.5)
        apply_change_set(self.master_user, self.master, change_set.id, ready.validation_token)
        item.refresh_from_db()
        self.assertEqual(item.peso, 2.5)

    def test_editing_invalidates_validation_token(self):
        change_set = self.create_set()
        operation = add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="item",
            action="create",
            values={"nome": "Token item"},
        )
        ready = validate_change_set(self.master_user, self.master, change_set.id)
        old_token = ready.validation_token
        update_change_operation(self.master_user, change_set.id, operation.id, {"editedValues": {"descrizione": "Changed"}})
        change_set.refresh_from_db()
        self.assertEqual(change_set.status, AIChangeSet.STATUS_DRAFT)
        self.assertEqual(change_set.validation_token, "")
        with self.assertRaises(ApiError):
            apply_change_set(self.master_user, self.master, change_set.id, old_token)

    def test_stale_target_returns_conflict_and_writes_nothing(self):
        item = create_item(self.master_user, self.master, {"nome": "Stale", "descrizione": "Before"})
        change_set = self.create_set()
        add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="item",
            action="update",
            target_id=item.id,
            values={"descrizione": "Proposal"},
        )
        ready = validate_change_set(self.master_user, self.master, change_set.id)
        update_item(self.master_user, self.master, item.id, {"descrizione": "Normal editor"})
        with self.assertRaises(ApiError) as captured:
            apply_change_set(self.master_user, self.master, change_set.id, ready.validation_token)
        self.assertEqual(captured.exception.status, 409)
        self.assertEqual(captured.exception.code, "ai.change_target_stale")
        item.refresh_from_db()
        self.assertEqual(item.descrizione, "Normal editor")
        change_set.refresh_from_db()
        self.assertEqual(change_set.status, AIChangeSet.STATUS_READY)

    def test_archive_uses_soft_archive_without_delete(self):
        item = create_item(self.master_user, self.master, {"nome": "Archive me"})
        change_set = self.create_set()
        add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="item",
            action="archive",
            target_id=item.id,
        )
        ready = validate_change_set(self.master_user, self.master, change_set.id)
        apply_change_set(self.master_user, self.master, change_set.id, ready.validation_token)
        item.refresh_from_db()
        self.assertTrue(item.archiviato)
        self.assertIsNotNone(item.archived_at)
        self.assertTrue(Oggetto.objects.filter(pk=item.id).exists())

    def test_deselected_operation_is_not_applied(self):
        change_set = self.create_set()
        add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="item",
            action="create",
            values={"nome": "Selected"},
        )
        second = add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="item",
            action="create",
            values={"nome": "Deselected"},
        )
        update_change_operation(self.master_user, change_set.id, second.id, {"selected": False})
        ready = validate_change_set(self.master_user, self.master, change_set.id)
        apply_change_set(self.master_user, self.master, change_set.id, ready.validation_token)
        self.assertTrue(Oggetto.objects.filter(nome="Selected").exists())
        self.assertFalse(Oggetto.objects.filter(nome="Deselected").exists())
        second.refresh_from_db()
        self.assertEqual(second.status, AIChangeOperation.STATUS_SKIPPED)

    def test_second_operation_failure_rolls_back_first(self):
        target = create_item(self.master_user, self.master, {"nome": "Rollback target"})
        change_set = self.create_set()
        add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="item",
            action="create",
            values={"nome": "Must roll back"},
        )
        add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="item",
            action="archive",
            target_id=target.id,
        )
        ready = validate_change_set(self.master_user, self.master, change_set.id)
        with patch("backend.ai.changes.handlers.item.ItemChangeHandler.apply_archive", side_effect=ApiError("test.failure", "Failure")):
            with self.assertRaises(ApiError):
                apply_change_set(self.master_user, self.master, change_set.id, ready.validation_token)
        self.assertFalse(Oggetto.objects.filter(nome="Must roll back").exists())
        target.refresh_from_db()
        self.assertFalse(target.archiviato)
        change_set.refresh_from_db()
        self.assertEqual(change_set.status, AIChangeSet.STATUS_READY)

    def test_discard_is_immutable_and_performs_no_write(self):
        change_set = self.create_set()
        add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="item",
            action="create",
            values={"nome": "Discarded item"},
        )
        discard_change_set(self.master_user, change_set.id)
        self.assertFalse(Oggetto.objects.filter(nome="Discarded item").exists())
        with self.assertRaises(ApiError):
            add_change_operation(
                self.master_user,
                self.master,
                change_set.id,
                entity_type="item",
                action="create",
                values={"nome": "No"},
            )

    def test_unsupported_entity_fails_closed(self):
        change_set = self.create_set()
        with self.assertRaises(ApiError) as captured:
            add_change_operation(
                self.master_user,
                self.master,
                change_set.id,
                entity_type="auth.user",
                action="create",
                values={"username": "bad"},
            )
        self.assertEqual(captured.exception.code, "ai.change_entity_unsupported")

    def test_manual_api_flow(self):
        self.client.force_login(self.master_user)
        created = self.client.post(
            "/api/ai/change-sets/",
            data=envelope("ai.changeSet.create", {"title": "API create"}),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        change_set_id = created.json()["data"]["changeSet"]["id"]
        operation = self.client.post(
            f"/api/ai/change-sets/{change_set_id}/operations/",
            data=envelope("ai.changeOperation.add", {"entityType": "item", "action": "create", "values": {"nome": "API item"}}),
            content_type="application/json",
        )
        self.assertEqual(operation.status_code, 201)
        validated = self.client.post(
            f"/api/ai/change-sets/{change_set_id}/validate/",
            data=envelope("ai.changeSet.validate", {}),
            content_type="application/json",
        )
        self.assertEqual(validated.status_code, 200)
        token = validated.json()["data"]["changeSet"]["validation"]["token"]
        applied = self.client.post(
            f"/api/ai/change-sets/{change_set_id}/apply/",
            data=envelope("ai.changeSet.apply", {"token": token}),
            content_type="application/json",
        )
        self.assertEqual(applied.status_code, 200)
        self.assertTrue(Oggetto.objects.filter(nome="API item").exists())

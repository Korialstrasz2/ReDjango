from django.test import SimpleTestCase

from backend.ai.changes.serializers import operation_diff, serialize_change_operation
from backend.ai.models import AIChangeOperation


class MasterAICloneDiffTests(SimpleTestCase):
    def test_clone_diff_uses_source_snapshot(self):
        operation = AIChangeOperation(
            action=AIChangeOperation.ACTION_CREATE,
            entity_type="item",
            source_id=14,
            original_snapshot={"values": {"nome": "Tocco", "descrizione": "Sorgente"}},
            proposed_values={"nome": "Tocco mortale", "descrizione": "Sorgente"},
            field_schema=[
                {"name": "nome", "label": "Nome"},
                {"name": "descrizione", "label": "Descrizione"},
            ],
        )

        diff = {entry["field"]: entry for entry in operation_diff(operation)}

        self.assertEqual(diff["nome"]["before"], "Tocco")
        self.assertEqual(diff["nome"]["after"], "Tocco mortale")
        self.assertTrue(diff["nome"]["changed"])
        self.assertEqual(diff["descrizione"]["before"], "Sorgente")
        self.assertFalse(diff["descrizione"]["changed"])

    def test_clone_intent_is_explicit_in_serialized_operation(self):
        operation = AIChangeOperation(
            action=AIChangeOperation.ACTION_CREATE,
            entity_type="item",
            source_id=14,
            proposed_values={},
            field_schema=[],
        )

        self.assertEqual(serialize_change_operation(operation)["intent"], "clone")

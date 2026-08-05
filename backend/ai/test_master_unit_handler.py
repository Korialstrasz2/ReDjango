from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.characters.models import Personaggio
from backend.core.api import ApiError
from backend.core.models import Giocatore, Unit

from .changes.registry import get_change_handler
from .changes.services import (
    add_change_operation,
    apply_change_set,
    create_change_set,
    update_change_operation,
    validate_change_set,
)
from .models import AIChangeSet


class MasterAIUnitHandlerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.master_user = user_model.objects.create_user(username="master_ai_unit")
        cls.master = Giocatore.objects.create(
            user=cls.master_user,
            nome="master_ai_unit",
            role=Giocatore.ROLE_MASTER,
        )
        cls.player_user = user_model.objects.create_user(username="master_ai_unit_player")
        cls.player = Giocatore.objects.create(
            user=cls.player_user,
            nome="master_ai_unit_player",
            role=Giocatore.ROLE_USER,
        )

    @staticmethod
    def creature_values(name="Creatura proposta"):
        return {
            "name": name,
            "category": "Creature test",
            "loreImageId": None,
            "archetypeDescription": "Creatura rapida con chassis deterministico e attacco innato manuale.",
            "loreDescription": "Una creatura usata per verificare il flusso Master AI.",
            "notes": "Curva e azione verificate dal generatore reale. L'attacco resta un promemoria manuale.",
            "generation": {
                "kind": "creature",
                "coreKey": "",
                "coreShare": 0.5,
                "startingXp": 0,
                "xpBase": 20,
                "xpGrowth": 1,
                "competenceStartingXp": 5,
                "competenceXpBase": 15,
                "competenceXpGrowth": 0,
                "finalSpendingPasses": 4,
                "magicPolicy": "any",
                "allowedClassFamilies": [],
                "allowedReligionFamilies": [],
                "allowedRaces": [],
                "allowedSubraces": [],
                "allowHumanoidStatGrowth": False,
            },
            "archetypeTags": {},
            "competenceProfile": {},
            "skillUnlocks": [],
            "equipmentSlots": [],
            "equipmentGroups": [],
            "accessoryCountByLevel": [],
            "accessoryProfileKey": "",
            "innateActions": [
                {
                    "key": "master-ai-unit-bite",
                    "name": "Morso di prova",
                    "description": "Azione: bersaglio adiacente; il Master risolve tiro, danno e condizioni.",
                    "minLevel": 1,
                    "maxLevel": 20,
                    "costs": {"energia": 1, "pa": 2},
                    "trigger": "Azione",
                    "duration": "Istantanea",
                    "icon": "runa",
                }
            ],
            "statProfile": {
                "baseModifiers": {},
                "perLevelModifiers": {},
                "milestones": [],
                "curves": [
                    {"key": "pf", "profile": "custom", "level1": 12, "level20": 60},
                    {"key": "pa", "profile": "custom", "level1": 7, "level20": 24},
                ],
            },
            "levels": [],
        }

    def create_set(self):
        return create_change_set(self.master_user, self.master, title="Unit proposal")

    def test_unit_is_registered_with_live_configuration_and_specialized_widget(self):
        handler = get_change_handler("unit")
        fields = handler.field_schema(self.master_user, self.master, action="create")
        by_name = {field["name"]: field for field in fields}
        self.assertEqual(by_name["name"]["ui"]["widget"], "unitDefinition")
        configuration = by_name["name"]["ui"]["configuration"]
        self.assertEqual({entry["value"] for entry in configuration["kinds"]}, {"creature", "humanoid"})
        self.assertTrue(configuration["cores"])
        self.assertTrue(configuration["equipmentSlots"])
        self.assertTrue(configuration["statCurveVariables"])
        self.assertTrue(by_name["auditPreview"]["readOnly"])

    def test_player_cannot_access_unit_handler(self):
        with self.assertRaises(ApiError) as captured:
            get_change_handler("unit").field_schema(self.player_user, self.player, action="create")
        self.assertEqual(captured.exception.status, 403)

    def test_create_validate_apply_runs_real_rollback_audit(self):
        handler = get_change_handler("unit")
        change_set = self.create_set()
        before_characters = Personaggio.objects.count()
        with (
            patch.object(handler, "AUDIT_LEVELS", (1, 10, 20)),
            patch.object(handler, "AUDIT_REPEAT_LEVELS", (1, 20)),
            patch.object(handler, "AUDIT_AUTO_LEVELS", (1, 20)),
            patch.object(handler, "AUDIT_AUTO_PER_LEVEL", 2),
        ):
            operation = add_change_operation(
                self.master_user,
                self.master,
                change_set.id,
                entity_type="unit",
                action="create",
                values=self.creature_values(),
            )
            self.assertTrue(operation.proposed_values["auditPreview"]["passed"])
            self.assertEqual(operation.proposed_values["auditPreview"]["levels"], [1, 10, 20])
            self.assertEqual(Personaggio.objects.count(), before_characters)

            ready = validate_change_set(self.master_user, self.master, change_set.id)
            self.assertEqual(ready.status, AIChangeSet.STATUS_READY)
            self.assertEqual(Personaggio.objects.count(), before_characters)

            applied = apply_change_set(
                self.master_user,
                self.master,
                change_set.id,
                ready.validation_token,
            )
        self.assertEqual(applied.status, AIChangeSet.STATUS_APPLIED)
        unit = Unit.objects.get(nome="Creatura proposta")
        self.assertEqual(unit.generation_rules["kind"], "creature")
        self.assertEqual(unit.skill_actions[0]["name"], "Morso di prova")
        self.assertEqual(Personaggio.objects.count(), before_characters)

    def test_audit_preview_is_read_only(self):
        handler = get_change_handler("unit")
        change_set = self.create_set()
        with (
            patch.object(handler, "AUDIT_LEVELS", (1,)),
            patch.object(handler, "AUDIT_REPEAT_LEVELS", (1,)),
            patch.object(handler, "AUDIT_AUTO_LEVELS", (1,)),
            patch.object(handler, "AUDIT_AUTO_PER_LEVEL", 2),
        ):
            operation = add_change_operation(
                self.master_user,
                self.master,
                change_set.id,
                entity_type="unit",
                action="create",
                values=self.creature_values("Audit protetto"),
            )
        with self.assertRaises(ApiError) as captured:
            update_change_operation(
                self.master_user,
                change_set.id,
                operation.id,
                {"editedValues": {"auditPreview": {"passed": False}}},
            )
        self.assertEqual(captured.exception.code, "ai.change_field_unknown")

    def test_archive_uses_unit_soft_archive_service(self):
        unit = Unit.objects.create(
            nome="Unit da archiviare",
            categoria="Creature test",
            generation_rules={"kind": "creature"},
        )
        change_set = self.create_set()
        add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="unit",
            action="archive",
            target_id=unit.id,
        )
        ready = validate_change_set(self.master_user, self.master, change_set.id)
        apply_change_set(self.master_user, self.master, change_set.id, ready.validation_token)
        unit.refresh_from_db()
        self.assertIsNotNone(unit.archived_at)
        self.assertTrue(Unit.objects.filter(pk=unit.id).exists())

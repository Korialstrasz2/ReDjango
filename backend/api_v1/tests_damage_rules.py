import copy
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.combat.damage_rules import (
    DAMAGE_RULES_CONFIG_KEY,
    configured_damage_rules,
    default_damage_rules,
)
from backend.core.models import Giocatore, GlobalModifiers


class DamageRuleManagementApiTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="damage-admin")
        self.giocatore = Giocatore.objects.create(
            user=user,
            nome="local_master",
            display_name="Admin danno",
            role=Giocatore.ROLE_ADMIN,
        )
        self.client.force_login(user)
        self.profile = GlobalModifiers.objects.create(
            name="Formule_base",
            value_string={
                DAMAGE_RULES_CONFIG_KEY: default_damage_rules(),
                "preserved": {"enabled": True},
            },
        )

    def command(self, action: str, payload: dict):
        return self.client.post(
            "/api/v1/actions",
            data=json.dumps({
                "action": action,
                "requestId": "damage-rules-test",
                "payload": payload,
            }),
            content_type="application/json",
        )

    def test_contract_contains_complete_elder_tables_and_is_admin_only(self):
        response = self.client.get("/api/v1/management/damage-rules")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["counts"]["resistanceLevels"], 14)
        self.assertEqual(data["counts"]["damageTiers"], 36)
        self.assertEqual(data["counts"]["d20Rows"], 20)
        self.assertEqual(data["counts"]["attackDifferenceColumns"], 71)
        self.assertEqual(len(data["rules"]["damageMultipliers"]["20"]), 71)
        self.assertEqual(data["rules"]["resistancePercentages"]["9"], 60)

        self.giocatore.role = Giocatore.ROLE_MASTER
        self.giocatore.save(update_fields=["role", "updated_at"])
        self.assertEqual(
            self.client.get("/api/v1/management/damage-rules").status_code,
            403,
        )

    def test_validation_and_save_update_the_combat_source_object(self):
        rules = configured_damage_rules(self.profile)
        rules["damageMultipliers"]["10"][32] = 137
        rules["tierDamageFormulas"]["0"] = "2d6+3"
        rules["resistancePercentages"]["0"] = 12

        validation_response = self.command(
            "management.damageRules.validate",
            {"rules": rules},
        )

        self.assertEqual(validation_response.status_code, 200)
        validation = validation_response.json()["data"]["management"][
            "validation"
        ]
        self.assertEqual(validation["changedCount"], 3)
        self.assertEqual(validation["changeCounts"]["multipliers"], 1)
        self.assertEqual(validation["changeCounts"]["tiers"], 1)
        self.assertEqual(validation["changeCounts"]["resistances"], 1)

        saved_response = self.command(
            "management.damageRules.save",
            {
                "rules": rules,
                "previewToken": validation["previewToken"],
            },
        )

        self.assertEqual(saved_response.status_code, 200)
        self.profile.refresh_from_db()
        saved = self.profile.value_string[DAMAGE_RULES_CONFIG_KEY]
        self.assertEqual(saved["damageMultipliers"]["10"][32], 137)
        self.assertEqual(saved["tierDamageFormulas"]["0"], "2d6+3")
        self.assertEqual(saved["resistancePercentages"]["0"], 12)
        self.assertEqual(
            self.profile.value_string["preserved"],
            {"enabled": True},
        )

    def test_invalid_grid_and_formula_are_rejected_without_writing(self):
        before = copy.deepcopy(self.profile.value_string)
        rules = configured_damage_rules(self.profile)
        rules["damageMultipliers"]["4"].pop()
        invalid_grid = self.command(
            "management.damageRules.validate",
            {"rules": rules},
        )
        self.assertEqual(invalid_grid.status_code, 400)
        self.assertEqual(
            invalid_grid.json()["errors"][0]["code"],
            "management.damage_rules.grid_columns_incomplete",
        )

        rules = configured_damage_rules(self.profile)
        rules["tierDamageFormulas"]["5"] = "eval(character)"
        invalid_formula = self.command(
            "management.damageRules.validate",
            {"rules": rules},
        )
        self.assertEqual(invalid_formula.status_code, 400)
        self.assertEqual(
            invalid_formula.json()["errors"][0]["code"],
            "management.damage_rules.formula_invalid",
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.value_string, before)

    def test_save_rejects_changes_made_after_validation(self):
        rules = configured_damage_rules(self.profile)
        rules["resistancePercentages"]["1"] = 16
        validation = self.command(
            "management.damageRules.validate",
            {"rules": rules},
        ).json()["data"]["management"]["validation"]
        rules["resistancePercentages"]["1"] = 17

        response = self.command(
            "management.damageRules.save",
            {
                "rules": rules,
                "previewToken": validation["previewToken"],
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["errors"][0]["code"],
            "management.damage_rules.changed_after_validation",
        )

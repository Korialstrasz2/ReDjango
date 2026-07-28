import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.core.defaults import (
    FORMULE_BASE_FORMULAS,
    FORMULE_BASE_VALUE_FLOAT,
    QUICK_STAT_ADJUSTMENT_DEFAULTS,
    SKILL_PRICING_DEFAULTS,
)
from backend.core.models import Giocatore, GlobalModifiers


class GameVariableManagementApiTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="variables-admin")
        self.giocatore = Giocatore.objects.create(
            user=user,
            nome="local_master",
            display_name="Admin test",
            role=Giocatore.ROLE_ADMIN,
        )
        self.client.force_login(user)
        self.profile = GlobalModifiers.objects.create(
            name="Formule_base",
            value_float=dict(FORMULE_BASE_VALUE_FLOAT),
            value_string={
                "formulas": dict(FORMULE_BASE_FORMULAS),
                "quick_stat_adjustments": dict(
                    QUICK_STAT_ADJUSTMENT_DEFAULTS,
                ),
                "skill_pricing": dict(SKILL_PRICING_DEFAULTS),
                "adjustment.livello": "personaggio.livello / 5",
                "adjustment.fortuna": "((final.fortuna - 10) * 0.15) - 0.15",
                "unrelated_preserved_key": {"enabled": True},
            },
            rule_notes="Profilo di prova.",
        )

    def command(self, action: str, payload: dict):
        return self.client.post(
            "/api/v1/actions",
            data=json.dumps({
                "action": action,
                "requestId": "variables-test",
                "payload": payload,
            }),
            content_type="application/json",
        )

    def variable_values(self) -> dict:
        response = self.client.get("/api/v1/management/game-variables")
        self.assertEqual(response.status_code, 200)
        return {
            field["id"]: field["value"]
            for group in response.json()["data"]["groups"]
            for field in group["fields"]
        }

    def test_page_contract_is_admin_only_and_type_aware(self):
        response = self.client.get("/api/v1/management/game-variables")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        fields = {
            field["id"]: field
            for group in data["groups"]
            for field in group["fields"]
        }
        self.assertEqual(fields["base.pf"]["valueType"], "integer")
        self.assertEqual(fields["formula.pf"]["valueType"], "formula")
        self.assertEqual(fields["adjustment.livello"]["valueType"], "formula")
        self.assertEqual(fields["adjustment.fortuna"]["valueType"], "formula")
        self.assertEqual(
            fields["quick.targets"]["valueType"],
            "multi_select",
        )
        self.assertEqual(fields["quick.fatigue_fixed_per_point"]["value"], 1)
        self.assertEqual(
            fields["quick.general_modifier_fixed_per_point"]["value"],
            1.5,
        )
        self.assertTrue(fields["base.stanchezza"]["guide"]["influence"])
        self.assertNotIn("base.mod_forza", fields)

        self.giocatore.role = Giocatore.ROLE_MASTER
        self.giocatore.save(update_fields=["role", "updated_at"])
        self.assertEqual(
            self.client.get("/api/v1/management/game-variables").status_code,
            403,
        )
        forbidden = self.command(
            "management.variables.validate",
            {"values": {}},
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_invalid_formula_is_rejected_without_writing(self):
        values = self.variable_values()
        values["formula.pf"] = "unknown.pf + 1"
        before = self.profile.value_string

        response = self.command(
            "management.variables.validate",
            {"values": values},
        )

        self.assertEqual(response.status_code, 400)
        error = response.json()["errors"][0]
        self.assertEqual(
            error["code"],
            "management.variables.formula_invalid",
        )
        self.assertEqual(error["field"], "formula.pf")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.value_string, before)

    def test_save_requires_matching_server_validation_and_preserves_unknown_data(self):
        values = self.variable_values()
        values["quick.fatigue_percent_per_point"] = "6.5"
        values["quick.fatigue_fixed_per_point"] = "2"
        values["adjustment.livello"] = "personaggio.livello / 4"
        values["base.pf"] = "22"

        validation_response = self.command(
            "management.variables.validate",
            {"values": values},
        )

        self.assertEqual(validation_response.status_code, 200)
        validation = validation_response.json()["data"]["management"][
            "validation"
        ]
        self.assertEqual(validation["changedCount"], 4)
        self.profile.refresh_from_db()
        self.assertEqual(
            self.profile.value_string["quick_stat_adjustments"][
                "fatigue_percent_per_point"
            ],
            3,
        )

        changed_values = dict(values)
        changed_values["base.pf"] = "23"
        mismatch = self.command(
            "management.variables.save",
            {
                "values": changed_values,
                "previewToken": validation["previewToken"],
            },
        )
        self.assertEqual(mismatch.status_code, 409)
        self.assertEqual(
            mismatch.json()["errors"][0]["code"],
            "management.variables.changed_after_validation",
        )

        saved = self.command(
            "management.variables.save",
            {
                "values": values,
                "previewToken": validation["previewToken"],
            },
        )

        self.assertEqual(saved.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.value_float["pf"], 22)
        self.assertEqual(
            self.profile.value_string["quick_stat_adjustments"][
                "fatigue_percent_per_point"
            ],
            6.5,
        )
        self.assertEqual(
            self.profile.value_string["quick_stat_adjustments"][
                "fatigue_fixed_per_point"
            ],
            2,
        )
        self.assertEqual(
            self.profile.value_string["adjustment.livello"],
            "personaggio.livello / 4",
        )
        self.assertEqual(
            self.profile.value_string["unrelated_preserved_key"],
            {"enabled": True},
        )

    def test_validation_token_detects_a_concurrent_profile_change(self):
        values = self.variable_values()
        values["base.mana"] = "14"
        validation = self.command(
            "management.variables.validate",
            {"values": values},
        ).json()["data"]["management"]["validation"]
        self.profile.rule_notes = "Modifica concorrente."
        self.profile.save(update_fields=["rule_notes", "updated_at"])

        response = self.command(
            "management.variables.save",
            {
                "values": values,
                "previewToken": validation["previewToken"],
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["errors"][0]["code"],
            "management.variables.stale",
        )

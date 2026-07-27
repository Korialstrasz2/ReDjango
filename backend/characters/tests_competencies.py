import json

from django.core.management import call_command
from django.test import TestCase

from backend.characters.models import Personaggio, TiroCompetenza
from backend.characters.services.custom_effects import create_custom_effect
from backend.core.models import Competenze, Giocatore, Oggetto


class CompetenceWorkspaceApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_minimum_data", verbosity=0)

    def setUp(self):
        self.giocatore = Giocatore.objects.get(nome="local_master")
        self.character = Personaggio.objects.get(nome_interno="poc_darion_frondaluna")
        self.giocatore.active_character = self.character
        if self.character.id not in self.giocatore.character_ids:
            self.giocatore.character_ids = [*self.giocatore.character_ids, self.character.id]
        self.giocatore.save(update_fields=["active_character", "character_ids", "updated_at"])

    def command(self, action, payload, request_id="competencies-test"):
        return self.client.post(
            "/api/v1/actions",
            data=json.dumps({"action": action, "requestId": request_id, "payload": payload}),
            content_type="application/json",
        )

    def state(self, key):
        self.character.refresh_from_db()
        return self.character.competenze[key]

    def test_seed_and_catalog_preserve_the_twenty_one_legacy_competencies(self):
        response = self.client.get(f"/api/v1/characters/{self.character.id}/competencies")

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(Competenze.objects.count(), 21)
        self.assertEqual(len(data["competencies"]), 21)
        self.assertEqual(data["competencies"][0]["name"], "Scalare")
        self.assertEqual(data["competencies"][-1]["name"], "Intuizione")
        self.assertTrue(all(entry["iconUrl"].endswith(f"/{entry['key']}.png") for entry in data["competencies"]))
        perception = next(entry for entry in data["competencies"] if entry["key"] == "percezione")
        self.assertGreaterEqual(len(perception["thresholds"]), 2)
        self.assertEqual(perception["baseRank"], 0)
        self.assertEqual(perception["masteryRank"], 0)
        self.assertEqual(perception["manualExtra"], 0)

    def test_progression_spends_triangular_xp_atomically(self):
        self.character.pe_abilita = 4
        self.character.save(update_fields=["pe_abilita", "updated_at"])

        response = self.command("competencies.upgrade", {
            "characterId": self.character.id,
            "competenceKey": "scalare",
            "track": "base",
            "targetRank": 2,
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.character.refresh_from_db()
        self.assertEqual(self.character.pe_abilita, 1)
        self.assertEqual(self.character.competenze["scalare"]["barra1"], 2)

        rejected = self.command("competencies.upgrade", {
            "characterId": self.character.id,
            "competenceKey": "scalare",
            "track": "base",
            "targetRank": 3,
        })
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(rejected.json()["errors"][0]["code"], "competencies.xp_insufficient")
        self.character.refresh_from_db()
        self.assertEqual(self.character.pe_abilita, 1)
        self.assertEqual(self.character.competenze["scalare"]["barra1"], 2)

    def test_rank_reduction_refunds_xp_without_enforcing_the_advisory_limit(self):
        self.character.competenze["scalare"] = {"barra1": 4, "barra2": 0, "extra": 0}
        self.character.pe_abilita = 0
        self.character.save(update_fields=["competenze", "pe_abilita", "updated_at"])

        # Four reductions deliberately remain valid: the UI warning is advisory, not a persisted rule.
        for target_rank in (3, 2, 1, 0):
            response = self.command("competencies.upgrade", {
                "characterId": self.character.id,
                "competenceKey": "scalare",
                "track": "base",
                "targetRank": target_rank,
            }, request_id=f"reduce-{target_rank}")
            self.assertEqual(response.status_code, 200, response.content)

        self.character.refresh_from_db()
        self.assertEqual(self.character.pe_abilita, 10)
        self.assertEqual(self.character.competenze["scalare"]["barra1"], 0)

    def test_manual_extra_and_equipped_bonus_remain_independent(self):
        response = self.command("competencies.updateExtra", {
            "characterId": self.character.id,
            "competenceKey": "scalare",
            "extra": 1,
        })
        self.assertEqual(response.status_code, 200, response.content)
        armor = Oggetto.objects.create(
            nome="Armatura dello scalatore",
            tipo_1="armatura",
            effects=[{"target": "competenza.scalare", "operation": "add", "value": 2}],
        )
        self.character.equip.armatura = armor
        self.character.equip.save(update_fields=["armatura", "updated_at"])

        equipped = self.client.get(f"/api/v1/characters/{self.character.id}/competencies").json()["data"]
        scalare = next(entry for entry in equipped["competencies"] if entry["key"] == "scalare")
        self.assertEqual((scalare["manualExtra"], scalare["linkedExtra"], scalare["effectiveExtra"]), (1, 2, 3))
        self.assertEqual(scalare["sourceBreakdown"][0]["sourceType"], "equipment")

        self.character.equip.armatura = None
        self.character.equip.save(update_fields=["armatura", "updated_at"])
        unequipped = self.client.get(f"/api/v1/characters/{self.character.id}/competencies").json()["data"]
        scalare = next(entry for entry in unequipped["competencies"] if entry["key"] == "scalare")
        self.assertEqual((scalare["manualExtra"], scalare["linkedExtra"], scalare["effectiveExtra"]), (1, 0, 1))

    def test_custom_effect_and_skill_passive_target_is_available(self):
        create_custom_effect(self.character.id, {
            "name": "Favore del Daedra",
            "description": "Un dono permanente.",
            "origin": "Abilità: Patto oscuro",
            "icon": "runa",
            "operations": [{
                "target": "competenza.intuizione",
                "operation": "add",
                "value": "1",
                "condition": "",
            }],
        })

        response = self.client.get(f"/api/v1/characters/{self.character.id}/competencies")
        intuition = next(entry for entry in response.json()["data"]["competencies"] if entry["key"] == "intuizione")
        self.assertEqual(intuition["linkedExtra"], 1)
        self.assertEqual(intuition["sourceBreakdown"][0]["sourceType"], "skill")
        sheet = self.client.get(f"/api/v1/characters/{self.character.id}/sheet").json()["data"]
        targets = {entry["value"] for entry in sheet["effectConfiguration"]["targets"]}
        self.assertIn("competenza.intuizione", targets)

    def test_mastery_roll_spends_energy_server_side_and_records_equation(self):
        self.character.competenze["scalare"] = {"barra1": 2, "barra2": 3, "extra": 1}
        self.character.tot = {**self.character.tot, "energia": 20}
        self.character.energia_spesa = 0
        self.character.save(update_fields=["competenze", "tot", "energia_spesa", "updated_at"])

        response = self.command("competencies.roll", {
            "characterId": self.character.id,
            "competenceKey": "scalare",
            "technique": "focus",
        })

        self.assertEqual(response.status_code, 200, response.content)
        roll = response.json()["data"]["competenceRoll"]
        self.assertEqual(roll["dieSides"], 8)
        self.assertEqual(roll["energySpent"], 3)
        self.assertEqual(roll["focusBonus"], 1)
        self.assertEqual(roll["multiplier"], 1)
        self.assertEqual(roll["total"], (roll["rolls"][0]["value"] + 3 + 1))
        self.character.refresh_from_db()
        self.assertEqual(self.character.energia_spesa, 3)

    def test_mastery_roll_cycles_energy_and_adds_fatigue_only_after_crossing_zero(self):
        self.character.competenze["scalare"] = {"barra1": 2, "barra2": 3, "extra": 0}
        energy_max = int(self.character.tot["energia"])
        self.assertGreaterEqual(energy_max, 3)
        self.character.energia_spesa = energy_max - 1
        self.character.stanchezza_accumulata = 0
        self.character.save(update_fields=["competenze", "energia_spesa", "stanchezza_accumulata", "updated_at"])

        cycled = self.command("competencies.roll", {
            "characterId": self.character.id,
            "competenceKey": "scalare",
            "technique": "focus",
        }, request_id="energy-cycle")

        self.assertEqual(cycled.status_code, 200, cycled.content)
        self.character.refresh_from_db()
        self.assertEqual(self.character.energia_spesa, 2)
        self.assertEqual(self.character.stanchezza_accumulata, 1)
        self.assertEqual(self.character.tot["stanchezza"], 1)

        self.character.energia_spesa = int(self.character.tot["energia"]) - 3
        self.character.stanchezza_accumulata = 0
        self.character.save(update_fields=["energia_spesa", "stanchezza_accumulata", "updated_at"])
        exact = self.command("competencies.roll", {
            "characterId": self.character.id,
            "competenceKey": "scalare",
            "technique": "focus",
        }, request_id="energy-exact-zero")

        self.assertEqual(exact.status_code, 200, exact.content)
        self.character.refresh_from_db()
        self.assertEqual(self.character.energia_spesa, int(self.character.tot["energia"]))
        self.assertEqual(self.character.stanchezza_accumulata, 0)

    def test_manually_saving_negative_energy_cycles_the_bar_and_adds_fatigue(self):
        response = self.command("character.updateResource", {
            "characterId": self.character.id,
            "resource": "energia",
            "current": -2,
        }, request_id="manual-energy-cycle")

        self.assertEqual(response.status_code, 200, response.content)
        self.character.refresh_from_db()
        self.assertEqual(self.character.energia_spesa, 2)
        self.assertEqual(self.character.stanchezza_accumulata, 1)
        self.assertEqual(self.character.tot["stanchezza"], 1)

    def test_energy_control_discounts_both_impulses_and_major_impulse_adds_two(self):
        self.character.competenze["scalare"] = {"barra1": 2, "barra2": 5, "extra": 1}
        self.character.tot = {**self.character.tot, "energia": 20}
        self.character.energia_spesa = 0
        self.character.save(update_fields=["competenze", "tot", "energia_spesa", "updated_at"])

        focus = self.command("competencies.roll", {
            "characterId": self.character.id,
            "competenceKey": "scalare",
            "technique": "focus",
        }, request_id="discounted-focus")
        amplify = self.command("competencies.roll", {
            "characterId": self.character.id,
            "competenceKey": "scalare",
            "technique": "amplify",
        }, request_id="discounted-amplify")

        self.assertEqual(focus.status_code, 200, focus.content)
        self.assertEqual(amplify.status_code, 200, amplify.content)
        focus_roll = focus.json()["data"]["competenceRoll"]
        amplify_roll = amplify.json()["data"]["competenceRoll"]
        self.assertEqual(focus_roll["energySpent"], 2)
        self.assertEqual(focus_roll["focusBonus"], 1)
        self.assertEqual(amplify_roll["energySpent"], 5)
        self.assertEqual(amplify_roll["focusBonus"], 2)
        self.assertEqual(amplify_roll["multiplier"], 1)
        self.assertEqual(amplify_roll["total"], amplify_roll["rolls"][0]["value"] + 3 + 2)
        self.character.refresh_from_db()
        self.assertEqual(self.character.energia_spesa, 7)

    def test_rank_seven_allows_two_free_rerolls_on_one_daily_roll(self):
        self.character.competenze["percezione"] = {"barra1": 0, "barra2": 7, "extra": 0}
        self.character.save(update_fields=["competenze", "updated_at"])
        first = self.command("competencies.roll", {
            "characterId": self.character.id,
            "competenceKey": "percezione",
            "technique": "standard",
        })
        roll_id = first.json()["data"]["competenceRoll"]["id"]

        for expected_used in (1, 2):
            reroll = self.command("competencies.reroll", {
                "characterId": self.character.id,
                "rollId": roll_id,
            }, request_id=f"reroll-{expected_used}")
            self.assertEqual(reroll.status_code, 200, reroll.content)
            self.assertEqual(reroll.json()["data"]["competenceRoll"]["rerollsUsed"], expected_used)

        rejected = self.command("competencies.reroll", {
            "characterId": self.character.id,
            "rollId": roll_id,
        }, request_id="reroll-3")
        self.assertEqual(rejected.status_code, 409)
        stored = TiroCompetenza.objects.get(pk=roll_id)
        self.assertEqual(stored.rerolls_used, 2)
        self.assertEqual(len(stored.rolls), 3)

    def test_competence_notes_are_saved_and_exposed_in_the_diary_contract(self):
        response = self.command("notes.updateSection", {
            "characterId": self.character.id,
            "section": "competenze",
            "content": "Il favore daedrico vale +1 Intuizione.",
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"]["notes"]["sections"]["competenze"], "Il favore daedrico vale +1 Intuizione.")
        notes = self.client.get(f"/api/v1/characters/{self.character.id}/notes").json()["data"]
        self.assertEqual(notes["sections"]["competenze"], "Il favore daedrico vale +1 Intuizione.")

    def test_openapi_contract_contains_competence_actions_and_catalog(self):
        schema_text = json.dumps(self.client.get("/api/v1/openapi.json").json())
        for action in (
            "competencies.upgrade", "competencies.updateExtra", "competencies.roll", "competencies.reroll",
        ):
            self.assertIn(action, schema_text)
        self.assertIn("CompetenceCatalogDataSchema", schema_text)

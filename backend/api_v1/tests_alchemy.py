import json

from django.core.management import call_command
from django.test import TestCase

from backend.characters.models import (
    ContenitoreInventario,
    Personaggio,
    VoceContenitoreInventario,
)
from backend.core.models import Giocatore, Oggetto, ReagenteAlchemico


class AlchemyCreationApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_minimum_data", verbosity=0)

    def setUp(self):
        self.giocatore = Giocatore.objects.get(nome="local_master")
        self.client.force_login(self.giocatore.user)
        self.character = Personaggio.objects.get(
            nome_interno="poc_darion_frondaluna"
        )
        self.container = ContenitoreInventario.objects.get(
            scope=ContenitoreInventario.SCOPE_PERSONAL,
            personaggio=self.character,
        )
        self.giocatore.active_character = self.character
        self.giocatore.save(update_fields=["active_character", "updated_at"])

    def command(self, action, payload):
        return self.client.post(
            "/api/v1/actions",
            data=json.dumps({"action": action, "requestId": "alchemy-test", "payload": payload}),
            content_type="application/json",
        )

    def set_stock(self, values):
        self.container.voci.exclude(reagent_stock_key="").delete()
        occupied = set(self.container.voci.values_list("slot", flat=True))
        for key, quantity in values.items():
            slot = next(candidate for candidate in range(1, self.container.capacita + 1) if candidate not in occupied)
            VoceContenitoreInventario.objects.create(
                contenitore=self.container,
                slot=slot,
                reagent_stock_key=key,
                quantita=quantity,
            )
            occupied.add(slot)

    def stock(self):
        return dict(
            self.container.voci.exclude(reagent_stock_key="").values_list(
                "reagent_stock_key", "quantita"
            )
        )

    def test_creation_workspace_exposes_twelve_rule_slots_and_elder_catalog(self):
        response = self.client.get(f"/api/v1/characters/{self.character.id}/creation")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data["bag"]["stock"]), 12)
        self.assertEqual(len(data["catalog"]), 42)
        self.assertEqual(ReagenteAlchemico.objects.count(), 42)
        self.assertEqual(
            {(entry["color"], entry["level"]) for entry in data["bag"]["stock"]},
            {(color, level) for color in ("rosso", "verde", "blu") for level in range(1, 5)},
        )
        self.assertEqual(data["rules"]["maxIngredients"], 4)
        self.assertEqual(data["thresholds"][-1], {"level": 10, "minimumPotency": 30})

    def test_brew_is_atomic_and_uses_character_level_and_color_multipliers(self):
        self.set_stock({"r1": 1, "b4": 1})
        totals = dict(self.character.tot)
        totals.update(
            {
                "moltiplicatore_reagenti_livello_1": 1.2,
                "moltiplicatore_reagenti_livello_4": 2.7,
                "moltiplicatore_reagenti_rossi": 0.2,
            }
        )
        self.character.tot = totals
        self.character.save(update_fields=["tot", "updated_at"])

        response = self.command(
            "alchemy.brew",
            {
                "characterId": self.character.id,
                "ingredients": [
                    {"color": "rosso", "level": 1},
                    {"color": "blu", "level": 4},
                ],
                "potionColor": "rosso",
                "effect": "Cura",
            },
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["data"]["alchemyResult"]
        self.assertEqual(result["levelTotal"], 3.9)
        self.assertEqual(result["abilityBonus"], 0.2)
        self.assertEqual(result["potency"], 4.68)
        self.assertEqual(result["potionLevel"], 1)
        self.assertEqual(self.stock(), {})

    def test_failed_brew_does_not_consume_available_stock(self):
        self.set_stock({"r1": 1})

        response = self.command(
            "alchemy.brew",
            {
                "characterId": self.character.id,
                "ingredients": [
                    {"color": "rosso", "level": 1},
                    {"color": "rosso", "level": 1},
                ],
                "potionColor": "rosso",
                "effect": "Cura",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["errors"][0]["code"], "alchemy.stock_insufficient")
        self.assertEqual(self.stock(), {"r1": 1})

    def test_extract_adds_a_canonical_color_level_stock_unit(self):
        self.set_stock({})
        self.container.capacita = 2
        self.container.save(update_fields=["capacita", "updated_at"])

        response = self.command("alchemy.extract", {"characterId": self.character.id})

        self.assertEqual(response.status_code, 200)
        extracted = response.json()["data"]["extractedReagent"]
        self.assertIn(extracted["color"], {"rosso", "verde", "blu"})
        self.assertIn(extracted["level"], range(1, 5))
        stock = self.stock()
        self.assertEqual(sum(stock.values()), 1)
        self.assertEqual(stock[extracted["stockKey"]], 1)

    def make_set(self, nome, descrizione):
        return Oggetto.objects.create(nome=nome, tipo_1="setalchemico", descrizione=descrizione)

    def store_item(self, container, item, slot):
        return VoceContenitoreInventario.objects.create(
            contenitore=container,
            slot=slot,
            oggetto=item,
            quantita=1,
        )

    def campaign_container(self):
        return ContenitoreInventario.objects.get_or_create(
            scope=ContenitoreInventario.SCOPE_CAMPAIGN,
            campagna=self.character.campagna,
            defaults={"nome": "Risorse gruppo · test", "capacita": 30},
        )[0]

    def test_creation_lists_reachable_sets_and_preselects_the_best_one(self):
        self.store_item(self.container, self.make_set("Set base test", "+ 10% effetto"), 10)
        self.store_item(self.campaign_container(), self.make_set("Set maestro test", "+ 40% effetto"), 1)

        response = self.client.get(f"/api/v1/characters/{self.character.id}/creation")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(
            [(entry["name"], entry["bonus"], entry["source"]) for entry in data["sets"]],
            [("Set maestro test", 1.4, "campaign"), ("Set base test", 1.1, "utility")],
        )
        self.assertEqual(data["rules"]["defaultSetId"], data["sets"][0]["id"])
        self.assertEqual(data["rules"]["defaultSetBonus"], 1.4)

    def test_brew_uses_the_server_side_bonus_of_the_selected_set(self):
        self.set_stock({"r1": 1})
        alchemy_set = self.make_set("Set qualificato test", "+ 25% effetto")
        self.store_item(self.container, alchemy_set, 10)
        totals = dict(self.character.tot)
        totals.update({"moltiplicatore_reagenti_livello_1": 2, "moltiplicatore_reagenti_rossi": 0})
        self.character.tot = totals
        self.character.save(update_fields=["tot", "updated_at"])

        response = self.command(
            "alchemy.brew",
            {
                "characterId": self.character.id,
                "ingredients": [{"color": "rosso", "level": 1}],
                "potionColor": "rosso",
                "effect": "Cura",
                "setItemId": alchemy_set.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["data"]["alchemyResult"]
        self.assertEqual(result["setBonus"], 1.25)
        self.assertEqual(result["setName"], "Set qualificato test")
        self.assertEqual(result["potency"], 2.5)

    def test_brew_rejects_a_set_the_character_cannot_reach(self):
        self.set_stock({"r1": 1})
        unreachable = self.make_set("Set irraggiungibile", "+ 40% effetto")

        response = self.command(
            "alchemy.brew",
            {
                "characterId": self.character.id,
                "ingredients": [{"color": "rosso", "level": 1}],
                "potionColor": "rosso",
                "effect": "Cura",
                "setItemId": unreachable.id,
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["errors"][0]["code"], "alchemy.set_not_available")
        self.assertEqual(self.stock(), {"r1": 1})

    def test_legacy_reagent_item_is_normalized_into_container_stock(self):
        self.set_stock({})
        legacy = Oggetto.objects.create(
            nome="Reagente Verde lv 2",
            tipo_1="reagente",
            tipo_2="verde",
            lv_loot="2",
        )

        response = self.command(
            "inventory.assignItem",
            {
                "characterId": self.character.id,
                "target": {"group": "utility", "slot": "1"},
                "itemId": legacy.id,
                "quantity": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        entry = self.container.voci.get(slot=1)
        self.assertIsNone(entry.oggetto_id)
        self.assertEqual(entry.reagent_stock_key, "v2")
        self.assertEqual(entry.quantita, 2)

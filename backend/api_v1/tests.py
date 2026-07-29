import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from backend.characters.models import BottoneCombat, EffettoPersonalizzato, Faretra, Note, OperazioneEffettoPersonalizzato, Personaggio, SkillPersonaggio, Zaino
from backend.characters.services.refresh_personaggio import refresh_personaggio
from backend.core.models import (
    DatiCampagna,
    FamigliaSkill,
    Giocatore,
    GruppoFamiglieSkill,
    Oggetto,
    OpzioneTipoOggetto,
    Skill,
    SpellDefinition,
    Theme,
    Unit,
)
from backend.core.weather import WEATHER_TABLE


class CharacterWorkspaceApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_minimum_data", verbosity=0)

    def setUp(self):
        self.giocatore = Giocatore.objects.get(nome="local_master")
        self.client.force_login(self.giocatore.user)
        self.character = Personaggio.objects.get(nome_interno="poc_darion_frondaluna")
        if self.character.id not in self.giocatore.character_ids:
            self.giocatore.character_ids = [*self.giocatore.character_ids, self.character.id]
        self.giocatore.active_character = self.character
        self.giocatore.save(update_fields=["character_ids", "active_character", "updated_at"])

    def command(self, action, payload, request_id="workspace-test"):
        return self.client.post(
            "/api/v1/actions",
            data=json.dumps({"action": action, "requestId": request_id, "payload": payload}),
            content_type="application/json",
        )

    def test_sheet_exposes_complete_slot_topology_and_theme_permissions(self):
        response = self.client.get(f"/api/v1/characters/{self.character.id}/sheet")
        self.assertEqual(response.status_code, 200)
        sheet = response.json()["data"]["character"]
        self.assertEqual(len(sheet["equipment"]["slots"]), 35)
        self.assertEqual(len(sheet["inventory"]["slots"]), 50)
        self.assertEqual(len(sheet["quiver"]["slots"]), 50)
        self.assertEqual(sheet["quiver"]["capacity"], 15)
        self.assertEqual(sheet["quiver"]["occupied"], 2)
        self.assertTrue(sheet["permissions"]["canManageItems"])
        self.assertEqual(sheet["appearance"]["characterKey"], "darion")
        self.assertEqual(sheet["appearance"]["preferredFilename"], "darion_base.webp")
        self.assertTrue(sheet["appearance"]["imageUrl"].startswith("/static/frontend/images/characters/"))
        self.assertIn("inventory_weight", self.character.effetti_finali)
        value_groups = {group["key"]: group for group in sheet["valueGroups"]}
        self.assertIn("load_capacity", value_groups)
        self.assertIn("magic_conversions", value_groups)
        self.assertIn("roll_modifiers", value_groups)
        self.assertIn("malus_carico", {value["key"] for value in value_groups["load_capacity"]["values"]})
        self.assertIn("sifone_di_mana", {value["key"] for value in value_groups["magic_conversions"]["values"]})
        self.assertEqual(sheet["reagents"]["slotMax"], 15)
        self.assertEqual(sheet["reagents"]["occupied"], 3)
        self.assertEqual(sheet["reagents"]["remaining"], 12)
        self.assertEqual(sheet["utilityContainer"]["capacity"], 15)
        self.assertEqual(sheet["utilityContainer"]["occupied"], 3)
        self.assertTrue(sheet["utilityContainer"]["weightless"])
        self.assertTrue(sheet["campaignContainer"]["available"])
        self.assertTrue(sheet["campaignContainer"]["shared"])
        self.assertFalse(sheet["permissions"]["canShowLockedSlots"])
        self.assertIn("Blu · livello 1", {row["label"] for row in sheet["reagents"]["ingredientRows"]})
        self.assertTrue(sheet["reagents"]["multiplierRows"])
        multiplier_values = {row["key"]: row["value"] for row in sheet["reagents"]["multiplierRows"]}
        self.assertEqual(multiplier_values["moltiplicatore_reagenti_livello_3"], 2.2)
        self.assertEqual(multiplier_values["moltiplicatore_reagenti_rossi"], 0)
        adjusted_stats = {"pf", "mana", "energia", "potere", "pa", "attacco", "difesa"}
        for stat in [*sheet["characteristics"], *sheet["combat"], *sheet["resistances"], *value_groups["load_capacity"]["values"]]:
            expected_keys = ["base", "items", "effects"]
            if stat["key"] in adjusted_stats:
                expected_keys.extend(("stanchezza", "modificatore_generale"))
            self.assertEqual([part["key"] for part in stat["calculation"]], expected_keys)
            self.assertAlmostEqual(sum(part["value"] for part in stat["calculation"]), stat["value"])
        for resource in sheet["resources"]:
            self.assertEqual(
                [part["key"] for part in resource["calculation"]],
                ["base", "items", "effects", "stanchezza", "modificatore_generale"],
            )
            self.assertAlmostEqual(sum(part["value"] for part in resource["calculation"]), resource["maximum"])
        self.assertEqual(
            set(sheet["encumbrance"]),
            {
                "equipmentRaw",
                "equipment",
                "equipmentDiscountPercent",
                "backpack",
                "magicalWeightIgnored",
                "quiver",
                "total",
                "loadStep",
                "penalty",
            },
        )

    def test_player_can_update_carried_and_shared_coins_through_typed_actions(self):
        carried = self.command(
            "character.updateCoins",
            {
                "characterId": self.character.id,
                "coins": 0,
                "expectedCoins": self.character.monete,
                "transferOverflow": False,
            },
        )
        self.assertEqual(carried.status_code, 200)
        carried_sheet = carried.json()["data"]["character"]
        self.assertEqual(carried_sheet["coins"], 0)
        self.assertEqual(carried_sheet["coinStorage"]["requiredSlots"], 0)

        self.character.campagna.refresh_from_db()
        shared = self.command(
            "campaign.updateSharedCoins",
            {
                "characterId": self.character.id,
                "coins": 4_321,
                "expectedCoins": self.character.campagna.monete_condivise,
            },
        )
        self.assertEqual(shared.status_code, 200)
        shared_sheet = shared.json()["data"]["character"]
        self.assertEqual(shared_sheet["coinStorage"]["sharedCoins"], 4_321)
        self.assertEqual(shared_sheet["campaignContainer"]["occupied"], carried_sheet["campaignContainer"]["occupied"])

    def test_sheet_and_stack_updates_do_not_recalculate_owned_skill_cards(self):
        family = FamigliaSkill.objects.first()
        skills = [
            Skill.objects.create(
                nome=f"Sheet performance {index}",
                slug=f"sheet-performance-{index}",
                numero=900000 + index,
                famiglia=family,
            )
            for index in range(30)
        ]
        SkillPersonaggio.objects.bulk_create(
            [
                SkillPersonaggio(personaggio=self.character, skill=skill)
                for skill in skills
            ]
        )

        with CaptureQueriesContext(connection) as sheet_queries:
            response = self.client.get(
                f"/api/v1/characters/{self.character.id}/sheet"
            )

        self.assertEqual(response.status_code, 200)
        self.assertLess(len(sheet_queries), 60)
        self.assertEqual(response.json()["data"]["character"]["skills"], [])

        with CaptureQueriesContext(connection) as quantity_queries:
            quantity_response = self.command(
                "inventory.setQuantity",
                {
                    "characterId": self.character.id,
                    "target": {"group": "utility", "slot": "1"},
                    "quantity": 2,
                },
            )

        self.assertEqual(quantity_response.status_code, 200)
        self.assertLess(len(quantity_queries), 70)
        self.assertEqual(
            quantity_response.json()["data"]["character"]["skills"],
            [],
        )

    def test_weightless_personal_and_shared_containers_support_stacks(self):
        initial_sheet = self.client.get(
            f"/api/v1/characters/{self.character.id}/sheet"
        ).json()["data"]["character"]
        initial_weight = initial_sheet["encumbrance"]["total"]
        # Le monete sono il primo oggetto del catalogo ma sono gestite dal sistema: un
        # inserimento manuale viene giustamente rifiutato, quindi qui serve un oggetto normale.
        item = next(
            candidate
            for candidate in Oggetto.objects.filter(archiviato=False, archived_at__isnull=True)[:20]
            if not (candidate.metadata if isinstance(candidate.metadata, dict) else {}).get("systemManaged")
        )

        personal_response = self.command("inventory.assignItem", {
            "characterId": self.character.id,
            "target": {"group": "utility", "slot": "4"},
            "itemId": item.id,
            "quantity": 5,
        })
        self.assertEqual(personal_response.status_code, 200)
        personal_sheet = personal_response.json()["data"]["character"]
        personal_slot = personal_sheet["utilityContainer"]["slots"][3]
        self.assertEqual(personal_slot["item"]["id"], item.id)
        self.assertEqual(personal_slot["quantity"], 5)
        self.assertEqual(personal_sheet["encumbrance"]["total"], initial_weight)

        quantity_response = self.command("inventory.setQuantity", {
            "characterId": self.character.id,
            "target": {"group": "utility", "slot": "4"},
            "quantity": 7,
        })
        self.assertEqual(quantity_response.status_code, 200)
        self.assertEqual(
            quantity_response.json()["data"]["character"]["utilityContainer"]["slots"][3]["quantity"],
            7,
        )

        reagent_response = self.command("inventory.assignItem", {
            "characterId": self.character.id,
            "target": {"group": "utility", "slot": "5"},
            "stockKey": "r3",
            "quantity": 3,
        })
        self.assertEqual(reagent_response.status_code, 200)
        reagent_slot = reagent_response.json()["data"]["character"]["utilityContainer"]["slots"][4]
        self.assertEqual(reagent_slot["quantity"], 3)
        self.assertEqual(reagent_slot["item"]["metadata"]["storageStockKey"], "r3")
        container = self.character.contenitori_inventario.get(scope="personal")
        self.assertEqual(
            container.voci.get(reagent_stock_key="r3").quantita,
            3,
        )

        shared_response = self.command("inventory.assignItem", {
            "characterId": self.character.id,
            "target": {"group": "campaign", "slot": "1"},
            "itemId": item.id,
            "quantity": 2,
        })
        self.assertEqual(shared_response.status_code, 200)
        other = Personaggio.objects.filter(
            campagna=self.character.campagna,
        ).exclude(pk=self.character.pk).first()
        other_sheet = self.client.get(
            f"/api/v1/characters/{other.id}/sheet"
        ).json()["data"]["character"]
        self.assertEqual(other_sheet["campaignContainer"]["slots"][0]["item"]["id"], item.id)
        self.assertEqual(other_sheet["campaignContainer"]["slots"][0]["quantity"], 2)

    def test_no_role_can_reveal_locked_character_slots(self):
        self.giocatore.role = Giocatore.ROLE_USER
        self.giocatore.save(update_fields=["role", "updated_at"])
        player_sheet = self.client.get(
            f"/api/v1/characters/{self.character.id}/sheet"
        ).json()["data"]["character"]
        self.assertFalse(player_sheet["permissions"]["canShowLockedSlots"])
        self.assertFalse(player_sheet["permissions"]["canManageItems"])

    def test_combat_button_actions_return_the_updated_character_configuration(self):
        created = self.command("combatButtons.create", {
            "characterId": self.character.id,
            "values": {
                "name": "Affondo API",
                "helpText": "Usalo sul prossimo attacco.",
                "modifiers": {"attackBonus": 2, "damageBonus": 1, "damageTierBonus": 0, "penetrationFlat": 0, "penetrationPercent": 0},
                "public": True,
                "active": True,
                "keepActiveInCombat": False,
            },
        })

        self.assertEqual(created.status_code, 200)
        buttons = created.json()["data"]["skills"]["combatButtons"]["own"]
        created_button = next(button for button in buttons if button["name"] == "Affondo API")
        self.assertTrue(created_button["public"])

        updated = self.command("combatButtons.update", {
            "characterId": self.character.id,
            "buttonId": created_button["id"],
            "values": {
                "name": "Affondo API persistente",
                "helpText": "Resta acceso.",
                "modifiers": {"attackBonus": 3, "damageBonus": 0, "damageTierBonus": 1, "penetrationFlat": 0, "penetrationPercent": 0},
                "public": False,
                "active": True,
                "keepActiveInCombat": True,
            },
        })
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.json()["data"]["skills"]["combatButtons"]["own"][0]["keepActiveInCombat"])

        deleted = self.command("combatButtons.delete", {
            "characterId": self.character.id,
            "buttonId": created_button["id"],
        })
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(BottoneCombat.objects.filter(pk=created_button["id"]).exists())

    def test_ring_earring_and_sack_slots_after_character_limits_are_locked(self):
        totals = dict(self.character.tot or {})
        totals.update({"anelli_max": 3, "orecchini_max": 2, "sacchi_max": 1})
        self.character.tot = totals
        self.character.save(update_fields=["tot", "updated_at"])

        response = self.client.get(f"/api/v1/characters/{self.character.id}/sheet")

        self.assertEqual(response.status_code, 200)
        slots = {slot["slot"]: slot for slot in response.json()["data"]["character"]["equipment"]["slots"]}
        self.assertFalse(slots["anello_3"]["isLocked"])
        self.assertTrue(slots["anello_4"]["isLocked"])
        self.assertFalse(slots["orecchino_2"]["isLocked"])
        self.assertTrue(slots["orecchino_3"]["isLocked"])
        self.assertFalse(slots["sacco_1"]["isLocked"])
        self.assertTrue(slots["sacco_2"]["isLocked"])

        ring = Oggetto.objects.create(nome="Anello oltre il limite", tipo_1="anello")
        rejected = self.command(
            "inventory.assignItem",
            {
                "characterId": self.character.id,
                "target": {"group": "equipment", "slot": "anello_4"},
                "itemId": ring.id,
            },
        )
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(rejected.json()["errors"][0]["code"], "inventory.slot_locked")

    def test_equipping_armor_refreshes_the_portrait_key_without_a_reload(self):
        livia = Personaggio.objects.get(nome_interno="poc_livia_occhiodoro")
        response = self.command("inventory.assignItem", {
            "characterId": self.character.id,
            "target": {"group": "equipment", "slot": "armatura"},
            "itemId": livia.equip.armatura_id,
        })

        self.assertEqual(response.status_code, 200)
        appearance = response.json()["data"]["character"]["appearance"]
        self.assertEqual(appearance["armorKey"], "cuoio")
        self.assertEqual(appearance["preferredFilename"], "darion_cuoio.webp")

    def test_replacing_an_equipped_item_moves_the_previous_item_to_an_unlocked_backpack_slot(self):
        previous = Oggetto.objects.create(nome="Armatura precedente test", tipo_1="armatura")
        replacement = Oggetto.objects.create(nome="Armatura nuova test", tipo_1="armatura")
        self.character.equip.armatura = previous
        self.character.equip.save(update_fields=["armatura", "updated_at"])
        for index in range(1, 51):
            setattr(self.character.zaino, f"slot_{index}", None)
        self.character.zaino.save()

        response = self.command("inventory.assignItem", {
            "characterId": self.character.id,
            "target": {"group": "equipment", "slot": "armatura"},
            "itemId": replacement.id,
        })

        self.assertEqual(response.status_code, 200)
        self.character.equip.refresh_from_db()
        self.character.zaino.refresh_from_db()
        self.assertEqual(self.character.equip.armatura_id, replacement.id)
        self.assertEqual(self.character.zaino.slot_1_id, previous.id)
        self.assertIn("spazio 1 dello zaino", response.json()["events"][0]["message"])

    def test_replacing_an_equipped_item_uses_a_locked_backpack_slot_when_unlocked_slots_are_full(self):
        previous = Oggetto.objects.create(nome="Armatura precedente overflow", tipo_1="armatura")
        replacement = Oggetto.objects.create(nome="Armatura nuova overflow", tipo_1="armatura")
        filler = Oggetto.objects.create(nome="Riempitivo zaino overflow")
        self.character.equip.armatura = previous
        self.character.equip.save(update_fields=["armatura", "updated_at"])
        capacity = self.client.get(f"/api/v1/characters/{self.character.id}/sheet").json()["data"]["character"]["inventory"]["capacity"]
        for index in range(1, 51):
            setattr(self.character.zaino, f"slot_{index}", filler if index <= capacity else None)
        self.character.zaino.save()

        response = self.command("inventory.assignItem", {
            "characterId": self.character.id,
            "target": {"group": "equipment", "slot": "armatura"},
            "itemId": replacement.id,
        })

        self.assertEqual(response.status_code, 200)
        self.character.zaino.refresh_from_db()
        self.assertEqual(getattr(self.character.zaino, f"slot_{capacity + 1}_id"), previous.id)
        returned_slot = response.json()["data"]["character"]["inventory"]["slots"][capacity]
        self.assertTrue(returned_slot["isLocked"])
        self.assertEqual(returned_slot["item"]["id"], previous.id)
        self.assertIn(f"spazio bloccato {capacity + 1}", response.json()["events"][0]["message"])

    def test_replacing_an_equipped_item_reports_loss_only_when_all_backpack_slots_are_full(self):
        previous = Oggetto.objects.create(nome="Armatura precedente persa", tipo_1="armatura")
        replacement = Oggetto.objects.create(nome="Armatura nuova pieno", tipo_1="armatura")
        filler = Oggetto.objects.create(nome="Riempitivo zaino pieno")
        self.character.equip.armatura = previous
        self.character.equip.save(update_fields=["armatura", "updated_at"])
        for index in range(1, 51):
            setattr(self.character.zaino, f"slot_{index}", filler)
        self.character.zaino.save()

        response = self.command("inventory.assignItem", {
            "characterId": self.character.id,
            "target": {"group": "equipment", "slot": "armatura"},
            "itemId": replacement.id,
        })

        self.assertEqual(response.status_code, 200)
        self.character.equip.refresh_from_db()
        self.character.zaino.refresh_from_db()
        self.assertEqual(self.character.equip.armatura_id, replacement.id)
        self.assertNotIn(previous.id, [getattr(self.character.zaino, f"slot_{index}_id") for index in range(1, 51)])
        self.assertEqual(response.json()["warnings"][0]["code"], "inventory.displaced_item_lost")
        self.assertIn("è stato perso", response.json()["warnings"][0]["message"])

    def test_invalid_ring_to_weapon_swap_is_atomic_and_friendly(self):
        livia = Personaggio.objects.get(nome_interno="poc_livia_occhiodoro")
        original_weapon = livia.equip.arma_id
        original_ring = livia.equip.anello_1_id

        response = self.command("inventory.swapItems", {
            "characterId": livia.id,
            "source": {"group": "equipment", "slot": "anello_1"},
            "target": {"group": "equipment", "slot": "arma"},
        })

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["errors"][0]["code"], "inventory.incompatible_slot")
        self.assertIn("slot Arma", response.json()["errors"][0]["message"])
        livia.equip.refresh_from_db()
        self.assertEqual(livia.equip.arma_id, original_weapon)
        self.assertEqual(livia.equip.anello_1_id, original_ring)

    def test_direct_assignment_rejects_an_item_incompatible_with_the_equipment_slot(self):
        potion = Oggetto.objects.get(nome="Pozione di cura minore")
        original_armor = self.character.equip.armatura_id

        response = self.command("inventory.assignItem", {
            "characterId": self.character.id,
            "target": {"group": "equipment", "slot": "armatura"},
            "itemId": potion.id,
        })

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["errors"][0]["code"], "inventory.incompatible_slot")
        self.assertIn("slot Armatura", response.json()["errors"][0]["message"])
        self.character.equip.refresh_from_db()
        self.assertEqual(self.character.equip.armatura_id, original_armor)

    def test_extra_equipment_slot_accepts_any_item_and_saves_immediately(self):
        source_item = self.character.zaino.slot_1
        response = self.command("inventory.swapItems", {
            "characterId": self.character.id,
            "source": {"group": "backpack", "slot": "1"},
            "target": {"group": "equipment", "slot": "extra_slot_1"},
        })
        self.assertEqual(response.status_code, 200)
        self.character.equip.refresh_from_db()
        self.character.zaino.refresh_from_db()
        self.assertEqual(self.character.equip.extra_slot_1_id, source_item.id)
        backpack_items = [getattr(self.character.zaino, f"slot_{index}") for index in range(1, 51)]
        occupied_items = [item for item in backpack_items if item is not None]
        self.assertNotIn(source_item.id, [item.id for item in occupied_items])
        self.assertTrue(all(item is not None for item in backpack_items[: len(occupied_items)]))
        self.assertEqual(
            [item.peso or 0 for item in occupied_items],
            sorted((item.peso or 0 for item in occupied_items), reverse=True),
        )

    def test_backpack_and_quiver_assignments_sort_every_item_by_descending_weight(self):
        backpack_items = [
            Oggetto.objects.create(nome=f"Peso zaino {weight}", peso=weight)
            for weight in (1, 9, 3, 7, 2)
        ]
        for index in range(1, 51):
            setattr(self.character.zaino, f"slot_{index}", None)
        for index, item in enumerate(backpack_items[:-1], start=1):
            setattr(self.character.zaino, f"slot_{index}", item)
        self.character.zaino.save()

        backpack_response = self.command("inventory.assignItem", {
            "characterId": self.character.id,
            "target": {"group": "backpack", "slot": "12"},
            "itemId": backpack_items[-1].id,
        })

        self.assertEqual(backpack_response.status_code, 200)
        self.character.zaino.refresh_from_db()
        ordered_backpack = [getattr(self.character.zaino, f"slot_{index}") for index in range(1, 6)]
        self.assertEqual([item.peso for item in ordered_backpack], [9, 7, 3, 2, 1])
        self.assertTrue(all(getattr(self.character.zaino, f"slot_{index}") is None for index in range(6, 51)))

        sheet = backpack_response.json()["data"]["character"]
        magical_slots = sheet["inventory"]["magicalSlots"]
        self.assertGreater(magical_slots, 0)
        self.assertTrue(all(slot["isMagical"] for slot in sheet["inventory"]["slots"][:magical_slots]))
        self.assertFalse(sheet["inventory"]["slots"][magical_slots]["isMagical"])
        expected_ignored_weight = sum((item.peso or 0) for item in ordered_backpack[:magical_slots])
        self.assertEqual(sheet["encumbrance"]["magicalWeightIgnored"], expected_ignored_weight)

        quiver_items = [
            Oggetto.objects.create(nome=f"Peso faretra {weight}", tipo_1="freccia", peso=weight)
            for weight in (0.25, 4, 1.5)
        ]
        for index in range(1, 51):
            setattr(self.character.faretra, f"slot_{index}", None)
        self.character.faretra.slot_1 = quiver_items[0]
        self.character.faretra.slot_9 = quiver_items[2]
        self.character.faretra.save()

        quiver_response = self.command("inventory.assignItem", {
            "characterId": self.character.id,
            "target": {"group": "quiver", "slot": "14"},
            "itemId": quiver_items[1].id,
        })

        self.assertEqual(quiver_response.status_code, 200)
        self.character.faretra.refresh_from_db()
        ordered_quiver = [getattr(self.character.faretra, f"slot_{index}") for index in range(1, 4)]
        self.assertEqual([item.peso for item in ordered_quiver], [4, 1.5, 0.25])
        self.assertTrue(all(getattr(self.character.faretra, f"slot_{index}") is None for index in range(4, 51)))

    def test_quiver_accepts_projectiles_and_rejects_other_items(self):
        potion = Oggetto.objects.get(nome="Pozione di cura minore")
        invalid = self.command("inventory.assignItem", {
            "characterId": self.character.id,
            "target": {"group": "quiver", "slot": "3"},
            "itemId": potion.id,
        })
        self.assertEqual(invalid.status_code, 409)
        self.assertIn("non è un proiettile", invalid.json()["errors"][0]["message"])

        arrow = Oggetto.objects.get(nome="Freccia normale")
        valid = self.command("inventory.assignItem", {
            "characterId": self.character.id,
            "target": {"group": "quiver", "slot": "3"},
            "itemId": arrow.id,
        })
        self.assertEqual(valid.status_code, 200)
        self.character.faretra.refresh_from_db()
        self.assertEqual(self.character.faretra.slot_3_id, arrow.id)

    def test_equipped_quiver_cannot_be_removed_while_it_contains_projectiles(self):
        quiver_id = self.character.equip.faretra_1_id
        response = self.command("inventory.swapItems", {
            "characterId": self.character.id,
            "source": {"group": "equipment", "slot": "faretra_1"},
            "target": {"group": "backpack", "slot": "5"},
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["errors"][0]["code"], "inventory.quiver_capacity_reduced")
        self.character.equip.refresh_from_db()
        self.assertEqual(self.character.equip.faretra_1_id, quiver_id)

    def test_resource_effect_and_rest_changes_are_immediate(self):
        sheet = self.client.get(f"/api/v1/characters/{self.character.id}/sheet").json()["data"]["character"]
        maximum = next(resource["maximum"] for resource in sheet["resources"] if resource["key"] == "pf")
        response = self.command("character.updateResource", {
            "characterId": self.character.id, "resource": "pf", "current": maximum - 2,
        })
        self.assertEqual(response.status_code, 200)
        self.character.refresh_from_db()
        self.assertEqual(self.character.danno, 2)

        above_maximum = self.command("character.updateResource", {
            "characterId": self.character.id, "resource": "pf", "current": maximum + 5,
        })
        self.assertEqual(above_maximum.status_code, 200)
        self.assertEqual(
            next(resource["current"] for resource in above_maximum.json()["data"]["character"]["resources"] if resource["key"] == "pf"),
            maximum + 5,
        )

        below_zero = self.command("character.updateResource", {
            "characterId": self.character.id, "resource": "pf", "current": -3,
        })
        self.assertEqual(below_zero.status_code, 200)
        self.assertEqual(
            next(resource["current"] for resource in below_zero.json()["data"]["character"]["resources"] if resource["key"] == "pf"),
            -3,
        )

        effect_id = self.client.get(f"/api/v1/characters/{self.character.id}/sheet").json()["data"]["effectCatalog"][0]["id"]
        applied = self.command("effects.apply", {"characterId": self.character.id, "effectId": effect_id})
        self.assertEqual(applied.status_code, 200)
        active = applied.json()["data"]["character"]["effects"]
        slot = next(effect["slot"] for effect in active if effect["id"] == effect_id)
        removed = self.command("effects.remove", {"characterId": self.character.id, "slot": slot})
        self.assertEqual(removed.status_code, 200)
        self.assertNotIn(effect_id, [effect["id"] for effect in removed.json()["data"]["character"]["effects"]])

        rested = self.command("character.rest", {"characterId": self.character.id, "fatigueRecovery": 1})
        self.assertEqual(rested.status_code, 200)
        self.character.refresh_from_db()
        self.assertEqual(self.character.danno, 0)

    def test_rest_restores_energy_only_after_fatigue_is_recovered_with_capacity_left(self):
        self.character.stanchezza_accumulata = 2
        self.character.energia_spesa = 4
        self.character.save(update_fields=["stanchezza_accumulata", "energia_spesa", "updated_at"])

        exact_recovery = self.command("character.rest", {
            "characterId": self.character.id, "fatigueRecovery": 2,
        })
        self.assertEqual(exact_recovery.status_code, 200)
        self.character.refresh_from_db()
        self.assertEqual(self.character.stanchezza_accumulata, 0)
        self.assertEqual(self.character.energia_spesa, 4)

        recovery_with_capacity_left = self.command("character.rest", {
            "characterId": self.character.id, "fatigueRecovery": 1,
        })
        self.assertEqual(recovery_with_capacity_left.status_code, 200)
        self.character.refresh_from_db()
        self.assertEqual(self.character.energia_spesa, 0)

    def test_custom_effect_crud_uses_normalized_rows_and_complex_formulas(self):
        sheet_response = self.client.get(f"/api/v1/characters/{self.character.id}/sheet")
        self.assertEqual(sheet_response.status_code, 200)
        sheet_data = sheet_response.json()["data"]
        configuration = sheet_data["effectConfiguration"]
        self.assertIn("forza", {target["value"] for target in configuration["targets"]})
        self.assertIn("formula_override", {operation["value"] for operation in configuration["operations"]})
        self.assertIn("strong_set", {operation["value"] for operation in configuration["operations"]})
        self.assertGreaterEqual(len(configuration["icons"]), 70)
        self.assertTrue(all(icon["category"] and icon["keywords"] for icon in configuration["icons"]))
        rune_icon = next(icon for icon in configuration["icons"] if icon["value"] == "runa")
        self.assertEqual(rune_icon["imageUrl"], "/static/frontend/images/effects/icons/Runa%20arcana.webp")
        self.assertEqual(next(icon for icon in configuration["icons"] if icon["value"] == "fiamma")["imageUrl"], "")
        elder_icons = {
            icon["value"]: icon["imageUrl"]
            for icon in configuration["icons"]
            if icon["category"] == "Elder Django"
        }
        self.assertEqual(len(elder_icons), 78)
        self.assertEqual(elder_icons["pf_extra"], "/static/frontend/images/effects/icons/elder/pf_extra.png")
        self.assertEqual(
            next(icon for icon in configuration["icons"] if icon["value"] == "pf")["imageUrl"],
            "/static/frontend/images/effects/icons/elder/pf_extra.png",
        )
        self.assertTrue(configuration["operationOrderNote"])
        self.assertTrue(configuration["formulaGuide"])
        original_forza = next(
            stat["value"]
            for stat in sheet_data["character"]["characteristics"]
            if stat["key"] == "forza"
        )

        values = {
            "name": "Vigore della Luna",
            "description": "La luce lunare sostiene il corpo.",
            "origin": "Santuario di Azura",
            "icon": "luna",
            "temporary": True,
            "operations": [
                {
                    "target": "forza",
                    "operation": "add",
                    "value": "floor(personaggio.livello / 2) + max(1, 2)",
                    "condition": "personaggio.livello >= 1",
                }
            ],
        }
        created = self.command("effects.create", {"characterId": self.character.id, "values": values})
        self.assertEqual(created.status_code, 200)
        created_character = created.json()["data"]["character"]
        effect = next(entry for entry in created_character["effects"] if entry["name"] == values["name"])
        self.assertEqual(effect["scope"], "custom")
        self.assertTrue(effect["temporary"])
        self.assertEqual(effect["description"].count("(t)"), 1)
        self.assertEqual(effect["operations"][0]["value"], values["operations"][0]["value"])
        expected_delta = self.character.livello // 2 + 2
        updated_forza = next(
            stat["value"]
            for stat in created_character["characteristics"]
            if stat["key"] == "forza"
        )
        self.assertEqual(updated_forza, original_forza + expected_delta)

        stored = EffettoPersonalizzato.objects.get(pk=effect["id"])
        self.assertEqual(stored.personaggio_id, self.character.id)
        self.assertFalse(hasattr(stored, "tipo"))
        self.assertFalse(hasattr(stored, "created_at"))
        operation = OperazioneEffettoPersonalizzato.objects.get(effetto=stored)
        self.assertEqual(operation.bersaglio, "forza")
        self.assertEqual(operation.condizione, "personaggio.livello >= 1")

        updated_values = {
            **values,
            "description": "La luce cambia intensità. (t)",
            "operations": [{"target": "forza", "operation": "add", "value": "5", "condition": ""}],
        }
        updated = self.command("effects.update", {
            "characterId": self.character.id,
            "effectId": effect["id"],
            "values": updated_values,
        })
        self.assertEqual(updated.status_code, 200)
        updated_effect = next(entry for entry in updated.json()["data"]["character"]["effects"] if entry["id"] == effect["id"] and entry["scope"] == "custom")
        self.assertEqual(updated_effect["description"].count("(t)"), 1)
        self.assertEqual(updated_effect["operations"][0]["value"], "5")

        second_values = {
            **values,
            "name": "Secondo effetto",
            "temporary": False,
            "description": "Usato per verificare l'ordine.",
        }
        second_response = self.command(
            "effects.create",
            {"characterId": self.character.id, "values": second_values},
        )
        second_effect = next(
            entry
            for entry in second_response.json()["data"]["character"]["effects"]
            if entry["name"] == second_values["name"]
        )
        moved = self.command("effects.move", {
            "characterId": self.character.id,
            "effectId": second_effect["id"],
            "direction": "up",
        })
        custom_names = [
            entry["name"]
            for entry in moved.json()["data"]["character"]["effects"]
            if entry["scope"] == "custom"
        ]
        self.assertEqual(custom_names[:2], [second_values["name"], values["name"]])

        removed = self.command("effects.remove", {"characterId": self.character.id, "effectId": effect["id"]})
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(EffettoPersonalizzato.objects.filter(pk=effect["id"]).exists())
        self.command("effects.remove", {"characterId": self.character.id, "effectId": second_effect["id"]})

    def test_invalid_custom_effect_formula_is_rejected_without_partial_data(self):
        response = self.command("effects.create", {
            "characterId": self.character.id,
            "values": {
                "name": "Formula proibita",
                "icon": "runa",
                "temporary": False,
                "operations": [{
                    "target": "forza",
                    "operation": "add",
                    "value": "__import__('os').system('echo no')",
                    "condition": "",
                }],
            },
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["code"], "effects.formula_invalid")
        self.assertFalse(EffettoPersonalizzato.objects.filter(nome="Formula proibita").exists())

    def test_strong_set_is_final_and_visible_in_calculation_breakdown(self):
        response = self.command("effects.create", {
            "characterId": self.character.id,
            "values": {
                "name": "Vita bloccata",
                "description": "Verifica del valore terminale.",
                "icon": "pf",
                "temporary": False,
                "operations": [{
                    "target": "pf",
                    "operation": "strong_set",
                    "value": "77",
                    "condition": "",
                }],
            },
        })

        self.assertEqual(response.status_code, 200)
        resource = next(
            entry
            for entry in response.json()["data"]["character"]["resources"]
            if entry["key"] == "pf"
        )
        self.assertEqual(resource["maximum"], 77)
        strong_part = next(part for part in resource["calculation"] if part["key"] == "imposta_forte")
        self.assertEqual(strong_part["label"], "Imposta forte (valore finale bloccato)")
        self.assertAlmostEqual(sum(part["value"] for part in resource["calculation"]), 77)

    def test_editing_a_legacy_effect_promotes_only_that_active_slot(self):
        catalog_effect = self.client.get(
            f"/api/v1/characters/{self.character.id}/sheet"
        ).json()["data"]["effectCatalog"][0]
        applied = self.command("effects.apply", {
            "characterId": self.character.id,
            "effectId": catalog_effect["id"],
        })
        legacy = next(
            effect
            for effect in applied.json()["data"]["character"]["effects"]
            if effect["scope"] == "legacy" and effect["id"] == catalog_effect["id"]
        )

        promoted = self.command("effects.update", {
            "characterId": self.character.id,
            "legacySlot": legacy["slot"],
            "values": {
                "name": f"{legacy['name']} personale",
                "type": legacy["type"],
                "description": legacy["description"],
                "origin": legacy["originName"],
                "icon": "runa",
                "temporary": legacy["temporary"],
                "operations": legacy["operations"] or [
                    {"target": "forza", "operation": "add", "value": "1", "condition": ""}
                ],
            },
        })

        self.assertEqual(promoted.status_code, 200)
        active = promoted.json()["data"]["character"]["effects"]
        self.assertFalse(any(effect["scope"] == "legacy" and effect["slot"] == legacy["slot"] for effect in active))
        custom = next(effect for effect in active if effect["name"] == f"{legacy['name']} personale")
        self.assertEqual(custom["scope"], "custom")
        self.assertTrue(EffettoPersonalizzato.objects.filter(pk=custom["id"]).exists())

    def test_quick_stats_adjust_immediately_and_persist_on_the_character(self):
        sheet = self.client.get(f"/api/v1/characters/{self.character.id}/sheet").json()["data"]["character"]
        original_pf = next(resource["maximum"] for resource in sheet["resources"] if resource["key"] == "pf")
        original = {
            stat["key"]: stat["value"]
            for stat in sheet["combat"]
            if stat["key"] in {"stanchezza", "modificatore_generale"}
        }

        for stat, value in original.items():
            increased = self.command("character.adjustQuickStat", {
                "characterId": self.character.id, "stat": stat, "delta": 1,
            })
            self.assertEqual(increased.status_code, 200)
            increased_character = increased.json()["data"]["character"]
            updated = next(entry for entry in increased_character["combat"] if entry["key"] == stat)
            self.assertEqual(updated["value"], value + 1)
            updated_pf_resource = next(
                resource
                for resource in increased_character["resources"]
                if resource["key"] == "pf"
            )
            updated_pf = updated_pf_resource["maximum"]
            calculation_labels = [part["label"] for part in updated_pf_resource["calculation"]]
            self.assertTrue(any(label.startswith("Stanchezza (") for label in calculation_labels))
            self.assertTrue(any(label.startswith("Modificatore generale (") for label in calculation_labels))
            self.assertAlmostEqual(
                sum(part["value"] for part in updated_pf_resource["calculation"]),
                updated_pf,
            )
            if stat == "stanchezza":
                self.assertLess(updated_pf, original_pf)
            else:
                self.assertGreater(updated_pf, original_pf)

            restored = self.command("character.adjustQuickStat", {
                "characterId": self.character.id, "stat": stat, "delta": -1,
            })
            restored_value = next(entry for entry in restored.json()["data"]["character"]["combat"] if entry["key"] == stat)
            self.assertEqual(restored_value["value"], value)
            restored_pf = next(
                resource["maximum"]
                for resource in restored.json()["data"]["character"]["resources"]
                if resource["key"] == "pf"
            )
            self.assertEqual(restored_pf, original_pf)

    def test_pa_calculation_explains_the_elder_minimum_when_it_applies(self):
        self.character.stanchezza_accumulata = 100
        self.character.save(update_fields=["stanchezza_accumulata", "updated_at"])
        refresh_personaggio(self.character)

        sheet = self.client.get(f"/api/v1/characters/{self.character.id}/sheet").json()["data"]["character"]
        action_points = next(stat for stat in sheet["combat"] if stat["key"] == "pa")

        self.assertEqual(action_points["value"], 4)
        minimum = next(part for part in action_points["calculation"] if part["key"] == "pa_minimum")
        self.assertEqual(minimum["label"], "Limite minimo PA (4)")
        self.assertGreater(minimum["value"], 0)
        self.assertAlmostEqual(sum(part["value"] for part in action_points["calculation"]), 4)

    def test_only_master_and_admin_can_select_campaign(self):
        self.giocatore.role = Giocatore.ROLE_USER
        self.giocatore.save(update_fields=["role", "updated_at"])
        campaign_id = DatiCampagna.objects.filter(archived_at__isnull=True).values_list("id", flat=True).first()

        response = self.command("campaign.select", {"campaignId": campaign_id})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["errors"][0]["code"], "campaign.forbidden")

    def test_campaign_clock_and_weather_are_master_only_and_answer_with_the_top_bar_state(self):
        campaign = DatiCampagna.objects.filter(archived_at__isnull=True).order_by("-attiva", "nome").first()
        campaign.ora_corrente = "5"
        campaign.meteo = ""
        campaign.save(update_fields=["ora_corrente", "meteo", "updated_at"])

        response = self.command("campaign.clock.update", {"campaignId": campaign.id, "field": "ora", "direction": "increase"})

        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]
        self.assertTrue(body["weatherReminder"])
        self.assertEqual(next(entry for entry in body["campaigns"]["campaigns"] if entry["id"] == campaign.id)["currentHour"], 6)

        response = self.command("campaign.weather.reroll", {"campaignId": campaign.id})

        self.assertEqual(response.status_code, 200)
        campaign.refresh_from_db()
        self.assertIn(campaign.meteo.split(" - ")[0], {entry.label for entry in WEATHER_TABLE})

        self.giocatore.role = Giocatore.ROLE_USER
        self.giocatore.save(update_fields=["role", "updated_at"])
        for action, payload in (
            ("campaign.clock.update", {"campaignId": campaign.id, "field": "giorno", "direction": "increase"}),
            ("campaign.weather.reroll", {"campaignId": campaign.id}),
        ):
            with self.subTest(action=action):
                forbidden = self.command(action, payload)
                self.assertEqual(forbidden.status_code, 403)
                self.assertEqual(forbidden.json()["errors"][0]["code"], "campaign.forbidden")

    def test_item_authoring_is_role_gated_and_round_trips_all_core_fields(self):
        OpzioneTipoOggetto.objects.get_or_create(posizione=1, valore="dardo", defaults={"etichetta": "Dardo"})
        OpzioneTipoOggetto.objects.get_or_create(posizione=2, valore="ferro", defaults={"etichetta": "Ferro"})
        payload = {
            "nome": "Dardo di prova completo", "modello": True, "temporaneo": False,
            "archiviato": False, "tipo_1": "dardo", "tipo_2": "ferro",
            "descrizione": "Munizione bilanciata secondo la guida.", "valore": 3,
            "peso": 0.5, "rarita": 1, "lv_loot": "1-2", "regione_loot": "Skyrim",
            "peso_regione": 1.0, "pa_per_attacco": 1,
            "effetto_1": "Personaggio.attacco_extra +1", "effetto_8": "Promemoria Elder",
            "effects": [{"target": "attacco", "operation": "add", "value": 1}],
            "alchemy_profile": {}, "crafting_profile": {"material": "ferro"}, "notes": "Test completo",
        }
        created = self.command("items.create", {"values": payload})
        self.assertEqual(created.status_code, 200)
        item = created.json()["data"]["item"]
        self.assertEqual(item["name"], payload["nome"])
        self.assertTrue(item["isProjectile"])
        self.assertEqual(item["craftingProfile"]["material"], "ferro")
        self.assertEqual(item["typeValues"], ["dardo", "ferro", "", ""])
        self.assertEqual(item["elderEffects"][0], payload["effetto_1"])
        self.assertEqual(item["elderEffects"][7], payload["effetto_8"])
        self.assertEqual(item["rarityLabel"], "1")
        self.assertIn({"value": 0, "label": "Unico"}, created.json()["data"]["catalog"]["rarityChoices"])

        self.giocatore.role = Giocatore.ROLE_USER
        self.giocatore.save(update_fields=["role", "updated_at"])
        forbidden = self.command("items.update", {"itemId": item["id"], "values": {"nome": "No"}})
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json()["errors"][0]["code"], "items.forbidden")

    def test_item_authoring_rejects_unconfigured_types_and_invalid_rarity(self):
        invalid_type = self.command(
            "items.create",
            {"values": {"nome": "Oggetto con tipo libero", "tipo_1": "non-configurato"}},
        )
        self.assertEqual(invalid_type.status_code, 400)
        self.assertEqual(invalid_type.json()["errors"][0]["code"], "items.type_not_configured")

        invalid_rarity = self.command(
            "items.create",
            {"values": {"nome": "Oggetto con rarità errata", "rarita": 7}},
        )
        self.assertEqual(invalid_rarity.status_code, 400)
        self.assertEqual(invalid_rarity.json()["errors"][0]["code"], "items.rarity_invalid")

    def test_item_catalog_scopes_results_by_destination_slot_and_filters(self):
        ring = Oggetto.objects.create(nome="Anello di verifica catalogo", tipo_1="anello", rarita=2)
        Oggetto.objects.create(nome="Pozione di verifica catalogo", tipo_1="pozione", rarita=2)

        def catalog(url):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            return response.json()["data"]["items"]

        ring_slot = catalog("/api/v1/items?group=equipment&slot=anello_1&limit=200")
        self.assertIn(ring.nome, {item["name"] for item in ring_slot})
        self.assertNotIn("Pozione di verifica catalogo", {item["name"] for item in ring_slot})

        quiver = catalog("/api/v1/items?group=quiver&slot=1&limit=200")
        self.assertTrue(quiver)
        self.assertTrue(all(item["isProjectile"] for item in quiver))

        typed = catalog("/api/v1/items?type_1=pozione&limit=200")
        self.assertTrue(typed)
        self.assertEqual({item["typeValues"][0] for item in typed}, {"pozione"})

        rare_rings = catalog("/api/v1/items?type_1=anello&rarity=2&limit=200")
        self.assertIn(ring.nome, {item["name"] for item in rare_rings})
        self.assertTrue(all(item["rarity"] == 2 for item in rare_rings))

        self.assertEqual(len(catalog("/api/v1/items?group=equipment&slot=anello_1&limit=1")), 1)

        invalid_group = self.client.get("/api/v1/items?group=inesistente")
        self.assertEqual(invalid_group.status_code, 400)
        self.assertEqual(invalid_group.json()["errors"][0]["code"], "items.group_not_found")

    def test_management_character_editor_lists_orphans_and_updates_related_records(self):
        orphan = Faretra.objects.create(nome="Faretra senza proprietario")
        overview = self.client.get("/api/v1/management/characters")
        self.assertEqual(overview.status_code, 200)
        data = overview.json()["data"]
        self.assertIn(self.character.id, [entry["id"] for entry in data["characters"]])
        self.assertIn(
            ("faretra", orphan.id),
            [(entry["kind"], entry["id"]) for entry in data["orphans"]],
        )

        original_level = self.character.livello
        updated = self.command(
            "management.characters.update",
            {
                "characterId": self.character.id,
                "profile": {"livello": original_level + 1},
                "relations": {"zaino": {"nome": "Zaino rinominato dal manager"}},
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.character.refresh_from_db()
        self.character.zaino.refresh_from_db()
        self.assertEqual(self.character.livello, original_level + 1)
        self.assertEqual(self.character.zaino.nome, "Zaino rinominato dal manager")

        self.character.faretra = None
        self.character.save(update_fields=["faretra", "updated_at"])
        attached = self.command(
            "management.characters.attach",
            {"characterId": self.character.id, "kind": "faretra", "recordId": orphan.id},
        )
        self.assertEqual(attached.status_code, 200)
        self.character.refresh_from_db()
        self.assertEqual(self.character.faretra_id, orphan.id)

    def test_management_character_delete_uses_preview_and_preserves_shared_records(self):
        unique_backpack = Zaino.objects.create(nome="Zaino da eliminare")
        shared_notes = Note.objects.create(nome="Note condivise")
        target = Personaggio.objects.create(
            nome="Personaggio eliminabile",
            nome_interno="personaggio_eliminabile_test",
            zaino=unique_backpack,
            note=shared_notes,
        )
        other = Personaggio.objects.create(
            nome="Personaggio con note condivise",
            nome_interno="personaggio_note_condivise_test",
            note=shared_notes,
        )
        self.giocatore.character_ids = [*self.giocatore.character_ids, target.id, other.id]
        self.giocatore.save(update_fields=["character_ids", "updated_at"])

        detail = self.client.get(f"/api/v1/management/characters/{target.id}")
        self.assertEqual(detail.status_code, 200)
        preview = detail.json()["data"]["deletionPreview"]
        records = {entry["kind"]: entry for entry in preview["records"]}
        self.assertTrue(records["zaino"]["willDelete"])
        self.assertFalse(records["note"]["willDelete"])

        deleted = self.command(
            "management.characters.delete",
            {
                "characterId": target.id,
                "previewToken": preview["token"],
            },
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(Personaggio.objects.filter(pk=target.id).exists())
        self.assertFalse(Zaino.objects.filter(pk=unique_backpack.id).exists())
        self.assertTrue(Note.objects.filter(pk=shared_notes.id).exists())
        self.giocatore.refresh_from_db()
        self.assertNotIn(target.id, self.giocatore.character_ids)

    def test_management_tools_are_hidden_from_user_role_on_the_backend(self):
        self.giocatore.role = Giocatore.ROLE_USER
        self.giocatore.save(update_fields=["role", "updated_at"])
        response = self.client.get("/api/v1/management/characters")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["errors"][0]["code"], "management.forbidden")
        self.assertEqual(self.client.get("/api/v1/management/skills").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/management/units").status_code, 403)

    def test_unit_management_api_creates_and_previews_an_animal_without_residue(self):
        overview = self.client.get("/api/v1/management/units")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(
            {entry["value"] for entry in overview.json()["data"]["configuration"]["kinds"]},
            {"creature", "humanoid"},
        )
        configuration = overview.json()["data"]["configuration"]
        self.assertEqual(
            {entry["value"] for entry in configuration["accessoryProfiles"]},
            {"guerriero", "tank", "mago", "battlemage", "arciere", "assassino", "supporto"},
        )
        self.assertEqual(
            {entry["value"] for entry in configuration["statCurveProfiles"]},
            {"very_low", "low", "medium", "high", "very_high", "custom"},
        )
        pf_variable = next(entry for entry in configuration["statCurveVariables"] if entry["key"] == "pf")
        self.assertEqual(pf_variable["presets"]["very_low"], {"level1": 10, "level20": 50})
        self.assertEqual(pf_variable["presets"]["very_high"], {"level1": 35, "level20": 225})
        before_characters = Personaggio.objects.count()
        created = self.command(
            "management.units.save",
            {
                "values": {
                    "name": "Lupo API",
                    "category": "Animali",
                    "archetypeTags": {},
                    "competenceProfile": {},
                    "skillUnlocks": [],
                    "equipmentSlots": [],
                    "equipmentGroups": [],
                    "innateActions": [
                        {
                            "key": "morso",
                            "name": "Morso",
                            "description": "Attacco naturale.",
                            "minLevel": 1,
                            "maxLevel": 20,
                            "costs": {"pa": 2},
                        }
                    ],
                    "statProfile": {
                        "curves": [
                            {
                                "key": "pf",
                                "profile": "very_high",
                                "level1": 35,
                                "level20": 225,
                                
                            }
                        ],
                    },
                    "generation": {
                        "kind": "creature",
                    },
                }
            },
        )
        self.assertEqual(created.status_code, 200)
        unit_data = created.json()["data"]["management"]["unit"]
        unit = Unit.objects.get(pk=unit_data["id"])
        self.assertEqual(unit.generation_rules["kind"], "creature")

        detail = self.client.get(f"/api/v1/management/units/{unit.id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["data"]["name"], "Lupo API")

        preview = self.command(
            "management.units.preview",
            {"unitId": unit.id, "level": 20, "variant": "api"},
        )
        self.assertEqual(preview.status_code, 200)
        generated = preview.json()["data"]["management"]["preview"]
        self.assertEqual(generated["skills"], [])
        self.assertEqual(generated["equipment"], [])
        self.assertEqual(generated["competences"], {})
        self.assertEqual(generated["totals"]["pf"], 225)
        self.assertEqual([entry["name"] for entry in generated["innateActions"]], ["Morso"])
        self.assertEqual(Personaggio.objects.count(), before_characters)

    def test_skill_management_creates_groups_and_families_and_lists_the_full_catalog(self):
        overview = self.client.get("/api/v1/management/skills")
        self.assertEqual(overview.status_code, 200)
        self.assertGreaterEqual(overview.json()["data"]["metrics"]["activeSkills"], 0)
        self.assertTrue(overview.json()["data"]["groups"])

        group_response = self.command(
            "management.skills.group.save",
            {"values": {"name": "Tradizioni perdute", "slug": "tradizioni-perdute", "order": 80, "notes": "Test"}},
        )
        self.assertEqual(group_response.status_code, 200)
        group = GruppoFamiglieSkill.objects.get(nome="Tradizioni perdute")

        family_response = self.command(
            "management.skills.family.save",
            {
                "values": {
                    "name": "Custodi del test",
                    "groupId": group.id,
                    "order": 10,
                    "notes": "Famiglia gestita dalla SPA",
                    "additionalNotes": "",
                    "isClass": False,
                    "isReligion": False,
                    "isPerk": False,
                    "imageId": None,
                }
            },
        )
        self.assertEqual(family_response.status_code, 200)
        family = FamigliaSkill.objects.select_related("gruppo").get(nome="Custodi del test")
        self.assertEqual(family.gruppo_id, group.id)

        refreshed = self.client.get("/api/v1/management/skills").json()["data"]
        self.assertIn(group.id, [entry["id"] for entry in refreshed["groups"]])
        self.assertIn(family.id, [entry["id"] for entry in refreshed["families"]])

    def test_item_comparer_updates_only_matching_identity_and_otherwise_creates(self):
        source = Oggetto.objects.create(nome="Oggetto confronto sorgente", peso=1)
        updated = self.command(
            "items.compareSave",
            {
                "itemId": source.id,
                "identityName": source.nome,
                "values": {"nome": source.nome, "peso": 2},
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(updated.json()["data"]["management"]["created"])
        source.refresh_from_db()
        self.assertEqual(source.peso, 2)

        created = self.command(
            "items.compareSave",
            {
                "itemId": source.id,
                "identityName": source.nome,
                "values": {"nome": "Oggetto confronto copia", "peso": 3},
            },
        )
        self.assertEqual(created.status_code, 200)
        self.assertTrue(created.json()["data"]["management"]["created"])
        self.assertTrue(Oggetto.objects.filter(nome="Oggetto confronto copia", peso=3).exists())

        duplicate = self.command(
            "items.compareSave",
            {"itemId": None, "identityName": "", "values": {"nome": source.nome}},
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["errors"][0]["code"], "items.duplicate_name")

    def test_theme_has_character_workspace_tokens(self):
        theme = Theme.objects.get(slug="parchment")
        self.assertTrue(theme.health_color.startswith("#"))
        response = self.client.get("/api/settings/")
        colors = response.json()["data"]["theme"]["colors"]
        for token in ("health", "mana", "energy", "power", "validSlot", "invalidSlot"):
            self.assertIn(token, colors)

    def test_openapi_contract_lists_every_character_action(self):
        response = self.client.get("/api/v1/openapi.json")
        self.assertEqual(response.status_code, 200)
        schema_text = json.dumps(response.json())
        for action in (
            "inventory.swapItems", "inventory.assignItem", "character.updateResource",
            "character.adjustQuickStat", "character.rest", "character.updateOverview",
            "character.updateCoins", "campaign.updateSharedCoins", "effects.apply", "effects.remove",
            "items.create", "items.update", "items.archive", "items.compareSave",
            "management.characters.update", "management.characters.delete", "management.characters.attach",
        ):
            self.assertIn(action, schema_text)
        self.assertIn("CharacterAppearanceSchema", schema_text)


class UnifiedSkillsApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_minimum_data", verbosity=0)
        character = Personaggio.objects.get(nome_interno="poc_darion_frondaluna")
        action_family = FamigliaSkill.objects.get(nome="Gestione PA")
        combat_family = FamigliaSkill.objects.get(nome="Combat")
        melee_family = FamigliaSkill.objects.get(nome="Attacchi Melee")
        alchemy_family = FamigliaSkill.objects.get(nome="Alchimia")
        magic_family = FamigliaSkill.objects.get(nome="Misticismo")
        swift = Skill.objects.create(
            nome="Test - Svelto", slug="test-svelto", numero=910001,
            famiglia=action_family, costo_pe=5, tipo_pe="all",
            descrizione="+1 Punto Azione come talento passivo.",
            effetti_passivi=[{"id": "passivo-svelto", "name": "Passo fulmineo", "description": "Ottieni permanentemente +1 Punto Azione.", "icon": "pa", "operations": [{"target": "pa", "operation": "add", "value": "1", "condition": ""}]}],
        )
        defender = Skill.objects.create(
            nome="Test - Difensore", slug="test-difensore", numero=910002,
            famiglia=combat_family, costo_pe=5, tipo_pe="red",
            descrizione="+1 Difesa.",
            effetti_passivi=[{"id": "passivo-difensore", "name": "Guardia addestrata", "description": "Ottieni permanentemente +1 Difesa.", "icon": "difesa", "operations": [{"target": "difesa", "operation": "add", "value": "1", "condition": ""}]}],
            azioni_attive=[{"id": "azione-dimezza-colpo", "name": "Dimezza il colpo", "description": "Promemoria difensivo.", "trigger": "Quando vieni colpito", "duration": "Un attacco", "usageNotes": "", "costs": {"energia": 4}, "icon": "difesa"}],
        )
        defender.prerequisiti.add(swift)
        blade = Skill.objects.create(
            nome="Test - Lama precisa", slug="test-lama-precisa", numero=910003,
            famiglia=melee_family, costo_pe=6, tipo_pe="green",
            descrizione="Prepara un attacco accurato.",
            azioni_attive=[{"id": "azione-lama-precisa", "name": "Lama precisa", "description": "Promemoria di attacco.", "trigger": "Prima dell'attacco", "duration": "Un attacco", "usageNotes": "", "costs": {"pa": 1}, "icon": "attacco"}],
        )
        Skill.objects.create(
            nome="Test - Alchimia rapida", slug="test-alchimia-rapida", numero=910004,
            famiglia=alchemy_family, costo_pe=4, tipo_pe="blue", descrizione="Prepara un tonico.",
        )
        spell_skill = Skill.objects.create(
            nome="Test - Intuito arcano", slug="test-intuito-arcano", numero=910005,
            famiglia=magic_family, costo_pe=7, tipo_pe="blue", descrizione="Leggi un residuo magico.",
        )
        SpellDefinition.objects.create(
            skill=spell_skill, tier="base", range_text="Vicino", effect_unit="Intensità",
            base_mana=1, effect_per_mana=1, minimum_mana=1,
            combat_configuration={"prepared": True, "spendsResources": False},
        )
        SkillPersonaggio.objects.create(
            personaggio=character,
            skill=blade,
            spesa_pe={"general": 0, "red": 0, "green": 0, "blue": 0},
            configurazione_azioni={"azione-lama-precisa": {"enabled": True, "order": 0, "note": ""}},
        )

    def setUp(self):
        self.giocatore = Giocatore.objects.get(nome="local_master")
        self.client.force_login(self.giocatore.user)
        self.character = Personaggio.objects.get(nome_interno="poc_darion_frondaluna")
        self.giocatore.active_character = self.character
        if self.character.id not in self.giocatore.character_ids:
            self.giocatore.character_ids = [*self.giocatore.character_ids, self.character.id]
        self.giocatore.save(update_fields=["active_character", "character_ids", "updated_at"])

    def command(self, action, payload, request_id="skills-test"):
        return self.client.post(
            "/api/v1/actions",
            data=json.dumps({"action": action, "requestId": request_id, "payload": payload}),
            content_type="application/json",
        )

    def test_catalog_groups_complete_skill_cards_and_owned_reminders(self):
        response = self.client.get(f"/api/v1/skills?character_id={self.character.id}")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual([group["key"] for group in data["groups"]], [
            "Generali", "Religioni", "Scuole di Magia", "Classi", "Perk",
        ])
        self.assertEqual(len(data["families"]), 79)
        self.assertTrue(all(family["imageUrl"] for family in data["families"]))
        self.assertGreaterEqual(len(data["skills"]), 1)
        self.assertEqual(len(data["skillOptions"]), 5)
        self.assertTrue(all(option["number"] for option in data["skillOptions"]))
        self.assertFalse(data["permissions"]["canManageSkills"])
        self.assertFalse(data["permissions"]["canDeleteSkills"])
        self.assertNotIn(
            "Categoria iniziale per l'organizzazione delle abilità V2.",
            {family["notes"] for family in data["families"]},
        )
        self.assertEqual(data["activeReminders"][0]["skillName"], "Test - Lama precisa")
        self.assertEqual(data["activeReminders"][0]["enabled"], True)
        self.assertEqual(data["characterAnalysis"]["ownedSkills"], 1)

        combat_family = next(family for family in data["families"] if family["name"] == "Combat")
        combat_data = self.client.get(
            f"/api/v1/skills?character_id={self.character.id}&family_id={combat_family['id']}"
        ).json()["data"]
        self.assertEqual(combat_data["selectedGroup"], "Generali")
        hybrid = next(skill for skill in combat_data["skills"] if skill["name"] == "Test - Difensore")
        self.assertEqual(hybrid["familyGroup"], "Generali")
        self.assertEqual(len(hybrid["passiveEffects"]), 1)
        self.assertEqual(len(hybrid["activeReminders"]), 1)
        self.assertNotIn("summary", hybrid)
        self.assertNotIn("minimumLevel", hybrid)

        owned_data = self.client.get(
            f"/api/v1/skills?character_id={self.character.id}&owned_only=true"
        ).json()["data"]
        self.assertEqual([skill["name"] for skill in owned_data["skills"]], ["Test - Lama precisa"])

        search_data = self.client.get(
            f"/api/v1/skills?character_id={self.character.id}&search_mode=true&name_query=Test"
        ).json()["data"]
        self.assertSetEqual(
            {skill["name"] for skill in search_data["skills"]},
            {option["name"] for option in search_data["skillOptions"]},
        )

        card_search = self.client.get(
            f"/api/v1/skills?character_id={self.character.id}&search_mode=true&card_query=permanentemente"
        ).json()["data"]
        self.assertSetEqual(
            {skill["name"] for skill in card_search["skills"]},
            {"Test - Svelto", "Test - Difensore"},
        )

        target_search = self.client.get(
            f"/api/v1/skills?character_id={self.character.id}&search_mode=true&effect_target=pa"
        ).json()["data"]
        self.assertEqual([skill["name"] for skill in target_search["skills"]], ["Test - Svelto"])

        owned_search = self.client.get(
            f"/api/v1/skills?character_id={self.character.id}&search_mode=true&unlock_status=owned"
        ).json()["data"]
        self.assertEqual([skill["name"] for skill in owned_search["skills"]], ["Test - Lama precisa"])

    def test_manager_can_reorder_every_active_skill_in_a_family(self):
        family = FamigliaSkill.objects.get(nome="Combat")
        existing = Skill.objects.get(nome="Test - Difensore")
        added = Skill.objects.create(
            nome="Test - Guardia mobile",
            slug="test-guardia-mobile",
            numero=910006,
            famiglia=family,
            ordine_famiglia=50,
        )

        response = self.command(
            "skills.reorder",
            {"familyId": family.id, "skillIds": [added.id, existing.id]},
        )

        self.assertEqual(response.status_code, 200, response.content)
        existing.refresh_from_db()
        added.refresh_from_db()
        self.assertEqual((added.ordine_famiglia, existing.ordine_famiglia), (0, 10))

    def test_copy_with_the_same_name_is_rejected(self):
        existing = Skill.objects.get(nome="Test - Difensore")
        response = self.command(
            "skills.create",
            {
                "values": {
                    "name": existing.nome,
                    "number": 910007,
                    "familyId": existing.famiglia_id,
                    "xpType": "all",
                }
            },
        )

        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()["errors"][0]["code"], "skills.name_duplicate")

    def test_only_admin_can_delete_a_skill_and_owned_xp_is_refunded(self):
        family = FamigliaSkill.objects.get(nome="Alchimia")
        skill = Skill.objects.create(
            nome="Test - Elisir eliminabile",
            slug="test-elisir-eliminabile",
            numero=910008,
            famiglia=family,
        )
        before_general = self.character.pe_generali
        self.character.pe_generali = before_general - 2
        self.character.save(update_fields=["pe_generali", "updated_at"])
        SkillPersonaggio.objects.create(
            personaggio=self.character,
            skill=skill,
            spesa_pe={"general": 2, "red": 0, "green": 0, "blue": 0},
        )
        effect = EffettoPersonalizzato.objects.create(
            personaggio=self.character,
            nome=f"{skill.nome} · Effetto copiato",
            origine=f"Abilità: {skill.nome}",
        )

        denied = self.command(
            "skills.delete",
            {"skillId": skill.id, "confirmation": skill.nome},
        )
        self.assertEqual(denied.status_code, 403, denied.content)

        self.giocatore.role = Giocatore.ROLE_ADMIN
        self.giocatore.save(update_fields=["role", "updated_at"])
        deleted = self.command(
            "skills.delete",
            {"skillId": skill.id, "confirmation": skill.nome},
        )

        self.assertEqual(deleted.status_code, 200, deleted.content)
        self.assertFalse(Skill.objects.filter(pk=skill.id).exists())
        self.assertFalse(EffettoPersonalizzato.objects.filter(pk=effect.id).exists())
        self.character.refresh_from_db()
        self.assertEqual(self.character.pe_generali, before_general)

    def test_prerequisites_are_enforced_for_players_and_bypassed_for_staff(self):
        skill = Skill.objects.get(nome="Test - Difensore")
        master_preview = self.command(
            "skills.previewUnlock",
            {"characterId": self.character.id, "skillId": skill.id},
        ).json()["data"]["skillPreview"]
        self.assertTrue(master_preview["canConfirm"])
        self.assertTrue(master_preview["prerequisitesBypassed"])

        self.giocatore.role = Giocatore.ROLE_USER
        self.giocatore.save(update_fields=["role", "updated_at"])
        player_preview = self.command(
            "skills.previewUnlock",
            {"characterId": self.character.id, "skillId": skill.id},
        ).json()["data"]["skillPreview"]
        self.assertFalse(player_preview["canConfirm"])
        self.assertFalse(player_preview["prerequisitesBypassed"])
        self.assertIn(Skill.objects.get(nome="Test - Svelto").id, player_preview["missingPrerequisiteIds"])

        denied = self.command(
            "skills.unlock",
            {
                "characterId": self.character.id,
                "skillId": skill.id,
                "spend": {"general": 0, "red": player_preview["cost"], "green": 0, "blue": 0},
                "acceptedPassiveIds": ["passivo-difensore"],
            },
        )
        self.assertEqual(denied.status_code, 409, denied.content)
        self.assertEqual(denied.json()["errors"][0]["code"], "skills.prerequisites_missing")

    def test_gifted_skill_can_be_recorded_with_only_a_note_then_removed(self):
        skill = Skill.objects.get(nome="Test - Alchimia rapida")
        before_blue = self.character.pe_blu

        gifted = self.command(
            "skills.unlock",
            {
                "characterId": self.character.id,
                "skillId": skill.id,
                "spend": {"general": 0, "red": 0, "green": 0, "blue": 0},
                "acceptedPassiveIds": [],
                "note": "Insegnato da Master Kahar",
            },
        )
        self.assertEqual(gifted.status_code, 200, gifted.content)
        ownership = SkillPersonaggio.objects.get(personaggio=self.character, skill=skill)
        self.assertEqual(ownership.note, "Insegnato da Master Kahar")
        self.character.refresh_from_db()
        self.assertEqual(self.character.pe_blu, before_blue)

        removed = self.command(
            "skills.unlock",
            {
                "characterId": self.character.id,
                "skillId": skill.id,
                "spend": {"general": 0, "red": 0, "green": 0, "blue": 0},
                "acceptedPassiveIds": [],
                "note": "",
            },
        )
        self.assertEqual(removed.status_code, 200, removed.content)
        self.assertFalse(SkillPersonaggio.objects.filter(personaggio=self.character, skill=skill).exists())

    def test_discounted_unlock_can_be_edited_and_relocked_with_a_refund(self):
        skill = Skill.objects.get(nome="Test - Svelto")
        before_general = self.character.pe_generali
        unlocked = self.command(
            "skills.unlock",
            {
                "characterId": self.character.id,
                "skillId": skill.id,
                "spend": {"general": 1, "red": 0, "green": 0, "blue": 0},
                "acceptedPassiveIds": ["passivo-svelto"],
                "note": "Sconto concordato",
            },
        )
        self.assertEqual(unlocked.status_code, 200, unlocked.content)
        self.character.refresh_from_db()
        self.assertEqual(self.character.pe_generali, before_general - 1)
        self.assertTrue(EffettoPersonalizzato.objects.filter(personaggio=self.character, origine=f"Abilità: {skill.nome}").exists())

        relocked = self.command(
            "skills.unlock",
            {
                "characterId": self.character.id,
                "skillId": skill.id,
                "spend": {"general": 0, "red": 0, "green": 0, "blue": 0},
                "acceptedPassiveIds": [],
                "note": "",
            },
        )
        self.assertEqual(relocked.status_code, 200, relocked.content)
        self.character.refresh_from_db()
        self.assertEqual(self.character.pe_generali, before_general)
        self.assertFalse(SkillPersonaggio.objects.filter(personaggio=self.character, skill=skill).exists())
        self.assertFalse(EffettoPersonalizzato.objects.filter(personaggio=self.character, origine=f"Abilità: {skill.nome}").exists())

    def test_available_skill_and_competence_xp_can_be_edited_together(self):
        response = self.command(
            "skills.updateCharacterXp",
            {
                "characterId": self.character.id,
                "xp": {"general": 31, "red": 21, "green": 11, "blue": 7, "ability": 19},
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.character.refresh_from_db()
        self.assertEqual(
            (
                self.character.pe_generali,
                self.character.pe_rossi,
                self.character.pe_verdi,
                self.character.pe_blu,
                self.character.pe_abilita,
            ),
            (31, 21, 11, 7, 19),
        )
        self.assertEqual(response.json()["data"]["skills"]["character"]["competenceXp"], 19)

    def test_spell_preview_is_unified_and_does_not_spend_resources(self):
        skill = Skill.objects.get(nome="Test - Intuito arcano")
        before = (self.character.mana_speso, self.character.energia_spesa, self.character.potere_speso)
        response = self.command(
            "skills.previewSpell",
            {"characterId": self.character.id, "skillId": skill.id, "effect": 5, "power": 1},
        )
        self.assertEqual(response.status_code, 200, response.content)
        preview = response.json()["data"]["spellPreview"]
        self.assertFalse(preview["spendsResources"])
        self.assertFalse(preview["combatReady"])
        self.assertIn("mana", preview["resourceOptions"])
        self.assertNotIn("order", json.dumps(preview).lower())
        self.assertNotIn("chaos", json.dumps(preview).lower())
        self.character.refresh_from_db()
        self.assertEqual(
            (self.character.mana_speso, self.character.energia_spesa, self.character.potere_speso),
            before,
        )

    def test_character_actions_can_be_ordered_hidden_and_annotated(self):
        response = self.command(
            "skills.configureCharacterActions",
            {
                "characterId": self.character.id,
                "actions": [
                    {
                        "skillId": Skill.objects.get(nome="Test - Lama precisa").id,
                        "actionId": "azione-lama-precisa",
                        "enabled": False,
                        "order": 0,
                        "note": "Usare soltanto contro bersagli isolati.",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200, response.content)
        ownership = SkillPersonaggio.objects.get(
            personaggio=self.character,
            skill__nome="Test - Lama precisa",
        )
        self.assertEqual(
            ownership.configurazione_azioni["azione-lama-precisa"],
            {"enabled": False, "order": 0, "note": "Usare soltanto contro bersagli isolati."},
        )
        reminder = response.json()["data"]["skills"]["activeReminders"][0]
        self.assertFalse(reminder["enabled"])
        self.assertEqual(reminder["characterNote"], "Usare soltanto contro bersagli isolati.")

    def test_unlock_is_atomic_and_applies_accepted_passive(self):
        skill = Skill.objects.get(nome="Test - Difensore")
        before_red = self.character.pe_rossi

        preview = self.command(
            "skills.previewUnlock",
            {"characterId": self.character.id, "skillId": skill.id},
        )
        self.assertEqual(preview.status_code, 200)
        preview_data = preview.json()["data"]["skillPreview"]
        self.assertTrue(preview_data["canConfirm"])
        cost = preview_data["cost"]
        self.assertEqual(preview_data["pricing"]["baseCost"], 5)

        response = self.command(
            "skills.unlock",
            {
                "characterId": self.character.id,
                "skillId": skill.id,
                "spend": {"general": 0, "red": cost, "green": 0, "blue": 0},
                "acceptedPassiveIds": ["passivo-difensore"],
            },
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.character.refresh_from_db()
        self.assertEqual(self.character.pe_rossi, before_red - cost)
        ownership = SkillPersonaggio.objects.get(personaggio=self.character, skill=skill)
        self.assertEqual(ownership.passivi_accettati, ["passivo-difensore"])
        effect = EffettoPersonalizzato.objects.get(personaggio=self.character, origine=f"Abilità: {skill.nome}")
        operation = effect.operazioni.get()
        self.assertEqual((operation.bersaglio, operation.operazione, operation.valore), ("difesa", "add", "1"))
        reminders = response.json()["data"]["skills"]["activeReminders"]
        self.assertIn("Dimezza il colpo", {reminder["name"] for reminder in reminders})

    def test_missing_passive_acceptance_rolls_back_xp_and_ownership(self):
        skill = Skill.objects.get(nome="Test - Svelto")
        before_general = self.character.pe_generali
        preview = self.command(
            "skills.previewUnlock",
            {"characterId": self.character.id, "skillId": skill.id},
        ).json()["data"]["skillPreview"]

        response = self.command(
            "skills.unlock",
            {
                "characterId": self.character.id,
                "skillId": skill.id,
                "spend": {"general": preview["cost"], "red": 0, "green": 0, "blue": 0},
                "acceptedPassiveIds": [],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["code"], "skills.passive_acceptance_incomplete")
        self.character.refresh_from_db()
        self.assertEqual(self.character.pe_generali, before_general)
        self.assertFalse(SkillPersonaggio.objects.filter(personaggio=self.character, skill=skill).exists())
        self.assertFalse(EffettoPersonalizzato.objects.filter(personaggio=self.character, origine=f"Abilità: {skill.nome}").exists())

    def test_unlock_keeps_a_manual_effect_with_the_same_display_name(self):
        skill = Skill.objects.get(nome="Test - Svelto")
        preview = self.command(
            "skills.previewUnlock",
            {"characterId": self.character.id, "skillId": skill.id},
        ).json()["data"]["skillPreview"]
        EffettoPersonalizzato.objects.create(
            personaggio=self.character,
            nome="Test - Svelto · Passo fulmineo",
            descrizione="Promemoria manuale preesistente.",
            origine="Manuale",
            ordine=50,
        )

        response = self.command(
            "skills.unlock",
            {
                "characterId": self.character.id,
                "skillId": skill.id,
                "spend": {"general": preview["cost"], "red": 0, "green": 0, "blue": 0},
                "acceptedPassiveIds": ["passivo-svelto"],
            },
        )

        self.assertEqual(response.status_code, 200, response.content)
        generated = EffettoPersonalizzato.objects.get(
            personaggio=self.character,
            origine=f"Abilità: {skill.nome}",
        )
        self.assertNotEqual(generated.nome, "Test - Svelto · Passo fulmineo")
        self.assertIn(f"abilità {skill.pk}", generated.nome)

    def test_player_cannot_edit_skill_catalog(self):
        skill = Skill.objects.get(nome="Test - Intuito arcano")
        self.giocatore.role = Giocatore.ROLE_USER
        self.giocatore.save(update_fields=["role", "updated_at"])

        response = self.command(
            "skills.update",
            {"skillId": skill.id, "values": {}},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["errors"][0]["code"], "management.forbidden")

    def test_openapi_contract_contains_skill_actions_and_catalog(self):
        schema_text = json.dumps(self.client.get("/api/v1/openapi.json").json())
        for action in (
            "skills.previewUnlock", "skills.previewSpell", "skills.unlock", "skills.updateCharacterXp", "skills.configureCharacterActions",
            "skills.create", "skills.update", "skills.archive", "skills.reorder", "skills.delete",
        ):
            self.assertIn(action, schema_text)
        self.assertIn("SkillCatalogDataSchema", schema_text)

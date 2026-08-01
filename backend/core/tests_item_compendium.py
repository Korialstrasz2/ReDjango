from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.core.item_compendium import item_compendium_page, item_compendium_reference
from backend.core.models import Giocatore, Oggetto, OpzioneTipoOggetto, TipoArma


KATANA_POWER = "1 reroll per turno al tiro attacco o danno."


class ItemCompendiumSelectorTests(TestCase):
    """Le migrazioni seminano tipi arma e l'oggetto Monete: le asserzioni sui
    contenuti confrontano quindi la differenza rispetto al catalogo di partenza,
    non un catalogo vuoto."""

    def setUp(self):
        self.baseline = self._names()
        TipoArma.objects.update_or_create(
            nome="katana",
            defaults={
                "lunghezza": "media",
                "potenza": "precisa",
                "bonus_1": KATANA_POWER,
                "rules": {
                    "profile": {
                        "heaviness": "leggera",
                        "length": "media",
                        "power": "precisa",
                        "damageType": "taglio",
                        "combatMode": "melee",
                        "costBand": "B",
                        "handling": "one_handed",
                        "bonusNotes": [KATANA_POWER],
                    }
                },
            },
        )
        self.katana_type = TipoArma.objects.get(nome="katana")
        for position, value, label in (
            (1, "katana", "Katana"),
            (1, "pozione", "Pozione"),
            (2, "acciaio", "Acciaio"),
            (2, "cura", "Cura"),
        ):
            OpzioneTipoOggetto.objects.update_or_create(
                posizione=position, valore=value, defaults={"etichetta": label},
            )
        self.blade = Oggetto.objects.create(
            nome="Katana (acciaio)",
            tipo_1="katana",
            tipo_2="acciaio",
            descrizione="Lama sottile ripiegata molte volte.",
            valore=400,
            peso=8,
            rarita=3,
            lv_loot="4-6",
            regione_loot="Skyrim",
            pa_per_attacco=4,
            effetto_1="Personaggio.attacco_extra +5",
            effects=[{"target": "attacco", "operation": "add", "value": 5}],
        )
        self.potion = Oggetto.objects.create(
            nome="Pozione di cura",
            tipo_1="pozione",
            tipo_2="cura",
            valore=40,
            peso=1,
            rarita=1,
            lv_loot="2",
        )
        self.archived = Oggetto.objects.create(nome="Prototipo ritirato", tipo_1="pozione", archiviato=True)
        self.copy = Oggetto.objects.create(nome="Copia assegnata", tipo_1="pozione", modello=False)
        self.draft = Oggetto.objects.create(nome="Prova provvisoria", tipo_1="pozione", temporaneo=True)

    def _names(self, **filters) -> set[str]:
        return {item["name"] for item in item_compendium_page(limit=200, **filters)["items"]}

    def _added(self, **filters) -> set[str]:
        return self._names(**filters) - self.baseline

    def test_page_hides_archived_rows_character_copies_and_drafts(self):
        self.assertEqual(self._added(), {self.blade.nome, self.potion.nome})

    def test_item_carries_every_readable_field_and_no_authoring_state(self):
        item = next(entry for entry in item_compendium_page(query="Katana (acciaio)")["items"])

        self.assertEqual(item["typeValues"], ["katana", "acciaio", "", ""])
        self.assertEqual(item["value"], 400)
        self.assertEqual(item["weight"], 8)
        self.assertEqual(item["rarityLabel"], "3")
        self.assertEqual(item["lootLevel"], "4-6")
        self.assertEqual(item["lootLevels"], [4, 5, 6])
        self.assertEqual(item["region"], "Skyrim")
        self.assertEqual(item["actionPointCost"], 4)
        self.assertEqual(item["description"], "Lama sottile ripiegata molte volte.")
        self.assertEqual(item["elderEffects"], ["Personaggio.attacco_extra +5"])
        self.assertEqual(
            item["operations"],
            [{"target": "attacco", "operation": "add", "value": "5", "condition": ""}],
        )
        self.assertIn("Arma", item["equipmentSlots"])
        self.assertTrue(item["imageUrl"])
        for authoring_field in ("special", "specialReasons", "model", "temporary", "metadata", "archived"):
            self.assertNotIn(authoring_field, item)

    def test_weapon_category_is_resolved_from_the_type_when_the_relation_is_missing(self):
        """La maggior parte delle armi importate nomina la categoria solo in tipo_1."""
        self.assertIsNone(self.blade.tipo_arma_id)

        item = next(entry for entry in item_compendium_page(query="Katana (acciaio)")["items"])

        self.assertEqual(item["weaponCategory"], "katana")

    def test_weapon_category_carries_its_unique_power_and_profile(self):
        category = next(
            entry for entry in item_compendium_reference()["weaponCategories"] if entry["key"] == "katana"
        )

        self.assertEqual(category["label"], "Katana")
        self.assertEqual(category["uniquePowers"], [KATANA_POWER])
        self.assertEqual(category["combatModeLabel"], "Mischia")
        self.assertEqual(category["actionPointCost"], 4)
        self.assertEqual(category["handlingLabel"], "Una mano")
        self.assertEqual(category["costBandLabel"], "Una mano media")
        self.assertIn("Attacco +4", category["heavinessNotes"])
        self.assertFalse(category["incomplete"])

    def test_weapon_category_filter_matches_both_the_relation_and_the_type(self):
        linked = Oggetto.objects.create(nome="Katana daedrica", tipo_1="arma", tipo_arma=self.katana_type)

        self.assertEqual(self._added(weapon_category="katana"), {self.blade.nome, linked.nome})

    def test_loot_level_filter_reads_elder_bands_inclusively(self):
        self.assertEqual(self._added(loot_level=5), {self.blade.nome})
        self.assertEqual(self._added(loot_level=2), {self.potion.nome})

    def test_filters_narrow_the_catalogue(self):
        self.assertEqual(self._added(type_1="katana"), {self.blade.nome})
        self.assertEqual(self._added(type_1="katana", type_2="acciaio"), {self.blade.nome})
        self.assertEqual(self._added(rarity=3), {self.blade.nome})
        self.assertEqual(self._added(region="skyrim"), {self.blade.nome})
        self.assertEqual(self._added(value_min=100), {self.blade.nome})
        self.assertEqual(self._added(weight_max=2), {self.potion.nome})
        self.assertEqual(self._added(with_effects=True), {self.blade.nome})
        self.assertEqual(self._added(query="ripiegata"), {self.blade.nome})

    def test_sorting_orders_the_whole_catalogue(self):
        ordered = [item["name"] for item in item_compendium_page(limit=200, sort="value_desc")["items"]]

        self.assertLess(ordered.index(self.blade.nome), ordered.index(self.potion.nome))

    def test_page_reports_its_own_window(self):
        total = item_compendium_page(limit=1)["total"]
        first = item_compendium_page(limit=1)
        last = item_compendium_page(limit=1, offset=total - 1)

        self.assertEqual(total, len(self.baseline) + 2)
        self.assertEqual(first["limit"], 1)
        self.assertTrue(first["hasMore"])
        self.assertFalse(last["hasMore"])

    def test_page_size_stays_within_the_declared_ceiling(self):
        self.assertEqual(item_compendium_page(limit=10_000)["limit"], 200)
        self.assertEqual(item_compendium_page(limit=0)["limit"], 1)
        self.assertEqual(item_compendium_page(offset=-5)["offset"], 0)

    def test_reference_lists_each_filter_vocabulary_once(self):
        reference = item_compendium_reference()

        self.assertEqual(reference["regions"], sorted(set(reference["regions"])))
        self.assertIn("Skyrim", reference["regions"])
        self.assertEqual(reference["lootLevels"], sorted(set(reference["lootLevels"])))
        self.assertLessEqual({2, 4, 5, 6}, set(reference["lootLevels"]))
        self.assertEqual([group["label"] for group in reference["typeGroups"]][0], "Categoria")
        self.assertEqual(reference["subtypesByCategory"]["katana"], ["acciaio"])
        self.assertEqual(reference["subtypesByCategory"]["pozione"], ["cura"])
        self.assertTrue(all(entry["note"] for entry in reference["rarityChoices"]))
        self.assertTrue(reference["glossary"])

    def test_reference_collapses_the_numbered_equipment_slots(self):
        labels = [slot["label"] for slot in item_compendium_reference()["equipmentSlots"]]

        self.assertIn("Anello", labels)
        self.assertNotIn("Anello 1", labels)
        self.assertEqual(len(labels), len(set(labels)))


class ItemCompendiumApiTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="giocatore", password="prova-compendio")
        Giocatore.objects.create(user=user, nome="giocatore", display_name="Giocatore", role=Giocatore.ROLE_USER)
        self.user = user
        Oggetto.objects.create(nome="Pozione di prova", tipo_1="pozione", valore=40, rarita=1, lv_loot="2")

    def test_every_player_may_read_the_compendium(self):
        self.client.force_login(self.user)

        page = self.client.get("/api/v1/compendium/items?query=Pozione di prova")
        reference = self.client.get("/api/v1/compendium/items/reference")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(reference.status_code, 200)
        self.assertTrue(page.json()["ok"])
        self.assertEqual(page.json()["data"]["items"][0]["name"], "Pozione di prova")
        self.assertTrue(reference.json()["data"]["weaponCategories"])

    def test_the_compendium_still_requires_a_session(self):
        self.assertEqual(self.client.get("/api/v1/compendium/items").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/compendium/items/reference").status_code, 401)

    def test_query_parameters_reach_the_selector(self):
        self.client.force_login(self.user)

        matching = self.client.get("/api/v1/compendium/items?query=Pozione di prova&rarity=1&loot_level=2")
        missing = self.client.get("/api/v1/compendium/items?query=Pozione di prova&rarity=5")

        self.assertEqual(matching.json()["data"]["total"], 1)
        self.assertEqual(missing.json()["data"]["total"], 0)

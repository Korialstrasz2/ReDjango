from copy import deepcopy

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from backend.core.defaults import V2_SETTING_DEFAULTS
from backend.characters.models import Personaggio, Zaino
from backend.core.api import ApiError
from backend.core.models import Giocatore, Negozio, Oggetto, SettingDefinition
from backend.market.config import GENERATOR_RULES_KEY, SHOP_TYPES_KEY, get_generator_rules, get_market_locations, get_shop_type_definitions, rarity_choices, validate_generator_rules, validate_market_locations
from backend.market.generator import generate_stock, parse_loot_levels
from backend.market.selectors import _exclusion_reasons, market_overview, rollable_rarity_values
from backend.market.services import purchase, regenerate_all_shops, regenerate_shop, save_market_settings


class MarketConfigurationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for definition in V2_SETTING_DEFAULTS:
            if definition["key"].startswith("mercato."):
                SettingDefinition.objects.create(**definition, value=definition["default_value"])

    def test_locations_reject_duplicate_place_key_in_region(self):
        with self.assertRaises(ValidationError):
            validate_market_locations({"regions": [{"key": "skyrim", "label": "Skyrim", "places": [{"key": "whiterun", "label": "Whiterun"}, {"key": "whiterun", "label": "Whiterun 2"}]}]})

    def test_legacy_item_weights_are_normalized(self):
        SettingDefinition.objects.filter(key=SHOP_TYPES_KEY).update(value={"version": 1, "types": [{"key": "legacy", "label": "Legacy", "itemWeights": {"pozione": 10, "arma": 2}}]})
        category = get_shop_type_definitions()["types"][0]
        self.assertEqual(category["itemTypeRanks"]["pozione"], 0)
        self.assertGreater(category["itemTypeRanks"]["arma"], 0)

    def test_master_can_change_locations_but_not_rules(self):
        master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER)
        save_market_settings(None, master, {"locations": get_market_locations()})
        with self.assertRaisesMessage(Exception, "generatore"):
            save_market_settings(None, master, {"generatorRules": SettingDefinition.objects.get(key=GENERATOR_RULES_KEY).base_value})

    def test_quantity_scale_must_be_a_positive_multiplier(self):
        rules = deepcopy(get_generator_rules())
        rules["quantityScale"] = 0
        with self.assertRaises(ValidationError):
            validate_generator_rules(rules)

    def test_location_label_changes_update_existing_shop_projection(self):
        master = Giocatore.objects.create(nome="structure-master", role=Giocatore.ROLE_MASTER)
        shop = Negozio.objects.create(nome="Bottega", location_key="skyrim/whiterun", categoria="generale")
        locations = deepcopy(get_market_locations())
        locations["regions"][0]["label"] = "Nord"
        locations["regions"][0]["places"][0]["label"] = "Città Bianca"
        save_market_settings(None, master, {"locations": locations})
        shop.refresh_from_db()
        self.assertEqual((shop.regione_nome, shop.citta_nome), ("Nord", "Città Bianca"))

    def test_manager_configuration_lists_catalog_item_types_without_admin_rules(self):
        master = Giocatore.objects.create(nome="catalog-master", role=Giocatore.ROLE_MASTER)
        Oggetto.objects.create(nome="Categoria test", tipo_1="categoria-test", modello=True)
        configuration = market_overview(master)["configuration"]
        self.assertIn("categoria-test", configuration["itemTypes"])
        self.assertIsNone(configuration["generatorRules"])


class MarketGeneratorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for definition in V2_SETTING_DEFAULTS:
            if definition["key"].startswith("mercato."):
                SettingDefinition.objects.create(**definition, value=definition["default_value"])
        Oggetto.objects.create(nome="Pozione test", tipo_1="pozione", valore=100, rarita=1, lv_loot="1")

    def test_generation_is_deterministic_and_respects_copy_cap(self):
        category = {"key": "test", "inventoryMultiplier": 1, "itemTypeRanks": {"pozione": 0}}
        rules = {"minLevel": 1, "maxLevel": 10, "baseCount": 30, "countPerLevel": 0, "countVariance": 0, "rarityProbabilities": {"1": 1, "2": 0, "3": 0, "4": 0}, "fallbackLevelDeltas": [0], "maximumCopies": 3, "priceBasePercent": 100, "priceLevelPercent": 0, "maximumNegotiationPercent": 0}
        first = generate_stock(seed="same", category=category, level=1, region_key="skyrim", rules=rules)
        second = generate_stock(seed="same", category=category, level=1, region_key="skyrim", rules=rules)
        self.assertEqual(first.entries, second.entries)
        self.assertEqual(first.entries[0]["quantity"], 3)

    def test_default_alchemist_uses_catalog_item_and_multilevel_loot(self):
        item = Oggetto.objects.create(nome="Pozione multilevel", tipo_1="pozione", valore=100, rarita=1, lv_loot="1-4", modello=True)
        category = next(item for item in get_shop_type_definitions()["types"] if item["key"] == "alchimista")
        rules = get_generator_rules()
        generated = generate_stock(seed="alchemist", category=category, level=3, region_key="skyrim", rules=rules)
        self.assertIn(3, parse_loot_levels("1-4"))
        self.assertTrue(any(entry["itemId"] == item.id for entry in generated.entries))

    def test_variety_bias_spreads_the_stock_over_more_templates(self):
        items = [Oggetto.objects.create(nome=f"Pozione {index}", tipo_1="pozione", valore=10, rarita=1, lv_loot="1", modello=True) for index in range(12)]
        category = {"key": "test", "inventoryMultiplier": 1, "itemTypeRanks": {"pozione": 0}}
        rules = {"minLevel": 1, "maxLevel": 10, "baseCount": 24, "countPerLevel": 0, "countVariance": 0, "rarityProbabilities": {"1": 1, "2": 0, "3": 0, "4": 0, "5": 0}, "fallbackLevelDeltas": [0], "maximumCopies": 12, "priceBasePercent": 100, "priceLevelPercent": 0, "maximumNegotiationPercent": 0}
        repetitive = generate_stock(seed="variety", category=category, level=1, region_key="", rules={**rules, "varietyBias": 1}, candidates=items)
        assorted = generate_stock(seed="variety", category=category, level=1, region_key="", rules={**rules, "varietyBias": .35}, candidates=items)
        self.assertEqual(repetitive.diagnostics["fulfilledRolls"], assorted.diagnostics["fulfilledRolls"])
        self.assertGreater(assorted.diagnostics["distinctItems"], repetitive.diagnostics["distinctItems"])

    def test_level_spread_stocks_neighbouring_grades_at_a_discount(self):
        exact = Oggetto.objects.create(nome="Pozione di grado", tipo_1="pozione", valore=10, rarita=1, lv_loot="4", modello=True)
        neighbour = Oggetto.objects.create(nome="Pozione vicina", tipo_1="pozione", valore=10, rarita=1, lv_loot="5", modello=True)
        category = {"key": "test", "inventoryMultiplier": 1, "itemTypeRanks": {"pozione": 0}}
        rules = {"minLevel": 1, "maxLevel": 10, "baseCount": 20, "countPerLevel": 0, "countVariance": 0, "rarityProbabilities": {"1": 1, "2": 0, "3": 0, "4": 0, "5": 0}, "fallbackLevelDeltas": [0, -1, 1], "maximumCopies": 20, "priceBasePercent": 100, "priceLevelPercent": 0, "maximumNegotiationPercent": 0}
        narrow = generate_stock(seed="spread", category=category, level=4, region_key="", rules={**rules, "levelSpread": 0}, candidates=[exact, neighbour])
        wide = generate_stock(seed="spread", category=category, level=4, region_key="", rules={**rules, "levelSpread": 1, "levelSpreadWeight": .5}, candidates=[exact, neighbour])
        self.assertEqual([entry["itemId"] for entry in narrow.entries], [exact.id])
        stocked = {entry["itemId"]: entry["quantity"] for entry in wide.entries}
        self.assertEqual(sorted(stocked), sorted([exact.id, neighbour.id]))
        self.assertGreater(stocked[exact.id], stocked[neighbour.id])

    def test_variety_bias_of_zero_stocks_each_template_once(self):
        items = [Oggetto.objects.create(nome=f"Reagente {index}", tipo_1="pozione", valore=10, rarita=1, lv_loot="1", modello=True) for index in range(4)]
        category = {"key": "test", "inventoryMultiplier": 1, "itemTypeRanks": {"pozione": 0}}
        rules = {"minLevel": 1, "maxLevel": 10, "baseCount": 20, "countPerLevel": 0, "countVariance": 0, "varietyBias": 0, "rarityProbabilities": {"1": 1, "2": 0, "3": 0, "4": 0, "5": 0}, "fallbackLevelDeltas": [0], "maximumCopies": 5, "priceBasePercent": 100, "priceLevelPercent": 0, "maximumNegotiationPercent": 0}
        generated = generate_stock(seed="unique", category=category, level=1, region_key="", rules=rules, candidates=items)
        self.assertEqual([entry["quantity"] for entry in generated.entries], [1] * len(items))
        self.assertEqual(generated.diagnostics["missingByItemType"]["eligible"], 20 - len(items))

    def test_unservable_rarity_slides_to_the_nearest_one_instead_of_losing_the_roll(self):
        item = Oggetto.objects.create(nome="Pozione comune", tipo_1="pozione", valore=10, rarita=1, lv_loot="1", modello=True)
        category = {"key": "test", "inventoryMultiplier": 1, "itemTypeRanks": {"pozione": 0}}
        rules = {"minLevel": 1, "maxLevel": 10, "baseCount": 10, "countPerLevel": 0, "countVariance": 0, "rarityProbabilities": {"1": .5, "2": .5, "3": 0, "4": 0, "5": 0}, "fallbackLevelDeltas": [0], "maximumCopies": 10, "priceBasePercent": 100, "priceLevelPercent": 0, "maximumNegotiationPercent": 0}
        generated = generate_stock(seed="slide", category=category, level=1, region_key="", rules=rules, candidates=[item])
        self.assertEqual(generated.diagnostics["fulfilledRolls"], generated.diagnostics["requestedRolls"])
        self.assertGreater(generated.diagnostics["raritySubstitutions"], 0)
        self.assertEqual(generated.diagnostics["missingByItemType"], {})

    def test_quantity_scale_multiplies_the_generated_count(self):
        item = Oggetto.objects.create(nome="Pozione scala", tipo_1="pozione", valore=100, rarita=1, lv_loot="1", modello=True)
        category = {"key": "test", "inventoryMultiplier": 1, "itemTypeRanks": {"pozione": 0}}
        rules = {"minLevel": 1, "maxLevel": 10, "baseCount": 4, "countPerLevel": 0, "countVariance": 0, "quantityScale": .5, "rarityProbabilities": {"1": 1, "2": 0, "3": 0, "4": 0, "5": 0}, "fallbackLevelDeltas": [0], "maximumCopies": 10, "priceBasePercent": 100, "priceLevelPercent": 0, "maximumNegotiationPercent": 0}
        generated = generate_stock(seed="scale", category=category, level=1, region_key="skyrim", rules=rules, candidates=[item])
        self.assertEqual(generated.entries[0]["quantity"], 2)
        self.assertEqual(generated.entries[0]["unitPrice"], 100)


class MarketRarityCoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for definition in V2_SETTING_DEFAULTS:
            if definition["key"].startswith("mercato."):
                SettingDefinition.objects.create(**definition, value=definition["default_value"])

    def test_every_catalogue_rarity_except_unico_can_be_configured(self):
        expected = [str(value) for value in Oggetto.Rarita.values if value != Oggetto.Rarita.UNICO]
        self.assertEqual([choice["value"] for choice in rarity_choices()], expected)
        self.assertEqual(sorted(get_generator_rules()["rarityProbabilities"], key=int), expected)

    def test_rarity_five_item_is_generated_when_the_rules_ask_for_it(self):
        item = Oggetto.objects.create(nome="Reliquia", tipo_1="pozione", valore=100, rarita=5, lv_loot="1", modello=True)
        category = {"key": "test", "inventoryMultiplier": 1, "itemTypeRanks": {"pozione": 0}}
        rules = {**get_generator_rules(), "rarityProbabilities": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 1}}
        generated = generate_stock(seed="rarity5", category=category, level=1, region_key="", rules=rules, candidates=[item])
        self.assertTrue(any(entry["itemId"] == item.id for entry in generated.entries))

    def test_item_without_rarity_is_skipped_instead_of_counting_as_common(self):
        item = Oggetto.objects.create(nome="Senza rarità", tipo_1="pozione", valore=100, rarita=None, lv_loot="1", modello=True)
        category = {"key": "test", "inventoryMultiplier": 1, "itemTypeRanks": {"pozione": 0}}
        rules = {**get_generator_rules(), "rarityProbabilities": {"1": 1, "2": 0, "3": 0, "4": 0, "5": 0}}
        generated = generate_stock(seed="norarity", category=category, level=1, region_key="", rules=rules, candidates=[item])
        self.assertEqual(generated.entries, [])
        self.assertIn("missingRarity", _exclusion_reasons(item, {"pozione"}, rollable_rarity_values()))

    def test_rarity_without_probability_is_reported_as_excluded(self):
        rules = deepcopy(get_generator_rules())
        share = rules["rarityProbabilities"].pop("5")
        rules["rarityProbabilities"]["1"] = round(rules["rarityProbabilities"]["1"] + share, 4)
        SettingDefinition.objects.filter(key=GENERATOR_RULES_KEY).update(value=rules)
        item = Oggetto.objects.create(nome="Irraggiungibile", tipo_1="pozione", valore=10, rarita=5, lv_loot="1", modello=True)
        self.assertNotIn(5, rollable_rarity_values())
        self.assertIn("unreachableRarity", _exclusion_reasons(item, {"pozione"}, rollable_rarity_values()))


class MarketFullRegenerationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for definition in V2_SETTING_DEFAULTS:
            if definition["key"].startswith("mercato."):
                SettingDefinition.objects.create(**definition, value=definition["default_value"])
        cls.admin = Giocatore.objects.create(nome="market-admin", role=Giocatore.ROLE_ADMIN)
        cls.master = Giocatore.objects.create(nome="market-master", role=Giocatore.ROLE_MASTER)
        Oggetto.objects.create(nome="Pozione per ricreazione", tipo_1="pozione", valore=20, rarita=1, lv_loot="1")
        cls.active_shop = Negozio.objects.create(nome="Alchimista attivo", location_key="skyrim/whiterun", categoria="alchimista", livello=1)
        cls.archived_shop = Negozio.objects.create(nome="Alchimista archiviato", location_key="skyrim/whiterun", categoria="alchimista", livello=1, archived_at=timezone.now())

    def test_admin_regenerates_every_active_shop_and_skips_archived(self):
        result = regenerate_all_shops(None, self.admin)
        self.active_shop.refresh_from_db()
        self.archived_shop.refresh_from_db()
        self.assertEqual(result["shopCount"], 1)
        self.assertGreater(result["requestedRolls"], 0)
        self.assertEqual(self.active_shop.stock_revision, 1)
        self.assertTrue(self.active_shop.lista_oggetti["entries"])
        self.assertEqual(self.archived_shop.stock_revision, 0)
        self.assertEqual(self.archived_shop.lista_oggetti, [])

    def test_full_regeneration_is_admin_only(self):
        with self.assertRaises(ApiError) as caught:
            regenerate_all_shops(None, self.master)
        self.assertEqual(caught.exception.code, "market.regenerate_all_admin_only")


class MarketRestockTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for definition in V2_SETTING_DEFAULTS:
            if definition["key"].startswith("mercato."):
                SettingDefinition.objects.create(**definition, value=definition["default_value"])
        cls.master = Giocatore.objects.create(nome="restock-master", role=Giocatore.ROLE_MASTER)
        for index in range(24):
            Oggetto.objects.create(nome=f"Pozione {index}", tipo_1="pozione", valore=10 + index, rarita=1, lv_loot="1", modello=True)
        cls.shop = Negozio.objects.create(nome="Bottega da rifornire", location_key="skyrim/whiterun", categoria="alchimista", livello=1)

    def _entries(self) -> list[dict]:
        self.shop.refresh_from_db()
        return self.shop.lista_oggetti["entries"]

    def test_restocking_rolls_a_new_seed_so_the_shelves_actually_change(self):
        regenerate_shop(None, self.master, self.shop.id)
        first_seed, first = self.shop.generation_seed, self._entries()
        regenerate_shop(None, self.master, self.shop.id)
        second_seed, second = self.shop.generation_seed, self._entries()
        self.assertNotEqual(first_seed, second_seed)
        self.assertNotEqual(first, second)
        self.assertEqual(self.shop.stock_revision, 2)

    def test_an_explicit_seed_still_reproduces_the_same_shelves(self):
        regenerate_shop(None, self.master, self.shop.id, "fiera-di-primavera")
        first = self._entries()
        regenerate_shop(None, self.master, self.shop.id, "fiera-di-primavera")
        self.assertEqual(self.shop.generation_seed, "fiera-di-primavera")
        self.assertEqual(self._entries(), first)



class MarketPurchaseTests(TestCase):
    def setUp(self):
        for definition in V2_SETTING_DEFAULTS:
            if definition["key"].startswith("mercato."):
                SettingDefinition.objects.create(**definition, value=definition["default_value"])
        self.item = Oggetto.objects.create(nome="Acquisto test", tipo_1="pozione", valore=30, rarita=1, lv_loot="1")
        self.shop = Negozio.objects.create(nome="Bottega test", location_key="skyrim/whiterun", categoria="generale", livello=1, stock_revision=2, lista_oggetti={"version": 2, "entries": [{"itemId": self.item.id, "quantity": 2, "unitPrice": 30, "source": "manual"}]})
        self.player = Giocatore.objects.create(nome="buyer", role=Giocatore.ROLE_USER)
        self.zaino = Zaino.objects.create(nome="Zaino test")
        self.character = Personaggio.objects.create(nome="Buyer", nome_interno="buyer-test", monete=100, zaino=self.zaino, tot={"slot_magici": 0, "slot_non_magici": 3})

    def test_purchase_moves_items_deducts_coins_and_revises_stock(self):
        shop, character, quote = purchase(None, self.player, {"shopId": self.shop.id, "characterId": self.character.id, "stockRevision": 2, "lines": [{"itemId": self.item.id, "quantity": 2}]})
        self.character.refresh_from_db(); self.zaino.refresh_from_db(); self.shop.refresh_from_db()
        self.assertEqual(quote["total"], 60)
        self.assertEqual(self.character.monete, 40)
        carried_ids = [self.zaino.slot_1_id, self.zaino.slot_2_id, self.zaino.slot_3_id]
        self.assertEqual(carried_ids.count(self.item.id), 2)
        self.assertEqual(
            carried_ids.count(Oggetto.objects.get(metadata__systemKey="currency.coins").id),
            1,
        )
        self.assertEqual(self.shop.lista_oggetti["entries"][0]["quantity"], 0)
        self.assertEqual(self.shop.stock_revision, 3)

    def test_stale_stock_rejects_without_mutating_coins_or_inventory(self):
        with self.assertRaises(ApiError) as caught:
            purchase(None, self.player, {"shopId": self.shop.id, "characterId": self.character.id, "stockRevision": 1, "lines": [{"itemId": self.item.id, "quantity": 1}]})
        self.assertEqual(caught.exception.code, "market.stale_stock")
        self.character.refresh_from_db(); self.zaino.refresh_from_db(); self.shop.refresh_from_db()
        self.assertEqual(self.character.monete, 100)
        self.assertIsNone(self.zaino.slot_1_id)
        self.assertEqual(self.shop.lista_oggetti["entries"][0]["quantity"], 2)

    def test_purchase_applies_validated_haggle_modifier(self):
        _shop, _character, quote = purchase(None, self.player, {"shopId": self.shop.id, "characterId": self.character.id, "stockRevision": 2, "lines": [{"itemId": self.item.id, "quantity": 2}], "negotiationPercent": -25})
        self.character.refresh_from_db()
        self.assertEqual(quote["baseTotal"], 60)
        self.assertEqual(quote["negotiationPercent"], -25)
        self.assertEqual(quote["total"], 45)
        self.assertEqual(self.character.monete, 55)

    def test_purchase_rejects_haggle_modifier_beyond_configured_limit(self):
        with self.assertRaises(ApiError) as caught:
            purchase(None, self.player, {"shopId": self.shop.id, "characterId": self.character.id, "stockRevision": 2, "lines": [{"itemId": self.item.id, "quantity": 1}], "negotiationPercent": -30})
        self.assertEqual(caught.exception.code, "market.negotiation_limit")
        self.character.refresh_from_db()
        self.assertEqual(self.character.monete, 100)

from copy import deepcopy

from django.core.exceptions import ValidationError
from django.test import TestCase

from backend.core.defaults import V2_SETTING_DEFAULTS
from backend.characters.models import Personaggio, Zaino
from backend.core.api import ApiError
from backend.core.models import Giocatore, Negozio, Oggetto, SettingDefinition
from backend.market.config import GENERATION_PROFILES_KEY, GENERATOR_RULES_KEY, SHOP_TYPES_KEY, get_generation_profiles, get_generator_rules, get_market_locations, get_shop_type_definitions, rarity_choices, validate_generation_profiles, validate_market_locations
from backend.market.generator import generate_stock, parse_loot_levels
from backend.market.selectors import _exclusion_reasons, market_overview, rollable_rarity_values
from backend.market.services import assign_generation_profile, preview_generation_profile, purchase, save_market_settings


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
        with self.assertRaisesMessage(Exception, "profili"):
            save_market_settings(None, master, {"generationProfiles": get_generation_profiles()})

    def test_generation_profiles_require_an_enabled_existing_default(self):
        profiles = deepcopy(get_generation_profiles())
        for profile in profiles["profiles"]:
            profile["enabled"] = profile["key"] != profiles["defaultProfileKey"]
        with self.assertRaises(ValidationError):
            validate_generation_profiles(profiles)

    def test_location_label_changes_update_existing_shop_projection(self):
        master = Giocatore.objects.create(nome="structure-master", role=Giocatore.ROLE_MASTER)
        shop = Negozio.objects.create(nome="Bottega", location_key="skyrim/whiterun", categoria="generale")
        locations = deepcopy(get_market_locations())
        locations["regions"][0]["label"] = "Nord"
        locations["regions"][0]["places"][0]["label"] = "Città Bianca"
        save_market_settings(None, master, {"locations": locations})
        shop.refresh_from_db()
        self.assertEqual((shop.regione_nome, shop.citta_nome), ("Nord", "Città Bianca"))

    def test_manager_can_assign_an_enabled_profile_to_a_shop(self):
        master = Giocatore.objects.create(nome="profile-master", role=Giocatore.ROLE_MASTER)
        shop = Negozio.objects.create(nome="Bottega", location_key="skyrim/whiterun", categoria="generale")
        assign_generation_profile(None, master, shop.id, "ricco")
        shop.refresh_from_db()
        self.assertEqual(shop.generation_profile_key, "ricco")

    def test_player_cannot_assign_a_generation_profile(self):
        player = Giocatore.objects.create(nome="profile-player", role=Giocatore.ROLE_USER)
        shop = Negozio.objects.create(nome="Bottega giocatore", location_key="skyrim/whiterun", categoria="generale")
        with self.assertRaises(ApiError):
            assign_generation_profile(None, player, shop.id, "ricco")

    def test_admin_can_update_generation_profiles(self):
        admin = Giocatore.objects.create(nome="profile-admin", role=Giocatore.ROLE_ADMIN)
        profiles = deepcopy(get_generation_profiles())
        profiles["profiles"][0]["label"] = "Povero personalizzato"
        save_market_settings(None, admin, {"generationProfiles": profiles})
        saved = SettingDefinition.objects.get(key=GENERATION_PROFILES_KEY).value
        self.assertEqual(saved["profiles"][0]["label"], "Povero personalizzato")

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

    def test_generation_profile_changes_quantity_rarity_source_and_price(self):
        item = Oggetto.objects.create(nome="Pozione profilo", tipo_1="pozione", valore=100, rarita=1, lv_loot="1", modello=True)
        category = {"key": "test", "inventoryMultiplier": 1, "itemTypeRanks": {"pozione": 0}}
        rules = {"minLevel": 1, "maxLevel": 10, "baseCount": 4, "countPerLevel": 0, "countVariance": 0, "rarityProbabilities": {"1": 0, "2": 0, "3": 0, "4": 1}, "fallbackLevelDeltas": [0], "maximumCopies": 10, "priceBasePercent": 100, "priceLevelPercent": 0, "maximumNegotiationPercent": 0}
        profile = {"key": "test-profile", "quantityMultiplier": .5, "priceMultiplier": 1.5, "rarityProbabilities": {"1": 1, "2": 0, "3": 0, "4": 0}}
        generated = generate_stock(seed="profile", category=category, level=1, region_key="skyrim", rules=rules, candidates=[item], generation_profile=profile)
        self.assertEqual(generated.entries[0]["quantity"], 2)
        self.assertEqual(generated.entries[0]["unitPrice"], 150)
        self.assertEqual(generated.diagnostics["generationProfileKey"], "test-profile")


class MarketRarityCoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for definition in V2_SETTING_DEFAULTS:
            if definition["key"].startswith("mercato."):
                SettingDefinition.objects.create(**definition, value=definition["default_value"])

    def test_every_catalogue_rarity_except_unico_can_be_configured(self):
        expected = [str(value) for value in Oggetto.Rarita.values if value != Oggetto.Rarita.UNICO]
        self.assertEqual([choice["value"] for choice in rarity_choices()], expected)
        for profile in get_generation_profiles()["profiles"]:
            self.assertEqual(sorted(profile["rarityProbabilities"], key=int), expected)

    def test_rarity_five_item_is_generated_when_the_profile_asks_for_it(self):
        item = Oggetto.objects.create(nome="Reliquia", tipo_1="pozione", valore=100, rarita=5, lv_loot="1", modello=True)
        category = {"key": "test", "inventoryMultiplier": 1, "itemTypeRanks": {"pozione": 0}}
        rules = get_generator_rules()
        profile = {"key": "leggendario", "rarityProbabilities": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 1}}
        generated = generate_stock(seed="rarity5", category=category, level=1, region_key="", rules=rules, candidates=[item], generation_profile=profile)
        self.assertTrue(any(entry["itemId"] == item.id for entry in generated.entries))

    def test_item_without_rarity_is_skipped_instead_of_counting_as_common(self):
        item = Oggetto.objects.create(nome="Senza rarità", tipo_1="pozione", valore=100, rarita=None, lv_loot="1", modello=True)
        category = {"key": "test", "inventoryMultiplier": 1, "itemTypeRanks": {"pozione": 0}}
        rules = get_generator_rules()
        profile = {"key": "comune", "rarityProbabilities": {"1": 1, "2": 0, "3": 0, "4": 0, "5": 0}}
        generated = generate_stock(seed="norarity", category=category, level=1, region_key="", rules=rules, candidates=[item], generation_profile=profile)
        self.assertEqual(generated.entries, [])
        self.assertIn("missingRarity", _exclusion_reasons(item, {"pozione"}, rollable_rarity_values()))

    def test_rarity_without_probability_anywhere_is_reported_as_excluded(self):
        profiles = deepcopy(get_generation_profiles())
        for profile in profiles["profiles"]:
            share = profile["rarityProbabilities"].pop("5")
            profile["rarityProbabilities"]["1"] = round(profile["rarityProbabilities"]["1"] + share, 4)
        SettingDefinition.objects.filter(key=GENERATION_PROFILES_KEY).update(value=profiles)
        item = Oggetto.objects.create(nome="Irraggiungibile", tipo_1="pozione", valore=10, rarita=5, lv_loot="1", modello=True)
        self.assertNotIn(5, rollable_rarity_values())
        self.assertIn("unreachableRarity", _exclusion_reasons(item, {"pozione"}, rollable_rarity_values()))

    def test_profile_preview_reports_a_requested_rarity_that_produced_nothing(self):
        Oggetto.objects.create(nome="Solo comune", tipo_1="pozione", valore=10, rarita=1, lv_loot="1", modello=True)
        preview = preview_generation_profile({"generationProfileKey": "standard", "categoryKey": "alchimista", "level": 1, "samples": 2})
        rarity_five = next(entry for entry in preview["rarities"] if entry["rarity"] == "5")
        self.assertGreater(rarity_five["configured"], 0)
        self.assertEqual(rarity_five["produced"], 0)
        self.assertGreater(rarity_five["unfulfilled"], 0)


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

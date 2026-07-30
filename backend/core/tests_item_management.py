from django.test import TestCase

from backend.characters.selectors import serialize_item
from backend.core.api import ApiError
from backend.core.item_selectors import item_catalog_payload
from backend.core.item_services import archive_item, recheck_items_special, restore_item, set_items_special, update_item
from backend.core.item_special import compute_special_reasons
from backend.core.models import Giocatore, Oggetto, TipoArma


class ItemArchiveStateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER)
        cls.player = Giocatore.objects.create(nome="player", role=Giocatore.ROLE_USER)

    def test_archiving_sets_both_archive_markers(self):
        item = Oggetto.objects.create(nome="Da archiviare", tipo_1="pozione")
        archived = archive_item(None, self.master, item.id)
        self.assertTrue(archived.archiviato)
        self.assertIsNotNone(archived.archived_at)

    def test_restoring_clears_both_archive_markers(self):
        item = Oggetto.objects.create(nome="Da ripristinare", tipo_1="pozione")
        archive_item(None, self.master, item.id)
        restored = restore_item(None, self.master, item.id)
        self.assertFalse(restored.archiviato)
        self.assertIsNone(restored.archived_at)

    def test_unticking_the_editor_checkbox_brings_the_item_back(self):
        item = Oggetto.objects.create(nome="Riattivato dall'editor", tipo_1="pozione")
        archive_item(None, self.master, item.id)
        update_item(None, self.master, item.id, {"archiviato": False})
        item.refresh_from_db()
        self.assertFalse(item.archiviato)
        self.assertIsNone(item.archived_at)
        payload = item_catalog_payload("Riattivato", limit=10)
        self.assertIn(item.id, [entry["id"] for entry in payload["items"]])

    def test_archived_item_disappears_from_the_default_catalogue(self):
        item = Oggetto.objects.create(nome="Sparisce", tipo_1="pozione")
        archive_item(None, self.master, item.id)
        payload = item_catalog_payload(limit=100)
        self.assertNotIn(item.id, [entry["id"] for entry in payload["items"]])


class ItemSpecialTriageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER)
        cls.player = Giocatore.objects.create(nome="player", role=Giocatore.ROLE_USER)

    def test_clearing_the_flag_in_batch_only_touches_the_selection(self):
        cleared = Oggetto.objects.create(nome="Ripulito", tipo_1="pozione", speciale=True)
        untouched = Oggetto.objects.create(nome="Intatto", tipo_1="pozione", speciale=True)
        updated = set_items_special(None, self.master, [cleared.id], False)
        cleared.refresh_from_db()
        untouched.refresh_from_db()
        self.assertEqual(updated, 1)
        self.assertFalse(cleared.speciale)
        self.assertTrue(untouched.speciale)

    def test_players_cannot_clear_the_flag(self):
        item = Oggetto.objects.create(nome="Protetto", tipo_1="pozione", speciale=True)
        with self.assertRaises(ApiError):
            set_items_special(None, self.player, [item.id], False)

    def test_an_empty_selection_is_refused(self):
        with self.assertRaises(ApiError):
            set_items_special(None, self.master, [], False)


class ItemSpecialReasonsTests(TestCase):
    def test_a_clean_item_has_no_reasons(self):
        item = Oggetto.objects.create(nome="A posto", tipo_1="pozione")
        self.assertEqual(compute_special_reasons(item), [])

    def test_each_reason_is_detected_independently(self):
        self.assertEqual(
            compute_special_reasons(Oggetto.objects.create(nome="Non modello", tipo_1="pozione", modello=False)),
            ["non_modello"],
        )
        self.assertEqual(
            compute_special_reasons(Oggetto.objects.create(nome="Temporaneo", tipo_1="pozione", temporaneo=True)),
            ["temporaneo"],
        )
        self.assertEqual(
            compute_special_reasons(Oggetto.objects.create(nome="Senza tipo")),
            ["tipo_1_vuoto"],
        )
        descriptive = Oggetto.objects.create(
            nome="Effetto testuale", tipo_1="pozione", effetto_1="Un effetto scritto a mano",
        )
        self.assertEqual(compute_special_reasons(descriptive), ["effetti_descrittivi"])

    def test_a_convertible_elder_effect_is_not_a_reason(self):
        item = Oggetto.objects.create(nome="Effetto convertibile", tipo_1="pozione", effetto_1="Personaggio.pf +5")
        self.assertEqual(compute_special_reasons(item), [])

    def test_multiple_reasons_stack_in_a_stable_order(self):
        item = Oggetto.objects.create(nome="Un disastro", modello=False, temporaneo=True)
        self.assertEqual(compute_special_reasons(item), ["non_modello", "temporaneo", "tipo_1_vuoto"])

    def test_serialize_item_reports_labeled_reasons(self):
        item = Oggetto.objects.create(nome="Serializzato", modello=False)
        reasons = serialize_item(item, detailed=True)["specialReasons"]
        self.assertEqual([entry["code"] for entry in reasons], ["non_modello", "tipo_1_vuoto"])
        self.assertTrue(all(entry["label"] for entry in reasons))

    def test_the_summary_view_does_not_include_reasons(self):
        item = Oggetto.objects.create(nome="Riassunto", modello=False)
        self.assertNotIn("specialReasons", serialize_item(item, detailed=False))


class ItemRecheckSpecialTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER)
        cls.player = Giocatore.objects.create(nome="player", role=Giocatore.ROLE_USER)

    def test_recheck_clears_the_flag_once_the_cause_is_fixed(self):
        item = Oggetto.objects.create(
            nome="Da rivalutare", tipo_1="pozione", modello=False, speciale=True,
            metadata={"specialReasons": ["non_modello"]},
        )
        update_item(None, self.master, item.id, {"modello": True})
        result = recheck_items_special(None, self.master, [item.id])
        item.refresh_from_db()
        self.assertEqual(result, {"checked": 1, "cleared": 1, "stillSpecial": 0})
        self.assertFalse(item.speciale)
        self.assertEqual(item.metadata["specialReasons"], [])

    def test_recheck_keeps_the_flag_when_the_cause_persists(self):
        item = Oggetto.objects.create(nome="Ancora da sistemare", modello=False, speciale=True)
        result = recheck_items_special(None, self.master, [item.id])
        item.refresh_from_db()
        self.assertEqual(result, {"checked": 1, "cleared": 0, "stillSpecial": 1})
        self.assertTrue(item.speciale)
        self.assertEqual(item.metadata["specialReasons"], ["non_modello", "tipo_1_vuoto"])

    def test_recheck_only_touches_the_selected_items(self):
        selected = Oggetto.objects.create(nome="Selezionato", tipo_1="pozione", speciale=True)
        untouched = Oggetto.objects.create(nome="Non toccato", modello=False, speciale=True)
        recheck_items_special(None, self.master, [selected.id])
        selected.refresh_from_db()
        untouched.refresh_from_db()
        self.assertFalse(selected.speciale)
        self.assertTrue(untouched.speciale)

    def test_players_cannot_recheck(self):
        item = Oggetto.objects.create(nome="Protetto", tipo_1="pozione", speciale=True)
        with self.assertRaises(ApiError):
            recheck_items_special(None, self.player, [item.id])

    def test_an_empty_selection_is_refused(self):
        with self.assertRaises(ApiError):
            recheck_items_special(None, self.master, [])


class ItemCatalogPaginationTests(TestCase):
    """Scoped by name so a seeded catalogue row cannot shift the counts."""

    PREFIX = "Paginazione"

    @classmethod
    def setUpTestData(cls):
        for index in range(12):
            Oggetto.objects.create(
                nome=f"{cls.PREFIX} {index:02d}",
                tipo_1="pozione",
                numero_ordine=index,
                speciale=index % 2 == 0,
                regione_loot="Skyrim" if index < 4 else "",
            )

    def page(self, **kwargs):
        return item_catalog_payload(self.PREFIX, **kwargs)

    def test_a_page_reports_the_total_and_whether_more_remain(self):
        first = self.page(limit=5, offset=0)
        self.assertEqual(first["total"], 12)
        self.assertEqual(len(first["items"]), 5)
        self.assertTrue(first["hasMore"])
        last = self.page(limit=5, offset=10)
        self.assertEqual(len(last["items"]), 2)
        self.assertFalse(last["hasMore"])

    def test_pages_do_not_repeat_or_skip_rows(self):
        seen = []
        for offset in (0, 5, 10):
            seen.extend(entry["id"] for entry in self.page(limit=5, offset=offset)["items"])
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(len(seen), 12)

    def test_the_special_filter_narrows_the_total_as_well_as_the_page(self):
        payload = self.page(limit=100, special=True)
        self.assertEqual(payload["total"], 6)
        self.assertTrue(all(entry["special"] for entry in payload["items"]))

    def test_the_region_filter_uses_the_reported_region_list(self):
        payload = self.page(limit=100, region="skyrim")
        self.assertEqual(payload["total"], 4)
        self.assertIn("Skyrim", payload["regions"])


class ItemCatalogExtendedFilterTests(TestCase):
    """Scoped by name so a seeded catalogue row cannot shift the counts."""

    PREFIX = "Filtro"

    @classmethod
    def setUpTestData(cls):
        cls.spada = TipoArma.objects.create(nome=f"{cls.PREFIX} spada")
        cls.ascia = TipoArma.objects.create(nome=f"{cls.PREFIX} ascia")
        Oggetto.objects.create(
            nome=f"{cls.PREFIX} lieve", tipo_1="arma", tipo_2="taglio", tipo_3="corta",
            rarita=1, peso=1.5, valore=10, tipo_arma=cls.spada, numero_ordine=1,
        )
        Oggetto.objects.create(
            nome=f"{cls.PREFIX} media", tipo_1="arma", tipo_2="contundente", tipo_3="",
            rarita=3, peso=5.0, valore=50, tipo_arma=cls.ascia, numero_ordine=2,
        )
        Oggetto.objects.create(
            nome=f"{cls.PREFIX} pesante", tipo_1="armatura", tipo_2="", tipo_3="",
            rarita=5, peso=20.0, valore=200, tipo_arma=None, numero_ordine=3,
        )
        Oggetto.objects.create(
            nome=f"{cls.PREFIX} senza regione", tipo_1="pozione", regione_loot="", numero_ordine=4,
        )
        Oggetto.objects.create(
            nome=f"{cls.PREFIX} con regione", tipo_1="pozione", regione_loot="Skyrim", numero_ordine=5,
        )

    def page(self, **kwargs):
        return item_catalog_payload(self.PREFIX, **kwargs)

    def test_type_2_narrows_results(self):
        payload = self.page(limit=100, type_2="taglio")
        self.assertEqual([entry["name"] for entry in payload["items"]], [f"{self.PREFIX} lieve"])

    def test_type_3_narrows_results(self):
        payload = self.page(limit=100, type_3="corta")
        self.assertEqual([entry["name"] for entry in payload["items"]], [f"{self.PREFIX} lieve"])

    def test_rarity_filters_exactly(self):
        payload = self.page(limit=100, rarity=5)
        self.assertEqual([entry["name"] for entry in payload["items"]], [f"{self.PREFIX} pesante"])

    def test_weapon_type_id_filters_exactly(self):
        payload = self.page(limit=100, weapon_type_id=self.ascia.id)
        self.assertEqual([entry["name"] for entry in payload["items"]], [f"{self.PREFIX} media"])

    def test_weight_range_is_inclusive_on_both_ends(self):
        payload = self.page(limit=100, weight_min=5.0, weight_max=5.0)
        self.assertEqual([entry["name"] for entry in payload["items"]], [f"{self.PREFIX} media"])

    def test_value_range_narrows_results(self):
        payload = self.page(limit=100, value_min=100)
        self.assertEqual([entry["name"] for entry in payload["items"]], [f"{self.PREFIX} pesante"])

    def test_sort_by_rarity_descending(self):
        payload = self.page(limit=100, sort="rarity_desc")
        names = [entry["name"] for entry in payload["items"]]
        self.assertEqual(names[:3], [f"{self.PREFIX} pesante", f"{self.PREFIX} media", f"{self.PREFIX} lieve"])

    def test_sort_by_value_ascending(self):
        payload = self.page(limit=100, sort="value")
        weapon_names = [entry["name"] for entry in payload["items"] if entry["name"].startswith(f"{self.PREFIX} ") and entry["value"]]
        self.assertEqual(weapon_names[:3], [f"{self.PREFIX} lieve", f"{self.PREFIX} media", f"{self.PREFIX} pesante"])

    def test_none_sentinel_on_region_finds_untagged_items(self):
        payload = self.page(limit=100, region="__none__")
        names = {entry["name"] for entry in payload["items"]}
        self.assertIn(f"{self.PREFIX} senza regione", names)
        self.assertNotIn(f"{self.PREFIX} con regione", names)

    def test_none_sentinel_on_type_2_finds_items_without_that_type(self):
        payload = self.page(limit=100, type_1="armatura", type_2="__none__")
        self.assertEqual([entry["name"] for entry in payload["items"]], [f"{self.PREFIX} pesante"])

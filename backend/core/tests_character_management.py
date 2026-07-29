from django.test import TestCase

from backend.characters.models import (
    BottoneCombat,
    ContenitoreInventario,
    Equip,
    Note,
    Personaggio,
    VoceContenitoreInventario,
    Zaino,
)
from backend.core.api import ApiError
from backend.core.management_selectors import (
    character_management_detail,
    character_management_overview,
)
from backend.core.management_services import delete_orphan_record, update_managed_character
from backend.core.models import DatiCampagna, Effetto, Giocatore, Oggetto


class CharacterProfileFieldTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER)
        cls.campaign = DatiCampagna.objects.create(nome="Sanguine")
        cls.other = DatiCampagna.objects.create(nome="Principale")
        cls.character = Personaggio.objects.create(nome="Eroe", nome_interno="eroe", campagna=cls.campaign)

    def test_campaign_is_editable_and_reported(self):
        detail = update_managed_character(
            None, self.master, self.character.id, {"campagna": str(self.other.id)}, {},
        )
        self.character.refresh_from_db()
        self.assertEqual(self.character.campagna_id, self.other.id)
        self.assertEqual(detail["character"]["campaignName"], "Principale")

    def test_campaign_can_be_cleared(self):
        update_managed_character(None, self.master, self.character.id, {"campagna": ""}, {})
        self.character.refresh_from_db()
        self.assertIsNone(self.character.campagna_id)

    def test_unknown_campaign_is_refused(self):
        with self.assertRaises(ApiError):
            update_managed_character(None, self.master, self.character.id, {"campagna": "9999"}, {})

    def test_calculated_fields_are_shown_but_never_written(self):
        detail = character_management_detail(self.character.id)
        calculated = {field["key"] for field in detail["profileFields"] if field.get("readOnly")}
        self.assertEqual(calculated, {"effetti_finali", "tot"})
        update_managed_character(None, self.master, self.character.id, {"tot": {"pf": 9999}}, {})
        self.character.refresh_from_db()
        self.assertNotEqual(self.character.tot.get("pf"), 9999)

    def test_the_campaign_filter_narrows_the_list(self):
        Personaggio.objects.create(nome="Senza", nome_interno="senza")
        self.assertEqual(len(character_management_overview()["characters"]), 2)
        self.assertEqual(len(character_management_overview(campaign_id=str(self.campaign.id))["characters"]), 1)
        self.assertEqual(len(character_management_overview(campaign_id="none")["characters"]), 1)

    def test_slot_options_only_carry_the_items_this_character_uses(self):
        Oggetto.objects.create(nome="Non usato", tipo_1="pozione")
        used = Oggetto.objects.create(nome="Usato", tipo_1="pozione")
        self.character.zaino = Zaino.objects.create(nome="Zaino", slot_1=used)
        self.character.save(update_fields=["zaino"])
        options = character_management_detail(self.character.id)["options"]
        self.assertEqual([entry["name"] for entry in options["items"]], ["Usato"])


class DeletionPreviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER)
        cls.character = Personaggio.objects.create(nome="Eroe", nome_interno="eroe")

    def test_preview_lists_the_records_that_cascade(self):
        ContenitoreInventario.objects.create(nome="Zaino", scope="personal", personaggio=self.character)
        records = {entry["kind"]: entry for entry in character_management_detail(self.character.id)["deletionPreview"]["records"]}
        self.assertIn("contenitori_inventario", records)
        self.assertIn("skill_sbloccate", records)
        self.assertIn("tiri_competenze", records)
        self.assertTrue(records["contenitori_inventario"]["willDelete"])
        self.assertEqual(records["skill_sbloccate"]["status"], "empty")


class InventoryContainerViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.character = Personaggio.objects.create(nome="Eroe", nome_interno="eroe")

    def test_the_slot_inventory_is_reported_alongside_the_legacy_records(self):
        item = Oggetto.objects.create(nome="Corda", tipo_1="utile")
        container = ContenitoreInventario.objects.create(nome="Zaino", scope="personal", personaggio=self.character, capacita=15)
        VoceContenitoreInventario.objects.create(contenitore=container, slot=2, oggetto=item, quantita=3)
        VoceContenitoreInventario.objects.create(contenitore=container, slot=1, reagent_stock_key="r1", quantita=5)
        containers = character_management_detail(self.character.id)["inventoryContainers"]
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0]["capacity"], 15)
        self.assertEqual([entry["slot"] for entry in containers[0]["entries"]], [1, 2])
        self.assertTrue(containers[0]["entries"][0]["isReagent"])
        self.assertEqual(containers[0]["entries"][1]["name"], "Corda")

    def test_a_character_without_a_container_reports_an_empty_list(self):
        self.assertEqual(character_management_detail(self.character.id)["inventoryContainers"], [])


class OrphanCleanupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER)
        cls.player = Giocatore.objects.create(nome="player", role=Giocatore.ROLE_USER)

    def test_an_unattached_record_is_listed_as_an_orphan(self):
        Zaino.objects.create(nome="Zaino perduto")
        orphans = character_management_overview()["orphans"]
        self.assertEqual([entry["kind"] for entry in orphans], ["zaino"])
        self.assertTrue(orphans[0]["attachable"])

    def test_an_unattached_combat_button_is_found_too(self):
        BottoneCombat.objects.create(nome="Bottone perduto")
        orphans = character_management_overview(orphan_kind="bottoni_combat")["orphans"]
        self.assertEqual(len(orphans), 1)
        self.assertFalse(orphans[0]["attachable"])

    def test_a_record_still_attached_is_not_an_orphan(self):
        zaino = Zaino.objects.create(nome="Zaino in uso")
        Personaggio.objects.create(nome="Eroe", nome_interno="eroe", zaino=zaino)
        self.assertEqual(character_management_overview()["orphans"], [])

    def test_deleting_an_orphan_leaves_the_catalogue_untouched(self):
        item = Oggetto.objects.create(nome="Spada", tipo_1="arma")
        effect = Effetto.objects.create(nome="Fuoco")
        zaino = Zaino.objects.create(nome="Zaino perduto", slot_1=item)
        equip = Equip.objects.create(nome="Equip perduto", arma=item)
        delete_orphan_record(None, self.master, "zaino", zaino.id)
        delete_orphan_record(None, self.master, "equip", equip.id)
        self.assertFalse(Zaino.objects.filter(pk=zaino.id).exists())
        self.assertFalse(Equip.objects.filter(pk=equip.id).exists())
        self.assertTrue(Oggetto.objects.filter(pk=item.id).exists())
        self.assertTrue(Effetto.objects.filter(pk=effect.id).exists())

    def test_a_record_attached_to_a_character_is_refused(self):
        zaino = Zaino.objects.create(nome="Zaino in uso")
        Personaggio.objects.create(nome="Eroe", nome_interno="eroe", zaino=zaino)
        with self.assertRaisesMessage(ApiError, "non è un orfano"):
            delete_orphan_record(None, self.master, "zaino", zaino.id)
        self.assertTrue(Zaino.objects.filter(pk=zaino.id).exists())

    def test_a_record_shared_by_another_character_is_refused(self):
        note = Note.objects.create(nome="Note condivise")
        Personaggio.objects.create(nome="Primo", nome_interno="primo", note=note)
        Personaggio.objects.create(nome="Secondo", nome_interno="secondo", note=note)
        with self.assertRaises(ApiError):
            delete_orphan_record(None, self.master, "note", note.id)
        self.assertTrue(Note.objects.filter(pk=note.id).exists())

    def test_players_cannot_delete_leftovers(self):
        zaino = Zaino.objects.create(nome="Zaino perduto")
        with self.assertRaises(ApiError):
            delete_orphan_record(None, self.player, "zaino", zaino.id)
        self.assertTrue(Zaino.objects.filter(pk=zaino.id).exists())

    def test_an_unknown_kind_is_refused(self):
        with self.assertRaises(ApiError):
            delete_orphan_record(None, self.master, "oggetti", 1)

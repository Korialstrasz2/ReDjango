from django.db import IntegrityError, transaction
from django.test import TestCase

from backend.characters.models import Personaggio
from backend.core.campaigns import campaigns_payload, select_campaign, update_shared_campaign_notes
from backend.core.models import DatiCampagna, Giocatore


class CampaignSelectionTests(TestCase):
    def setUp(self):
        self.test_campaign = DatiCampagna.objects.create(nome="Campagna Test", attiva=True)
        self.sanguine = DatiCampagna.objects.create(nome="Sanguine", attiva=False)
        self.character = Personaggio.objects.create(
            nome="Personaggio Test",
            nome_interno="personaggio_test_campaign",
            campagna=self.test_campaign,
        )
        self.player = Giocatore.objects.create(
            nome="campaign-player",
            active_campaign=self.test_campaign,
            active_character=self.character,
        )

    def test_select_campaign_keeps_one_global_active_and_clears_foreign_character(self):
        payload = select_campaign(self.player, self.sanguine.id)

        self.player.refresh_from_db()
        self.test_campaign.refresh_from_db()
        self.sanguine.refresh_from_db()
        self.assertEqual(self.player.active_campaign_id, self.sanguine.id)
        self.assertIsNone(self.player.active_character_id)
        self.assertFalse(self.test_campaign.attiva)
        self.assertTrue(self.sanguine.attiva)
        self.assertEqual(payload["activeCampaignId"], self.sanguine.id)
        self.assertEqual(sum(1 for entry in payload["campaigns"] if entry["isSelected"]), 1)

    def test_shared_notes_belong_to_selected_campaign(self):
        select_campaign(self.player, self.sanguine.id)
        self.player.refresh_from_db()

        payload = update_shared_campaign_notes(self.player, self.sanguine.id, "Nota comune")

        self.sanguine.refresh_from_db()
        self.assertEqual(self.sanguine.note_condivise, "Nota comune")
        self.assertEqual(
            next(entry for entry in payload["campaigns"] if entry["id"] == self.sanguine.id)["sharedNotes"],
            "Nota comune",
        )

    def test_payload_falls_back_to_global_active_campaign(self):
        self.player.active_campaign = None
        self.player.save(update_fields=["active_campaign", "updated_at"])

        payload = campaigns_payload(self.player)

        self.assertEqual(payload["activeCampaignId"], self.test_campaign.id)

    def test_database_rejects_two_active_campaigns_even_when_save_is_bypassed(self):
        DatiCampagna.objects.update(attiva=False)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DatiCampagna.objects.bulk_create([
                DatiCampagna(nome="Attiva A", attiva=True),
                DatiCampagna(nome="Attiva B", attiva=True),
            ])

from unittest.mock import patch
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.core.api import ApiError
from backend.core.models import DatiCampagna, Giocatore, Oggetto

from .models import Personaggio, Zaino
from .services.coins import (
    COIN_SYSTEM_KEY,
    coin_storage_payload,
    update_carried_coins,
    update_shared_coins,
)


class CharacterCoinStorageTests(TestCase):
    def setUp(self):
        self.campaign = DatiCampagna.objects.create(nome="Tesoreria test")
        self.backpack = Zaino.objects.create(nome="Zaino monete")
        self.other_item = Oggetto.objects.create(nome="Razioni test monete", peso=2)
        self.backpack.slot_1 = self.other_item
        self.backpack.save(update_fields=["slot_1", "updated_at"])
        self.character = Personaggio.objects.create(
            nome="Portatore",
            nome_interno="portatore-monete-test",
            campagna=self.campaign,
            zaino=self.backpack,
            monete=0,
            tot={"slot_magici": 0, "slot_non_magici": 7, "monete_per_slot": 300},
        )
        self.no_refresh = patch(
            "backend.characters.services.coins.refresh_personaggio",
            side_effect=lambda character: None,
        )
        self.no_refresh.start()
        self.addCleanup(self.no_refresh.stop)

    def coin_slots(self):
        self.backpack.refresh_from_db()
        coin_id = Oggetto.objects.get(metadata__systemKey=COIN_SYSTEM_KEY).id
        return [
            index
            for index in range(1, 51)
            if getattr(self.backpack, f"slot_{index}_id") == coin_id
        ]

    def test_balance_populates_bounded_derived_coin_slots(self):
        result = update_carried_coins(self.character.id, 700)

        self.assertEqual(result.character.monete, 700)
        self.assertEqual(len(self.coin_slots()), 3)
        self.assertEqual(Oggetto.objects.get(metadata__systemKey=COIN_SYSTEM_KEY).peso, 1)
        self.assertIn(self.other_item.id, [
            getattr(self.backpack, f"slot_{index}_id") for index in range(1, 8)
        ])

    def test_decreasing_balance_removes_surplus_coin_slots(self):
        update_carried_coins(self.character.id, 700)
        update_carried_coins(self.character.id, 300, expected_coins=700)

        self.character.refresh_from_db()
        self.assertEqual(self.character.monete, 300)
        self.assertEqual(len(self.coin_slots()), 1)

    def test_over_capacity_rejects_without_changing_balance_or_items(self):
        with self.assertRaises(ApiError) as caught:
            update_carried_coins(self.character.id, 2_100)

        self.assertEqual(caught.exception.code, "character.coins_over_capacity")
        self.character.refresh_from_db()
        self.assertEqual(self.character.monete, 0)
        self.assertEqual(self.backpack.slot_1_id, self.other_item.id)
        self.assertEqual(self.coin_slots(), [])

    def test_overflow_can_be_transferred_atomically_to_campaign(self):
        result = update_carried_coins(
            self.character.id,
            2_100,
            transfer_overflow=True,
            expected_coins=0,
            expected_shared_coins=0,
        )

        self.campaign.refresh_from_db()
        self.assertEqual(result.character.monete, 1_800)
        self.assertEqual(result.transferred, 300)
        self.assertEqual(self.campaign.monete_condivise, 300)
        self.assertEqual(len(self.coin_slots()), 6)

    def test_huge_typo_is_rejected_with_constant_physical_slot_work(self):
        with self.assertRaises(ApiError) as caught:
            update_carried_coins(self.character.id, 99_999_999)

        self.assertEqual(caught.exception.code, "character.coins_over_capacity")
        self.assertEqual(self.coin_slots(), [])

    def test_shared_balance_is_independent_and_stale_safe(self):
        updated = update_shared_coins(self.character.id, 12_345, expected_coins=0)
        self.assertEqual(updated.campagna.monete_condivise, 12_345)

        with self.assertRaises(ApiError) as caught:
            update_shared_coins(self.character.id, 12_346, expected_coins=0)
        self.assertEqual(caught.exception.code, "campaign.shared_coins_stale")

    def test_storage_preview_reports_required_and_available_slots(self):
        preview = coin_storage_payload(self.character, requested_coins=2_100)

        self.assertEqual(preview["requiredSlots"], 7)
        self.assertEqual(preview["availableSlots"], 6)
        self.assertEqual(preview["maxCarryableCoins"], 1_800)
        self.assertFalse(preview["fits"])

    def test_authenticated_player_actions_return_updated_carried_and_shared_balances(self):
        user = get_user_model().objects.create_user(username="coin-player", password="test-password")
        player = Giocatore.objects.create(
            user=user,
            nome="coin-player",
            character_ids=[self.character.id],
            active_character=self.character,
            active_campaign=self.campaign,
        )
        self.client.force_login(user)

        carried = self.client.post(
            "/api/v1/actions",
            data=json.dumps({
                "action": "character.updateCoins",
                "requestId": "coins-api",
                "payload": {
                    "characterId": self.character.id,
                    "coins": 700,
                    "expectedCoins": 0,
                    "transferOverflow": False,
                },
            }),
            content_type="application/json",
        )
        self.assertEqual(carried.status_code, 200)
        self.assertEqual(carried.json()["data"]["character"]["coins"], 700)
        self.assertEqual(carried.json()["data"]["character"]["coinStorage"]["requiredSlots"], 3)

        shared = self.client.post(
            "/api/v1/actions",
            data=json.dumps({
                "action": "campaign.updateSharedCoins",
                "requestId": "shared-coins-api",
                "payload": {
                    "characterId": self.character.id,
                    "coins": 4_321,
                    "expectedCoins": 0,
                },
            }),
            content_type="application/json",
        )
        self.assertEqual(shared.status_code, 200)
        self.assertEqual(shared.json()["data"]["character"]["coinStorage"]["sharedCoins"], 4_321)
        player.refresh_from_db()

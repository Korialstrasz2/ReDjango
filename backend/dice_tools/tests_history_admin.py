from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from backend.core.api import ApiError
from backend.core.models import Giocatore
from backend.dice_tools.models import DiceRollRecord, DiceSet, DiceTexture
from backend.dice_tools.selectors import dice_history_payload, serialize_dice_set
from backend.dice_tools.services import duplicate_dice_set, purge_dice_history
from backend.media_library.models import UploadedImage


class DiceHistoryAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER)
        cls.admin = Giocatore.objects.create(nome="admin", role=Giocatore.ROLE_ADMIN)
        cls.player = Giocatore.objects.create(nome="player", role=Giocatore.ROLE_USER)
        for index in range(6):
            DiceRollRecord.objects.create(
                player_name="Ale" if index % 2 else "Bea",
                source=DiceRollRecord.SOURCE_QUICK if index % 2 else DiceRollRecord.SOURCE_COMPETENCE,
                notation="1d20", rolls=[index + 1], modifier=0, total=index + 1,
                dice_set_name="Set A" if index < 3 else "Set B",
            )

    def test_players_cannot_read_the_group_log(self):
        with self.assertRaises(ApiError):
            dice_history_payload(None, self.player)

    def test_the_player_filter_narrows_the_total(self):
        payload = dice_history_payload(None, self.master, player="Ale")
        self.assertEqual(payload["total"], 3)
        self.assertTrue(all(roll["playerName"] == "Ale" for roll in payload["rolls"]))

    def test_the_source_filter_narrows_the_total(self):
        payload = dice_history_payload(None, self.master, source=DiceRollRecord.SOURCE_COMPETENCE)
        self.assertEqual(payload["total"], 3)

    def test_the_player_list_has_no_duplicates(self):
        self.assertEqual(dice_history_payload(None, self.master)["players"], ["Ale", "Bea"])

    def test_pages_report_whether_more_remain(self):
        first = dice_history_payload(None, self.master, limit=4)
        self.assertEqual(len(first["rolls"]), 4)
        self.assertTrue(first["hasMore"])
        self.assertFalse(dice_history_payload(None, self.master, limit=4, offset=4)["hasMore"])

    def test_statistics_are_only_computed_when_requested(self):
        self.assertNotIn("statistics", dice_history_payload(None, self.master))
        statistics = dice_history_payload(None, self.master, include_statistics=True)["statistics"]
        self.assertEqual({row["name"] for row in statistics["byPlayer"]}, {"Ale", "Bea"})
        self.assertEqual({row["name"] for row in statistics["byDiceSet"]}, {"Set A", "Set B"})
        self.assertEqual(sum(entry["count"] for entry in statistics["faceDistribution"]), 6)

    def test_statistics_follow_the_active_filter(self):
        statistics = dice_history_payload(None, self.master, player="Ale", include_statistics=True)["statistics"]
        self.assertEqual([row["name"] for row in statistics["byPlayer"]], ["Ale"])
        self.assertEqual(statistics["byPlayer"][0]["rolls"], 3)


class DiceHistoryPurgeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Giocatore.objects.create(nome="admin", role=Giocatore.ROLE_ADMIN)
        cls.master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER)

    def _roll(self, days_ago: int) -> DiceRollRecord:
        record = DiceRollRecord.objects.create(
            player_name="Ale", source=DiceRollRecord.SOURCE_QUICK,
            notation="1d6", rolls=[3], modifier=0, total=3,
        )
        DiceRollRecord.objects.filter(pk=record.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
        return record

    def test_only_records_older_than_the_cut_off_are_archived(self):
        old = self._roll(40)
        recent = self._roll(2)
        archived = purge_dice_history(None, self.admin, older_than_days=30)
        old.refresh_from_db()
        recent.refresh_from_db()
        self.assertEqual(archived, 1)
        self.assertIsNotNone(old.archived_at)
        self.assertIsNone(recent.archived_at)

    def test_archived_records_leave_the_log_but_stay_in_the_database(self):
        self._roll(40)
        purge_dice_history(None, self.admin, older_than_days=30)
        self.assertEqual(dice_history_payload(None, self.master)["total"], 0)
        self.assertEqual(DiceRollRecord.objects.count(), 1)

    def test_a_zero_day_cut_off_is_refused(self):
        with self.assertRaises(ApiError):
            purge_dice_history(None, self.admin, older_than_days=0)

    def test_masters_cannot_purge(self):
        with self.assertRaises(ApiError):
            purge_dice_history(None, self.master, older_than_days=30)


class DiceSetCoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Giocatore.objects.create(nome="admin", role=Giocatore.ROLE_ADMIN)
        cls.image = UploadedImage.objects.create(title="Texture")
        cls.dice_set = DiceSet.objects.create(
            slug="set-base", name="Set base", dice=[4, 6, 20],
            surface_color="#111111", accent_color="#222222", text_color="#333333",
        )
        DiceTexture.objects.create(dice_set=cls.dice_set, sides=6, image=cls.image)

    def test_untextured_sides_are_reported(self):
        self.assertEqual(serialize_dice_set(self.dice_set)["untexturedDice"], [4, 20])

    def test_duplicating_copies_dice_textures_and_colours(self):
        copy = duplicate_dice_set(None, self.admin, self.dice_set.id)
        self.assertEqual(copy.name, "Copia di Set base")
        self.assertEqual(copy.dice, [4, 6, 20])
        self.assertEqual(copy.surface_color, "#111111")
        self.assertEqual([texture.sides for texture in copy.textures.all()], [6])

    def test_the_copy_starts_as_an_inactive_non_default_draft(self):
        copy = duplicate_dice_set(None, self.admin, self.dice_set.id)
        self.assertFalse(copy.is_active)
        self.assertFalse(copy.is_default)
        self.assertNotEqual(copy.slug, self.dice_set.slug)

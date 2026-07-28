import random

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from backend.characters.models import Personaggio
from backend.core.api import ApiError
from backend.core.campaigns import (
    campaigns_payload,
    reroll_campaign_weather,
    select_campaign,
    update_campaign_clock,
    update_shared_campaign_notes,
)
from backend.core.models import DatiCampagna, Giocatore
from backend.core.weather import DEFAULT_WEATHER, WEATHER_TABLE, entry_for, roll_weather, split_weather


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


class ScriptedRandom(random.Random):
    """Feeds `roll_weather` the exact d2 and d100 results a test needs."""

    def __init__(self, *results: int):
        super().__init__()
        self.results = list(results)

    def randint(self, low: int, high: int) -> int:  # noqa: ARG002 - the script decides
        return self.results.pop(0)


class WeatherTableTests(TestCase):
    def test_the_table_covers_the_whole_d100_without_gaps_or_overlaps(self):
        covered = [value for entry in WEATHER_TABLE for value in range(entry.low, entry.high + 1)]

        self.assertEqual(covered, list(range(1, 101)))

    def test_soleggiato_takes_half_of_the_table(self):
        self.assertEqual((DEFAULT_WEATHER.label, DEFAULT_WEATHER.low, DEFAULT_WEATHER.high), ("Soleggiato", 1, 50))

    def test_stored_weather_splits_into_name_and_effects(self):
        label, effects = split_weather("Pioggia - Costo movimento in combat +25%, Attacco -3")

        self.assertEqual(label, "Pioggia")
        self.assertEqual(effects, "Costo movimento in combat +25%, Attacco -3")

    def test_a_hand_edited_effect_text_still_matches_its_table_row(self):
        self.assertEqual(entry_for("Nebbia - effetti riscritti a mano").label, "Nebbia")

    def test_an_unknown_weather_name_matches_nothing(self):
        self.assertIsNone(entry_for("Pioggia di rane"))

    def test_half_of_every_roll_prolongs_the_current_weather(self):
        entry, prolonged = roll_weather(WEATHER_TABLE[-1].name, ScriptedRandom(1))

        self.assertTrue(prolonged)
        self.assertEqual(entry.label, "Tempesta")

    def test_a_campaign_without_weather_prolongs_soleggiato(self):
        entry, prolonged = roll_weather("", ScriptedRandom(1))

        self.assertTrue(prolonged)
        self.assertEqual(entry, DEFAULT_WEATHER)

    def test_a_fresh_roll_reads_the_d100_ranges(self):
        for roll, expected in [(1, "Soleggiato"), (50, "Soleggiato"), (51, "Pioggia"), (80, "Grande Pioggia"), (90, "Nebbia"), (95, "Temporale"), (100, "Tempesta")]:
            with self.subTest(roll=roll):
                entry, prolonged = roll_weather("Nebbia - x", ScriptedRandom(2, roll))

                self.assertFalse(prolonged)
                self.assertEqual(entry.label, expected)


class CampaignClockTests(TestCase):
    def setUp(self):
        self.campaign = DatiCampagna.objects.create(nome="Sanguine", attiva=True, ora_corrente="9", giorni_da_inizio=33)
        self.user = User.objects.create(username="clock_master")
        self.master = Giocatore.objects.create(
            nome="clock_master",
            role=Giocatore.ROLE_MASTER,
            active_campaign=self.campaign,
        )
        self.player = Giocatore.objects.create(
            nome="clock_player",
            role=Giocatore.ROLE_USER,
            active_campaign=self.campaign,
        )

    def move(self, field, direction, giocatore=None):
        return update_campaign_clock(self.user, giocatore or self.master, self.campaign.id, field, direction)

    def test_the_hour_wraps_around_midnight(self):
        self.campaign.ora_corrente = "23"
        self.campaign.save(update_fields=["ora_corrente"])

        self.move("ora", "increase")

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.ora_corrente, "0")

        self.move("ora", "decrease")

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.ora_corrente, "23")

    def test_a_free_text_clock_restarts_from_zero(self):
        self.campaign.ora_corrente = "Sera"
        self.campaign.save(update_fields=["ora_corrente"])

        self.move("ora", "increase")

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.ora_corrente, "1")

    def test_the_day_stays_inside_its_range(self):
        self.campaign.giorni_da_inizio = 1
        self.campaign.save(update_fields=["giorni_da_inizio"])

        payload, weather_reminder = self.move("giorno", "decrease")

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.giorni_da_inizio, 1)
        self.assertFalse(weather_reminder)
        self.assertEqual(next(entry for entry in payload["campaigns"] if entry["id"] == self.campaign.id)["daysSinceStart"], 1)

        self.campaign.giorni_da_inizio = 1000
        self.campaign.save(update_fields=["giorni_da_inizio"])
        self.move("giorno", "increase")

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.giorni_da_inizio, 1000)

    def test_the_weather_reminder_falls_every_six_hours(self):
        due = []
        for _ in range(24):
            _, weather_reminder = self.move("ora", "increase")
            self.campaign.refresh_from_db()
            if weather_reminder:
                due.append(int(self.campaign.ora_corrente))

        self.assertEqual(sorted(due), [0, 6, 12, 18])

    def test_any_day_change_asks_for_a_weather_roll(self):
        _, weather_reminder = self.move("giorno", "increase")

        self.assertTrue(weather_reminder)

    def test_only_a_master_moves_the_clock(self):
        with self.assertRaises(ApiError) as raised:
            self.move("ora", "increase", self.player)

        self.assertEqual(raised.exception.status, 403)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.ora_corrente, "9")

    def test_an_unknown_field_or_direction_is_refused(self):
        with self.assertRaises(ApiError):
            self.move("minuti", "increase")
        with self.assertRaises(ApiError):
            self.move("ora", "reset")

    def test_the_clock_belongs_to_the_selected_campaign(self):
        other = DatiCampagna.objects.create(nome="Altra campagna")

        with self.assertRaises(ApiError) as raised:
            update_campaign_clock(self.user, self.master, other.id, "ora", "increase")

        self.assertEqual(raised.exception.status, 409)


class CampaignWeatherRerollTests(TestCase):
    def setUp(self):
        self.campaign = DatiCampagna.objects.create(nome="Sanguine", attiva=True, meteo=WEATHER_TABLE[1].name)
        self.user = User.objects.create(username="weather_master")
        self.master = Giocatore.objects.create(
            nome="weather_master",
            role=Giocatore.ROLE_MASTER,
            active_campaign=self.campaign,
        )
        self.player = Giocatore.objects.create(
            nome="weather_player",
            role=Giocatore.ROLE_USER,
            active_campaign=self.campaign,
        )

    def test_a_reroll_always_stores_a_table_entry(self):
        payload, entry, _ = reroll_campaign_weather(self.user, self.master, self.campaign.id)

        self.campaign.refresh_from_db()
        self.assertIn(entry, WEATHER_TABLE)
        self.assertEqual(self.campaign.meteo, entry.name)
        campaign_entry = next(row for row in payload["campaigns"] if row["id"] == self.campaign.id)
        self.assertEqual(campaign_entry["weatherLabel"], entry.label)
        self.assertEqual(campaign_entry["weatherEffects"], entry.effects)

    def test_only_a_master_rerolls_the_weather(self):
        with self.assertRaises(ApiError) as raised:
            reroll_campaign_weather(self.user, self.player, self.campaign.id)

        self.assertEqual(raised.exception.status, 403)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.meteo, WEATHER_TABLE[1].name)

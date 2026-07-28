from django.contrib.auth.models import User
from django.test import TestCase

from backend.core.api import ApiError
from backend.core.models import DatiCampagna, Giocatore, TimelineEvent
from backend.lore.models import EventoReputazione, Fazione, PersonaggioLore
from backend.lore.selectors import lore_payload, reputation_tier
from backend.lore.services import (
    archive_timeline_event,
    delete_event,
    delete_faction,
    record_event,
    save_faction,
    save_npc,
    save_relations,
    save_timeline_event,
    update_event,
)


class LoreTestCase(TestCase):
    def setUp(self):
        self.campaign = DatiCampagna.objects.create(nome="Campagna Lore", giorni_da_inizio=12, ora_corrente="Sera")
        self.user = User.objects.create(username="lore_master")
        self.master = Giocatore.objects.create(
            user=self.user,
            nome="lore_master",
            role=Giocatore.ROLE_MASTER,
            active_campaign=self.campaign,
        )
        self.player = Giocatore.objects.create(
            nome="lore_player",
            role=Giocatore.ROLE_USER,
            active_campaign=self.campaign,
        )
        save_faction(self.user, self.master, {"name": "Gilda dei Ladri", "baseReputation": 10})
        save_faction(self.user, self.master, {"name": "Guardia Cittadina", "baseReputation": 0})
        self.thieves = Fazione.objects.get(nome="Gilda dei Ladri")
        self.guards = Fazione.objects.get(nome="Guardia Cittadina")

    def scores(self, giocatore=None):
        payload = lore_payload(self.user, giocatore or self.master)
        return {faction["name"]: faction["reputation"] for faction in payload["factions"]}

    def link(self, coefficient):
        save_relations(self.user, self.master, [
            {"sourceId": self.thieves.id, "targetId": self.guards.id, "coefficient": coefficient},
        ])


class ReputationReplayTests(LoreTestCase):
    def test_base_values_are_the_starting_scores(self):
        self.assertEqual(self.scores(), {"Gilda dei Ladri": 10, "Guardia Cittadina": 0})

    def test_adjustment_propagates_one_hop_through_the_grid(self):
        self.link(-0.5)
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Colpo al banco dei pegni",
            "entries": [{"factionId": self.thieves.id, "value": 20}],
        })
        self.assertEqual(self.scores(), {"Gilda dei Ladri": 30, "Guardia Cittadina": -10})

    def test_propagated_effect_does_not_propagate_again(self):
        # guards react to thieves, and a third faction reacts to guards.
        save_faction(self.user, self.master, {"name": "Mercanti", "baseReputation": 0})
        merchants = Fazione.objects.get(nome="Mercanti")
        save_relations(self.user, self.master, [
            {"sourceId": self.thieves.id, "targetId": self.guards.id, "coefficient": -0.5},
            {"sourceId": self.guards.id, "targetId": merchants.id, "coefficient": 1.0},
        ])
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Colpo al banco dei pegni",
            "entries": [{"factionId": self.thieves.id, "value": 20}],
        })
        self.assertEqual(self.scores()["Mercanti"], 0)

    def test_authored_value_wins_over_propagation(self):
        self.link(-0.5)
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Trattativa doppia",
            "entries": [
                {"factionId": self.thieves.id, "value": 20},
                {"factionId": self.guards.id, "value": 4},
            ],
        })
        self.assertEqual(self.scores(), {"Gilda dei Ladri": 30, "Guardia Cittadina": 4})

    def test_backdated_event_replays_in_campaign_day_order(self):
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Evento recente",
            "entries": [{"factionId": self.guards.id, "value": -10}],
        })
        record_event(self.user, self.master, {
            "mode": "set",
            "reason": "Vecchio decreto",
            "campaignDay": 3,
            "entries": [{"factionId": self.guards.id, "value": 50}],
        })
        # Day 3 anchors at 50, then day 12 subtracts 10.
        self.assertEqual(self.scores()["Guardia Cittadina"], 40)

    def test_campaign_day_defaults_to_the_current_day(self):
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Oggi",
            "entries": [{"factionId": self.guards.id, "value": 5}],
        })
        event = EventoReputazione.objects.get(campagna=self.campaign)
        self.assertEqual(event.giorno_campagna, 12)
        self.assertEqual(event.ora_campagna, "Sera")

    def test_set_event_does_not_propagate(self):
        self.link(-0.5)
        record_event(self.user, self.master, {
            "mode": "set",
            "reason": "Correzione del master",
            "entries": [{"factionId": self.thieves.id, "value": 80}],
        })
        self.assertEqual(self.scores(), {"Gilda dei Ladri": 80, "Guardia Cittadina": 0})

    def test_scores_stay_within_the_allowed_range(self):
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Massacro",
            "entries": [{"factionId": self.guards.id, "value": -100}],
        })
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Altro massacro",
            "entries": [{"factionId": self.guards.id, "value": -100}],
        })
        self.assertEqual(self.scores()["Guardia Cittadina"], -100)

    def test_deleting_an_event_retroactively_recomputes_the_present(self):
        self.link(-0.5)
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Colpo al banco dei pegni",
            "entries": [{"factionId": self.thieves.id, "value": 20}],
        })
        event = EventoReputazione.objects.get(campagna=self.campaign)
        delete_event(self.user, self.master, event.id)
        self.assertEqual(self.scores(), {"Gilda dei Ladri": 10, "Guardia Cittadina": 0})

    def test_editing_the_grid_does_not_rewrite_past_events(self):
        self.link(-0.5)
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Colpo al banco dei pegni",
            "entries": [{"factionId": self.thieves.id, "value": 20}],
        })
        self.link(2.0)
        self.assertEqual(self.scores()["Guardia Cittadina"], -10)

    def test_archived_faction_keeps_history_readable(self):
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Accordo",
            "entries": [{"factionId": self.guards.id, "value": 10}],
        })
        delete_faction(self.user, self.master, self.guards.id)
        payload = lore_payload(self.user, self.master)
        self.assertEqual([faction["name"] for faction in payload["factions"]], ["Gilda dei Ladri"])
        self.assertEqual(payload["events"][0]["effects"], [])

    def test_tier_labels_track_the_score(self):
        self.assertEqual(reputation_tier(-100)["key"], "ostilita_aperta")
        self.assertEqual(reputation_tier(0)["key"], "neutrale")
        self.assertEqual(reputation_tier(100)["key"], "alleato")


class ReputationEventEditTests(LoreTestCase):
    def record(self, value=20):
        self.link(-0.5)
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Colpo al banco dei pegni",
            "entries": [{"factionId": self.thieves.id, "value": value}],
        })
        return EventoReputazione.objects.get(campagna=self.campaign)

    def test_editing_only_the_reason_keeps_the_recorded_reactions(self):
        event = self.record()
        self.link(2.0)  # grid changed after the fact
        update_event(self.user, self.master, {
            "id": event.id,
            "mode": "adjust",
            "reason": "Colpo al banco dei pegni, corretto",
            "entries": [{"factionId": self.thieves.id, "value": 20}],
        })
        event.refresh_from_db()
        self.assertEqual(event.motivo, "Colpo al banco dei pegni, corretto")
        # The original -0.5 reaction survives instead of being recomputed at 2.0.
        self.assertEqual(self.scores()["Guardia Cittadina"], -10)

    def test_changing_a_value_rebuilds_the_reactions(self):
        event = self.record()
        update_event(self.user, self.master, {
            "id": event.id,
            "mode": "adjust",
            "reason": "Colpo al banco dei pegni",
            "entries": [{"factionId": self.thieves.id, "value": 40}],
        })
        self.assertEqual(self.scores(), {"Gilda dei Ladri": 50, "Guardia Cittadina": -20})

    def test_changing_the_mode_rebuilds_and_stops_propagation(self):
        event = self.record()
        update_event(self.user, self.master, {
            "id": event.id,
            "mode": "set",
            "reason": "Correzione",
            "entries": [{"factionId": self.thieves.id, "value": 40}],
        })
        self.assertEqual(self.scores(), {"Gilda dei Ladri": 40, "Guardia Cittadina": 0})

    def test_editing_the_day_reorders_the_replay(self):
        first = self.record()
        record_event(self.user, self.master, {
            "mode": "set",
            "reason": "Decreto",
            "entries": [{"factionId": self.thieves.id, "value": 5}],
        })
        self.assertEqual(self.scores()["Gilda dei Ladri"], 5)
        update_event(self.user, self.master, {
            "id": first.id,
            "mode": "adjust",
            "reason": "Colpo al banco dei pegni",
            "campaignDay": 99,
            "entries": [{"factionId": self.thieves.id, "value": 20}],
        })
        # The adjustment now lands after the anchor instead of before it.
        self.assertEqual(self.scores()["Gilda dei Ladri"], 25)

    def test_players_cannot_edit_events(self):
        event = self.record()
        with self.assertRaises(ApiError) as caught:
            update_event(self.user, self.player, {
                "id": event.id,
                "mode": "adjust",
                "reason": "x",
                "entries": [{"factionId": self.thieves.id, "value": 1}],
            })
        self.assertEqual(caught.exception.status, 403)

    def test_editing_an_unknown_event_is_rejected(self):
        with self.assertRaises(ApiError) as caught:
            update_event(self.user, self.master, {
                "id": 9999,
                "mode": "adjust",
                "reason": "x",
                "entries": [{"factionId": self.thieves.id, "value": 1}],
            })
        self.assertEqual(caught.exception.status, 404)


class LoreVisibilityTests(LoreTestCase):
    def test_players_read_standings_but_never_the_grid(self):
        self.link(-0.5)
        payload = lore_payload(self.user, self.player)
        self.assertFalse(payload["permissions"]["canManage"])
        for faction in payload["factions"]:
            self.assertNotIn("relations", faction)
            self.assertNotIn("baseReputation", faction)
            self.assertIn("reputation", faction)

    def test_hidden_event_still_moves_the_visible_score(self):
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Patto segreto",
            "entries": [{"factionId": self.guards.id, "value": 25}],
            "visibleToPlayers": False,
        })
        self.assertEqual(self.scores(self.player)["Guardia Cittadina"], 25)
        self.assertEqual(lore_payload(self.user, self.player)["events"], [])
        self.assertEqual(len(lore_payload(self.user, self.master)["events"]), 1)

    def test_players_only_see_visible_characters(self):
        save_npc(self.user, self.master, {"name": "Brynjolf", "visibleToPlayers": True})
        save_npc(self.user, self.master, {"name": "Informatore", "visibleToPlayers": False})
        self.assertEqual([npc["name"] for npc in lore_payload(self.user, self.player)["npcs"]], ["Brynjolf"])
        self.assertEqual(len(lore_payload(self.user, self.master)["npcs"]), 2)

    def test_players_cannot_mutate_lore(self):
        for call, args in [
            (save_faction, ({"name": "Nuova"},)),
            (save_npc, ({"name": "Nuovo"},)),
            (save_relations, ([],)),
            (record_event, ({"mode": "adjust", "reason": "x", "entries": []},)),
        ]:
            with self.assertRaises(ApiError) as caught:
                call(self.user, self.player, *args)
            self.assertEqual(caught.exception.status, 403)


class LoreValidationTests(LoreTestCase):
    def test_reason_is_required(self):
        with self.assertRaises(ApiError) as caught:
            record_event(self.user, self.master, {
                "mode": "adjust",
                "reason": "  ",
                "entries": [{"factionId": self.guards.id, "value": 5}],
            })
        self.assertEqual(caught.exception.field, "reason")

    def test_adjustment_of_zero_is_rejected(self):
        with self.assertRaises(ApiError) as caught:
            record_event(self.user, self.master, {
                "mode": "adjust",
                "reason": "Nulla di fatto",
                "entries": [{"factionId": self.guards.id, "value": 0}],
            })
        self.assertEqual(caught.exception.code, "lore.delta_zero")

    def test_event_needs_at_least_one_faction(self):
        with self.assertRaises(ApiError) as caught:
            record_event(self.user, self.master, {"mode": "adjust", "reason": "Vuoto", "entries": []})
        self.assertEqual(caught.exception.code, "lore.entries_required")

    def test_same_faction_cannot_appear_twice_in_one_event(self):
        with self.assertRaises(ApiError) as caught:
            record_event(self.user, self.master, {
                "mode": "adjust",
                "reason": "Doppione",
                "entries": [
                    {"factionId": self.guards.id, "value": 5},
                    {"factionId": self.guards.id, "value": 7},
                ],
            })
        self.assertEqual(caught.exception.code, "lore.entry_duplicate")

    def test_duplicate_faction_names_are_rejected(self):
        with self.assertRaises(ApiError) as caught:
            save_faction(self.user, self.master, {"name": "gilda dei ladri"})
        self.assertEqual(caught.exception.code, "lore.faction_duplicate")

    def test_archived_faction_frees_its_name(self):
        delete_faction(self.user, self.master, self.guards.id)
        save_faction(self.user, self.master, {"name": "Guardia Cittadina", "baseReputation": -5})
        self.assertEqual(self.scores()["Guardia Cittadina"], -5)

    def test_faction_cannot_react_to_itself(self):
        with self.assertRaises(ApiError) as caught:
            save_relations(self.user, self.master, [
                {"sourceId": self.guards.id, "targetId": self.guards.id, "coefficient": 1},
            ])
        self.assertEqual(caught.exception.code, "lore.relation_self")

    def test_coefficient_range_is_enforced(self):
        with self.assertRaises(ApiError) as caught:
            save_relations(self.user, self.master, [
                {"sourceId": self.thieves.id, "targetId": self.guards.id, "coefficient": 99},
            ])
        self.assertEqual(caught.exception.code, "lore.coefficient_range")

    def test_archiving_a_faction_detaches_its_characters(self):
        save_npc(self.user, self.master, {"name": "Capitano", "factionId": self.guards.id})
        delete_faction(self.user, self.master, self.guards.id)
        self.assertIsNone(PersonaggioLore.objects.get(nome="Capitano").fazione_id)


class LoreTimelineTests(LoreTestCase):
    def test_timeline_is_campaign_scoped_and_ordered_by_signed_year(self):
        for title, year in (("Dopo", 12), ("Prima", -10), ("Anno zero", 0)):
            save_timeline_event(self.user, self.master, {
                "title": title,
                "year": year,
                "description": f"Evento {year}",
                "tags": ["TES"],
            })
        payload = lore_payload(self.user, self.master)
        self.assertEqual(
            [(event["title"], event["year"]) for event in payload["timelineEvents"]],
            [("Prima", -10), ("Anno zero", 0), ("Dopo", 12)],
        )

    def test_timeline_update_keeps_the_same_record(self):
        save_timeline_event(self.user, self.master, {"title": "Bozza", "year": 2})
        event = TimelineEvent.objects.get(campagna=self.campaign)
        save_timeline_event(self.user, self.master, {
            "id": event.id,
            "title": "Corretto",
            "year": 3,
            "description": "Testo definitivo",
            "tags": ["Morrowind", "morrowind", "Campagna"],
        })
        event.refresh_from_db()
        self.assertEqual(event.nome, "Corretto")
        self.assertEqual(event.ordine_cronologico, 3)
        self.assertEqual(event.data_evento, "3")
        self.assertEqual(event.tags, ["Morrowind", "Campagna"])

    def test_timeline_archive_is_reversible_storage_not_a_delete(self):
        save_timeline_event(self.user, self.master, {"title": "Da archiviare", "year": 1})
        event = TimelineEvent.objects.get(campagna=self.campaign)
        archive_timeline_event(self.user, self.master, event.id)
        event.refresh_from_db()
        self.assertIsNotNone(event.archived_at)
        self.assertEqual(lore_payload(self.user, self.master)["timelineEvents"], [])

    def test_player_cannot_mutate_timeline(self):
        with self.assertRaises(ApiError) as caught:
            save_timeline_event(self.user, self.player, {"title": "Vietato", "year": 1})
        self.assertEqual(caught.exception.status, 403)

    def test_timeline_cannot_edit_another_campaign(self):
        other_campaign = DatiCampagna.objects.create(nome="Altra campagna")
        event = TimelineEvent.objects.create(
            campagna=other_campaign,
            nome="Altrove",
            data_evento="1",
            ordine_cronologico=1,
        )
        with self.assertRaises(ApiError) as caught:
            save_timeline_event(self.user, self.master, {
                "id": event.id,
                "title": "Intrusione",
                "year": 2,
            })
        self.assertEqual(caught.exception.status, 404)


class LoreActionApiTests(LoreTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def command(self, action, payload):
        return self.client.post(
            "/api/v1/actions",
            data={
                "action": action,
                "requestId": "lore-test",
                "context": {"screen": "lore"},
                "payload": payload,
                "meta": {},
            },
            content_type="application/json",
            HTTP_X_REDJANGO_ACTION=action,
        )

    def test_lore_endpoint_returns_the_workspace(self):
        response = self.client.get("/api/v1/lore")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(len(body["data"]["factions"]), 2)

    def test_updating_an_event_returns_the_refreshed_projection(self):
        record_event(self.user, self.master, {
            "mode": "adjust",
            "reason": "Primo tentativo",
            "entries": [{"factionId": self.thieves.id, "value": 15}],
        })
        event = EventoReputazione.objects.get(campagna=self.campaign)
        response = self.command("lore.event.update", {"values": {
            "id": event.id,
            "mode": "adjust",
            "reason": "Motivo corretto",
            "entries": [{"factionId": self.thieves.id, "value": 30}],
        }})
        self.assertEqual(response.status_code, 200)
        factions = {f["name"]: f["reputation"] for f in response.json()["data"]["lore"]["factions"]}
        self.assertEqual(factions["Gilda dei Ladri"], 40)
        event.refresh_from_db()
        self.assertEqual(event.motivo, "Motivo corretto")

    def test_recording_an_event_returns_the_refreshed_projection(self):
        response = self.command("lore.event.record", {"values": {
            "mode": "adjust",
            "reason": "Salvato il mercante",
            "entries": [{"factionId": self.thieves.id, "value": 15}],
        }})
        self.assertEqual(response.status_code, 200)
        factions = {f["name"]: f["reputation"] for f in response.json()["data"]["lore"]["factions"]}
        self.assertEqual(factions["Gilda dei Ladri"], 25)

    def test_saving_a_timeline_event_returns_the_refreshed_projection(self):
        response = self.command("lore.timeline.save", {"values": {
            "title": "Il Warp in the West",
            "year": -10,
            "description": "Una Frattura del Drago trasforma la Baia di Iliac.",
            "imageId": None,
            "tags": ["TES", "Terza Era"],
        }})
        self.assertEqual(response.status_code, 200)
        timeline = response.json()["data"]["lore"]["timelineEvents"]
        self.assertEqual([(event["title"], event["year"]) for event in timeline], [("Il Warp in the West", -10)])

import json

from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase

from backend.characters.models import Personaggio
from backend.characters.selectors import ordered_personaggi_for
from backend.core.api import ApiError
from backend.core.models import CharacterAssignmentRequest, DatiCampagna, Giocatore
from backend.core.player_management_selectors import player_management_overview
from backend.core.player_management_services import (
    assign_player_characters,
    create_player,
    require_player_manager,
    set_player_password,
    update_player,
)


class PlayerManagementServiceTests(TestCase):
    def setUp(self):
        self.campaign = DatiCampagna.objects.create(nome="Sanguine")
        self.admin_user = get_user_model().objects.create_user(username="capo", password="Fortissima-1")
        self.admin = Giocatore.objects.create(
            user=self.admin_user,
            nome="capo",
            display_name="Il Capo",
            role=Giocatore.ROLE_ADMIN,
            active_campaign=self.campaign,
        )
        self.hero = Personaggio.objects.create(
            nome="Illaoi",
            nome_interno="illaoi",
            tipologia="giocabile",
            campagna=self.campaign,
        )
        self.rival = Personaggio.objects.create(
            nome="Ra'Zirr",
            nome_interno="razirr",
            tipologia="giocabile",
            campagna=self.campaign,
        )

    def _player(self, **overrides):
        values = {
            "name": "Nuovo",
            "displayName": "Nuovo Giocatore",
            "username": "nuovo",
            "password": "Ombra-Lunga-42",
            "role": Giocatore.ROLE_USER,
            "activeCampaignId": str(self.campaign.id),
            **overrides,
        }
        create_player(self.admin_user, self.admin, values)
        return Giocatore.objects.get(nome=values["name"])

    def test_only_an_admin_may_manage_players(self):
        master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER)
        with self.assertRaises(ApiError) as error:
            require_player_manager(None, master)
        self.assertEqual(error.exception.status, 403)
        require_player_manager(self.admin_user, self.admin)

    def test_creating_a_player_creates_a_usable_login(self):
        player = self._player()

        self.assertEqual(player.role, Giocatore.ROLE_USER)
        self.assertEqual(player.display_name, "Nuovo Giocatore")
        self.assertEqual(player.active_campaign_id, self.campaign.id)
        self.assertIsNotNone(authenticate(username="nuovo", password="Ombra-Lunga-42"))

    def test_a_duplicate_name_or_username_is_refused(self):
        self._player()
        with self.assertRaises(ApiError) as name_error:
            self._player(username="altro")
        self.assertEqual(name_error.exception.code, "players.name_taken")
        with self.assertRaises(ApiError) as username_error:
            self._player(name="Altro")
        self.assertEqual(username_error.exception.code, "players.username_taken")

    def test_a_weak_password_is_refused_before_the_account_exists(self):
        with self.assertRaises(ApiError) as error:
            self._player(password="123")
        self.assertEqual(error.exception.code, "players.password_weak")
        self.assertFalse(get_user_model().objects.filter(username="nuovo").exists())
        self.assertFalse(Giocatore.objects.filter(nome="Nuovo").exists())

    def test_changing_the_password_replaces_the_old_one(self):
        player = self._player()

        set_player_password(self.admin_user, self.admin, player.id, "Altra-Password-7")

        self.assertIsNone(authenticate(username="nuovo", password="Ombra-Lunga-42"))
        self.assertIsNotNone(authenticate(username="nuovo", password="Altra-Password-7"))

    def test_editing_a_player_renames_the_profile_and_the_account(self):
        player = self._player()

        update_player(self.admin_user, self.admin, player.id, {
            "name": "Rinominato",
            "displayName": "Alias Nuovo",
            "username": "rinominato",
            "role": Giocatore.ROLE_MASTER,
            "activeCampaignId": "",
            "accountActive": True,
        })

        player.refresh_from_db()
        self.assertEqual(player.nome, "Rinominato")
        self.assertEqual(player.role, Giocatore.ROLE_MASTER)
        self.assertIsNone(player.active_campaign_id)
        self.assertEqual(player.user.get_username(), "rinominato")

    def test_an_admin_cannot_change_or_disable_their_own_access(self):
        with self.assertRaises(ApiError) as role_error:
            update_player(self.admin_user, self.admin, self.admin.id, {"role": Giocatore.ROLE_USER})
        self.assertEqual(role_error.exception.code, "players.self_role_locked")
        with self.assertRaises(ApiError) as disable_error:
            update_player(self.admin_user, self.admin, self.admin.id, {"accountActive": False})
        self.assertEqual(disable_error.exception.code, "players.self_disable_locked")

    def test_assigning_characters_replaces_the_roster_and_repairs_the_active_one(self):
        player = self._player()

        assign_player_characters(self.admin_user, self.admin, player.id, [self.hero.id, self.rival.id])
        player.refresh_from_db()
        self.assertEqual(player.character_ids, [self.hero.id, self.rival.id])
        self.assertEqual(player.active_character_id, self.hero.id)

        assign_player_characters(self.admin_user, self.admin, player.id, [self.rival.id])
        player.refresh_from_db()
        self.assertEqual(player.character_ids, [self.rival.id])
        self.assertEqual(player.active_character_id, self.rival.id)

        assign_player_characters(self.admin_user, self.admin, player.id, [])
        player.refresh_from_db()
        self.assertEqual(player.character_ids, [])
        self.assertIsNone(player.active_character_id)

    def test_assigning_a_requested_character_approves_the_pending_request(self):
        player = self._player()
        request = CharacterAssignmentRequest.objects.create(giocatore=player, personaggio=self.hero)

        assign_player_characters(self.admin_user, self.admin, player.id, [self.hero.id])

        request.refresh_from_db()
        self.assertEqual(request.status, CharacterAssignmentRequest.STATUS_APPROVED)
        self.assertIsNotNone(request.reviewed_at)

    def test_an_unknown_character_is_refused_without_touching_the_roster(self):
        player = self._player()
        assign_player_characters(self.admin_user, self.admin, player.id, [self.hero.id])

        with self.assertRaises(ApiError) as error:
            assign_player_characters(self.admin_user, self.admin, player.id, [self.hero.id, 987654])

        self.assertEqual(error.exception.status, 404)
        player.refresh_from_db()
        self.assertEqual(player.character_ids, [self.hero.id])

    def test_the_overview_reports_accounts_rosters_and_shared_characters(self):
        player = self._player()
        assign_player_characters(self.admin_user, self.admin, player.id, [self.hero.id])
        assign_player_characters(self.admin_user, self.admin, self.admin.id, [self.hero.id])

        overview = player_management_overview(self.admin)

        self.assertEqual(overview["currentPlayerId"], self.admin.id)
        entry = next(row for row in overview["players"] if row["id"] == player.id)
        self.assertEqual(entry["username"], "nuovo")
        self.assertTrue(entry["hasAccount"])
        self.assertEqual([character["name"] for character in entry["characters"]], ["Illaoi"])
        shared = next(row for row in overview["characters"] if row["id"] == self.hero.id)
        self.assertEqual(sorted(shared["assignedTo"]), ["Il Capo", "Nuovo Giocatore"])

    def test_an_assignment_outside_the_active_campaign_is_flagged(self):
        other_campaign = DatiCampagna.objects.create(nome="Altrove")
        outsider = Personaggio.objects.create(
            nome="Straniero", nome_interno="straniero", tipologia="giocabile", campagna=other_campaign,
        )
        player = self._player()
        assign_player_characters(self.admin_user, self.admin, player.id, [outsider.id])

        entry = next(
            row for row in player_management_overview(self.admin)["players"] if row["id"] == player.id
        )

        self.assertFalse(entry["characters"][0]["inActiveCampaign"])


class PlayerManagementApiTests(TestCase):
    """The typed contract: the endpoint and every action of the Gestione Player screen."""

    def setUp(self):
        self.campaign = DatiCampagna.objects.create(nome="Sanguine")
        self.admin_user = get_user_model().objects.create_user(username="capo", password="Fortissima-1")
        self.admin = Giocatore.objects.create(
            user=self.admin_user, nome="capo", role=Giocatore.ROLE_ADMIN, active_campaign=self.campaign,
        )
        self.hero = Personaggio.objects.create(
            nome="Illaoi", nome_interno="illaoi", tipologia="giocabile", campagna=self.campaign,
        )
        self.client.force_login(self.admin_user)

    def command(self, action, payload):
        return self.client.post(
            "/api/v1/actions",
            data=json.dumps({"action": action, "requestId": "players-test", "payload": payload}),
            content_type="application/json",
        )

    def test_the_overview_endpoint_is_reserved_to_admins(self):
        response = self.client.get("/api/v1/management/players")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["players"])

        self.admin.role = Giocatore.ROLE_MASTER
        self.admin.save(update_fields=["role", "updated_at"])
        self.assertEqual(self.client.get("/api/v1/management/players").status_code, 403)

    def test_every_write_action_answers_with_the_refreshed_overview(self):
        created = self.command("management.players.create", {"values": {
            "name": "Nuovo",
            "displayName": "Nuovo Giocatore",
            "username": "nuovo",
            "password": "Ombra-Lunga-42",
            "role": Giocatore.ROLE_USER,
            "activeCampaignId": str(self.campaign.id),
        }})
        self.assertEqual(created.status_code, 200)
        overview = created.json()["data"]["management"]
        player_id = overview["savedPlayerId"]
        self.assertIn("Nuovo", [row["name"] for row in overview["players"]])

        updated = self.command("management.players.update", {
            "playerId": player_id,
            "values": {"displayName": "Alias", "role": Giocatore.ROLE_MASTER},
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["data"]["management"]["savedPlayerId"], player_id)

        assigned = self.command("management.players.assignCharacters", {
            "playerId": player_id,
            "characterIds": [self.hero.id],
        })
        self.assertEqual(assigned.status_code, 200)
        entry = next(row for row in assigned.json()["data"]["management"]["players"] if row["id"] == player_id)
        self.assertEqual([character["id"] for character in entry["characters"]], [self.hero.id])

        password = self.command("management.players.setPassword", {"playerId": player_id, "password": "Terza-Chiave-9"})
        self.assertEqual(password.status_code, 200)
        self.assertIsNotNone(authenticate(username="nuovo", password="Terza-Chiave-9"))

    def test_a_rejected_password_answers_with_a_field_error(self):
        response = self.command("management.players.create", {"values": {
            "name": "Debole", "username": "debole", "password": "1234", "role": Giocatore.ROLE_USER,
        }})

        self.assertEqual(response.status_code, 400)
        error = response.json()["errors"][0]
        self.assertEqual(error["code"], "players.password_weak")
        self.assertEqual(error["field"], "password")


class AssignedRosterVisibilityTests(TestCase):
    """The Sala principale roster: assigned characters only, unless master or admin."""

    def setUp(self):
        self.campaign = DatiCampagna.objects.create(nome="Sanguine")
        self.hero = Personaggio.objects.create(
            nome="Illaoi", nome_interno="illaoi", tipologia="giocabile", campagna=self.campaign,
        )
        self.other = Personaggio.objects.create(
            nome="Ra'Zirr",
            nome_interno="razirr",
            tipologia="giocabile",
            campagna=self.campaign,
            metadata={"seed_kind": "poc_personaggio"},
        )

    def test_a_player_without_assignments_sees_no_characters(self):
        player = Giocatore.objects.create(nome="solo", role=Giocatore.ROLE_USER, active_campaign=self.campaign)

        self.assertEqual(ordered_personaggi_for(player), [])

    def test_a_player_sees_only_the_assigned_characters(self):
        player = Giocatore.objects.create(
            nome="assegnato",
            role=Giocatore.ROLE_USER,
            active_campaign=self.campaign,
            character_ids=[self.hero.id],
        )

        self.assertEqual([entry.id for entry in ordered_personaggi_for(player)], [self.hero.id])

    def test_a_master_sees_every_character_of_the_campaign(self):
        master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER, active_campaign=self.campaign)

        visible = {entry.id for entry in ordered_personaggi_for(master, include_all=True)}

        self.assertEqual(visible, {self.hero.id, self.other.id})

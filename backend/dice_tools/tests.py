import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from backend.characters.models import Personaggio
from backend.core.models import Giocatore
from backend.media_library.models import UploadedImage

from .models import DiceRollRecord, DiceSet, DiceTexture


class QuickToolsApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_minimum_data", verbosity=0)

    def setUp(self):
        self.giocatore = Giocatore.objects.get(nome="local_master")
        self.client.force_login(self.giocatore.user)
        self.character = Personaggio.objects.get(nome_interno="poc_darion_frondaluna")
        self.other_character = Personaggio.objects.get(nome_interno="poc_livia_occhiodoro")

    def command(self, action, payload, request_id="quick-tools-test"):
        return self.client.post(
            "/api/v1/actions",
            data=json.dumps({"action": action, "requestId": request_id, "context": {"screen": "dice"}, "payload": payload}),
            content_type="application/json",
        )

    def login_admin(self):
        User = get_user_model()
        admin = User.objects.create_superuser(username="quick_tools_admin", password="test-pass")
        Giocatore.objects.create(
            user=admin,
            nome=admin.username,
            display_name="Quick Tools Admin",
            role=Giocatore.ROLE_ADMIN,
        )
        self.client.force_login(admin)
        return admin

    def test_seeded_sets_are_available_and_seed_is_idempotent(self):
        response = self.client.get("/api/v1/dice-sets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]["diceSets"]), 4)
        edited = DiceSet.objects.get(slug="crimson")
        edited.name = "Nome amministratore"
        edited.save(update_fields=["name", "updated_at"])
        call_command("seed_minimum_data", verbosity=0)
        edited.refresh_from_db()
        self.assertEqual(edited.name, "Nome amministratore")

    def test_only_admin_can_create_sets_and_new_set_becomes_a_setting_choice(self):
        values = {"name": "Dweomer Dwemer", "description": "Bronzo e vapore.", "dice": [6, 10, 20], "surfaceColor": "#6f512d", "accentColor": "#d8a74c", "textColor": "#fff2cc", "isActive": True}
        forbidden = self.command("diceSets.create", {"values": values})
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json()["errors"][0]["code"], "dice_sets.forbidden")

        self.login_admin()
        created = self.command("diceSets.create", {"values": values})
        self.assertEqual(created.status_code, 200)
        dice_set = DiceSet.objects.get(name="Dweomer Dwemer")
        self.assertEqual(dice_set.dice, [6, 10, 20])
        settings = self.client.get("/api/settings/").json()["data"]
        definition = next(entry for entry in settings["settings"] if entry["key"] == "dice.default_set")
        self.assertIn({"value": dice_set.slug, "label": dice_set.name}, definition["choices"])

    def test_admin_can_assign_one_positioned_texture_to_each_die(self):
        admin = self.login_admin()
        texture = UploadedImage.objects.create(
            title="Marmo runico",
            folder="user_media",
            file="v2/images/user_media/marmo-runico.webp",
            usage_type="dice_texture",
            source="test",
            metadata={"ownerUserId": admin.id, "originalName": "marmo-runico.webp", "mimeType": "image/webp"},
        )
        values = {
            "name": "Rune di marmo",
            "dice": [6, 20],
            "surfaceColor": "#27343d",
            "accentColor": "#c8aa6e",
            "textColor": "#fff8dc",
            "textures": [{"sides": 20, "imageId": texture.id, "offsetX": 12, "offsetY": -8, "scale": 145, "rotation": 18}],
        }

        response = self.command("diceSets.create", {"values": values})

        self.assertEqual(response.status_code, 200)
        dice_set = DiceSet.objects.get(name="Rune di marmo")
        saved = DiceTexture.objects.get(dice_set=dice_set, sides=20)
        self.assertEqual(saved.image_id, texture.id)
        self.assertEqual(saved.scale, 145)
        serialized = next(entry for entry in response.json()["data"]["diceSets"]["diceSets"] if entry["id"] == dice_set.id)
        self.assertEqual(serialized["textures"][0]["imageUrl"], "/media/v2/images/user_media/marmo-runico.webp")
        self.assertEqual(serialized["textures"][0]["rotation"], 18)

        duplicate = {**values, "name": "Rune duplicate", "textures": [values["textures"][0], values["textures"][0]]}
        invalid = self.command("diceSets.create", {"values": duplicate})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["errors"][0]["code"], "dice_sets.texture_duplicate")

    @patch("backend.dice_tools.services.secrets.randbelow", return_value=19)
    def test_roll_is_server_generated_and_validated(self, randbelow):
        dice_set = DiceSet.objects.get(slug="crimson")
        response = self.command("dice.roll", {"sides": 20, "count": 2, "modifier": 3, "diceSetId": dice_set.id, "characterId": self.character.id})
        self.assertEqual(response.status_code, 200)
        result = response.json()["data"]["diceRoll"]
        self.assertEqual(result["rolls"], [20, 20])
        self.assertEqual(result["total"], 43)
        self.assertEqual(result["notation"], "2d20+3")
        self.assertEqual(randbelow.call_count, 2)
        recorded = DiceRollRecord.objects.get()
        self.assertEqual(recorded.giocatore, self.giocatore)
        self.assertEqual(recorded.personaggio, self.character)
        self.assertEqual(recorded.character_name, self.character.nome)
        self.assertEqual(recorded.rolls, [20, 20])
        self.assertEqual(recorded.total, 43)

        invalid = self.command("dice.roll", {"sides": 7, "count": 1, "modifier": 0})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["errors"][0]["code"], "dice.invalid_sides")

    def test_group_history_is_master_only_and_includes_quick_and_competence_rolls(self):
        quick = self.command("dice.roll", {
            "sides": 20,
            "count": 1,
            "modifier": 2,
            "characterId": self.character.id,
        })
        competence = self.command("competencies.roll", {
            "characterId": self.other_character.id,
            "competenceKey": "scalare",
            "technique": "standard",
        })
        self.assertEqual(quick.status_code, 200, quick.content)
        self.assertEqual(competence.status_code, 200, competence.content)

        response = self.client.get("/api/v1/dice-history")
        self.assertEqual(response.status_code, 200, response.content)
        rolls = response.json()["data"]["rolls"]
        self.assertEqual(len(rolls), 2)
        self.assertEqual({roll["source"] for roll in rolls}, {"quick", "competence"})
        self.assertEqual({roll["characterName"] for roll in rolls}, {self.character.nome, self.other_character.nome})
        self.assertTrue(all(roll["playerName"] == self.giocatore.display_name for roll in rolls))
        self.assertTrue(all(roll["rolledAt"] for roll in rolls))
        self.assertEqual(response.json()["data"]["limit"], 100)

        self.giocatore.role = Giocatore.ROLE_USER
        self.giocatore.save(update_fields=["role", "updated_at"])
        forbidden = self.client.get("/api/v1/dice-history")
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json()["errors"][0]["code"], "dice_history.forbidden")

    def test_group_history_returns_only_the_newest_100_rolls(self):
        for index in range(105):
            DiceRollRecord.objects.create(
                giocatore=self.giocatore,
                player_name=self.giocatore.display_name,
                personaggio=self.character,
                character_name=self.character.nome,
                source=DiceRollRecord.SOURCE_QUICK,
                label=f"Tiro {index}",
                notation="1d6",
                rolls=[1],
                total=index,
            )

        rolls = self.client.get("/api/v1/dice-history").json()["data"]["rolls"]

        self.assertEqual(len(rolls), 100)
        self.assertEqual(rolls[0]["total"], 104)
        self.assertEqual(rolls[-1]["total"], 5)

    def test_note_sections_are_shared_with_the_character_sheet_and_validate_input(self):
        initial = self.client.get(f"/api/v1/characters/{self.character.id}/notes")
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(set(initial.json()["data"]["sections"]), {"zaino", "combat", "competenze", "crafting", "viaggio", "appunti", "missioni", "background"})
        other_zaino = self.other_character.note.zaino

        updated = self.command("notes.updateSection", {"characterId": self.character.id, "section": "zaino", "content": "Tre sigilli recuperati. Portare corde e torce."})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["data"]["notes"]["sections"]["zaino"], "Tre sigilli recuperati. Portare corde e torce.")
        sheet = self.client.get(f"/api/v1/characters/{self.character.id}/sheet").json()["data"]["character"]
        self.assertEqual(sheet["notes"]["zaino"], "Tre sigilli recuperati. Portare corde e torce.")
        call_command("seed_minimum_data", verbosity=0)
        self.character.note.refresh_from_db()
        self.assertEqual(self.character.note.zaino, "Tre sigilli recuperati. Portare corde e torce.")
        self.other_character.note.refresh_from_db()
        self.assertEqual(self.other_character.note.zaino, other_zaino)

        invalid = self.command("notes.updateSection", {"characterId": self.character.id, "section": "titoli", "content": "No"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["errors"][0]["code"], "notes.invalid_section")

        too_long = self.command("notes.updateSection", {"characterId": self.character.id, "section": "appunti", "content": "x" * 30001})
        self.assertEqual(too_long.status_code, 400)
        self.assertEqual(too_long.json()["errors"][0]["code"], "notes.section_too_long")

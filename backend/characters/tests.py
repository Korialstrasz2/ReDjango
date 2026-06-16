import json

from django.test import TestCase

from .models import Character


def envelope(action: str, request_id: str, payload: dict | None = None) -> str:
    return json.dumps(
        {
            "action": action,
            "requestId": request_id,
            "context": {"screen": "characters"},
            "payload": payload or {},
            "meta": {"clientVersion": "test"},
        }
    )


class CharacterApiContractTests(TestCase):
    def test_create_character_accepts_envelope_and_returns_envelope(self):
        response = self.client.post(
            "/api/characters/",
            data=envelope(
                "characters.create",
                "char-create-1",
                {
                    "name": "Seren",
                    "ancestry": "Elf",
                    "archetype": "Scholar",
                    "level": 2,
                    "stats": {"mind": 4},
                    "resources": {"mana": 9},
                },
            ),
            content_type="application/json",
            HTTP_X_REDJANGO_ACTION="characters.create",
            HTTP_X_REDJANGO_REQUEST_ID="char-create-1",
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["requestId"], "char-create-1")
        self.assertEqual(body["events"][0]["type"], "character.created")
        character = body["data"]["character"]
        self.assertEqual(character["name"], "Seren")
        self.assertEqual(character["stats"]["might"], 1)
        self.assertEqual(character["stats"]["mind"], 4)
        self.assertEqual(character["resources"]["mana"], 9)
        self.assertTrue(Character.objects.filter(name="Seren").exists())

    def test_invalid_character_payload_returns_structured_error(self):
        response = self.client.post(
            "/api/characters/",
            data=envelope("characters.create", "char-invalid-1", {"name": "Bad Level", "level": "not-a-number"}),
            content_type="application/json",
            HTTP_X_REDJANGO_ACTION="characters.create",
            HTTP_X_REDJANGO_REQUEST_ID="char-invalid-1",
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["requestId"], "char-invalid-1")
        self.assertEqual(body["errors"][0]["code"], "character.level_invalid")
        self.assertEqual(body["errors"][0]["field"], "level")

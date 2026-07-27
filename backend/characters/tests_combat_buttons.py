from django.test import TestCase

from backend.characters.models import BottoneCombat, Personaggio
from backend.characters.services.combat_buttons import (
    MAX_COMBAT_BUTTONS_PER_CHARACTER,
    combat_button_configuration_payload,
    create_combat_button,
    update_combat_button,
)
from backend.core.api import ApiError
from backend.core.models import Giocatore


class CombatButtonServiceTests(TestCase):
    def setUp(self):
        self.character = Personaggio.objects.create(nome="Eroina", nome_interno="eroina-bottoni")

    def values(self, name="Assalto"):
        return {
            "name": name,
            "helpText": "Vale per il prossimo attacco.",
            "modifiers": {
                "attackBonus": 2,
                "damageBonus": 3,
                "damageTierBonus": 1,
                "penetrationFlat": 4,
                "penetrationPercent": 5,
            },
            "public": False,
            "active": True,
            "keepActiveInCombat": False,
        }

    def test_create_and_update_preserve_defaults_and_all_five_modifiers(self):
        button = create_combat_button(self.character.id, self.values())

        self.assertEqual(button.bonus_attacco, 2)
        self.assertEqual(button.bonus_danno, 3)
        self.assertEqual(button.bonus_tier, 1)
        self.assertEqual(button.perforazione, 4)
        self.assertEqual(button.perforazione_percentuale, 5)
        self.assertFalse(button.pubblico)
        self.assertTrue(button.attivo)
        self.assertFalse(button.tieni_attivo_in_combat)

        updated_values = self.values("Assalto condiviso")
        updated_values.update({"public": True, "keepActiveInCombat": True})
        updated = update_combat_button(self.character.id, button.id, updated_values)
        self.assertTrue(updated.pubblico)
        self.assertTrue(updated.tieni_attivo_in_combat)

    def test_character_cannot_configure_more_than_twelve_buttons(self):
        for index in range(MAX_COMBAT_BUTTONS_PER_CHARACTER):
            create_combat_button(self.character.id, self.values(f"Bottone {index + 1}"))

        with self.assertRaises(ApiError) as error:
            create_combat_button(self.character.id, self.values("Tredicesimo"))

        self.assertEqual(error.exception.code, "combat_buttons.limit_reached")

    def test_public_buttons_are_visible_but_not_editable_from_another_character(self):
        other = Personaggio.objects.create(nome="Alleato", nome_interno="alleato-bottoni")
        values = self.values("Condiviso")
        values["public"] = True
        public_button = create_combat_button(self.character.id, values)

        payload = combat_button_configuration_payload(other)

        self.assertEqual(payload["own"], [])
        self.assertEqual(payload["public"][0]["id"], public_button.id)
        self.assertFalse(payload["public"][0]["canEdit"])

    def test_deleting_character_deletes_private_buttons_and_reassigns_public_ones(self):
        replacement = Personaggio.objects.create(nome="Recente", nome_interno="recente-bottoni")
        Giocatore.objects.create(
            nome="giocatore-recente",
            active_character=replacement,
            character_ids=[replacement.id],
        )
        private_button = create_combat_button(self.character.id, self.values("Privato"))
        public_values = self.values("Pubblico")
        public_values["public"] = True
        public_button = create_combat_button(self.character.id, public_values)

        self.character.delete()

        self.assertFalse(BottoneCombat.objects.filter(pk=private_button.id).exists())
        public_button.refresh_from_db()
        self.assertEqual(public_button.personaggio_id, replacement.id)


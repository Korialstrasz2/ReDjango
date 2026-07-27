from django.test import TestCase

from backend.characters.models import Equip, Personaggio
from backend.characters.selectors import serialize_item
from backend.characters.services.inventory_rules import (
    InventoryRuleError,
    active_equipped_weapon,
    equipment_dual_wield,
    item_compatible_with_equipment_slot,
    validate_hand_configuration,
)
from backend.characters.services.refresh_personaggio import collect_personaggio_effect_payloads
from backend.core.models import Oggetto, TipoArma


class DualWieldRulesTests(TestCase):
    def weapon(self, name: str, length: str, attack: int) -> Oggetto:
        return Oggetto.objects.create(
            nome=name,
            tipo_1="arma",
            weapon_profile={"length": length, "combatMode": "melee"},
            effects=[{"target": "attacco", "operation": "add", "value": attack}],
        )

    def test_only_one_handed_weapons_fit_the_shield_slot(self):
        short = self.weapon("Arma corta test", "corta", 1)
        long = self.weapon("Arma lunga test", "lunga", 2)
        self.assertTrue(item_compatible_with_equipment_slot(short, "scudo"))
        self.assertFalse(item_compatible_with_equipment_slot(long, "scudo"))

        equip = Equip(nome="Equip due mani test", arma=long, scudo=short)
        with self.assertRaises(InventoryRuleError):
            validate_hand_configuration(equip)

    def test_only_primary_dual_wield_weapon_contributes_item_effects(self):
        main = self.weapon("Primaria effetti test", "corta", 1)
        offhand = self.weapon("Secondaria effetti test", "media", 7)
        equip = Equip.objects.create(nome="Equip doppio test", arma=main, scudo=offhand)
        character = Personaggio.objects.create(nome="Doppio test", nome_interno="doppio-test", equip=equip)

        self.assertTrue(equipment_dual_wield(equip))
        self.assertEqual(active_equipped_weapon(equip), main)
        payloads = collect_personaggio_effect_payloads(character)
        self.assertEqual([entry["source"] for entry in payloads], [f"equip.arma:{main.nome}"])

        equip.arma_primaria_slot = "scudo"
        equip.save(update_fields=["arma_primaria_slot", "updated_at"])
        character.refresh_from_db()
        payloads = collect_personaggio_effect_payloads(character)
        self.assertEqual(active_equipped_weapon(character.equip), offhand)
        self.assertEqual([entry["source"] for entry in payloads], [f"equip.scudo:{offhand.nome}"])

    def test_serialized_weapon_axes_use_the_saved_item_profile(self):
        weapon_type = TipoArma.objects.create(
            nome="Tipo serializzazione obsoleto",
            lunghezza="corta",
            potenza="potente",
            bonus_1="Primo bonus Elder",
            bonus_2="Secondo bonus Elder",
            rules={"profile": {"length": "corta", "power": "potente"}},
        )
        weapon = Oggetto.objects.create(
            nome="Arma serializzazione profilo",
            tipo_1="arma",
            tipo_arma=weapon_type,
            weapon_profile={"length": "media", "power": "media", "damageType": "taglio"},
        )

        payload = serialize_item(weapon)

        self.assertEqual(payload["weaponLength"], "media")
        self.assertEqual(payload["weaponPower"], "media")
        self.assertEqual(payload["weaponTypeBonuses"], ["Primo bonus Elder", "Secondo bonus Elder"])
        self.assertEqual(payload["weaponProfile"]["damageType"], "taglio")

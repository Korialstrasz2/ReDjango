from django.test import SimpleTestCase

from backend.core.weapon_presets import WEAPON_TYPE_PRESETS
from backend.core.weapon_rules import suggested_weapon_values


class WeaponRuleTests(SimpleTestCase):
    def test_all_elder_weapon_types_are_available_as_presets(self):
        self.assertEqual(len(WEAPON_TYPE_PRESETS), 46)
        self.assertEqual(len({entry["name"] for entry in WEAPON_TYPE_PRESETS}), 46)

    def test_suggestions_combine_independent_axes_and_material_once(self):
        suggested = suggested_weapon_values({
            "heaviness": "leggera",
            "length": "corta",
            "power": "potente",
            "damageType": "taglio",
            "materialFamily": "leggera",
            "material": "elfico",
            "materialTier": 3,
            "costBand": "A",
        })
        effects = {entry["target"]: entry["value"] for entry in suggested["effects"]}
        self.assertEqual(effects, {"attacco": 5, "pa": 4, "tier": -5, "ap": 3})
        self.assertEqual(suggested["paPerAttacco"], 3)
        self.assertEqual((suggested["price"], suggested["weight"]), (350, 4))


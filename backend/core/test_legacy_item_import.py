from django.test import SimpleTestCase

from backend.core.legacy_item_import import clean_legacy_value, convert_effect


class LegacyItemEffectConversionTests(SimpleTestCase):
    def test_vuoto_is_saved_as_blank(self):
        self.assertEqual(clean_legacy_value(" Vuoto "), "")

    def test_numeric_character_effect_is_converted(self):
        self.assertEqual(
            convert_effect("Personaggio.attacco_extra -3"),
            {"target": "attacco", "operation": "subtract", "value": 3, "source": "elder_import"},
        )

    def test_competence_bonus_is_converted(self):
        self.assertEqual(
            convert_effect("Scalare + 1"),
            {"target": "competenza.scalare", "operation": "add", "value": 1, "source": "elder_import"},
        )

    def test_level_formula_effect_is_converted(self):
        self.assertEqual(
            convert_effect("Personaggio.attacco_extra + (f)Personaggio.livello +2"),
            {
                "target": "attacco",
                "operation": "add",
                "value": "personaggio.livello + 2",
                "source": "elder_import",
            },
        )

    def test_legacy_magic_target_is_converted_to_the_unified_stat(self):
        self.assertEqual(
            convert_effect("Personaggio.ogni_pa_x_mana_caos + 1,5"),
            {
                "target": "ogni_pa_x_mana",
                "operation": "add",
                "value": 1.5,
                "source": "elder_import",
            },
        )

    def test_descriptive_rule_is_retained_not_guessed(self):
        self.assertIsNone(convert_effect("Cast Silenzioso SI"))

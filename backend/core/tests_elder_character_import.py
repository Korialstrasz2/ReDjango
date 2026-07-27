from django.test import SimpleTestCase

from backend.core.management.commands.import_elder_characters import (
    converted_effect_operations,
    normalized_elder_totals,
)


class ElderEffectConversionTests(SimpleTestCase):
    def test_order_and_chaos_pair_is_averaged_into_one_operation(self):
        operations, skipped = converted_effect_operations({
            "effetti": [
                {"name": "ogni_en_x_mana_ordine", "operation": "+", "value": "4"},
                {"name": "ogni_en_x_mana_caos", "operation": "+", "value": "8"},
            ]
        })

        self.assertEqual(skipped, [])
        self.assertEqual(operations, [{"target": "ogni_en_x_mana", "operation": "add", "value": "6"}])

    def test_formula_values_use_redjango_expression_contexts(self):
        operations, skipped = converted_effect_operations({
            "effetti": [
                {"name": "potere", "operation": "+", "value": "(f)Personaggio.saggezza - 10"},
                {"name": "mana", "operation": "+", "value": "(f)Personaggio.livello * 2.5"},
            ]
        })

        self.assertEqual(skipped, [])
        self.assertEqual(operations[0]["value"], "final.saggezza - 10")
        self.assertEqual(operations[1]["value"], "personaggio.livello * 2.5")

    def test_reconciliation_totals_apply_the_same_order_chaos_rule(self):
        totals = normalized_elder_totals({
            "forza_tot": 12,
            "en_per_mana_ordine_tot": 2,
            "en_per_mana_caos_tot": 4,
            "tipo_danno_arma": "taglio",
        })

        self.assertEqual(totals, {"forza": 12.0, "en_per_mana": 3.0})

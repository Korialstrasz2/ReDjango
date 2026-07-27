from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from backend.characters.models import Personaggio, SkillPersonaggio
from backend.core.legacy_skill_import import (
    ImportRun,
    _active,
    _apply_approved_resolution,
    _approved_generated_passives,
    _passive,
    _requirement_source_ids,
    _spell,
    apply_import_run,
    parse_spell_formula,
)
from backend.core.models import FamigliaSkill, GruppoFamiglieSkill, Skill
from backend.core.skill_pricing import skill_price
from backend.core.skill_requirements import structured_requirement_reasons


class SkillPricingTests(TestCase):
    def setUp(self):
        group, _created = GruppoFamiglieSkill.objects.get_or_create(
            nome="Generali",
            defaults={"slug": "generali"},
        )
        self.family = FamigliaSkill.objects.create(nome="Test prezzi", gruppo=group)
        self.character = Personaggio.objects.create(
            nome="Prezzi",
            nome_interno="test_prezzi",
            livello=10,
        )

    def test_elder_price_curve_and_color_discount_are_restored(self):
        skill = Skill.objects.create(
            nome="Skill blu",
            slug="skill-blu",
            numero=2_000_001,
            famiglia=self.family,
            costo_pe=10,
            tipo_pe="blue",
        )
        self.assertEqual(skill_price(skill, self.character)["calculatedCost"], 15)

        previous = Skill.objects.create(
            nome="Spesa blu precedente",
            slug="spesa-blu-precedente",
            numero=2_000_002,
            famiglia=self.family,
            costo_pe=50,
            tipo_pe="blue",
        )
        SkillPersonaggio.objects.create(
            personaggio=self.character,
            skill=previous,
            spesa_pe={"general": 0, "red": 0, "green": 0, "blue": 50},
        )
        pricing = skill_price(skill, self.character)
        self.assertEqual(pricing["baseCost"], 10)
        self.assertEqual(pricing["calculatedCost"], 12)
        self.assertEqual(pricing["spentXpInCategory"], 50)

    def test_discounted_fractional_cost_always_rounds_down(self):
        skill = Skill.objects.create(
            nome="Skill verde frazionaria",
            slug="skill-verde-frazionaria",
            numero=2_000_004,
            famiglia=self.family,
            costo_pe=4,
            tipo_pe="green",
        )
        previous = Skill.objects.create(
            nome="Spesa verde precedente",
            slug="spesa-verde-precedente",
            numero=2_000_005,
            famiglia=self.family,
            costo_pe=60,
            tipo_pe="green",
        )
        ownership = SkillPersonaggio.objects.create(
            personaggio=self.character,
            skill=previous,
            spesa_pe={"general": 0, "red": 0, "green": 60, "blue": 0},
        )
        self.assertEqual(skill_price(skill, self.character)["calculatedCost"], 4)  # raw result: 4.8

        ownership.spesa_pe["green"] = 90
        ownership.save(update_fields=["spesa_pe", "updated_at"])
        self.assertEqual(skill_price(skill, self.character)["calculatedCost"], 4)  # raw result: 4.2

    def test_all_color_skills_keep_the_legacy_zero_color_discount_behavior(self):
        skill = Skill.objects.create(
            nome="Skill tutti",
            slug="skill-tutti",
            numero=2_000_003,
            famiglia=self.family,
            costo_pe=10,
            tipo_pe="all",
        )
        self.assertEqual(skill_price(skill, self.character)["spentXpInCategory"], 0)

    def test_owned_skill_discount_is_automatic_and_disappears_with_ownership(self):
        target = Skill.objects.create(
            nome="Skill blu scontabile",
            slug="skill-blu-scontabile",
            numero=2_000_006,
            famiglia=self.family,
            costo_pe=10,
            tipo_pe="blue",
        )
        discount_skill = Skill.objects.create(
            nome="Smart test",
            slug="smart-test",
            numero=2_000_007,
            famiglia=self.family,
            costo_pe=5,
            tipo_pe="all",
            metadata={
                "pricingModifier": {
                    "type": "owned_skill_flat_discount",
                    "amount": 1,
                    "minimumBaseCost": 6,
                    "xpTypes": ["blue"],
                }
            },
        )
        normal_price = skill_price(target, self.character)["calculatedCost"]
        ownership = SkillPersonaggio.objects.create(
            personaggio=self.character,
            skill=discount_skill,
            spesa_pe={"general": 5},
        )

        discounted = skill_price(target, self.character)
        self.assertEqual(discounted["calculatedCost"], normal_price - 1)
        self.assertEqual(discounted["ownedSkillDiscount"], 1)
        self.assertEqual(discounted["ownedSkillDiscountSources"], ["Smart test"])

        ownership.delete()
        restored = skill_price(target, self.character)
        self.assertEqual(restored["calculatedCost"], normal_price)
        self.assertEqual(restored["ownedSkillDiscount"], 0)

    def test_structured_characteristic_requirement_uses_current_character_total(self):
        skill = Skill.objects.create(
            nome="Smart requisito",
            slug="smart-requisito",
            numero=2_000_008,
            famiglia=self.family,
            metadata={
                "unlockRequirements": [
                    {"type": "stat_minimum", "stat": "intelligenza", "minimum": 15}
                ]
            },
        )
        self.character.tot = {**self.character.tot, "intelligenza": 14}
        self.assertEqual(
            structured_requirement_reasons(self.character, skill),
            ["Richiede Intelligenza almeno 15 (attuale: 14)."],
        )
        self.character.tot["intelligenza"] = 15
        self.assertEqual(structured_requirement_reasons(self.character, skill), [])


class SpellFormulaImportTests(TestCase):
    def test_elder_linear_formulas_are_normalized_without_eval(self):
        self.assertEqual(
            parse_spell_formula("M/4"),
            {"base_mana": Decimal("0"), "effect_per_mana": Decimal("0.25")},
        )
        self.assertEqual(
            parse_spell_formula("(m-10) /7"),
            {"base_mana": Decimal("10"), "effect_per_mana": Decimal(1) / Decimal(7)},
        )
        self.assertEqual(
            parse_spell_formula("M*0,75"),
            {"base_mana": Decimal("0"), "effect_per_mana": Decimal("0.75")},
        )
        self.assertIsNone(parse_spell_formula("__import__('os')"))

    def test_formula_offset_and_minimum_cast_cost_remain_separate(self):
        blockers: list[str] = []
        spell = _spell(
            {
                "magia": 1,
                "formula_effetto": "(M-25)/15",
                "livello_magia": "Base",
                "raggio": "sé",
                "costo": "40 mana + 15 mana / d8",
                "costo_man": 25,
                "effetto_1": "1 Effetto = 15 Mana",
            },
            blockers,
        )

        self.assertIsNotNone(spell)
        self.assertEqual(spell["baseMana"], 25.0)
        self.assertEqual(spell["minimumMana"], 40.0)
        self.assertNotIn("spell_base_mana_conflicts_with_rules_cost", blockers)

    def test_generated_active_effect_is_ignored_when_formula_and_rules_agree(self):
        blockers: list[str] = []
        spell = _spell(
            {
                "magia": 1,
                "formula_effetto": "M/2",
                "livello_magia": "Base",
                "raggio": "touch",
                "costo": "1 mana / 0,5 pf",
                "costo_man": None,
                "effetto_1": "1 Effetto = 1 Mana",
            },
            blockers,
        )

        self.assertEqual(spell["effectPerMana"], 0.5)
        self.assertEqual(spell["minimumMana"], 1.0)
        self.assertNotIn("spell_formula_conflicts_with_active_effect", blockers)


class LegacySkillCandidateRepairTests(TestCase):
    def test_reviewed_alchemy_rank_generates_a_normal_character_effect(self):
        passives = _approved_generated_passives(
            {
                "id": 872,
                "nome": "Alchimia Vitale 2",
                "descrizione": "Aumenta di +0,2 il moltiplicatore dei reagenti rossi.",
            }
        )

        self.assertEqual(len(passives), 1)
        self.assertEqual(
            passives[0]["operations"],
            [
                {
                    "target": "moltiplicatore_reagenti_rossi",
                    "operation": "add",
                    "value": "0.2",
                    "condition": "",
                }
            ],
        )

    def test_focus_on_power_uses_concentration_modifier_after_review(self):
        blockers = ["passive_value_not_evidenced_in_prose"]
        passives = [
            {
                "operations": [
                    {"target": "potere", "operation": "add", "value": "final.mod_resistenza+0"}
                ]
            }
        ]

        _apply_approved_resolution({"id": 632}, passives, [], None, blockers)

        self.assertEqual(passives[0]["operations"][0]["value"], "final.mod_concentrazione+0")
        self.assertNotIn("passive_value_not_evidenced_in_prose", blockers)

    def test_reviewed_alternative_cost_stays_one_reminder(self):
        blockers = ["active_cost_conflict"]
        actions = [{"description": "legacy", "costs": {"energia": 6}}]

        _apply_approved_resolution(
            {
                "id": 47,
                "descrizione": (
                    "Il reroll costa 4 Energia. In alternativa, spendi 6 Energia per un reroll con vantaggio."
                ),
            },
            [],
            actions,
            None,
            blockers,
        )

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["costs"], {"energia": 4})
        self.assertIn("6 Energia", actions[0]["description"])
        self.assertNotIn("active_cost_conflict", blockers)

    def test_reviewed_spell_formula_replaces_only_the_conflicting_conversion(self):
        blockers = ["spell_formula_conflicts_with_active_effect"]
        spell = {"effectPerMana": 1.25, "minimumMana": 0}

        _apply_approved_resolution(
            {"id": 531},
            [],
            [],
            spell,
            blockers,
        )

        self.assertEqual(spell["effectPerMana"], 0.8)
        self.assertEqual(spell["minimumMana"], 1)
        self.assertNotIn("spell_formula_conflicts_with_active_effect", blockers)

    def test_review_candidates_are_suspended_from_an_older_import(self):
        group, _created = GruppoFamiglieSkill.objects.get_or_create(
            nome="Generali",
            defaults={"slug": "generali"},
        )
        family = FamigliaSkill.objects.create(nome="Test sospensione", gruppo=group)
        skill = Skill.objects.create(
            nome="Skill da sospendere",
            slug="skill-da-sospendere",
            numero=2_100_001,
            famiglia=family,
            metadata={"sourceProject": "the_elder_django", "sourceId": 47},
        )
        run = ImportRun(
            candidates=[{"sourceId": 47, "decision": "needs_review"}],
            summary={},
        )

        result = apply_import_run(run)

        skill.refresh_from_db()
        self.assertIsNotNone(skill.archived_at)
        self.assertEqual(result["reviewSkillsSuspended"], 1)

    def test_cost_aliases_are_fixed_but_variable_parts_stay_in_prose(self):
        blockers: list[str] = []
        warnings: list[str] = []
        actions = _active(
            {
                "active_id": 1,
                "active_name": "Costo misto",
                "active_description": "Costo: 3 Energia e 3+ Potere.",
                "descrizione": "Costo: 3 Energia e 3+ Potere.",
                "costo": "3 Energia, 3+ Potere",
                "costo_en": 3,
                "costo_pow": 3,
                "costo_man": None,
                "costo_pa": None,
                "costo_pf": None,
                "costo_st": None,
                "effetto_attivabile": "{}",
                "active_icon": None,
                "durata_turni": None,
            },
            blockers,
            warnings,
        )

        self.assertEqual(actions[0]["costs"], {"energia": 3})
        self.assertNotIn("active_cost_conflict", blockers)

    def test_genuine_cost_disagreement_stays_suspended(self):
        blockers: list[str] = []
        _active(
            {
                "active_id": 2,
                "active_name": "Costo in conflitto",
                "active_description": "Il costo diventa 4 Energia. Costo: 6 Energia",
                "descrizione": "Il costo diventa 4 Energia.",
                "costo": "6 Energia",
                "costo_en": 4,
                "costo_pow": None,
                "costo_man": None,
                "costo_pa": None,
                "costo_pf": None,
                "costo_st": None,
                "effetto_attivabile": "{}",
                "active_icon": None,
                "durata_turni": None,
            },
            blockers,
            [],
        )

        self.assertIn("active_cost_conflict", blockers)

    def test_ranked_decimal_passive_keeps_incremental_value(self):
        blockers: list[str] = []
        passives = _passive(
            {
                "proposal_id": 10,
                "proposal_name": "Magia potente 3",
                "nome": "Magia potente 3",
                "descrizione": "Riduci di 0,6 invece di 0,4.",
                "note": "",
                "effetto_proposto": '{"tipo":"effetto_extra","effetto_extra":{"nome":"Sconto","descrizione":"Riduci di 0,6 invece di 0,4.","icona":"runa","effetti":[{"name":"sconto_mana_per_potere","operation":"+","value":"0.2"}]}}',
            },
            blockers,
            [],
        )

        self.assertEqual(passives[0]["operations"][0]["value"], "0.2")
        self.assertNotIn("passive_value_not_evidenced_in_prose", blockers)

    def test_exact_requirement_lists_and_obvious_aliases_resolve(self):
        names = {
            "ballerino": 1,
            "cantante": 2,
            "suonatore": 3,
            "controincantesimo": 4,
        }
        self.assertEqual(_requirement_source_ids("Ballerino, Cantante, Suonatore", names), [1, 2, 3])
        self.assertEqual(_requirement_source_ids("Counterspell", names), [4])


class SkillSeedRetirementTests(TestCase):
    def test_minimum_seed_does_not_recreate_poc_skills(self):
        call_command("seed_minimum_data", verbosity=0)
        self.assertFalse(Skill.objects.filter(nome__startswith="POC -").exists())

from decimal import Decimal

from django.test import TestCase

from backend.characters.models import (
    EffettoPersonalizzato,
    OperazioneEffettoPersonalizzato,
    Personaggio,
    SkillPersonaggio,
)
from backend.characters.services.refresh_personaggio import refresh_personaggio
from backend.core.legacy_skill_import import _passive
from backend.core.models import FamigliaSkill, GruppoFamiglieSkill, Skill, SpellDefinition
from backend.core.spell_economy_repair import repair_spell_economy, skill_derived_spell_economy
from backend.core.spell_services import spell_cast_breakdown, spell_cost_summary


ILLAOI_ECONOMY = {
    "manaDiscountPerPower": Decimal("1.5"),
    "actionPointDiscountPerPower": Decimal("1.5"),
    "manaPerEnergy": Decimal("10"),
    "manaPerActionPoint": Decimal("2.9"),
}


def _family(name: str) -> FamigliaSkill:
    group, _created = GruppoFamiglieSkill.objects.get_or_create(nome="Magia", defaults={"slug": "magia"})
    return FamigliaSkill.objects.create(nome=name, gruppo=group)


class SpellCastCostTests(TestCase):
    def setUp(self):
        self.family = _family("Costi incantesimo")

    def _spell(self, **fields) -> SpellDefinition:
        number = fields.pop("numero", 1)
        skill = Skill.objects.create(
            nome=fields.pop("nome", "Incantesimo"),
            slug=f"incantesimo-di-prova-{number}",
            numero=number,
            famiglia=self.family,
        )
        return SpellDefinition.objects.create(skill=skill, **fields)

    def test_a_purely_variable_spell_charges_only_what_the_effect_buys(self):
        definition = self._spell(effect_per_mana=Decimal("0.5"))  # 2 Mana per effetto

        breakdown = spell_cast_breakdown(definition, Decimal("6"), economy=ILLAOI_ECONOMY)

        self.assertEqual(breakdown["fixedMana"], 0)
        self.assertEqual(breakdown["variableMana"], 12)
        self.assertEqual(breakdown["requiredMana"], 12)

    def test_a_mixed_spell_keeps_the_fixed_and_the_per_effect_halves_separate(self):
        definition = self._spell(
            nome="Aura", numero=2, base_mana=Decimal("15"), effect_per_mana=Decimal(1) / Decimal(3)
        )

        breakdown = spell_cast_breakdown(definition, Decimal("4"), economy=ILLAOI_ECONOMY)

        self.assertEqual(breakdown["fixedMana"], 15)
        self.assertEqual(breakdown["variableMana"], 12)  # 4 effetti × 3 Mana
        self.assertEqual(breakdown["requiredMana"], 27)

    def test_the_fixed_mana_is_charged_even_without_any_effect(self):
        definition = self._spell(nome="Rito", numero=3, base_mana=Decimal("15"), effect_per_mana=Decimal("1"))

        breakdown = spell_cast_breakdown(definition, Decimal("0"), economy=ILLAOI_ECONOMY)

        self.assertEqual(breakdown["requiredMana"], 15)
        self.assertEqual(breakdown["costs"]["mana"], 15)

    def test_energia_and_pa_convert_from_the_whole_required_mana_before_discounts(self):
        # 12 Mana di Caos con 1 Potere sui valori Elder di Illaoi.
        definition = self._spell(nome="Caos", numero=4, effect_per_mana=Decimal("1"))

        breakdown = spell_cast_breakdown(
            definition, Decimal("12"), economy=ILLAOI_ECONOMY, power_used=Decimal("1")
        )

        self.assertEqual(breakdown["requiredMana"], 12)
        self.assertEqual(breakdown["costs"]["mana"], 11)  # 12 − 1 × 1,5, arrotondato per eccesso
        self.assertEqual(breakdown["costs"]["energia"], 2)  # ceil(12 / 10)
        self.assertEqual(breakdown["costs"]["pa"], 3)  # ceil(12 / 2,9 − 1 × 1,5)
        self.assertEqual(breakdown["costs"]["potere"], 1)

    def test_fixed_costs_are_added_on_top_and_never_converted(self):
        definition = self._spell(
            nome="Sigillo",
            numero=5,
            base_mana=Decimal("10"),
            effect_per_mana=Decimal("1"),
            fixed_costs={"pf": 3, "energia": 2, "pa": 1, "stanchezza": 4},
        )

        breakdown = spell_cast_breakdown(definition, Decimal("0"), economy=ILLAOI_ECONOMY)

        self.assertEqual(breakdown["convertedEnergy"], 1)  # ceil(10 / 10)
        self.assertEqual(breakdown["costs"]["energia"], 3)  # 1 convertita + 2 fisse
        self.assertEqual(breakdown["costs"]["pa"], 5)  # ceil(10 / 2,9) + 1 fisso
        self.assertEqual(breakdown["costs"]["pf"], 3)
        self.assertEqual(breakdown["costs"]["stanchezza"], 4)

    def test_a_free_cast_costs_nothing_instead_of_being_blocked(self):
        definition = self._spell(nome="Gratis", numero=6, effect_per_mana=Decimal("1"))

        breakdown = spell_cast_breakdown(
            definition,
            Decimal("0"),
            economy={key: Decimal("0") for key in ILLAOI_ECONOMY},
        )

        self.assertEqual(breakdown["costs"], {"pf": 0, "mana": 0, "energia": 0, "potere": 0, "pa": 0, "stanchezza": 0})

    def test_the_summary_names_the_fixed_part_only_when_there_is_one(self):
        variable_only = self._spell(nome="Scudo", numero=7, effect_per_mana=Decimal("0.25"))
        mixed = self._spell(
            nome="Forma",
            numero=8,
            base_mana=Decimal("10"),
            effect_per_mana=Decimal(1) / Decimal(7),
            fixed_costs={"pa": 2},
        )

        self.assertEqual(spell_cost_summary(variable_only), "4 Mana per effetto")
        self.assertIn("10 Mana fissi più 7 Mana per effetto", spell_cost_summary(mixed))
        self.assertIn("costi fissi 2 PA", spell_cost_summary(mixed))


class SpellEconomyImportTests(TestCase):
    def test_order_and_chaos_halves_of_a_skill_tier_apply_only_once(self):
        blockers: list[str] = []
        passives = _passive(
            {
                "proposal_id": 1,
                "nome": "Cast Leggero 1",
                "descrizione": "Lanciare incantesimi costa 1 Energia ogni 2 Mana spesi.",
                "effetto_proposto": (
                    '{"tipo": "effetto_extra", "effetto_extra": {"nome": "Sconto Energia per Mana",'
                    ' "descrizione": "Lanciare incantesimi costa 1 Energia ogni 2 Mana spesi.",'
                    ' "icona": "runa", "effetti": ['
                    '{"name": "ogni_en_x_mana_ordine", "operation": "+", "value": "2"},'
                    '{"name": "ogni_en_x_mana_caos", "operation": "+", "value": "2"}]}}'
                ),
            },
            blockers,
            [],
        )

        self.assertEqual(
            passives[0]["operations"],
            [{"target": "ogni_en_x_mana", "operation": "add", "value": "2", "condition": ""}],
        )


class SpellEconomyRepairTests(TestCase):
    def setUp(self):
        self.family = _family("Cast Leggero")
        self.character = Personaggio.objects.create(nome="Caster", nome_interno="caster", livello=5)

    def _owned_skill(self, name: str, number: int, target: str, value: str, twice: bool) -> Skill:
        operations = [{"target": target, "operation": "add", "value": value, "condition": ""}]
        skill = Skill.objects.create(
            nome=name,
            slug=f"abilita-di-prova-{number}",
            numero=number,
            famiglia=self.family,
            effetti_passivi=[{
                "id": f"passivo-{number}",
                "name": name,
                "description": "",
                "icon": "runa",
                "operations": operations * (2 if twice else 1),
            }],
        )
        SkillPersonaggio.objects.create(personaggio=self.character, skill=skill)
        effect = EffettoPersonalizzato.objects.create(
            personaggio=self.character, nome=f"{name} · passivo", origine=f"Abilità: {name}"
        )
        for order, operation in enumerate(operations * (2 if twice else 1)):
            OperazioneEffettoPersonalizzato.objects.create(
                effetto=effect, ordine=order, bersaglio=operation["target"],
                operazione=operation["operation"], valore=operation["value"],
            )
        return skill

    def _manual_effect(self, name: str, marker: str, target: str, value: str) -> EffettoPersonalizzato:
        effect = EffettoPersonalizzato.objects.create(
            personaggio=self.character, nome=name, origine=f"{marker} · Manuale Elder"
        )
        OperazioneEffettoPersonalizzato.objects.create(
            effetto=effect, ordine=0, bersaglio=target, operazione="add", valore=value
        )
        return effect

    def test_duplicate_tiers_and_the_manual_recap_are_both_removed_once(self):
        self._owned_skill("Cast Leggero 1", 1, "ogni_en_x_mana", "2", twice=True)
        self._owned_skill("Cast Leggero 2", 2, "ogni_en_x_mana", "3", twice=True)
        recap = self._manual_effect("Cast Leggero", "Elder Django #019", "ogni_en_x_mana", "5")

        self.assertEqual(skill_derived_spell_economy(self.character), {"ogni_en_x_mana": Decimal("5")})

        report = repair_spell_economy(apply=True)

        self.assertEqual(report["duplicateSkillOperationsRemoved"], 2)
        self.assertFalse(EffettoPersonalizzato.objects.filter(pk=recap.pk).exists())
        self.character.refresh_from_db()
        # Base globale 1 più i due gradini della skill, contati una sola volta.
        self.assertEqual(self.character.tot["ogni_en_x_mana"], 6)

    def test_a_manual_bonus_no_skill_explains_survives_the_repair(self):
        unexplained = self._manual_effect("Dono arcano", "Elder Django #005", "ogni_en_x_mana", "2")

        report = repair_spell_economy(apply=True)

        self.assertEqual(report["redundantManualEffects"], [])
        self.assertEqual(report["affectedCharacters"], [])
        self.assertTrue(EffettoPersonalizzato.objects.filter(pk=unexplained.pk).exists())
        refresh_personaggio(self.character)
        self.character.refresh_from_db()
        # Base globale 1 più il bonus manuale che nessuna abilità spiega.
        self.assertEqual(self.character.tot["ogni_en_x_mana"], 3)

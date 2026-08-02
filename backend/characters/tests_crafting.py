"""Forgiatura e Incantamento: gating, registro dei costi, isolamento degli esemplari."""

from __future__ import annotations

from django.test import TestCase

from backend.core.crafting_skill_rules import plan_for
from backend.core.forge_defaults import INGOT_NAME_BY_MATERIAL
from backend.core.item_special import compute_special_reasons
from backend.core.models import FamigliaSkill, GruppoFamiglieSkill, Oggetto, Skill

from .crafting_capability import improvement_budget, unlocked_materials
from .models import Equip, Personaggio, SkillPersonaggio, Zaino
from .services.forge import craft_item, improve_item, melt_item
from .services.item_instances import instance_block, is_instance
from .services.refresh_personaggio import refresh_personaggio


def _skill(family: FamigliaSkill, name: str, number: int) -> Skill:
    """Crea l'abilità e ci scrive sopra la regola, come fa la migrazione 0054."""
    skill = Skill.objects.create(
        nome=name,
        slug=name.lower().replace(" ", "-").replace("'", ""),
        numero=number,
        famiglia=family,
        costo_pe=4,
        tipo_pe="red" if family.nome == "Fabbro" else "blue",
    )
    plan = plan_for(family.nome, name)
    if plan:
        if plan["passives"]:
            skill.effetti_passivi = plan["passives"]
        skill.metadata = {**(skill.metadata or {}), plan["key"]: plan["rule"]}
        skill.save(update_fields=["effetti_passivi", "metadata"])
    return skill


class CraftingTestBase(TestCase):
    def setUp(self):
        # Le famiglie arrivano già dalle migrazioni di seed: qui si riusano.
        gruppo, _ = GruppoFamiglieSkill.objects.get_or_create(nome="Classi", defaults={"ordine": 1})
        self.fabbro, _ = FamigliaSkill.objects.get_or_create(
            nome="Fabbro", defaults={"gruppo": gruppo, "is_classe": True}
        )
        self.incantatore, _ = FamigliaSkill.objects.get_or_create(
            nome="Incantatore", defaults={"gruppo": gruppo, "is_classe": True}
        )
        self.zaino = Zaino.objects.create(nome="Zaino test")
        self.equip = Equip.objects.create(nome="Equip test")
        self.character = Personaggio.objects.create(
            nome="Fabbro di Prova",
            nome_interno="fabbro-di-prova",
            tipologia="giocabile",
            livello=5,
            zaino=self.zaino,
            equip=self.equip,
        )
        self.counter = 900000

    def grant(self, family: FamigliaSkill, name: str) -> Skill:
        self.counter += 1
        skill = _skill(family, name, self.counter)
        SkillPersonaggio.objects.create(personaggio=self.character, skill=skill, spesa_pe={"red": 4})
        # Lo sblocco reale materializza i passivi come effetti personalizzati;
        # qui basta che il totale arrivi in tot, quindi si ricalcola a mano.
        for passive in skill.effetti_passivi or []:
            from .models import EffettoPersonalizzato, OperazioneEffettoPersonalizzato

            effect = EffettoPersonalizzato.objects.create(
                personaggio=self.character, nome=skill.nome, origine="Abilità"
            )
            for order, operation in enumerate(passive.get("operations", []), start=1):
                OperazioneEffettoPersonalizzato.objects.create(
                    effetto=effect,
                    ordine=order,
                    bersaglio=operation["target"],
                    operazione=operation["operation"],
                    valore=operation["value"],
                )
        refresh_personaggio(self.character)
        self.character.refresh_from_db()
        return skill

    def put_in_backpack(self, item: Oggetto, quantity: int = 1) -> None:
        placed = 0
        for slot in range(1, 51):
            if placed >= quantity:
                break
            if getattr(self.zaino, f"slot_{slot}_id", None) is None:
                setattr(self.zaino, f"slot_{slot}", item)
                placed += 1
        self.zaino.save()

    def give_ingots(self, material: str, quantity: int) -> None:
        ingot, _ = Oggetto.objects.get_or_create(
            nome=INGOT_NAME_BY_MATERIAL[material],
            defaults={"tipo_1": "lingotto", "tipo_2": "lingotto", "valore": 25, "peso": 1.0},
        )
        self.put_in_backpack(ingot, quantity)

    def give_tools(self, level: int) -> None:
        tools, _ = Oggetto.objects.get_or_create(
            nome=f"Strumenti da Fabbro di livello {level}",
            defaults={"tipo_1": "strumentidafabbro", "valore": 50, "peso": 4.0},
        )
        self.put_in_backpack(tools)


class ForgeGatingTests(CraftingTestBase):
    def test_fabbro_3_unlocks_steel_but_not_elven(self):
        self.grant(self.fabbro, "Fabbro 2")
        self.grant(self.fabbro, "Fabbro 3")
        unlocked = unlocked_materials(self.character)
        self.assertIn("acciaio", unlocked)
        self.assertIn("chitina", unlocked)
        self.assertNotIn("elfico", unlocked)
        self.assertEqual(unlocked["acciaio"], "Fabbro 3")

    def test_light_and_heavy_branches_unlock_independently(self):
        """La fascia 6 leggera non porta con sé la fascia 4 pesante."""
        self.grant(self.fabbro, "Lavorazione del Vetro")
        unlocked = unlocked_materials(self.character)
        self.assertIn("vetro", unlocked)
        self.assertNotIn("ebano", unlocked)
        self.assertNotIn("orchesco", unlocked)

    def test_forging_without_tools_is_refused(self):
        self.grant(self.fabbro, "Fabbro 3")
        self.give_ingots("acciaio", 6)
        axe = Oggetto.objects.create(nome="Ascia (acciaio)", tipo_1="ascia", tipo_2="acciaio", peso=4.0)
        with self.assertRaises(Exception) as caught:
            craft_item(self.character.id, axe.id)
        self.assertIn("strumenti", str(caught.exception).lower())


class ForgeCraftTests(CraftingTestBase):
    def setUp(self):
        super().setUp()
        self.grant(self.fabbro, "Fabbro 3")
        self.give_tools(2)
        self.axe = Oggetto.objects.create(
            nome="Ascia (acciaio)", tipo_1="ascia", tipo_2="acciaio", tipo_3="taglio", peso=4.0, valore=200
        )

    def test_crafting_consumes_ingots_and_creates_an_instance(self):
        self.give_ingots("acciaio", 6)
        _character, result = craft_item(self.character.id, self.axe.id)
        self.assertEqual(result["ingotsSpent"], 4)  # armi medie
        self.assertEqual(result["hours"], 4)
        instance = Oggetto.objects.get(pk=result["itemId"])
        self.assertTrue(is_instance(instance))
        self.assertFalse(instance.modello)
        self.assertTrue(instance.archiviato)
        self.assertEqual(instance_block(instance)["material"], "acciaio")

    def test_instance_is_not_flagged_for_review(self):
        """Un esemplare è `modello=False` per costruzione: non deve finire in coda."""
        self.give_ingots("acciaio", 6)
        _character, result = craft_item(self.character.id, self.axe.id)
        instance = Oggetto.objects.get(pk=result["itemId"])
        self.assertNotIn("non_modello", compute_special_reasons(instance))

    def test_crafting_without_enough_ingots_is_refused(self):
        self.give_ingots("acciaio", 2)
        with self.assertRaises(Exception):
            craft_item(self.character.id, self.axe.id)
        self.assertEqual(Oggetto.objects.filter(nome__startswith="Ascia (acciaio) #").count(), 0)


class ImprovementTests(CraftingTestBase):
    def setUp(self):
        super().setUp()
        # Ferro è fascia 1 e Potenziato 7 alza il tetto a 8: restano 7 punti,
        # esattamente quanto costa la scala 1 + 2 + 4 dello stesso miglioramento.
        self.grant(self.fabbro, "Fabbro 2")
        self.grant(self.fabbro, "Potenziato 7")
        self.give_tools(1)
        self.give_ingots("ferro", 12)
        self.template = Oggetto.objects.create(
            nome="Martello (ferro)", tipo_1="martello", tipo_2="ferro", peso=4.0, valore=70
        )
        _character, result = craft_item(self.character.id, self.template.id)
        self.instance_id = result["itemId"]

    def test_repeating_the_same_improvement_doubles_its_cost(self):
        costs = []
        for _ in range(3):
            _character, result = improve_item(self.character.id, self.instance_id, "attacco")
            costs.append(result["cost"])
        self.assertEqual(costs, [1, 2, 4])
        instance = Oggetto.objects.get(pk=self.instance_id)
        self.assertEqual(instance_block(instance)["pointsSpent"], 7)

    def test_budget_is_potenziato_minus_material_tier(self):
        budget = improvement_budget(self.character, "ferro")
        self.assertEqual(budget["base"], 8)
        self.assertEqual(budget["materialTier"], 1)
        self.assertEqual(budget["max"], 7)
        # e lo stesso fabbro su un materiale più duro ha meno margine
        self.assertEqual(improvement_budget(self.character, "acciaio")["max"], 6)

    def test_improvement_beyond_the_budget_is_refused(self):
        for _ in range(3):
            improve_item(self.character.id, self.instance_id, "attacco")  # 1 + 2 + 4 = 7
        with self.assertRaises(Exception):
            # il quarto costerebbe 8, ben oltre il tetto di 7
            improve_item(self.character.id, self.instance_id, "attacco")

    def test_improvement_does_not_touch_the_shared_template(self):
        """Il cuore della faccenda: il martello dell'altro non deve cambiare."""
        improve_item(self.character.id, self.instance_id, "attacco")
        self.template.refresh_from_db()
        self.assertEqual(self.template.effects, [])
        self.assertEqual(self.template.peso, 4.0)

    def test_weight_improvement_writes_the_instance_column_only(self):
        improve_item(self.character.id, self.instance_id, "peso")
        instance = Oggetto.objects.get(pk=self.instance_id)
        self.assertEqual(instance.peso, 3.0)
        self.template.refresh_from_db()
        self.assertEqual(self.template.peso, 4.0)

    def test_table_rule_improvement_writes_regole_speciali(self):
        improve_item(self.character.id, self.instance_id, "sanguinamento")
        instance = Oggetto.objects.get(pk=self.instance_id)
        self.assertIn("Sanguinamento", instance.regole_speciali)
        # e non deve dichiarare rivisti i testi Elder del modello
        self.assertNotIn("descriptiveEffectsReviewed", instance.metadata)

    def test_instance_effects_reach_character_totals(self):
        improve_item(self.character.id, self.instance_id, "attacco")
        instance = Oggetto.objects.get(pk=self.instance_id)
        self.equip.arma = instance
        self.equip.save()
        before = float(self.character.tot.get("attacco", 0))
        refresh_personaggio(self.character)
        self.character.refresh_from_db()
        self.assertEqual(float(self.character.tot["attacco"]), before + 1)

    def test_chainmail_cannot_be_improved(self):
        mail = Oggetto.objects.create(
            nome="Chainmail (ferro)", tipo_1="chainmail", tipo_2="ferro", peso=6.0
        )
        _character, result = craft_item(self.character.id, mail.id)
        with self.assertRaises(Exception) as caught:
            improve_item(self.character.id, result["itemId"], "difesaArmatura")
        self.assertIn("cotte di maglia", str(caught.exception).lower())


class MeltTests(CraftingTestBase):
    def test_melting_requires_the_skill(self):
        self.grant(self.fabbro, "Fabbro 3")
        self.give_tools(2)
        self.give_ingots("acciaio", 6)
        template = Oggetto.objects.create(nome="Ascia (acciaio)", tipo_1="ascia", tipo_2="acciaio", peso=4.0)
        _character, result = craft_item(self.character.id, template.id)
        with self.assertRaises(Exception) as caught:
            melt_item(self.character.id, result["itemId"])
        self.assertIn("scioglitore", str(caught.exception).lower())

    def test_melting_returns_the_ingots_spent(self):
        self.grant(self.fabbro, "Fabbro 3")
        self.grant(self.fabbro, "Scioglitore")
        self.give_tools(2)
        self.give_ingots("acciaio", 6)
        template = Oggetto.objects.create(nome="Ascia (acciaio)", tipo_1="ascia", tipo_2="acciaio", peso=4.0)
        _character, crafted = craft_item(self.character.id, template.id)
        _character, melted = melt_item(self.character.id, crafted["itemId"])
        self.assertEqual(melted["expected"], 4)
        self.assertEqual(melted["recovered"], 4)
        self.assertFalse(Oggetto.objects.filter(pk=crafted["itemId"]).exists())


class EnchantCapabilityTests(CraftingTestBase):
    def test_infusore_raises_mana_per_level(self):
        from .crafting_capability import enchant_capabilities

        self.assertEqual(enchant_capabilities(self.character)["manaPerLevel"], 5.0)
        self.grant(self.incantatore, "Infusore 3")
        self.assertEqual(enchant_capabilities(self.character)["manaPerLevel"], 8.0)

    def test_gioielliere_sets_the_item_cap_without_touching_scrolls(self):
        from .crafting_capability import enchant_capabilities

        self.grant(self.incantatore, "Gioielliere 5")
        capability = enchant_capabilities(self.character)
        self.assertEqual(capability["maxItemLevel"], 8)
        self.assertEqual(capability["maxScrollLevel"], 0)

    def test_multi_enchant_raises_the_effect_limit(self):
        from .crafting_capability import enchant_capabilities

        self.assertEqual(enchant_capabilities(self.character)["maxEffects"], 1)
        self.grant(self.incantatore, "Multi Incantamento 1")
        self.assertEqual(enchant_capabilities(self.character)["maxEffects"], 2)


class EnchantMathTests(TestCase):
    def test_scroll_level_follows_the_elder_ladder(self):
        from backend.core.enchant_defaults import scroll_level_for_mana

        self.assertEqual(scroll_level_for_mana(11), 0)
        self.assertEqual(scroll_level_for_mana(12), 1)
        self.assertEqual(scroll_level_for_mana(21), 1)
        self.assertEqual(scroll_level_for_mana(22), 2)
        self.assertEqual(scroll_level_for_mana(118), 10)
        self.assertEqual(scroll_level_for_mana(500), 10)

    def test_effective_mana_applies_the_altar_bonus(self):
        from backend.core.enchant_defaults import effective_enchant_mana

        self.assertEqual(effective_enchant_mana(4, 5, 0.0), 20)
        self.assertEqual(effective_enchant_mana(4, 8, 0.0), 32)
        self.assertEqual(effective_enchant_mana(4, 5, 0.25), 25)

    def test_charges_follow_gem_level_and_compression(self):
        from backend.core.enchant_defaults import charges_for_gem

        self.assertEqual(charges_for_gem(4, 0), 4)
        self.assertEqual(charges_for_gem(4, 25), 5)
        self.assertEqual(charges_for_gem(4, 50), 6)

    def test_harmonic_gem_sum_truncates(self):
        from backend.core.enchant_defaults import harmonic_gem_level

        self.assertEqual(harmonic_gem_level([6]), 6)
        self.assertEqual(harmonic_gem_level([6, 4]), 8)  # 6 + 2
        self.assertEqual(harmonic_gem_level([10, 10, 10]), 10)  # tetto

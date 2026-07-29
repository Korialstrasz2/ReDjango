import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from backend.core.defaults import FORMULE_BASE_VALUE_FLOAT
from backend.core.models import Effetto, Giocatore, GlobalModifiers, Oggetto, Skill, TipoArma

from .models import PERSONAGGIO_TOT_KEYS, EffettiPersonaggio, Equip, Personaggio
from .selectors import _character_appearance
from .selectors import _effects
from .selectors import serialize_item
from .services.item_icons import special_icon_directory
from .race_rules import RACE_CATALOG, RACE_NAMES, automatic_race_effects, race_configuration_payload, subraces_for
from .services.refresh_personaggio import (
    apply_equipment_specializations,
    calculate_personaggio_totals,
    refresh_personaggio,
)


def profile_values(**overrides):
    values = dict(FORMULE_BASE_VALUE_FLOAT)
    values.update(overrides)
    return values


class PersonaggioTotSchemaTests(TestCase):
    def test_tot_json_replaces_individual_tot_model_fields(self):
        field_names = {field.name for field in Personaggio._meta.fields}

        self.assertIn("tot", field_names)
        self.assertIn("effetti", field_names)
        self.assertIn("effetti_finali", field_names)
        self.assertNotIn("act", field_names)
        self.assertNotIn("attacco_npc", field_names)
        self.assertNotIn("difesa_npc", field_names)
        for key in PERSONAGGIO_TOT_KEYS:
            self.assertNotIn(f"{key}_tot", field_names)

    def test_tot_defaults_keep_known_total_keys(self):
        personaggio = Personaggio.objects.create(
            nome="Schema Test",
            nome_interno="schema_test_personaggio",
        )

        self.assertEqual(set(personaggio.tot), set(PERSONAGGIO_TOT_KEYS))
        self.assertEqual(personaggio.tot["forza"], 0)
        self.assertEqual(personaggio.tot["mana"], 0)
        self.assertEqual(personaggio.tot["mod_forza"], 0)
        self.assertEqual(personaggio.tot["malus_carico"], 0)


class CharacterRaceRulesTests(TestCase):
    def test_refresh_applies_and_exposes_primary_race_and_subrace_rules(self):
        character = Personaggio.objects.create(
            nome="Ordinatore",
            nome_interno="ordinatore-race-test",
            razza_1="Dunmer",
            razza_2="Retaggio Mago",
        )

        refresh_personaggio(character)
        character.refresh_from_db()

        self.assertEqual(character.tot["intelligenza"], 11)
        self.assertEqual(character.tot["fortuna"], 8)
        self.assertGreaterEqual(character.tot["mana"], 8)
        automatic = [effect for effect in _effects(character) if effect["scope"] == "automatic"]
        self.assertEqual(
            [effect["name"] for effect in automatic],
            ["RAZZA: Dunmer", "Dunmer: tratto razziale", "SUBRAZZA: Retaggio Mago"],
        )
        self.assertTrue(all(not effect["editable"] for effect in automatic))

    def test_subrace_catalog_is_dependent_on_primary_race(self):
        self.assertIn("Retaggio Mago", subraces_for("Dunmer"))
        self.assertNotIn("Retaggio Mago", subraces_for("Nord"))

    def test_dremora_matches_existing_race_budget_and_exposes_rank_subraces(self):
        modifiers = RACE_CATALOG["Dremora"]["modifiers"]

        self.assertIn("Dremora", RACE_NAMES)
        self.assertEqual(sum(value for value in modifiers.values() if value > 0), 5)
        self.assertEqual(sum(value for value in modifiers.values() if value < 0), -5)
        self.assertEqual(
            subraces_for("Dremora"),
            ("Churl", "Caitiff", "Kynval", "Kynreeve", "Kynmarcher", "Markynaz", "Valkynaz"),
        )
        configuration = race_configuration_payload()
        dremora = next(entry for entry in configuration["races"] if entry["value"] == "Dremora")
        self.assertEqual(len(dremora["subraces"]), 7)

        effects = automatic_race_effects("Dremora", "Kynval")
        self.assertEqual(
            [effect["name"] for effect in effects],
            ["RAZZA: Dremora", "Dremora: tratto razziale", "SUBRAZZA: Kynval"],
        )
        self.assertIn(
            {"target": "attacco", "operation": "add", "value": "1"},
            effects[-1]["operations"],
        )

    def test_xivilai_is_a_distinct_balanced_daedric_race_without_dremora_ranks(self):
        modifiers = RACE_CATALOG["Xivilai"]["modifiers"]

        self.assertIn("Xivilai", RACE_NAMES)
        self.assertEqual(sum(value for value in modifiers.values() if value > 0), 5)
        self.assertEqual(sum(value for value in modifiers.values() if value < 0), -5)
        self.assertEqual(subraces_for("Xivilai"), ())

        effects = automatic_race_effects("Xivilai", "")
        self.assertEqual(
            [effect["name"] for effect in effects],
            ["RAZZA: Xivilai", "Xivilai: tratto razziale"],
        )
        self.assertEqual(
            effects[1]["operations"],
            [
                {"target": "res_fuoco", "operation": "add", "value": "1"},
                {"target": "rd_fuoco", "operation": "add", "value": "2"},
            ],
        )

    def test_undead_race_covers_skeletons_draugr_and_other_undead_forms(self):
        modifiers = RACE_CATALOG["Non morto"]["modifiers"]

        self.assertIn("Non morto", RACE_NAMES)
        self.assertEqual(sum(value for value in modifiers.values() if value > 0), 4)
        self.assertEqual(sum(value for value in modifiers.values() if value < 0), -4)
        self.assertEqual(
            subraces_for("Non morto"),
            ("Scheletro", "Draugr", "Revenant", "Mummia", "Vampiro", "Lich", "Spettro"),
        )
        effects = automatic_race_effects("Non morto", "Draugr")
        self.assertEqual(effects[1]["operations"], [{"target": "rd_fis", "operation": "add", "value": "1"}])
        self.assertIn(
            {"target": "res_gelo", "operation": "add", "value": "1"},
            effects[-1]["operations"],
        )


class CharacterAppearanceTests(TestCase):
    @patch("backend.characters.selectors.finders.find")
    def test_armor_portrait_is_sanitized_and_resolved_without_queries(self, find_static):
        armor = Oggetto.objects.create(nome="Corazza elfica", tipo_1="armatura", tipo_2="Élfico/../")
        equip = Equip.objects.create(nome="Equip ritratto", armatura=armor)
        personaggio = Personaggio.objects.create(nome="Íllaoi Mare Lungo", nome_interno="illaoi_test", equip=equip)
        expected_path = "frontend/images/characters/match/illaoi_elfico.webp"
        find_static.side_effect = lambda path: path if path == expected_path else None

        with self.assertNumQueries(0):
            appearance = _character_appearance(personaggio, {armor.id: armor})

        self.assertEqual(appearance["characterKey"], "illaoi")
        self.assertEqual(appearance["armorKey"], "elfico")
        self.assertEqual(appearance["imageUrl"], f"/static/{expected_path}")
        self.assertEqual(appearance["portraitUrl"], "")
        self.assertFalse(appearance["isPlaceholder"])

    @patch("backend.characters.selectors.finders.find")
    def test_main_figure_uses_armor_match_while_portrait_stays_separate(self, find_static):
        expected_path = "frontend/images/characters/match/illaoi_base.webp"
        find_static.side_effect = lambda path: path if path == expected_path else None
        personaggio = SimpleNamespace(
            nome="Illaoi Karanen",
            metadata={},
            equip=None,
            portrait_id=1,
            portrait=SimpleNamespace(file=SimpleNamespace(url="/media/portraits/illaoi.png")),
        )

        appearance = _character_appearance(personaggio, {})

        self.assertEqual(appearance["imageUrl"], f"/static/{expected_path}")
        self.assertEqual(appearance["portraitUrl"], "/media/portraits/illaoi.png")
        self.assertNotEqual(appearance["imageUrl"], appearance["portraitUrl"])

    @patch("backend.characters.selectors.finders.find", return_value=None)
    def test_robe_rank_takes_precedence_and_falls_back_to_placeholder(self, _find_static):
        armor = Oggetto.objects.create(nome="Corazza", tipo_1="armatura", tipo_2="cuoio")
        robe = Oggetto.objects.create(nome="Veste del Gran Maestro", tipo_1="veste", tipo_2="magica")
        equip = Equip.objects.create(nome="Equip veste", armatura=armor, veste=robe)
        personaggio = Personaggio.objects.create(nome="Rhyss il Saggio", nome_interno="rhyss_test", equip=equip)

        appearance = _character_appearance(personaggio, {armor.id: armor, robe.id: robe})

        self.assertEqual(appearance["armorKey"], "veste-gm")
        self.assertEqual(appearance["preferredFilename"], "rhyss_veste-gm.webp")
        self.assertTrue(appearance["isPlaceholder"])
        self.assertEqual(appearance["imageUrl"], appearance["fallbackUrl"])

    @patch("backend.characters.selectors.finders.find")
    def test_robe_rank_is_resolved_when_legacy_secondary_type_is_blank(self, find_static):
        robe = Oggetto.objects.create(nome="Veste qualificato (Di)", tipo_1="veste", tipo_2="")
        equip = Equip.objects.create(nome="Equip veste legacy", veste=robe)
        personaggio = Personaggio.objects.create(nome="Illaoi Karanen", nome_interno="illaoi_veste_test", equip=equip)
        expected_path = "frontend/images/characters/match/illaoi_veste-q.png"
        find_static.side_effect = lambda path: path if path == expected_path else None

        appearance = _character_appearance(personaggio, {robe.id: robe})

        self.assertEqual(appearance["armorKey"], "veste-q")
        self.assertEqual(appearance["preferredFilename"], "illaoi_veste-q.webp")
        self.assertEqual(appearance["imageUrl"], f"/static/{expected_path}")


class RefreshPersonaggioCalculationTests(TestCase):
    def test_alchemy_multipliers_use_base_values_and_normal_effect_operations(self):
        result = calculate_personaggio_totals(
            global_values=profile_values(),
            global_strings={},
            effect_payloads=[
                {"target": "moltiplicatore_reagenti_rossi", "operation": "add", "value": "0.2"},
                {"target": "moltiplicatore_reagenti_livello_3", "operation": "add", "value": "0.5"},
            ],
        )

        self.assertEqual(result.totals["moltiplicatore_reagenti_rossi"], 0.2)
        self.assertEqual(result.totals["moltiplicatore_reagenti_livello_3"], 2.7)
        self.assertIn("moltiplicatore_reagenti_rossi", result.breakdown["applied_operations"])

    def test_equipment_specializations_follow_current_weapon_armor_and_shield(self):
        weapon_type = TipoArma.objects.create(
            nome="Lama corta test",
            lunghezza="corta",
            potenza="media",
            bonus_1="taglio",
        )
        weapon = Oggetto.objects.create(nome="Coltello test", tipo_1="arma", tipo_arma=weapon_type)
        armor = Oggetto.objects.create(nome="Cuoio test", tipo_1="armatura", tipo_2="leggera")
        shield = Oggetto.objects.create(nome="Scudo test", tipo_1="scudo")
        equip = Equip.objects.create(nome="Equip specializzazioni", arma=weapon, armatura=armor, scudo=shield)
        personaggio = Personaggio.objects.create(
            nome="Specialista",
            nome_interno="specialista",
            equip=equip,
        )
        totals = {
            **{key: 0 for key in PERSONAGGIO_TOT_KEYS},
            "attacco": 5,
            "difesa": 10,
            "atk_skill_corte": 1,
            "atk_skill_medie2": 2,
            "atk_skill_taglio": 3,
            "def_skill_leggera": 4,
            "def_skill_scudo": 5,
            "atk_skill_maninude": 6,
            "tier_skill_maninude": 2,
            "def_skill_noarmatura": 7,
        }

        equipped, report = apply_equipment_specializations(totals, personaggio)
        self.assertEqual(equipped["attacco"], 11)
        self.assertEqual(equipped["difesa"], 19)
        self.assertEqual(report["attackTargets"], ["atk_skill_corte", "atk_skill_medie2", "atk_skill_taglio"])

        equip.arma = None
        equip.armatura = None
        equip.scudo = None
        unarmed, report = apply_equipment_specializations(totals, personaggio)
        self.assertEqual(unarmed["attacco"], 11)
        self.assertEqual(unarmed["difesa"], 17)
        self.assertEqual(unarmed["tier"], 2)
        self.assertEqual(report["attackTargets"], ["atk_skill_maninude"])

    def test_saved_weapon_profile_overrides_stale_weapon_type_categories(self):
        weapon_type = TipoArma.objects.create(
            nome="Martello categoria obsoleta",
            lunghezza="corta",
            potenza="potente",
            bonus_1="contundente",
            rules={
                "profile": {
                    "length": "corta",
                    "power": "potente",
                    "damageType": "contundente",
                }
            },
        )
        weapon = Oggetto.objects.create(
            nome="Martello con profilo aggiornato",
            tipo_1="arma",
            tipo_2="contundente",
            tipo_arma=weapon_type,
            weapon_profile={
                "length": "media",
                "power": "media",
                "damageType": "taglio",
            },
        )
        equip = Equip.objects.create(nome="Equip profilo autorevole", arma=weapon)
        personaggio = Personaggio.objects.create(
            nome="Profilo autorevole",
            nome_interno="profilo-autorevole",
            equip=equip,
        )
        totals = {
            **{key: 0 for key in PERSONAGGIO_TOT_KEYS},
            "attacco": 5,
            "atk_skill_medie1": 2,
            "atk_skill_medie2": 3,
            "atk_skill_taglio": 4,
            "atk_skill_corte": 20,
            "atk_skill_potenti": 25,
            "atk_skill_contundente": 30,
        }

        equipped, report = apply_equipment_specializations(totals, personaggio)

        self.assertEqual(equipped["attacco"], 14)
        self.assertEqual(
            report["attackTargets"],
            ["atk_skill_medie1", "atk_skill_medie2", "atk_skill_taglio"],
        )

    def test_weapon_specializations_follow_the_active_dual_wield_profile(self):
        balanced = Oggetto.objects.create(
            nome="Bilanciata attiva test",
            tipo_1="arma",
            weapon_profile={"length": "corta", "power": "media", "damageType": "taglio"},
        )
        powerful = Oggetto.objects.create(
            nome="Potente attiva test",
            tipo_1="arma",
            weapon_profile={"length": "corta", "power": "potente", "damageType": "taglio"},
        )
        equip = Equip.objects.create(nome="Equip cambio primaria", arma=balanced, scudo=powerful)
        personaggio = Personaggio.objects.create(
            nome="Cambio primaria",
            nome_interno="cambio-primaria",
            equip=equip,
        )
        totals = {
            **{key: 0 for key in PERSONAGGIO_TOT_KEYS},
            "attacco": 5,
            "atk_skill_medie2": 3,
            "atk_skill_potenti": 25,
        }

        balanced_totals, balanced_report = apply_equipment_specializations(totals, personaggio)
        self.assertEqual(balanced_totals["attacco"], 8)
        self.assertNotIn("atk_skill_potenti", balanced_report["attackTargets"])

        equip.arma_primaria_slot = "scudo"
        equip.save(update_fields=["arma_primaria_slot", "updated_at"])
        powerful_totals, powerful_report = apply_equipment_specializations(totals, personaggio)
        self.assertEqual(powerful_totals["attacco"], 30)
        self.assertIn("atk_skill_potenti", powerful_report["attackTargets"])

    def test_quick_stats_adjust_selected_derived_stats_with_configured_percentages(self):
        result = calculate_personaggio_totals(
            global_values=profile_values(
                stanchezza=2,
                modificatore_generale=1,
                pf=100,
                attacco=100,
            ),
            global_strings={
                "formulas": {"pf": "base.pf", "attacco": "base.attacco"},
                "quick_stat_adjustments": {
                    "fatigue_percent_per_point": 10,
                    "fatigue_fixed_per_point": 1,
                    "general_modifier_percent_per_point": 5,
                    "general_modifier_fixed_per_point": 0,
                    "targets": ["pf"],
                },
            },
            effect_payloads=[{"target": "pf", "operation": "add", "value": 20}],
        )

        self.assertEqual(result.totals["pf"], 100)
        self.assertEqual(result.totals["attacco"], 100)
        self.assertEqual(result.breakdown["quick_stat_adjustment"]["total_percent"], -15)
        self.assertEqual(result.breakdown["quick_stat_adjustment"]["applied"]["pf"]["before"], 120)
        self.assertEqual(
            result.breakdown["quick_stat_adjustment"]["applied"]["pf"]["fatigue_fixed"],
            -2,
        )

    def test_level_and_fortuna_adjustments_follow_the_configured_order(self):
        personaggio = SimpleNamespace(livello=10)
        result = calculate_personaggio_totals(
            global_values=profile_values(forza=10, fortuna=10),
            global_strings={
                "adjustment.livello": "personaggio.livello / 5",
                "adjustment.fortuna": "final.fortuna - 10",
            },
            personaggio=personaggio,
            apply_quick_stats=False,
        )

        # Level makes Fortuna 12; its contribution is then applied to the
        # other characteristics, but not recursively to Fortuna itself.
        self.assertEqual(result.totals["fortuna"], 12)
        self.assertEqual(result.totals["forza"], 14)
        self.assertEqual(
            result.breakdown["characteristic_adjustments"]["fortuna"]["value"],
            2,
        )

    def test_characteristics_round_down_once_after_all_progression_adjustments(self):
        result = calculate_personaggio_totals(
            global_values=profile_values(forza=10, fortuna=11),
            global_strings={
                "adjustment.livello": "personaggio.livello / 5",
                "adjustment.fortuna": "final.fortuna / 10",
            },
            personaggio=SimpleNamespace(livello=8),
            effect_payloads=[{"target": "forza", "operation": "add", "value": 0.4}],
            apply_quick_stats=False,
        )

        # No contribution is truncated on its own: 10 + .4 + 1.6 + 1.26.
        self.assertEqual(result.totals["forza"], 13)
        self.assertEqual(result.totals["fortuna"], 12)
        self.assertEqual(
            result.breakdown["characteristic_rounding"]["forza"],
            {"before": 13.26, "after": 13},
        )

    def test_refresh_reports_base_item_and_effect_contributions_including_derived_values(self):
        GlobalModifiers.objects.create(
            name="Formule_base",
            value_float=profile_values(forza=10, pf=15),
            value_string={"formulas": {"pf": "base.pf + (final.forza - 10) * 3"}},
        )
        item = Oggetto.objects.create(
            nome="Bracciale della forza",
            effects=[{"target": "forza", "operation": "add", "value": 2}],
        )
        effect = Effetto.objects.create(
            nome="Forza temporanea",
            tipo="effetto",
            effect_payload={"target": "forza", "operation": "add", "value": 1},
        )
        equip = Equip.objects.create(nome="Equip contributi", extra_slot_1=item)
        active_effects = EffettiPersonaggio.objects.create(nome="Effetti contributi", effetto_1=effect)
        personaggio = Personaggio.objects.create(
            nome="Contributi",
            nome_interno="contributi",
            equip=equip,
            effetti=active_effects,
        )

        refresh_personaggio(personaggio)
        personaggio.refresh_from_db()

        sources = personaggio.effetti_finali["calculation_sources"]
        self.assertEqual(sources["forza"], {"base": 10, "items": 2, "effects": 1})
        self.assertEqual(sources["pf"], {"base": 15, "items": 6, "effects": 3})

    def test_refresh_loads_base_values_from_global_modifiers_only(self):
        GlobalModifiers.objects.create(
            name="Formule_base",
            value_float=profile_values(forza=12, pf=30),
            value_string={"formulas": {"pf": "base.pf"}},
        )
        personaggio = Personaggio.objects.create(
            nome="Base Source",
            nome_interno="base_source",
            extra={"forza": 99, "pf": 99},
            custom_overrides={"forza": 99, "pf": 99},
        )

        result = refresh_personaggio(personaggio)
        personaggio.refresh_from_db()

        self.assertEqual(result.totals["forza"], 12)
        self.assertEqual(personaggio.tot["forza"], 12)
        self.assertEqual(personaggio.tot["pf"], 30)
        self.assertEqual(personaggio.custom_overrides, {})
        self.assertIn("base", personaggio.effetti_finali)

    def test_refresh_reads_effects_from_effetti_personaggio_slots(self):
        GlobalModifiers.objects.create(
            name="Formule_base",
            value_float=profile_values(forza=12, pf=30),
            value_string={"formulas": {"pf": "base.pf"}},
        )
        effetto = Effetto.objects.create(
            nome="Forza dello slot",
            tipo="effetto",
            effect_payload={"target": "forza", "operation": "add", "value": 3},
        )
        effetti = EffettiPersonaggio.objects.create(nome="Effetti test", effetto_1=effetto)
        personaggio = Personaggio.objects.create(
            nome="Slot Source",
            nome_interno="slot_source",
            effetti=effetti,
        )

        refresh_personaggio(personaggio)
        personaggio.refresh_from_db()

        self.assertEqual(personaggio.tot["forza"], 15)
        self.assertIn("forza", personaggio.effetti_finali["applied_operations"])
        self.assertEqual(
            personaggio.effetti_finali["modified_stats"]["forza"][0]["source"],
            "effetti.effetto_1:Forza dello slot",
        )

    def test_effetti_finali_is_report_data_not_refresh_input(self):
        GlobalModifiers.objects.create(
            name="Formule_base",
            value_float=profile_values(forza=12),
            value_string={},
        )
        personaggio = Personaggio.objects.create(
            nome="Cache Ignored",
            nome_interno="cache_ignored",
            effetti_finali={"operations": [{"target": "forza", "operation": "add", "value": 50}]},
        )

        refresh_personaggio(personaggio)
        personaggio.refresh_from_db()

        self.assertEqual(personaggio.tot["forza"], 12)

    def test_characteristic_circular_effects_use_frozen_pre_snapshot(self):
        result = calculate_personaggio_totals(
            global_values=profile_values(forza=15, resistenza=18),
            global_strings={},
            effect_payloads=[
                {"target": "forza", "operation": "add", "value": "pre.mod_resistenza * 2"},
                {"target": "resistenza", "operation": "add", "value": "pre.mod_forza"},
            ],
        )

        self.assertEqual(result.totals["forza"], 23)
        self.assertEqual(result.totals["resistenza"], 20)
        self.assertEqual(result.totals["mod_forza"], 6)
        self.assertEqual(result.totals["mod_resistenza"], 5)

    def test_final_modifiers_are_calculated_after_characteristics(self):
        result = calculate_personaggio_totals(
            global_values=profile_values(forza=10),
            global_strings={},
            effect_payloads=[{"target": "forza", "operation": "add", "value": 8}],
        )

        self.assertEqual(result.totals["forza"], 18)
        self.assertEqual(result.totals["mod_forza"], 4)

    def test_derived_formulas_run_last_and_use_final_modifiers(self):
        result = calculate_personaggio_totals(
            global_values=profile_values(forza=18, attacco=5),
            global_strings={"formulas": {"attacco": "base.attacco + final.mod_forza * 2"}},
            effect_payloads=[{"target": "forza", "operation": "add", "value": 2}],
        )

        self.assertEqual(result.totals["forza"], 20)
        self.assertEqual(result.totals["mod_forza"], 5)
        self.assertEqual(result.totals["attacco"], 15)

    def test_formula_override_replaces_normal_formula(self):
        result = calculate_personaggio_totals(
            global_values=profile_values(attacco=5),
            global_strings={"formulas": {"attacco": "1"}},
            effect_payloads=[
                {"formula_overrides": {"attacco": "base.attacco + 10"}},
            ],
        )

        self.assertEqual(result.totals["attacco"], 15)
        self.assertEqual(result.breakdown["custom_overrides"], {"attacco": "base.attacco + 10"})
        self.assertIn("attacco", result.breakdown["modified_stats"])

    def test_multiple_formula_overrides_newest_processed_wins(self):
        result = calculate_personaggio_totals(
            global_values=profile_values(attacco=5),
            global_strings={"formulas": {"attacco": "base.attacco"}},
            effect_payloads=[
                {"formula_overrides": {"attacco": "1"}},
                {"formula_overrides": {"attacco": "2"}},
            ],
        )

        self.assertEqual(result.totals["attacco"], 2)
        self.assertEqual(result.breakdown["custom_overrides"], {"attacco": "2"})
        active_overrides = [
            override
            for override in result.breakdown["formula_overrides"]
            if override["active"]
        ]
        self.assertEqual(len(active_overrides), 1)
        self.assertEqual(active_overrides[0]["formula"], "2")

    def test_refresh_writes_only_winning_formula_overrides_to_custom_overrides(self):
        GlobalModifiers.objects.create(
            name="Formule_base",
            value_float=profile_values(attacco=5),
            value_string={"formulas": {"attacco": "base.attacco"}},
        )
        weak_item = Oggetto.objects.create(
            nome="Override debole",
            effects=[{"formula_overrides": {"attacco": "base.attacco + 1"}}],
        )
        strong_item = Oggetto.objects.create(
            nome="Override medio",
            effects=[{"formula_overrides": {"attacco": "base.attacco + 5"}}],
        )
        winning_effect = Effetto.objects.create(
            nome="Override maggiore",
            tipo="effetto",
            effect_payload={"formula_overrides": {"attacco": "base.attacco + 10"}},
        )
        equip = Equip.objects.create(nome="Equip override", arma=weak_item, armatura=strong_item)
        effetti = EffettiPersonaggio.objects.create(nome="Effetti override", effetto_1=winning_effect)
        personaggio = Personaggio.objects.create(
            nome="Formula Source",
            nome_interno="formula_source",
            equip=equip,
            effetti=effetti,
            custom_overrides={"attacco": "stale"},
        )

        refresh_personaggio(personaggio)
        personaggio.refresh_from_db()

        self.assertEqual(personaggio.tot["attacco"], 15)
        self.assertEqual(personaggio.custom_overrides, {"attacco": "base.attacco + 10"})
        self.assertEqual(personaggio.effetti_finali["custom_overrides"], personaggio.custom_overrides)
        self.assertEqual(
            personaggio.effetti_finali["resolved_formula_overrides"]["attacco"]["source"],
            "effetti.effetto_1:Override maggiore",
        )
        self.assertEqual(
            personaggio.effetti_finali["modified_stats"]["attacco"][-1]["kind"],
            "formula_override",
        )
        active_overrides = [
            override
            for override in personaggio.effetti_finali["formula_overrides"]
            if override["active"]
        ]
        self.assertEqual(len(active_overrides), 1)
        self.assertEqual(active_overrides[0]["source"], "effetti.effetto_1:Override maggiore")

    def test_operation_order_is_deterministic(self):
        result = calculate_personaggio_totals(
            global_values=profile_values(pf=10),
            global_strings={},
            effect_payloads=[
                {"target": "pf", "operation": "cap", "value": 30},
                {"target": "pf", "operation": "percent", "value": 50},
                {"target": "pf", "operation": "max", "value": 35},
                {"target": "pf", "operation": "multiply", "value": 2},
                {"target": "pf", "operation": "subtract", "value": 3},
                {"target": "pf", "operation": "add", "value": 5},
                {"target": "pf", "operation": "min", "value": 40},
            ],
        )

        self.assertEqual(result.totals["pf"], 30)

    def test_set_is_definitive_within_the_phase(self):
        result = calculate_personaggio_totals(
            global_values=profile_values(pf=10),
            global_strings={},
            effect_payloads=[
                {"target": "pf", "operation": "set", "value": 100},
                {"target": "pf", "operation": "add", "value": 1000},
                {"target": "pf", "operation": "multiply", "value": 2},
                {"target": "pf", "operation": "cap", "value": 50},
            ],
        )

        self.assertEqual(result.totals["pf"], 100)

    def test_strong_set_runs_after_quick_adjustments_and_last_one_wins(self):
        result = calculate_personaggio_totals(
            global_values=profile_values(stanchezza=2, modificatore_generale=1, pf=100),
            global_strings={
                "formulas": {"pf": "base.pf"},
                "quick_stat_adjustments": {
                    "fatigue_percent_per_point": 10,
                    "fatigue_fixed_per_point": 0,
                    "general_modifier_percent_per_point": 5,
                    "general_modifier_fixed_per_point": 0,
                    "targets": ["pf"],
                },
            },
            effect_payloads=[
                {"target": "pf", "operation": "strong_set", "value": 40, "source": "primo"},
                {"target": "pf", "operation": "strong_set", "value": 50, "source": "secondo"},
            ],
        )

        self.assertEqual(result.breakdown["quick_stat_adjustment"]["applied"]["pf"]["after"], 85)
        self.assertEqual(result.totals["pf"], 50)
        applied = result.breakdown["strong_set_adjustment"]["applied"]["pf"]
        self.assertEqual([row["after"] for row in applied], [40, 50])
        self.assertEqual(applied[-1]["source"], "secondo")

    def test_action_points_never_drop_below_elder_minimum(self):
        result = calculate_personaggio_totals(
            global_values=profile_values(pa=5, stanchezza=10),
            global_strings={
                "formulas": {"pa": "base.pa"},
                "quick_stat_adjustments": {
                    "fatigue_percent_per_point": 10,
                    "fatigue_fixed_per_point": 0,
                    "general_modifier_percent_per_point": 0,
                    "general_modifier_fixed_per_point": 0,
                    "targets": ["pa"],
                },
            },
        )

        self.assertEqual(result.breakdown["quick_stat_adjustment"]["applied"]["pa"]["after"], 0)
        self.assertEqual(result.totals["pa"], 4)
        self.assertEqual(result.breakdown["action_point_minimum"], {
            "minimum": 4,
            "before": 0,
            "after": 4,
            "applied": True,
        })


class PersonaggioPocApiTests(TestCase):
    def setUp(self):
        call_command("seed_minimum_data", verbosity=0)
        self.client.force_login(Giocatore.objects.get(nome="local_master").user)

    def test_seed_creates_poc_content_and_personaggio_payload(self):
        self.assertEqual(Oggetto.objects.filter(metadata__seed_kind="poc_item").count(), 22)
        self.assertEqual(Skill.objects.filter(metadata__seed_kind="poc_skill").count(), 0)
        self.assertEqual(Personaggio.objects.filter(metadata__seed_kind="poc_personaggio").count(), 3)

        response = self.client.get("/api/personaggi/", HTTP_X_REDJANGO_REQUEST_ID="poc-list")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["requestId"], "poc-list")
        data = body["data"]
        self.assertEqual(len(data["personaggi"]), 3)
        self.assertIsNotNone(data["giocatore"]["activePersonaggioId"])
        self.assertEqual(len(data["activePersonaggio"]["abilities"]), 10)
        self.assertEqual(len(data["activePersonaggio"]["skills"]), 0)
        self.assertTrue(data["activePersonaggio"]["equipment"])
        self.assertTrue(data["activePersonaggio"]["inventory"])

    def test_reseed_preserves_saved_inventory_and_equipment(self):
        personaggio = Personaggio.objects.get(nome_interno="poc_darion_frondaluna")
        replacement = Oggetto.objects.get(nome="Pozione di cura minore")
        personaggio.zaino.slot_1 = replacement
        personaggio.zaino.save(update_fields=["slot_1", "updated_at"])
        personaggio.equip.arma = None
        personaggio.equip.save(update_fields=["arma", "updated_at"])
        personaggio.monete = 999
        personaggio.save(update_fields=["monete", "updated_at"])
        replacement.descrizione = "Descrizione personalizzata"
        replacement.save(update_fields=["descrizione", "updated_at"])

        call_command("seed_minimum_data", verbosity=0)

        personaggio.zaino.refresh_from_db()
        personaggio.equip.refresh_from_db()
        personaggio.refresh_from_db()
        replacement.refresh_from_db()
        self.assertEqual(personaggio.zaino.slot_1_id, replacement.id)
        self.assertIsNone(personaggio.equip.arma_id)
        self.assertEqual(personaggio.monete, 999)
        self.assertEqual(replacement.descrizione, "Descrizione personalizzata")

    def test_select_personaggio_updates_current_giocatore(self):
        list_response = self.client.get("/api/personaggi/")
        personaggi = list_response.json()["data"]["personaggi"]
        target_id = personaggi[1]["id"]

        response = self.client.post(
            "/api/personaggi/select/",
            data=json.dumps(
                {
                    "action": "personaggi.select",
                    "requestId": "select-poc",
                    "payload": {"personaggioId": target_id},
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["requestId"], "select-poc")
        self.assertEqual(body["data"]["giocatore"]["activePersonaggioId"], target_id)
        self.assertEqual(body["data"]["activePersonaggio"]["id"], target_id)
        giocatore = Giocatore.objects.get(nome="local_master")
        self.assertEqual(giocatore.active_character_id, target_id)

    def test_master_sees_assigned_characters_first_and_can_take_control_of_any_character(self):
        assigned = Personaggio.objects.get(nome_interno="poc_darion_frondaluna")
        unassigned = Personaggio.objects.create(
            nome="Altro personaggio",
            nome_interno="altro_personaggio_master_test",
        )
        giocatore = Giocatore.objects.get(nome="local_master")
        giocatore.character_ids = [assigned.id]
        giocatore.active_character = assigned
        giocatore.save(update_fields=["character_ids", "active_character", "updated_at"])

        list_response = self.client.get("/api/personaggi/")

        self.assertEqual(list_response.status_code, 200)
        listed_ids = [entry["id"] for entry in list_response.json()["data"]["personaggi"]]
        self.assertEqual(listed_ids[0], assigned.id)
        self.assertIn(unassigned.id, listed_ids)
        self.assertSetEqual(
            set(listed_ids),
            set(
                Personaggio.objects.filter(archived_at__isnull=True)
                .exclude(nome_interno="template_personaggio_vuoto")
                .values_list("id", flat=True)
            ),
        )

        sheet_response = self.client.get(f"/api/v1/characters/{unassigned.id}/sheet")
        self.assertEqual(sheet_response.status_code, 200)

        select_response = self.client.post(
            "/api/personaggi/select/",
            data=json.dumps(
                {
                    "action": "personaggi.select",
                    "payload": {"personaggioId": unassigned.id},
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(select_response.status_code, 200)
        self.assertEqual(
            select_response.json()["data"]["giocatore"]["activePersonaggioId"],
            unassigned.id,
        )
        giocatore.refresh_from_db()
        self.assertEqual(giocatore.active_character_id, unassigned.id)
        self.assertEqual(giocatore.character_ids, [assigned.id, unassigned.id])

    def test_player_remains_limited_to_assigned_characters(self):
        assigned = Personaggio.objects.get(nome_interno="poc_darion_frondaluna")
        unassigned = Personaggio.objects.create(
            nome="Personaggio non assegnato",
            nome_interno="personaggio_non_assegnato_user_test",
        )
        giocatore = Giocatore.objects.get(nome="local_master")
        giocatore.role = Giocatore.ROLE_USER
        giocatore.character_ids = [assigned.id]
        giocatore.active_character = assigned
        giocatore.save(
            update_fields=["role", "character_ids", "active_character", "updated_at"]
        )

        list_response = self.client.get("/api/personaggi/")
        listed_ids = [entry["id"] for entry in list_response.json()["data"]["personaggi"]]
        self.assertEqual(listed_ids, [assigned.id])
        self.assertEqual(
            self.client.get(f"/api/v1/characters/{unassigned.id}/sheet").status_code,
            404,
        )

        select_response = self.client.post(
            "/api/personaggi/select/",
            data=json.dumps(
                {
                    "action": "personaggi.select",
                    "payload": {"personaggioId": unassigned.id},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(select_response.status_code, 404)

    def test_admin_sees_assigned_characters_first_and_all_other_characters(self):
        assigned = Personaggio.objects.get(nome_interno="poc_darion_frondaluna")
        unassigned = Personaggio.objects.create(
            nome="Personaggio disponibile all'admin",
            nome_interno="personaggio_disponibile_admin_test",
        )
        giocatore = Giocatore.objects.get(nome="local_master")
        giocatore.role = Giocatore.ROLE_ADMIN
        giocatore.character_ids = [assigned.id]
        giocatore.active_character = assigned
        giocatore.save(
            update_fields=["role", "character_ids", "active_character", "updated_at"]
        )

        list_response = self.client.get("/api/personaggi/")
        listed_ids = [entry["id"] for entry in list_response.json()["data"]["personaggi"]]

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(listed_ids[0], assigned.id)
        self.assertIn(unassigned.id, listed_ids)
        self.assertEqual(
            self.client.get(f"/api/v1/characters/{unassigned.id}/sheet").status_code,
            200,
        )


class ItemSpecialIconTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_minimum_data", verbosity=0)

    def setUp(self):
        self.client.force_login(Giocatore.objects.get(nome="local_master").user)
        self.item = Oggetto.objects.create(nome="Lama di Prova Icona", tipo_1="spadalunga")
        self.target = special_icon_directory() / "lama_di_prova_icona.webp"
        self.addCleanup(lambda: self.target.unlink() if self.target.exists() else None)

    def _webp(self) -> bytes:
        # Minimal lossless WebP container: "RIFF" <size> "WEBP" is all the view checks.
        body = b"VP8L" + b"\x00" * 16
        return b"RIFF" + len(body).to_bytes(4, "little") + b"WEBP" + body

    def upload(self, payload: bytes, name="icona.webp", content_type="image/webp"):
        return self.client.post(
            f"/api/oggetti/{self.item.id}/icona/",
            {"file": SimpleUploadedFile(name, payload, content_type=content_type)},
        )

    def test_upload_writes_icon_named_after_the_item(self):
        response = self.upload(self._webp())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(self.target.is_file())
        self.assertEqual(self.target.read_bytes(), self._webp())

    def test_uploaded_icon_wins_over_the_category_icon(self):
        self.assertTrue(serialize_item(self.item)["imageUrl"].endswith("/items/spadalunga.webp"))
        self.upload(self._webp())
        self.assertTrue(
            serialize_item(self.item)["imageUrl"].endswith("/items/speciali/lama_di_prova_icona.webp")
        )

    def test_non_webp_uploads_are_rejected(self):
        response = self.upload(b"\x89PNG\r\n\x1a\n" + b"0" * 40, name="icona.png", content_type="image/png")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["code"], "item.icon_invalid_format")
        self.assertFalse(self.target.exists())

    def test_oversized_uploads_are_rejected(self):
        response = self.upload(b"RIFF" + b"\x00" * 4 + b"WEBP" + b"0" * (512 * 1024))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["code"], "item.icon_too_large")
        self.assertFalse(self.target.exists())

    def test_delete_removes_the_icon_and_falls_back_to_the_category(self):
        self.upload(self._webp())
        response = self.client.delete(f"/api/oggetti/{self.item.id}/icona/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.target.exists())
        self.assertTrue(serialize_item(self.item)["imageUrl"].endswith("/items/spadalunga.webp"))

    def test_players_cannot_change_item_icons(self):
        giocatore = Giocatore.objects.get(nome="local_master")
        giocatore.role = Giocatore.ROLE_USER
        giocatore.save(update_fields=["role", "updated_at"])
        response = self.upload(self._webp())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.target.exists())

    def test_missing_item_returns_not_found(self):
        response = self.client.post(f"/api/oggetti/{self.item.id + 99999}/icona/", {})
        self.assertEqual(response.status_code, 404)

import importlib
import random
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from backend.characters.models import BottoneCombat, EffettiPersonaggio, Equip, Faretra, Note, Personaggio, SkillPersonaggio, Zaino, default_personaggio_tot
from backend.characters.selectors import ordered_personaggi_for
from backend.core.api import ApiError
from backend.core.competence_defaults import default_competence_state
from backend.core.management_selectors import deletion_preview_token
from backend.core.management_services import delete_managed_character
from backend.core.models import AccessoryProfile, DatiCampagna, Effetto, FamigliaSkill, Giocatore, GlobalModifiers, GruppoFamiglieSkill, Oggetto, SettingDefinition, Skill, Unit
from backend.media_library.models import ImageCategory, UploadedImage

from .damage_rules import DAMAGE_RULES_CONFIG_KEY, default_damage_rules
from .models import CombatEvent, HexType, MapHex, MapMetadata, MapParticipant, MapParticipantFootprint, MapSnapshot, MapType
from .rules import direct_hex_line, hex_distance, resolve_attack_values
from .selectors import combat_workspace_payload
from .services import (
    _participant_cells,
    activate_character,
    apply_direct_damage,
    apply_enemy_effect,
    calculate_paths,
    commit_plan_action,
    create_or_update_map,
    create_map_snapshot,
    deactivate_participant,
    ensure_viewer_character,
    create_plan_action,
    import_character,
    move_participant,
    paint_hexes,
    resolve_attack,
    reload_active_weapon,
    remove_quiver_item,
    restore_map_snapshot,
    duplicate_map,
    generate_unit,
    take_control,
    update_action_settings,
    update_combat_resource,
    update_fog,
)
from .unit_generation import create_unit_character
from .accessory_profiles import equip_accessory_profile
from .unit_management_services import preview_managed_unit, save_managed_unit


class CombatTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(username="combat-master")
        self.giocatore = Giocatore.objects.create(nome="combat-master", role=Giocatore.ROLE_MASTER)
        self.map_type = MapType.objects.create(name="Test", slug="test")
        self.map = MapMetadata.objects.create(name="Arena", map_type=self.map_type, created_by=self.giocatore, rows=12, columns=12)

    def character(self, name, **totals):
        tot = default_personaggio_tot()
        tot.update({"pf": 30, "mana": 20, "energia": 15, "potere": 10, "pa": 8, **totals})
        return Personaggio.objects.create(
            nome=name,
            nome_interno=f"{name.lower()}-{Personaggio.objects.count()}",
            zaino=Zaino.objects.create(nome=f"{name} zaino"),
            equip=Equip.objects.create(nome=f"{name} equip"),
            faretra=Faretra.objects.create(nome=f"{name} faretra"),
            note=Note.objects.create(nome=f"{name} note"),
            tot=tot,
        )


class EventStreamTests(CombatTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_stream_is_async_and_reconnect_prefers_last_event_id(self):
        already_seen = CombatEvent.objects.create(
            map=self.map,
            event_type="combat.first",
            message="Evento già ricevuto.",
        )
        newest = CombatEvent.objects.create(
            map=self.map,
            event_type="combat.second",
            message="Evento nuovo.",
        )

        response = self.client.get(
            f"/api/combat/maps/{self.map.id}/events/?after=0",
            HTTP_LAST_EVENT_ID=str(already_seen.id),
        )

        async def first_two_chunks():
            iterator = response.streaming_content.__aiter__()
            try:
                return [await anext(iterator), await anext(iterator)]
            finally:
                await iterator.aclose()

        chunks = async_to_sync(first_two_chunks)()
        event_chunk = chunks[1].decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_async)
        self.assertEqual(response.headers["Cache-Control"], "no-cache, no-transform")
        self.assertIn("retry: 2000", chunks[0].decode("utf-8"))
        self.assertIn(f"id: {newest.id}", event_chunk)
        self.assertIn("Evento nuovo.", event_chunk)
        self.assertNotIn(f"id: {already_seen.id}", event_chunk)


class PathRulesTests(CombatTestCase):
    def test_offset_rows_are_real_hex_neighbors_without_axial_drift(self):
        self.assertEqual(hex_distance((0, 0), (0, 1), "pointy"), 1)
        self.assertEqual(hex_distance((0, 0), (1, 1), "pointy"), 2)
        self.assertEqual(direct_hex_line((0, 0), (0, 2), "pointy"), [(0, 0), (0, 1), (0, 2)])

    def test_fastest_multiplies_all_terrain_tags_and_direct_ignores_them(self):
        mud = HexType.objects.create(name="Fango", slug="fango-test", movement_multiplier=1.5)
        climb = HexType.objects.create(name="Salita", slug="salita-test", movement_multiplier=2)
        edited = MapHex.objects.create(map=self.map, q=1, r=0)
        edited.terrain_types.set([mud, climb])
        result = calculate_paths({"mapId": self.map.id, "start": {"q": 0, "r": 0}, "end": {"q": 2, "r": 0}})
        self.assertEqual(result["direct"]["distance"], 2)
        self.assertEqual(result["direct"]["path"], [{"q": 0, "r": 0}, {"q": 1, "r": 0}, {"q": 2, "r": 0}])
        self.assertGreater(result["fastest"]["cost"], 2)
        self.assertNotEqual(result["fastest"]["path"], result["direct"]["path"])

    def test_path_cost_uses_the_global_setting_definition_value(self):
        SettingDefinition.objects.create(
            key="combat.base_movement_ap",
            label="Costo base movimento per esagono",
            category="Combattimento",
            value_type=SettingDefinition.TYPE_INT,
            default_value=1,
            value=3,
        )

        result = calculate_paths(
            {"mapId": self.map.id, "start": {"q": 0, "r": 0}, "end": {"q": 2, "r": 0}}
        )

        self.assertEqual(result["fastest"]["cost"], 6)
        self.assertEqual(result["fastest"]["actionPoints"], 6)

    def test_multi_hex_move_preserves_footprint(self):
        character = self.character("Gigante")
        participant = MapParticipant.objects.create(map=self.map, character=character, anchor_q=0, anchor_r=0)
        MapParticipantFootprint.objects.bulk_create([
            MapParticipantFootprint(participant=participant, q=0, r=0),
            MapParticipantFootprint(participant=participant, q=1, r=0),
            MapParticipantFootprint(participant=participant, q=0, r=1),
        ])
        move_participant(self.user, self.giocatore, {"participantId": participant.id, "q": 4, "r": 5})
        participant.refresh_from_db()
        self.assertEqual((participant.anchor_q, participant.anchor_r), (4, 5))
        self.assertEqual(set(participant.footprint.values_list("q", "r")), {(0, 0), (1, 0), (0, 1)})
        self.assertEqual(set(_participant_cells(participant, (4, 5))), {(4, 5), (5, 5), (5, 6)})


class MapWorkspaceTests(CombatTestCase):
    def test_workspace_query_count_does_not_scale_with_owned_skill_cards(self):
        group = GruppoFamiglieSkill.objects.create(
            nome="Combat performance",
            slug="combat-performance",
        )
        family = FamigliaSkill.objects.create(
            nome="Combat performance",
            gruppo=group,
        )
        skills = [
            Skill.objects.create(
                nome=f"Combat performance {index}",
                slug=f"combat-performance-{index}",
                numero=10000 + index,
                famiglia=family,
                azioni_attive=[
                    {
                        "id": f"action-{index}",
                        "name": f"Azione {index}",
                        "description": "Test",
                    }
                ],
            )
            for index in range(20)
        ]
        for character_index in range(3):
            character = self.character(f"Profilato {character_index}")
            MapParticipant.objects.create(
                map=self.map,
                character=character,
                anchor_q=character_index,
                anchor_r=0,
            )
            SkillPersonaggio.objects.bulk_create(
                [
                    SkillPersonaggio(personaggio=character, skill=skill)
                    for skill in skills
                ]
            )

        with CaptureQueriesContext(connection) as queries:
            payload = combat_workspace_payload(
                self.user,
                self.giocatore,
                self.map.id,
            )

        self.assertLess(len(queries), 60)
        self.assertEqual(len(payload["map"]["participants"]), 3)
        self.assertTrue(
            payload["map"]["participants"][0]["character"]["skills"][0][
                "activeReminders"
            ]
        )

    def test_new_map_keeps_the_sheet_character_active_and_exposes_the_portrait_fallback(self):
        character = self.character("Esploratrice")
        self.giocatore.active_character = character
        self.giocatore.character_ids = [character.id]
        self.giocatore.save(update_fields=["active_character", "character_ids", "updated_at"])
        created = create_or_update_map(self.user, self.giocatore, {
            "name": "Bosco",
            "mapTypeId": self.map_type.id,
            "rows": 10,
            "columns": 12,
        })
        created.refresh_from_db()
        self.assertEqual(created.active_character_id, character.id)
        self.assertTrue(created.participants.filter(character=character, active=True).exists())
        payload = combat_workspace_payload(self.user, self.giocatore, created.id)
        self.assertEqual(payload["focusCharacter"]["id"], character.id)
        self.assertEqual(payload["map"]["activeCharacterIds"], [character.id])
        self.assertEqual(payload["viewerCharacterId"], character.id)

    def test_page_access_activates_selected_character_but_respects_master_removal(self):
        character = self.character("Visitatrice")
        self.giocatore.active_character = character
        self.giocatore.character_ids = [character.id]
        self.giocatore.save(update_fields=["active_character", "character_ids", "updated_at"])
        _map, added = ensure_viewer_character(self.giocatore, {"mapId": self.map.id})
        self.assertTrue(added)
        participant = self.map.participants.get(character=character)
        self.assertTrue(participant.active)
        deactivate_participant(self.user, self.giocatore, {"participantId": participant.id})
        _map, added_again = ensure_viewer_character(self.giocatore, {"mapId": self.map.id})
        participant.refresh_from_db()
        self.assertFalse(added_again)
        self.assertFalse(participant.active)

    def test_master_adds_inactive_character_without_cloning_and_can_reactivate_it(self):
        character = self.character("Alleata")
        _map, added = activate_character(self.user, self.giocatore, {
            "mapId": self.map.id,
            "characterId": character.id,
            "footprint": [{"q": 0, "r": 0}],
        })
        self.assertTrue(added)
        participant = self.map.participants.get(character=character)
        self.assertEqual(participant.character_id, character.id)
        deactivate_participant(self.user, self.giocatore, {"participantId": participant.id})
        _map, reactivated = activate_character(self.user, self.giocatore, {
            "mapId": self.map.id,
            "characterId": character.id,
        })
        participant.refresh_from_db()
        self.assertTrue(reactivated)
        self.assertTrue(participant.active)
        self.assertEqual(Personaggio.objects.filter(pk=character.id).count(), 1)

    def test_bulk_hex_editor_applies_fog_and_one_terrain_to_exact_cells(self):
        marsh = HexType.objects.create(name="Palude test", slug="palude-editor-test", movement_multiplier=2)
        paint_hexes(self.user, self.giocatore, {
            "mapId": self.map.id,
            "cells": [{"q": 2, "r": 3}, {"q": 3, "r": 3}],
            "fogEffect": True,
            "terrainTypeIds": [marsh.id],
            "blocked": False,
        })
        edited = list(self.map.hexes.filter(q__in=[2, 3], r=3).order_by("q"))
        self.assertEqual(len(edited), 2)
        self.assertTrue(all(entry.fog_effect for entry in edited))
        self.assertTrue(all(list(entry.terrain_types.values_list("id", flat=True)) == [marsh.id] for entry in edited))

    def test_automatic_backups_are_created_every_four_revisions_and_keep_three(self):
        for index in range(15):
            paint_hexes(self.user, self.giocatore, {
                "mapId": self.map.id,
                "center": {"q": index % 4, "r": 0},
                "radius": 0,
                "overlayColor": "#336699",
            })
        self.map.refresh_from_db()
        self.assertEqual(self.map.revision, 16)
        self.assertEqual(list(self.map.snapshots.order_by("revision").values_list("revision", flat=True)), [8, 12, 16])


class AttackRulesTests(CombatTestCase):
    def test_saved_damage_rule_object_drives_grid_tier_and_resistance(self):
        rules = default_damage_rules()
        # With ATK 0, DEF 0, Luck 10 and d20 10, the Elder difference is 7.
        rules["damageMultipliers"]["10"][7 - (-25)] = 100
        rules["tierDamageFormulas"]["0"] = "10"
        rules["resistancePercentages"]["0"] = 50
        GlobalModifiers.objects.create(
            name="Formule_base",
            value_string={DAMAGE_RULES_CONFIG_KEY: rules},
        )
        attacker = self.character("Configurabile", attacco=0, tier=0, fortuna=10)
        defender = self.character("Bersaglio configurabile", difesa=0, res_taglio=0)

        result = resolve_attack_values(
            attacker,
            defender,
            {"damageType": "Taglio", "attackRoll": 10},
            rng=random.Random(4),
        )

        self.assertTrue(result["hit"])
        self.assertEqual(result["damageMultiplier"], 1)
        self.assertEqual(result["damageRoll"], 10)
        self.assertEqual(result["resistancePercent"], 50)
        self.assertEqual(result["finalDamage"], 5)

    def test_resistance_levels_use_elder_endpoint_clamping(self):
        attacker = self.character("Attaccante resistenze", attacco=20)
        resistant = self.character(
            "Oltre resistenza",
            difesa=0,
            res_taglio=10,
        )
        vulnerable = self.character(
            "Sotto resistenza",
            difesa=0,
            res_taglio=-5,
        )

        high = resolve_attack_values(
            attacker,
            resistant,
            {"damageType": "Taglio", "attackRoll": 10, "rawDamage": 100},
        )
        low = resolve_attack_values(
            attacker,
            vulnerable,
            {"damageType": "Taglio", "attackRoll": 10, "rawDamage": 100},
        )

        self.assertEqual(high["sourceResistanceLevel"], 10)
        self.assertEqual(high["resistanceLevel"], 9)
        self.assertEqual(high["resistancePercent"], 60)
        self.assertEqual(high["finalDamage"], 40)
        self.assertEqual(low["sourceResistanceLevel"], -5)
        self.assertEqual(low["resistanceLevel"], -4)
        self.assertEqual(low["resistancePercent"], -45)
        self.assertEqual(low["finalDamage"], 145)

    def test_tier_outside_elder_table_has_no_automatic_damage(self):
        attacker = self.character("Fuori Tier", attacco=20, tier=31)
        defender = self.character("Difensore fuori Tier", difesa=0)

        result = resolve_attack_values(
            attacker,
            defender,
            {"damageType": "Puro", "attackRoll": 10},
        )

        self.assertTrue(result["hit"])
        self.assertEqual(result["damageTier"], 31)
        self.assertEqual(result["damageFormula"], "Nessun danno")
        self.assertEqual(result["rawDamage"], 0)
        self.assertEqual(result["finalDamage"], 0)

    def test_character_combat_buttons_are_validated_and_applied_server_side(self):
        attacker = self.character("Tattico", attacco=10, tier=2)
        defender = self.character("Corazzato bottoni", difesa=0, rd_fis=5)
        button = BottoneCombat.objects.create(
            personaggio=attacker,
            nome="Affondo preparato",
            bonus_attacco=3,
            bonus_danno=4,
            bonus_tier=2,
            perforazione=2,
            perforazione_percentuale=10,
        )
        MapParticipant.objects.create(map=self.map, character=attacker)
        MapParticipant.objects.create(map=self.map, character=defender, anchor_q=1)

        _map, result = resolve_attack(self.user, self.giocatore, {
            "mapId": self.map.id,
            "attackerId": attacker.id,
            "defenderId": defender.id,
            "damageType": "Taglio",
            "attackRoll": 10,
            "combatButtonIds": [button.id],
            "apply": False,
        })

        self.assertEqual(result["attackTotal"], 23)
        self.assertEqual(result["damageTier"], 4)
        self.assertEqual(result["damageBonus"], 4)
        self.assertEqual(result["penetrationFlat"], 2)
        self.assertEqual(result["penetrationPercent"], 10)
        self.assertEqual(result["combatButtonIds"], [button.id])

    def test_character_cannot_submit_another_characters_combat_button(self):
        attacker = self.character("Proprietario attacco", attacco=10)
        other = self.character("Altro proprietario", attacco=10)
        defender = self.character("Bersaglio bottoni", difesa=0)
        button = BottoneCombat.objects.create(personaggio=other, nome="Non tuo", bonus_attacco=99)
        MapParticipant.objects.create(map=self.map, character=attacker)
        MapParticipant.objects.create(map=self.map, character=defender, anchor_q=1)

        with self.assertRaises(ApiError) as error:
            resolve_attack(self.user, self.giocatore, {
                "mapId": self.map.id,
                "attackerId": attacker.id,
                "defenderId": defender.id,
                "damageType": "Taglio",
                "attackRoll": 10,
                "combatButtonIds": [button.id],
                "apply": False,
            })

        self.assertEqual(error.exception.code, "combat_buttons.unavailable")

    def test_pure_damage_ignores_flat_and_percent_resistance(self):
        attacker = self.character("Mago", attacco=20)
        defender = self.character("Custode", difesa=0, rd_fis=999, res_contundente=9)
        result = resolve_attack_values(attacker, defender, {"damageType": "Puro", "attackRoll": 10, "rawDamage": 11})
        self.assertTrue(result["hit"])
        self.assertEqual(result["effectiveFlatReduction"], 0)
        self.assertEqual(result["resistancePercent"], 0)
        self.assertEqual(result["finalDamage"], 11)

    def test_direct_damage_button_applies_server_side_reduction(self):
        attacker = self.character("Applicatore", attacco=20)
        defender = self.character("Corazza diretta", rd_fis=3, res_taglio=0)
        MapParticipant.objects.create(map=self.map, character=attacker)
        MapParticipant.objects.create(map=self.map, character=defender)
        _map, result = apply_direct_damage(self.user, self.giocatore, {
            "mapId": self.map.id,
            "attackerId": attacker.id,
            "defenderId": defender.id,
            "damageType": "Taglio",
            "rawDamage": 10,
        })
        defender.refresh_from_db()
        self.assertEqual(result["finalDamage"], 7)
        self.assertEqual(defender.danno, 7)

    def test_quiver_item_can_be_removed_from_combat_context_menu(self):
        archer = self.character("Arciere menu")
        arrow = Oggetto.objects.create(nome="Freccia menu", tipo_1="freccia")
        archer.faretra.slot_1 = arrow
        archer.faretra.save(update_fields=["slot_1", "updated_at"])
        MapParticipant.objects.create(map=self.map, character=archer)
        remove_quiver_item(self.user, self.giocatore, {"mapId": self.map.id, "characterId": archer.id, "slot": "1"})
        archer.faretra.refresh_from_db()
        self.assertIsNone(archer.faretra.slot_1)

    def test_applied_power_pays_its_stored_resource_costs(self):
        attacker = self.character("Incantatore", attacco=20)
        defender = self.character("Bersaglio", difesa=0)
        MapParticipant.objects.create(map=self.map, character=attacker)
        MapParticipant.objects.create(map=self.map, character=defender)
        _map, result = resolve_attack(self.user, self.giocatore, {
            "mapId": self.map.id,
            "attackerId": attacker.id,
            "defenderId": defender.id,
            "damageType": "Fuoco",
            "attackRoll": 10,
            "rawDamage": 5,
            "powerName": "Fiamma breve",
            "resourceCosts": {"mana": 3, "pa": 2},
            "apply": True,
        })
        attacker.refresh_from_db()
        self.assertEqual(attacker.mana_speso, 3)
        self.assertEqual(result["resourceCosts"]["pa"], 4)
        self.assertEqual(result["powerName"], "Fiamma breve")
        self.assertEqual(result["weaponActionPointCost"], 2)

    def test_alternating_dual_wield_weapons_reduces_only_second_weapon_cost(self):
        attacker = self.character("Duellante", attacco=20, pa=20)
        defender = self.character("Bersaglio doppio", difesa=0)
        main = Oggetto.objects.create(
            nome="Lama primaria test", tipo_1="arma", pa_per_attacco=3,
            weapon_profile={"length": "corta", "damageType": "taglio", "combatMode": "melee"},
        )
        offhand = Oggetto.objects.create(
            nome="Lama secondaria test", tipo_1="arma", pa_per_attacco=4,
            weapon_profile={"length": "media", "damageType": "perforante", "combatMode": "melee"},
        )
        attacker.equip.arma = main
        attacker.equip.scudo = offhand
        attacker.equip.save(update_fields=["arma", "scudo", "updated_at"])
        MapParticipant.objects.create(map=self.map, character=attacker)
        MapParticipant.objects.create(map=self.map, character=defender, anchor_q=1)

        _map, first = resolve_attack(self.user, self.giocatore, {
            "mapId": self.map.id, "attackerId": attacker.id, "defenderId": defender.id,
            "damageType": "Taglio", "attackRoll": 10, "rawDamage": 1, "apply": True,
        })
        attacker.equip.arma_primaria_slot = "scudo"
        attacker.equip.save(update_fields=["arma_primaria_slot", "updated_at"])
        _map, second = resolve_attack(self.user, self.giocatore, {
            "mapId": self.map.id, "attackerId": attacker.id, "defenderId": defender.id,
            "damageType": "Perforante", "attackRoll": 10, "rawDamage": 1, "apply": True,
        })

        self.assertEqual(first["resourceCosts"]["pa"], 3)
        self.assertEqual(second["resourceCosts"]["pa"], 3)
        self.assertEqual(second["dualWieldDiscount"], 1)

    def test_ranged_attack_consumes_ammunition_and_reload_pays_stored_cost(self):
        attacker = self.character("Balestriere", attacco=20, pa=30)
        defender = self.character("Bersaglio a distanza", difesa=0)
        weapon = Oggetto.objects.create(
            nome="Balestra test", tipo_1="arma", pa_per_attacco=4,
            weapon_profile={
                "length": "media", "damageType": "perforante", "combatMode": "ranged",
                "ammunitionType": "dardo", "magazineSize": 2, "reloadBaseCost": 3,
                "reloadPerProjectileCost": 2,
            },
        )
        attacker.equip.arma = weapon
        attacker.equip.save(update_fields=["arma", "updated_at"])
        for index in range(1, 4):
            projectile = Oggetto.objects.create(nome=f"Dardo test {index}", tipo_1="dardo")
            setattr(attacker.faretra, f"slot_{index}", projectile)
        attacker.faretra.save()
        MapParticipant.objects.create(map=self.map, character=attacker, anchor_q=0)
        MapParticipant.objects.create(map=self.map, character=defender, anchor_q=2)

        for expected_loaded in (1, 0):
            _map, result = resolve_attack(self.user, self.giocatore, {
                "mapId": self.map.id, "attackerId": attacker.id, "defenderId": defender.id,
                "damageType": "Perforante", "attackRoll": 10, "rawDamage": 1, "apply": True,
            })
            self.assertEqual(result["loadedAfter"], expected_loaded)
            self.assertTrue(result["ammunitionName"].startswith("Dardo test"))

        with self.assertRaises(ApiError) as error:
            resolve_attack(self.user, self.giocatore, {
                "mapId": self.map.id, "attackerId": attacker.id, "defenderId": defender.id,
                "damageType": "Perforante", "attackRoll": 10, "rawDamage": 1, "apply": True,
            })
        self.assertEqual(error.exception.code, "combat.weapon_reload_required")

        _map, reload_result = reload_active_weapon(self.user, self.giocatore, {
            "mapId": self.map.id, "characterId": attacker.id,
        })
        self.assertEqual(reload_result["loaded"], 2)
        self.assertEqual(reload_result["actionPointCost"], 7)

    def test_applied_power_cycles_insufficient_energy_into_fatigue(self):
        attacker = self.character("Affaticato", attacco=20, energia=15)
        defender = self.character("Bersaglio energia", difesa=0)
        attacker.energia_spesa = 14
        attacker.save(update_fields=["energia_spesa", "updated_at"])
        MapParticipant.objects.create(map=self.map, character=attacker)
        MapParticipant.objects.create(map=self.map, character=defender)

        resolve_attack(self.user, self.giocatore, {
            "mapId": self.map.id,
            "attackerId": attacker.id,
            "defenderId": defender.id,
            "damageType": "Fuoco",
            "attackRoll": 10,
            "rawDamage": 5,
            "resourceCosts": {"energia": 3},
            "apply": True,
        })

        attacker.refresh_from_db()
        self.assertEqual(attacker.energia_spesa, 2)
        self.assertEqual(attacker.stanchezza_accumulata, 1)

    def test_legacy_table_uses_tier_formula_attributes_percent_and_critical_thresholds(self):
        attacker = self.character("Duellante", attacco=18, tier=6, forza=16, fortuna=12)
        attacker.crit_mag = "20"
        attacker.save(update_fields=["crit_mag", "updated_at"])
        defender = self.character("Corazzato", difesa=8, rd_fis=2, res_taglio=1)
        result = resolve_attack_values(attacker, defender, {
            "damageType": "Taglio",
            "attackRoll": 20,
            "damageTierBonus": 1,
            "damageBonus": 2,
            "damagePercentBonus": 33,
            "attributeKeys": ["forza"],
        }, rng=random.Random(7))
        self.assertTrue(result["hit"])
        self.assertEqual(result["damageTier"], 7)
        self.assertEqual(result["attributeBonus"], 3)
        self.assertEqual(result["critical"], "major")
        self.assertGreater(result["damageMultiplier"], 0)
        self.assertIn("d", result["damageFormula"])
        self.assertGreater(result["finalDamage"], 0)


class FogBackupAndControlTests(CombatTestCase):
    def setUp(self):
        super().setUp()
        self.hero = self.character("Eroe")
        self.enemy = self.character("Nemico")
        self.hero_participant = MapParticipant.objects.create(map=self.map, character=self.hero, anchor_q=0, anchor_r=0)
        self.enemy_participant = MapParticipant.objects.create(map=self.map, character=self.enemy, anchor_q=4, anchor_r=4)
        self.player_user = get_user_model().objects.create(username="combat-player")
        self.player = Giocatore.objects.create(
            nome="combat-player",
            role=Giocatore.ROLE_USER,
            active_character=self.hero,
            character_ids=[self.hero.id],
        )

    def test_fog_radius_is_persisted_and_filters_player_payload(self):
        update_fog(self.user, self.giocatore, {
            "mapId": self.map.id,
            "enabled": True,
            "mode": "reveal",
            "center": {"q": 0, "r": 0},
            "radius": 1,
        })
        payload = combat_workspace_payload(self.player_user, self.player, self.map.id)["map"]
        self.assertTrue(payload["fogEnabled"])
        self.assertTrue(payload["hexes"])
        self.assertTrue(all(entry["revealed"] for entry in payload["hexes"]))
        self.assertEqual([entry["character"]["id"] for entry in payload["participants"]], [self.hero.id])

    def test_combat_payload_exposes_full_action_points_without_a_fatigue_bar(self):
        payload = combat_workspace_payload(self.player_user, self.player, self.map.id)["map"]
        resources = payload["participants"][0]["character"]["resources"]
        action_points = next(resource for resource in resources if resource["key"] == "pa")

        self.assertEqual(action_points["current"], action_points["maximum"])
        self.assertEqual(action_points["spent"], 0)
        self.assertNotIn("stanchezza", {resource["key"] for resource in resources})

    def test_revision_metadata_is_visible_only_to_master_and_admin_roles(self):
        player_payload = combat_workspace_payload(self.player_user, self.player, self.map.id)
        master_payload = combat_workspace_payload(self.user, self.giocatore, self.map.id)
        self.assertNotIn("revision", player_payload["map"])
        self.assertNotIn("revision", player_payload["maps"][0])
        self.assertEqual(master_payload["map"]["revision"], self.map.revision)

    def test_snapshot_restore_and_duplicate_keep_map_runtime_state(self):
        painted = MapHex.objects.create(map=self.map, q=2, r=3, overlay_color="#cc8844", overlay_opacity=.5, revealed=True)
        self.map.fog_enabled = True
        self.map.save(update_fields=["fog_enabled", "updated_at"])
        create_map_snapshot(self.user, self.giocatore, {"mapId": self.map.id, "label": "Prima"})
        snapshot = MapSnapshot.objects.get(map=self.map, label="Prima")
        painted.overlay_color = "#000000"
        painted.revealed = False
        painted.save()
        restore_map_snapshot(self.user, self.giocatore, {"snapshotId": snapshot.id})
        restored = self.map.hexes.get(q=2, r=3)
        self.assertEqual(restored.overlay_color, "#cc8844")
        self.assertTrue(restored.revealed)
        copied = duplicate_map(self.user, self.giocatore, {"mapId": self.map.id, "name": "Arena copia"})
        self.assertEqual(copied.name, "Arena copia")
        self.assertTrue(copied.fog_enabled)
        self.assertEqual(copied.hexes.get(q=2, r=3).overlay_color, "#cc8844")
        self.assertEqual(copied.participants.filter(active=True).count(), 2)

    def test_master_can_apply_enemy_effect_and_take_control(self):
        campaign = DatiCampagna.objects.create(nome="Campagna controllo Unit test", attiva=True)
        self.giocatore.active_campaign = campaign
        self.giocatore.save(update_fields=["active_campaign", "updated_at"])
        self.enemy.metadata = {"generatedFromUnitId": 999}
        self.enemy.save(update_fields=["metadata", "updated_at"])
        effect = Effetto.objects.create(nome="Stordito", tipo="Malus", durata_turni=2)
        apply_enemy_effect(self.user, self.giocatore, {
            "mapId": self.map.id,
            "defenderId": self.enemy.id,
            "effectId": effect.id,
        })
        self.enemy.refresh_from_db()
        self.assertEqual(self.enemy.effetti.effetto_1_id, effect.id)
        take_control(self.user, self.giocatore, {"mapId": self.map.id, "characterId": self.enemy.id})
        immediate_workspace = combat_workspace_payload(self.user, self.giocatore, self.map.id)
        self.assertEqual(immediate_workspace["viewerCharacterId"], self.enemy.id)
        self.assertIn(self.enemy.id, self.giocatore.character_ids)
        self.giocatore.refresh_from_db()
        self.enemy.refresh_from_db()
        self.map.refresh_from_db()
        self.assertEqual(self.giocatore.active_character_id, self.enemy.id)
        self.assertEqual(self.map.active_character_id, self.enemy.id)
        self.assertEqual(self.enemy.campagna_id, campaign.id)
        self.assertIn(
            self.enemy.id,
            [character.id for character in ordered_personaggi_for(self.giocatore, include_all=True)],
        )

    def test_player_cannot_paint_or_take_control(self):
        with self.assertRaises(ApiError) as paint_error:
            paint_hexes(self.player_user, self.player, {
                "mapId": self.map.id,
                "center": {"q": 0, "r": 0},
                "radius": 1,
                "overlayColor": "#cc8844",
            })
        self.assertEqual(paint_error.exception.status, 403)
        with self.assertRaises(ApiError) as control_error:
            take_control(self.player_user, self.player, {"mapId": self.map.id, "characterId": self.enemy.id})
        self.assertEqual(control_error.exception.status, 403)

    def test_combat_rail_updates_persistent_resources_but_rejects_local_action_points(self):
        update_combat_resource(self.player_user, self.player, {
            "mapId": self.map.id,
            "characterId": self.hero.id,
            "resource": "pf",
            "current": 21,
        })
        with self.assertRaises(ApiError) as action_points_error:
            update_combat_resource(self.player_user, self.player, {
                "mapId": self.map.id,
                "characterId": self.hero.id,
                "resource": "pa",
                "current": 3,
            })
        self.assertEqual(action_points_error.exception.code, "combat.action_points_local_only")
        update_combat_resource(self.player_user, self.player, {
            "mapId": self.map.id,
            "characterId": self.hero.id,
            "resource": "stanchezza",
            "current": 4,
        })
        self.hero.refresh_from_db()
        self.assertEqual((self.hero.danno, self.hero.stanchezza_accumulata), (9, 4))

        with self.assertRaises(ApiError) as resource_error:
            update_combat_resource(self.player_user, self.player, {
                "mapId": self.map.id,
                "characterId": self.enemy.id,
                "resource": "pf",
                "current": 1,
            })
        self.assertEqual(resource_error.exception.status, 403)


class QuickActionSettingsTests(CombatTestCase):
    def setUp(self):
        super().setUp()
        self.fighter = self.character(
            "Etichettatrice",
            sconto_mana_per_potere=2,
            sconto_pa_per_potere=1,
            ogni_en_x_mana=4,
            ogni_pa_x_mana=5,
        )
        activate_character(self.user, self.giocatore, {
            "mapId": self.map.id,
            "characterId": self.fighter.id,
            "footprint": [{"q": 0, "r": 0}],
        })

    def _payload_character(self):
        workspace = combat_workspace_payload(self.user, self.giocatore, self.map.id)
        return next(
            entry["character"]
            for entry in workspace["map"]["participants"]
            if entry["character"]["id"] == self.fighter.id
        )

    def test_conversions_and_default_filters_reach_the_quick_actions_payload(self):
        character = self._payload_character()

        self.assertEqual(character["spellEconomy"], {
            "manaDiscountPerPower": 2,
            "actionPointDiscountPerPower": 1,
            "manaPerEnergy": 4,
            "manaPerActionPoint": 5,
        })
        self.assertEqual(character["actionSettings"]["tags"], {})
        self.assertEqual(character["actionSettings"]["tagFilters"], ["preferito", "combat", "no tag"])

    def test_tags_and_filters_are_stored_on_the_character_without_no_tag(self):
        update_action_settings(self.user, self.giocatore, {
            "mapId": self.map.id,
            "characterId": self.fighter.id,
            "tags": {
                "skill:1:colpo": ["melee", "combat", "inventata"],
                # "no tag" resta implicito: un'azione senza etichette non viene salvata.
                "skill:1:vuota": ["no tag"],
            },
            "tagFilters": ["utility", "melee", "inventata"],
        })
        character = self._payload_character()

        self.assertEqual(character["actionSettings"]["tags"], {"skill:1:colpo": ["combat", "melee"]})
        self.assertEqual(character["actionSettings"]["tagFilters"], ["utility", "melee"])

    def test_an_empty_filter_list_is_kept_instead_of_falling_back_to_the_default(self):
        update_action_settings(self.user, self.giocatore, {
            "mapId": self.map.id,
            "characterId": self.fighter.id,
            "tagFilters": [],
        })

        self.assertEqual(self._payload_character()["actionSettings"]["tagFilters"], [])

    def test_a_player_cannot_configure_a_character_they_do_not_control(self):
        player = Giocatore.objects.create(nome="giocatore-tag", role=Giocatore.ROLE_USER)
        other = get_user_model().objects.create(username="giocatore-tag")

        with self.assertRaises(ApiError) as raised:
            update_action_settings(other, player, {
                "mapId": self.map.id,
                "characterId": self.fighter.id,
                "tagFilters": ["combat"],
            })
        self.assertEqual(raised.exception.status, 403)


class CharacterCloneAndPlannerTests(CombatTestCase):
    def test_import_copies_owned_containers_and_keeps_catalog_references(self):
        source = self.character("Bandito sorgente")
        sword = Oggetto.objects.create(nome="Spada test", modello=False)
        effect = Effetto.objects.create(nome="Effetto test")
        source.effetti = EffettiPersonaggio.objects.create(nome="Bandito sorgente effetti")
        source.equip.arma = sword
        source.zaino.slot_1 = sword
        source.zaino.slot_2 = sword
        source.faretra.slot_1 = sword
        source.effetti.effetto_1 = effect
        source.metadata = {
            "combat_cloned_item_ids": [sword.id],
            "combat_cloned_effect_ids": [effect.id],
        }
        source.equip.save()
        source.zaino.save()
        source.faretra.save()
        source.effetti.save()
        source.save(update_fields=["effetti", "metadata", "updated_at"])
        item_count = Oggetto.objects.count()
        effect_count = Effetto.objects.count()

        imported = import_character(self.user, self.giocatore, {
            "mapId": self.map.id,
            "characterId": source.id,
            "footprint": [{"q": 0, "r": 0}],
        })

        self.assertNotEqual(imported.id, source.id)
        self.assertNotEqual(imported.zaino_id, source.zaino_id)
        self.assertNotEqual(imported.equip_id, source.equip_id)
        self.assertNotEqual(imported.faretra_id, source.faretra_id)
        self.assertNotEqual(imported.note_id, source.note_id)
        self.assertNotEqual(imported.effetti_id, source.effetti_id)
        self.assertEqual(imported.equip.arma_id, sword.id)
        self.assertEqual(imported.zaino.slot_1_id, sword.id)
        self.assertEqual(imported.zaino.slot_2_id, sword.id)
        self.assertEqual(imported.faretra.slot_1_id, sword.id)
        self.assertEqual(imported.effetti.effetto_1_id, effect.id)
        self.assertEqual(Oggetto.objects.count(), item_count)
        self.assertEqual(Effetto.objects.count(), effect_count)
        self.assertNotIn("combat_cloned_item_ids", imported.metadata)
        self.assertNotIn("combat_cloned_effect_ids", imported.metadata)

        token = deletion_preview_token(imported)
        delete_managed_character(self.user, self.giocatore, imported.id, token)
        self.assertFalse(Personaggio.objects.filter(pk=imported.id).exists())
        self.assertTrue(Personaggio.objects.filter(pk=source.id).exists())
        self.assertTrue(Oggetto.objects.filter(pk=sword.id).exists())
        self.assertTrue(Effetto.objects.filter(pk=effect.id).exists())

    def test_repair_migration_restores_shared_catalog_references(self):
        source_item = Oggetto.objects.create(nome="Lama catalogo", modello=False)
        source_effect = Effetto.objects.create(nome="Effetto catalogo")
        cloned_item = Oggetto.objects.create(
            nome="Lama catalogo (copia)",
            modello=False,
            metadata={"combat_clone_source_id": source_item.id},
        )
        cloned_effect = Effetto.objects.create(
            nome="Effetto catalogo (copia)",
            metadata={"combat_clone_source_id": source_effect.id},
        )
        character = self.character("Copia da riparare")
        character.effetti = EffettiPersonaggio.objects.create(
            nome="Copia da riparare effetti",
            effetto_1=cloned_effect,
        )
        character.zaino.slot_1 = cloned_item
        character.metadata = {
            "combat_clone_source_id": 999,
            "combat_owned_item_ids": [source_item.id],
            "combat_cloned_item_ids": [cloned_item.id, {"valore": "invalido"}],
            "combat_cloned_effect_ids": [cloned_effect.id],
        }
        character.zaino.save()
        character.save(update_fields=["effetti", "metadata", "updated_at"])

        migration = importlib.import_module(
            "backend.combat.migrations.0003_repair_combat_catalog_clones"
        )
        migration.repair_combat_catalog_clones(django_apps, None)

        character.refresh_from_db()
        character.zaino.refresh_from_db()
        character.effetti.refresh_from_db()
        self.assertEqual(character.zaino.slot_1_id, source_item.id)
        self.assertEqual(character.effetti.effetto_1_id, source_effect.id)
        self.assertFalse(Oggetto.objects.filter(pk=cloned_item.id).exists())
        self.assertFalse(Effetto.objects.filter(pk=cloned_effect.id).exists())
        self.assertEqual(character.metadata, {"combat_clone_source_id": 999})

    def test_each_planned_action_commits_its_costs_once(self):
        character = self.character("Pianificatore")
        action_map = create_plan_action({
            "mapId": self.map.id,
            "characterId": character.id,
            "actionType": "cast",
            "name": "Lancia Gelo",
            "costs": {"mana": 4, "pa": 2, "stanchezza": 1},
        })
        action = action_map.planned_actions.get()
        commit_plan_action({"actionId": action.id})
        character.refresh_from_db()
        action.refresh_from_db()
        self.assertEqual(character.mana_speso, 4)
        self.assertEqual(action.cost_ap, 2)
        self.assertEqual(character.stanchezza_accumulata, 1)
        self.assertIsNotNone(action.committed_at)


class UnitGenerationTests(CombatTestCase):
    def setUp(self):
        super().setUp()
        self.group = GruppoFamiglieSkill.objects.create(
            nome="Progressione Unit test",
            slug="progressione-unit-test",
        )
        self.normal_family = FamigliaSkill.objects.create(
            nome="Tecniche Unit test",
            gruppo=self.group,
        )
        self.minor_family = FamigliaSkill.objects.create(
            nome="Perk Minori Unit test",
            gruppo=self.group,
            is_perk=True,
        )
        self.major_family = FamigliaSkill.objects.create(
            nome="Perk Maggiori Unit test",
            gruppo=self.group,
            is_perk=True,
        )
        self.skill_number = 70_000

    def skill(self, name, *, family=None, cost=3, tags=None, passives=None):
        self.skill_number += 1
        return Skill.objects.create(
            nome=name,
            slug=f"unit-test-{self.skill_number}",
            numero=self.skill_number,
            famiglia=family or self.normal_family,
            costo_pe=cost,
            tipo_pe="all",
            profile_tags=tags or {},
            effetti_passivi=passives or [],
        )

    def perk_catalog(self):
        for index in range(1, 21):
            self.skill(
                f"Perk minore test {index}",
                family=self.minor_family,
                cost=0,
                tags={"core_fisico": 1, "focus_combat": 1},
            )
        for index in range(1, 11):
            self.skill(
                f"Perk maggiore test {index}",
                family=self.major_family,
                cost=0,
                tags={"core_fisico": 1, "focus_combat": 1},
            )

    def humanoid_unit(self):
        core_first = self.skill(
            "Fondamento del guerriero test",
            tags={"core_fisico": 5, "focus_combat": 3},
            passives=[
                {
                    "id": "unit-core-forza",
                    "name": "Addestramento fisico",
                    "description": "+2 Forza dalla Skill realmente sbloccata.",
                    "icon": "forza",
                    "operations": [
                        {
                            "target": "forza",
                            "operation": "add",
                            "value": "2",
                            "condition": "",
                        }
                    ],
                }
            ],
        )
        core_second = self.skill(
            "Tecnica avanzata del guerriero test",
            tags={"core_fisico": 5, "focus_combat": 4},
        )
        core_second.prerequisiti.add(core_first)
        archetype_first = self.skill("Imboscata del bandito test", tags={"esplorazione_infiltrazione": 4})
        archetype_second = self.skill("Ricatto del bandito test", tags={"sociale": 4})
        archetype_second.prerequisiti.add(archetype_first)
        leather = Oggetto.objects.create(nome="Armatura di pelle Unit test", tipo_1="armatura")
        nordic = Oggetto.objects.create(nome="Armatura nordica Unit test", tipo_1="armatura")
        adamantium = Oggetto.objects.create(nome="Armatura di adamantio Unit test", tipo_1="armatura")
        earring_a = Oggetto.objects.create(nome="Orecchino del predone Unit test", tipo_1="orecchino")
        earring_b = Oggetto.objects.create(nome="Orecchino del guado Unit test", tipo_1="orecchino")
        unit = Unit.objects.create(
            nome="Bandito Unit test",
            categoria="Banditi",
            generation_rules={
                "kind": "humanoid",
                "coreKey": "warrior",
                "coreShare": 0.5,
            },
            stat_profiles={"baseModifiers": {"forza": 1}},
            skill_unlocks=[
                {"skillId": core_first.id, "pool": "core", "weight": 5},
                {"skillId": core_second.id, "pool": "core", "weight": 3},
                {"skillId": archetype_first.id, "weight": 5, "requiredAtLevel": 2},
                {"skillId": archetype_second.id, "weight": 3},
            ],
            equipment_profiles={
                "slots": {
                    "armatura": [
                        {"itemId": leather.id, "minLevel": 1, "maxLevel": 9, "weight": 1},
                        {"itemId": nordic.id, "minLevel": 10, "maxLevel": 20, "weight": 1},
                    ]
                },
                "groups": [
                    {
                        "slots": ["orecchino_1", "orecchino_2"],
                        "count": 1,
                        "items": [
                            {"itemId": earring_a.id, "minLevel": 1, "maxLevel": 20},
                            {"itemId": earring_b.id, "minLevel": 1, "maxLevel": 20},
                        ],
                    }
                ],
            },
        )
        return unit, {
            "core": {core_first.id, core_second.id},
            "archetype": {archetype_first.id, archetype_second.id},
            "leather": leather,
            "nordic": nordic,
            "adamantium": adamantium,
        }

    def test_animals_and_creatures_never_gain_humanoid_skills_or_equipment(self):
        animal = Unit.objects.create(
            nome="Skeever Unit test",
            categoria="Animali",
            generation_rules={"kind": "creature"},
            stat_profiles={
                "baseModifiers": {"forza": 1, "resistenza": 2},
                "perLevelModifiers": {"forza": 0.5, "resistenza": 1},
            },
            skill_actions=[
                {
                    "key": "morso",
                    "name": "Morso infetto",
                    "description": "Azione innata, non Skill a PE.",
                    "minLevel": 1,
                }
            ],
        )
        dragon = Unit.objects.create(
            nome="Drago Unit test",
            categoria="Creature",
            generation_rules={"kind": "creature"},
            stat_profiles={
                "baseModifiers": {"forza": 8},
                "perLevelModifiers": {"forza": 1},
            },
            skill_actions=[
                {
                    "key": "soffio",
                    "name": "Soffio elementale",
                    "description": "Un cono di energia elementale.",
                    "minLevel": 1,
                    "costs": {"energia": 2},
                },
                {
                    "key": "volo",
                    "name": "Volo",
                    "description": "Il drago prende quota.",
                    "minLevel": 5,
                },
            ],
        )

        skeever_20 = create_unit_character(animal, 20, "veterano")
        dragon_1 = create_unit_character(dragon, 1, "cucciolo")
        dragon_20 = create_unit_character(dragon, 20, "antico")

        for character in (skeever_20, dragon_1, dragon_20):
            self.assertIsNone(character.equip_id)
            self.assertIsNone(character.zaino_id)
            self.assertIsNone(character.faretra_id)
            self.assertFalse(SkillPersonaggio.objects.filter(personaggio=character).exists())
        self.assertEqual([entry["name"] for entry in skeever_20.abilita["known"]], ["Morso infetto"])
        self.assertEqual([entry["name"] for entry in dragon_1.abilita["known"]], ["Soffio elementale"])
        self.assertEqual(
            [entry["name"] for entry in dragon_20.abilita["known"]],
            ["Soffio elementale", "Volo"],
        )
        self.assertGreater(dragon_20.tot["forza"], dragon_1.tot["forza"])

    def test_generated_character_snapshots_the_unit_portrait(self):
        first_portrait = UploadedImage.objects.create(
            title="Ritratto Lupo Unit test",
            file="v2/images/personaggi/lupo-unit-test.webp",
            usage_type="character_portrait",
        )
        second_portrait = UploadedImage.objects.create(
            title="Ritratto Lupo nuovo Unit test",
            file="v2/images/personaggi/lupo-unit-test-nuovo.webp",
            usage_type="character_portrait",
        )
        unit = Unit.objects.create(
            nome="Lupo con ritratto Unit test",
            categoria="Animali",
            generation_rules={"kind": "creature"},
            lore_image=first_portrait,
        )

        existing = create_unit_character(unit, 1, "ritratto-originale")
        unit.lore_image = second_portrait
        unit.save(update_fields=["lore_image", "updated_at"])
        future = create_unit_character(unit, 1, "ritratto-nuovo")

        existing.refresh_from_db()
        self.assertEqual(existing.portrait_id, first_portrait.id)
        self.assertEqual(future.portrait_id, second_portrait.id)

    def test_non_humanoid_curves_hit_exact_endpoints_and_are_traced(self):
        animal = Unit.objects.create(
            nome="Gatto con curve Unit test",
            categoria="Animali",
            generation_rules={"kind": "creature"},
            stat_profiles={
                "curves": [
                    {
                        "key": "pf",
                        "profile": "very_low",
                        "level1": 10,
                        "level20": 50,
                        
                    },
                    {
                        "key": "pa",
                        "profile": "high",
                        "level1": 9,
                        "level20": 32,
                        
                    },
                    {
                        "key": "res_fuoco",
                        "profile": "custom",
                        "level1": -2,
                        "level20": 4,
                        
                    },
                ]
            },
        )

        level_1 = create_unit_character(animal, 1, "curve")
        level_10 = create_unit_character(animal, 10, "curve")
        level_20 = create_unit_character(animal, 20, "curve")

        self.assertEqual((level_1.tot["pf"], level_20.tot["pf"]), (10, 50))
        self.assertEqual((level_1.tot["pa"], level_20.tot["pa"]), (9, 32))
        self.assertEqual((level_1.tot["res_fuoco"], level_20.tot["res_fuoco"]), (-2, 4))
        self.assertGreater(level_10.tot["pf"], level_1.tot["pf"])
        self.assertLess(level_10.tot["pf"], level_20.tot["pf"])
        self.assertEqual(
            {entry["key"] for entry in level_20.metadata["unitGeneration"]["statCurves"]},
            {"pf", "pa", "res_fuoco"},
        )
        for character in (level_1, level_10, level_20):
            self.assertIsNone(character.equip_id)
            self.assertFalse(SkillPersonaggio.objects.filter(personaggio=character).exists())

    def test_non_humanoid_with_a_humanoid_pool_is_rejected_instead_of_ignored(self):
        item = Oggetto.objects.create(nome="Armatura impossibile Unit test", tipo_1="armatura")
        invalid = Unit.objects.create(
            nome="Lupo configurato male Unit test",
            categoria="Animali",
            generation_rules={"kind": "creature"},
            equipment_profiles={"slots": {"armatura": [{"itemId": item.id}]}},
        )

        with self.assertRaises(ApiError) as error:
            create_unit_character(invalid, 1)

        self.assertEqual(error.exception.code, "combat.unit_non_humanoid_loadout")

    def test_humanoid_replays_xp_perks_prerequisites_and_level_banded_equipment(self):
        self.perk_catalog()
        unit, catalog = self.humanoid_unit()

        level_1 = create_unit_character(unit, 1, "standard")
        level_20 = create_unit_character(unit, 20, "standard")

        self.assertEqual(level_1.equip.armatura_id, catalog["leather"].id)
        self.assertEqual(level_20.equip.armatura_id, catalog["nordic"].id)
        self.assertNotEqual(level_20.equip.armatura_id, catalog["adamantium"].id)
        self.assertTrue(level_20.skill_sbloccate.filter(skill_id__in=catalog["core"]).exists())
        self.assertTrue(level_20.skill_sbloccate.filter(skill_id__in=catalog["archetype"]).exists())
        self.assertTrue(
            level_20.effetti_personalizzati.filter(origine="Abilità: Fondamento del guerriero test").exists()
        )

        minor_count = level_20.skill_sbloccate.filter(skill__famiglia=self.minor_family).count()
        major_count = level_20.skill_sbloccate.filter(skill__famiglia=self.major_family).count()
        self.assertEqual(minor_count, 20)
        self.assertEqual(major_count, 10)
        self.assertEqual(level_1.skill_sbloccate.filter(skill__famiglia=self.minor_family).count(), 1)
        self.assertEqual(level_1.skill_sbloccate.filter(skill__famiglia=self.major_family).count(), 0)

        trace = level_20.metadata["unitGeneration"]
        self.assertEqual(trace["xp"]["allocatedCore"], trace["xp"]["allocatedArchetype"])
        self.assertTrue(all(entry["cost"] >= 0 for entry in trace["skills"]))
        self.assertEqual({entry["source"] for entry in trace["skills"]}, {"core", "archetype"})
        self.assertEqual(len(trace["perks"]), 30)

    def test_humanoid_unit_can_lock_generated_characters_to_dunmer(self):
        self.perk_catalog()
        unit, _catalog = self.humanoid_unit()
        unit.generation_rules = {**unit.generation_rules, "allowedRaces": ["Dunmer"]}
        unit.save(update_fields=["generation_rules", "updated_at"])

        character = create_unit_character(unit, 1, "ordinatore")

        self.assertEqual(character.razza_1, "Dunmer")
        self.assertIn(character.razza_2, {"Retaggio Mago", "Retaggio Guerriero", "Nobile di Vvardenfell", "Esule di Solstheim", "Servo del Tribunale"})
        self.assertEqual(character.metadata["unitGeneration"]["race"]["allowed"], ["Dunmer"])

    def test_humanoid_unit_can_lock_dremora_to_rank_and_file_subraces(self):
        self.perk_catalog()
        unit, _catalog = self.humanoid_unit()
        unit.generation_rules = {
            **unit.generation_rules,
            "allowedRaces": ["Dremora"],
            "allowedSubraces": ["Churl", "Caitiff", "Kynval"],
        }
        unit.save(update_fields=["generation_rules", "updated_at"])

        characters = [
            create_unit_character(unit, 1, variant)
            for variant in ("dremora-a", "dremora-b", "dremora-c")
        ]

        self.assertEqual({character.razza_1 for character in characters}, {"Dremora"})
        self.assertTrue(
            {character.razza_2 for character in characters}
            <= {"Churl", "Caitiff", "Kynval"}
        )

    def test_same_variant_is_reproducible_and_combat_action_attaches_the_result(self):
        self.perk_catalog()
        unit, catalog = self.humanoid_unit()
        first = create_unit_character(unit, 4, "sentinella")
        second = create_unit_character(unit, 4, "sentinella")

        def signature(character):
            return {
                "skills": list(character.skill_sbloccate.order_by("skill_id").values_list("skill_id", flat=True)),
                "equipment": [
                    character.equip.armatura_id,
                    character.equip.orecchino_1_id,
                    character.equip.orecchino_2_id,
                ],
            }

        self.assertEqual(signature(first), signature(second))
        campaign = DatiCampagna.objects.create(nome="Campagna generazione Unit test", attiva=True)
        self.giocatore.active_campaign = campaign
        self.giocatore.save(update_fields=["active_campaign", "updated_at"])
        generated = generate_unit(
            self.user,
            self.giocatore,
            {
                "mapId": self.map.id,
                "unitId": unit.id,
                "level": 4,
                "variant": "sentinella",
                "footprint": [{"q": 0, "r": 0}, {"q": 1, "r": 0}],
            },
        )
        participant = self.map.participants.get(character=generated)
        self.assertEqual(generated.campagna_id, campaign.id)
        self.assertEqual(set(participant.footprint.values_list("q", "r")), {(0, 0), (1, 0)})
        self.assertIn(generated.id, self.giocatore.character_ids)
        workspace = combat_workspace_payload(self.user, self.giocatore, self.map.id)
        self.assertEqual(workspace["unitCatalog"][0]["generationKind"], "humanoid")

    def test_auto_variant_creates_independent_builds_while_named_variants_stay_stable(self):
        self.perk_catalog()
        unit, _catalog = self.humanoid_unit()
        unit.equipment_profiles["groups"][0].pop("count", None)
        unit.equipment_profiles["groups"][0].update(
            {"minCount": 0, "maxCount": 2, "emptyChance": 0.1}
        )
        unit.save(update_fields=["equipment_profiles", "updated_at"])

        generated = [create_unit_character(unit, 4, "auto") for _index in range(12)]
        seeds = {
            character.metadata["generationSeed"]
            for character in generated
        }
        signatures = {
            (
                tuple(character.skill_sbloccate.order_by("skill_id").values_list("skill_id", flat=True)),
                character.equip.orecchino_1_id,
                character.equip.orecchino_2_id,
            )
            for character in generated
        }

        self.assertEqual(len(seeds), len(generated))
        self.assertGreater(len(signatures), 1)
        self.assertTrue(
            all(character.metadata["generationVariantAutomatic"] for character in generated)
        )

    def test_curated_skill_lists_keep_unlisted_melee_out_of_unit_pools(self):
        self.perk_catalog()
        unit, catalog = self.humanoid_unit()
        melee = self.skill(
            "Carica estranea Unit test",
            cost=1,
            tags={
                "core_fisico": 5,
                "focus_combat": 5,
                "attacco": 5,
            },
        )
        character = create_unit_character(unit, 20, "strict-pools")

        self.assertFalse(character.skill_sbloccate.filter(skill=melee).exists())

    def test_accessory_curve_honors_total_and_guaranteed_ring_group(self):
        self.perk_catalog()
        unit, _catalog = self.humanoid_unit()
        ring = Oggetto.objects.create(
            nome="Anello garantito Unit test",
            tipo_1="anello",
        )
        profile = unit.equipment_profiles
        profile["groups"][0].update({"minCount": 1, "maxCount": 1, "emptyChance": 0})
        profile["groups"].append(
            {
                "name": "Anello obbligatorio",
                "slots": ["anello_1", "anello_2"],
                "minCount": 1,
                "maxCount": 1,
                "emptyChance": 0,
                "items": [{"itemId": ring.id, "minLevel": 1, "maxLevel": 20}],
            }
        )
        profile["accessoryCountByLevel"] = [
            {"minLevel": 1, "maxLevel": 20, "minCount": 2, "maxCount": 2}
        ]
        unit.equipment_profiles = profile
        unit.save(update_fields=["equipment_profiles", "updated_at"])

        character = create_unit_character(unit, 4, "accessory-curve")
        accessory_slots = [
            entry["slot"]
            for entry in character.metadata["unitGeneration"]["equipment"]
            if entry["slot"].startswith(("anello_", "orecchino_"))
        ]

        self.assertEqual(len(accessory_slots), 2)
        self.assertTrue(
            character.equip.anello_1_id or character.equip.anello_2_id
        )
        self.assertTrue(
            character.equip.orecchino_1_id or character.equip.orecchino_2_id
        )

    def test_shared_accessory_profile_uses_elder_level_formula_and_repeatable_kinds(self):
        self.perk_catalog()
        unit, _catalog = self.humanoid_unit()
        ring = Oggetto.objects.create(
            nome="Anello vitale livello cinque Unit test",
            tipo_1="anello",
            tipo_2="pf_item",
            tipo_4="Livello 5",
            effects=[{"target": "pf", "operation": "add", "value": 18}],
        )
        profile = AccessoryProfile.objects.get(key="guerriero")
        profile.rules = {
            "slots": ["anello_1", "anello_2"],
            "countCurve": [{"maxLevel": 20, "count": 2}],
            "countJitter": [0],
            "itemLevelJitter": [0],
            "coreWeight": 3,
            "coreKinds": ["pf_item"],
            "variantPools": [],
            "repeatableKinds": ["pf_item"],
        }
        profile.save(update_fields=["rules", "updated_at"])
        unit.accessory_profile = profile
        unit.equipment_profiles = {
            **unit.equipment_profiles,
            "groups": [],
        }
        unit.save(update_fields=["accessory_profile", "equipment_profiles", "updated_at"])

        character = create_unit_character(unit, 10, "elder-repeatable")

        self.assertEqual(character.equip.anello_1_id, ring.id)
        self.assertEqual(character.equip.anello_2_id, ring.id)
        generated = [
            entry
            for entry in character.metadata["unitGeneration"]["equipment"]
            if entry.get("source") == "accessoryProfile"
        ]
        self.assertEqual(len(generated), 2)
        self.assertEqual({entry["requestedItemLevel"] for entry in generated}, {5})
        self.assertEqual({entry["itemLevel"] for entry in generated}, {5})

    def test_shared_accessory_profile_keeps_nonrepeatable_kinds_unique(self):
        profile = AccessoryProfile.objects.get(key="assassino")
        profile.rules = {
            "slots": ["anello_1", "anello_2"],
            "countCurve": [{"maxLevel": 20, "count": 2}],
            "countJitter": [0],
            "itemLevelJitter": [0],
            "coreWeight": 3,
            "coreKinds": ["attacco_item"],
            "variantPools": [],
            "repeatableKinds": [],
        }
        profile.save(update_fields=["rules", "updated_at"])
        ring = Oggetto.objects.create(
            nome="Anello attacco non ripetibile Unit test",
            tipo_1="anello",
            tipo_2="attacco_item",
            tipo_4="Livello 3",
        )
        totals = default_personaggio_tot()
        totals["anelli_max"] = 4
        character = Personaggio.objects.create(
            nome="Profilo accessori unico Unit test",
            nome_interno="profilo-accessori-unico-unit-test",
            equip=Equip.objects.create(nome="Equip profilo unico Unit test"),
            tot=totals,
        )
        report = {"equipment": [], "warnings": []}

        equip_accessory_profile(character, profile, 6, random.Random(41), report)

        equipped_ids = [
            character.equip.anello_1_id,
            character.equip.anello_2_id,
        ]
        self.assertEqual(equipped_ids.count(ring.id), 1)
        self.assertEqual(report["accessoryProfile"]["generated"], 1)

    def test_shared_accessory_profile_varies_count_slots_and_item_level_by_seed(self):
        profile = AccessoryProfile.objects.get(key="arciere")
        profile.rules = {
            "slots": ["anello_1", "anello_2", "anello_3", "anello_4"],
            "countCurve": [{"maxLevel": 20, "count": 3}],
            "countJitter": [-1, 0, 1],
            "itemLevelJitter": [-2, -1, 0, 1, 2],
            "coreWeight": 3,
            "coreKinds": ["pf_item"],
            "variantPools": [],
            "repeatableKinds": ["pf_item"],
        }
        profile.save(update_fields=["rules", "updated_at"])
        for item_level in range(1, 11):
            Oggetto.objects.create(
                nome=f"Anello vitale casuale L{item_level} Unit test",
                tipo_1="anello",
                tipo_2="pf_item",
                tipo_4=f"Livello {item_level}",
            )
        counts = set()
        levels = set()
        slot_sets = set()
        for seed in range(12):
            totals = default_personaggio_tot()
            totals["anelli_max"] = 4
            character = Personaggio.objects.create(
                nome=f"Profilo casuale {seed} Unit test",
                nome_interno=f"profilo-casuale-{seed}-unit-test",
                equip=Equip.objects.create(nome=f"Equip profilo casuale {seed} Unit test"),
                tot=totals,
            )
            report = {"equipment": [], "warnings": []}
            equip_accessory_profile(character, profile, 10, random.Random(seed), report)
            generated = report["equipment"]
            counts.add(len(generated))
            levels.update(entry["requestedItemLevel"] for entry in generated)
            slot_sets.add(tuple(sorted(entry["slot"] for entry in generated)))

        self.assertGreater(len(counts), 1)
        self.assertGreater(len(levels), 1)
        self.assertGreater(len(slot_sets), 1)

    def test_unified_perk_progression_can_apply_milestone_characteristics(self):
        for name, family in (
            ("+1 caratteristica", self.minor_family),
            ("Migliore (1)", self.major_family),
            ("Migliore (2)", self.major_family),
        ):
            self.skill(
                name,
                family=family,
                cost=0,
                tags={"core_fisico": 1, "focus_combat": 1},
            )
        unit, _catalog = self.humanoid_unit()

        with patch(
            "backend.combat.unit_generation._use_milestone_progression",
            return_value=True,
        ) as path_choice:
            character = create_unit_character(unit, 4, "perk-milestones")
        trace = character.metadata["unitGeneration"]
        improvements = [
            entry["improvement"]
            for entry in trace["perks"]
            if entry.get("improvement")
        ]

        self.assertEqual(len(trace["perks"]), 6)
        self.assertEqual(path_choice.call_count, 4)
        self.assertEqual(len(improvements), 6)
        self.assertEqual(
            character.effetti_personalizzati.filter(origine__startswith="Unit perk:").count(),
            6,
        )
        self.assertEqual(
            character.skill_sbloccate.filter(
                skill__nome__in=["+1 caratteristica", "Migliore (1)", "Migliore (2)"]
            ).count(),
            3,
        )

    def test_management_contract_saves_a_plain_animal_and_rejects_humanoid_features(self):
        values = {
            "name": "Lupo gestito Unit test",
            "category": "Animali",
            "archetypeTags": {},
            "competenceProfile": {},
            "skillUnlocks": [],
            "equipmentSlots": [],
            "equipmentGroups": [],
            "innateActions": [
                {
                    "key": "morso",
                    "name": "Morso",
                    "description": "Attacco naturale.",
                    "minLevel": 1,
                    "maxLevel": 20,
                    "costs": {"pa": 2},
                }
            ],
            "statProfile": {
                "curves": [
                    {
                        "key": "pf",
                        "profile": "low",
                        "level1": 14,
                        "level20": 75,
                        
                    }
                ],
            },
            "generation": {
                "kind": "creature",
            },
        }

        unit, created = save_managed_unit(self.user, self.giocatore, values)

        self.assertTrue(created)
        self.assertEqual(unit.generation_rules["kind"], "creature")
        self.assertEqual(unit.skill_unlocks, [])
        self.assertEqual(unit.equipment_profiles, {})
        self.assertEqual(unit.profilo_competenze, {})
        self.assertEqual(unit.skill_actions[0]["name"], "Morso")
        self.assertEqual(unit.stat_profiles["curves"][0]["level20"], 75.0)

        invalid = {
            **values,
            "name": "Lupo invalido Unit test",
            "skillUnlocks": [{"skillId": 999999}],
        }
        with self.assertRaises(ApiError) as error:
            save_managed_unit(self.user, self.giocatore, invalid)
        self.assertEqual(error.exception.code, "management.units.non_humanoid_skills")

        category = ImageCategory.objects.create(
            name="Personaggi Unit test",
            slug="personaggi",
            usage_types=["character_portrait"],
        )
        portrait = UploadedImage.objects.create(
            title="Lupo gestito Unit test",
            file="v2/images/personaggi/lupo-gestito-unit-test.webp",
            usage_type="character_portrait",
            category=category,
            group="Unit e NPC",
            metadata={"convertedToWebp": True, "webpQuality": 70},
        )
        updated, was_created = save_managed_unit(
            self.user,
            self.giocatore,
            {**values, "loreImageId": portrait.id},
            unit.id,
        )
        self.assertFalse(was_created)
        self.assertEqual(updated.lore_image_id, portrait.id)

        wrong_portrait = UploadedImage.objects.create(
            title="Lupo non conforme Unit test",
            file="v2/images/personaggi/lupo-non-conforme.png",
            usage_type="generic",
            category=category,
            group="Altro",
        )
        with self.assertRaises(ApiError) as portrait_error:
            save_managed_unit(
                self.user,
                self.giocatore,
                {**values, "loreImageId": wrong_portrait.id},
                unit.id,
            )
        self.assertEqual(
            portrait_error.exception.code,
            "management.units.portrait_contract",
        )
        unit.refresh_from_db()
        self.assertEqual(unit.lore_image_id, portrait.id)

    def test_management_preview_rolls_back_and_scales_weighted_competences(self):
        self.perk_catalog()
        unit, _catalog = self.humanoid_unit()
        unit.profilo_competenze = {
            **{key: -5 for key in default_competence_state()},
            "percezione": 5,
        }
        unit.generation_rules = {
            **unit.generation_rules,
            "competenceXp": {"starting": 2, "base": 3, "growth": 0},
        }
        unit.save(update_fields=["profilo_competenze", "generation_rules", "updated_at"])
        character_count = Personaggio.objects.count()

        level_1 = preview_managed_unit(self.user, self.giocatore, unit.id, 1, "test")
        level_20 = preview_managed_unit(self.user, self.giocatore, unit.id, 20, "test")

        self.assertEqual(Personaggio.objects.count(), character_count)
        self.assertEqual(level_1["trace"]["competences"]["earned"], 2)
        self.assertEqual(level_20["trace"]["competences"]["earned"], 59)
        self.assertIn("percezione", level_20["competences"])
        self.assertNotIn("sapienza_magica", level_20["competences"])
        self.assertGreater(
            level_20["competences"]["percezione"]["barra1"],
            level_1["competences"]["percezione"]["barra1"],
        )

    def test_humanoid_level_bands_do_not_bypass_skill_driven_growth(self):
        self.perk_catalog()
        unit, _catalog = self.humanoid_unit()
        unit.stat_profiles = {
            "baseModifiers": {"forza": 1},
            "perLevelModifiers": {"forza": 99},
            "milestones": [{"level": 2, "modifiers": {"forza": 99}}],
        }
        unit.levels = [{"minLevel": 2, "maxLevel": 20, "modifiers": {"forza": 99}}]
        unit.save(update_fields=["stat_profiles", "levels", "updated_at"])

        level_1 = create_unit_character(unit, 1, "crescita")
        level_20 = create_unit_character(unit, 20, "crescita")

        # Both characters receive the same Unit chassis. Any remaining
        # difference is produced by unlocked Skill passives, never by these
        # direct per-level/milestone fields.
        chassis_1 = level_1.effetti_personalizzati.get(origine=f"Unit: {unit.nome}")
        chassis_20 = level_20.effetti_personalizzati.get(origine=f"Unit: {unit.nome}")
        values_1 = dict(chassis_1.operazioni.values_list("bersaglio", "valore"))
        values_20 = dict(chassis_20.operazioni.values_list("bersaglio", "valore"))
        self.assertEqual(values_1, {"forza": "1.0"})
        self.assertEqual(values_20, values_1)

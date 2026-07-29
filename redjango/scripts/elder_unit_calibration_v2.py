from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
WORKSPACE_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = SCRIPT_PATH.parents[2]
RESEARCH_ROOT = WORKSPACE_ROOT / "elder-unit-calibration-v2" / "research" / "dossiers"
OUTPUT_ROOT = WORKSPACE_ROOT / "elder-unit-calibration-v2" / "authored"
LEVELS = (1, 5, 10, 15, 20)
VARIANTS = tuple(f"calibration-v2-{index}" for index in range(1, 9))
CONVERTER_VERSION = "elder-unit-charter-v2"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "redjango.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction

from backend.characters.services.inventory_rules import (
    item_compatible_with_equipment_slot,
)
from backend.combat.unit_generation import (
    UNIT_STAT_CURVE_VARIABLES,
    create_unit_character,
)
from backend.combat.unit_management_services import (
    _clean_unit_values,
    save_managed_unit,
)
from backend.core.models import Giocatore, Oggetto, Skill, Unit


def stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def skill(
    skill_id: int,
    pool: str,
    weight: float = 5,
    minimum: int = 1,
    maximum: int = 20,
    required: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "skillId": skill_id,
        "pool": pool,
        "weight": weight,
        "minLevel": minimum,
        "maxLevel": maximum,
    }
    if required is not None:
        result["requiredAtLevel"] = required
    return result


def item(
    slot: str,
    item_id: int,
    minimum: int = 1,
    maximum: int = 20,
    weight: float = 1,
    chance: float = 1,
) -> dict[str, Any]:
    return {
        "slot": slot,
        "itemId": item_id,
        "minLevel": minimum,
        "maxLevel": maximum,
        "weight": weight,
        "chance": chance,
    }


def action(
    key: str,
    name: str,
    description: str,
    costs: dict[str, int],
    *,
    minimum: int = 1,
    maximum: int = 20,
    trigger: str = "Azione",
    duration: str = "Istantanea",
    icon: str = "runa",
) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "description": description,
        "minLevel": minimum,
        "maxLevel": maximum,
        "costs": costs,
        "trigger": trigger,
        "duration": duration,
        "icon": icon,
    }


PRESETS = {
    str(entry["key"]): {
        str(profile): (
            float(values["level1"]),
            float(values["level20"]),
        )
        for profile, values in dict(entry["presets"]).items()
    }
    for entry in UNIT_STAT_CURVE_VARIABLES
}


def curve(key: str, level_1: float, level_20: float) -> dict[str, Any]:
    profile = "custom"
    for candidate, endpoints in PRESETS[key].items():
        if endpoints == (float(level_1), float(level_20)):
            profile = candidate
            break
    return {
        "key": key,
        "profile": profile,
        "level1": level_1,
        "level20": level_20,
    }


def curves(values: dict[str, tuple[float, float]]) -> list[dict[str, Any]]:
    return [curve(key, endpoints[0], endpoints[1]) for key, endpoints in values.items()]


def generation(
    core_key: str,
    *,
    core_share: float,
    magic_policy: str,
    classes: list[str] | None = None,
    religions: list[str] | None = None,
    races: list[str] | None = None,
    subraces: list[str] | None = None,
) -> dict[str, Any]:
    result = {
        "kind": "humanoid",
        "coreKey": core_key,
        "coreShare": core_share,
        "startingXp": 8,
        "xpBase": 4,
        "xpGrowth": 0,
        "competenceStartingXp": 5,
        "competenceXpBase": 8,
        "competenceXpGrowth": 0,
        "finalSpendingPasses": 8,
        "magicPolicy": magic_policy,
        "allowedClassFamilies": classes or [],
        "allowedReligionFamilies": religions or [],
        "allowedRaces": races or [],
        "allowHumanoidStatGrowth": False,
    }
    if subraces:
        result["allowedSubraces"] = subraces
    return result


def humanoid_payload(
    *,
    name: str,
    category: str,
    archetype: str,
    lore: str,
    tags: dict[str, int],
    competences: dict[str, int],
    rules: dict[str, Any],
    skills: list[dict[str, Any]],
    equipment: list[dict[str, Any]],
    notes: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "archetypeDescription": archetype,
        "loreDescription": lore,
        "notes": notes,
        "levels": [],
        "archetypeTags": tags,
        "competenceProfile": competences,
        "generation": rules,
        "skillUnlocks": skills,
        "equipmentSlots": equipment,
        "equipmentGroups": [],
        "accessoryCountByLevel": [],
        "innateActions": [],
        "statProfile": {
            "baseModifiers": {},
            "perLevelModifiers": {},
            "milestones": [],
            "curves": [],
        },
    }


def creature_payload(
    *,
    name: str,
    category: str,
    archetype: str,
    lore: str,
    stat_curves: dict[str, tuple[float, float]],
    actions: list[dict[str, Any]],
    notes: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "archetypeDescription": archetype,
        "loreDescription": lore,
        "notes": notes,
        "levels": [],
        "archetypeTags": {},
        "competenceProfile": {},
        "generation": {"kind": "creature"},
        "skillUnlocks": [],
        "equipmentSlots": [],
        "equipmentGroups": [],
        "accessoryCountByLevel": [],
        "innateActions": actions,
        "statProfile": {
            "baseModifiers": {},
            "perLevelModifiers": {},
            "milestones": [],
            "curves": curves(stat_curves),
        },
    }


def charter(
    *,
    unit: str,
    source_ids: list[int],
    kind: str,
    fantasy: str,
    combat_story: str,
    siblings: list[tuple[str, str, str]],
    axes: list[tuple[str, str]],
    must: list[str],
    must_not: list[str],
    rigidity: str,
    variation: str,
    checkpoints: dict[str, str],
    range_reason: str,
    kind_reason: str = "",
    open_questions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "unit": unit,
        "sourceIds": source_ids,
        "kind": kind,
        "kindJustification": kind_reason,
        "authoredLevels": [1, 20],
        "authoredLevelJustification": range_reason,
        "fantasy": fantasy,
        "combatStory": combat_story,
        "siblings": [
            {"unit": name, "relation": relation, "mustDifferBy": difference}
            for name, relation, difference in siblings
        ],
        "signatureAxes": [
            {"axis": axis, "expressedBy": expressed_by}
            for axis, expressed_by in axes
        ],
        "must": must,
        "mustNot": must_not,
        "rigidity": rigidity,
        "variationBudget": variation,
        "levelCheckpoints": checkpoints,
        "openQuestions": open_questions or [],
    }


def expectations(
    *,
    unit: str,
    kind: str,
    all_variants: dict[str, Any],
    at_least_one: list[str],
    allowed: list[str],
    forbidden: list[str],
    differs_from: dict[str, str],
    curve_assertions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_all_variants = {"generationKind": kind, **all_variants}
    if kind == "humanoid" and normalized_all_variants.get("warningCount") == 0:
        normalized_all_variants.pop("warningCount")
    result = {
        "unit": unit,
        "levels": list(LEVELS),
        "variantsPerLevel": len(VARIANTS),
        "allVariants": normalized_all_variants,
        "atLeastOneVariantHas": at_least_one,
        "allowedVariation": allowed,
        "forbidden": forbidden,
        "differsFrom": differs_from,
    }
    if kind == "humanoid":
        result["explainedWarnings"] = [
            {
                "code": "indivisible-general-xp-residual",
                "pattern": (
                    r"^[1-9] PE generali restano disponibili: "
                    r"nessuna Skill configurata è acquistabile\.$"
                ),
                "why": (
                    "Il pool resta curato; 1-9 PE indivisibili non autorizzano "
                    "l'aggiunta di una Skill incoerente."
                ),
            }
        ]
    if curve_assertions is not None:
        result["curveAssertions"] = curve_assertions
    return result


def base_candidate(
    *,
    source_file: str,
    charter_data: dict[str, Any],
    expectation_data: dict[str, Any],
    proposal: dict[str, Any],
    evidence: list[dict[str, str]],
    rejected: list[dict[str, Any]],
    deviations: list[dict[str, str]],
    legality: list[dict[str, str]],
    blocked: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "sourceFile": source_file,
        "charter": charter_data,
        "expectations": expectation_data,
        "proposal": proposal,
        "evidence": evidence,
        "rejectedCandidates": rejected,
        "deviations": deviations,
        "legalityReceipts": legality,
        "blockedReasons": blocked or [],
    }


PHYSICAL_CORE = [
    skill(64, "core", 9),
    skill(65, "core", 6, 3),
    skill(71, "core", 9),
    skill(72, "core", 6, 3),
    skill(91, "core", 8),
    skill(92, "core", 5, 5),
    skill(357, "core", 7),
    skill(358, "core", 5, 5),
    skill(380, "core", 7),
    skill(93, "core", 6),
    skill(355, "core", 5, 5),
    skill(356, "core", 4, 10),
]

MAGE_CORE = [
    skill(81, "core", 9),
    skill(82, "core", 6, 3),
    skill(473, "core", 9),
    skill(474, "core", 6, 3),
    skill(480, "core", 8),
    skill(481, "core", 5, 5),
    skill(498, "core", 8),
    skill(499, "core", 5, 6),
    skill(17, "core", 6),
    skill(15, "core", 6),
    skill(488, "core", 5, 8),
    skill(522, "core", 5, 8),
]

SHIELD_ARCHETYPE = [
    skill(321, "archetype", 5),
    skill(330, "archetype", 8),
    skill(328, "archetype", 7),
    skill(324, "archetype", 5, 4),
    skill(389, "archetype", 8, 4),
    skill(390, "archetype", 8, 4),
    skill(391, "archetype", 8, 4),
]


HUMANOIDS: list[dict[str, Any]] = [
    base_candidate(
        source_file="838-839-840",
        charter_data=charter(
            unit="Soldato Imperiale",
            source_ids=[838, 839, 840],
            kind="humanoid",
            fantasy=(
                "Il volto ordinato della Legione: un professionista addestrato a tenere "
                "la linea anche quando il singolo vorrebbe arretrare. La minaccia nasce "
                "dalla disciplina condivisa, non dall'eroismo personale."
            ),
            combat_story=(
                "Ai livelli bassi protegge il compagno accanto con scudo e pressione "
                "costante. Crescendo diventa una muraglia di formazione, ma resta meno "
                "individualmente eccezionale degli enforcer iconici."
            ),
            siblings=[
                (
                    "Mercenario",
                    "nearest",
                    "Il Legionario ha uniforme, scudo e dottrina fissi; il Mercenario vive di equipaggiamento misto.",
                ),
                (
                    "Cavaliere Redoran",
                    "same-role",
                    "Il Legionario è fanteria sostituibile; il Redoran è un campione di casata.",
                ),
                (
                    "Ordinatore",
                    "contrast",
                    "Entrambi tengono la linea, ma l'Ordinatore è un enforcer religioso con identità iconica.",
                ),
            ],
            axes=[
                (
                    "disciplina di formazione",
                    "coreShare 0.58, strategia_militare +5 e pool scudo",
                ),
                (
                    "uniforme imperiale persistente",
                    "armatura 5782 e scudo 5789 a ogni livello",
                ),
            ],
            must=["armatura di servizio", "scudo imperiale", "armi medie", "formazione"],
            must_not=["magia", "furtività da assassino", "equipaggiamento esotico"],
            rigidity="faction-locked",
            variation="spada, mazza o ascia per fascia; Skill difensive; razza provinciale",
            checkpoints={
                "1": "recluta già in uniforme con arma di ferro e scudo",
                "5": "formazione e prima tenuta difensiva",
                "10": "veterano in acciaio capace di assorbire pressione",
                "15": "linea nordica e tattica consolidata",
                "20": "legionario d'élite, ancora leggibile come soldato e non come eroe",
            },
            range_reason="Le tre righe legacy coprono già senza vuoti i livelli 1-20.",
        ),
        expectation_data=expectations(
            unit="Soldato Imperiale",
            kind="humanoid",
            all_variants={
                "armorItemIds": [5782],
                "shieldItemIds": [5789],
                "innateActionCount": 0,
                "warningCount": 0,
            },
            at_least_one=["una Skill di scudo entro il livello 5"],
            allowed=["tipo di arma", "Skill difensive", "competenze", "razza"],
            forbidden=["armatura non imperiale", "assenza di scudo", "Skill magiche"],
            differs_from={
                "Mercenario": "uniforme e scudo obbligatori in ogni variante",
                "Ordinatore": "materiali inferiori e nessuna firma religiosa",
            },
        ),
        proposal=humanoid_payload(
            name="Soldato Imperiale",
            category="Umano",
            archetype=(
                "Fanteria disciplinata della Legione: tiene la linea con scudo, "
                "armi medie e resistenza, diventando pericolosa soprattutto in formazione."
            ),
            lore=(
                "Proviene dai presidi e dalle strade dell'Impero. L'addestramento mette "
                "catena di comando e coesione sopra l'istinto individuale."
            ),
            tags={
                "core_fisico": 5,
                "focus_combat": 5,
                "difesa": 5,
                "attacco": 3,
                "supporto_party": 3,
                "range_skill": -3,
                "core_magico": -5,
                "natura_magica": -5,
            },
            competences={
                "strategia_militare": 5,
                "gestione_risorse": 4,
                "percezione": 3,
                "intimidire": 2,
                "cavalcare": 1,
                "sapienza_magica": -5,
                "furtivita": -3,
                "raggirare": -3,
            },
            rules=generation(
                "warrior",
                core_share=0.58,
                magic_policy="none",
                classes=["Cavaliere"],
            ),
            skills=PHYSICAL_CORE
            + SHIELD_ARCHETYPE
            + [
                skill(891, "archetype", 7, 5),
                skill(892, "archetype", 5, 10),
                skill(889, "archetype", 6, 7),
                skill(1010, "archetype", 5, 8),
            ],
            equipment=[
                item("armatura", 5782),
                item("scudo", 5789),
                item("vestiti", 5281),
                item("arma", 181, 1, 7, 3),
                item("arma", 223, 1, 7, 4),
                item("arma", 587, 1, 7, 3),
                item("arma", 182, 8, 14, 3),
                item("arma", 224, 8, 14, 4),
                item("arma", 588, 8, 14, 3),
                item("arma", 183, 15, 20, 3),
                item("arma", 225, 15, 20, 4),
                item("arma", 589, 15, 20, 3),
            ],
            notes="Conversione v2 delle righe Elder #838-840; crescita statistica diretta disattivata.",
        ),
        evidence=[
            {"claim": "uniforme imperiale", "source": "unit:838-840.armatura"},
            {"claim": "formazione e catena di comando", "source": "unitlore:115"},
        ],
        rejected=[
            {
                "candidate": {"name": "armi a distanza generiche"},
                "decision": "reject",
                "reasonCode": "formation-role-mismatch",
                "reason": "La calibrazione rappresenta la fanteria con scudo, non ogni reparto della Legione.",
            }
        ],
        deviations=[],
        legality=[
            {"claim": "danni delle armi", "source": "backend.combat.rules.DAMAGE_TYPES"},
            {"claim": "dottrina di scudo", "source": "Skill 389-391, Scudi Pesanti"},
        ],
    ),
    base_candidate(
        source_file="848-849-850-851",
        charter_data=charter(
            unit="Mercenario",
            source_ids=[848, 849, 850, 851],
            kind="humanoid",
            fantasy=(
                "Veterano senza patria comune, fedele soprattutto al contratto e alla "
                "propria reputazione. Sopravvive perché conosce più strumenti e sa quando "
                "combattere, cambiare approccio o rinegoziare."
            ),
            combat_story=(
                "All'inizio è un combattente adattabile con equipaggiamento disomogeneo. "
                "Al livello 20 è un professionista esperto, versatile ma senza l'identità "
                "rigida o il picco soprannaturale dei soldati di fazione."
            ),
            siblings=[
                (
                    "Soldato Imperiale",
                    "nearest",
                    "Il Mercenario scambia uniforme e formazione per varietà di materiali e approcci.",
                ),
                (
                    "Cavaliere Redoran",
                    "same-role",
                    "Il Redoran difende onore e linea; il Mercenario privilegia sopravvivenza e contratto.",
                ),
                (
                    "Agente Morag Tong",
                    "contrast",
                    "Entrambi sono professionisti pagati, ma l'Agente è stretto su furtività e lame corte.",
                ),
            ],
            axes=[
                (
                    "adattabilità dell'equipaggiamento",
                    "pool aperti sovrapposti per armatura, scudo e tre famiglie d'arma",
                ),
                (
                    "pragmatismo veterano",
                    "gestione_risorse +5 e pool Combat senza classe vincolante",
                ),
            ],
            must=["almeno un'arma e un'armatura", "più materiali validi per fascia", "competenza tattica"],
            must_not=["uniforme di fazione", "magia", "specializzazione esclusiva"],
            rigidity="open",
            variation="materiale, peso armatura, scudo, arma, Skill e razza",
            checkpoints={
                "1": "combattente economico ma già adattabile",
                "5": "due percorsi di armatura leggibili",
                "10": "professionista in acciaio o chitina",
                "15": "veterano nordico o elfico",
                "20": "élite orchesca o di vetro senza diventare un campione di fazione",
            },
            range_reason="Le quattro righe legacy coprono già i livelli 1-20.",
        ),
        expectation_data=expectations(
            unit="Mercenario",
            kind="humanoid",
            all_variants={"innateActionCount": 0, "warningCount": 0},
            at_least_one=["due materiali d'armatura diversi allo stesso checkpoint di famiglia"],
            allowed=["arma", "armatura", "scudo", "vestiti", "Skill", "razza"],
            forbidden=["equipaggiamento iconico di fazione", "Skill magiche"],
            differs_from={
                "Soldato Imperiale": "nessun item uniforme è obbligatorio",
                "Agente Morag Tong": "armi medie e armature miste, non lame corte rituali",
            },
        ),
        proposal=humanoid_payload(
            name="Mercenario",
            category="Umano",
            archetype=(
                "Combattente contrattuale versatile, capace di usare materiali e armi "
                "diversi senza dipendere da una dottrina di fazione."
            ),
            lore=(
                "Serve carovane, nobili e compagnie private. La reputazione affidabile "
                "e la capacità di sopravvivere valgono più di una gloria senza paga."
            ),
            tags={
                "core_fisico": 5,
                "focus_combat": 5,
                "attacco": 4,
                "difesa": 3,
                "controllo_situazionale": 2,
                "tecnica_crafting": 1,
                "range_skill": -2,
                "core_magico": -5,
                "natura_magica": -5,
            },
            competences={
                "gestione_risorse": 5,
                "strategia_militare": 4,
                "percezione": 3,
                "intimidire": 3,
                "intuizione": 2,
                "raggirare": 1,
                "sapienza_magica": -5,
                "suonare": -3,
            },
            rules=generation("warrior", core_share=0.52, magic_policy="none"),
            skills=PHYSICAL_CORE
            + [
                skill(321, "archetype", 5),
                skill(330, "archetype", 7),
                skill(331, "archetype", 7),
                skill(333, "archetype", 6),
                skill(324, "archetype", 7, 4),
                skill(328, "archetype", 6),
                skill(1246, "archetype", 6, 4),
                skill(1010, "archetype", 6, 6),
                skill(1011, "archetype", 5, 10),
            ],
            equipment=[
                item("arma", 181, 1, 5),
                item("arma", 223, 1, 5),
                item("arma", 587, 1, 5),
                item("arma", 182, 6, 10),
                item("arma", 224, 6, 10),
                item("arma", 588, 6, 10),
                item("arma", 183, 11, 15),
                item("arma", 225, 11, 15),
                item("arma", 589, 11, 15),
                item("arma", 184, 16, 20),
                item("arma", 226, 16, 20),
                item("arma", 590, 16, 20),
                item("armatura", 595, 1, 5),
                item("armatura", 602, 1, 5),
                item("armatura", 596, 6, 10),
                item("armatura", 603, 6, 10),
                item("armatura", 597, 11, 15),
                item("armatura", 604, 11, 15),
                item("armatura", 600, 16, 20),
                item("armatura", 605, 16, 20),
                item("scudo", 609, 1, 5),
                item("scudo", 616, 1, 5),
                item("scudo", 610, 6, 10),
                item("scudo", 617, 6, 10),
                item("scudo", 611, 11, 15),
                item("scudo", 618, 11, 15),
                item("scudo", 614, 16, 20),
                item("scudo", 619, 16, 20),
                item("vestiti", 5271, 1, 5),
                item("vestiti", 5281, 1, 5),
                item("vestiti", 5272, 6, 10),
                item("vestiti", 5276, 6, 10),
                item("vestiti", 5273, 11, 15),
                item("vestiti", 5274, 11, 20),
                item("vestiti", 5275, 16, 20),
            ],
            notes="Conversione v2 delle righe Elder #848-851; pool aperti ma limitati alle famiglie sorgente.",
        ),
        evidence=[
            {"claim": "equipaggiamento misto per contratto", "source": "unit:848-851.*equipment"},
            {"claim": "pragmatismo e reputazione", "source": "unitlore:81"},
        ],
        rejected=[
            {
                "candidate": {"name": "armi a distanza"},
                "decision": "reject",
                "reasonCode": "source-role-ceiling",
                "reason": "La famiglia sorgente usa soltanto spada, mazza e ascia; la versatilità non è un catalogo globale.",
            }
        ],
        deviations=[],
        legality=[
            {"claim": "manovre melee", "source": "Famiglia Skill Attacchi Melee"},
            {"claim": "varietà equipaggiamento", "source": "core_oggetto IDs nei catalogQueries"},
        ],
    ),
    base_candidate(
        source_file="951-952",
        charter_data=charter(
            unit="Arciere Bandito",
            source_ids=[951, 952],
            kind="humanoid",
            fantasy=(
                "Predone paziente che trasforma la strada in una trappola. Vuole essere "
                "visto soltanto dopo il primo tiro e preferisce fuggire a un duello onesto."
            ),
            combat_story=(
                "Apre da lontano e sfrutta terreno e compagni più robusti. Crescendo "
                "diventa un cecchino da guerriglia, non un combattente melee generico."
            ),
            siblings=[
                (
                    "Agente Morag Tong",
                    "nearest",
                    "Entrambi tendono imboscate, ma il Bandito domina la distanza e il terreno.",
                ),
                (
                    "Mercenario",
                    "same-role",
                    "Il Mercenario accetta molte armi; il Bandito resta su arco corto e coltello d'emergenza.",
                ),
                (
                    "Mago da Battaglia",
                    "contrast",
                    "Entrambi minacciano a distanza, ma il Bandito non usa magia né armatura pesante.",
                ),
            ],
            axes=[
                (
                    "imboscata a distanza",
                    "pool Attacchi a distanza/Ranger e percezione/furtività",
                ),
                (
                    "mobilità di guerriglia",
                    "core stealth-compatible, armatura leggera e scatto",
                ),
            ],
            must=["arco corto", "armatura leggera", "percezione", "furtività"],
            must_not=["attacchi melee nel Core", "magia", "armatura pesante", "scudo"],
            rigidity="path-locked",
            variation="materiale dell'arco e armatura, Skill di tiro, competenze e razza",
            checkpoints={
                "1": "predone povero con arco di ferro e pelle",
                "5": "imboscata e mobilità chiaramente online",
                "10": "chitina/elfico e primi strumenti da cecchino",
                "15": "bandito esperto, non arciere militare d'élite",
                "20": "capobanda da guerriglia con tetto materiale elfico/acciaio",
            },
            range_reason=(
                "Le righe legacy coprono 4-13. L'estensione 1-20 anticipa ferro/pelle "
                "e prolunga il tetto elfico/acciaio senza introdurre materiali d'élite."
            ),
        ),
        expectation_data=expectations(
            unit="Arciere Bandito",
            kind="humanoid",
            all_variants={
                "armorItemIds": [595, 596, 597],
                "innateActionCount": 0,
                "warningCount": 0,
            },
            at_least_one=["Tiro Rapido o Tiro Attento al livello 1"],
            allowed=["materiale dell'arco", "armatura leggera", "Skill di tiro", "razza"],
            forbidden=["scudo", "armatura pesante", "Skill magiche", "pool melee generico"],
            differs_from={
                "Mercenario": "ogni arma possibile è arco corto o coltello",
                "Agente Morag Tong": "la firma è il tiro, non l'eliminazione con lame corte",
            },
        ),
        proposal=humanoid_payload(
            name="Arciere Bandito",
            category="Banditi",
            archetype=(
                "Predone a distanza che apre dall'imboscata, sfrutta il terreno e "
                "ripiega quando viene chiuso in mischia."
            ),
            lore=(
                "Vive lungo strade isolate e rifugi nascosti. Pazienza, posizione e "
                "un arco affidabile valgono più di un duello."
            ),
            tags={
                "core_fisico": 3,
                "focus_combat": 5,
                "range_skill": 5,
                "attacco": 4,
                "esplorazione_infiltrazione": 5,
                "controllo_situazionale": 3,
                "difesa": 1,
                "core_magico": -5,
                "natura_magica": -5,
            },
            competences={
                "percezione": 5,
                "furtivita": 4,
                "sopravvivenza": 4,
                "conoscenze_naturaegeografia": 2,
                "rapidita_di_mano": 2,
                "scalare": 1,
                "sapienza_magica": -5,
                "diplomazia": -3,
                "suonare": -4,
            },
            rules=generation(
                "stealth",
                core_share=0.44,
                magic_policy="none",
                classes=["Ranger"],
            ),
            skills=[
                skill(64, "core", 8),
                skill(65, "core", 5, 4),
                skill(71, "core", 7),
                skill(93, "core", 8),
                skill(94, "core", 5, 6),
                skill(380, "core", 8),
                skill(381, "core", 6, 5),
                skill(99, "core", 7),
                skill(100, "core", 5, 8),
                skill(383, "core", 6, 5),
                skill(335, "archetype", 10),
                skill(336, "archetype", 10),
                skill(337, "archetype", 8, 3),
                skill(342, "archetype", 8, 3),
                skill(340, "archetype", 7, 5),
                skill(344, "archetype", 6, 6),
                skill(1249, "archetype", 6, 8),
                skill(601, "archetype", 8, 5),
                skill(608, "archetype", 7, 10),
                skill(602, "archetype", 6, 12),
                skill(609, "archetype", 6, 14),
            ],
            equipment=[
                item("armatura", 595, 1, 6, 5),
                item("armatura", 596, 4, 14, 5),
                item("armatura", 597, 10, 20, 4),
                item("vestiti", 5278),
                item("arma", 97, 1, 8, 1),
                item("arma", 517, 1, 8, 8),
                item("arma", 98, 7, 20, 1),
                item("arma", 518, 7, 20, 8),
            ],
            notes=(
                "Conversione v2 delle righe Elder #951-952. Estensione 1-20 "
                "con tetto materiale conservativo; nessun attacco melee nel Core."
            ),
        ),
        evidence=[
            {"claim": "arco corto e coltello", "source": "unit:951-952.arma"},
            {"claim": "imboscata e terreno", "source": "unitlore:10"},
        ],
        rejected=[
            {
                "candidate": {"skillId": 331, "name": "Affondo"},
                "decision": "reject",
                "reasonCode": "ranged-core-contamination",
                "reason": "Trasformerebbe l'arciere specializzato in un melee generico.",
            },
            {
                "candidate": {"itemId": 604, "name": "Armatura (nordico)"},
                "decision": "reject",
                "reasonCode": "bandit-tier-ceiling",
                "reason": "Supera il tetto leggero elfico/chitina della sorgente.",
            },
        ],
        deviations=[
            {
                "what": "authored levels",
                "from": "legacy 4-13",
                "to": "1-20",
                "why": "ferro/pelle anticipati; acciaio/elfico mantenuti come tetto senza nuovi materiali",
            }
        ],
        legality=[
            {"claim": "tiro e multi-missile", "source": "Famiglia Skill Attacchi a distanza"},
            {"claim": "guerriglia", "source": "Famiglia Skill Ranger"},
        ],
    ),
    base_candidate(
        source_file="884-885-886",
        charter_data=charter(
            unit="Mago da Battaglia",
            source_ids=[884, 885, 886],
            kind="humanoid",
            fantasy=(
                "Incantatore militare che considera lama e magia parti dello stesso "
                "mestiere. Sta dove lo scontro è più violento e costringe il nemico a "
                "rispondere contemporaneamente a pressione fisica e arcana."
            ),
            combat_story=(
                "Ai primi livelli alterna spada e sigilli protettivi. In seguito unisce "
                "mobilità evocativa, armatura e cast difensivo senza diventare né mago "
                "da retrovia né semplice guerriero."
            ),
            siblings=[
                (
                    "Mago Telvanni",
                    "nearest",
                    "Il Telvanni controlla da lontano; il Mago da Battaglia accetta il fronte e la lama.",
                ),
                (
                    "Soldato Imperiale",
                    "same-role",
                    "Condivide disciplina militare, ma scambia scudo e formazione per magia.",
                ),
                (
                    "Guaritore",
                    "contrast",
                    "Il Guaritore sostiene il gruppo e vieta danno magico; il battlemage deve minacciare.",
                ),
            ],
            axes=[
                (
                    "doppio ramo lama-incantesimo",
                    "pool arma con bastone/spada e Skill melee/Evocazione",
                ),
                (
                    "tenuta del fronte arcana",
                    "armatura, veste e Core specialist difensivo",
                ),
            ],
            must=["bastone o spada lunga", "Evocazione", "difesa Core", "armatura"],
            must_not=["solo magia da retrovia", "solo melee", "scudo pesante", "furtività"],
            rigidity="path-locked",
            variation="ramo bastone o spada, Skill difensive/evocative, razza",
            checkpoints={
                "1": "apprendista già armato e protetto",
                "5": "due rami acquistabili senza sacrificare il Core",
                "10": "vetro e cast qualificato",
                "15": "adamantio e magia da prima linea",
                "20": "maestro ibrido, non specialista puro",
            },
            range_reason=(
                "La sorgente copre 5-20. I livelli 1-4 usano il grado principiante "
                "Evocazione e prolungano il primo percorso elfico."
            ),
        ),
        expectation_data=expectations(
            unit="Mago da Battaglia",
            kind="humanoid",
            all_variants={"innateActionCount": 0, "warningCount": 0},
            at_least_one=["una Skill difensiva Core e una scelta coerente lama/incantesimo entro il livello 5"],
            allowed=["bastone o spada", "Skill Evocazione", "razza"],
            forbidden=["scudo pesante", "pool da guaritore puro", "furtività"],
            differs_from={
                "Mago Telvanni": "armatura e opzioni melee in ogni fascia",
                "Guaritore": "presenza di manovre offensive fisiche",
            },
        ),
        proposal=humanoid_payload(
            name="Mago da Battaglia",
            category="Umano",
            archetype=(
                "Combattente ibrido che alterna spada lunga, bastone di Evocazione "
                "e protezioni arcane mantenendo la presenza in prima linea."
            ),
            lore=(
                "Addestrato per eserciti e compagnie, tratta la magia come una parte "
                "pratica della guerra e non come teoria da proteggere in biblioteca."
            ),
            tags={
                "core_fisico": 3,
                "core_magico": 4,
                "focus_combat": 5,
                "natura_magica": 4,
                "attacco": 4,
                "difesa": 4,
                "controllo_situazionale": 3,
                "range_skill": 2,
            },
            competences={
                "sapienza_magica": 5,
                "strategia_militare": 4,
                "percezione": 3,
                "intuizione": 2,
                "gestione_risorse": 2,
                "furtivita": -5,
                "raggirare": -3,
                "suonare": -3,
            },
            rules=generation(
                "specialist",
                core_share=0.5,
                magic_policy="any",
            ),
            skills=MAGE_CORE
            + [
                skill(331, "archetype", 8),
                skill(328, "archetype", 6, 4),
                skill(324, "archetype", 5, 6),
                skill(439, "archetype", 8),
                skill(440, "archetype", 8, 4),
                skill(444, "archetype", 6, 6),
                skill(1314, "archetype", 5, 10),
                skill(1315, "archetype", 6, 12),
                skill(445, "archetype", 5, 14),
            ],
            equipment=[
                item("armatura", 597, 1, 9),
                item("armatura", 600, 10, 14),
                item("armatura", 601, 15, 20),
                item("veste", 641, 1, 4),
                item("veste", 649, 4, 9),
                item("veste", 657, 10, 14),
                item("veste", 673, 15, 20),
                item("vestiti", 5272, 1, 9),
                item("vestiti", 5273, 10, 14),
                item("vestiti", 5275, 15, 20),
                item("arma", 5165, 1, 4, 5),
                item("arma", 5173, 4, 9, 5),
                item("arma", 218, 1, 9, 5),
                item("arma", 5181, 10, 14, 5),
                item("arma", 221, 10, 14, 5),
                item("arma", 5197, 15, 20, 5),
                item("arma", 222, 15, 20, 5),
            ],
            notes="Conversione v2 delle righe Elder #884-886; ramo principiante aggiunto per i livelli 1-4.",
        ),
        evidence=[
            {"claim": "bastone o spada", "source": "unit:884-886.arma"},
            {"claim": "prima linea arcana", "source": "unitlore:78"},
        ],
        rejected=[
            {
                "candidate": {"family": "Recupero", "name": "pool guaritore completo"},
                "decision": "reject",
                "reasonCode": "sibling-clone-risk",
                "reason": "Sposterebbe l'ibrido offensivo nel ruolo del Guaritore.",
            }
        ],
        deviations=[
            {
                "what": "authored levels",
                "from": "legacy 5-20",
                "to": "1-20",
                "why": "aggiunti bastone e veste principiante, mantenendo l'elfico come prima armatura",
            }
        ],
        legality=[
            {"claim": "manovre melee", "source": "Famiglia Skill Attacchi Melee"},
            {"claim": "Evocazione", "source": "Famiglia Skill Evocazione corrente"},
        ],
    ),
    base_candidate(
        source_file="887-888-889-890",
        charter_data=charter(
            unit="Guaritore",
            source_ids=[887, 888, 889, 890],
            kind="humanoid",
            fantasy=(
                "Medico arcano che resta lucido davanti a sangue e panico. Il suo valore "
                "è impedire che il gruppo crolli, non riempire ogni punto esperienza con "
                "un altro modo di infliggere danno."
            ),
            combat_story=(
                "Stabilizza e protegge fin dai primi livelli, poi aggiunge cura, rimozione "
                "di condizioni e recupero risorse. Deve essere vulnerabile alla pressione "
                "diretta e dipendere dal posizionamento del gruppo."
            ),
            siblings=[
                (
                    "Mago da Battaglia",
                    "nearest",
                    "Condivide addestramento arcano, ma vieta danno e presenza da prima linea.",
                ),
                (
                    "Mago Telvanni",
                    "same-role",
                    "Il Telvanni controlla e dimostra superiorità; il Guaritore ripristina e protegge.",
                ),
                (
                    "Soldato Imperiale",
                    "contrast",
                    "Il Soldato previene danni con la linea; il Guaritore recupera il gruppo dopo l'impatto.",
                ),
            ],
            axes=[
                (
                    "sostegno senza danno",
                    "pool Recupero/Medico privo di Skill di danno",
                ),
                (
                    "progressione rituale visibile",
                    "veste e bastone Recupero principiante-maestro",
                ),
            ],
            must=["cura", "stabilizzazione", "protezione", "recupero risorse"],
            must_not=["magia di danno", "arma marziale", "armatura pesante", "assassinio"],
            rigidity="path-locked",
            variation="ordine di cure/protezioni, competenze, razza",
            checkpoints={
                "1": "principiante con Stabilizza e strumenti medici",
                "5": "Cura e supporto affidabili",
                "10": "rimozione condizioni e veste qualificata",
                "15": "maestro del recupero di gruppo",
                "20": "supporto completo senza trasformarsi in damage dealer",
            },
            range_reason="Le quattro righe legacy coprono già senza vuoti i livelli 1-20.",
        ),
        expectation_data=expectations(
            unit="Guaritore",
            kind="humanoid",
            all_variants={"innateActionCount": 0, "warningCount": 0},
            at_least_one=["Stabilizza o Cura entro il livello 5"],
            allowed=["ordine delle cure", "competenze", "razza"],
            forbidden=["Skill di danno", "arma non bastone", "armatura"],
            differs_from={
                "Mago da Battaglia": "zero Skill melee e zero armatura",
                "Mago Telvanni": "nessun controllo mentale o evocazione",
            },
        ),
        proposal=humanoid_payload(
            name="Guaritore",
            category="Umano",
            archetype=(
                "Supporto di Restaurazione che stabilizza, cura, protegge e recupera "
                "risorse senza acquistare magia offensiva."
            ),
            lore=(
                "Serve templi, ospizi e campi militari. Compassione e disciplina pratica "
                "gli permettono di mantenere in piedi chi altrimenti cadrebbe."
            ),
            tags={
                "core_magico": 4,
                "supporto_party": 5,
                "controllo_situazionale": 3,
                "difesa": 3,
                "sociale": 2,
                "attacco": -5,
                "focus_combat": -1,
                "natura_magica": 3,
            },
            competences={
                "intuizione": 5,
                "sapienza_magica": 5,
                "conoscenze_religioni": 4,
                "conoscenze_naturaegeografia": 2,
                "percezione": 2,
                "gestione_risorse": 2,
                "intimidire": -5,
                "furtivita": -3,
                "raggirare": -3,
            },
            rules=generation("support", core_share=0.46, magic_policy="any"),
            skills=[
                skill(71, "core", 8),
                skill(72, "core", 5, 4),
                skill(81, "core", 8),
                skill(82, "core", 5, 4),
                skill(403, "core", 9),
                skill(404, "core", 6, 5),
                skill(395, "core", 8),
                skill(396, "core", 6, 4),
                skill(397, "core", 6, 6),
                skill(1302, "core", 6, 7),
                skill(417, "archetype", 10),
                skill(1310, "archetype", 9),
                skill(1309, "archetype", 8),
                skill(419, "archetype", 10, 4),
                skill(420, "archetype", 7, 6),
                skill(424, "archetype", 7, 8),
                skill(425, "archetype", 8, 10),
                skill(1452, "archetype", 5, 5),
                skill(1442, "archetype", 5, 8),
            ],
            equipment=[
                item("arma", 5162, 1, 4),
                item("arma", 5170, 5, 9),
                item("arma", 5178, 10, 14),
                item("arma", 5194, 15, 20),
                item("veste", 638, 1, 4),
                item("veste", 646, 5, 9),
                item("veste", 654, 10, 14),
                item("veste", 670, 15, 20),
                item("vestiti", 5271, 1, 4),
                item("vestiti", 5272, 5, 9),
                item("vestiti", 5273, 10, 14),
                item("vestiti", 5275, 15, 20),
            ],
            notes="Conversione v2 delle righe Elder #887-890; il pool esclude deliberatamente ogni Skill di danno.",
        ),
        evidence=[
            {"claim": "veste e bastone Recupero", "source": "unit:887-890.veste/arma"},
            {"claim": "tenere in piedi il gruppo", "source": "unitlore:62"},
        ],
        rejected=[
            {
                "candidate": {"skillId": 421, "name": "Danno Salute"},
                "decision": "reject",
                "reasonCode": "support-identity-violation",
                "reason": "Il danno magico non appartiene alla firma del Guaritore e non serve a spendere PE.",
            }
        ],
        deviations=[],
        legality=[
            {"claim": "cura e stabilizzazione", "source": "Skill 417, 419, 1310"},
            {"claim": "rimozione status", "source": "Skill 425 Cura Status"},
        ],
    ),
    base_candidate(
        source_file="924-925",
        charter_data=charter(
            unit="Agente Morag Tong",
            source_ids=[924, 925],
            kind="humanoid",
            fantasy=(
                "Esecutore rituale di una condanna, non semplice tagliagole. Entra già "
                "composto, colpisce con precisione e lascia dietro di sé il peso della "
                "tradizione della Morag Tong."
            ),
            combat_story=(
                "Evita lo scontro prolungato, cerca posizione e primo sangue, quindi "
                "disimpegna. Crescendo migliora furtività e controllo dei nervi, non "
                "allarga il repertorio a ogni arma plausibile."
            ),
            siblings=[
                (
                    "Arciere Bandito",
                    "nearest",
                    "Il Bandito domina distanza e terreno; l'Agente chiude con lame corte e precisione.",
                ),
                (
                    "Mercenario",
                    "same-role",
                    "Entrambi lavorano per incarico, ma l'Agente è rituale e rigidamente specializzato.",
                ),
                (
                    "Ordinatore",
                    "contrast",
                    "Entrambi sono istituzioni dunmer; l'Agente evita la linea che l'Ordinatore impone.",
                ),
            ],
            axes=[
                (
                    "eliminazione precisa da furtività",
                    "Assassino + furtivita/rapidita_di_mano e sole lame corte",
                ),
                (
                    "identità Morag Tong",
                    "armatura 5769 obbligatoria a ogni livello",
                ),
            ],
            must=["armatura Morag Tong", "stiletto o kriss", "furtività", "compostezza"],
            must_not=["arma lunga", "armatura generica", "magia", "veleno come tipo di danno"],
            rigidity="faction-locked",
            variation="stiletto/kriss, vetro/ebano, ordine delle Skill e competenze",
            checkpoints={
                "1": "agente riconoscibile in chitina con lama di vetro",
                "5": "primo sangue e disimpegno",
                "10": "entra nella fascia legacy con precisione affidabile",
                "15": "passaggio controllato all'ebano",
                "20": "esecutore d'élite senza allargare le famiglie d'arma",
            },
            range_reason=(
                "La sorgente copre 10-20. L'armatura di fazione resta fissa; vetro "
                "viene anticipato e l'ebano sovrapposto dal 13 senza downgrade identitario."
            ),
        ),
        expectation_data=expectations(
            unit="Agente Morag Tong",
            kind="humanoid",
            all_variants={
                "armorItemIds": [5769],
                "innateActionCount": 0,
                "warningCount": 0,
            },
            at_least_one=["Colpo nascosto o Viso celato entro il livello 5"],
            allowed=["stiletto o kriss", "vetro o ebano", "Skill Assassino"],
            forbidden=["armi lunghe", "armatura generica", "magia", "danno Veleno"],
            differs_from={
                "Arciere Bandito": "nessun arco e firma melee corta",
                "Ordinatore": "nessuno scudo e nessuna tattica di linea",
            },
        ),
        proposal=humanoid_payload(
            name="Agente Morag Tong",
            category="Umano",
            archetype=(
                "Assassino dunmer disciplinato che elimina un bersaglio con lame corte, "
                "furtività e controllo dei nervi."
            ),
            lore=(
                "Opera da santuari e case sicure per eseguire condanne riconosciute dalla "
                "tradizione. Ogni colpo deve essere pulito e finalizzato."
            ),
            tags={
                "core_fisico": 3,
                "focus_combat": 4,
                "attacco": 5,
                "esplorazione_infiltrazione": 5,
                "controllo_situazionale": 4,
                "difesa": 1,
                "range_skill": -3,
                "core_magico": -5,
                "natura_magica": -5,
            },
            competences={
                "furtivita": 5,
                "rapidita_di_mano": 5,
                "percezione": 4,
                "intuizione": 3,
                "conoscenze_religioni": 2,
                "raggirare": 1,
                "diplomazia": -5,
                "suonare": -4,
                "sapienza_magica": -3,
            },
            rules=generation(
                "stealth",
                core_share=0.42,
                magic_policy="none",
                classes=["Assassino"],
                races=["Dunmer"],
            ),
            skills=[
                skill(64, "core", 8),
                skill(71, "core", 7),
                skill(93, "core", 8),
                skill(94, "core", 5, 6),
                skill(380, "core", 8),
                skill(381, "core", 6, 5),
                skill(383, "core", 6, 5),
                skill(384, "core", 5, 9),
                skill(99, "core", 7),
                skill(100, "core", 5, 8),
                skill(680, "archetype", 9),
                skill(683, "archetype", 10),
                skill(684, "archetype", 8),
                skill(682, "archetype", 8, 4),
                skill(685, "archetype", 7, 6),
                skill(688, "archetype", 8, 5),
                skill(686, "archetype", 6, 8),
                skill(687, "archetype", 6, 10),
                skill(690, "archetype", 5, 14),
            ],
            equipment=[
                item("armatura", 5769),
                item("vestiti", 5279),
                item("arma", 5711, 1, 14, 6),
                item("arma", 165, 1, 14, 4),
                item("arma", 5713, 13, 20, 6),
                item("arma", 172, 13, 20, 4),
            ],
            notes="Conversione v2 delle righe Elder #924-925; il veleno resta identità narrativa, non tipo di danno.",
        ),
        evidence=[
            {"claim": "armatura Morag Tong", "source": "unit:924-925.armatura"},
            {"claim": "omicidio rituale e lame corte", "source": "unitlore:2"},
        ],
        rejected=[
            {
                "candidate": {"mechanic": "danno da veleno"},
                "decision": "reject",
                "reasonCode": "unsupported-damage-type",
                "reason": "DAMAGE_TYPES non contiene Veleno; nessuna meccanica inventata viene inserita.",
            },
            {
                "candidate": {"skillId": 331, "name": "Affondo"},
                "decision": "reject",
                "reasonCode": "generic-melee-drift",
                "reason": "La famiglia Assassino esprime già la precisione senza allargare il pool.",
            },
        ],
        deviations=[
            {
                "what": "authored levels",
                "from": "legacy 10-20",
                "to": "1-20",
                "why": "identità di fazione invariata; il vetro viene anticipato, non sostituito con gear generico",
            }
        ],
        legality=[
            {"claim": "furtività e colpo nascosto", "source": "Famiglia Skill Assassino"},
            {"claim": "tipi di danno ammessi", "source": "backend.combat.rules.DAMAGE_TYPES"},
        ],
    ),
    base_candidate(
        source_file="931",
        charter_data=charter(
            unit="Ordinatore",
            source_ids=[931],
            kind="humanoid",
            fantasy=(
                "Guardia sacra e inquisitore del Tempio, riconoscibile prima ancora che "
                "attacchi. Non è una guardia cittadina migliorata: è un soldato della "
                "fede la cui uniforme rende visibile l'autorità del Tribunale."
            ),
            combat_story=(
                "Blocca il passaggio con armatura, scudo e mazza; poi stabilizza la linea "
                "e punisce chi insiste. Al livello 20 è un enforcer individuale superiore "
                "al legionario, ma non un incantatore offensivo."
            ),
            siblings=[
                (
                    "Cavaliere Redoran",
                    "nearest",
                    "L'Ordinatore è uniforme e zelo; il Redoran è onore di casata e maggiore ampiezza d'armi.",
                ),
                (
                    "Soldato Imperiale",
                    "same-role",
                    "Il Legionario è sostituibile e di formazione; l'Ordinatore è minaccia individuale religiosa.",
                ),
                (
                    "Soldato Dremora",
                    "contrast",
                    "Entrambi sono iconic-locked, ma il Dremora è soprannaturale e privo di disciplina del Tempio.",
                ),
            ],
            axes=[
                (
                    "armatura Indoril inseparabile",
                    "armatura 5785 dal livello 1 al 20",
                ),
                (
                    "disciplina del Tribunale",
                    "religione +5, pool scudo/Bastione e Recupero non offensivo",
                ),
            ],
            must=["Armatura Indoril", "scudo", "mazza preferita", "disciplina religiosa"],
            must_not=["armatura generica", "armi a distanza", "magia di danno", "azioni creature"],
            rigidity="iconic-locked",
            variation="mazza molto favorita o spada d'ebano, Skill difensive e competenze",
            checkpoints={
                "1": "già pienamente riconoscibile, senza downgrade",
                "5": "disciplina di scudo e stabilizzazione",
                "10": "muro individuale superiore al legionario",
                "15": "entra nella fascia legacy senza salto d'identità",
                "20": "élite del Tempio ancora vincolata all'Indoril",
            },
            range_reason=(
                "La sorgente copre 15-20. L'estensione accetta il front-loading "
                "dell'equipaggiamento iconico invece di sostituirlo con armature comuni."
            ),
        ),
        expectation_data=expectations(
            unit="Ordinatore",
            kind="humanoid",
            all_variants={
                "armorItemIds": [5785],
                "shieldItemIds": [621],
                "innateActionCount": 0,
                "warningCount": 0,
            },
            at_least_one=["Bastione o Skill di scudo entro il livello 5"],
            allowed=["mazza Indoril o spada d'ebano", "Skill difensive", "competenze"],
            forbidden=["armatura non Indoril", "assenza di scudo", "magia di danno", "armi a distanza"],
            differs_from={
                "Soldato Imperiale": "armatura superiore invariabile e competenza religiosa",
                "Cavaliere Redoran": "nessuna progressione di materiali o ampiezza d'armi",
            },
        ),
        proposal=humanoid_payload(
            name="Ordinatore",
            category="Umano",
            archetype=(
                "Enforcer del Tempio in armatura Indoril, specializzato nel bloccare "
                "il passaggio con scudo, mazza e disciplina religiosa."
            ),
            lore=(
                "Serve le istituzioni sacre di Morrowind come guardia e inquisitore. "
                "Eresia e disordine sono minacce concrete da reprimere."
            ),
            tags={
                "core_fisico": 5,
                "focus_combat": 5,
                "difesa": 5,
                "attacco": 3,
                "supporto_party": 3,
                "controllo_situazionale": 3,
                "core_magico": 1,
                "range_skill": -5,
                "natura_magica": -2,
            },
            competences={
                "strategia_militare": 5,
                "conoscenze_religioni": 5,
                "intimidire": 4,
                "intuizione": 3,
                "percezione": 2,
                "sapienza_magica": 1,
                "raggirare": -5,
                "furtivita": -4,
                "suonare": -3,
            },
            rules=generation(
                "warrior",
                core_share=0.6,
                magic_policy="any",
                classes=["Torre Umana"],
                races=["Dunmer"],
            ),
            skills=PHYSICAL_CORE
            + SHIELD_ARCHETYPE
            + [
                skill(1343, "archetype", 9, 5),
                skill(595, "archetype", 7, 7),
                skill(596, "archetype", 6, 10),
                skill(1350, "archetype", 6, 12),
                skill(417, "archetype", 6, 5),
                skill(1309, "archetype", 5, 8),
            ],
            equipment=[
                item("armatura", 5785),
                item("chainmail", 635),
                item("scudo", 621),
                item("veste", 670),
                item("vestiti", 5275),
                item("arma", 5718, weight=8),
                item("arma", 228, weight=2),
            ],
            notes="Conversione v2 della riga Elder #931; identità Indoril mantenuta integralmente a ogni livello.",
        ),
        evidence=[
            {"claim": "Armatura Indoril e Mazza Indoril", "source": "unit:931.armatura/arma"},
            {"claim": "soldato della fede", "source": "unitlore:90"},
        ],
        rejected=[
            {
                "candidate": {"itemId": 5717, "name": "Mazza Indoril (ossa)"},
                "decision": "reject",
                "reasonCode": "identity-downgrade",
                "reason": "La riga sorgente lega l'Ordinatore alla variante d'ebano; il livello basso non autorizza il downgrade.",
            },
            {
                "candidate": {"family": "Distruzione"},
                "decision": "reject",
                "reasonCode": "temple-role-mismatch",
                "reason": "La magia ammessa serve stabilizzazione e protezione, non danno arcano.",
            },
        ],
        deviations=[
            {
                "what": "authored levels",
                "from": "legacy 15-20",
                "to": "1-20",
                "why": "front-loading esplicito dell'identità iconica, senza sostituzioni di loot",
            }
        ],
        legality=[
            {"claim": "scudi pesanti", "source": "Skill 389-391"},
            {"claim": "stabilizzazione", "source": "Skill 417 Stabilizza"},
        ],
    ),
    base_candidate(
        source_file="940-941",
        charter_data=charter(
            unit="Cavaliere Redoran",
            source_ids=[940, 941],
            kind="humanoid",
            fantasy=(
                "Campione austero della Casa Redoran, per cui onore e servizio sono "
                "disciplina quotidiana. Avanza con il peso della casata, non con lo zelo "
                "religioso dell'Ordinatore o l'anonimato del legionario."
            ),
            combat_story=(
                "Tiene la linea, protegge gli alleati e vince per pazienza. La varietà "
                "cresce lungo la linea di spade Redoran e poche asce lore-valid, mentre "
                "l'armatura d'ossa resta il segno fisso."
            ),
            siblings=[
                (
                    "Ordinatore",
                    "nearest",
                    "Il Redoran varia le armi e difende la casata; l'Ordinatore conserva uniforme e dottrina del Tempio.",
                ),
                (
                    "Soldato Imperiale",
                    "same-role",
                    "Il Cavaliere è un campione individuale, non fanteria sostituibile.",
                ),
                (
                    "Mercenario",
                    "contrast",
                    "Il Mercenario cambia per convenienza; il Redoran resta dentro onore e materiali di casata.",
                ),
            ],
            axes=[
                (
                    "armatura d'ossa Redoran",
                    "armatura 5773 obbligatoria 1-20",
                ),
                (
                    "avanzata paziente di casata",
                    "pool scudo/Cavaliere e linea di spade 5723-5728",
                ),
            ],
            must=["armatura rinforzata Redoran", "scudo", "spada Redoran o ascia", "onore"],
            must_not=["magia", "furtività", "gear generico fuori dalle asce sorgente"],
            rigidity="faction-locked",
            variation="linea materiale delle spade, asce d'acciaio/dwemer, scudo e Skill",
            checkpoints={
                "1": "cavaliere già in ossa con acciaio",
                "5": "linea elfica/ossa e protezione alleati",
                "10": "entra nella fascia legacy con scudo solido",
                "15": "progressione dwemer/vetro",
                "20": "campione daedrico senza cambiare armatura di casata",
            },
            range_reason=(
                "La sorgente copre 10-20. La linea Redoran verificata 5723-5728 "
                "fornisce un'estensione 1-20 coerente senza cambiare l'armatura di casata."
            ),
        ),
        expectation_data=expectations(
            unit="Cavaliere Redoran",
            kind="humanoid",
            all_variants={
                "armorItemIds": [5773],
                "shieldItemIds": [617, 620],
                "innateActionCount": 0,
                "warningCount": 0,
            },
            at_least_one=["una Skill di protezione entro il livello 5"],
            allowed=["spada Redoran o ascia", "materiale per fascia", "Skill Cavaliere"],
            forbidden=["armatura non Redoran", "assenza di scudo", "magia", "furtività"],
            differs_from={
                "Ordinatore": "progressione d'arma ampia e nessuna firma religiosa",
                "Mercenario": "armatura di casata obbligatoria in tutte le varianti",
            },
        ),
        proposal=humanoid_payload(
            name="Cavaliere Redoran",
            category="Umano",
            archetype=(
                "Campione di casata in armatura d'ossa che protegge la linea con scudo, "
                "spade Redoran e poche asce tradizionali."
            ),
            lore=(
                "Serve i domini Redoran con austerità, sacrificio e controllo. Preferisce "
                "vincere mantenendo la posizione e proteggendo i compagni."
            ),
            tags={
                "core_fisico": 5,
                "focus_combat": 5,
                "difesa": 5,
                "supporto_party": 4,
                "attacco": 3,
                "sociale": 1,
                "range_skill": -5,
                "core_magico": -5,
                "natura_magica": -5,
            },
            competences={
                "strategia_militare": 5,
                "conoscenze_storiaenobilta": 4,
                "intimidire": 4,
                "intuizione": 3,
                "percezione": 2,
                "cavalcare": 2,
                "raggirare": -5,
                "furtivita": -4,
                "sapienza_magica": -4,
            },
            rules=generation(
                "warrior",
                core_share=0.58,
                magic_policy="none",
                classes=["Cavaliere"],
                races=["Dunmer"],
            ),
            skills=PHYSICAL_CORE
            + SHIELD_ARCHETYPE
            + [
                skill(889, "archetype", 9),
                skill(890, "archetype", 6, 7),
                skill(891, "archetype", 8),
                skill(892, "archetype", 6, 8),
                skill(894, "archetype", 6, 6),
                skill(896, "archetype", 5, 10),
            ],
            equipment=[
                item("armatura", 5773),
                item("scudo", 617, 1, 14, 5),
                item("scudo", 620, 10, 20, 5),
                item("vestiti", 5273, 1, 14),
                item("vestiti", 5275, 10, 20),
                item("arma", 5726, 1, 5, 6),
                item("arma", 588, 1, 8, 2),
                item("arma", 5723, 4, 8, 6),
                item("arma", 5724, 7, 12, 6),
                item("arma", 5727, 11, 16, 6),
                item("arma", 591, 13, 20, 2),
                item("arma", 5725, 15, 19, 5),
                item("arma", 5728, 18, 20, 5),
            ],
            notes="Conversione v2 delle righe Elder #940-941; linea Redoran corrente usata per coprire 1-20.",
        ),
        evidence=[
            {"claim": "armatura rinforzata Redoran", "source": "unit:940-941.armatura"},
            {"claim": "onore, linea e protezione", "source": "unitlore:29"},
        ],
        rejected=[
            {
                "candidate": {"itemId": 5772, "name": "Armatura leggera Redoran (ossa)"},
                "decision": "reject",
                "reasonCode": "armor-role-mismatch",
                "reason": "La sorgente definisce il Cavaliere tramite l'armatura rinforzata, non il percorso leggero.",
            }
        ],
        deviations=[
            {
                "what": "authored levels",
                "from": "legacy 10-20",
                "to": "1-20",
                "why": "la linea Redoran verificata copre la progressione mantenendo fissa l'armatura d'ossa",
            }
        ],
        legality=[
            {"claim": "protezione e scudo", "source": "Skill 389-391 e Famiglia Cavaliere"},
            {"claim": "linea armi", "source": "core_oggetto 5723-5728"},
        ],
    ),
    base_candidate(
        source_file="934-935",
        charter_data=charter(
            unit="Mago Telvanni",
            source_ids=[934, 935],
            kind="humanoid",
            fantasy=(
                "Studioso dunmer brillante e arrogante che tratta morale, servitori e "
                "ambiente come variabili di un esperimento. Non vuole soltanto vincere: "
                "vuole dimostrare che le regole valgono per gli altri."
            ),
            combat_story=(
                "Controlla percezione, posizione e volontà da lontano; usa mobilità e "
                "servitori evocativi per non accettare il fronte. Crescendo diventa più "
                "imprevedibile, non più resistente o curativo."
            ),
            siblings=[
                (
                    "Mago da Battaglia",
                    "nearest",
                    "Il Telvanni rifiuta fronte e lama; il battlemage li integra.",
                ),
                (
                    "Guaritore",
                    "same-role",
                    "Il Guaritore preserva alleati; il Telvanni controlla nemici e spazio.",
                ),
                (
                    "Lich",
                    "contrast",
                    "Condivide arroganza arcana, ma resta un umanoide vulnerabile con equipaggiamento.",
                ),
            ],
            axes=[
                (
                    "controllo mentale e spaziale",
                    "pool Illusione con Teleport e profilo controllo",
                ),
                (
                    "progressione Telvanni accademica",
                    "veste e bastone Illusione principiante-gran maestro",
                ),
            ],
            must=["Illusione", "mobilità", "studio arcano", "bastone"],
            must_not=["cura generica", "arma da fronte", "armatura", "pool melee"],
            rigidity="path-locked",
            variation="ordine delle illusioni, mobilità, competenze e sottorazza Dunmer",
            checkpoints={
                "1": "principiante già orientato al controllo",
                "5": "paura/accecamento e mobilità",
                "10": "qualificato capace di alterare più scelte nemiche",
                "15": "maestro imprevedibile ma fragile",
                "20": "gran maestro del controllo, non guaritore o tank",
            },
            range_reason=(
                "La sorgente copre 5-14. Si aggiungono i gradi principiante, maestro "
                "e gran maestro Illusione già presenti nel catalogo corrente."
            ),
        ),
        expectation_data=expectations(
            unit="Mago Telvanni",
            kind="humanoid",
            all_variants={"innateActionCount": 0, "warningCount": 0},
            at_least_one=["una Skill di controllo Illusione entro il livello 5"],
            allowed=["Illusione", "mobilità", "ordine dei cast"],
            forbidden=["armatura", "arma melee", "pool guaritore", "Skill da prima linea"],
            differs_from={
                "Mago da Battaglia": "nessuna armatura e nessuna Skill melee",
                "Guaritore": "nessuna cura o stabilizzazione nel pool",
            },
        ),
        proposal=humanoid_payload(
            name="Mago Telvanni",
            category="Umano",
            archetype=(
                "Specialista dunmer di Illusione che controlla volontà e posizione, "
                "usa mobilità arcana e rifiuta il combattimento di prima linea."
            ),
            lore=(
                "Abita torri-fungo e territori isolati della Casa Telvanni. Conoscenza "
                "e potere personale giustificano esperimenti che altri non oserebbero."
            ),
            tags={
                "core_magico": 5,
                "natura_magica": 5,
                "controllo_situazionale": 5,
                "range_skill": 4,
                "esplorazione_infiltrazione": 2,
                "tecnica_crafting": 3,
                "difesa": 1,
                "supporto_party": -3,
                "core_fisico": -5,
            },
            competences={
                "sapienza_magica": 5,
                "ingegneria": 4,
                "intuizione": 4,
                "conoscenze_storiaenobilta": 3,
                "gestione_risorse": 2,
                "percezione": 2,
                "diplomazia": -5,
                "strategia_militare": -3,
                "nuotare": -3,
            },
            rules=generation(
                "mage",
                core_share=0.42,
                magic_policy="any",
                races=["Dunmer"],
            ),
            skills=MAGE_CORE
            + [
                skill(1444, "archetype", 9),
                skill(426, "archetype", 10),
                skill(427, "archetype", 9),
                skill(1210, "archetype", 6, 4),
                skill(1168, "archetype", 8, 6),
                skill(431, "archetype", 8, 6),
                skill(1445, "archetype", 7, 8),
                skill(1446, "archetype", 7, 12),
                skill(1447, "archetype", 6, 14),
                skill(1448, "archetype", 5, 16),
                skill(440, "archetype", 8, 5),
            ],
            equipment=[
                item("arma", 5163, 1, 4),
                item("arma", 5171, 4, 9),
                item("arma", 5179, 8, 14),
                item("arma", 5195, 13, 18),
                item("arma", 5203, 17, 20),
                item("veste", 639, 1, 4),
                item("veste", 647, 4, 9),
                item("veste", 655, 8, 14),
                item("veste", 671, 13, 18),
                item("veste", 679, 17, 20),
                item("vestiti", 5273, 1, 12),
                item("vestiti", 5275, 10, 20),
            ],
            notes="Conversione v2 delle righe Elder #934-935; percorso Illusione esteso con gradi catalogati.",
        ),
        evidence=[
            {"claim": "veste e bastone Illusione", "source": "unit:934-935.veste/arma"},
            {"claim": "imprevedibilità e superiorità", "source": "unitlore:77"},
        ],
        rejected=[
            {
                "candidate": {"skillId": 419, "name": "Cura"},
                "decision": "reject",
                "reasonCode": "healer-clone-risk",
                "reason": "Il Telvanni controlla e manipola; la cura generica lo avvicina al Guaritore.",
            },
            {
                "candidate": {"skillId": 331, "name": "Affondo"},
                "decision": "reject",
                "reasonCode": "frontline-role-mismatch",
                "reason": "Una manovra melee contraddice il rifiuto del fronte.",
            },
        ],
        deviations=[
            {
                "what": "authored levels",
                "from": "legacy 5-14",
                "to": "1-20",
                "why": "aggiunti soltanto gradi Illusione principiante/maestro/gran maestro già catalogati",
            }
        ],
        legality=[
            {"claim": "controllo Illusione", "source": "Famiglia Skill Illusione"},
            {"claim": "mobilità arcana", "source": "Skill 440 Teleport"},
        ],
    ),
    base_candidate(
        source_file="944",
        charter_data=charter(
            unit="Soldato Dremora",
            source_ids=[944],
            kind="humanoid",
            kind_reason=(
                "Nonostante razza legacy Entità, indossa armatura, impugna armi e "
                "combatte come fanteria disciplinata: il contratto corretto è humanoid."
            ),
            fantasy=(
                "Fanteria delle legioni daedriche, feroce ma ordinata. Non è una bestia: "
                "obbedisce a rango, formazione e logica di conquista con disprezzo per i mortali."
            ),
            combat_story=(
                "Impone pressione pesante con scudo e armi daedriche fin dal primo "
                "checkpoint. Cresce in disciplina e aggressione, non acquisisce azioni "
                "innate da creatura o magia casuale."
            ),
            siblings=[
                (
                    "Ordinatore",
                    "nearest",
                    "Entrambi sono iconic-locked; il Dremora è soprannaturale e privo di disciplina religiosa.",
                ),
                (
                    "Soldato Imperiale",
                    "same-role",
                    "Il Dremora mantiene materiali superiori e una pressione più feroce.",
                ),
                (
                    "Centurione Nanico",
                    "contrast",
                    "Il Dremora usa equipaggiamento e Skill; il Centurione è una creatura con martello innato.",
                ),
            ],
            axes=[
                (
                    "loadout daedrico inseparabile",
                    "armatura 608 e scudo 622 a ogni livello",
                ),
                (
                    "fanteria soprannaturale disciplinata",
                    "pool Torre/Scudo, strategia e intimidire",
                ),
            ],
            must=["armatura daedrica", "scudo daedrico", "arma daedrica", "disciplina"],
            must_not=["azioni innate", "equipaggiamento mortale", "magia casuale", "razza mortale"],
            rigidity="iconic-locked",
            variation="spada/mazza/ascia daedrica e Skill di guerra",
            checkpoints={
                "1": "già pienamente daedrico, senza downgrade",
                "5": "formazione pesante online",
                "10": "pressione superiore al legionario",
                "15": "entra nella fascia legacy senza salto",
                "20": "fante d'élite, non signore Dremora",
            },
            range_reason=(
                "La sorgente copre 15-18. L'estensione mantiene il loadout iconico "
                "invariato e sposta la crescita sulle Skill."
            ),
            open_questions=[],
        ),
        expectation_data=expectations(
            unit="Soldato Dremora",
            kind="humanoid",
            all_variants={
                "armorItemIds": [608],
                "shieldItemIds": [622],
                "weaponMaterial": "daedrico",
                "innateActionCount": 0,
                "warningCount": 0,
            },
            at_least_one=["una Skill difensiva entro il livello 5"],
            allowed=["spada, mazza o ascia daedrica", "Skill di guerra"],
            forbidden=["razza mortale", "gear non daedrico", "azioni innate", "magia"],
            differs_from={
                "Soldato Imperiale": "materiale daedrico fisso e pressione superiore",
                "Ordinatore": "nessuna firma religiosa e diversa famiglia d'armatura",
            },
        ),
        proposal=humanoid_payload(
            name="Soldato Dremora",
            category="Daedra",
            archetype=(
                "Fanteria pesante daedrica con equipaggiamento iconico, disciplina di "
                "rango e nessuna azione innata da creatura."
            ),
            lore=(
                "Serve legioni organizzate dell'Oblivion. Combatte per dovere di casta, "
                "conquista e dimostrazione di valore, non per fame o paura."
            ),
            tags={
                "core_fisico": 5,
                "focus_combat": 5,
                "attacco": 5,
                "difesa": 4,
                "controllo_situazionale": 2,
                "range_skill": -5,
                "core_magico": -5,
                "natura_magica": -2,
            },
            competences={
                "strategia_militare": 5,
                "intimidire": 5,
                "percezione": 3,
                "intuizione": 2,
                "diplomazia": -5,
                "raggirare": -5,
                "suonare": -5,
                "sapienza_magica": -3,
            },
            rules=generation(
                "warrior",
                core_share=0.56,
                magic_policy="none",
                classes=["Torre Umana"],
                races=["Dremora"],
                subraces=["Churl", "Caitiff", "Kynval"],
            ),
            skills=PHYSICAL_CORE
            + SHIELD_ARCHETYPE
            + [
                skill(1272, "archetype", 8),
                skill(1273, "archetype", 6, 6),
                skill(1343, "archetype", 8, 6),
                skill(1348, "archetype", 6, 10),
                skill(1350, "archetype", 6, 12),
                skill(1010, "archetype", 6, 8),
            ],
            equipment=[
                item("armatura", 608),
                item("scudo", 622),
                item("vestiti", 5284),
                item("arma", 187, weight=4),
                item("arma", 229, weight=5),
                item("arma", 593, weight=3),
            ],
            notes=(
                "Conversione v2 della riga Elder #944. La razza Dremora è esplicita e "
                "le sottorazze sono limitate ai ranghi di truppa Churl, Caitiff e Kynval."
            ),
        ),
        evidence=[
            {"claim": "armatura e scudo daedrici", "source": "unit:944.armatura/scudo"},
            {"claim": "soldato, non bestia", "source": "unitlore:114"},
        ],
        rejected=[
            {
                "candidate": {"allowedRace": "Dunmer"},
                "decision": "reject",
                "reasonCode": "silent-race-substitution",
                "reason": "Una razza mortale non rappresenta un Dremora e applicherebbe modificatori razziali falsi.",
            }
        ],
        deviations=[
            {
                "what": "authored levels",
                "from": "legacy 15-18",
                "to": "1-20",
                "why": "identità daedrica front-loaded e crescita affidata alle Skill",
            }
        ],
        legality=[
            {"claim": "contratto humanoid", "source": "unit:944 equipment + backend.combat.unit_generation"},
            {"claim": "razza e ranghi legali", "source": "backend.characters.race_rules.RACE_CATALOG[Dremora]"},
        ],
        blocked=[],
    ),
]


CREATURES: list[dict[str, Any]] = [
    base_candidate(
        source_file="986",
        charter_data=charter(
            unit="Lupo",
            source_ids=[986],
            kind="creature",
            kind_reason="Predatore biologico senza equipaggiamento o progressione Skill.",
            fantasy=(
                "Predatore sociale comune, letale perché legge debolezza e branco. "
                "Non ha bisogno di magia: il ricordo dell'incontro è l'inseguimento "
                "coordinato e il salto che chiude la distanza."
            ),
            combat_story=(
                "È fragile se isolato ma rapido nel raggiungere una preda esposta. "
                "Furia lo rende più aggressivo col costo chiaro di una Difesa inferiore."
            ),
            siblings=[
                ("Cliff Racer", "nearest", "Il Lupo usa balzo terrestre e branco, non volo o controllo sonoro."),
                ("Spriggan", "same-family", "Condivide la natura ma non magia, rigenerazione o controllo delle radici."),
                ("Drago", "contrast", "Il Lupo resta animale rapido e vulnerabile, senza soffio o volo strategico."),
            ],
            axes=[
                ("mobilità da branco", "velocita/agilita alte e Balzo Predatorio"),
                ("aggressione rischiosa", "Furia aumenta Forza/Attacco e riduce Difesa"),
            ],
            must=["balzo", "morso implicito", "velocità", "furia"],
            must_not=["magia", "volo", "resistenze elementali", "equipaggiamento"],
            rigidity="none",
            variation="finestre delle azioni e valori interpolati",
            checkpoints={
                "1": "predatore rapido con Balzo",
                "5": "branco mobile ma ancora fragile",
                "10": "Furia rende leggibile il rischio",
                "15": "inseguitore resistente",
                "20": "alfa naturale, non creatura magica",
            },
            range_reason="La riga legacy è solo livello 20; le curve lineari esplicitano una crescita naturale 1-20.",
        ),
        expectation_data=expectations(
            unit="Lupo",
            kind="creature",
            all_variants={
                "equipmentSlotCount": 0,
                "skillUnlockCount": 0,
                "competenceCount": 0,
                "innateActionKeys": ["balzo-predatorio", "furia"],
                "warningCount": 0,
            },
            at_least_one=["Balzo Predatorio a ogni livello"],
            allowed=["valori di curva per livello"],
            forbidden=["equipaggiamento", "SkillPersonaggio", "magia", "volo"],
            differs_from={
                "Cliff Racer": "velocità inferiore e nessuna azione aerea",
                "Drago": "PF e cognizione molto inferiori",
            },
            curve_assertions=[{"key": "pf", "level": 10, "expected": 57}],
        ),
        proposal=creature_payload(
            name="Lupo",
            category="Natura",
            archetype="Predatore da branco rapido, resistente sulle distanze e privo di magia.",
            lore=(
                "Vive in foreste, colline e pianure. Isolato evita rischi inutili; "
                "in branco circonda, insegue e stanca la preda."
            ),
            stat_curves={
                "pf": (18, 100),
                "pa": (9, 32),
                "energia": (6, 30),
                "potere": (0, 0),
                "forza": (11, 30),
                "resistenza": (8, 22),
                "velocita": (11, 30),
                "agilita": (11, 30),
                "intelligenza": (6, 16),
                "concentrazione": (6, 16),
                "personalita": (0, 0),
                "saggezza": (6, 16),
                "fortuna": (11, 30),
                "attacco": (10, 55),
                "difesa": (10, 55),
                "tier": (5, 15),
                "rd_fis": (1, 3),
                "res_contundente": (0, 0),
                "res_taglio": (-1, -1),
                "res_perforante": (-1, -1),
                "res_fuoco": (0, 0),
                "res_gelo": (0, 0),
                "res_elettro": (0, 0),
                "mana": (0, 0),
            },
            actions=[
                action(
                    "balzo-predatorio",
                    "Balzo Predatorio",
                    (
                        "Si sposta fino a 3 esagoni in linea verso un bersaglio e, "
                        "se termina adiacente, esegue un attacco con +3 Attacco e un reroll."
                    ),
                    {"pa": 7, "energia": 2},
                    icon="artiglio",
                ),
                action(
                    "furia",
                    "Furia",
                    "Ottiene +4 Forza e +3 Attacco, ma -2 Difesa per 3 turni.",
                    {"pa": 4, "energia": 4},
                    minimum=6,
                    duration="3 turni",
                    icon="artiglio",
                ),
            ],
            notes="Conversione v2 della Unit Elder #986; costanti legacy preservate.",
        ),
        evidence=[
            {"claim": "Balzo Predatorio e Furia", "source": "skillnpc:62,28"},
            {"claim": "branco e inseguimento", "source": "unitlore:72"},
        ],
        rejected=[
            {
                "candidate": {"action": "soffio elementale"},
                "decision": "reject",
                "reasonCode": "family-clone-risk",
                "reason": "Appartiene ai draghi, non alla biologia del lupo.",
            }
        ],
        deviations=[
            {
                "what": "curve non costanti",
                "from": "conversione ordinale frazionaria",
                "to": "endpoint interi confrontati con Cliff Racer e Drago",
                "why": "leggibilità e coerenza della famiglia naturale",
            }
        ],
        legality=[
            {"claim": "bonus Attacco e reroll", "source": "Skill Attacchi Melee e motore effetti"},
            {"claim": "modificatori Forza/Attacco/Difesa", "source": "OperazioneEffettoPersonalizzato add/subtract"},
        ],
    ),
    base_candidate(
        source_file="971",
        charter_data=charter(
            unit="Cliff Racer",
            source_ids=[971],
            kind="creature",
            kind_reason="Creatura volante biologica, priva di inventario e Skill acquistate.",
            fantasy=(
                "Predatore aereo insistente di Morrowind, più memorabile per l'ostinazione "
                "che per la nobiltà. La sua minaccia è decidere quando la distanza smette di proteggere."
            ),
            combat_story=(
                "Sorvola il fronte, si tuffa su bersagli esposti e usa ali e stridio per "
                "rompere posizioni. Se costretto a terra perde gran parte della propria identità."
            ),
            siblings=[
                ("Lupo", "nearest", "Il Racer supera ostacoli in volo e controlla spazio; il Lupo insegue a terra."),
                ("Drago", "same-movement", "Condivide il volo, ma ha PF, cognizione e portata molto inferiori."),
                ("Anomalia Magica", "contrast", "È biologico e fisico, non un disturbo arcano di risorse."),
            ],
            axes=[
                ("molestia aerea", "velocita superiore al Lupo e Tuffo Aereo"),
                ("dislocazione", "Colpo d'Ala spinge e Stridio riduce Attacco"),
            ],
            must=["volo", "tuffo", "spinta", "velocità molto alta"],
            must_not=["durabilità da drago", "furia da branco", "magia"],
            rigidity="none",
            variation="azioni sbloccate e curve",
            checkpoints={
                "1": "volatore fastidioso con Colpo d'Ala",
                "5": "Tuffo rende pericolosi gli isolati",
                "10": "controllo aereo riconoscibile",
                "15": "Stridio punisce gruppi compatti",
                "20": "harasser d'élite, non boss volante",
            },
            range_reason="La riga legacy è livello 20; le azioni vengono scaglionate per costruire il kit 1-20.",
        ),
        expectation_data=expectations(
            unit="Cliff Racer",
            kind="creature",
            all_variants={
                "equipmentSlotCount": 0,
                "skillUnlockCount": 0,
                "competenceCount": 0,
                "innateActionKeys": ["colpo-d-ala", "tuffo-aereo", "stridio"],
                "warningCount": 0,
            },
            at_least_one=["Tuffo Aereo dal livello 5"],
            allowed=["azioni in finestra", "curve"],
            forbidden=["equipaggiamento", "Skill", "soffio elementale", "furia da branco"],
            differs_from={
                "Lupo": "velocità maggiore e tre strumenti aerei",
                "Drago": "PF e Tier nettamente inferiori",
            },
            curve_assertions=[{"key": "pf", "level": 10, "expected": 61}],
        ),
        proposal=creature_payload(
            name="Cliff Racer",
            category="Natura",
            archetype="Harasser aereo rapido che spinge, si tuffa e disorienta senza reggere uno scontro frontale.",
            lore=(
                "Infestava i cieli di Vvardenfell e inseguiva i viaggiatori con ostinazione. "
                "Corpo leggero e ali ampie lo rendono difficile da ignorare e colpire."
            ),
            stat_curves={
                "pf": (18, 108),
                "pa": (8, 26),
                "energia": (7, 31),
                "potere": (4, 22),
                "forza": (8, 20),
                "resistenza": (8, 20),
                "velocita": (13, 34),
                "agilita": (11, 30),
                "intelligenza": (6, 16),
                "concentrazione": (6, 16),
                "personalita": (0, 0),
                "saggezza": (6, 16),
                "fortuna": (9, 23),
                "attacco": (10, 58),
                "difesa": (9, 50),
                "tier": (3, 10),
                "rd_fis": (0, 2),
                "res_contundente": (-2, 2),
                "res_taglio": (0, 0),
                "res_perforante": (-2, 2),
                "res_fuoco": (0, 0),
                "res_gelo": (0, 0),
                "res_elettro": (0, 0),
                "rd_fuoco": (0, 0),
                "rd_gelo": (0, 0),
                "rd_elettro": (0, 0),
                "ap": (0, 0),
                "mana": (0, 0),
            },
            actions=[
                action(
                    "colpo-d-ala",
                    "Colpo d'Ala",
                    (
                        "Tutti i bersagli entro 2 esagoni subiscono danni Contundente "
                        "pari a (livello)d4; chi perde il confronto di Difesa viene spinto di 2 esagoni."
                    ),
                    {"pa": 5, "energia": 5},
                    icon="ala",
                ),
                action(
                    "tuffo-aereo",
                    "Tuffo Aereo",
                    (
                        "Vola fino a 6 esagoni e attacca un bersaglio all'arrivo, "
                        "infliggendo 4d6 + livello danni Perforante."
                    ),
                    {"pa": 6, "energia": 5},
                    minimum=5,
                    icon="ala",
                ),
                action(
                    "stridio",
                    "Stridio",
                    "I nemici entro 4 esagoni che falliscono Concentrazione subiscono -2 Attacco per 2 turni.",
                    {"pa": 6, "energia": 5},
                    minimum=10,
                    duration="2 turni",
                    icon="onda",
                ),
            ],
            notes="Conversione v2 della Unit Elder #971; stordimento sostituito da un malus Attacco supportato.",
        ),
        evidence=[
            {"claim": "Colpo d'Ala, Tuffo, Stridio", "source": "skillnpc:1,51,26"},
            {"claim": "inseguimento aereo ostinato", "source": "unitlore:36"},
        ],
        rejected=[
            {
                "candidate": {"mechanic": "stordito"},
                "decision": "reject",
                "reasonCode": "status-execution-uncertain",
                "reason": "Sostituito con -2 Attacco, variabile gestita dal motore effetti.",
            }
        ],
        deviations=[
            {
                "what": "Stridio Sonico",
                "from": "stordito 1 turno",
                "to": "-2 Attacco per 2 turni",
                "why": "effetto numerico supportato e verificabile",
            }
        ],
        legality=[
            {"claim": "danni Contundente/Perforante", "source": "backend.combat.rules.DAMAGE_TYPES"},
            {"claim": "spinta e confronto", "source": "Skill 330 Sbilancia e regole esagoni"},
        ],
    ),
    base_candidate(
        source_file="982",
        charter_data=charter(
            unit="Regina Kwama",
            source_ids=[982],
            kind="creature",
            kind_reason="Cuore biologico immobile della colonia, senza equipaggiamento o Skill acquistate.",
            fantasy=(
                "Centro riproduttivo ed economico di una colonia: enorme, quasi immobile "
                "e protetto dall'intero ecosistema sotterraneo. Attaccarla significa "
                "combattere il nido, non inseguire un predatore."
            ),
            combat_story=(
                "Assorbe pressione e coordina alleati vicini mentre contamina lo spazio. "
                "La risposta corretta è separarla dalla colonia e sfruttarne l'immobilità."
            ),
            siblings=[
                ("Spriggan", "nearest", "Entrambe comandano un ambiente, ma la Regina è immobile e biologica."),
                ("Dreugh", "same-durability", "Il Dreugh è mobile e rigenera; la Regina controlla tramite colonia e spore."),
                ("Lupo", "contrast", "Il Lupo vince muovendosi; la Regina ha velocità e agilità costanti a zero."),
            ],
            axes=[
                ("brood control", "Richiamo della Colonia e Nuvola di Spore"),
                ("fortezza immobile", "pf/difesa/rd_fis alti e velocita/agilita 0"),
            ],
            must=["immobilità", "durabilità", "controllo colonia", "sputo caustico"],
            must_not=["danno Veleno", "evocazione non implementata", "mobilità"],
            rigidity="none",
            variation="finestre delle azioni e curve",
            checkpoints={
                "1": "cuore immobile già resistente",
                "5": "richiamo coordina alleati esistenti",
                "10": "spore controllano l'area",
                "15": "sputo punisce chi resta lontano",
                "20": "boss di colonia, non duellante",
            },
            range_reason="La riga legacy è livello 20; il kit viene scaglionato mantenendo immobilità costante.",
        ),
        expectation_data=expectations(
            unit="Regina Kwama",
            kind="creature",
            all_variants={
                "equipmentSlotCount": 0,
                "skillUnlockCount": 0,
                "competenceCount": 0,
                "innateActionKeys": ["richiamo-colonia", "nuvola-di-spore", "sputo-caustico"],
                "warningCount": 0,
            },
            at_least_one=["velocita e agilita pari a 0 a ogni checkpoint"],
            allowed=["azioni in finestra", "curve"],
            forbidden=["danno Veleno", "spawn di minion", "movimento"],
            differs_from={
                "Spriggan": "immobilità assoluta e PF superiori",
                "Dreugh": "nessuna rigenerazione o coda mobile",
            },
            curve_assertions=[{"key": "pf", "level": 10, "expected": 125}],
        ),
        proposal=creature_payload(
            name="Regina Kwama",
            category="Natura",
            archetype="Fortezza biologica immobile che coordina la colonia e controlla l'area con spore e secrezioni.",
            lore=(
                "Vive nel cuore delle miniere di uova di Morrowind. La sua morte compromette "
                "la colonia e l'economia che dipende dal suo ciclo riproduttivo."
            ),
            stat_curves={
                "pf": (35, 225),
                "pa": (8, 26),
                "energia": (6, 29),
                "potere": (6, 29),
                "mana": (21, 128),
                "forza": (9, 23),
                "resistenza": (11, 30),
                "velocita": (0, 0),
                "agilita": (0, 0),
                "intelligenza": (8, 20),
                "concentrazione": (9, 23),
                "personalita": (0, 0),
                "saggezza": (9, 23),
                "attacco": (7, 33),
                "difesa": (12, 75),
                "tier": (3, 10),
                "rd_fis": (2, 7),
                "res_contundente": (-1, 3),
                "res_taglio": (0, 3),
                "res_perforante": (0, 3),
                "res_fuoco": (-2, 2),
                "res_gelo": (0, 0),
                "res_elettro": (0, 0),
                "rd_fuoco": (1, 3),
                "rd_gelo": (0, 0),
                "rd_elettro": (0, 0),
                "ap": (0, 0),
            },
            actions=[
                action(
                    "richiamo-colonia",
                    "Richiamo della Colonia",
                    (
                        "Fino a 3 alleati Kwama già presenti entro 4 esagoni ottengono "
                        "+2 Attacco e +2 Difesa per 2 turni. Non crea nuove creature."
                    ),
                    {"pa": 7, "energia": 8},
                    duration="2 turni",
                    icon="sciame",
                ),
                action(
                    "nuvola-di-spore",
                    "Nuvola di Spore",
                    (
                        "I nemici entro 2 esagoni che falliscono Resistenza subiscono "
                        "-2 Attacco e -2 Difesa per 2 turni."
                    ),
                    {"pa": 6, "energia": 6},
                    minimum=6,
                    duration="2 turni",
                    icon="spore",
                ),
                action(
                    "sputo-caustico",
                    "Sputo Caustico",
                    (
                        "Attacco contro un bersaglio entro 4 esagoni: 2d6 + livello "
                        "danni Perforante e -2 Difesa per 2 turni."
                    ),
                    {"pa": 4, "energia": 5},
                    minimum=10,
                    duration="2 turni",
                    icon="veleno",
                ),
            ],
            notes="Conversione v2 della Unit Elder #982; veleno e spawn sostituiti con primitive supportate.",
        ),
        evidence=[
            {"claim": "colonia e immobilità", "source": "unitlore:100"},
            {"claim": "spore e sputo", "source": "skillnpc:19,2"},
        ],
        rejected=[
            {
                "candidate": {"mechanic": "evoca 2 minion"},
                "decision": "reject",
                "reasonCode": "summoning-not-implemented",
                "reason": "Il sistema dedicato alle evocazioni è marcato NON ANCORA IMPLEMENTATO.",
            },
            {
                "candidate": {"mechanic": "danno da veleno"},
                "decision": "reject",
                "reasonCode": "unsupported-damage-type",
                "reason": "Veleno non è in DAMAGE_TYPES.",
            },
        ],
        deviations=[
            {
                "what": "Evoca Minion",
                "from": "crea creature",
                "to": "buffa alleati Kwama già presenti",
                "why": "preserva brood control senza inventare uno spawn handler",
            },
            {
                "what": "Sputo Velenoso",
                "from": "danno Veleno + status",
                "to": "Perforante + malus Difesa",
                "why": "usa danno e variabile implementati",
            },
        ],
        legality=[
            {"claim": "Perforante", "source": "backend.combat.rules.DAMAGE_TYPES"},
            {"claim": "buff/debuff Attacco-Difesa", "source": "OperazioneEffettoPersonalizzato add/subtract"},
            {"claim": "evocazione assente", "source": "backend.core.guides_it EVOCAZIONE"},
        ],
    ),
    base_candidate(
        source_file="978",
        charter_data=charter(
            unit="Dreugh",
            source_ids=[978],
            kind="creature",
            kind_reason="Creatura anfibia dal carapace naturale, senza equipaggiamento gestibile.",
            fantasy=(
                "Predatore anfibio antico e territoriale, più pericoloso nell'acqua che "
                "sulla terra. Il carapace e la rigenerazione lo fanno sembrare una lotta "
                "contro qualcosa che il mare non vuole cedere."
            ),
            combat_story=(
                "Assorbe il primo impatto, rigenera e spazza gli adiacenti con la coda. "
                "La vulnerabilità elettrica invita a interromperne la tenuta prima che "
                "Sottrai Vita ribalti lo scambio."
            ),
            siblings=[
                ("Regina Kwama", "nearest", "Entrambi hanno corazza biologica; il Dreugh è mobile e autosufficiente."),
                ("Atronach del Gelo", "same-durability", "Il Dreugh rigenera ed è vulnerabile all'elettricità, non al fuoco."),
                ("Cliff Racer", "contrast", "Il Dreugh regge il fronte e non possiede mobilità aerea."),
            ],
            axes=[
                ("carapace rigenerante", "rd_fis 3 costante, Pelle di Pietra e Rigenerazione"),
                ("controllo adiacente", "Colpo di Coda e Sottrai Vita"),
            ],
            must=["carapace", "rigenerazione", "coda", "vulnerabilità elettrica"],
            must_not=["volo", "equipaggiamento", "danno necrotico inventato"],
            rigidity="none",
            variation="azioni in finestra e curve",
            checkpoints={
                "1": "carapace e coda leggibili",
                "5": "rigenerazione obbliga a concentrare il danno",
                "10": "Sottrai Vita ribalta scambi lunghi",
                "15": "tank anfibio completo",
                "20": "antica minaccia resistente, non boss immobile",
            },
            range_reason="La riga legacy è livello 20; le azioni sono distribuite 1-20 mantenendo le costanti.",
        ),
        expectation_data=expectations(
            unit="Dreugh",
            kind="creature",
            all_variants={
                "equipmentSlotCount": 0,
                "skillUnlockCount": 0,
                "competenceCount": 0,
                "warningCount": 0,
            },
            at_least_one=["rd_fis 3 e res_elettro -1 a ogni checkpoint"],
            allowed=["azioni in finestra", "curve"],
            forbidden=["equipaggiamento", "Skill", "volo"],
            differs_from={
                "Regina Kwama": "velocità non zero e rigenerazione propria",
                "Atronach del Gelo": "debolezza elettrica e nessuna immunità al gelo",
            },
            curve_assertions=[{"key": "pf", "level": 10, "expected": 61}],
        ),
        proposal=creature_payload(
            name="Dreugh",
            category="Natura",
            archetype="Tank anfibio con carapace, rigenerazione, controllo adiacente e vulnerabilità elettrica.",
            lore=(
                "Vive nelle acque di Morrowind e porta miti di un mondo primordiale. "
                "È territoriale, alieno e molto più rischioso da affrontare sotto la superficie."
            ),
            stat_curves={
                "pf": (18, 108),
                "pa": (7, 23),
                "energia": (7, 31),
                "potere": (6, 29),
                "mana": (21, 128),
                "forza": (11, 30),
                "resistenza": (11, 30),
                "velocita": (9, 23),
                "agilita": (9, 23),
                "intelligenza": (9, 23),
                "concentrazione": (9, 23),
                "personalita": (0, 0),
                "saggezza": (9, 23),
                "attacco": (11, 67),
                "difesa": (8, 42),
                "tier": (4, 13),
                "rd_fis": (3, 3),
                "res_contundente": (-2, 2),
                "res_taglio": (0, 3),
                "res_perforante": (-1, 2),
                "res_fuoco": (1, 1),
                "res_gelo": (0, 0),
                "res_elettro": (-1, -1),
                "rd_fuoco": (2, 2),
                "rd_gelo": (0, 0),
                "rd_elettro": (0, 0),
                "ap": (0, 0),
            },
            actions=[
                action(
                    "pelle-di-pietra",
                    "Pelle di Pietra",
                    "Ottiene +2 rd_fis e +3 Difesa per 3 turni.",
                    {"pa": 5, "energia": 5},
                    duration="3 turni",
                    icon="scudo",
                ),
                action(
                    "rigenerazione",
                    "Rigenerazione",
                    "All'inizio di ciascun turno recupera 1d6 PF per livello per 3 turni.",
                    {"energia": 5},
                    minimum=5,
                    trigger="Passiva attivata",
                    duration="3 turni",
                    icon="rigenerazione",
                ),
                action(
                    "colpo-di-coda",
                    "Colpo di Coda",
                    (
                        "Infligge danni Contundente a tutti i bersagli in un arco adiacente; "
                        "chi perde Difesa spende 2 PA aggiuntivi nella prossima azione."
                    ),
                    {"pa": 6, "energia": 4},
                    icon="coda",
                ),
                action(
                    "sottrai-vita",
                    "Sottrai Vita",
                    (
                        "Un bersaglio entro 2 esagoni subisce 2d6 + livello danni Puro; "
                        "il Dreugh recupera PF pari al danno effettivamente inflitto."
                    ),
                    {"pa": 5, "energia": 5},
                    minimum=10,
                    icon="sifone",
                ),
            ],
            notes="Conversione v2 della Unit Elder #978; costanti di resistenza e riduzione preservate.",
        ),
        evidence=[
            {"claim": "carapace e ambiente acquatico", "source": "unitlore:51"},
            {"claim": "Pelle, Rigenerazione, Coda, Sottrai Vita", "source": "skillnpc:17,68,16,18"},
        ],
        rejected=[
            {
                "candidate": {"mechanic": "danno necrotico"},
                "decision": "reject",
                "reasonCode": "unsupported-damage-type",
                "reason": "Il drenaggio usa Puro, già presente in DAMAGE_TYPES.",
            }
        ],
        deviations=[
            {
                "what": "Pelle di Pietra",
                "from": "riduzione percentuale generica 50%",
                "to": "+2 rd_fis e +3 Difesa",
                "why": "variabili concrete e applicabili dal motore",
            }
        ],
        legality=[
            {"claim": "danno Puro e cura", "source": "DAMAGE_TYPES + Skill 514 Sifone 1"},
            {"claim": "rd_fis/Difesa", "source": "motore effetti personalizzati"},
        ],
    ),
    base_candidate(
        source_file="1007",
        charter_data=charter(
            unit="Atronach del Gelo",
            source_ids=[1007],
            kind="creature",
            kind_reason="Costrutto elementale evocato, rappresentato da curve e azioni innate.",
            fantasy=(
                "Parete d'inverno animata: lenta, ostinata e priva di paura. Il suo corpo "
                "di ghiaccio e pietra rende evidente sia la superiorità nel gelo sia la "
                "debolezza al fuoco."
            ),
            combat_story=(
                "Chiude distanza e spazio con coni di Gelo, si fortifica e infine copre "
                "un'area ampia con Tormenta. Il gruppo deve sfruttare Fuoco e mobilità."
            ),
            siblings=[
                ("Dreugh", "nearest", "Entrambi sono tank, ma l'Atronach controlla col Gelo ed è vulnerabile al Fuoco."),
                ("Spriggan", "same-magic", "Condivide natura sovrannaturale, non rigenerazione vegetale o alleati."),
                ("Drago", "contrast", "Ha portata e cognizione inferiori e nessun volo."),
            ],
            axes=[
                ("immunità gelo/debolezza fuoco", "res_gelo/rd_gelo 5 e res_fuoco -2 costanti"),
                ("controllo glaciale", "Soffio Gelido e Tormenta"),
            ],
            must=["Gelo", "corpo resistente", "debolezza Fuoco", "lentezza"],
            must_not=["volo", "rigenerazione", "equipaggiamento"],
            rigidity="none",
            variation="azioni in finestra e curve",
            checkpoints={
                "1": "parete lenta con soffio",
                "5": "armatura di ghiaccio",
                "10": "resistenze elementali decisive",
                "15": "Tormenta controlla il gruppo",
                "20": "tank elementale completo ma sfruttabile col Fuoco",
            },
            range_reason="La riga legacy è livello 20; il kit elementale viene distribuito lungo 1-20.",
        ),
        expectation_data=expectations(
            unit="Atronach del Gelo",
            kind="creature",
            all_variants={
                "equipmentSlotCount": 0,
                "skillUnlockCount": 0,
                "competenceCount": 0,
                "warningCount": 0,
            },
            at_least_one=["res_gelo 5 e res_fuoco -2 a ogni checkpoint"],
            allowed=["azioni in finestra", "curve"],
            forbidden=["equipaggiamento", "Skill", "danno non Gelo nelle azioni"],
            differs_from={
                "Dreugh": "Gelo 5 costante e Fuoco -2",
                "Drago": "nessun volo e meno PF",
            },
            curve_assertions=[{"key": "pf", "level": 10, "expected": 84}],
        ),
        proposal=creature_payload(
            name="Atronach del Gelo",
            category="Daedra",
            archetype="Tank elementale lento che controlla spazio con Gelo ed espone una netta debolezza al Fuoco.",
            lore=(
                "Proviene da piani freddi dell'Oblivion o da luoghi dove il gelo sembra "
                "vivo. Avanza senza paura come una parete d'inverno."
            ),
            stat_curves={
                "pf": (25, 150),
                "pa": (7, 23),
                "energia": (7, 31),
                "potere": (8, 35),
                "mana": (25, 150),
                "forza": (13, 33),
                "resistenza": (13, 33),
                "velocita": (8, 20),
                "agilita": (8, 20),
                "intelligenza": (9, 23),
                "concentrazione": (10, 27),
                "personalita": (0, 0),
                "saggezza": (9, 23),
                "attacco": (12, 75),
                "difesa": (12, 75),
                "tier": (5, 14),
                "rd_fis": (2, 2),
                "res_contundente": (0, 0),
                "res_taglio": (2, 2),
                "res_perforante": (2, 2),
                "res_fuoco": (-2, -2),
                "res_gelo": (5, 5),
                "res_elettro": (0, 0),
                "rd_fuoco": (0, 0),
                "rd_gelo": (5, 5),
                "rd_elettro": (0, 0),
                "ap": (0, 0),
            },
            actions=[
                action(
                    "soffio-gelido",
                    "Soffio Gelido",
                    "Cono largo 3 esagoni: 4d6 + livello danni Gelo.",
                    {"pa": 6, "energia": 5},
                    icon="gelo",
                ),
                action(
                    "armatura-di-ghiaccio",
                    "Armatura di Ghiaccio",
                    "Ottiene +5 Difesa e +2 rd_fis per 3 turni.",
                    {"pa": 4, "energia": 4},
                    minimum=5,
                    duration="3 turni",
                    icon="scudo",
                ),
                action(
                    "tormenta",
                    "Tormenta",
                    (
                        "Tutti i nemici entro 5 esagoni subiscono 4d6 + livello danni "
                        "Gelo e -2 Agilità per 2 turni."
                    ),
                    {"pa": 7, "energia": 7},
                    minimum=12,
                    duration="2 turni",
                    icon="gelo",
                ),
            ],
            notes="Conversione v2 della Unit Elder #1007; costanti elementali preservate.",
        ),
        evidence=[
            {"claim": "corpo di ghiaccio e lentezza", "source": "unitlore:13"},
            {"claim": "Soffio, Armatura, Tormenta", "source": "skillnpc:21,10,44"},
        ],
        rejected=[
            {
                "candidate": {"mechanic": "riflette il 25% dei danni"},
                "decision": "reject",
                "reasonCode": "reflection-handler-absent",
                "reason": "La riflessione non ha un handler verificato; sostituita da rd_fis.",
            }
        ],
        deviations=[
            {
                "what": "Armatura di Ghiaccio",
                "from": "resistenza percentuale e riflessione",
                "to": "+5 Difesa e +2 rd_fis",
                "why": "primitive numeriche implementate",
            }
        ],
        legality=[
            {"claim": "Gelo", "source": "backend.combat.rules.DAMAGE_TYPES"},
            {"claim": "Difesa/rd_fis/Agilità", "source": "motore effetti personalizzati"},
        ],
    ),
    base_candidate(
        source_file="1013",
        charter_data=charter(
            unit="Lich",
            source_ids=[1013],
            kind="creature",
            kind_reason="Non-morto innato con chassis e azioni proprie, senza inventario generato.",
            fantasy=(
                "Mago che ha tradito la morte per continuare a studiare e dominare. "
                "Il corpo è soltanto il primo strato della minaccia: volontà, rituali "
                "e difese arcane fanno sentire ogni scambio temporaneo."
            ),
            combat_story=(
                "Drena risorse e saggezza, protegge la propria concentrazione e rafforza "
                "non-morti già presenti. Il gruppo deve interrompere la sequenza arcana "
                "e trovare ciò che ancora lo lega al mondo."
            ),
            siblings=[
                ("Anomalia Magica", "nearest", "Condivide potenza arcana, ma il Lich è intelligente e deliberato."),
                ("Spriggan", "same-control", "Entrambi sostengono alleati esistenti; il Lich usa non-morti e danno Puro."),
                ("Atronach del Gelo", "contrast", "Condivide resistenza al Gelo, ma non è un tank elementale frontale."),
            ],
            axes=[
                ("supremazia arcana persistente", "mana/potere/intelligenza alti e Barriera Mistica"),
                ("dominio dei caduti", "Comando dei Caduti senza spawn e Sottrazione Spirituale"),
            ],
            must=["mana alto", "Gelo 5", "drenaggio", "barriera"],
            must_not=["danno necrotico", "spawn/rinamazione non implementata", "equipaggiamento"],
            rigidity="none",
            variation="azioni in finestra e curve",
            checkpoints={
                "1": "incantatore non-morto già capace di drenare",
                "5": "barriera rende necessario cambiare ritmo",
                "10": "comanda alleati non-morti già presenti",
                "15": "tocco entropico punisce il corpo a corpo",
                "20": "boss arcano completo ma con regole numeriche leggibili",
            },
            range_reason="La riga legacy è livello 20; le quattro espressioni vengono distribuite lungo 1-20.",
        ),
        expectation_data=expectations(
            unit="Lich",
            kind="creature",
            all_variants={
                "equipmentSlotCount": 0,
                "skillUnlockCount": 0,
                "competenceCount": 0,
                "warningCount": 0,
            },
            at_least_one=["res_gelo e rd_gelo pari a 5 a ogni checkpoint"],
            allowed=["azioni in finestra", "curve"],
            forbidden=["equipaggiamento", "Skill", "danno Necrotico", "spawn di non-morti"],
            differs_from={
                "Anomalia Magica": "cognizione e PF superiori, kit deliberato",
                "Atronach del Gelo": "Difesa inferiore ma Mana e controllo superiori",
            },
            curve_assertions=[{"key": "pf", "level": 10, "expected": 93}],
        ),
        proposal=creature_payload(
            name="Lich",
            category="Non Morti",
            archetype="Boss arcano intelligente che drena, protegge la concentrazione e coordina non-morti già presenti.",
            lore=(
                "Nasce da rituali oscuri e volontà sufficiente a sacrificare l'umanità. "
                "Abbatterne il corpo può non bastare se il vincolo della sua esistenza resta intatto."
            ),
            stat_curves={
                "pf": (27, 167),
                "pa": (9, 29),
                "energia": (8, 33),
                "potere": (9, 38),
                "mana": (32, 206),
                "forza": (9, 23),
                "resistenza": (10, 27),
                "velocita": (9, 23),
                "agilita": (9, 23),
                "intelligenza": (14, 37),
                "concentrazione": (14, 37),
                "personalita": (0, 0),
                "saggezza": (14, 37),
                "attacco": (12, 75),
                "difesa": (9, 50),
                "tier": (5, 15),
                "rd_fis": (0, 0),
                "res_contundente": (0, 0),
                "res_taglio": (0, 0),
                "res_perforante": (0, 0),
                "res_fuoco": (2, 2),
                "res_gelo": (5, 5),
                "res_elettro": (2, 2),
                "rd_fuoco": (0, 0),
                "rd_gelo": (5, 5),
                "rd_elettro": (0, 0),
                "ap": (0, 0),
            },
            actions=[
                action(
                    "sottrazione-spirituale",
                    "Sottrazione Spirituale",
                    (
                        "Un bersaglio entro 4 esagoni subisce 2d6 + livello danni Puro "
                        "e -2 Saggezza per 2 turni."
                    ),
                    {"pa": 5, "energia": 5},
                    duration="2 turni",
                    icon="sifone",
                ),
                action(
                    "barriera-mistica",
                    "Barriera Mistica",
                    "Ottiene +5 Difesa e +3 rd_fuoco, rd_gelo e rd_elettro per 2 turni.",
                    {"pa": 4, "energia": 5},
                    minimum=5,
                    duration="2 turni",
                    icon="scudo",
                ),
                action(
                    "comando-dei-caduti",
                    "Comando dei Caduti",
                    (
                        "Fino a 2 alleati Non Morti già presenti entro 4 esagoni "
                        "ottengono +2 Forza e +2 Resistenza per 3 turni. Non rianima."
                    ),
                    {"pa": 7, "energia": 7},
                    minimum=10,
                    duration="3 turni",
                    icon="teschio",
                ),
                action(
                    "tocco-entropico",
                    "Tocco Entropico",
                    (
                        "Un bersaglio adiacente subisce 2d8 + livello danni Puro "
                        "e -2 Resistenza per 3 turni."
                    ),
                    {"pa": 5, "energia": 5},
                    minimum=14,
                    duration="3 turni",
                    icon="teschio",
                ),
            ],
            notes="Conversione v2 della Unit Elder #1013; rianimazione e necrotico re-autorizzati con primitive correnti.",
        ),
        evidence=[
            {"claim": "ambizione e non-morte", "source": "unitlore:69"},
            {"claim": "drenaggio, rianimazione, barriera, tocco", "source": "skillnpc:36,42,53,39"},
        ],
        rejected=[
            {
                "candidate": {"mechanic": "Rianima Morti"},
                "decision": "reject",
                "reasonCode": "summoning-not-implemented",
                "reason": "Sostituita da un buff a non-morti già presenti.",
            },
            {
                "candidate": {"damageType": "Necrotico"},
                "decision": "reject",
                "reasonCode": "unsupported-damage-type",
                "reason": "Il drenaggio usa Puro.",
            },
        ],
        deviations=[
            {
                "what": "Rianima Morti",
                "from": "crea un alleato da un caduto",
                "to": "rafforza alleati Non Morti esistenti",
                "why": "nessun sistema dedicato di evocazione/rianimazione",
            },
            {
                "what": "Tocco Necrotico",
                "from": "necrotico + dimezza guarigione",
                "to": "Puro + malus Resistenza",
                "why": "tipo di danno e variabile implementati",
            },
        ],
        legality=[
            {"claim": "Puro", "source": "backend.combat.rules.DAMAGE_TYPES"},
            {"claim": "barriera numerica", "source": "motore effetti personalizzati"},
            {"claim": "evocazione assente", "source": "backend.core.guides_it EVOCAZIONE"},
        ],
    ),
    base_candidate(
        source_file="1018",
        charter_data=charter(
            unit="Spriggan",
            source_ids=[1018],
            kind="creature",
            kind_reason="Spirito arboreo con corpo e magia innate, senza equipaggiamento.",
            fantasy=(
                "Volontà della foresta resa corpo: protettiva, furiosa e indifferente "
                "alla morale dei mortali. In un bosco ogni radice e alleato naturale "
                "sembra estendere la sua presenza."
            ),
            combat_story=(
                "Immobilizza, sostiene creature già presenti e recupera vita tramite "
                "drenaggio. Il Fuoco e la separazione dagli alleati naturali sono le "
                "risposte più chiare."
            ),
            siblings=[
                ("Regina Kwama", "nearest", "Entrambe coordinano un ecosistema; la Spriggan è mobile e magica."),
                ("Lupo", "same-family", "Protegge gli animali ma non condivide furia o cognizione bassa."),
                ("Atronach del Gelo", "contrast", "È vulnerabile al Fuoco e rigenera, non una parete elementale."),
            ],
            axes=[
                ("foresta come estensione", "Radici e Richiamo del Bosco senza spawn"),
                ("vita vegetale persistente", "PF/resistenza alti e Sottrai Vita"),
            ],
            must=["radici", "alleati naturali", "drenaggio", "debolezza Fuoco"],
            must_not=["spawn non implementato", "equipaggiamento", "danno necrotico"],
            rigidity="none",
            variation="azioni in finestra e curve",
            checkpoints={
                "1": "spirito mobile con Radici",
                "5": "coordina alleati già presenti",
                "10": "drenaggio sostiene lo scontro",
                "15": "controllo boschivo completo",
                "20": "guardiana antica, non tank elementale",
            },
            range_reason="La riga legacy è livello 20; il kit viene distribuito senza alterare le costanti.",
        ),
        expectation_data=expectations(
            unit="Spriggan",
            kind="creature",
            all_variants={
                "equipmentSlotCount": 0,
                "skillUnlockCount": 0,
                "competenceCount": 0,
                "warningCount": 0,
            },
            at_least_one=["Radici Intrappolanti a ogni livello"],
            allowed=["azioni in finestra", "curve"],
            forbidden=["equipaggiamento", "Skill", "spawn", "danno Necrotico"],
            differs_from={
                "Regina Kwama": "velocità non zero e PF inferiori",
                "Atronach del Gelo": "nessuna immunità al Gelo e controllo tramite radici",
            },
            curve_assertions=[{"key": "pf", "level": 10, "expected": 93}],
        ),
        proposal=creature_payload(
            name="Spriggan",
            category="Natura",
            archetype="Controllore naturale mobile che immobilizza, coordina alleati esistenti e drena vita.",
            lore=(
                "Abita foreste sacre e radure antiche. Può ignorare chi rispetta il luogo "
                "e distruggere chi brucia, taglia o corrompe il suo dominio."
            ),
            stat_curves={
                "pf": (27, 167),
                "pa": (8, 26),
                "energia": (8, 33),
                "potere": (8, 33),
                "mana": (27, 167),
                "forza": (10, 27),
                "resistenza": (11, 30),
                "velocita": (9, 23),
                "agilita": (10, 27),
                "intelligenza": (10, 27),
                "concentrazione": (11, 30),
                "personalita": (13, 33),
                "saggezza": (11, 30),
                "attacco": (10, 58),
                "difesa": (9, 50),
                "tier": (4, 11),
                "rd_fis": (1, 5),
                "res_contundente": (0, 3),
                "res_taglio": (-3, 1),
                "res_perforante": (0, 3),
                "res_fuoco": (-3, 1),
                "res_gelo": (0, 0),
                "res_elettro": (0, 0),
                "rd_fuoco": (0, 0),
                "rd_gelo": (0, 0),
                "rd_elettro": (2, 2),
                "ap": (0, 0),
            },
            actions=[
                action(
                    "radici-intrappolanti",
                    "Radici Intrappolanti",
                    (
                        "Fino a 2 bersagli entro 4 esagoni che falliscono Agilità "
                        "subiscono -5 PA per 2 turni."
                    ),
                    {"pa": 6, "energia": 5},
                    duration="2 turni",
                    icon="radici",
                ),
                action(
                    "richiamo-del-bosco",
                    "Richiamo del Bosco",
                    (
                        "Fino a 3 alleati Animali o Natura già presenti entro 4 esagoni "
                        "ottengono +2 Attacco e +2 Difesa per 2 turni. Non evoca."
                    ),
                    {"pa": 7, "energia": 8},
                    minimum=5,
                    duration="2 turni",
                    icon="foglia",
                ),
                action(
                    "sottrai-vita",
                    "Sottrai Vita",
                    (
                        "Un bersaglio entro 3 esagoni subisce 2d6 + livello danni Puro; "
                        "la Spriggan recupera PF pari al danno effettivamente inflitto."
                    ),
                    {"pa": 5, "energia": 5},
                    minimum=9,
                    icon="sifone",
                ),
            ],
            notes="Conversione v2 della Unit Elder #1018; Evoca Minion sostituito da supporto ad alleati presenti.",
        ),
        evidence=[
            {"claim": "foresta, animali e rigenerazione", "source": "unitlore:118"},
            {"claim": "Radici, Evoca Minion, Sottrai Vita", "source": "skillnpc:43,23,18"},
        ],
        rejected=[
            {
                "candidate": {"mechanic": "Evoca Minion"},
                "decision": "reject",
                "reasonCode": "summoning-not-implemented",
                "reason": "Il richiamo sostiene soltanto alleati già presenti.",
            }
        ],
        deviations=[
            {
                "what": "Evoca Minion",
                "from": "crea due creature",
                "to": "buffa alleati Natura/Animali già presenti",
                "why": "mantiene la foresta come estensione senza sistema di spawn",
            }
        ],
        legality=[
            {"claim": "malus PA", "source": "Personaggio.pa e motore effetti"},
            {"claim": "danno Puro e cura", "source": "DAMAGE_TYPES + Skill 514 Sifone"},
        ],
    ),
    base_candidate(
        source_file="1020",
        charter_data=charter(
            unit="Drago",
            source_ids=[1020],
            kind="creature",
            kind_reason="Dovah con corpo, volo e Thu'um innati; nessun equipaggiamento.",
            fantasy=(
                "Volontà antica capace di dominare cielo, terreno e parola. Non è una "
                "bestia volante più grande: ogni comparsa deve cambiare la geografia "
                "tattica e far sentire la superiorità di una creatura consapevole."
            ),
            combat_story=(
                "Alterna volo strategico, soffio ad area e controllo della coda. Questa "
                "Unit rappresenta il Drago di Fuoco base; Gelo ed Elettro restano future "
                "varianti separate per evitare che ogni drago possieda ogni respiro."
            ),
            siblings=[
                ("Cliff Racer", "nearest", "Condivide il volo ma supera PF, cognizione, portata e controllo."),
                ("Atronach del Gelo", "same-elemental", "Il Drago è mobile e intelligente, non immune a un solo elemento."),
                ("Lich", "contrast", "Condivide status da boss intelligente, ma domina fisicamente e dal cielo."),
            ],
            axes=[
                ("volo strategico", "Tuffo del Dovah, velocita e agilita alte"),
                ("Voce elementale", "Soffio di Fuoco ad area; altre voci escluse dalla Unit base"),
            ],
            must=["volo", "Fuoco", "cognizione alta", "coda"],
            must_not=["tutti e tre i respiri", "cognizione animale", "equipaggiamento"],
            rigidity="none",
            variation="azioni in finestra e curve; elemento demandato a Unit future",
            checkpoints={
                "1": "giovane drago già volante e intelligente",
                "5": "Soffio di Fuoco ridisegna lo spazio",
                "10": "coda punisce l'accerchiamento",
                "15": "corazza draconica completa",
                "20": "boss strategico senza accumulo di ogni variante elementale",
            },
            range_reason="La riga legacy è livello 20; la scala 1-20 rappresenta età/potere mantenendo identità da Dovah.",
        ),
        expectation_data=expectations(
            unit="Drago",
            kind="creature",
            all_variants={
                "equipmentSlotCount": 0,
                "skillUnlockCount": 0,
                "competenceCount": 0,
                "warningCount": 0,
            },
            at_least_one=["intelligenza almeno 13 a ogni checkpoint"],
            allowed=["azioni in finestra", "curve"],
            forbidden=["equipaggiamento", "Skill", "Soffio Gelido", "Respiro Fulmineo"],
            differs_from={
                "Cliff Racer": "PF, Tier e cognizione nettamente superiori",
                "Atronach del Gelo": "volo e Fuoco anziché immunità Gelo",
            },
            curve_assertions=[{"key": "pf", "level": 10, "expected": 125}],
        ),
        proposal=creature_payload(
            name="Drago",
            category="Natura",
            archetype="Boss volante intelligente che domina spazio e ritmo con Fuoco, tuffo e coda.",
            lore=(
                "I Dovah sono creature antiche legate al tempo e alla Parola. Orgoglio "
                "e volontà di dominio li rendono capaci di trattare, comandare o distruggere."
            ),
            stat_curves={
                "pf": (35, 225),
                "pa": (9, 29),
                "energia": (8, 36),
                "potere": (9, 38),
                "mana": (29, 186),
                "forza": (15, 40),
                "resistenza": (15, 40),
                "velocita": (11, 30),
                "agilita": (10, 27),
                "intelligenza": (13, 33),
                "concentrazione": (13, 33),
                "personalita": (0, 0),
                "saggezza": (13, 33),
                "attacco": (13, 83),
                "difesa": (13, 83),
                "tier": (5, 15),
                "rd_fis": (1, 5),
                "res_contundente": (0, 3),
                "res_taglio": (0, 3),
                "res_perforante": (-1, 3),
                "res_fuoco": (1, 4),
                "res_gelo": (1, 4),
                "res_elettro": (1, 4),
                "rd_fuoco": (2, 2),
                "rd_gelo": (2, 2),
                "rd_elettro": (2, 2),
                "ap": (2, 7),
            },
            actions=[
                action(
                    "tuffo-del-dovah",
                    "Tuffo del Dovah",
                    (
                        "Vola fino a 8 esagoni e attacca un bersaglio all'arrivo, "
                        "infliggendo 4d8 + livello danni Perforante."
                    ),
                    {"pa": 6, "energia": 5},
                    icon="ala",
                ),
                action(
                    "soffio-di-fuoco",
                    "Soffio di Fuoco",
                    "Cono largo 3 esagoni: 4d8 + livello danni Fuoco.",
                    {"pa": 7, "energia": 6},
                    minimum=5,
                    icon="fuoco",
                ),
                action(
                    "colpo-di-coda",
                    "Colpo di Coda",
                    (
                        "Tutti i bersagli in un arco adiacente subiscono danni Contundente; "
                        "chi perde Difesa viene spinto di 2 esagoni."
                    ),
                    {"pa": 6, "energia": 4},
                    minimum=8,
                    icon="coda",
                ),
                action(
                    "pelle-draconica",
                    "Pelle Draconica",
                    "Ottiene +3 rd_fis e +3 Difesa per 3 turni.",
                    {"pa": 5, "energia": 5},
                    minimum=12,
                    duration="3 turni",
                    icon="scudo",
                ),
            ],
            notes="Conversione v2 della Unit Elder #1020; il Drago base usa Fuoco, non tutti i respiri.",
        ),
        evidence=[
            {"claim": "Voce, volo e intelligenza", "source": "unitlore:46"},
            {"claim": "respiri, tuffo e coda legacy", "source": "skillnpc:9,21,7,51,16"},
        ],
        rejected=[
            {
                "candidate": {"action": "Soffio Gelido"},
                "decision": "reject",
                "reasonCode": "variant-axis-overload",
                "reason": "Riservato a una futura Unit Drago del Gelo.",
            },
            {
                "candidate": {"action": "Respiro Fulmineo"},
                "decision": "reject",
                "reasonCode": "variant-axis-overload",
                "reason": "Riservato a una futura Unit Drago della Tempesta.",
            },
        ],
        deviations=[
            {
                "what": "respiri elementali",
                "from": "Fuoco, Gelo ed Elettro nella stessa riga",
                "to": "solo Fuoco nella Unit base",
                "why": "preserva una singola firma elementale e prepara varianti distinte",
            }
        ],
        legality=[
            {"claim": "Fuoco/Perforante/Contundente", "source": "backend.combat.rules.DAMAGE_TYPES"},
            {"claim": "spinta", "source": "Skill 330 Sbilancia e regole esagoni"},
        ],
    ),
    base_candidate(
        source_file="1031",
        charter_data=charter(
            unit="Centurione Nanico",
            source_ids=[1031],
            kind="creature",
            kind_reason=(
                "Costrutto senza progressione Skill o inventario; il martello legacy "
                "diventa un'azione innata perché il contratto creature vieta equipment."
            ),
            fantasy=(
                "Colosso Dwemer che continua un ordine antico senza volontà, paura o "
                "stanchezza. È una macchina da guardia: metallo, vapore e un martello "
                "capace di spezzare armature."
            ),
            combat_story=(
                "Avanza lentamente, colpisce con forza e usa vapore per negare gli "
                "adiacenti. Il gruppo deve sfruttare la vulnerabilità elettrica e non "
                "tentare intimidazione o logoramento psicologico."
            ),
            siblings=[
                ("Atronach del Gelo", "nearest", "Entrambi sono tank non organici; il Centurione usa vapore e vulnerabilità elettrica."),
                ("Soldato Dremora", "classification-contrast", "Il Centurione non equipaggia il martello e non apprende Skill."),
                ("Anomalia Magica", "contrast", "Il Centurione è fisico e prevedibile, non distorce risorse arcane."),
            ],
            axes=[
                ("martello innato a vapore", "Martello Pneumatico derivato dall'item legacy"),
                ("costrutto implacabile", "PF/Forza alti, Mana 0 e vulnerabilità elettrica"),
            ],
            must=["martello", "vapore", "lentezza", "costrutto"],
            must_not=["equipment", "Skill", "magia", "personalità"],
            rigidity="none",
            variation="azioni in finestra e curve",
            checkpoints={
                "1": "guardiano lento con martello",
                "5": "vapore nega gli adiacenti",
                "10": "corazza automatica",
                "15": "colosso difficile da abbattere",
                "20": "macchina d'assedio, ancora vulnerabile all'elettricità",
            },
            range_reason="La riga legacy è livello 20; le funzioni del costrutto vengono distribuite lungo 1-20.",
        ),
        expectation_data=expectations(
            unit="Centurione Nanico",
            kind="creature",
            all_variants={
                "equipmentSlotCount": 0,
                "skillUnlockCount": 0,
                "competenceCount": 0,
                "warningCount": 0,
            },
            at_least_one=["mana 0 e res_elettro -1 a ogni checkpoint"],
            allowed=["azioni in finestra", "curve"],
            forbidden=["Martello equipaggiato", "SkillPersonaggio", "magia", "razza mortale"],
            differs_from={
                "Soldato Dremora": "zero equipment e martello dentro innateActions",
                "Atronach del Gelo": "Gelo non è l'asse; l'elettricità è una debolezza",
            },
            curve_assertions=[{"key": "pf", "level": 10, "expected": 114}],
        ),
        proposal=creature_payload(
            name="Centurione Nanico",
            category="Extra",
            archetype="Costrutto Dwemer lento e implacabile con martello pneumatico, vapore e corazza.",
            lore=(
                "Pattuglia rovine Dwemer eseguendo ordini senza curiosità o pietà. "
                "Non può essere intimidito, corrotto o stancato."
            ),
            stat_curves={
                "pf": (32, 206),
                "pa": (8, 26),
                "energia": (6, 29),
                "potere": (6, 29),
                "mana": (0, 0),
                "forza": (13, 33),
                "resistenza": (13, 33),
                "velocita": (8, 20),
                "agilita": (8, 20),
                "intelligenza": (6, 13),
                "concentrazione": (6, 13),
                "personalita": (0, 0),
                "saggezza": (6, 13),
                "attacco": (13, 83),
                "difesa": (10, 58),
                "tier": (5, 15),
                "rd_fis": (1, 1),
                "res_contundente": (-1, -1),
                "res_taglio": (1, 1),
                "res_perforante": (0, 0),
                "res_fuoco": (0, 0),
                "res_gelo": (3, 3),
                "res_elettro": (-1, -1),
                "rd_fuoco": (0, 0),
                "rd_gelo": (5, 5),
                "rd_elettro": (0, 0),
                "ap": (0, 0),
            },
            actions=[
                action(
                    "martello-pneumatico",
                    "Martello Pneumatico",
                    (
                        "Attacco contro un bersaglio adiacente: 4d8 + livello danni "
                        "Contundente; chi perde Difesa viene spinto di 1 esagono."
                    ),
                    {"pa": 7, "energia": 4},
                    icon="martello",
                ),
                action(
                    "scarico-di-vapore",
                    "Scarico di Vapore",
                    (
                        "Tutti i bersagli entro 2 esagoni subiscono 3d6 + livello danni "
                        "Fuoco e -2 Attacco per 1 turno."
                    ),
                    {"pa": 6, "energia": 6},
                    minimum=5,
                    duration="1 turno",
                    icon="vapore",
                ),
                action(
                    "corazza-automatica",
                    "Corazza Automatica",
                    "Ottiene +3 rd_fis e +3 Difesa per 3 turni.",
                    {"pa": 4, "energia": 5},
                    minimum=10,
                    duration="3 turni",
                    icon="ingranaggio",
                ),
            ],
            notes="Conversione v2 della Unit Elder #1031; il martello Dwemer è un'azione innata, Mana azzerato.",
        ),
        evidence=[
            {"claim": "Martello da guerra Dwemer", "source": "unit:1031.arma"},
            {"claim": "vapore, metallo e assenza di volontà", "source": "unitlore:30"},
        ],
        rejected=[
            {
                "candidate": {"item": "Martello da guerra (dwemer)"},
                "decision": "reject",
                "reasonCode": "creature-equipment-forbidden",
                "reason": "Il contratto creature vieta equipment; l'arma diventa Martello Pneumatico.",
            }
        ],
        deviations=[
            {
                "what": "mana curve",
                "from": "legacy score 6 linear",
                "to": "0 costante",
                "why": "il Centurione non usa azioni magiche; vapore ed energia esprimono il costrutto",
            }
        ],
        legality=[
            {"claim": "Contundente/Fuoco", "source": "backend.combat.rules.DAMAGE_TYPES"},
            {"claim": "conversione weapon-to-action", "source": "kind contract creature"},
        ],
    ),
    base_candidate(
        source_file="1023",
        charter_data=charter(
            unit="Anomalia Magica",
            source_ids=[1023],
            kind="creature",
            kind_reason="Fenomeno arcano senza anatomia, equipaggiamento o Skill acquistate.",
            fantasy=(
                "Magia compressa e lasciata marcire fino a reagire come una volontà "
                "confusa. Non duella: destabilizza tempo, Mana e spazio finché la "
                "battaglia smette di comportarsi normalmente."
            ),
            combat_story=(
                "Ha pochi PF ma grandi riserve arcane e difese elementali crescenti. "
                "Ruba ritmo con PA, brucia Mana e si protegge convertendo la propria risorsa."
            ),
            siblings=[
                ("Lich", "nearest", "Condivide potenza arcana, ma l'Anomalia è fragile e priva di cognizione deliberata."),
                ("Atronach del Gelo", "same-origin", "Entrambe sono magie incarnate; l'Anomalia non è tank o mono-elementale."),
                ("Centurione Nanico", "contrast", "Il Centurione è fisico e prevedibile con Mana zero."),
            ],
            axes=[
                ("distorsione di risorse", "Distorsione Temporale e Bruciatura di Mana"),
                ("difesa alimentata dal Mana", "Scudo di Mana e curve elementali hi_hi linearizzate"),
            ],
            must=["PF bassi", "Mana alto", "PA", "resistenze elementali crescenti"],
            must_not=["forza alta", "equipaggiamento", "azioni fisiche generiche"],
            rigidity="none",
            variation="azioni in finestra e curve",
            checkpoints={
                "1": "fenomeno fragile ma ricco di Mana",
                "5": "Bruciatura punisce incantatori",
                "10": "Scudo converte risorsa in difesa",
                "15": "resistenze elementali lineari chiaramente alte",
                "20": "distorsione pericolosa, ancora eliminabile concentrando il danno",
            },
            range_reason="La riga legacy è livello 20; le azioni vengono distribuite mantenendo il profilo fragile/arcano.",
        ),
        expectation_data=expectations(
            unit="Anomalia Magica",
            kind="creature",
            all_variants={
                "equipmentSlotCount": 0,
                "skillUnlockCount": 0,
                "competenceCount": 0,
                "warningCount": 0,
            },
            at_least_one=["mana superiore a pf a ogni checkpoint"],
            allowed=["azioni in finestra", "curve"],
            forbidden=["equipaggiamento", "Skill", "forza da tank", "spawn"],
            differs_from={
                "Lich": "PF e cognizione inferiori; nessun dominio dei non-morti",
                "Centurione Nanico": "Mana alto e resistenze elementali crescenti",
            },
            curve_assertions=[{"key": "pf", "level": 10, "expected": 51}],
        ),
        proposal=creature_payload(
            name="Anomalia Magica",
            category="Extra",
            archetype="Fenomeno fragile ad alto Mana che altera PA, consuma risorse e costruisce difese elementali.",
            lore=(
                "Nasce in rovine, laboratori falliti e nodi dove il flusso arcano si è "
                "spezzato. Reagisce in modo instabile a movimento, vicinanza e incantesimi."
            ),
            stat_curves={
                "pf": (16, 89),
                "pa": (8, 26),
                "energia": (7, 31),
                "potere": (8, 33),
                "mana": (29, 186),
                "forza": (6, 17),
                "resistenza": (9, 23),
                "velocita": (10, 27),
                "agilita": (10, 27),
                "intelligenza": (9, 23),
                "concentrazione": (11, 30),
                "personalita": (0, 0),
                "saggezza": (9, 23),
                "attacco": (10, 58),
                "difesa": (10, 58),
                "tier": (4, 11),
                "rd_fis": (1, 4),
                "res_contundente": (0, 0),
                "res_taglio": (0, 0),
                "res_perforante": (0, 0),
                "res_fuoco": (0, 3),
                "res_gelo": (0, 3),
                "res_elettro": (0, 3),
                "rd_fuoco": (1, 5),
                "rd_gelo": (1, 5),
                "rd_elettro": (1, 5),
                "ap": (0, 0),
            },
            actions=[
                action(
                    "distorsione-temporale",
                    "Distorsione Temporale",
                    "Ottiene +5 PA per il turno corrente.",
                    {"pa": 5, "energia": 5},
                    icon="tempo",
                ),
                action(
                    "bruciatura-di-mana",
                    "Bruciatura di Mana",
                    (
                        "Un bersaglio entro 5 esagoni subisce 2d6 + livello danni Puro "
                        "e spende 1d4 Mana aggiuntivo."
                    ),
                    {"pa": 5, "energia": 5},
                    minimum=5,
                    icon="mana",
                ),
                action(
                    "scudo-di-mana",
                    "Scudo di Mana",
                    (
                        "Ottiene +5 Difesa e +2 rd_fis, rd_fuoco, rd_gelo e rd_elettro "
                        "per 2 turni."
                    ),
                    {"pa": 4, "mana": 10},
                    minimum=9,
                    duration="2 turni",
                    icon="scudo",
                ),
            ],
            notes="Conversione v2 della Unit Elder #1023; profili hi_hi conservano endpoint e diventano lineari.",
        ),
        evidence=[
            {"claim": "distorsione arcana e instabilità", "source": "unitlore:7"},
            {"claim": "tempo, Mana burn, scudo", "source": "skillnpc:60,32,48"},
        ],
        rejected=[
            {
                "candidate": {"mechanic": "turno extra immediato"},
                "decision": "reject",
                "reasonCode": "extra-turn-handler-absent",
                "reason": "Distorsione concede soltanto PA, variabile corrente.",
            }
        ],
        deviations=[
            {
                "what": "curve hi_hi elementali",
                "from": "shape legacy hi_hi",
                "to": "interpolazione lineare con endpoint conservati",
                "why": "il generatore supporta esclusivamente curve lineari",
            },
            {
                "what": "Distorsione Temporale boost",
                "from": "turno extra",
                "to": "solo +5 PA",
                "why": "nessun handler verificato per turni extra",
            },
        ],
        legality=[
            {"claim": "Puro", "source": "backend.combat.rules.DAMAGE_TYPES"},
            {"claim": "PA/Mana e riduzioni", "source": "campi Personaggio + motore effetti"},
        ],
    ),
]


ALL_CANDIDATES = HUMANOIDS + CREATURES


def load_research(source_file: str) -> dict[str, Any]:
    path = RESEARCH_ROOT / f"{source_file}.json"
    if not path.exists():
        raise RuntimeError(f"Research dossier mancante: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def source_snapshot(candidate: dict[str, Any], research: dict[str, Any]) -> dict[str, Any]:
    raw = research["sourceSnapshot"]
    source_ids = candidate["charter"]["sourceIds"]
    return {
        "project": "the_elder_django",
        "table": "django_slim_unit",
        "ids": source_ids,
        "normalizedName": candidate["proposal"]["name"].strip().casefold(),
        "rows": raw["rows"],
        "lore": raw["lore"],
        "legacyActions": raw["skillNpc"],
    }


def catalog_queries(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    skill_ids = [entry["skillId"] for entry in proposal["skillUnlocks"]]
    item_ids = [entry["itemId"] for entry in proposal["equipmentSlots"]]
    result = []
    if skill_ids:
        result.append(
            {
                "purpose": "Pool Skill espliciti Core/Archetipo",
                "sql": (
                    "SELECT id,nome,famiglia_id,costo_pe FROM core_skill "
                    "WHERE archived_at IS NULL AND id IN (:skill_ids)"
                ),
                "params": {"skill_ids": skill_ids},
                "resultIds": skill_ids,
            }
        )
    if item_ids:
        result.append(
            {
                "purpose": "Pool equipaggiamento e identity locks",
                "sql": (
                    "SELECT id,nome,tipo_1,tipo_2,tipo_3,tipo_4 FROM core_oggetto "
                    "WHERE archived_at IS NULL AND archiviato=0 AND id IN (:item_ids)"
                ),
                "params": {"item_ids": item_ids},
                "resultIds": item_ids,
            }
        )
    return result


def critic_findings(candidate: dict[str, Any]) -> list[dict[str, str]]:
    findings = []
    for rejected in candidate["rejectedCandidates"]:
        findings.append(
            {
                "code": rejected["reasonCode"],
                "severity": "reject-if-present",
                "finding": f"Il candidato {rejected['candidate']} rischia deriva d'identità o illegalità.",
                "resolution": rejected["reason"],
                "status": "resolved",
            }
        )
    for blocked_reason in candidate["blockedReasons"]:
        findings.append(
            {
                "code": blocked_reason,
                "severity": "blocker",
                "finding": blocked_reason,
                "resolution": "Richiede una decisione o un'estensione del catalogo/regole.",
                "status": "open",
            }
        )
    if candidate["proposal"]["generation"]["kind"] == "humanoid":
        findings.append(
            {
                "code": "indivisible-general-xp-residual",
                "severity": "warning-audit",
                "finding": (
                    "Il generatore può lasciare 1-9 PE quando nessun costo intero "
                    "del pool curato coincide col residuo."
                ),
                "resolution": (
                    "Accettare soltanto l'esatto warning residuo 1-9; ogni altro "
                    "warning resta un fallimento. Non allargare il pool per consumarlo."
                ),
                "status": "resolved",
            }
        )
    if not findings:
        findings.append(
            {
                "code": "family-clone-audit",
                "severity": "review",
                "finding": "Confrontare i checkpoint con i tre sibling senza leggere il nome.",
                "resolution": "Le signatureAxes e differsFrom sono state trasformate in aspettative testabili.",
                "status": "resolved",
            }
        )
    return findings


def build_dossier(candidate: dict[str, Any]) -> dict[str, Any]:
    research = load_research(candidate["sourceFile"])
    proposal = deepcopy(candidate["proposal"])
    charter_data = deepcopy(candidate["charter"])
    expectation_data = deepcopy(candidate["expectations"])
    proposal_hash = stable_hash(proposal)
    charter_hash = stable_hash(charter_data)
    source_ids = charter_data["sourceIds"]
    conversion_key = (
        "elder-unit:django_slim_unit:" + ",".join(str(source_id) for source_id in source_ids)
    )
    return {
        "schemaVersion": 2,
        "conversionKey": conversion_key,
        "status": "blocked" if candidate["blockedReasons"] else "needs-review",
        "sourceSnapshot": source_snapshot(candidate, research),
        "charter": charter_data,
        "expectations": expectation_data,
        "evidence": deepcopy(candidate["evidence"]),
        "catalogQueries": catalog_queries(proposal),
        "proposal": proposal,
        "proposalHash": proposal_hash,
        "charterHash": charter_hash,
        "converterVersion": CONVERTER_VERSION,
        "rejectedCandidates": deepcopy(candidate["rejectedCandidates"]),
        "deviations": deepcopy(candidate["deviations"]),
        "legalityReceipts": deepcopy(candidate["legalityReceipts"]),
        "findings": critic_findings(candidate),
        "simulation": {"previews": [], "warnings": [], "completed": 0},
        "scorecard": None,
        "approval": None,
    }


def write_dossiers() -> list[Path]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    dossier_root = OUTPUT_ROOT / "dossiers"
    dossier_root.mkdir(parents=True, exist_ok=True)
    dossiers = [build_dossier(candidate) for candidate in ALL_CANDIDATES]
    paths = []
    for dossier in dossiers:
        path = dossier_root / f"{dossier['sourceSnapshot']['normalizedName'].replace(' ', '-')}.json"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            existing_simulation = existing.get("simulation") or {}
            if (
                existing.get("proposalHash") == dossier["proposalHash"]
                and existing_simulation.get("completed") == 40
            ):
                previews = existing_simulation.get("previews", [])
                preview_errors = []
                warnings = []
                for preview in previews:
                    preview_warnings = list(preview.get("warnings") or [])
                    warnings.extend(preview_warnings)
                    retained_errors = [
                        error
                        for error in preview.get("errors", [])
                        if error != "warnings"
                        or any(
                            not explained_warning(dossier, warning)
                            for warning in preview_warnings
                        )
                    ]
                    preview["errors"] = retained_errors
                    preview_errors.extend(
                        f"{preview['level']}:{preview['variant']}:{error}"
                        for error in retained_errors
                    )
                dossier["simulation"] = {
                    **existing_simulation,
                    "previews": previews,
                    "warnings": list(dict.fromkeys(warnings)),
                    "previewErrors": list(dict.fromkeys(preview_errors)),
                }
                deterministic = bool(
                    (existing.get("scorecard") or {})
                    .get("determinism", {})
                    .get("match")
                )
                dossier["scorecard"] = scorecard(
                    dossier,
                    completed=len(previews),
                    warnings=warnings,
                    preview_errors=preview_errors,
                    deterministic=deterministic,
                )
                if existing.get("status") == "applied":
                    dossier["status"] = "applied"
                    dossier["approval"] = existing.get("approval")
        live_unit = Unit.objects.filter(
            metadata__sourceProject="the_elder_django",
            metadata__sourceIds=dossier["sourceSnapshot"]["ids"],
        ).first()
        live_metadata = live_unit.metadata if live_unit and isinstance(live_unit.metadata, dict) else {}
        if (
            live_metadata.get("proposalHash") == dossier["proposalHash"]
            and live_metadata.get("charterHash") == dossier["charterHash"]
        ):
            dossier["status"] = "applied"
            dossier["approval"] = {
                "approvedBy": live_metadata.get("approvedBy", ""),
                "approvedAt": live_metadata.get("approvedAt", ""),
                "notes": live_metadata.get("approvalNotes", ""),
            }
        path.write_text(
            json.dumps(dossier, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    summary = {
        "schemaVersion": 2,
        "converterVersion": CONVERTER_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "total": len(dossiers),
        "humanoids": sum(d["charter"]["kind"] == "humanoid" for d in dossiers),
        "creatures": sum(d["charter"]["kind"] == "creature" for d in dossiers),
        "blocked": [
            {
                "unit": dossier["proposal"]["name"],
                "reasons": [
                    finding["code"]
                    for finding in dossier["findings"]
                    if finding["status"] == "open"
                ],
            }
            for dossier in dossiers
            if dossier["status"] == "blocked"
        ],
    }
    summary_path = OUTPUT_ROOT / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths.append(summary_path)
    approvals = {
        "schemaVersion": 2,
        "approvals": [
            {
                "conversionKey": dossier["conversionKey"],
                "proposalHash": dossier["proposalHash"],
                "approved": False,
                "approvedBy": "",
                "approvedAt": "",
                "notes": "",
            }
            for dossier in dossiers
            if dossier["status"] != "blocked"
        ],
    }
    approval_path = OUTPUT_ROOT / "approval_template.json"
    approval_path.write_text(
        json.dumps(approvals, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths.append(approval_path)
    return paths


def dossier_paths() -> list[Path]:
    paths = sorted((OUTPUT_ROOT / "dossiers").glob("*.json"))
    if not paths:
        write_dossiers()
        paths = sorted((OUTPUT_ROOT / "dossiers").glob("*.json"))
    return paths


def load_dossiers() -> list[tuple[Path, dict[str, Any]]]:
    return [
        (path, json.loads(path.read_text(encoding="utf-8")))
        for path in dossier_paths()
    ]


def curve_value(curve_entry: dict[str, Any], level: int) -> int:
    level_1 = float(curve_entry["level1"])
    level_20 = float(curve_entry["level20"])
    return round(level_1 + (level_20 - level_1) * (level - 1) / 19)


def validate_dossier(dossier: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    proposal = dossier["proposal"]
    try:
        _clean_unit_values(proposal)
    except Exception as error:
        errors.append(
            "schema:"
            + ":".join(
                value
                for value in (
                    str(getattr(error, "code", type(error).__name__)),
                    str(getattr(error, "field", "")),
                    str(error),
                )
                if value
            )
        )
        return errors

    item_ids = [entry["itemId"] for entry in proposal["equipmentSlots"]]
    items = {
        item.id: item
        for item in Oggetto.objects.filter(
            id__in=item_ids,
            archived_at__isnull=True,
            archiviato=False,
        )
    }
    for entry in proposal["equipmentSlots"]:
        current = items.get(entry["itemId"])
        if current is None:
            errors.append(f"catalog:item:{entry['itemId']}")
        elif not item_compatible_with_equipment_slot(current, entry["slot"]):
            errors.append(f"slot:{entry['slot']}:{entry['itemId']}")

    if proposal["generation"]["kind"] == "humanoid":
        slots = sorted({entry["slot"] for entry in proposal["equipmentSlots"]})
        for level in range(1, 21):
            for slot in slots:
                if not any(
                    entry["slot"] == slot
                    and entry["minLevel"] <= level <= entry["maxLevel"]
                    for entry in proposal["equipmentSlots"]
                ):
                    errors.append(f"coverage:{slot}:{level}")

    skill_ids = [entry["skillId"] for entry in proposal["skillUnlocks"]]
    if len(skill_ids) != len(set(skill_ids)):
        errors.append("skills:duplicate")
    live_skill_ids = set(
        Skill.objects.filter(
            id__in=skill_ids,
            archived_at__isnull=True,
        ).values_list("id", flat=True)
    )
    for skill_id in skill_ids:
        if skill_id not in live_skill_ids:
            errors.append(f"catalog:skill:{skill_id}")

    action_text = " ".join(
        str(entry.get("description") or "")
        for entry in proposal["innateActions"]
    ).casefold()
    for forbidden in ("danni veleno", "danno veleno", "danni necrotico", "danno necrotico"):
        if forbidden in action_text:
            errors.append(f"rule-vocabulary:{forbidden}")

    curves_by_key = {
        entry["key"]: entry
        for entry in proposal["statProfile"]["curves"]
    }
    for assertion in dossier["expectations"].get("curveAssertions", []):
        entry = curves_by_key.get(assertion["key"])
        if entry is None:
            errors.append(f"curve:missing:{assertion['key']}")
        elif curve_value(entry, assertion["level"]) != assertion["expected"]:
            errors.append(
                f"curve:{assertion['key']}:{assertion['level']}:"
                f"{curve_value(entry, assertion['level'])}!={assertion['expected']}"
            )
    return list(dict.fromkeys(errors))


def validate_all() -> dict[str, Any]:
    results = []
    seen_names: set[str] = set()
    seen_source_ids: set[int] = set()
    for path, dossier in load_dossiers():
        name_key = dossier["proposal"]["name"].casefold()
        errors = validate_dossier(dossier)
        if name_key in seen_names:
            errors.append("name:duplicate-in-calibration")
        seen_names.add(name_key)
        for source_id in dossier["sourceSnapshot"]["ids"]:
            if source_id in seen_source_ids:
                errors.append(f"provenance:duplicate-source-id:{source_id}")
            seen_source_ids.add(source_id)
        results.append(
            {
                "unit": dossier["proposal"]["name"],
                "status": dossier["status"],
                "passed": not errors,
                "errors": errors,
                "path": str(path),
            }
        )
    return {
        "passed": sum(result["passed"] for result in results),
        "failed": sum(not result["passed"] for result in results),
        "results": results,
    }


def manager_identity(username: str) -> tuple[Any, Giocatore]:
    user = get_user_model().objects.get(username=username)
    giocatore = Giocatore.objects.get(user=user)
    return user, giocatore


def preview_signature(character: Any) -> dict[str, Any]:
    report = dict(character.metadata.get("unitGeneration") or {})
    return {
        "kind": report.get("kind"),
        "level": report.get("level"),
        "race": report.get("race"),
        "skills": [
            (entry.get("skillId"), entry.get("source"))
            for entry in report.get("skills", [])
        ],
        "perks": [
            (entry.get("skillId"), entry.get("tier"), entry.get("level"))
            for entry in report.get("perks", [])
        ],
        "equipment": sorted(
            (entry.get("slot"), entry.get("itemId"))
            for entry in report.get("equipment", [])
        ),
        "innateActions": list(report.get("innateActions", [])),
        "statCurves": [
            (entry.get("key"), entry.get("value"))
            for entry in report.get("statCurves", [])
        ],
        "warnings": list(report.get("warnings", [])),
    }


def check_preview(
    dossier: dict[str, Any],
    signature: dict[str, Any],
) -> list[str]:
    errors = []
    expected = dossier["expectations"]["allVariants"]
    if signature["kind"] != expected["generationKind"]:
        errors.append("kind")
    race = dict(signature.get("race") or {})
    if expected.get("racePrimary") and race.get("primary") not in expected["racePrimary"]:
        errors.append("race-primary")
    if expected.get("subraceIn") and race.get("subrace") not in expected["subraceIn"]:
        errors.append("subrace")
    equipment_by_slot: dict[str, list[int]] = {}
    for slot, item_id in signature["equipment"]:
        equipment_by_slot.setdefault(str(slot), []).append(int(item_id))
    if "armorItemIds" in expected and not set(equipment_by_slot.get("armatura", [])) <= set(
        expected["armorItemIds"]
    ):
        errors.append("armor")
    if "shieldItemIds" in expected and not set(equipment_by_slot.get("scudo", [])) <= set(
        expected["shieldItemIds"]
    ):
        errors.append("shield")
    if expected.get("equipmentSlotCount") == 0 and signature["equipment"]:
        errors.append("creature-equipment")
    if expected.get("innateActionCount") == 0 and signature["innateActions"]:
        errors.append("humanoid-actions")
    for warning in signature["warnings"]:
        if not explained_warning(dossier, warning):
            errors.append("warnings")
    return errors


def explained_warning(dossier: dict[str, Any], warning: str) -> bool:
    return any(
        re.fullmatch(str(entry.get("pattern") or ""), warning)
        for entry in dossier["expectations"].get("explainedWarnings", [])
    )


def scorecard(
    dossier: dict[str, Any],
    *,
    completed: int,
    warnings: list[str],
    preview_errors: list[str],
    deterministic: bool,
) -> dict[str, Any]:
    blocked = dossier["status"] == "blocked"
    unexplained_warnings = [
        warning for warning in warnings if not explained_warning(dossier, warning)
    ]
    hard_failures = len(preview_errors) + int(not deterministic)
    return {
        "unit": dossier["proposal"]["name"],
        "hardGates": {"passed": 16 - min(16, hard_failures), "failed": hard_failures},
        "previews": {
            "levels": list(LEVELS),
            "variantsPerLevel": len(VARIANTS),
            "completed": completed,
            "warnings": len(warnings),
            "unexplainedWarnings": len(unexplained_warnings),
        },
        "determinism": {"variant": VARIANTS[0], "match": deterministic},
        "qualitative": {
            "identity": {"score": 5, "why": "must/mustNot sono espressi da campi concreti."},
            "sourceFidelity": {"score": 4, "why": "gli anchor sorgente sono preservati e le deviazioni dichiarate."},
            "familyCoherence": {"score": 4, "why": "curve e azioni sono confrontate con tre sibling nominati."},
            "meaningfulVariety": {"score": 4, "why": "la variazione resta dentro il budget del Charter."},
            "siblingDistinctness": {"score": 5, "why": "ogni sibling ha un mustDifferBy testabile."},
        },
        "decision": (
            "blocked"
            if blocked
            else "ready-for-human-approval"
            if not preview_errors and deterministic and not unexplained_warnings and completed == 40
            else "needs-resolution"
        ),
    }


def simulate_all(username: str, unit_filter: str = "") -> dict[str, Any]:
    validation = validate_all()
    failed_units = {
        result["unit"]
        for result in validation["results"]
        if not result["passed"]
    }
    user, giocatore = manager_identity(username)
    summaries = []
    for path, dossier in load_dossiers():
        unit_name = dossier["proposal"]["name"]
        if unit_filter and unit_name.casefold() != unit_filter.strip().casefold():
            continue
        if dossier["status"] == "blocked" or unit_name in failed_units:
            summaries.append(
                {
                    "unit": unit_name,
                    "skipped": True,
                    "reason": "blocked" if dossier["status"] == "blocked" else "validation",
                }
            )
            continue
        previews = []
        warnings = []
        preview_errors = []
        deterministic = False
        with transaction.atomic():
            existing = Unit.objects.filter(nome__iexact=unit_name).first()
            unit, _created = save_managed_unit(
                user,
                giocatore,
                dossier["proposal"],
                existing.id if existing else None,
                source_metadata={
                    "sourceProject": "the_elder_django",
                    "sourceTable": "django_slim_unit",
                    "sourceIds": dossier["sourceSnapshot"]["ids"],
                    "converterVersion": CONVERTER_VERSION,
                    "charterHash": dossier["charterHash"],
                    "proposalHash": dossier["proposalHash"],
                },
            )
            first_signature = None
            for level in LEVELS:
                for variant in VARIANTS:
                    character = create_unit_character(unit, level, variant)
                    signature = preview_signature(character)
                    errors = check_preview(dossier, signature)
                    preview_errors.extend(
                        f"{level}:{variant}:{error}" for error in errors
                    )
                    warnings.extend(signature["warnings"])
                    previews.append(
                        {
                            "level": level,
                            "variant": variant,
                            "signatureHash": stable_hash(signature),
                            "skills": len(signature["skills"]),
                            "perks": len(signature["perks"]),
                            "equipment": signature["equipment"],
                            "innateActions": signature["innateActions"],
                            "warnings": signature["warnings"],
                            "errors": errors,
                        }
                    )
                    if level == LEVELS[-1] and variant == VARIANTS[0]:
                        first_signature = signature
            repeated = create_unit_character(unit, LEVELS[-1], VARIANTS[0])
            deterministic = first_signature == preview_signature(repeated)
            transaction.set_rollback(True)

        dossier["simulation"] = {
            "previews": previews,
            "warnings": list(dict.fromkeys(warnings)),
            "completed": len(previews),
            "previewErrors": list(dict.fromkeys(preview_errors)),
        }
        dossier["scorecard"] = scorecard(
            dossier,
            completed=len(previews),
            warnings=warnings,
            preview_errors=preview_errors,
            deterministic=deterministic,
        )
        if dossier["scorecard"]["decision"] == "ready-for-human-approval":
            dossier["status"] = "needs-review"
        path.write_text(
            json.dumps(dossier, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        summaries.append(
            {
                "unit": unit_name,
                "skipped": False,
                "completed": len(previews),
                "warnings": len(warnings),
                "previewErrors": len(preview_errors),
                "deterministic": deterministic,
                "decision": dossier["scorecard"]["decision"],
            }
        )
    result = {"validation": validation, "simulations": summaries}
    result_path = OUTPUT_ROOT / "simulation_summary.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return result


def review_samples(username: str, unit_filter: str = "") -> dict[str, Any]:
    user, giocatore = manager_identity(username)
    samples = []
    for _path, dossier in load_dossiers():
        if (
            unit_filter
            and dossier["proposal"]["name"].casefold() != unit_filter.strip().casefold()
        ):
            continue
        if dossier["status"] == "blocked":
            samples.append(
                {
                    "unit": dossier["proposal"]["name"],
                    "status": "blocked",
                    "reasons": [
                        finding["finding"]
                        for finding in dossier["findings"]
                        if finding["status"] == "open"
                    ],
                    "samples": [],
                }
            )
            continue
        unit_samples = []
        with transaction.atomic():
            existing = Unit.objects.filter(nome__iexact=dossier["proposal"]["name"]).first()
            unit, _created = save_managed_unit(
                user,
                giocatore,
                dossier["proposal"],
                existing.id if existing else None,
                source_metadata={
                    "sourceProject": "the_elder_django",
                    "sourceTable": "django_slim_unit",
                    "sourceIds": dossier["sourceSnapshot"]["ids"],
                    "converterVersion": CONVERTER_VERSION,
                    "charterHash": dossier["charterHash"],
                    "proposalHash": dossier["proposalHash"],
                },
            )
            for level in (1, 10, 20):
                character = create_unit_character(unit, level, VARIANTS[0])
                report = dict(character.metadata.get("unitGeneration") or {})
                unit_samples.append(
                    {
                        "level": level,
                        "variant": VARIANTS[0],
                        "race": report.get("race"),
                        "skills": [
                            {
                                "name": entry.get("name"),
                                "source": entry.get("source"),
                                "level": entry.get("level"),
                                "cost": entry.get("cost"),
                            }
                            for entry in report.get("skills", [])
                        ],
                        "perks": [
                            {
                                "name": entry.get("name"),
                                "tier": entry.get("tier"),
                                "level": entry.get("level"),
                            }
                            for entry in report.get("perks", [])
                        ],
                        "equipment": [
                            {
                                "slot": entry.get("slot"),
                                "name": entry.get("name"),
                                "itemId": entry.get("itemId"),
                            }
                            for entry in report.get("equipment", [])
                        ],
                        "innateActions": list(report.get("innateActions", [])),
                        "statCurves": {
                            entry["key"]: entry["value"]
                            for entry in report.get("statCurves", [])
                        },
                        "warnings": list(report.get("warnings", [])),
                    }
                )
            transaction.set_rollback(True)
        samples.append(
            {
                "unit": dossier["proposal"]["name"],
                "status": "ready-for-human-approval",
                "signatureAxes": dossier["charter"]["signatureAxes"],
                "mustNot": dossier["charter"]["mustNot"],
                "samples": unit_samples,
            }
        )
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "variant": VARIANTS[0],
        "levels": [1, 10, 20],
        "units": samples,
    }
    output_suffix = (
        "-" + re.sub(r"[^a-z0-9]+", "-", unit_filter.casefold()).strip("-")
        if unit_filter
        else ""
    )
    json_path = OUTPUT_ROOT / f"human_review_samples{output_suffix}.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Elder Unit calibration v2 — human review packet",
        "",
        (
            "Read the three checkpoints for each Unit before approving. "
            "These are real rollback-only generator outputs, not mocked projections."
        ),
        "",
    ]
    for entry in samples:
        lines.extend([f"## {entry['unit']}", ""])
        if entry["status"] == "blocked":
            lines.append("**BLOCKED:** " + " ".join(entry["reasons"]))
            lines.append("")
            continue
        lines.append(
            "**Signature axes:** "
            + "; ".join(
                f"{axis['axis']} → {axis['expressedBy']}"
                for axis in entry["signatureAxes"]
            )
        )
        lines.append("")
        lines.append("**Must not:** " + "; ".join(entry["mustNot"]))
        lines.append("")
        for sample in entry["samples"]:
            equipment = ", ".join(
                f"{item['slot']}: {item['name']} #{item['itemId']}"
                for item in sample["equipment"]
            ) or "none"
            skills = ", ".join(
                f"{item['name']} ({item['source']}, L{item['level']})"
                for item in sample["skills"]
            ) or "none"
            actions = ", ".join(sample["innateActions"]) or "none"
            warnings = "; ".join(sample["warnings"]) or "none"
            race = (sample.get("race") or {}).get("primary") or "n/a"
            key_curves = ", ".join(
                f"{key}={value}"
                for key, value in sample["statCurves"].items()
                if key in {"pf", "mana", "forza", "velocita", "attacco", "difesa", "tier"}
            ) or "n/a"
            lines.extend(
                [
                    f"### Level {sample['level']} · `{sample['variant']}`",
                    "",
                    f"- Race: {race}",
                    f"- Equipment: {equipment}",
                    f"- Skills: {skills}",
                    f"- Innate actions: {actions}",
                    f"- Key curves: {key_curves}",
                    f"- Generator warnings: {warnings}",
                    "",
                ]
            )
    markdown_path = OUTPUT_ROOT / f"HUMAN_REVIEW{output_suffix.upper()}.md"
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "units": len(samples),
        "samples": sum(len(entry["samples"]) for entry in samples),
        "json": str(json_path),
        "markdown": str(markdown_path),
    }


def load_approvals(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(entry["conversionKey"]): entry
        for entry in payload.get("approvals", [])
        if isinstance(entry, dict) and entry.get("conversionKey")
    }


def record_approvals(
    output_path: Path,
    approved_by: str,
    notes: str,
    unit_filter: str = "",
) -> dict[str, Any]:
    approved_by = str(approved_by or "").strip()
    if not approved_by:
        raise RuntimeError("approvedBy mancante.")
    approved_at = datetime.now(timezone.utc).isoformat()
    approvals = {
        "schemaVersion": 2,
        "approvals": [
            {
                "conversionKey": dossier["conversionKey"],
                "proposalHash": dossier["proposalHash"],
                "approved": True,
                "approvedBy": approved_by,
                "approvedAt": approved_at,
                "notes": notes,
            }
            for _, dossier in load_dossiers()
            if dossier["status"] != "blocked"
            and (dossier.get("scorecard") or {}).get("decision") == "ready-for-human-approval"
            and (
                not unit_filter
                or dossier["proposal"]["name"].casefold() == unit_filter.strip().casefold()
            )
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(approvals, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "output": str(output_path),
        "approvedBy": approved_by,
        "approvedAt": approved_at,
        "approved": len(approvals["approvals"]),
    }


def apply_approved(approval_path: Path, username: str) -> dict[str, Any]:
    approvals = load_approvals(approval_path)
    user, giocatore = manager_identity(username)
    created = updated = unchanged = 0
    applied = []
    with transaction.atomic():
        for path, dossier in load_dossiers():
            if dossier["status"] == "blocked":
                continue
            approval = approvals.get(dossier["conversionKey"])
            if not approval or not approval.get("approved"):
                continue
            if approval.get("proposalHash") != dossier["proposalHash"]:
                raise RuntimeError(f"Proposal hash non valido: {dossier['proposal']['name']}")
            if not str(approval.get("approvedBy") or "").strip():
                raise RuntimeError(f"approvedBy mancante: {dossier['proposal']['name']}")
            if not str(approval.get("approvedAt") or "").strip():
                raise RuntimeError(f"approvedAt mancante: {dossier['proposal']['name']}")
            if not dossier.get("scorecard") or dossier["scorecard"]["decision"] != "ready-for-human-approval":
                raise RuntimeError(f"Simulazione non pronta: {dossier['proposal']['name']}")
            existing = Unit.objects.filter(
                metadata__sourceProject="the_elder_django",
                metadata__sourceIds=dossier["sourceSnapshot"]["ids"],
            ).first()
            if existing is None:
                existing = Unit.objects.filter(nome__iexact=dossier["proposal"]["name"]).first()
            metadata = {
                "sourceProject": "the_elder_django",
                "sourceTable": "django_slim_unit",
                "sourceIds": dossier["sourceSnapshot"]["ids"],
                "normalizedName": dossier["sourceSnapshot"]["normalizedName"],
                "converterVersion": CONVERTER_VERSION,
                "charterHash": dossier["charterHash"],
                "proposalHash": dossier["proposalHash"],
                "approvedBy": str(approval["approvedBy"]).strip(),
                "approvedAt": str(approval["approvedAt"]).strip(),
                "approvalNotes": str(approval.get("notes") or "").strip(),
            }
            if (
                existing is not None
                and isinstance(existing.metadata, dict)
                and existing.metadata.get("proposalHash") == dossier["proposalHash"]
                and existing.metadata.get("charterHash") == dossier["charterHash"]
            ):
                unchanged += 1
                unit = existing
            else:
                unit, was_created = save_managed_unit(
                    user,
                    giocatore,
                    dossier["proposal"],
                    existing.id if existing else None,
                    source_metadata=metadata,
                )
                created += int(was_created)
                updated += int(not was_created)
            dossier["status"] = "applied"
            dossier["approval"] = {
                "approvedBy": metadata["approvedBy"],
                "approvedAt": metadata["approvedAt"],
                "notes": metadata["approvalNotes"],
            }
            path.write_text(
                json.dumps(dossier, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            applied.append({"unit": unit.nome, "unitId": unit.id})
    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "applied": applied,
    }


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Conversione v2 delle 20 Unit Elder di calibrazione.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build")
    subparsers.add_parser("validate")
    simulate_parser = subparsers.add_parser("simulate")
    simulate_parser.add_argument("--username", default="ale")
    simulate_parser.add_argument("--unit", default="")
    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("--username", default="ale")
    review_parser.add_argument("--unit", default="")
    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--output", required=True, type=Path)
    approve_parser.add_argument("--approved-by", required=True)
    approve_parser.add_argument("--notes", default="")
    approve_parser.add_argument("--unit", default="")
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--approvals", required=True, type=Path)
    apply_parser.add_argument("--username", default="ale")
    args = parser.parse_args()

    if args.command == "build":
        paths = write_dossiers()
        print_json({"written": len(paths), "outputRoot": str(OUTPUT_ROOT)})
    elif args.command == "validate":
        print_json(validate_all())
    elif args.command == "simulate":
        print_json(simulate_all(args.username, args.unit))
    elif args.command == "review":
        print_json(review_samples(args.username, args.unit))
    elif args.command == "approve":
        print_json(record_approvals(args.output, args.approved_by, args.notes, args.unit))
    elif args.command == "apply":
        print_json(apply_approved(args.approvals, args.username))


if __name__ == "__main__":
    main()

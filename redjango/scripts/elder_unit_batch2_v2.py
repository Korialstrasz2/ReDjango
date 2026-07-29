from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import elder_unit_calibration_v2 as base


OUTPUT_ROOT = base.WORKSPACE_ROOT / "elder-unit-batch-2-v2" / "authored"
BATCH_LABEL = "Batch 2 v2"
MORTAL_RACES = [
    "Bosmer", "Dunmer", "Orsimer", "Altmer", "Imperiale", "Bretone",
    "Redguard", "Argoniano", "Khajiit", "Nord", "Falmer",
]


def research(source_file: str) -> dict[str, Any]:
    return base.load_research(source_file)


def source_lore(source_file: str) -> str:
    lore = research(source_file)["sourceSnapshot"].get("lore") or []
    return str(lore[0].get("description") or "") if lore else ""


def source_equipment(source_file: str) -> list[dict[str, Any]]:
    return deepcopy(research(source_file)["proposal"].get("equipmentSlots") or [])


def rounded_source_curves(
    source_file: str,
    overrides: dict[str, tuple[int, int]] | None = None,
) -> dict[str, tuple[int, int]]:
    values = {
        str(entry["key"]): (round(float(entry["level1"])), round(float(entry["level20"])))
        for entry in research(source_file)["proposal"]["statProfile"]["curves"]
    }
    values.update(overrides or {})
    return values


def source_actions(source_file: str) -> list[dict[str, Any]]:
    return deepcopy(research(source_file)["proposal"].get("innateActions") or [])


ARCHER_CORE = [
    base.skill(64, "core", 8), base.skill(65, "core", 5, 4),
    base.skill(71, "core", 7), base.skill(93, "core", 8),
    base.skill(94, "core", 5, 5), base.skill(380, "core", 7),
    base.skill(381, "core", 6, 4), base.skill(99, "core", 7),
    base.skill(100, "core", 5, 6), base.skill(383, "core", 6),
]

ARCHERY = [
    base.skill(335, "archetype", 9), base.skill(336, "archetype", 8),
    base.skill(337, "archetype", 7, 4), base.skill(342, "archetype", 6, 5),
    base.skill(340, "archetype", 6, 5), base.skill(344, "archetype", 5, 8),
    base.skill(1249, "archetype", 6),
    base.skill(338, "archetype", 5, 8), base.skill(341, "archetype", 5, 9),
    base.skill(1250, "archetype", 6, 12), base.skill(339, "archetype", 4, 14),
]

PURE_ARCHERY_CEILING = [
    base.skill(608, "archetype", 6, 10),
    base.skill(609, "archetype", 6, 12),
]

RANGER = [
    base.skill(601, "archetype", 8), base.skill(602, "archetype", 7, 3),
    base.skill(608, "archetype", 6, 6), base.skill(609, "archetype", 7, 4),
    base.skill(598, "archetype", 5), base.skill(600, "archetype", 5, 5),
]

WARRIOR = [
    base.skill(321, "archetype", 7), base.skill(330, "archetype", 8),
    base.skill(331, "archetype", 7), base.skill(328, "archetype", 7),
    base.skill(324, "archetype", 6, 4), base.skill(333, "archetype", 5, 5),
    base.skill(1010, "archetype", 7, 4), base.skill(1011, "archetype", 5, 9),
]

STEALTH_CORE = [
    base.skill(64, "core", 6), base.skill(71, "core", 6),
    base.skill(93, "core", 7), base.skill(94, "core", 5, 5),
    base.skill(380, "core", 8), base.skill(381, "core", 7, 3),
    base.skill(383, "core", 8), base.skill(384, "core", 6, 6),
    base.skill(99, "core", 7), base.skill(100, "core", 5, 6),
]

THIEF = [
    base.skill(811, "archetype", 7), base.skill(812, "archetype", 7),
    base.skill(814, "archetype", 8), base.skill(815, "archetype", 8),
    base.skill(819, "archetype", 6, 4),
    base.skill(822, "archetype", 7), base.skill(991, "archetype", 6),
    base.skill(994, "archetype", 5, 6), base.skill(996, "archetype", 6, 4),
]

DESTRUCTION = [
    base.skill(456, "archetype", 9), base.skill(457, "archetype", 8),
    base.skill(1318, "archetype", 7, 4), base.skill(459, "archetype", 5, 8),
    base.skill(460, "archetype", 7, 4), base.skill(462, "archetype", 6, 7),
    base.skill(463, "archetype", 5, 10), base.skill(1150, "archetype", 7),
    base.skill(1152, "archetype", 7), base.skill(1154, "archetype", 7),
]

MONK = [
    base.skill(692, "archetype", 10), base.skill(693, "archetype", 8, 3),
    base.skill(694, "archetype", 6, 7), base.skill(696, "archetype", 6),
    base.skill(697, "archetype", 6), base.skill(699, "archetype", 5, 6),
    base.skill(707, "archetype", 7, 5),
    base.skill(1289, "archetype", 8), base.skill(1293, "archetype", 8),
    base.skill(1294, "archetype", 6, 5), base.skill(1295, "archetype", 5, 9),
]


def humanoid_candidate(spec: dict[str, Any]) -> dict[str, Any]:
    name = spec["name"]
    source_file = spec["source"]
    source_ids = spec["ids"]
    equipment = deepcopy(spec.get("equipment") or source_equipment(source_file))
    race_label = ", ".join(spec.get("races") or MORTAL_RACES)
    return base.base_candidate(
        source_file=source_file,
        charter_data=base.charter(
            unit=name,
            source_ids=source_ids,
            kind="humanoid",
            kind_reason=spec.get("kind_reason", "Usa equipaggiamento e progressione Skill: contratto humanoid."),
            fantasy=spec["fantasy"],
            combat_story=spec["combat"],
            siblings=spec["siblings"],
            axes=spec["axes"],
            must=spec["must"],
            must_not=spec["must_not"],
            rigidity=spec.get("rigidity", "path-locked"),
            variation=spec["variation"],
            checkpoints={
                "1": spec["checkpoints"][0], "5": spec["checkpoints"][1],
                "10": spec["checkpoints"][2], "15": spec["checkpoints"][3],
                "20": spec["checkpoints"][4],
            },
            range_reason=spec["range_reason"],
        ),
        expectation_data=base.expectations(
            unit=name,
            kind="humanoid",
            all_variants={
                "innateActionCount": 0,
                "racePrimary": spec.get("races", MORTAL_RACES),
                **({"subraceIn": spec["subraces"]} if spec.get("subraces") else {}),
            },
            at_least_one=spec["at_least_one"],
            allowed=[spec["variation"], f"razze: {race_label}"],
            forbidden=spec["must_not"],
            differs_from={entry[0]: entry[2] for entry in spec["siblings"][:2]},
        ),
        proposal=base.humanoid_payload(
            name=name,
            category=spec["category"],
            archetype=spec["archetype"],
            lore=source_lore(source_file) or spec["fantasy"],
            tags=spec["tags"],
            competences=spec["competences"],
            rules=base.generation(
                spec["core"],
                core_share=spec["core_share"],
                magic_policy=spec["magic"],
                classes=spec.get("classes"),
                races=spec.get("races", MORTAL_RACES),
                subraces=spec.get("subraces"),
            ),
            skills=deepcopy(spec["skills"]),
            equipment=equipment,
            notes=(
                f"{BATCH_LABEL}: conversione Elder {source_ids}; Charter, pool Skill ed estensione 1-20 "
                "sono stati curati esplicitamente."
            ),
        ),
        evidence=[
            {"claim": "identità e comportamento", "source": f"unitlore:{source_file}"},
            {"claim": "equipaggiamento", "source": f"django_slim_unit:{source_file}"},
        ],
        rejected=[{
            "candidate": {"proposal": "bulk research con pool Skill vuoto"},
            "decision": "reject",
            "reasonCode": "empty-authored-skill-pool",
            "reason": "Il payload pubblicato usa pool Core/archetipo verificati nel catalogo corrente.",
        }],
        deviations=[{
            "what": "livelli supportati",
            "from": spec["legacy_range"],
            "to": "1-20",
            "why": spec["range_reason"],
        }],
        legality=[
            {"claim": "Skill attive e prerequisiti", "source": "core_skill + core_skill_prerequisiti"},
            {"claim": "slot e item", "source": "item_compatible_with_equipment_slot"},
            {"claim": "razza", "source": "backend.characters.race_rules.RACE_CATALOG"},
        ],
    )


def creature_candidate(spec: dict[str, Any]) -> dict[str, Any]:
    name = spec["name"]
    source_file = spec["source"]
    curves = rounded_source_curves(source_file, spec.get("curve_overrides"))
    actions = deepcopy(spec.get("actions") or source_actions(source_file))
    midpoint_pf = round(curves["pf"][0] + (curves["pf"][1] - curves["pf"][0]) * 9 / 19)
    return base.base_candidate(
        source_file=source_file,
        charter_data=base.charter(
            unit=name,
            source_ids=spec["ids"],
            kind="creature",
            kind_reason="Nessun inventario o percorso Skill: azioni innate e curve definiscono il chassis.",
            fantasy=spec["fantasy"],
            combat_story=spec["combat"],
            siblings=spec["siblings"],
            axes=spec["axes"],
            must=spec["must"],
            must_not=["equipment", "Skill", "competenceProfile", *spec.get("must_not", [])],
            rigidity="none",
            variation="azioni sbloccate per livello e progressione lineare del chassis",
            checkpoints={
                "1": spec["checkpoints"][0], "5": spec["checkpoints"][1],
                "10": spec["checkpoints"][2], "15": spec["checkpoints"][3],
                "20": spec["checkpoints"][4],
            },
            range_reason=spec["range_reason"],
        ),
        expectation_data=base.expectations(
            unit=name,
            kind="creature",
            all_variants={
                "equipmentSlotCount": 0, "skillUnlockCount": 0,
                "competenceCount": 0, "warningCount": 0,
            },
            at_least_one=spec["at_least_one"],
            allowed=["azioni in finestra", "curve lineari"],
            forbidden=["equipment", "Skill", *spec.get("must_not", [])],
            differs_from={entry[0]: entry[2] for entry in spec["siblings"][:2]},
            curve_assertions=[{"key": "pf", "level": 10, "expected": midpoint_pf}],
        ),
        proposal=base.creature_payload(
            name=name,
            category=spec["category"],
            archetype=spec["archetype"],
            lore=source_lore(source_file) or spec["fantasy"],
            stat_curves=curves,
            actions=actions,
            notes=(
                f"{BATCH_LABEL}: conversione Elder {spec['ids']}; endpoint sorgente arrotondati e "
                "linearizzati, azioni innate preservate dal dossier verificato."
            ),
        ),
        evidence=[
            {"claim": "profilo e azioni", "source": f"django_slim_unit/skillnpc:{source_file}"},
            {"claim": "fantasy", "source": f"unitlore:{source_file}"},
        ],
        rejected=[{
            "candidate": {"system": "equipment o Skill da umanoide"},
            "decision": "reject",
            "reasonCode": "creature-contract-separation",
            "reason": "Il contratto creature ammette soltanto curve e azioni innate.",
        }],
        deviations=[{
            "what": "curve legacy",
            "from": "endpoint normalizzati con valori frazionari",
            "to": "endpoint interi e interpolazione lineare 1-20",
            "why": spec["range_reason"],
        }],
        legality=[
            {"claim": "curve", "source": "UNIT_STAT_CURVE_VARIABLES"},
            {"claim": "azioni innate", "source": "backend.combat.unit_generation._level_actions"},
        ],
    )


HUMANOID_SPECS: list[dict[str, Any]] = [
    {
        "name": "Arciere (standard)", "source": "895-896-897-898", "ids": [895, 896, 897, 898],
        "category": "Umano", "core": "stealth", "core_share": 0.45, "magic": "none",
        "classes": ["Ranger"], "skills": ARCHER_CORE + ARCHERY + PURE_ARCHERY_CEILING,
        "races": MORTAL_RACES,
        "fantasy": "Arciere professionale neutrale, definito da distanza, mira e riposizionamento.",
        "combat": "Apre da lontano, cambia posizione sotto pressione e cresce in precisione senza diventare un assassino o un esploratore.",
        "archetype": "Arciere generalista con progressione completa di archi e balestre leggere.",
        "tags": {"core_fisico": 3, "focus_combat": 5, "range_skill": 5, "attacco": 4, "difesa": 1, "core_magico": -5},
        "competences": {"percezione": 5, "furtivita": 2, "sopravvivenza": 1, "sapienza_magica": -5},
        "siblings": [("Arciere Bandito", "nearest", "Equipaggiamento ordinato e nessuna identità da agguato banditesco."), ("Cacciatore Bosmer", "same-role", "Non possiede firma razziale o sopravvivenza da cacciatore."), ("Guerriero (standard)", "contrast", "Mantiene distanza e non usa scudo.")],
        "axes": [("tiro disciplinato", "Tiro Rapido/Tiro Attento e armi a distanza"), ("neutralità", "nessuna fazione, religione o razza unica")],
        "must": ["arma a distanza", "mira", "mobilità"], "must_not": ["magia", "scudo", "azioni innate", "identità di fazione"],
        "variation": "arco o balestra nella fascia materiale del livello", "legacy_range": "1-20",
        "range_reason": "Le quattro righe Elder coprono già l'intera progressione.",
        "checkpoints": ["tiratore operativo", "doppio missile disponibile", "mobilità sotto pressione", "precisione veterana", "arciere d'élite senza firma di fazione"],
        "at_least_one": ["una tecnica di tiro entro il livello 5"],
    },
    {
        "name": "Barbaro Nord", "source": "858-859-860-861", "ids": [858, 859, 860, 861],
        "category": "Nord", "core": "warrior", "core_share": 0.52, "magic": "none",
        "skills": deepcopy(base.PHYSICAL_CORE) + WARRIOR, "races": ["Nord"],
        "fantasy": "Guerriero nordico aggressivo che trasforma resistenza e slancio in pressione frontale.",
        "combat": "Carica con arma pesante, accetta lo scambio di colpi e cresce in danno e tenuta invece che in difesa di formazione.",
        "archetype": "Bruto Nord con armi a due mani, carica e grande riserva fisica.",
        "tags": {"core_fisico": 5, "focus_combat": 5, "attacco": 5, "difesa": 1, "range_skill": -5, "core_magico": -5},
        "competences": {"intimidire": 5, "sopravvivenza": 3, "scalare": 2, "diplomazia": -5, "sapienza_magica": -5},
        "siblings": [("Guerriero (standard)", "nearest", "Più aggressione e armi pesanti, meno scudo e flessibilità."), ("Berserker Nord", "same-culture", "Il Barbaro conserva controllo tattico e non dipende dalla furia."), ("Soldato Imperiale", "contrast", "Individualista e offensivo, non formazione disciplinata.")],
        "axes": [("arma pesante", "martelli/asce a due mani per fascia"), ("tenacia nordica", "Core fisico, intimidire e razza Nord")],
        "must": ["Nord", "arma pesante", "carica", "resistenza"], "must_not": ["magia", "scudo", "disciplina legionaria", "azioni innate"],
        "variation": "ascia o martello pesante nella fascia prevista", "legacy_range": "1-20",
        "range_reason": "Le quattro righe Elder coprono 1-20 senza extrapolazione.",
        "checkpoints": ["bruto riconoscibile", "carica e danno", "veterano resistente", "pressione pesante", "campione barbarico non berserker"],
        "at_least_one": ["Carica o Più Danno entro il livello 5"],
    },
    {
        "name": "Cacciatore Bosmer", "source": "899-900-901-902", "ids": [899, 900, 901, 902],
        "category": "Bosmer", "core": "stealth", "core_share": 0.42, "magic": "none",
        "classes": ["Ranger"], "skills": ARCHER_CORE + ARCHERY + RANGER, "races": ["Bosmer"],
        "fantasy": "Cacciatore di Valenwood che legge terreno e preda prima di scoccare.",
        "combat": "Prepara l'ingaggio, colpisce da copertura e usa mobilità e guerriglia per non offrire un bersaglio stabile.",
        "archetype": "Ranger Bosmer da imboscata, percezione e sopravvivenza.",
        "tags": {"core_fisico": 3, "focus_combat": 4, "range_skill": 5, "attacco": 4, "esplorazione_infiltrazione": 5, "core_magico": -5},
        "competences": {"conoscenze_naturaegeografia": 5, "sopravvivenza": 5, "percezione": 4, "furtivita": 3, "diplomazia": -3},
        "siblings": [("Arciere (standard)", "nearest", "Ranger, natura e guerriglia sostituiscono neutralità professionale."), ("Arciere Bandito", "same-role", "Caccia e sopravvivenza, non rapina e improvvisazione."), ("Esploratore Imperiale", "contrast", "Più letale a distanza, meno ricognizione istituzionale.")],
        "axes": [("predatore del bosco", "Ranger e competenze naturali"), ("tiro da imboscata", "archi, Focus e Guerriglia")],
        "must": ["Bosmer", "Ranger", "arco", "sopravvivenza"], "must_not": ["magia", "scudo", "armatura pesante", "azioni innate"],
        "variation": "archi e coltelli da caccia per fascia", "legacy_range": "1-20",
        "range_reason": "Le quattro righe Elder forniscono un percorso completo.",
        "checkpoints": ["cacciatore mobile", "Guerriglia online", "predatore esperto", "cecchino del bosco", "maestro di Valenwood"],
        "at_least_one": ["una Skill Ranger entro il livello 5"],
    },
    {
        "name": "Esploratore Imperiale", "source": "841-842-843-844", "ids": [841, 842, 843, 844],
        "category": "Imperiale", "core": "stealth", "core_share": 0.5, "magic": "none",
        "classes": ["Ranger"], "skills": ARCHER_CORE + WARRIOR[:4] + RANGER, "races": ["Imperiale"],
        "fantasy": "Ricognitore della Legione capace di osservare, riferire e sopravvivere oltre la linea.",
        "combat": "Alterna arco e spada, marca percorsi sicuri e si ritira prima che la schermaglia diventi una battaglia frontale.",
        "archetype": "Scout Imperiale ibrido a distanza/melee leggero con forte percezione.",
        "tags": {"core_fisico": 3, "focus_combat": 3, "range_skill": 4, "attacco": 3, "esplorazione_infiltrazione": 5, "controllo_situazionale": 3, "core_magico": -5},
        "competences": {"percezione": 5, "sopravvivenza": 4, "strategia_militare": 3, "furtivita": 3, "diplomazia": 1},
        "siblings": [("Soldato Imperiale", "nearest", "Ricognizione e mobilità sostituiscono scudo e linea."), ("Cacciatore Bosmer", "same-role", "Dottrina militare e arma secondaria invece di caccia pura."), ("Arciere (standard)", "contrast", "Meno specializzato nel tiro, più utile fuori dallo scontro.")],
        "axes": [("ricognizione legionaria", "percezione, strategia e sopravvivenza"), ("ibrido leggero", "arco/spada e armatura scout fissa")],
        "must": ["Imperiale", "ricognizione", "mobilità", "arma leggera"], "must_not": ["magia", "scudo pesante", "tank", "azioni innate"],
        "variation": "arco o spada nella fascia materiale", "legacy_range": "1-20",
        "range_reason": "Le quattro righe Elder coprono l'intero arco.",
        "checkpoints": ["scout operativo", "guerriglia leggera", "ricognitore veterano", "caposquadra mobile", "esploratore d'élite"],
        "at_least_one": ["Percezione alta e una Skill Ranger entro il livello 5"],
    },
    {
        "name": "Guerriero (standard)", "source": "864-865-866-867", "ids": [864, 865, 866, 867],
        "category": "Umano", "core": "warrior", "core_share": 0.55, "magic": "none",
        "skills": deepcopy(base.PHYSICAL_CORE) + deepcopy(base.SHIELD_ARCHETYPE) + [
            base.skill(331, "archetype", 7), base.skill(333, "archetype", 5, 5),
            base.skill(1010, "archetype", 7, 4), base.skill(1011, "archetype", 5, 9),
        ], "races": MORTAL_RACES,
        "fantasy": "Combattente generalista, riferimento neutrale per armi, scudo e tenuta.",
        "combat": "Tiene il centro, alterna offesa e difesa e cresce in affidabilità senza assorbire firme di fazione o classe.",
        "archetype": "Guerriero versatile con armi a una mano, scudo opzionale e materiali progressivi.",
        "tags": {"core_fisico": 5, "focus_combat": 5, "attacco": 4, "difesa": 4, "range_skill": -4, "core_magico": -5},
        "competences": {"strategia_militare": 3, "intimidire": 2, "percezione": 2, "sapienza_magica": -5},
        "siblings": [("Mercenario", "nearest", "Più neutrale e regolare, meno opportunista e misto."), ("Soldato Imperiale", "same-role", "Nessuna uniforme o dottrina di formazione."), ("Barbaro Nord", "contrast", "Difesa e scudo bilanciano l'aggressione.")],
        "axes": [("versatilità marziale", "tre famiglie d'arma e scudi"), ("baseline leggibile", "nessuna firma razziale o di fazione")],
        "must": ["arma marziale", "difesa", "progressione materiali"], "must_not": ["magia", "religione", "fazione", "azioni innate"],
        "variation": "spada, ascia o mazza con armatura/scudo della fascia", "legacy_range": "1-20",
        "range_reason": "Le quattro righe Elder sono già complete.",
        "checkpoints": ["baseline marziale", "scudo e manovre", "veterano versatile", "equipaggiamento superiore", "guerriero d'élite neutrale"],
        "at_least_one": ["una manovra offensiva e una difensiva entro il livello 5"],
    },
    {
        "name": "Ladro (standard)", "source": "903-904-905-906", "ids": [903, 904, 905, 906],
        "category": "Umano", "core": "stealth", "core_share": 0.48, "magic": "none",
        "classes": ["Ladro"], "skills": STEALTH_CORE + THIEF, "races": MORTAL_RACES,
        "fantasy": "Professionista dell'accesso illecito che vince con posizione, strumenti e fuga.",
        "combat": "Evita lo scontro onesto, colpisce quando ha vantaggio e conserva sempre una via d'uscita.",
        "archetype": "Ladro generalista con lame corte, strumenti, acrobazia e infiltrazione.",
        "tags": {"core_fisico": 2, "focus_combat": 3, "attacco": 3, "difesa": 1, "esplorazione_infiltrazione": 5, "tecnica_crafting": 3, "core_magico": -5},
        "competences": {"furtivita": 5, "rapidita_di_mano": 5, "raggirare": 4, "percezione": 3, "strategia_militare": -4},
        "siblings": [("Agente Morag Tong", "nearest", "Furto e fuga sostituiscono omicidio e sangue."), ("Arciere Bandito", "same-space", "Lame corte e accesso, non tiro e agguato."), ("Guerriero (standard)", "contrast", "Rifiuta lo scontro frontale.")],
        "axes": [("accesso illecito", "Attrezzi del Mestiere e Manolesta"), ("fuga", "Fuga Rapida, Blink e acrobazia")],
        "must": ["furtività", "lame corte", "strumenti", "fuga"], "must_not": ["magia", "armatura pesante", "scudo", "assassino rituale"],
        "variation": "daga o stiletto nella fascia", "legacy_range": "1-20",
        "range_reason": "Le quattro righe Elder coprono 1-20.",
        "checkpoints": ["scassinatore mobile", "fuga affidabile", "ladro acrobata", "infiltratore esperto", "maestro neutrale del furto"],
        "at_least_one": ["Attrezzi del Mestiere o Fuga Rapida entro il livello 5"],
    },
    {
        "name": "Mago (standard)", "source": "868-869-870-871", "ids": [868, 869, 870, 871],
        "category": "Umano", "core": "mage", "core_share": 0.5, "magic": "any",
        "skills": deepcopy(base.MAGE_CORE) + DESTRUCTION, "races": MORTAL_RACES,
        "fantasy": "Incantatore generalista che rappresenta la baseline arcana, non una scuola o fazione specifica.",
        "combat": "Gestisce distanza e Mana, sceglie forma ed elemento dell'attacco e cresce verso effetti d'area controllati.",
        "archetype": "Mago generalista di Distruzione con difese e risorse arcane di base.",
        "tags": {"core_magico": 5, "natura_magica": 5, "range_skill": 4, "area_e_multi_target": 4, "controllo_situazionale": 3, "core_fisico": -5},
        "competences": {"sapienza_magica": 5, "conoscenze_storiaenobilta": 2, "percezione": 2, "intimidire": -3},
        "siblings": [("Mago da Battaglia", "nearest", "Nessuna arma o ramo marziale."), ("Mago Telvanni", "same-role", "Nessuna firma Illusione, evocazione o casata."), ("Anomalia Magica", "contrast", "Gestione deliberata di Skill e Mana, non fenomeno innato.")],
        "axes": [("baseline arcana", "Core mage e Distruzione multi-elementale"), ("crescita di area", "Sfera, Runa e Muro")],
        "must": ["Mana", "Distruzione", "veste", "distanza"], "must_not": ["arma marziale", "armatura pesante", "religione", "azioni innate"],
        "variation": "staff e veste di Evocazione/Distruzione per grado", "legacy_range": "1-20",
        "range_reason": "Le quattro righe Elder coprono 1-20.",
        "checkpoints": ["incantatore funzionale", "forma elementale scelta", "area controllata", "mago veterano", "maestro generalista"],
        "at_least_one": ["un attacco di Distruzione entro il livello 1"],
    },
    {
        "name": "Monaco (standard)", "source": "913-914-915-916", "ids": [913, 914, 915, 916],
        "category": "Umano", "core": "warrior", "core_share": 0.46, "magic": "none",
        "classes": ["Monaco"], "skills": deepcopy(base.PHYSICAL_CORE) + MONK, "races": MORTAL_RACES,
        "fantasy": "Combattente disciplinato che usa corpo, postura e concentrazione invece dell'armatura.",
        "combat": "Entra a corta distanza, cambia stile per il problema e cresce in precisione senza diventare un bruto corazzato.",
        "archetype": "Monaco marziale con mani nude, bastone e stili elementali non magici.",
        "tags": {"core_fisico": 4, "focus_combat": 5, "attacco": 4, "difesa": 3, "controllo_situazionale": 4, "core_magico": -4},
        "competences": {"intuizione": 5, "percezione": 4, "scalare": 3, "intimidire": -3, "sapienza_magica": -2},
        "siblings": [("Guerriero (standard)", "nearest", "Stili e mani nude sostituiscono armatura e scudo."), ("Barbaro Nord", "same-range", "Controllo e precisione sostituiscono forza bruta."), ("Mago (standard)", "contrast", "Gli stili sono disciplina fisica, non incantesimi.")],
        "axes": [("stili marziali", "famiglia Monaco"), ("corpo come arma", "Mani Nude e assenza di armatura")],
        "must": ["Monaco", "mani nude", "stile", "disciplina"], "must_not": ["armatura", "scudo", "magia", "azioni innate"],
        "variation": "bastone o mani nude con stili diversi", "legacy_range": "1-20",
        "range_reason": "Le quattro righe Elder coprono l'intero percorso.",
        "checkpoints": ["adepto riconoscibile", "primo stile", "combattente disciplinato", "stili avanzati", "maestro fisico non magico"],
        "at_least_one": ["Adepto e una tecnica Mani Nude entro il livello 5"],
    },
    {
        "name": "Arciere Scheletro", "source": "1010", "ids": [1010],
        "category": "Non morto", "core": "stealth", "core_share": 0.48, "magic": "none",
        "skills": ARCHER_CORE + ARCHERY + PURE_ARCHERY_CEILING, "races": ["Non morto"], "subraces": ["Scheletro"],
        "equipment": [base.item("arma", 532), base.item("arma", 533)],
        "kind_reason": "Impugna archi e usa tecniche di tiro: ora che la razza Non morto esiste, il contratto corretto è humanoid.",
        "fantasy": "Ossa animate che conservano addestramento di tiro e obbediscono senza esitazione.",
        "combat": "Mantiene distanza, concentra il fuoco e sfrutta l'assenza di paura; resta fragile se raggiunto e colpito con armi contundenti.",
        "archetype": "Arciere non morto disciplinato con arco lungo e vulnerabilità narrativa alle mazze.",
        "tags": {"core_fisico": 3, "focus_combat": 5, "range_skill": 5, "attacco": 4, "difesa": 1, "core_magico": -5},
        "competences": {"percezione": 4, "strategia_militare": 2, "furtivita": 1, "diplomazia": -5, "raggirare": -5},
        "siblings": [("Arciere (standard)", "nearest", "Razza Scheletro, nessun bisogno biologico e arco lungo fisso."), ("Lich", "same-origin", "Tiro fisico e obbedienza sostituiscono magia e comando."), ("Draugr Guerriero", "same-race", "Distanza e fragilità invece di pressione melee.")],
        "axes": [("scheletro tiratore", "razza/sottorazza bloccate e arco lungo"), ("disciplina senza paura", "pool tiro privo di magia o sociale")],
        "must": ["Non morto", "Scheletro", "arco lungo", "tiro"], "must_not": ["magia", "teletrasporto", "azioni innate", "razza mortale"],
        "variation": "arco lungo acciaio o nordico", "legacy_range": "solo livello 20",
        "range_reason": "L'identità è front-loaded; 1-20 varia soltanto per Skill e materiale dell'arco.",
        "checkpoints": ["scheletro arciere completo", "tecniche di tiro", "focus coordinato", "precisione veterana", "tiratore d'élite non magico"],
        "at_least_one": ["razza Non morto/Scheletro in ogni variante"],
    },
    {
        "name": "Draugr Guerriero", "source": "1014", "ids": [1014],
        "category": "Non morto", "core": "warrior", "core_share": 0.56, "magic": "none",
        "skills": deepcopy(base.PHYSICAL_CORE) + WARRIOR, "races": ["Non morto"], "subraces": ["Draugr"],
        "equipment": [base.item("arma", 225), base.item("arma", 589), base.item("arma", 183)],
        "kind_reason": "Impugna armi nordiche e combatte con manovre: la razza Non morto consente un humanoid fedele.",
        "fantasy": "Guardiano nordico sepolto che continua a difendere tomba, giuramento e rango.",
        "combat": "Avanza con armi nordiche, assorbe gelo e paura e usa pressione semplice ma inesorabile.",
        "archetype": "Guerriero Draugr resistente con armi nordiche e disciplina funebre.",
        "tags": {"core_fisico": 5, "focus_combat": 5, "attacco": 4, "difesa": 4, "range_skill": -5, "core_magico": -5},
        "competences": {"intimidire": 5, "strategia_militare": 3, "percezione": 2, "diplomazia": -5, "raggirare": -5},
        "siblings": [("Guerriero (standard)", "nearest", "Draugr, gelo e armi nordiche fisse sostituiscono neutralità."), ("Arciere Scheletro", "same-race", "Pressione melee e resistenza invece di tiro."), ("Lich", "same-origin", "Nessuna magia o comando dei morti.")],
        "axes": [("guardiano della tomba", "Non morto/Draugr e competenze di intimidazione"), ("arsenale nordico", "spada, ascia o mazza nordica")],
        "must": ["Non morto", "Draugr", "arma nordica", "resistenza"], "must_not": ["magia", "azioni innate", "razza mortale", "equipaggiamento casuale"],
        "variation": "spada, ascia o mazza nordica", "legacy_range": "solo livello 20",
        "range_reason": "La funzione di guardiano è valida dal livello 1; la crescita passa solo dalle Skill.",
        "checkpoints": ["guardiano Draugr completo", "manovre melee", "tenuta gelida", "veterano della tomba", "campione non morto non magico"],
        "at_least_one": ["razza Non morto/Draugr in ogni variante"],
    },
]


CREATURE_SPECS: list[dict[str, Any]] = [
    {
        "name": "Atronach della Tempesta", "source": "1008", "ids": [1008], "category": "Daedra",
        "fantasy": "Tempesta cosciente compressa in un corpo daedrico.",
        "combat": "Controlla la media distanza con fulmini, richiama la tempesta e converte Mana in difesa.",
        "archetype": "Caster elettrico mobile con grandi riserve arcane e resistenza elettrica.",
        "siblings": [("Atronach del Gelo", "nearest", "Mobilità e fulmini sostituiscono tanking e rallentamento."), ("Atronach di Fuoco", "same-family", "Controllo elettrico e difesa Mana, non aura incendiaria."), ("Anomalia Magica", "contrast", "Elemento e corpo definiti, non distorsione instabile.")],
        "axes": [("dominio elettrico", "Respiro Fulmineo e res/rd elettrica"), ("tempesta mobile", "velocità, Richiamo e Mana alto")],
        "must": ["elettricità", "Mana", "tempesta"], "must_not": ["fuoco dominante"],
        "checkpoints": ["elementale elettrico", "richiamo della tempesta", "scudo arcano", "caster mobile", "incarnazione della tempesta"],
        "range_reason": "La riga 20 viene distribuita 1-20 preservando l'asse elettrico.", "at_least_one": ["res_elettro positiva a ogni livello"],
    },
    {
        "name": "Atronach di Carne", "source": "1002", "ids": [1002], "category": "Daedra",
        "fantasy": "Massa cucita e animata che trasforma danno subito in rigenerazione.",
        "combat": "Occupa spazio, rigenera e colpisce con peso e coda; è lento e vulnerabile a taglio ed elettricità.",
        "archetype": "Bruto rigenerante ad alti PF con debolezze fisiche leggibili.",
        "siblings": [("Atronach del Gelo", "nearest", "Rigenerazione organica invece di armatura elementale."), ("Colosso d’Ossa", "same-scale", "Carne e guarigione invece di ossa e gelo."), ("Cinghiale", "contrast", "Costrutto magico, non bestia da carica.")],
        "axes": [("rigenerazione di carne", "Pelle/Scoppio di Rigenerazione"), ("massa instabile", "PF e Forza alti, taglio/elettro deboli")],
        "must": ["rigenerazione", "carne", "forza"], "must_not": ["armatura elementale"],
        "checkpoints": ["massa resistente", "rigenerazione attiva", "coda e controllo", "bruto persistente", "abominio di carne"],
        "range_reason": "Il profilo livello 20 viene reso lineare senza nascondere le vulnerabilità.", "at_least_one": ["res_taglio o res_elettro negativa"],
    },
    {
        "name": "Atronach di Fuoco", "source": "1006", "ids": [1006], "category": "Daedra",
        "fantasy": "Fiamma vincolata in forma agile, letale se può restare in movimento.",
        "combat": "Lancia fuoco, punisce gli adiacenti con aura e usa Mana per proteggersi; teme il gelo.",
        "archetype": "Caster di Fuoco rapido con aura, proiettile e vulnerabilità al gelo.",
        "siblings": [("Atronach del Gelo", "nearest", "Velocità e danno sostituiscono tanking e controllo."), ("Atronach della Tempesta", "same-family", "Aura di Fuoco e debolezza gelo invece di controllo elettrico."), ("Daedroth", "contrast", "Puro elemento a distanza, non bruto daedrico.")],
        "axes": [("fiamma mobile", "velocità/agilità e Palla di Fuoco"), ("polarità elementale", "res_fuoco alta e res_gelo bassa")],
        "must": ["fuoco", "mobilità", "Mana"], "must_not": ["gelo offensivo"],
        "checkpoints": ["fiamma mobile", "aura online", "scudo Mana", "caster incendiario", "elementale maggiore"],
        "range_reason": "La riga 20 viene estesa con firma elementale costante.", "at_least_one": ["res_fuoco 5 e debolezza gelo"],
    },
    {
        "name": "Cinghiale", "source": "988", "ids": [988], "category": "Animale",
        "fantasy": "Bestia territoriale che converte massa, rabbia e terreno in una carica devastante.",
        "combat": "Carica in linea, incassa e usa Furia quando ferito; non possiede alcun trucco magico.",
        "archetype": "Animale resistente da carica e furia.",
        "curve_overrides": {"mana": (0, 0)},
        "siblings": [("Lupo", "nearest", "Carica e massa invece di branco e balzo."), ("Clannfear", "same-role", "Animale naturale privo di coda e resistenza daedrica."), ("Atronach di Carne", "contrast", "Nessuna rigenerazione magica.")],
        "axes": [("carica", "azione Carica e Forza"), ("ostinazione", "PF/Resistenza e Furia")],
        "must": ["carica", "Furia", "Mana zero"], "must_not": ["magia", "volo"],
        "checkpoints": ["bestia da carica", "Furia", "massa crescente", "cinghiale veterano", "mostro territoriale"],
        "range_reason": "Il profilo 20 viene esteso mantenendo Mana zero e biologia naturale.", "at_least_one": ["mana 0 a ogni checkpoint"],
    },
    {
        "name": "Clannfear", "source": "1000", "ids": [1000], "category": "Daedra",
        "fantasy": "Predatore daedrico bipede che spezza la linea con cranio e coda.",
        "combat": "Carica il bersaglio, usa la coda contro chi lo circonda e cresce in Furia senza magia.",
        "archetype": "Predatore daedrico rapido da carica e controllo ravvicinato.",
        "curve_overrides": {"mana": (0, 0)},
        "siblings": [("Cinghiale", "nearest", "Più agile e con coda, oltre a natura daedrica."), ("Daedroth", "same-origin", "Predatore rapido non caster, meno massiccio."), ("Crepuscolo Alato", "contrast", "Terrestre e fisico, non volante e mentale.")],
        "axes": [("cranio e coda", "Carica e Colpo di Coda"), ("predatore daedrico", "velocità/forza e res_fuoco")],
        "must": ["carica", "coda", "Furia", "Mana zero"], "must_not": ["incantesimi", "volo"],
        "checkpoints": ["predatore rapido", "coda online", "Furia", "cacciatore daedrico", "Clannfear maggiore"],
        "range_reason": "La riga 20 viene resa giocabile 1-20 senza aggiungere magie.", "at_least_one": ["mana 0 e res_fuoco positiva"],
    },
    {
        "name": "Colosso d’Ossa", "source": "1012", "ids": [1012], "category": "Non morto",
        "fantasy": "Monumento necromantico costruito da ossa intrecciate e volontà vincolate.",
        "combat": "Avanza lentamente, pesta un'area e alza scudi d'ossa; teme contundente e fuoco.",
        "archetype": "Colosso non morto lento con pestone, corazza e scudo d'ossa.",
        "siblings": [("Atronach di Carne", "nearest", "Ossa, gelo e difesa invece di carne e rigenerazione."), ("Drago d’Ossa", "same-origin", "Terrestre e lento, senza volo o soffio."), ("Centurione Nanico", "contrast", "Necromanzia e gelo, non metallo e vapore.")],
        "axes": [("massa d'ossa", "PF/Forza e Pestone Tonante"), ("fortezza necromantica", "Pelle di Pietra, Scudo d'Ossa e res_gelo")],
        "must": ["ossa", "pestone", "gelo", "lentezza"], "must_not": ["volo", "rigenerazione di carne"],
        "checkpoints": ["massa lenta", "pestone", "pelle protettiva", "scudo d'ossa", "colosso funebre"],
        "range_reason": "La riga 20 viene linearizzata conservando debolezza contundente.", "at_least_one": ["res_contundente negativa e res_gelo 5"],
    },
    {
        "name": "Crepuscolo Alato", "source": "1003", "ids": [1003], "category": "Daedra",
        "fantasy": "Daedra volante intelligente che alterna picchiata, assalto mentale e ombra.",
        "combat": "Controlla quota e distanza, entra in picchiata e scompare nell'ombra prima della rappresaglia.",
        "archetype": "Predatore volante daedrico con danno mentale e occultamento.",
        "siblings": [("Cliff Racer", "nearest", "Magia mentale e ombra sostituiscono comportamento animale."), ("Clannfear", "same-origin", "Volo e controllo invece di carica terrestre."), ("Drago Spettrale", "contrast", "Più agile e fragile, senza chassis draconico.")],
        "axes": [("volo tattico", "Tuffo Aereo e alta Agilità"), ("assalto psichico", "Sferzata Mentale e ombra")],
        "must": ["volo", "ombra", "attacco mentale"], "must_not": ["carica terrestre"],
        "checkpoints": ["predatore volante", "sferzata mentale", "fusione nell'ombra", "controllore aereo", "crepuscolo maggiore"],
        "range_reason": "La riga 20 viene estesa distribuendo le tre azioni distintive.", "at_least_one": ["Tuffo Aereo presente"],
    },
    {
        "name": "Daedroth", "source": "999", "ids": [999], "category": "Daedra",
        "fantasy": "Bruto daedrico rettiliano che combina zanne, fuoco e furia.",
        "combat": "Preme in melee, usa coda e fiato pestilenziale e può proiettare fuoco quando il bersaglio arretra.",
        "archetype": "Bruto Daedra ibrido con coda, fuoco e pressione ravvicinata.",
        "siblings": [("Clannfear", "nearest", "Più lento, resistente e capace di attacchi a distanza."), ("Atronach di Fuoco", "same-element", "Bruto fisico con fuoco secondario, non elemento puro."), ("Dreugh", "contrast", "Daedra offensivo, non predatore acquatico rigenerante.")],
        "axes": [("bruto rettiliano", "Forza, PF, coda e Furia"), ("fiato daedrico", "Soffio Pestilenziale e Palla di Fuoco")],
        "must": ["coda", "fuoco", "Furia", "forza"], "must_not": ["volo", "controllo mentale"],
        "checkpoints": ["bruto daedrico", "fiato", "coda", "Furia", "Daedroth maggiore"],
        "range_reason": "La riga 20 viene distribuita senza ridurlo a un Atronach di Fuoco.", "at_least_one": ["azione fisica e azione a distanza"],
    },
    {
        "name": "Drago d’Ossa", "source": "1025", "ids": [1025], "category": "Non morto",
        "fantasy": "Scheletro draconico sostenuto da necromanzia e odio residuo.",
        "combat": "Vola, picchia, soffia energia pestilenziale e indurisce le ossa contro il contrattacco.",
        "archetype": "Drago non morto fisico con volo, soffio necrotico e corazza d'ossa.",
        "siblings": [("Drago Spettrale", "nearest", "Corpo osseo e protezione fisica, non etereo e fulmineo."), ("Drago", "same-chassis", "Non morto e pestilenziale invece di vivo e incendiario."), ("Colosso d’Ossa", "same-origin", "Volo e intelligenza draconica invece di massa terrestre.")],
        "axes": [("drago scheletrico", "volo, PF e Pelle di Pietra"), ("soffio necrotico", "Soffio Pestilenziale")],
        "must": ["ossa", "volo", "soffio", "gelo"], "must_not": ["forma eterea", "fuoco dominante"],
        "checkpoints": ["drago osseo", "tuffo", "soffio necrotico", "corazza", "drago d'ossa antico"],
        "range_reason": "La riga 20 viene resa progressiva mantenendo il chassis draconico.", "at_least_one": ["rd_fis e res_gelo positive"],
    },
    {
        "name": "Drago Spettrale", "source": "1026", "ids": [1026], "category": "Non morto",
        "fantasy": "Memoria draconica incorporea che attraversa materia e colpisce con gelo e fulmine.",
        "combat": "Usa forma eterea per negare il contatto, poi picchia o scarica elettricità da quota sicura.",
        "archetype": "Drago incorporeo ad alto Mana con forma eterea, volo e fulmini.",
        "siblings": [("Drago d’Ossa", "nearest", "Etereo, arcano e fulmineo invece di corporeo e pestilenziale."), ("Drago", "same-chassis", "Spettro gelido, non creatura viva di Fuoco."), ("Crepuscolo Alato", "contrast", "Chassis draconico e potenza superiore, meno furtivo.")],
        "axes": [("incorporeità", "Forma Eterea e resistenze fisiche"), ("tempesta funebre", "Respiro Fulmineo, Mana e gelo")],
        "must": ["forma eterea", "volo", "fulmine", "gelo"], "must_not": ["corpo osseo", "fuoco dominante"],
        "checkpoints": ["drago spettrale", "tuffo", "forma eterea", "respiro fulmineo", "ombra draconica antica"],
        "range_reason": "La riga 20 viene estesa mantenendo identità incorporea a ogni checkpoint.", "at_least_one": ["Forma Eterea e res_gelo positiva"],
    },
]


BATCH_CANDIDATES = [humanoid_candidate(spec) for spec in HUMANOID_SPECS] + [
    creature_candidate(spec) for spec in CREATURE_SPECS
]

base.OUTPUT_ROOT = OUTPUT_ROOT
base.ALL_CANDIDATES = BATCH_CANDIDATES
base.VARIANTS = tuple(f"batch2-v2-{index}" for index in range(1, 9))
base.CONVERTER_VERSION = "elder-unit-charter-v2-batch2"


if __name__ == "__main__":
    base.main()

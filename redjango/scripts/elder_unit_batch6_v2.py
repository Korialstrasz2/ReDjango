from __future__ import annotations

from copy import deepcopy
from typing import Any

import elder_unit_calibration_v2 as base
import elder_unit_batch2_v2 as toolkit
import elder_unit_batch3_v2 as rolekit
import elder_unit_batch4_v2 as batch4
import elder_unit_batch5_v2 as previous


OUTPUT_ROOT = base.WORKSPACE_ROOT / "elder-unit-batch-6-v2" / "authored"
toolkit.BATCH_LABEL = "Batch 6 v2"

MORTAL_RACES = deepcopy(previous.MORTAL_RACES)


def covered_equipment(source_file: str) -> list[dict[str, Any]]:
    return previous.covered_equipment(source_file)


def unique_skills(*pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return previous.unique_skills(*pools)


EVOCATION = [
    base.skill(438, "archetype", 8),
    base.skill(1213, "archetype", 7, 3),
    base.skill(439, "archetype", 9),
    base.skill(440, "archetype", 8, 4),
    base.skill(442, "archetype", 7, 5),
    base.skill(1212, "archetype", 7, 5),
    base.skill(443, "archetype", 6, 7),
    base.skill(444, "archetype", 6, 8),
    base.skill(1314, "archetype", 6, 9),
    base.skill(445, "archetype", 5, 11),
    base.skill(1315, "archetype", 5, 13),
]

DAEDRIC_EVOCATION = [
    base.skill(439, "archetype", 9),
    base.skill(440, "archetype", 8, 4),
    base.skill(442, "archetype", 8, 5),
    base.skill(443, "archetype", 6, 7),
    base.skill(444, "archetype", 6, 8),
    base.skill(1314, "archetype", 6, 9),
    base.skill(445, "archetype", 5, 11),
    base.skill(1315, "archetype", 5, 13),
]

ANCESTOR_RITES = [
    base.skill(1212, "archetype", 10),
    base.skill(439, "archetype", 7, 4),
    base.skill(432, "archetype", 7, 5),
    base.skill(440, "archetype", 6, 7),
    base.skill(1311, "archetype", 6, 8),
    base.skill(444, "archetype", 5, 10),
]

BRIAR_RITES = [
    base.skill(432, "archetype", 6, 4),
    base.skill(1311, "archetype", 6, 7),
]

MASTER_THIEF = [
    base.skill(811, "archetype", 7),
    base.skill(812, "archetype", 7),
    base.skill(814, "archetype", 8),
    base.skill(815, "archetype", 8),
    base.skill(818, "archetype", 6, 4),
    base.skill(819, "archetype", 6, 4),
    base.skill(820, "archetype", 5, 7),
    base.skill(822, "archetype", 7),
    base.skill(823, "archetype", 6),
    base.skill(989, "archetype", 6),
    base.skill(990, "archetype", 6, 5),
    base.skill(991, "archetype", 6),
    base.skill(992, "archetype", 5, 7),
    base.skill(993, "archetype", 5, 8),
    base.skill(994, "archetype", 5, 9),
    base.skill(995, "archetype", 5, 10),
    base.skill(996, "archetype", 6, 5),
]

LISTENER_ASSASSIN = unique_skills(
    previous.ASSASSIN,
    [
        base.skill(682, "archetype", 7, 5),
        base.skill(685, "archetype", 8, 4),
    ],
)
for listener_skill in LISTENER_ASSASSIN:
    if listener_skill["skillId"] == 685:
        listener_skill["minLevel"] = 1


def humanoid_candidate(spec: dict[str, Any]) -> dict[str, Any]:
    return previous.humanoid_candidate(spec)


def sourced_action(source_file: str, name: str, *, key: str, description: str) -> dict[str, Any]:
    action = next(
        deepcopy(entry)
        for entry in toolkit.source_actions(source_file)
        if entry["name"] == name
    )
    action["key"] = key
    action["description"] = description
    action["minLevel"] = 1
    action["maxLevel"] = 20
    return action


FLIGHT = sourced_action(
    "1028",
    "Volo",
    key="batch6-volo",
    description=(
        "Passiva. La creatura può attraversare il campo in volo; usa l'azione "
        "Volo già presente nel vocabolario delle Unit."
    ),
)

SHADOW_STEP = sourced_action(
    "1005",
    "Passo d'Ombra",
    key="batch6-ragno-daedra-passo-ombra",
    description=(
        "La creatura si riposiziona attraverso una piega d'ombra usando PA ed Energia; "
        "non introduce danni o risorse fuori vocabolario."
    ),
)
SHADOW_STEP["minLevel"] = 6

SKELETON_WEAPON = {
    "key": "batch6-arma-da-cripta",
    "name": "Arma da Cripta",
    "description": (
        "Bersaglio adiacente. Lo scheletro colpisce con spada, ascia o mazza d'acciaio "
        "incorporata nel profilo, infliggendo rispettivamente Taglio o Contundente. "
        "L'arma non è un oggetto equipaggiato o recuperabile."
    ),
    "minLevel": 1, "maxLevel": 20,
    "costs": {"pa": 4, "energia": 2},
    "trigger": "Azione", "duration": "Istantanea", "icon": "spada",
}

GOBLIN_WEAPON = {
    "key": "batch6-arma-tribale-goblin",
    "name": "Arma Tribale",
    "description": (
        "Bersaglio adiacente. Il Goblin usa ascia, mazza o spada rozza come parte del "
        "suo profilo innato, infliggendo Taglio o Contundente. Non crea equipment."
    ),
    "minLevel": 1, "maxLevel": 20,
    "costs": {"pa": 4, "energia": 2},
    "trigger": "Azione", "duration": "Istantanea", "icon": "ascia",
}

SWARM_ASSAULT = {
    "key": "batch6-assalto-dello-sciame",
    "name": "Assalto dello Sciame",
    "description": (
        "Bersaglio entro 2 esagoni. Lo sciame avvolge il bersaglio e infligge danni "
        "Perforante; la dispersione collettiva è rappresentata dalle curve difensive."
    ),
    "minLevel": 1, "maxLevel": 20,
    "costs": {"pa": 4, "energia": 3},
    "trigger": "Azione", "duration": "Istantanea", "icon": "vento",
}


def rewrite_actions(
    source_file: str,
    unlocks: dict[str, int],
    descriptions: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    actions = previous.authored_actions(source_file, unlocks)
    for action in actions:
        if descriptions and action["name"] in descriptions:
            action["description"] = descriptions[action["name"]]
    return actions


def sanguine_anomaly_actions() -> list[dict[str, Any]]:
    actions = rewrite_actions(
        "1044",
        {"Immunità magica": 1, "Attacco dell'Anomalia": 4},
        {
            "Immunità magica": "Passiva. Le alte resistenze e RD a Fuoco, Gelo ed Elettro sono espresse dalle curve; non concede immunità assoluta.",
            "Attacco dell'Anomalia": "Si teletrasporta adiacente a un bersaglio entro 12 metri, infligge danni Puro e riduce il Mana.",
        },
    )
    for action in actions:
        if action["name"] == "Immunità magica":
            action["name"] = "Resistenza Magica"
    return actions


def creature_candidate(spec: dict[str, Any]) -> dict[str, Any]:
    return previous.creature_candidate(spec)


HUMANOID_SPECS: list[dict[str, Any]] = [
    {
        "name": "Ascoltatore della Confraternita Oscura", "source": "928", "ids": [928],
        "category": "Umano", "core": "stealth", "core_share": 0.44, "magic": "none",
        "classes": ["Assassino"], "skills": unique_skills(toolkit.STEALTH_CORE, LISTENER_ASSASSIN),
        "races": MORTAL_RACES,
        "subraces": [
            "Cacciatore", "Esploratore", "Retaggio Guerriero", "Selvaggio",
            "Plebeo", "Di Città", "Mercante", "Deserto",
            "Guerriero dell'Ombra", "Ladro Corridore", "Sud",
        ],
        "equipment": covered_equipment("928"),
        "fantasy": "Vertice rituale della Confraternita Oscura, interprete della Madre Notte e giudice dei contratti.",
        "combat": "Sceglie il momento dell'esecuzione, apre con una lama corta e usa le tecniche Assassino più avanzate senza diventare un mago.",
        "archetype": "Capo assassino cosmopolita con armatura della Confraternita e tecniche di esecuzione d'élite.",
        "tags": {"esplorazione_infiltrazione": 5, "attacco": 5, "focus_combat": 5, "sociale": 3, "controllo_situazionale": 4, "core_magico": -5},
        "competences": {"furtivita": 5, "percezione": 5, "intuizione": 5, "intimidire": 4, "conoscenze_religioni": 4, "diplomazia": -4},
        "siblings": [("Assassino della Confraternita Oscura", "nearest", "Capstone, autorità rituale e giudizio dei contratti invece di operatività ordinaria."), ("Agente Morag Tong", "same-role", "Comando sacrilego e segreto invece di mandato legale dunmer."), ("Shadowscale Argoniano", "contrast", "Vertice cosmopolita, non tradizione razziale.")],
        "axes": [("autorità della Madre Notte", "intuizione, religione e tecniche Assassino avanzate"), ("esecuzione d'élite", "Kriss/Shiv, Primo sangue e Bacio della morte")],
        "must": ["Confraternita Oscura", "autorità rituale", "lama corta", "Assassino"],
        "must_not": ["magia", "scudo", "arma pesante", "azioni innate"],
        "variation": "Kriss di vetro o Shiv adamantio con capstone Assassino",
        "legacy_range": "15-20",
        "range_reason": "Rango e set sono front-loaded a ogni livello; la progressione 1-20 passa dalle Skill.",
        "checkpoints": ["Ascoltatore riconoscibile", "esecuzione disciplinata", "Primo sangue", "Killer veterano", "voce della Madre Notte"],
        "at_least_one": ["una Skill Assassino entro il livello 5"],
    },
    {
        "name": "Briarheart Forsworn", "source": "957", "ids": [957],
        "category": "Bretone", "core": "specialist", "core_share": 0.5, "magic": "any",
        "classes": ["Barbaro"],
        "skills": unique_skills(base.PHYSICAL_CORE, rolekit.BARBARIAN, BRIAR_RITES),
        "races": ["Bretone"], "subraces": ["Soldato a Piedi"],
        "equipment": covered_equipment("957"),
        "fantasy": "Campione Forsworn rianimato da un cuore di rovo, sospeso fra guerriero tribale e non morte rituale.",
        "combat": "Preme con ascia o spada d'ebano, entra in Furia e usa protezioni negromantiche come estensione del rito Briarheart.",
        "archetype": "Bruto Bretone ibrido Barbaro-Negromanzia con cuore rituale e armi d'ebano.",
        "tags": {"core_fisico": 5, "focus_combat": 5, "attacco": 5, "core_magico": 3, "natura_magica": 3, "difesa": 2},
        "competences": {"sopravvivenza": 5, "conoscenze_naturaegeografia": 4, "conoscenze_religioni": 4, "intimidire": 5, "diplomazia": -5},
        "siblings": [("Guerriero Forsworn", "nearest", "Cuore rituale, Furia e Negromanzia sostituiscono guerriglia ordinaria."), ("Berserker Nord", "same-role", "Rito e magia oscura invece di tradizione nordica."), ("Lich", "contrast", "Bruto vivente rituale, non incantatore non morto.")],
        "axes": [("cuore di rovo", "Negromanzia protettiva e religione tribale"), ("campione Forsworn", "ascia/spada d'ebano e Barbaro")],
        "must": ["Bretone", "Forsworn", "cuore di rovo", "arma d'ebano"],
        "must_not": ["staff", "scudo", "furtività", "azioni innate"],
        "variation": "ascia o spada lunga d'ebano",
        "legacy_range": "18-20",
        "range_reason": "Il rito Briarheart e l'ebano sono identitari e non vengono degradati ai livelli bassi.",
        "checkpoints": ["Briarheart completo", "Furia rituale", "protezione oscura", "campione della Reach", "Briarheart antico"],
        "at_least_one": ["una Skill Barbaro entro il livello 5"],
    },
    {
        "name": "Cultista Daedrico", "source": "947-948", "ids": [947, 948],
        "category": "Dunmer", "core": "mage", "core_share": 0.5, "magic": "any",
        "skills": unique_skills(base.MAGE_CORE, toolkit.DESTRUCTION, DAEDRIC_EVOCATION),
        "races": ["Dunmer"], "subraces": ["Retaggio Mago"],
        "equipment": covered_equipment("947-948"),
        "fantasy": "Devoto generico dell'Oblivion che cerca potere attraverso invocazioni, sigilli e magia distruttiva.",
        "combat": "Apre con un sigillo o un attacco elementale, mantiene distanza con lo staff e richiama un Daedra solo ai gradi più alti.",
        "archetype": "Mago cultista Dunmer con Distruzione, Evocazione e vesti isolate.",
        "tags": {"core_magico": 5, "natura_magica": 5, "attacco": 4, "controllo_situazionale": 3, "area_e_multi_target": 3, "core_fisico": -5},
        "competences": {"sapienza_magica": 5, "conoscenze_religioni": 5, "intimidire": 4, "intuizione": 3, "diplomazia": -4},
        "siblings": [("Cultista di Molag Bal", "nearest", "Generalismo daedrico invece di dominio e coercizione di Molag Bal."), ("Cultista di Mehrunes Dagon", "same-role", "Sigilli e scelta di patrono invece di Evocazione distruttiva focalizzata."), ("Mago (standard)", "contrast", "Fede proibita e Oblivion invece di educazione neutrale.")],
        "axes": [("culto di Oblivion", "religione, staff e vesti isolate"), ("magia daedrica", "Distruzione più Sigilli/Evoca Daedra")],
        "must": ["Dunmer", "Daedra", "staff", "culto"],
        "must_not": ["cura", "armatura", "arma melee", "azioni innate"],
        "variation": "staff qualificato o maestro con ramo Distruzione/Evocazione",
        "legacy_range": "10-20",
        "range_reason": "La veste qualificata viene anticipata ai livelli 1-9; il rango maestro resta alto.",
        "checkpoints": ["cultista operativo", "sigillo", "Distruzione", "evocazione daedrica", "maestro del culto"],
        "at_least_one": ["una Skill Distruzione o Evocazione entro il livello 1"],
    },
    {
        "name": "Cultista di Molag Bal", "source": "963", "ids": [963],
        "category": "Dunmer", "core": "mage", "core_share": 0.48, "magic": "any",
        "skills": unique_skills(base.MAGE_CORE, toolkit.DESTRUCTION, rolekit.NECROMANCY),
        "races": ["Dunmer"], "subraces": ["Retaggio Mago"],
        "equipment": covered_equipment("963"),
        "fantasy": "Seguace di Molag Bal ossessionato da dominio, degradazione e controllo della vita altrui.",
        "combat": "Indebolisce e terrorizza, usa Distruzione e Negromanzia e non devia verso il supporto o il duello.",
        "archetype": "Cultista Dunmer di Molag Bal con Distruzione, oscurità e controllo necromantico.",
        "tags": {"core_magico": 5, "natura_magica": 5, "controllo_situazionale": 5, "attacco": 4, "sociale": -2, "core_fisico": -5},
        "competences": {"conoscenze_religioni": 5, "sapienza_magica": 5, "intimidire": 5, "intuizione": 3, "diplomazia": -5},
        "siblings": [("Cultista Daedrico", "nearest", "Dominio e Negromanzia sostituiscono il generalismo daedrico."), ("Cultista di Mehrunes Dagon", "same-role", "Controllo e degradazione invece di invasione ed Evocazione."), ("Lich", "contrast", "Mortale devoto, non maestro immortale.")],
        "axes": [("dominio di Molag Bal", "intimidire, oscurità e decomposizione"), ("cultista distruttivo", "staff/veste Di e magia offensiva")],
        "must": ["Molag Bal", "dominio", "Distruzione", "Negromanzia"],
        "must_not": ["cura", "Evoca Animali", "arma melee", "azioni innate"],
        "variation": "staff qualificato di Distruzione con ramo oscuro variabile",
        "legacy_range": "12-16",
        "range_reason": "Il set qualificato resta fisso 1-20; la profondità delle Skill rappresenta il rango.",
        "checkpoints": ["devoto di Molag Bal", "oscurità", "dominio", "negromante offensivo", "tiranno del culto"],
        "at_least_one": ["una Skill Distruzione o Negromanzia entro il livello 1"],
    },
    {
        "name": "Cultista di Mehrunes Dagon", "source": "964", "ids": [964],
        "category": "Dunmer", "core": "mage", "core_share": 0.48, "magic": "any",
        "skills": unique_skills(base.MAGE_CORE, DAEDRIC_EVOCATION, toolkit.DESTRUCTION),
        "races": ["Dunmer"], "subraces": ["Retaggio Mago"],
        "equipment": covered_equipment("964"),
        "fantasy": "Seguace di Mehrunes Dagon che vede portali, fuoco e Daedra come strumenti di rivoluzione violenta.",
        "combat": "Apre varchi, evoca armi o Daedra e usa magia offensiva per spezzare una posizione invece di dominarla lentamente.",
        "archetype": "Cultista Dunmer di Mehrunes Dagon focalizzato su Evocazione, portali e assalto.",
        "tags": {"core_magico": 5, "natura_magica": 5, "attacco": 5, "area_e_multi_target": 4, "controllo_situazionale": 3, "core_fisico": -5},
        "competences": {"conoscenze_religioni": 5, "sapienza_magica": 5, "intimidire": 4, "strategia_militare": 3, "diplomazia": -5},
        "siblings": [("Cultista Daedrico", "nearest", "Assalto e portali di Dagon invece di culto generico."), ("Cultista di Molag Bal", "same-role", "Invasione ed Evocazione invece di dominio necromantico."), ("Mago da Battaglia", "contrast", "Fanatismo distruttivo, non disciplina professionale.")],
        "axes": [("invasione di Dagon", "Portali, Sigilli ed Evoca Daedra"), ("distruzione rivoluzionaria", "staff Ev e pressione offensiva")],
        "must": ["Mehrunes Dagon", "Evocazione", "portali", "assalto"],
        "must_not": ["cura", "Negromanzia", "arma melee", "azioni innate"],
        "variation": "staff qualificato di Evocazione con sigilli o Daedra",
        "legacy_range": "12-16",
        "range_reason": "Il set qualificato resta fisso 1-20; le evocazioni maggiori restano level-gated.",
        "checkpoints": ["devoto di Dagon", "sigillo", "portale", "Evoca Daedra", "araldo dell'invasione"],
        "at_least_one": ["una Skill Evocazione entro il livello 1"],
    },
    {
        "name": "Esploratore Ashlander", "source": "968", "ids": [968],
        "category": "Dunmer", "core": "stealth", "core_share": 0.5, "magic": "none",
        "classes": ["Ranger"],
        "skills": unique_skills(toolkit.ARCHER_CORE, toolkit.RANGER),
        "races": ["Dunmer"], "subraces": ["Esule di Solstheim"],
        "equipment": covered_equipment("968"),
        "fantasy": "Ricognitore nomade delle terre di cenere, capace di trovare sentieri e prede dove gli stranieri vedono solo desolazione.",
        "combat": "Mantiene distanza con l'arco lungo, usa il coltello soltanto quando chiuso e cambia posizione sfruttando il terreno.",
        "archetype": "Ranger Ashlander con arco lungo, armatura di chitina e sopravvivenza estrema.",
        "tags": {"range_skill": 5, "esplorazione_infiltrazione": 5, "focus_combat": 4, "attacco": 4, "difesa": 1, "core_magico": -5},
        "competences": {"sopravvivenza": 5, "conoscenze_naturaegeografia": 5, "percezione": 5, "furtivita": 3, "diplomazia": -4},
        "siblings": [("Combattente Ashlander", "nearest", "Ricognizione e arco invece di difesa tribale in mischia."), ("Saggia Ashlander", "same-tribe", "Sentieri e caccia invece di guida spirituale."), ("Cacciatore Bosmer", "contrast", "Cultura delle ceneri e dotazione tribale invece di firma bosmer.")],
        "axes": [("nomade delle ceneri", "Dunmer, chitina e geografia"), ("ricognizione a distanza", "arco lungo e Ranger")],
        "must": ["Dunmer", "Ashlander", "arco lungo", "sopravvivenza"],
        "must_not": ["magia", "scudo", "armatura pesante", "azioni innate"],
        "variation": "arco lungo d'acciaio con coltello di riserva",
        "legacy_range": "5-9",
        "range_reason": "La singola dotazione Ashlander è identitaria e resta fissa 1-20; scalano le Skill.",
        "checkpoints": ["esploratore tribale", "Guerriglia", "cecchino delle ceneri", "nomade veterano", "occhio della tribù"],
        "at_least_one": ["una Skill Arciere o Ranger entro il livello 5"],
    },
    {
        "name": "Esploratore Dres", "source": "969", "ids": [969],
        "category": "Dunmer", "core": "stealth", "core_share": 0.5, "magic": "none",
        "classes": ["Ranger"],
        "skills": unique_skills(toolkit.ARCHER_CORE, toolkit.ARCHERY),
        "races": ["Dunmer"], "subraces": ["Retaggio Guerriero", "Nobile di Vvardenfell"],
        "equipment": covered_equipment("969"),
        "fantasy": "Battitore Dres che sorveglia confini, piste e proprietà della Casata con arco e disciplina coercitiva.",
        "combat": "Apre con l'arco lungo, usa la mazzafrusta quando la preda raggiunge la linea e privilegia controllo del territorio.",
        "archetype": "Ranger Dres con arco elfico, mazzafrusta e armatura d'ossa.",
        "tags": {"range_skill": 5, "focus_combat": 4, "attacco": 4, "esplorazione_infiltrazione": 4, "controllo_situazionale": 3, "core_magico": -5},
        "competences": {"percezione": 5, "sopravvivenza": 4, "intimidire": 4, "strategia_militare": 3, "diplomazia": -4},
        "siblings": [("Schiavista Dunmer", "nearest", "Sorveglianza a distanza invece di coercizione melee."), ("Esploratore Ashlander", "same-role", "Controllo di proprietà Dres invece di nomadismo."), ("Arciere Redoran", "contrast", "Battitore territoriale, non soldato di Casata.")],
        "axes": [("territorio Dres", "armatura d'ossa e intimidire"), ("arco e mazzafrusta", "distanza primaria con riserva identitaria")],
        "must": ["Dunmer", "Dres", "arco lungo", "mazzafrusta"],
        "must_not": ["magia", "scudo", "armatura pesante", "azioni innate"],
        "variation": "arco lungo e mazzafrusta elfici",
        "legacy_range": "5-9",
        "range_reason": "Il set Dres elfico è un identity lock 1-20; la progressione avviene tramite Skill.",
        "checkpoints": ["battitore Dres", "arco lungo", "Guerriglia", "sorvegliante veterano", "maestro dei confini"],
        "at_least_one": ["una Skill Arciere o Ranger entro il livello 5"],
    },
    {
        "name": "Ladro della Gilda", "source": "960-961", "ids": [960, 961],
        "category": "Dunmer", "core": "stealth", "core_share": 0.58, "magic": "none",
        "classes": ["Ladro"], "skills": unique_skills(toolkit.STEALTH_CORE, toolkit.THIEF),
        "races": ["Dunmer"], "subraces": ["Nobile di Vvardenfell", "Esule di Solstheim"],
        "equipment": covered_equipment("960-961"),
        "fantasy": "Professionista della Gilda dei Ladri che unisce regole interne, attrezzi affidabili e vie di fuga preparate.",
        "combat": "Evita il confronto, usa Shiv o daga per liberarsi e investe in furto, acrobazia e recupero degli strumenti.",
        "archetype": "Ladro Dunmer di fazione con equipaggiamento leggero, attrezzi e fuga.",
        "tags": {"esplorazione_infiltrazione": 5, "tecnica_crafting": 5, "attacco": 2, "sociale": 3, "difesa": 1, "core_magico": -5},
        "competences": {"furtivita": 5, "rapidita_di_mano": 5, "raggirare": 4, "percezione": 4, "gestione_risorse": 3, "intimidire": -4},
        "siblings": [("Ladro (standard)", "nearest", "Identità di Gilda e disciplina degli attrezzi invece di neutralità."), ("Contrabbandiere", "same-core", "Furto urbano organizzato invece di logistica clandestina."), ("Maestro della Gilda dei Ladri", "same-faction", "Operativo intermedio senza capstone o vetro fisso.")],
        "axes": [("disciplina di Gilda", "attrezzi, recupero e raggirare"), ("furto leggero", "Shiv/daga e armatura pelle/chitina")],
        "must": ["Dunmer", "Gilda dei Ladri", "attrezzi", "furtività"],
        "must_not": ["magia", "scudo", "assassinio primario", "azioni innate"],
        "variation": "Shiv o daga in ferro/acciaio con pelle o chitina",
        "legacy_range": "5-14",
        "range_reason": "Le due fasce vengono estese agli estremi senza raggiungere il set in vetro del Maestro.",
        "checkpoints": ["ladro di Gilda", "attrezzi", "fuga", "acrobata esperto", "veterano della Gilda"],
        "at_least_one": ["Attrezzi del Mestiere o Fuga Rapida entro il livello 5"],
    },
    {
        "name": "Maestro della Gilda dei Ladri", "source": "962", "ids": [962],
        "category": "Dunmer", "core": "stealth", "core_share": 0.54, "magic": "none",
        "classes": ["Ladro"], "skills": unique_skills(toolkit.STEALTH_CORE, MASTER_THIEF),
        "races": ["Dunmer"], "subraces": ["Nobile di Vvardenfell"],
        "equipment": covered_equipment("962"),
        "fantasy": "Capo della Gilda dei Ladri che controlla reti, ricettatori e colpi complessi senza perdere l'abilità sul campo.",
        "combat": "Non cerca duelli: manipola posizione, strumenti e fuga, usando la lama di vetro soltanto quando il piano si spezza.",
        "archetype": "Maestro ladro Dunmer con set di vetro, competenze sociali e capstone di Gilda.",
        "tags": {"esplorazione_infiltrazione": 5, "tecnica_crafting": 5, "sociale": 5, "controllo_situazionale": 4, "attacco": 2, "core_magico": -5},
        "competences": {"furtivita": 5, "rapidita_di_mano": 5, "raggirare": 5, "diplomazia": 4, "gestione_risorse": 5, "intimidire": -3},
        "siblings": [("Ladro della Gilda", "nearest", "Rete, capstone e set di vetro sostituiscono operatività intermedia."), ("Agente Hlaalu", "same-social", "Autorità criminale e furto invece di influenza politica."), ("Ascoltatore della Confraternita Oscura", "contrast", "Profitto e rete, non omicidio rituale.")],
        "axes": [("capo della rete", "raggirare, diplomazia e gestione risorse"), ("maestro del colpo", "set di vetro e capstone Ladro")],
        "must": ["Dunmer", "Maestro della Gilda", "vetro", "furtività"],
        "must_not": ["magia", "scudo", "assassinio rituale", "azioni innate"],
        "variation": "Daga o Shiv di vetro con set di fazione fisso",
        "legacy_range": "15-20",
        "range_reason": "Rango e vetro sono identity lock 1-20; la profondità delle Skill rappresenta l'esperienza.",
        "checkpoints": ["Maestro riconoscibile", "rete di Gilda", "acrobazia", "colpo complesso", "signore dei ladri"],
        "at_least_one": ["una Skill Ladro entro il livello 1"],
    },
    {
        "name": "Saggia Ashlander", "source": "967", "ids": [967],
        "category": "Dunmer", "core": "mage", "core_share": 0.5, "magic": "any",
        "skills": unique_skills(base.MAGE_CORE, ANCESTOR_RITES),
        "races": ["Dunmer"], "subraces": ["Servo del Tribunale", "Retaggio Mago"],
        "equipment": covered_equipment("967"),
        "fantasy": "Guida spirituale Ashlander che custodisce memoria, antenati e sopravvivenza rituale della tribù.",
        "combat": "Richiama uno spirito antenato, crea oscurità o protezione e sostiene la tribù senza diventare un necromante da cripta.",
        "archetype": "Sciamana Dunmer con spiriti ancestrali, Negromanzia rituale e dotazione da viaggio.",
        "tags": {"core_magico": 5, "natura_magica": 4, "supporto": 4, "controllo_situazionale": 4, "sociale": 3, "attacco": 1},
        "competences": {"conoscenze_religioni": 5, "sapienza_magica": 5, "conoscenze_naturaegeografia": 5, "intuizione": 4, "diplomazia": 3},
        "siblings": [("Combattente Ashlander", "nearest", "Guida spirituale e antenati invece di difesa fisica."), ("Esploratore Ashlander", "same-tribe", "Memoria rituale invece di ricognizione."), ("Mago Scheletro", "contrast", "Evoca antenati per la tribù, non magia di cripta.")],
        "axes": [("memoria Ashlander", "religione, natura e spirito antenato"), ("sciamana itinerante", "staff Ne, veste e abiti caldi")],
        "must": ["Dunmer", "Ashlander", "spirito antenato", "religione"],
        "must_not": ["armatura", "arma melee", "Distruzione primaria", "azioni innate"],
        "variation": "staff qualificato con ramo spiriti o protezione",
        "legacy_range": "10-14",
        "range_reason": "La dotazione qualificata resta fissa 1-20; gli effetti maggiori rimangono level-gated.",
        "checkpoints": ["Saggia riconoscibile", "spirito antenato", "oscurità rituale", "guida della tribù", "custode della memoria"],
        "at_least_one": ["Evoca Spirito Antenato o una Skill Negromanzia entro il livello 5"],
    },
]


CREATURE_SPECS: list[dict[str, Any]] = [
    {
        "name": "Chaurus Mietitore", "source": "995", "ids": [995], "category": "Natura",
        "fantasy": "Forma dominante della colonia Chaurus, enorme, corazzata e capace di entrare in una furia territoriale.",
        "combat": "Controlla il corridoio come il Chaurus base, ma aggiunge Furia, massa e perforazione da predatore apicale.",
        "archetype": "Chaurus d'élite con Furia, ragnatela, gelo e grande resistenza.",
        "actions": rewrite_actions("995", {"Inietta veleno gelido": 1, "Sputo Velenoso": 4, "Trappola di Ragnatela": 7, "Furia": 10}),
        "siblings": [("Chaurus", "nearest", "Furia, massa e AP superiori definiscono il Mietitore."), ("Chaurus Cacciatore", "same-family", "Dominio terrestre invece di volo e tuffo."), ("Ragno Gigante", "contrast", "Corazza e pressione frontale invece di agilità da trappola.")],
        "axes": [("sovrano del nido", "PF, forza, difesa e AP superiori"), ("furia territoriale", "Furia aggiunta al kit Chaurus")],
        "must": ["Chaurus", "Furia", "ragnatela", "Gelo"],
        "must_not": ["volo", "Mana", "equipment"],
        "checkpoints": ["Mietitore giovane", "sputo", "ragnatela", "Furia", "sovrano del nido"],
        "range_reason": "Gli endpoint livello 20 vengono linearizzati mantenendo un vantaggio netto sul Chaurus base.",
        "at_least_one": ["Furia presente dal livello 10"],
    },
    {
        "name": "Chaurus Cacciatore", "source": "996", "ids": [996], "category": "Natura",
        "fantasy": "Forma alata nata dalla metamorfosi Chaurus, rapida e capace di colpire dall'alto.",
        "combat": "Vola dal primo livello, apre con Tuffo Aereo e usa gelo o sputo per impedire alla preda di riorganizzarsi.",
        "archetype": "Chaurus volante con tuffo, velocità e pressione biologica.",
        "actions": [deepcopy(FLIGHT)] + rewrite_actions("996", {"Tuffo Aereo": 1, "Inietta veleno gelido": 5, "Sputo Velenoso": 8}),
        "siblings": [("Chaurus", "nearest", "Volo e Tuffo sostituiscono ragnatela e pressione di corridoio."), ("Chaurus Mietitore", "same-family", "Mobilità aerea invece di massa e Furia."), ("Cliff Racer", "contrast", "Carapace e secrezioni Chaurus, non predatore aviario.")],
        "axes": [("metamorfosi alata", "Volo e velocità/agilità 30"), ("tuffo Chaurus", "Tuffo Aereo più gelo")],
        "must": ["Chaurus", "Volo", "Tuffo Aereo", "Gelo"],
        "must_not": ["ragnatela", "Furia", "Mana"],
        "checkpoints": ["Cacciatore alato", "Tuffo", "iniezione", "sputo", "predatore della colonia"],
        "range_reason": "Le curve vengono linearizzate e Volo è esplicitato perché necessario a Tuffo Aereo.",
        "at_least_one": ["Volo e Tuffo Aereo presenti dal livello 1"],
        "extra_deviations": [{
            "what": "locomozione del Cacciatore",
            "from": "Tuffo Aereo senza azione Volo separata",
            "to": "Volo innato dal livello 1",
            "why": "La metamorfosi alata è esplicita nel lore e Volo è già implementato.",
        }],
    },
    {
        "name": "Ragno Daedra", "source": "1001", "ids": [1001], "category": "Daedra",
        "fantasy": "Predatore intelligente di Oblivion legato a reti, segreti e trappole di Mephala.",
        "combat": "Prepara ragnatele, si riposiziona nell'ombra e combina gelo e secrezione corrosiva con pazienza sovrannaturale.",
        "archetype": "Controllore Daedra aracnide con Mana, Passo d'Ombra e ragnatela.",
        "actions": rewrite_actions("1001", {"Trappola di Ragnatela": 1, "Inietta veleno gelido": 4, "Sputo Velenoso": 8}) + [deepcopy(SHADOW_STEP)],
        "siblings": [("Ragno Gigante", "nearest", "Mana, intelligenza e Passo d'Ombra sostituiscono biologia naturale."), ("Segugio di Xivilai", "same-origin", "Trappole e controllo invece di inseguimento."), ("Crepuscolo Alato", "contrast", "Rete terrestre, non volo e coercizione mentale.")],
        "axes": [("rete di Mephala", "ragnatela e intelligenza elevata"), ("predatore di Oblivion", "Mana, resistenza al Fuoco e Passo d'Ombra")],
        "must": ["Daedra", "ragnatela", "Mana", "Passo d'Ombra"],
        "must_not": ["volo", "Carica", "Furia"],
        "checkpoints": ["ragno daedrico", "iniezione", "Passo d'Ombra", "sputo", "tessitore di Mephala"],
        "range_reason": "Gli endpoint vengono linearizzati; Passo d'Ombra usa un'azione Daedra già implementata.",
        "at_least_one": ["Trappola di Ragnatela presente dal livello 1"],
        "extra_deviations": [{
            "what": "mobilità daedrica",
            "from": "nessuna mobilità speciale nella riga Elder",
            "to": "Passo d'Ombra dal livello 6",
            "why": "Lore di Mephala, Mana elevato e precedente Daedra implementato sostengono il riposizionamento.",
        }],
    },
    {
        "name": "Guerriero Scheletro", "source": "1009", "ids": [1009], "category": "Non morto",
        "fantasy": "Soldato d'ossa animato per avanzare senza paura con una memoria frammentaria delle armi.",
        "combat": "Entra in mischia con un'arma da cripta, usa Furia e occasionalmente sfasa per evitare il colpo.",
        "archetype": "Non morto fisico con arma innata, Furia e Spostamento Fase.",
        "actions": [deepcopy(SKELETON_WEAPON)] + rewrite_actions("1009", {"Spostamento Fase": 4, "Furia": 7}),
        "siblings": [("Arciere Scheletro", "nearest", "Mischia e Furia invece di tiro a distanza."), ("Mago Scheletro", "same-family", "Mana zero e arma fisica invece di magia."), ("Draugr Guerriero", "contrast", "Ossa leggere e fase invece di corpo nordico corazzato.")],
        "axes": [("soldato d'ossa", "arma da cripta e resistenze scheletriche"), ("aggressione innaturale", "Furia e Spostamento Fase")],
        "must": ["scheletro", "arma innata", "Furia", "Mana zero"],
        "must_not": ["equipment", "Skill", "incantesimi"],
        "checkpoints": ["scheletro armato", "fase", "Furia", "soldato veterano", "guardiano della cripta"],
        "range_reason": "Le armi legacy diventano una singola azione innata; le curve livello 20 sono linearizzate.",
        "at_least_one": ["Arma da Cripta presente dal livello 1"],
        "extra_rejected": [{
            "candidate": {"slot": "arma", "names": ["Ascia (acciaio)", "Mazza (acciaio)", "Spada lunga (acciaio)"]},
            "decision": "reject",
            "reasonCode": "creature-equipment-contract",
            "reason": "Le armi diventano l'azione Arma da Cripta e non oggetti equipaggiati.",
        }],
    },
    {
        "name": "Viverna", "source": "1024", "ids": [1024], "category": "Natura",
        "fantasy": "Parente minore e imperfetto dei draghi, territoriale, alato e privo della loro intelligenza.",
        "combat": "Vola, apre con Tuffo, usa la coda contro chi la circonda e sputa secrezione corrosiva senza impiegare Thu'um.",
        "archetype": "Grande predatore volante con tuffo, coda e attacco corrosivo.",
        "actions": [deepcopy(FLIGHT)] + rewrite_actions("1024", {"Tuffo Aereo": 1, "Colpo di Coda": 5, "Sputo Velenoso": 8}),
        "siblings": [("Drago", "nearest", "Nessun Thu'um, respiro elementale o intelligenza draconica."), ("Chaurus Cacciatore", "same-mobility", "Più massa e coda, senza gelo Chaurus."), ("Manticora", "contrast", "Linea draconica minore invece di chimera alchemica.")],
        "axes": [("drago imperfetto", "grande Mana/PF ma nessun respiro draconico"), ("predatore aereo", "Volo, Tuffo e Colpo di Coda")],
        "must": ["Volo", "Tuffo Aereo", "Colpo di Coda", "sputo"],
        "must_not": ["Thu'um", "respiri elementali", "Pelle di Pietra"],
        "checkpoints": ["Viverna alata", "Tuffo", "coda", "sputo", "predatore delle gole"],
        "range_reason": "La riga livello 20 viene linearizzata e Volo esplicita il requisito di Tuffo Aereo.",
        "at_least_one": ["Volo e Tuffo Aereo presenti dal livello 1"],
        "extra_deviations": [{
            "what": "locomozione",
            "from": "Tuffo Aereo senza Volo separato",
            "to": "Volo innato dal livello 1",
            "why": "Anatomia e lore alata; azione già implementata.",
        }],
    },
    {
        "name": "Goblin", "source": "1027", "ids": [1027], "category": "Extra",
        "fantasy": "Razziatore tribale delle caverne che combatte con armi rozze e cooperazione istintiva.",
        "combat": "Avanza in mischia con ascia, mazza o spada e dipende dalla pressione numerica, non dalla magia del singolo.",
        "archetype": "Combattente tribale minore con arma innata e chassis agile ma fragile.",
        "curve_overrides": {"mana": (0, 0)},
        "actions": [deepcopy(GOBLIN_WEAPON)],
        "siblings": [("Guerriero Scheletro", "nearest", "Tribale vivente senza fase o resistenze non morte."), ("Scamp", "same-scale", "Mischia fisica e Mana zero invece di fuoco daedrico."), ("Guerriero (standard)", "contrast", "Creatura senza progressione Skill o equipment.")],
        "axes": [("tribù Goblin", "chassis minore e arma rozza"), ("pressione fisica", "Arma Tribale e Mana zero")],
        "must": ["Goblin", "arma tribale", "Mana zero", "equipment zero"],
        "must_not": ["Skill", "magia", "armatura"],
        "checkpoints": ["Goblin armato", "razzia", "combattente tribale", "veterano della tana", "campione Goblin"],
        "range_reason": "Le armi legacy diventano azione innata e il Mana inutilizzato viene azzerato.",
        "at_least_one": ["Arma Tribale presente dal livello 1"],
        "extra_rejected": [{
            "candidate": {"slot": "arma", "names": ["Ascia (acciaio)", "Mazza (legno)", "Spada lunga (ferro)"]},
            "decision": "reject",
            "reasonCode": "creature-equipment-contract",
            "reason": "Il Goblin resta creature e le armi sono astratte nell'azione Arma Tribale.",
        }],
        "extra_deviations": [{
            "what": "Mana legacy",
            "from": "curva Mana senza azioni magiche",
            "to": "Mana 0 costante",
            "why": "Evita una risorsa morta e mantiene il Goblin base distinto da uno Sciamano.",
        }],
    },
    {
        "name": "Slime di Alcol", "source": "1034", "ids": [1034], "category": "Daedra",
        "fantasy": "Massa vivente del piano di Sanguine, nata da eccesso, alcol e magia daedrica fermentata.",
        "combat": "Brucia, avvolge e si divide se abbattuta nel modo sbagliato; il Fuoco è insieme arma e vulnerabilità.",
        "archetype": "Slime Daedra con assimilazione, esplosione di Fuoco e moltiplicazione condizionata.",
        "actions": rewrite_actions(
            "1034",
            {"Esplosione Elementale - Fuoco": 1, "Assimila": 5, "Moltiplicazione di slime di Alcol": 8},
            {
                "Esplosione Elementale - Fuoco": "Area adiacente. Lo Slime esplode e infligge danni da Fuoco usando il tipo implementato.",
                "Assimila": "Dopo un attacco melee, lo Slime avvolge il bersaglio: infligge danni Puro e riduce i PA finché l'avversario non si libera.",
                "Moltiplicazione di slime di Alcol": "Passiva dal livello 8. Se distrutto senza Fuoco, genera due manifestazioni minori; usa il precedente di evocazione/minion.",
            },
        ),
        "siblings": [("Anomalia Magica di Sanguine", "nearest", "Massa fisica assimilante invece di teletrasporto arcano."), ("Atronach di Fuoco", "same-element", "Vulnerabile al Fuoco nonostante lo usi, e capace di dividersi."), ("Hunger", "contrast", "Inglobamento e fermentazione invece di drenaggio predatorio.")],
        "axes": [("eccesso fermentato", "Assimila e Mana"), ("slime instabile", "Fuoco, enorme vulnerabilità al Fuoco e moltiplicazione")],
        "must": ["Sanguine", "Assimila", "Fuoco", "moltiplicazione"],
        "must_not": ["equipment", "Skill", "volo"],
        "checkpoints": ["slime ardente", "Assimila", "moltiplicazione", "massa fermentata", "slime maggiore"],
        "range_reason": "Le curve sorgente 1-20 sono preservate; i testi vengono ricondotti a Fuoco, Puro e PA.",
        "at_least_one": ["Esplosione Elementale - Fuoco presente dal livello 1"],
    },
    {
        "name": "Anomalia Magica di Sanguine", "source": "1044", "ids": [1044], "category": "Daedra",
        "fantasy": "Nodo instabile del piano di Sanguine che seduce, devia e scarica magia senza possedere una mente.",
        "combat": "Resiste agli elementi, salta fra bersagli e converte l'eccesso arcano in danno Puro e perdita di Mana.",
        "archetype": "Anomalia Daedra mobile con resistenze elementali, teletrasporto e bruciatura di Mana.",
        "actions": sanguine_anomaly_actions(),
        "siblings": [("Anomalia Magica", "nearest", "Firma di Sanguine, teletrasporto e resistenze estreme invece di distorsione temporale."), ("Slime di Alcol", "same-plane", "Entità arcana mobile invece di massa assimilante."), ("Scamp", "contrast", "Nodo astratto resistente, non caster Daedra minore.")],
        "axes": [("eccesso arcano", "Mana/potere elevati e danno Puro"), ("instabilità di Sanguine", "teletrasporto casuale e difese elementali")],
        "must": ["Sanguine", "teletrasporto", "Mana", "Puro"],
        "must_not": ["equipment", "Skill", "attacco fisico"],
        "checkpoints": ["anomalia instabile", "resistenze", "teletrasporto", "bruciatura Mana", "nodo di Sanguine"],
        "range_reason": "Le curve sorgente coprono 1-20; l'attacco viene espresso con Puro e Mana supportati.",
        "at_least_one": ["Resistenza Magica presente dal livello 1 come tratto di curva"],
        "extra_deviations": [{
            "what": "nome del tratto difensivo",
            "from": "Immunità magica",
            "to": "Resistenza Magica",
            "why": "Le curve concedono resistenze e RD molto alte, non immunità assoluta.",
        }],
    },
    {
        "name": "Manticora", "source": "1052", "ids": [1052], "category": "Natura",
        "fantasy": "Chimera alchemica alata, territoriale e maliziosa, costruita per colpire da ogni angolo.",
        "combat": "Vola, respinge con le ali, spazza con la coda, sputa secrezione corrosiva e divora chi cade.",
        "archetype": "Predatore chimerico volante con controllo d'area, coda e recupero su caduto.",
        "actions": [deepcopy(FLIGHT)] + rewrite_actions("1052", {"Colpo d'Ala": 1, "Colpo di Coda": 4, "Sputo Velenoso": 7, "Divorare": 10}),
        "siblings": [("Viverna", "nearest", "Chimera con ala/coda/Divorare invece di drago minore."), ("Tigre denti a Sciabola", "same-predator", "Volo e controllo d'area invece di balzo/Furia."), ("Drago", "contrast", "Creazione alchemica senza Thu'um o respiri elementali.")],
        "axes": [("corpo chimerico", "ala, coda e sputo"), ("predatore alato", "Volo e Divorare")],
        "must": ["Volo", "Colpo d'Ala", "Colpo di Coda", "Divorare"],
        "must_not": ["Thu'um", "Furia", "Mana"],
        "checkpoints": ["chimera alata", "coda", "sputo", "Divorare", "Manticora dominante"],
        "range_reason": "Le curve 1-20 sorgente sono preservate e Volo esplicita l'anatomia alata.",
        "at_least_one": ["Volo e Colpo d'Ala presenti dal livello 1"],
        "extra_deviations": [{
            "what": "locomozione",
            "from": "Colpo d'Ala senza Volo separato",
            "to": "Volo innato dal livello 1",
            "why": "Anatomia alata e azione già implementata.",
        }],
    },
    {
        "name": "Sciame di Vespe", "source": "1054", "ids": [1054], "category": "Natura",
        "fantasy": "Nuvola vivente di insetti territoriali che agisce come un'unica volontà attorno al nido.",
        "combat": "Avvolge un bersaglio con molte punture, è difficile da fermare con colpi contundenti ma teme gli elementi.",
        "archetype": "Sciame fragile ma offensivo con attacco Perforante e resistenze collettive.",
        "actions": [deepcopy(SWARM_ASSAULT)],
        "siblings": [("Scrib", "nearest", "Sciame mobile con punture invece di creatura singola da supporto."), ("Nix-Hound", "same-pressure", "Assalto collettivo melee invece di secrezioni a distanza."), ("Cliff Racer", "contrast", "Nuvola di insetti, non singolo predatore volante.")],
        "axes": [("corpo collettivo", "res_contundente alta e PF bassi"), ("nuvola di punture", "Assalto dello Sciame Perforante")],
        "must": ["sciame", "Perforante", "Mana zero", "equipment zero"],
        "must_not": ["magia", "arma", "sputo"],
        "checkpoints": ["sciame giovane", "assalto", "nido irritato", "sciame fitto", "nuvola dominante"],
        "range_reason": "Le curve sorgente 1-20 sono preservate; l'azione innata colma l'assenza di SkillNpc.",
        "at_least_one": ["Assalto dello Sciame presente dal livello 1"],
        "extra_deviations": [{
            "what": "azione offensiva",
            "from": "nessuna SkillNpc nella sorgente",
            "to": "Assalto dello Sciame con danno Perforante",
            "why": "Il lore descrive punture collettive e Perforante è un tipo supportato.",
        }],
    },
]


BATCH_CANDIDATES = [humanoid_candidate(spec) for spec in HUMANOID_SPECS] + [
    creature_candidate(spec) for spec in CREATURE_SPECS
]

base.OUTPUT_ROOT = OUTPUT_ROOT
base.ALL_CANDIDATES = BATCH_CANDIDATES
base.VARIANTS = tuple(f"batch6-v2-{index}" for index in range(1, 9))
base.CONVERTER_VERSION = "elder-unit-charter-v2-batch6"


if __name__ == "__main__":
    base.main()

from __future__ import annotations

from copy import deepcopy
from typing import Any

import elder_unit_calibration_v2 as base
import elder_unit_batch2_v2 as toolkit
import elder_unit_batch3_v2 as rolekit
import elder_unit_batch4_v2 as previous


OUTPUT_ROOT = base.WORKSPACE_ROOT / "elder-unit-batch-5-v2" / "authored"
toolkit.BATCH_LABEL = "Batch 5 v2"

MORTAL_RACES = [
    "Bosmer", "Dunmer", "Orsimer", "Altmer", "Imperiale",
    "Bretone", "Redguard", "Argoniano", "Khajiit", "Nord",
]


def covered_equipment(source_file: str) -> list[dict[str, Any]]:
    return previous.covered_equipment(source_file)


def unique_skills(*pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return previous.unique_skills(*pools)


ASSASSIN = [
    base.skill(680, "archetype", 7),
    base.skill(683, "archetype", 9, 3),
    base.skill(684, "archetype", 7, 4),
    base.skill(686, "archetype", 6, 6),
    base.skill(687, "archetype", 6, 8),
    base.skill(688, "archetype", 5, 10),
    base.skill(689, "archetype", 5, 12),
    base.skill(690, "archetype", 4, 14),
]

ALTERATION = [
    base.skill(406, "archetype", 8),
    base.skill(407, "archetype", 9),
    base.skill(1308, "archetype", 7, 3),
    base.skill(408, "archetype", 7, 4),
    base.skill(1209, "archetype", 6, 5),
    base.skill(409, "archetype", 6, 6),
    base.skill(410, "archetype", 6, 7),
    base.skill(411, "archetype", 5, 8),
    base.skill(412, "archetype", 6, 9),
    base.skill(413, "archetype", 5, 11),
    base.skill(414, "archetype", 5, 12),
]

COURTLY = [
    base.skill(306, "archetype", 8),
    base.skill(321, "archetype", 7),
    base.skill(330, "archetype", 7),
    base.skill(331, "archetype", 8),
    base.skill(328, "archetype", 6, 4),
    base.skill(324, "archetype", 6, 5),
    base.skill(1210, "archetype", 6, 5),
    base.skill(427, "archetype", 5, 7),
]


def humanoid_candidate(spec: dict[str, Any]) -> dict[str, Any]:
    candidate = previous.humanoid_candidate(spec)
    return candidate


LEGAL_ACTION_TEXT = {
    "Sputo Velenoso": (
        "Bersaglio entro 4 esagoni. La secrezione corrosiva infligge danni Perforante; "
        "il nome conserva la firma biologica senza introdurre elementi fuori vocabolario."
    ),
    "Inietta veleno gelido": (
        "Dopo un attacco riuscito, il bersaglio subisce danni da Gelo e perde PA nel "
        "turno successivo. Usa soltanto il tipo Gelo e la risorsa PA già implementati."
    ),
    "Nuvola di Spore": (
        "Tutti i nemici entro 2 esagoni subiscono danni Puro dalle spore e perdono PA "
        "nel turno successivo; nessun nuovo status o tipo di danno viene introdotto."
    ),
    "Sangue Tossico": (
        "Passiva. Chi infligge danno in mischia alla creatura subisce danni Puro dalla "
        "secrezione irritante."
    ),
    "Morso Infettivo": (
        "Passiva. Dopo un morso riuscito, il bersaglio subisce una riduzione temporanea "
        "di Resistenza; la penalità usa una variabile già supportata."
    ),
}


def authored_actions(
    source_file: str,
    unlocks: dict[str, int],
    *,
    keep: list[str] | None = None,
) -> list[dict[str, Any]]:
    actions = toolkit.source_actions(source_file)
    selected = []
    for action in actions:
        name = str(action.get("name") or "")
        if keep is not None and name not in keep:
            continue
        if name in LEGAL_ACTION_TEXT:
            action["description"] = LEGAL_ACTION_TEXT[name]
        action["minLevel"] = int(unlocks.get(name, 1))
        action["maxLevel"] = 20
        selected.append(action)
    return selected


NETCH_FLIGHT = next(
    action
    for action in toolkit.source_actions("1028")
    if action["name"] == "Volo"
)
NETCH_FLIGHT["key"] = "batch5-netch-volo"
NETCH_FLIGHT["description"] = (
    "Passiva. Il Netch levita e può attraversare il campo in volo; la capacità "
    "usa l'azione Volo già presente nel vocabolario delle Unit."
)


def creature_candidate(spec: dict[str, Any]) -> dict[str, Any]:
    actions = list(spec.get("actions") or [])
    reauthored = [
        action["name"]
        for action in actions
        if action["name"] in LEGAL_ACTION_TEXT
    ]
    if reauthored:
        spec = deepcopy(spec)
        spec.setdefault("extra_rejected", []).append({
            "candidate": {
                "mechanic": "danni da veleno legacy",
                "actions": reauthored,
            },
            "decision": "reject",
            "reasonCode": "unsupported-poison-damage-reauthored",
            "reason": (
                "ReDjango non possiede il tipo di danno Veleno: le azioni usano "
                "Perforante, Puro, Gelo o penalità a variabili supportate."
            ),
        })
        spec.setdefault("extra_deviations", []).append({
            "what": "meccaniche veleno legacy",
            "from": "danni da veleno o status non verificati",
            "to": "Perforante/Puro/Gelo e penalità PA o Resistenza",
            "why": (
                "DAMAGE_TYPES consente soltanto Contundente, Perforante, Taglio, "
                "Gelo, Fuoco, Elettro e Puro."
            ),
        })
    return previous.creature_candidate(spec)


HUMANOID_SPECS: list[dict[str, Any]] = [
    {
        "name": "Pirata", "source": "855-856-857", "ids": [855, 856, 857],
        "category": "Umano", "core": "stealth", "core_share": 0.54, "magic": "none",
        "classes": ["Ladro"],
        "skills": unique_skills(toolkit.STEALTH_CORE, toolkit.THIEF, rolekit.DUELIST),
        "races": MORTAL_RACES, "equipment": covered_equipment("855-856-857"),
        "fantasy": "Predone di mare adattabile, abituato ad abbordaggi, fughe e combattimenti su ponti instabili.",
        "combat": "Apre con una lama corta, sfrutta mobilità e scorrettezze e passa ad accetta o sciabola durante l'abbordaggio.",
        "archetype": "Combattente furtivo da abbordaggio con sciabola, accetta o coltello e protezioni leggere.",
        "tags": {"core_fisico": 3, "focus_combat": 4, "attacco": 4, "esplorazione_infiltrazione": 4, "tecnica_crafting": 2, "core_magico": -5},
        "competences": {"percezione": 4, "rapidita_di_mano": 4, "furtivita": 3, "sopravvivenza": 3, "gestione_risorse": 3, "sapienza_magica": -5},
        "siblings": [("Contrabbandiere", "nearest", "Abbordaggio e pressione melee invece di trasporto clandestino e fuga."), ("Ladro (standard)", "same-core", "Sopravvivenza marittima e armi da ponte invece di furto urbano."), ("Duellante", "contrast", "Scorrettezze e adattamento invece di disciplina formale.")],
        "axes": [("abbordaggio", "sciabola/accetta e mobilità"), ("vita di mare", "percezione, sopravvivenza e gestione risorse")],
        "must": ["arma da abbordaggio", "mobilità", "equipaggiamento leggero", "livelli 1-20"],
        "must_not": ["magia", "scudo", "armatura pesante", "azioni innate"],
        "variation": "sciabola, accetta o coltello dentro la corretta fascia materiale",
        "legacy_range": "1-15",
        "range_reason": "La fascia adamantio finale viene estesa al 20 senza introdurre materiali o ruoli nuovi.",
        "checkpoints": ["pirata operativo", "mobilità da ponte", "predone esperto", "equipaggiamento adamantio", "capitano d'abbordaggio"],
        "at_least_one": ["una Skill da Ladro o Duellante entro il livello 5"],
    },
    {
        "name": "Stregone Bretone", "source": "872-873-874", "ids": [872, 873, 874],
        "category": "Bretone", "core": "mage", "core_share": 0.48, "magic": "any",
        "skills": unique_skills(base.MAGE_CORE, previous.RECOVERY, ALTERATION),
        "races": ["Bretone"], "subraces": ["Mago della Torre"],
        "equipment": covered_equipment("872-873-874"),
        "fantasy": "Mago corazzato di High Rock che intreccia recupero, protezione e scherma senza rinunciare alla disciplina della torre.",
        "combat": "Protegge sé e gli alleati, controlla il ritmo con Alterazione e alterna staff di Recupero e spada lunga.",
        "archetype": "Stregone Bretone ibrido Recupero-Protezione con armatura media e staff o spada.",
        "tags": {"core_magico": 5, "difesa": 4, "natura_magica": 4, "focus_combat": 3, "supporto": 4, "attacco": 2},
        "competences": {"sapienza_magica": 5, "conoscenze_storiaenobilta": 4, "intuizione": 4, "diplomazia": 3, "furtivita": -5},
        "siblings": [("Nobile Bretone", "nearest", "Recupero e disciplina di torre invece di autorità sociale e fioretto."), ("Guaritore", "same-school", "Armatura e capacità personale di combattimento invece di supporto puro."), ("Mago da Battaglia", "contrast", "Protezione e Recupero invece di Distruzione offensiva.")],
        "axes": [("mago della torre", "Bretone, sapienza e staff di Recupero"), ("protezione corazzata", "armatura, Scudo magico e cure")],
        "must": ["Bretone", "Mago della Torre", "Recupero", "protezione"],
        "must_not": ["furtività", "necromanzia", "Distruzione primaria", "azioni innate"],
        "variation": "staff di Recupero o spada lunga nella fascia corretta",
        "legacy_range": "5-20",
        "range_reason": "La fascia apprendista è anticipata ai livelli 1-4 mantenendo la stessa identità di torre.",
        "checkpoints": ["apprendista corazzato", "cura e scudo", "qualificato della torre", "maestro di Recupero", "stregone veterano"],
        "at_least_one": ["una Skill Recupero o Alterazione entro il livello 1"],
    },
    {
        "name": "Nobile Bretone", "source": "875-876-877", "ids": [875, 876, 877],
        "category": "Bretone", "core": "specialist", "core_share": 0.56, "magic": "any",
        "skills": unique_skills(base.PHYSICAL_CORE, rolekit.DUELIST, COURTLY),
        "races": ["Bretone"], "subraces": ["Cavaliere", "Mercante"],
        "equipment": covered_equipment("875-876-877"),
        "fantasy": "Aristocratico di High Rock educato a negoziare, comandare e difendere il proprio rango con fioretto e scudo.",
        "combat": "Tiene una linea elegante con fioretto e scudo, usa presenza e lettura sociale e non compete con uno stregone di torre.",
        "archetype": "Nobile Bretone difensivo-sociale con rapier, scudo e progressione di materiali prestigiosi.",
        "tags": {"core_fisico": 3, "focus_combat": 3, "difesa": 4, "sociale": 5, "attacco": 2, "core_magico": 1},
        "competences": {"diplomazia": 5, "conoscenze_storiaenobilta": 5, "intuizione": 4, "strategia_militare": 3, "furtivita": -5},
        "siblings": [("Stregone Bretone", "nearest", "Autorità sociale, fioretto e scudo invece di Recupero e staff."), ("Duellante", "same-weapon", "Difesa del rango e scudo invece di specializzazione offensiva."), ("Comandante della Legione Imperiale", "contrast", "Corte e lignaggio invece di comando istituzionale.")],
        "axes": [("rango bretone", "diplomazia e conoscenze nobiliari"), ("scherma protetta", "rapier e scudo in ogni fascia")],
        "must": ["Bretone", "fioretto", "scudo", "nobiltà"],
        "must_not": ["staff", "furtività", "necromanzia", "azioni innate"],
        "variation": "rapier, scudo e armatura coordinati per materiale",
        "legacy_range": "1-15",
        "range_reason": "La fascia adamantio conclusiva viene estesa al 20 come apice del prestigio nobiliare.",
        "checkpoints": ["nobile armato", "difesa di corte", "materiale vetro", "set adamantio", "signore di High Rock"],
        "at_least_one": ["una Skill difensiva o da Duellante entro il livello 5"],
    },
    {
        "name": "Stregone Dunmer", "source": "878-879-880", "ids": [878, 879, 880],
        "category": "Dunmer", "core": "mage", "core_share": 0.46, "magic": "any",
        "skills": unique_skills(base.MAGE_CORE, rolekit.ILLUSION, ALTERATION),
        "races": ["Dunmer"], "subraces": ["Retaggio Mago", "Nobile di Vvardenfell"],
        "equipment": covered_equipment("878-879-880"),
        "fantasy": "Incantatore Telvanni di medio rango che usa Illusione, Alterazione e prestigio di Casata come strumenti di controllo.",
        "combat": "Disorienta e rallenta, si protegge con Alterazione e usa staff o fioretto Telvanni quando il controllo non basta.",
        "archetype": "Stregone Dunmer Telvanni con Illusione, Alterazione e dotazione d'ossa.",
        "tags": {"core_magico": 5, "controllo_situazionale": 5, "natura_magica": 4, "difesa": 3, "sociale": 2, "core_fisico": -2},
        "competences": {"sapienza_magica": 5, "conoscenze_storiaenobilta": 4, "intimidire": 3, "intuizione": 3, "sopravvivenza": -4},
        "siblings": [("Mago Telvanni", "nearest", "Ibrido staff-fioretto e protezione invece di specialista Illusione puro."), ("Alto Stregone Telvanni", "same-house", "Rango e capstone inferiori, senza dominio da maestro."), ("Spadaccino Telvanni", "contrast", "Controllo arcano prima della lama.")],
        "axes": [("stregoneria Telvanni", "Dunmer, Illusione e armatura d'ossa"), ("controllo ibrido", "Alterazione più staff o fioretto")],
        "must": ["Dunmer", "Telvanni", "Illusione", "staff o fioretto"],
        "must_not": ["cura primaria", "scudo", "religione", "azioni innate"],
        "variation": "staff di Illusione o fioretto Telvanni per fascia",
        "legacy_range": "5-20",
        "range_reason": "La fascia apprendista viene anticipata ai livelli 1-4 senza concedere magie da Alto Stregone.",
        "checkpoints": ["apprendista Telvanni", "controllo mentale", "qualificato ibrido", "maestro Illusione", "stregone di Casata"],
        "at_least_one": ["una Skill Illusione entro il livello 1"],
    },
    {
        "name": "Schiavista Dunmer", "source": "881-882-883", "ids": [881, 882, 883],
        "category": "Dunmer", "core": "warrior", "core_share": 0.56, "magic": "none",
        "skills": unique_skills(base.PHYSICAL_CORE, toolkit.WARRIOR, rolekit.DUELIST),
        "races": ["Dunmer"], "subraces": ["Retaggio Guerriero", "Nobile di Vvardenfell"],
        "equipment": covered_equipment("881-882-883"),
        "fantasy": "Sorvegliante Dres brutale che usa rango, paura e mazzafrusta per spezzare ogni resistenza.",
        "combat": "Controlla la distanza corta con la mazzafrusta, intimidisce e resta mobile dentro un'armatura d'ossa.",
        "archetype": "Enforcer Dres con mazzafrusta, intimidazione e armatura di Casata.",
        "tags": {"core_fisico": 4, "focus_combat": 4, "attacco": 4, "controllo_situazionale": 3, "sociale": 2, "core_magico": -5},
        "competences": {"intimidire": 5, "percezione": 4, "strategia_militare": 3, "gestione_risorse": 3, "diplomazia": -5},
        "siblings": [("Esploratore Dres", "nearest", "Coercizione e mischia invece di ricognizione a distanza."), ("Sicario Camonna Tong", "same-culture", "Violenza pubblica e mazzafrusta invece di omicidio clandestino."), ("Cavaliere Redoran", "contrast", "Paura e dominio invece di onore difensivo.")],
        "axes": [("autorità Dres", "armatura d'ossa e intimidire"), ("mazzafrusta coercitiva", "arma identitaria in ogni fascia")],
        "must": ["Dunmer", "Dres", "mazzafrusta", "intimidazione"],
        "must_not": ["magia", "scudo", "arma a distanza", "azioni innate"],
        "variation": "mazzafrusta elfica, vetro o adamantio secondo fascia",
        "legacy_range": "1-15",
        "range_reason": "La mazzafrusta adamantio resta il tetto coerente fino al livello 20.",
        "checkpoints": ["sorvegliante Dres", "pressione melee", "mazzafrusta di vetro", "adamantio", "enforcer veterano"],
        "at_least_one": ["una manovra melee entro il livello 5"],
    },
    {
        "name": "Studioso Altmer", "source": "891-892-893-894", "ids": [891, 892, 893, 894],
        "category": "Altmer", "core": "mage", "core_share": 0.52, "magic": "any",
        "skills": unique_skills(base.MAGE_CORE, ALTERATION),
        "races": ["Altmer"], "subraces": ["Sangue Nobile", "Accolito di Aetherius"],
        "equipment": covered_equipment("891-892-893-894"),
        "fantasy": "Ricercatore Altmer che considera Alterazione, osservazione e metodo più importanti della distruzione spettacolare.",
        "combat": "Illumina, protegge, manipola oggetti e terreno e sopravvive grazie alla preparazione invece che al danno diretto.",
        "archetype": "Studioso Altmer di Alterazione con staff progressivo e forte profilo di conoscenza.",
        "tags": {"core_magico": 5, "tecnica_crafting": 4, "controllo_situazionale": 4, "difesa": 3, "supporto": 3, "attacco": -2},
        "competences": {"sapienza_magica": 5, "conoscenze_storiaenobilta": 5, "intuizione": 4, "percezione": 3, "intimidire": -5},
        "siblings": [("Mago (standard)", "nearest", "Alterazione e ricerca invece di generalismo scolastico."), ("Stregone Bretone", "same-method", "Studio non corazzato invece di protezione da battaglia."), ("Giustiziere Thalmor", "contrast", "Conoscenza e utilità invece di coercizione politica.")],
        "axes": [("ricerca Altmer", "sapienza e conoscenze nobiliari"), ("Alterazione applicata", "Luce, Scudo, Telecinesi e utility")],
        "must": ["Altmer", "Alterazione", "staff", "conoscenza"],
        "must_not": ["armatura", "arma melee", "Distruzione primaria", "azioni innate"],
        "variation": "staff e veste di Alterazione coordinati per grado",
        "legacy_range": "1-20",
        "range_reason": "Le quattro fasce sorgente coprono già integralmente i livelli 1-20.",
        "checkpoints": ["studioso principiante", "protezione e luce", "qualificato", "maestro di Alterazione", "erudito di Aetherius"],
        "at_least_one": ["una Skill Alterazione entro il livello 1"],
    },
    {
        "name": "Contrabbandiere", "source": "910-911-912", "ids": [910, 911, 912],
        "category": "Umano", "core": "stealth", "core_share": 0.58, "magic": "none",
        "classes": ["Ladro"],
        "skills": unique_skills(toolkit.STEALTH_CORE, toolkit.THIEF),
        "races": MORTAL_RACES, "equipment": covered_equipment("910-911-912"),
        "fantasy": "Corriere clandestino che misura il successo in carichi consegnati, controlli evitati e vie di fuga ancora aperte.",
        "combat": "Evita lo scontro, usa daga o accetta per creare spazio e sfrutta furtività, attrezzi e mobilità per sparire.",
        "archetype": "Ladro logistico con lame corte, equipaggiamento leggero e forte gestione delle risorse.",
        "tags": {"esplorazione_infiltrazione": 5, "tecnica_crafting": 4, "core_fisico": 2, "attacco": 2, "difesa": 1, "core_magico": -5},
        "competences": {"furtivita": 5, "rapidita_di_mano": 5, "raggirare": 4, "gestione_risorse": 5, "percezione": 3, "intimidire": -4},
        "siblings": [("Pirata", "nearest", "Fuga e trasporto invece di abbordaggio offensivo."), ("Ladro della Gilda", "same-core", "Rotte clandestine e logistica invece di furto organizzato."), ("Mercenario", "contrast", "Evita il combattimento anziché venderlo.")],
        "axes": [("logistica clandestina", "gestione risorse e attrezzi"), ("fuga discreta", "furtività, daga e Fuga Rapida")],
        "must": ["furtività", "gestione risorse", "lama corta", "livelli 1-20"],
        "must_not": ["magia", "scudo", "armatura pesante", "azioni innate"],
        "variation": "daga, coltello o accetta dentro la fascia materiale",
        "legacy_range": "1-15",
        "range_reason": "La fascia elfica conclusiva viene estesa al 20 senza trasformarlo in assassino.",
        "checkpoints": ["corriere clandestino", "attrezzi e fuga", "rotta esperta", "materiale elfico", "maestro del contrabbando"],
        "at_least_one": ["Fuga Rapida o Attrezzi del Mestiere entro il livello 5"],
    },
    {
        "name": "Shadowscale Argoniano", "source": "917-918", "ids": [917, 918],
        "category": "Argoniano", "core": "stealth", "core_share": 0.48, "magic": "none",
        "classes": ["Assassino"],
        "skills": unique_skills(toolkit.STEALTH_CORE, ASSASSIN),
        "races": ["Argoniano"], "subraces": ["Guerriero dell'Ombra"],
        "equipment": covered_equipment("917-918"),
        "fantasy": "Assassino consacrato alla nascita sotto l'Ombra, addestrato a colpire per il proprio ordine con precisione rituale.",
        "combat": "Si avvicina senza essere visto, sceglie Estoc o Shiv e chiude il bersaglio con un singolo assalto controllato.",
        "archetype": "Assassino Argoniano d'élite con armatura An-Xileel e lame da esecuzione.",
        "tags": {"esplorazione_infiltrazione": 5, "attacco": 5, "focus_combat": 4, "controllo_situazionale": 3, "difesa": 1, "core_magico": -5},
        "competences": {"furtivita": 5, "percezione": 5, "rapidita_di_mano": 4, "intuizione": 3, "diplomazia": -5},
        "siblings": [("Assassino della Confraternita Oscura", "nearest", "Disciplina Shadowscale e armatura An-Xileel invece di cellule cosmopolite."), ("Agente Morag Tong", "same-role", "Tradizione argoniana e assalto diretto invece di mandato dunmer."), ("Guerriero Forsworn", "contrast", "Precisione furtiva invece di imboscata tribale.")],
        "axes": [("nato sotto l'Ombra", "Argoniano Guerriero dell'Ombra e furtività"), ("esecuzione An-Xileel", "Estoc/Shiv e armatura dreugh")],
        "must": ["Argoniano", "Guerriero dell'Ombra", "An-Xileel", "assassinio"],
        "must_not": ["magia", "scudo", "arma pesante", "azioni innate"],
        "variation": "Estoc o Shiv in acciaio/ebano",
        "legacy_range": "10-20",
        "range_reason": "Il set An-Xileel è identitario e resta disponibile anche ai livelli bassi; scalano le Skill.",
        "checkpoints": ["Shadowscale completo", "colpo nascosto", "assassino disciplinato", "lama d'ebano", "maestro dell'Ombra"],
        "at_least_one": ["una Skill Assassino entro il livello 5"],
    },
    {
        "name": "Sicario Camonna Tong", "source": "922-923", "ids": [922, 923],
        "category": "Dunmer", "core": "stealth", "core_share": 0.5, "magic": "none",
        "classes": ["Assassino", "Ladro"],
        "skills": unique_skills(toolkit.STEALTH_CORE, ASSASSIN, toolkit.THIEF),
        "races": ["Dunmer"], "subraces": ["Retaggio Guerriero", "Nobile di Vvardenfell"],
        "equipment": covered_equipment("922-923"),
        "fantasy": "Sicario nazionalista della Camonna Tong che usa la rete Hlaalu come copertura e la violenza come messaggio.",
        "combat": "Infiltra ambienti civili, colpisce con coltello o daga Hlaalu e preferisce intimidire i superstiti anziché sparire senza traccia.",
        "archetype": "Assassino Dunmer criminale con lame Hlaalu, armatura d'ossa e pressione sociale.",
        "tags": {"esplorazione_infiltrazione": 5, "attacco": 5, "sociale": 2, "focus_combat": 4, "difesa": 1, "core_magico": -5},
        "competences": {"furtivita": 5, "intimidire": 5, "raggirare": 4, "percezione": 3, "diplomazia": -4},
        "siblings": [("Agente Hlaalu", "nearest", "Omicidio e intimidazione sostituiscono diplomazia e influenza."), ("Agente Morag Tong", "same-culture", "Crimine politico invece di mandato rituale legale."), ("Schiavista Dunmer", "contrast", "Lama clandestina invece di coercizione pubblica.")],
        "axes": [("nazionalismo criminale", "Dunmer e intimidire"), ("copertura Hlaalu", "vesti civili, armatura d'ossa e lame corte")],
        "must": ["Dunmer", "Camonna Tong", "lama Hlaalu", "intimidazione"],
        "must_not": ["magia", "scudo", "religione", "azioni innate"],
        "variation": "coltello Hlaalu o daga elfica/dwemer",
        "legacy_range": "8-17",
        "range_reason": "Le due fasce vengono estese agli estremi mantenendo soltanto materiali elfico e dwemer.",
        "checkpoints": ["sicario riconoscibile", "colpo clandestino", "lama dwemer", "killer politico", "veterano Camonna Tong"],
        "at_least_one": ["una Skill Assassino entro il livello 5"],
    },
    {
        "name": "Assassino della Confraternita Oscura", "source": "926-927", "ids": [926, 927],
        "category": "Umano", "core": "stealth", "core_share": 0.46, "magic": "none",
        "classes": ["Assassino"],
        "skills": unique_skills(toolkit.STEALTH_CORE, ASSASSIN),
        "races": MORTAL_RACES, "equipment": covered_equipment("926-927"),
        "fantasy": "Esecutore della Confraternita Oscura che trasforma anonimato, preparazione e devozione al contratto in morte improvvisa.",
        "combat": "Entra celato, usa Kriss o Shiv, concentra tutto sul primo sangue e si ritira prima che lo scontro diventi una mischia.",
        "archetype": "Assassino di fazione con armatura della Confraternita e lame corte ad alta precisione.",
        "tags": {"esplorazione_infiltrazione": 5, "attacco": 5, "focus_combat": 5, "controllo_situazionale": 3, "difesa": 1, "core_magico": -5},
        "competences": {"furtivita": 5, "percezione": 5, "rapidita_di_mano": 4, "intuizione": 4, "diplomazia": -5},
        "siblings": [("Shadowscale Argoniano", "nearest", "Reclutamento cosmopolita e contratto della Confraternita invece di tradizione argoniana."), ("Agente Morag Tong", "same-role", "Segretezza sacrilega invece di mandato pubblico dunmer."), ("Ascoltatore della Confraternita Oscura", "same-faction", "Operativo di campo, non vertice rituale.")],
        "axes": [("contratto oscuro", "armatura di fazione e disciplina Assassino"), ("primo sangue", "Kriss/Shiv e apertura furtiva")],
        "must": ["Confraternita Oscura", "Kriss o Shiv", "furtività", "primo sangue"],
        "must_not": ["magia", "scudo", "arma pesante", "azioni innate"],
        "variation": "Kriss o Shiv in chitina/vetro",
        "legacy_range": "5-14",
        "range_reason": "Chitina e vetro vengono estesi agli estremi senza concedere il grado dell'Ascoltatore.",
        "checkpoints": ["assassino di fazione", "colpo nascosto", "lama di vetro", "killer esperto", "esecutore veterano"],
        "at_least_one": ["Colpo nascosto o Primo sangue entro il livello 5"],
    },
]


CREATURE_SPECS: list[dict[str, Any]] = [
    {
        "name": "Alit", "source": "973", "ids": [973], "category": "Natura",
        "fantasy": "Predatore delle terre di cenere che combina massa, carica e secrezioni gelide.",
        "combat": "Chiude in linea retta con Carica, poi alterna iniezione gelida e sputo corrosivo per negare la fuga.",
        "archetype": "Predatore ashland pesante con carica e pressione biologica a corto raggio.",
        "actions": authored_actions("973", {"Carica": 1, "Inietta veleno gelido": 4, "Sputo Velenoso": 8}),
        "siblings": [("Kagouti", "nearest", "Secrezioni gelide e sputo invece di pura pressione fisica."), ("Nix-Hound", "same-biome", "Massa e carica invece di velocità e spore."), ("Guar", "contrast", "Predatore aggressivo, non animale da soma.")],
        "axes": [("massa ashland", "PF, forza e Carica"), ("secrezione gelida", "danno Gelo e perdita PA")],
        "must": ["Carica", "Gelo", "sputo corrosivo", "Mana zero"],
        "must_not": ["spore", "ragnatela", "volo"],
        "checkpoints": ["Alit giovane", "iniezione gelida", "sputo", "predatore maturo", "Alit dominante"],
        "range_reason": "La riga livello 20 viene linearizzata; le azioni si sbloccano senza aggiungere magia.",
        "at_least_one": ["Carica presente dal livello 1"],
    },
    {
        "name": "Nix-Hound", "source": "975", "ids": [975], "category": "Natura",
        "fantasy": "Cacciatore rapido di Morrowind che logora la preda con secrezioni, gelo e spore.",
        "combat": "Resta mobile, riduce PA con l'iniezione e crea una nuvola che punisce gruppi troppo vicini.",
        "archetype": "Predatore ashland veloce con controllo PA e nuvola di spore.",
        "actions": authored_actions("975", {"Inietta veleno gelido": 1, "Sputo Velenoso": 5, "Nuvola di Spore": 9}),
        "siblings": [("Alit", "nearest", "Velocità e spore invece di massa e Carica."), ("Scrib", "same-biome", "Predatore mobile invece di creatura debole da colonia."), ("Lupo", "contrast", "Controllo biologico a distanza invece di balzo e Furia.")],
        "axes": [("caccia rapida", "velocità/agilità superiori"), ("pressione di spore", "Puro e perdita PA ad area")],
        "must": ["velocità", "Gelo", "spore", "Mana zero"],
        "must_not": ["Carica", "pelle di pietra", "ragnatela"],
        "checkpoints": ["Nix-Hound giovane", "iniezione", "sputo", "nuvola di spore", "cacciatore ashland"],
        "range_reason": "Gli endpoint livello 20 sono distribuiti 1-20 mantenendo lo chassis veloce.",
        "at_least_one": ["Inietta veleno gelido presente dal livello 1"],
    },
    {
        "name": "Granchio del Fango", "source": "976", "ids": [976], "category": "Natura",
        "fantasy": "Crostaceo territoriale lento, protetto da un carapace duro e fluidi irritanti.",
        "combat": "Si chiude dietro Pelle di Pietra e punisce gli attaccanti in mischia; non insegue e non controlla a distanza.",
        "archetype": "Piccolo difensore naturale con carapace e danno reattivo Puro.",
        "actions": authored_actions("976", {"Pelle di Pietra": 1, "Sangue Tossico": 6}),
        "siblings": [("Scrib", "nearest", "Carapace difensivo e reazione melee invece di spore e suono."), ("Ragno Frostbite", "same-scale", "Difesa statica invece di mobilità e ragnatela."), ("Dreugh", "contrast", "Fauna minore, non combattente anfibio rigenerante.")],
        "axes": [("carapace", "rd_fis e Pelle di Pietra"), ("deterrente reattivo", "Sangue Tossico convertito in Puro")],
        "must": ["carapace", "Pelle di Pietra", "reazione melee", "Mana zero"],
        "must_not": ["sputo", "ragnatela", "Carica"],
        "checkpoints": ["granchio coriaceo", "Pelle di Pietra", "sangue irritante", "carapace maturo", "guardiano del fango"],
        "range_reason": "La singola riga viene linearizzata mantenendo velocità bassa e difesa alta.",
        "at_least_one": ["Pelle di Pietra presente dal livello 1"],
    },
    {
        "name": "Pesce Carnefice", "source": "977", "ids": [977], "category": "Natura",
        "fantasy": "Predatore acquatico che ferisce, indebolisce e divora chi cade nell'acqua.",
        "combat": "Logora con il morso, entra in Furia e recupera solo divorando un nemico già caduto.",
        "archetype": "Predatore acquatico rapido con morso debilitante, Furia e Divorare.",
        "actions": authored_actions("977", {"Morso Infettivo": 1, "Furia": 4, "Divorare": 8}),
        "siblings": [("Tigre denti a Sciabola", "nearest", "Predazione acquatica e Divorare invece di balzo e carica."), ("Nix-Hound", "same-role", "Mischia pura e recupero su caduto invece di controllo a distanza."), ("Dreugh", "contrast", "Animale predatore, non creatura anfibia corazzata.")],
        "axes": [("predatore acquatico", "velocità e chassis fragile"), ("alimentazione brutale", "Morso, Furia e Divorare")],
        "must": ["morso", "Furia", "Divorare", "Mana zero"],
        "must_not": ["sputo", "Carica", "armatura"],
        "checkpoints": ["predatore acquatico", "Furia", "morso debilitante", "Divorare", "carnefice delle acque"],
        "range_reason": "Gli endpoint livello 20 vengono linearizzati senza aumentare la protezione fisica.",
        "at_least_one": ["Morso Infettivo presente dal livello 1"],
    },
    {
        "name": "Scrib", "source": "979", "ids": [979], "category": "Natura",
        "fantasy": "Piccola creatura Kwama che difende i tunnel con spore, secrezioni gelide e stridio.",
        "combat": "Disturba gruppi con spore e suono, riduce PA e dipende dalla colonia per sopravvivere.",
        "archetype": "Supporto biologico Kwama fragile con controllo PA e stridio sonico.",
        "actions": authored_actions("979", {"Nuvola di Spore": 1, "Stridio Sonico": 5, "Inietta veleno gelido": 9}),
        "siblings": [("Operaio Kwama", "nearest", "Controllo di gruppo invece di rigenerazione operaia."), ("Guerriero Kwama", "same-colony", "Supporto fragile invece di carica difensiva."), ("Nix-Hound", "contrast", "Creatura di colonia lenta, non predatore mobile.")],
        "axes": [("difesa della colonia", "spore e stridio"), ("fragilità Scrib", "PF e forza basse")],
        "must": ["Kwama", "spore", "stridio", "Mana zero"],
        "must_not": ["Carica", "rigenerazione", "Furia"],
        "checkpoints": ["Scrib di colonia", "spore", "stridio", "iniezione gelida", "Scrib maturo"],
        "range_reason": "La riga livello 20 viene distribuita senza confonderlo con le caste Operaio o Guerriero.",
        "at_least_one": ["Nuvola di Spore presente dal livello 1"],
    },
    {
        "name": "Tigre denti a Sciabola", "source": "987", "ids": [987], "category": "Animale",
        "fantasy": "Grande felino preistorico che abbatte la preda con esplosività, zanne e massa.",
        "combat": "Apre con Balzo, entra in Furia e usa Carica soltanto quando dispone di spazio.",
        "archetype": "Predatore apicale mobile con balzo, Furia e carica.",
        "actions": authored_actions("987", {"Balzo Predatorio": 1, "Furia": 5, "Carica": 9}),
        "siblings": [("Lupo", "nearest", "Predatore solitario più massiccio invece di cacciatore di branco."), ("Orso delle Caverne", "same-scale", "Velocità e balzo invece di rigenerazione."), ("Pesce Carnefice", "contrast", "Predazione terrestre esplosiva invece di logoramento acquatico.")],
        "axes": [("zanne a sciabola", "forza e attacco alti"), ("esplosività felina", "Balzo, Furia e Carica")],
        "must": ["felino", "Balzo Predatorio", "Furia", "Mana zero"],
        "must_not": ["rigenerazione", "sputo", "spore"],
        "checkpoints": ["felino predatore", "Balzo", "Furia", "Carica", "tigre apicale"],
        "range_reason": "Lo chassis livello 20 viene linearizzato preservando il ruolo di predatore apicale.",
        "at_least_one": ["Balzo Predatorio presente dal livello 1"],
    },
    {
        "name": "Netch (Betty)", "source": "990", "ids": [990], "category": "Natura",
        "fantasy": "Netch femmina sospeso nell'aria, più arcano e orientato al logoramento del massiccio Bull.",
        "combat": "Attacca a distanza, riduce PA con il gelo e usa Pelle di Pietra quando viene raggiunto.",
        "archetype": "Netch controllore con Mana elevato, sputo, gelo e difesa temporanea.",
        "actions": [deepcopy(NETCH_FLIGHT)] + authored_actions(
            "990",
            {"Sputo Velenoso": 1, "Inietta veleno gelido": 4, "Pelle di Pietra": 8},
        ),
        "siblings": [("Netch (Bull)", "nearest", "Controllo a distanza e gelo invece di Carica e massa."), ("Cliff Racer", "same-space", "Levitazione difensiva invece di tuffo aereo."), ("Regina Kwama", "contrast", "Individuo arcano, non controllo di colonia.")],
        "axes": [("Betty arcana", "Mana e potere elevati"), ("logoramento sospeso", "sputo, Gelo e Pelle di Pietra")],
        "must": ["Netch", "Volo", "Mana", "Gelo", "sputo"],
        "must_not": ["Carica", "ragnatela", "Furia"],
        "checkpoints": ["Betty riconoscibile", "iniezione gelida", "sputo", "Pelle di Pietra", "Betty anziana"],
        "range_reason": "Gli endpoint livello 20 vengono linearizzati mantenendo Mana e ruolo di controllo.",
        "at_least_one": ["Sputo Velenoso presente dal livello 1"],
        "extra_deviations": [{
            "what": "locomozione Netch",
            "from": "nessuna azione di volo elencata nella riga Elder 990",
            "to": "Volo innato dal livello 1",
            "why": "La levitazione è anatomia identitaria del Netch e usa un'azione già implementata.",
        }],
    },
    {
        "name": "Netch (Bull)", "source": "991", "ids": [991], "category": "Natura",
        "fantasy": "Netch maschio enorme che protegge il branco con massa, carica e carapace.",
        "combat": "Entra con Carica, assorbe la risposta con Pelle di Pietra e usa lo sputo solo come opzione tardiva.",
        "archetype": "Netch bruto con PF elevati, carica e difesa temporanea.",
        "actions": [deepcopy(NETCH_FLIGHT)] + authored_actions(
            "991",
            {"Carica": 1, "Pelle di Pietra": 5, "Sputo Velenoso": 9},
        ),
        "siblings": [("Netch (Betty)", "nearest", "Massa e Carica invece di controllo gelido."), ("Kagouti", "same-role", "Levitazione e Mana invece di bestia terrestre."), ("Cliff Racer", "contrast", "Bruto sospeso, non predatore da tuffo.")],
        "axes": [("Bull massiccio", "PF, forza e resistenza superiori"), ("protezione del branco", "Carica e Pelle di Pietra")],
        "must": ["Netch", "Volo", "Carica", "Pelle di Pietra", "PF elevati"],
        "must_not": ["iniezione gelida", "ragnatela", "Furia"],
        "checkpoints": ["Bull riconoscibile", "Carica", "Pelle di Pietra", "sputo tardivo", "Bull dominante"],
        "range_reason": "La curva livello 20 viene linearizzata mantenendo il netto vantaggio di PF sulla Betty.",
        "at_least_one": ["Carica presente dal livello 1"],
        "extra_deviations": [{
            "what": "locomozione Netch",
            "from": "nessuna azione di volo elencata nella riga Elder 991",
            "to": "Volo innato dal livello 1",
            "why": "La levitazione è anatomia identitaria del Netch e usa un'azione già implementata.",
        }],
    },
    {
        "name": "Ragno Gigante", "source": "992", "ids": [992], "category": "Natura",
        "fantasy": "Predatore aracnide enorme che prepara il terreno, immobilizza e finisce la preda con secrezioni gelide.",
        "combat": "Posa ragnatele, riduce PA e usa lo sputo corrosivo per costringere il gruppo a muoversi.",
        "archetype": "Controllore aracnide grande con ragnatela, gelo e pressione a distanza.",
        "actions": authored_actions("992", {"Trappola di Ragnatela": 1, "Inietta veleno gelido": 4, "Sputo Velenoso": 8}),
        "siblings": [("Ragno Frostbite", "nearest", "Controllo del terreno e sputo invece di puro gelo aggressivo."), ("Chaurus", "same-kit", "Più agile e fragile, con ragnatela primaria."), ("Ragno Daedra", "contrast", "Creatura naturale senza proprietà daedriche.")],
        "axes": [("trappola aracnide", "Ragnatela dal livello 1"), ("predazione gelida", "Gelo, perdita PA e sputo")],
        "must": ["ragnatela", "Gelo", "sputo", "Mana zero"],
        "must_not": ["volo", "Carica", "Furia"],
        "checkpoints": ["ragno controllore", "iniezione", "ragnatela affidabile", "sputo", "predatore gigante"],
        "range_reason": "Lo chassis livello 20 viene linearizzato; la debolezza al Fuoco resta parte del contrasto.",
        "at_least_one": ["Trappola di Ragnatela presente dal livello 1"],
    },
    {
        "name": "Chaurus", "source": "994", "ids": [994], "category": "Natura",
        "fantasy": "Insetto cavernicolo corazzato che pressa frontalmente e controlla corridoi con secrezioni e filamenti.",
        "combat": "Riduce PA in mischia, sputa a media distanza e chiude le vie di fuga con una trappola tardiva.",
        "archetype": "Insetto Falmer robusto con gelo, sputo e controllo di corridoio.",
        "actions": authored_actions("994", {"Inietta veleno gelido": 1, "Sputo Velenoso": 5, "Trappola di Ragnatela": 8}),
        "siblings": [("Ragno Gigante", "nearest", "Robustezza frontale e iniezione primaria invece di ragnatela primaria."), ("Chaurus Mietitore", "same-family", "Forma base senza Furia o potenziamento da Mietitore."), ("Ragno Frostbite", "contrast", "Insetto corazzato invece di predatore aracnide rapido.")],
        "axes": [("carapace Chaurus", "forza/resistenza e res_taglio"), ("controllo di corridoio", "Gelo, sputo e ragnatela")],
        "must": ["Chaurus", "Gelo", "sputo", "ragnatela"],
        "must_not": ["Furia", "volo", "Mana"],
        "checkpoints": ["Chaurus base", "iniezione", "sputo", "ragnatela", "Chaurus maturo"],
        "range_reason": "Gli endpoint livello 20 vengono linearizzati senza concedere Furia o tratti del Mietitore.",
        "at_least_one": ["Inietta veleno gelido presente dal livello 1"],
    },
]


BATCH_CANDIDATES = [humanoid_candidate(spec) for spec in HUMANOID_SPECS] + [
    creature_candidate(spec) for spec in CREATURE_SPECS
]

base.OUTPUT_ROOT = OUTPUT_ROOT
base.ALL_CANDIDATES = BATCH_CANDIDATES
base.VARIANTS = tuple(f"batch5-v2-{index}" for index in range(1, 9))
base.CONVERTER_VERSION = "elder-unit-charter-v2-batch5"


if __name__ == "__main__":
    base.main()

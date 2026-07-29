from __future__ import annotations

from copy import deepcopy
from typing import Any

import elder_unit_calibration_v2 as base
import elder_unit_batch2_v2 as toolkit
import elder_unit_batch3_v2 as rolekit
import elder_unit_batch4_v2 as rankkit
import elder_unit_batch5_v2 as archetypekit
import elder_unit_batch6_v2 as previous


OUTPUT_ROOT = base.WORKSPACE_ROOT / "elder-unit-final-batch-v2" / "authored"
toolkit.BATCH_LABEL = "Final Batch v2"

MORTAL_RACES = deepcopy(previous.MORTAL_RACES)

MARTIAL_SUBRACES = [
    "Cacciatore",
    "Esploratore",
    "Retaggio Guerriero",
    "Selvaggio",
    "Plebeo",
    "Di Città",
    "Soldato a Piedi",
    "Guerriero delle Dune",
    "Guerriero dell'Ombra",
    "Cacciatore di Elsweyr",
    "Ladro Corridore",
    "Sud",
]

OUTLAW_MAGE_SUBRACES = [
    "Erborista",
    "Retaggio Mago",
    "Sciamano",
    "Accolito di Aetherius",
    "Apprendista",
    "Mago della Torre",
    "Erudito di Daggerfall",
    "Oasi",
    "Alchimista esploratore",
    "Tribale",
    "Custode della Parola",
]


def covered_equipment(source_file: str) -> list[dict[str, Any]]:
    return previous.covered_equipment(source_file)


def unique_skills(*pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return previous.unique_skills(*pools)


SPELLSWORD_ALTERATION = [
    base.skill(407, "archetype", 9),
    base.skill(1308, "archetype", 10),
    base.skill(408, "archetype", 7, 4),
    base.skill(410, "archetype", 7, 6),
    base.skill(409, "archetype", 6, 7),
    base.skill(413, "archetype", 5, 10),
]

DREMORA_COMMAND_MAGIC = [
    base.skill(439, "archetype", 8, 3),
    base.skill(440, "archetype", 7, 6),
    base.skill(444, "archetype", 6, 8),
    base.skill(442, "archetype", 5, 12),
]

XIVILAI_WAR_MAGIC = [
    base.skill(445, "archetype", 9),
    base.skill(456, "archetype", 7, 3),
    base.skill(440, "archetype", 7, 5),
    base.skill(442, "archetype", 7, 7),
    base.skill(460, "archetype", 6, 8),
    base.skill(444, "archetype", 5, 10),
    base.skill(463, "archetype", 5, 13),
]


def humanoid_candidate(spec: dict[str, Any]) -> dict[str, Any]:
    return previous.humanoid_candidate(spec)


def creature_candidate(spec: dict[str, Any]) -> dict[str, Any]:
    return previous.creature_candidate(spec)


def source_actions(
    source_file: str,
    definitions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    actions = previous.rewrite_actions(
        source_file,
        {name: int(definition["minLevel"]) for name, definition in definitions.items()},
        {name: str(definition["description"]) for name, definition in definitions.items()},
    )
    selected = []
    for action in actions:
        definition = definitions.get(action["name"])
        if definition is None:
            continue
        action["costs"] = deepcopy(definition.get("costs") or {})
        action["trigger"] = str(definition.get("trigger") or "Azione")
        action["duration"] = str(definition.get("duration") or "Istantanea")
        action["icon"] = str(definition.get("icon") or action.get("icon") or "runa")
        selected.append(action)
    return selected


FLIGHT = deepcopy(previous.FLIGHT)
FLIGHT["key"] = "final-batch-volo"

BOCCA_ACTIONS = source_actions(
    "1050",
    {
        "Inghiotti pericolo": {
            "minLevel": 1,
            "costs": {},
            "trigger": "Reazione",
            "description": (
                "Passiva frontale. Quando subisce un attacco proveniente dal fronte, la "
                "Bocca può assorbirne parte dell'impatto e recuperare PF; l'effetto non "
                "distrugge né trasferisce equipment."
            ),
        },
        "Vomito Acido": {
            "minLevel": 5,
            "costs": {"pa": 5, "mana": 3},
            "description": (
                "Area entro 2 esagoni. La Bocca erutta una sostanza corrosiva che "
                "infligge danni Puro a tutti i bersagli nell'area."
            ),
        },
    },
)

NEBBIA_ACTIONS = [deepcopy(FLIGHT)] + source_actions(
    "1047",
    {
        "Nebbia": {
            "minLevel": 1,
            "costs": {"potere": 2},
            "trigger": "Reazione",
            "description": (
                "Una volta per turno, quando viene bersagliata, la Nebbia può spendere "
                "Potere per teletrasportarsi entro 4 esagoni senza generare attacchi di "
                "opportunità. La sua natura incorporea è espressa dalle curve difensive."
            ),
        },
        "Assorbimento droga": {
            "minLevel": 4,
            "costs": {"pa": 4, "mana": 2},
            "description": (
                "Bersaglio entro 4 esagoni. Una prova di Resistenza e Concentrazione "
                "contrasta la foschia; in caso di fallimento il bersaglio perde PA nel "
                "turno successivo. Non introduce una nuova condizione persistente."
            ),
        },
        "Esplosione Nube di Droga": {
            "minLevel": 8,
            "costs": {},
            "trigger": "Alla sconfitta",
            "description": (
                "Alla sconfitta, tutti i bersagli adiacenti risolvono Assorbimento droga. "
                "La nube residua è narrativa e non genera automaticamente oggetti."
            ),
        },
    },
)

PENE_VOLANTE_ACTIONS = [deepcopy(FLIGHT)] + source_actions(
    "1028",
    {
        "Sparo Bianco": {
            "minLevel": 4,
            "costs": {"pa": 4, "mana": 2},
            "description": (
                "Bersaglio entro 9 esagoni. Una secrezione vischiosa raddoppia il costo "
                "in PA del movimento finché il bersaglio o un alleato adiacente spende "
                "10 PA complessivi per liberarlo."
            ),
        },
        "Carica del Pene": {
            "minLevel": 8,
            "costs": {"pa": 6, "energia": 4},
            "description": (
                "Carica in linea entro 12 esagoni. L'Attacco aumenta con la distanza "
                "percorsa; se la carica inizia in volo ottiene inoltre Attacco e Tier "
                "temporanei per la risoluzione del colpo."
            ),
        },
    },
)

TAMBURO_ACTIONS = source_actions(
    "1051",
    {
        "Danza continua": {
            "minLevel": 1,
            "costs": {"pa": 3, "mana": 2},
            "duration": "1 turno",
            "description": (
                "Tutti i nemici entro 5 esagoni effettuano una prova di Concentrazione. "
                "Chi fallisce può usare soltanto metà dei propri PA per muoversi nel "
                "turno successivo; i PA restanti vengono persi nel ritmo."
            ),
        },
        "Bacchetta Deviatrice": {
            "minLevel": 5,
            "costs": {"pa": 2},
            "trigger": "Reazione",
            "description": (
                "Quando riceve un attacco a distanza, il Tamburo tenta una prova di "
                "Velocità per deviarlo; con una successiva prova di Agilità può "
                "rispedirlo al lanciatore."
            ),
        },
        "Colpo Sonico": {
            "minLevel": 8,
            "costs": {"pa": 6, "mana": 4},
            "description": (
                "Area concentrica entro 3 esagoni. Il Tamburo recupera il 20% dei PF e "
                "infligge danni Puro, più intensi contro i bersagli adiacenti."
            ),
        },
    },
)

VERME_ASSAULT = {
    "key": "final-batch-avvolgimento-sanguine",
    "name": "Avvolgimento di Sanguine",
    "description": (
        "Bersaglio adiacente. Il verme si avvolge con uno spasmo daedrico, infligge "
        "danni Contundente e riduce i PA del bersaglio nel turno successivo. Questa "
        "azione usa soltanto variabili e tipi di danno già supportati."
    ),
    "minLevel": 1,
    "maxLevel": 20,
    "costs": {"pa": 4, "mana": 2},
    "trigger": "Azione",
    "duration": "Istantanea",
    "icon": "tentacolo",
}


HUMANOID_SPECS: list[dict[str, Any]] = [
    {
        "name": "Amazzone di Sanguine",
        "source": "1053",
        "ids": [1053],
        "category": "Daedra",
        "core": "stealth",
        "core_share": 0.46,
        "magic": "none",
        "classes": ["Ranger"],
        "skills": unique_skills(toolkit.ARCHER_CORE, toolkit.ARCHERY, toolkit.PURE_ARCHERY_CEILING),
        "races": MORTAL_RACES,
        "subraces": MARTIAL_SUBRACES,
        "equipment": covered_equipment("1053"),
        "fantasy": "Arciera umanoide legata alle arene di Sanguine, teatrale, mobile e pericolosa senza ricorrere a magia casuale.",
        "combat": "Mantiene distanza con l'arco corto elfico, provoca l'avversario e sfrutta mobilità e tiro multiplo.",
        "archetype": "Arciera d'arena di Sanguine con arco elfico, armatura leggera e pressione mobile.",
        "tags": {"range_skill": 5, "focus_combat": 5, "attacco": 5, "esplorazione_infiltrazione": 3, "sociale": 3, "core_magico": -5},
        "competences": {"percezione": 5, "suonare": 4, "intimidire": 4, "raggirare": 3, "sapienza_magica": -4},
        "siblings": [
            ("Arciere (standard)", "nearest", "Set elfico fisso e identità d'arena di Sanguine invece di neutralità professionale."),
            ("Arciere Bandito", "same-role", "Spettacolo e mobilità d'arena invece di imboscata e bottino."),
            ("Anomalia Magica di Sanguine", "contrast", "Umanoide equipaggiato e non entità arcana."),
        ],
        "axes": [("arena di Sanguine", "presenza sociale e armatura leggera iconica"), ("tiro mobile", "arco corto elfico e tecniche a distanza")],
        "must": ["Sanguine", "arco corto elfico", "armatura leggera", "mobilità"],
        "must_not": ["magia", "scudo", "arma pesante", "azioni innate"],
        "variation": "armatura di pelle o chitina con progressione di tiro",
        "legacy_range": "solo livello 10",
        "range_reason": "Arco e armatura restano identitari dal livello 1; la profondità delle Skill scala fino al 20.",
        "checkpoints": ["arciera d'arena", "tiro rapido", "mobilità scenica", "tiratrice veterana", "campionessa di Sanguine"],
        "at_least_one": ["una tecnica di tiro entro il livello 5"],
    },
    {
        "name": "Assassino dei Tsaesci",
        "source": "965",
        "ids": [965],
        "category": "Akavir",
        "core": "stealth",
        "core_share": 0.5,
        "magic": "none",
        "classes": ["Assassino"],
        "skills": unique_skills(toolkit.STEALTH_CORE, archetypekit.ASSASSIN, rolekit.DUELIST),
        "races": MORTAL_RACES,
        "subraces": MARTIAL_SUBRACES,
        "equipment": covered_equipment("965"),
        "fantasy": "Esecutore formato nelle discipline tsaesci, definito da pazienza rituale, precisione e lame akaviri d'ebano.",
        "combat": "Apre nascosto, alterna kriss e katana e chiude il duello con colpi precisi senza magia o veleno non supportato.",
        "archetype": "Assassino akaviri d'élite con armatura d'ebano, lama corta e katana.",
        "tags": {"esplorazione_infiltrazione": 5, "attacco": 5, "focus_combat": 5, "difesa": 2, "controllo_situazionale": 3, "core_magico": -5},
        "competences": {"furtivita": 5, "percezione": 5, "rapidita_di_mano": 4, "intuizione": 4, "intimidire": 3, "diplomazia": -4},
        "siblings": [
            ("Agente Morag Tong", "nearest", "Scuola akaviri e katana d'ebano invece di mandato legale dunmer."),
            ("Ascoltatore della Confraternita Oscura", "same-role", "Precisione rituale tsaesci invece di autorità religiosa."),
            ("Duellante", "contrast", "Eliminazione furtiva invece di sfida pubblica."),
        ],
        "axes": [("disciplina tsaesci", "katana/kriss e autocontrollo"), ("esecuzione precisa", "Assassino più Parata/Affondo")],
        "must": ["Tsaesci", "katana", "kriss", "d'ebano"],
        "must_not": ["magia", "scudo", "veleno inventato", "azioni innate"],
        "variation": "katana o kriss d'ebano con tecniche Assassino e Duellante",
        "legacy_range": "15-20",
        "range_reason": "Il set akaviri d'ebano è un identity lock; i livelli bassi riducono soltanto la profondità tecnica.",
        "checkpoints": ["assassino akaviri completo", "colpo nascosto", "duello evasivo", "primo sangue", "maestro tsaesci"],
        "at_least_one": ["una Skill Assassino entro il livello 5"],
    },
    {
        "name": "Signore Dremora",
        "source": "945",
        "ids": [945],
        "category": "Dremora",
        "core": "warrior",
        "core_share": 0.48,
        "magic": "any",
        "classes": ["Cavaliere"],
        "skills": unique_skills(base.PHYSICAL_CORE, rankkit.COMMANDER, DREMORA_COMMAND_MAGIC),
        "races": ["Dremora"],
        "subraces": ["Markynaz"],
        "equipment": [entry for entry in covered_equipment("945") if entry["slot"] != "scudo"],
        "kind_reason": "Ufficiale daedrico senziente con rango, Skill, armatura e armi: usa il contratto humanoid Dremora/Markynaz.",
        "fantasy": "Signore Markynaz che guida reparti daedrici con autorità, forza marziale e magia tattica dell'Oblivion.",
        "combat": "Comanda dalla prima linea con spadone o martello, usa sigilli e teletrasporto e richiama Daedra solo ai ranghi alti.",
        "archetype": "Comandante Dremora Markynaz con arma a due mani, armatura daedrica e magia tattica.",
        "tags": {"core_fisico": 5, "focus_combat": 5, "attacco": 5, "difesa": 4, "core_magico": 3, "sociale": 3},
        "competences": {"strategia_militare": 5, "intimidire": 5, "sapienza_magica": 4, "percezione": 3, "diplomazia": -4},
        "siblings": [
            ("Principe Dremora", "nearest", "Rango Markynaz e magia tattica invece del Valkynaz apicale puramente marziale."),
            ("Soldato Dremora", "same-race", "Comando e arma a due mani invece di fanteria con scudo."),
            ("Xivilai", "contrast", "Gerarchia di casta e comando invece di potenza daedrica indipendente."),
        ],
        "axes": [("rango Markynaz", "sottorazza bloccata, strategia e comando"), ("signore dell'Oblivion", "set daedrico e sigilli/teletrasporto")],
        "must": ["Dremora", "Markynaz", "comando", "arma daedrica"],
        "must_not": ["razza mortale", "scudo con arma a due mani", "magia di cura", "azioni innate"],
        "variation": "spadone o martello daedrico con magia di comando",
        "legacy_range": "19-20",
        "range_reason": "Rango e set sono front-loaded; la progressione 1-20 amplia manovre e magia senza promuoverlo a Valkynaz.",
        "checkpoints": ["Markynaz completo", "manovre di comando", "sigilli", "teletrasporto tattico", "signore daedrico"],
        "at_least_one": ["razza Dremora/Markynaz in ogni variante"],
        "extra_rejected": [{
            "candidate": {"slot": "scudo", "itemId": 622, "name": "Scudo (daedrico)"},
            "decision": "reject",
            "reasonCode": "two-handed-loadout-conflict",
            "reason": "Spadone e martello sono armi a due mani; lo scudo sorgente non può coesistere nel loadout.",
        }],
        "extra_deviations": [{
            "what": "scudo legacy",
            "from": "Scudo (daedrico) nella riga 945",
            "to": "rimosso dal pool",
            "why": "Conflitto con entrambe le armi a due mani preservate.",
        }],
    },
    {
        "name": "Spadaccino Telvanni",
        "source": "936",
        "ids": [936],
        "category": "Dunmer",
        "core": "specialist",
        "core_share": 0.48,
        "magic": "any",
        "skills": unique_skills(base.PHYSICAL_CORE, base.MAGE_CORE, rolekit.DUELIST, SPELLSWORD_ALTERATION),
        "races": ["Dunmer"],
        "subraces": ["Retaggio Mago", "Nobile di Vvardenfell"],
        "equipment": covered_equipment("936"),
        "fantasy": "Guardia del corpo Telvanni che fonde fioretto, protezione arcana e ambizione personale.",
        "combat": "Duella con il fioretto adamantio e usa Guida Arma, Scudo e mobilità di Alterazione per restare aggressivo.",
        "archetype": "Spadaccino Dunmer Telvanni con fioretto adamantio e Alterazione da duello.",
        "tags": {"core_fisico": 4, "core_magico": 4, "focus_combat": 5, "attacco": 5, "difesa": 3, "controllo_situazionale": 3},
        "competences": {"sapienza_magica": 5, "percezione": 4, "rapidita_di_mano": 4, "conoscenze_storiaenobilta": 3, "diplomazia": -2},
        "siblings": [
            ("Stregone Telvanni", "nearest", "Fioretto e Alterazione da duello invece di controllo Illusione."),
            ("Alto Stregone Telvanni", "same-house", "Campione armato invece di maestro mentale."),
            ("Mago da Battaglia", "contrast", "Stile personale Telvanni e lama leggera invece di dottrina militare."),
        ],
        "axes": [("duello Telvanni", "fioretto adamantio e Parata/Affondo"), ("lama arcana", "Guida Arma e protezioni di Alterazione")],
        "must": ["Dunmer", "Telvanni", "fioretto", "Alterazione"],
        "must_not": ["staff", "scudo equipaggiato", "Illusione primaria", "azioni innate"],
        "variation": "tecniche Duellante o protezioni di Alterazione sul set fisso",
        "legacy_range": "6-10",
        "range_reason": "Il set Telvanni resta fisso 1-20; la crescita alterna tecnica di lama e supporto arcano.",
        "checkpoints": ["spadaccino arcano", "Guida Arma", "difesa Telvanni", "duellante veterano", "campione della torre"],
        "at_least_one": ["Guida Arma o una Skill Duellante entro il livello 5"],
    },
    {
        "name": "Stregone Bandito",
        "source": "953-954",
        "ids": [953, 954],
        "category": "Banditi",
        "core": "mage",
        "core_share": 0.5,
        "magic": "any",
        "skills": unique_skills(base.MAGE_CORE, toolkit.DESTRUCTION),
        "races": MORTAL_RACES,
        "subraces": OUTLAW_MAGE_SUBRACES,
        "equipment": covered_equipment("953-954"),
        "fantasy": "Incantatore fuorilegge pragmatico che usa magia elementale brutale dietro la linea dei compagni.",
        "combat": "Attacca con raggi, rune e sfere elementali, affidandosi allo staff e senza acquisire disciplina accademica o supporto.",
        "archetype": "Mago bandito offensivo con Distruzione, staff progressivo e vesti da ladro.",
        "tags": {"core_magico": 5, "natura_magica": 5, "attacco": 5, "area_e_multi_target": 4, "difesa": 1, "sociale": -2},
        "competences": {"sapienza_magica": 5, "intimidire": 4, "sopravvivenza": 3, "percezione": 3, "diplomazia": -5},
        "siblings": [
            ("Mago (standard)", "nearest", "Distruzione brutale e dotazione criminale invece di generalismo."),
            ("Arciere Bandito", "same-faction", "Pressione elementale invece di imboscata fisica."),
            ("Cultista Daedrico", "contrast", "Nessuna fede, evocazione o patrono."),
        ],
        "axes": [("mago fuorilegge", "vestiti da ladro e competenze pragmatiche"), ("artiglieria elementale", "Distruzione pura e staff Ne")],
        "must": ["Bandito", "Distruzione", "staff", "magia offensiva"],
        "must_not": ["Evocazione", "cura", "armatura", "azioni innate"],
        "variation": "staff apprendista o qualificato con ramo elementale",
        "legacy_range": "5-14",
        "range_reason": "Le due fasce di staff e veste vengono estese agli estremi senza introdurre equipaggiamento maestro.",
        "checkpoints": ["stregone fuorilegge", "raggio elementale", "staff qualificato", "muro o sfera", "artiglieria della banda"],
        "at_least_one": ["una Skill Distruzione entro il livello 1"],
    },
    {
        "name": "Xivilai",
        "source": "946",
        "ids": [946],
        "category": "Daedra",
        "core": "specialist",
        "core_share": 0.5,
        "magic": "any",
        "skills": unique_skills(base.PHYSICAL_CORE, base.MAGE_CORE, toolkit.WARRIOR, XIVILAI_WAR_MAGIC),
        "races": ["Xivilai"],
        "equipment": covered_equipment("946"),
        "kind_reason": "Daedra senziente che impugna un martello e combina Skill marziali e magia: richiede il contratto humanoid e la razza Xivilai.",
        "fantasy": "Daedra maggiore indipendente che combina forza imponente, martello daedrico e magia evocativa.",
        "combat": "Spezza la linea con il martello, evoca armi o Daedra e cambia posizione con Teleport senza assumere rango Dremora.",
        "archetype": "Xivilai ibrido guerriero-evocatore con martello daedrico e magia aggressiva.",
        "tags": {"core_fisico": 5, "core_magico": 4, "focus_combat": 5, "attacco": 5, "natura_magica": 5, "difesa": 3},
        "competences": {"sapienza_magica": 5, "intimidire": 5, "percezione": 4, "strategia_militare": 3, "diplomazia": -5},
        "siblings": [
            ("Signore Dremora", "nearest", "Potenza indipendente ed Evocazione aggressiva invece di comando gerarchico."),
            ("Principe Dremora", "same-scale", "Specie Xivilai e magia invece di rango Valkynaz."),
            ("Ogrim", "contrast", "Intelligenza, equipment e Skill invece di chassis da creatura."),
        ],
        "axes": [("specie Xivilai", "razza autonoma senza ranghi Dremora"), ("bruto arcano", "martello daedrico più Evocazione/Distruzione")],
        "must": ["Xivilai", "martello daedrico", "Evocazione", "forza"],
        "must_not": ["razza Dremora", "razza mortale", "scudo", "azioni innate"],
        "variation": "manovre pesanti o magia daedrica sul martello fisso",
        "legacy_range": "solo livello 20",
        "range_reason": "Specie e martello sono front-loaded; la profondità marziale e arcana scala lungo 1-20.",
        "checkpoints": ["Xivilai completo", "arma evocata", "teletrasporto", "evocazione aggressiva", "Daedra maggiore"],
        "at_least_one": ["razza Xivilai e martello daedrico in ogni variante"],
        "extra_rejected": [{
            "candidate": {"allowedRace": "Dremora"},
            "decision": "reject",
            "reasonCode": "distinct-daedric-species",
            "reason": "Gli Xivilai non appartengono alla gerarchia o alla specie dei Dremora.",
        }],
        "extra_deviations": [{
            "what": "razza legacy",
            "from": "generico Entità",
            "to": "Xivilai",
            "why": "Il nome e il lore identificano esplicitamente una specie daedrica senziente distinta.",
        }],
    },
]


CREATURE_SPECS: list[dict[str, Any]] = [
    {
        "name": "Bocca Vorace di Sanguine",
        "source": "1050",
        "ids": [1050],
        "category": "Daedra",
        "fantasy": "Fauce daedrica vivente che trasforma la fame e il banchetto in difesa e aggressione.",
        "combat": "Assorbe frontalmente gli attacchi e riversa danno Puro in area con il vomito corrosivo.",
        "archetype": "Massa daedrica resistente con assorbimento frontale e attacco Puro ad area.",
        "actions": BOCCA_ACTIONS,
        "siblings": [
            ("Hunger", "nearest", "Fame grottesca e assorbimento frontale invece di drenaggio predatorio."),
            ("Slime di Alcol", "same-plane", "Fauce corazzata invece di assimilazione e moltiplicazione."),
            ("Tamburo di Sanguine", "contrast", "Pressione fisica e corrosiva invece di controllo sonoro."),
        ],
        "axes": [("fame di Sanguine", "Inghiotti pericolo e PF elevati"), ("eccesso corrosivo", "Vomito Acido con danno Puro")],
        "must": ["Sanguine", "fauci", "assorbimento", "Puro"],
        "must_not": ["equipment", "Skill", "volo", "distruzione permanente di oggetti"],
        "checkpoints": ["fauce vorace", "difesa frontale", "vomito corrosivo", "massa da banchetto", "bocca insaziabile"],
        "range_reason": "Le curve 1-20 sorgente sono preservate; l'ingestione non altera permanentemente l'inventario.",
        "at_least_one": ["Inghiotti pericolo presente dal livello 1"],
        "extra_deviations": [{
            "what": "ingestione di equipment",
            "from": "possibile rimozione temporanea delle armi legacy",
            "to": "assorbimento difensivo senza mutare equipment",
            "why": "Il generatore Unit non implementa trasferimenti o distruzione di oggetti in combattimento.",
        }],
    },
    {
        "name": "Nebbia di zucchero lunare",
        "source": "1047",
        "ids": [1047],
        "category": "Daedra",
        "fantasy": "Foschia daedrica di Sanguine che seduce, disorienta e si sottrae agli attacchi come vapore.",
        "combat": "Levità, reagisce con un breve teletrasporto e sottrae PA prima di esplodere alla sconfitta.",
        "archetype": "Entità incorporea mobile con controllo dei PA, reazione evasiva ed esplosione finale.",
        "actions": NEBBIA_ACTIONS,
        "siblings": [
            ("Anomalia Magica di Sanguine", "nearest", "Controllo morbido e corpo di vapore invece di bruciatura di Mana."),
            ("Spettro", "same-form", "Seduzione daedrica e PA invece di non morte."),
            ("Tamburo di Sanguine", "contrast", "Mobilità incorporea invece di oggetto sonoro stazionario."),
        ],
        "axes": [("corpo di foschia", "Volo, reazione Nebbia e difese incorporee"), ("zucchero lunare corrotto", "perdita di PA e nube alla sconfitta")],
        "must": ["Sanguine", "foschia", "teletrasporto", "PA"],
        "must_not": ["equipment", "Skill", "oggetti automatici", "danni da veleno"],
        "checkpoints": ["foschia volante", "Nebbia evasiva", "assorbimento", "nube finale", "miraggio di Sanguine"],
        "range_reason": "Le curve 1-20 sono preservate e gli status legacy vengono ricondotti a PA e prove supportate.",
        "at_least_one": ["Volo e Nebbia presenti dal livello 1"],
        "extra_deviations": [{
            "what": "condizioni da droga",
            "from": "comando, frenesia, paralisi e stordimento a soglie",
            "to": "perdita di PA su prova fallita",
            "why": "Evita condizioni non gestite automaticamente conservando il ruolo di controllo.",
        }],
    },
    {
        "name": "Pene Volante",
        "source": "1028",
        "ids": [1028],
        "category": "Daedra",
        "fantasy": "Aberrazione volante di Sanguine che usa shock, secrezioni e cariche aeree come scherzo crudele.",
        "combat": "Vola, limita il movimento a distanza e converte la rincorsa in una carica fisica crescente.",
        "archetype": "Aberrazione daedrica mobile con Volo, rallentamento in PA e Carica.",
        "actions": PENE_VOLANTE_ACTIONS,
        "siblings": [
            ("Verme Penico di Sanguine", "nearest", "Mobilità aerea e attacco a distanza invece di avvolgimento terrestre."),
            ("Manticora", "same-mobility", "Controllo umiliante invece di chimera predatoria."),
            ("Cliff Racer", "contrast", "Costrutto osceno di Sanguine, non fauna."),
        ],
        "axes": [("aberrazione di Sanguine", "identità grottesca preservata senza nuove regole"), ("assalto aereo", "Volo, Sparo Bianco e Carica")],
        "must": ["Sanguine", "Volo", "Sparo Bianco", "Carica"],
        "must_not": ["equipment", "Skill", "seduzione sociale", "danni fuori vocabolario"],
        "checkpoints": ["aberrazione volante", "sparo vischioso", "Carica", "incursore aereo", "incubo di Sanguine"],
        "range_reason": "La riga livello 20 viene linearizzata; Volo e identità restano presenti fin dal livello 1.",
        "at_least_one": ["Volo presente dal livello 1"],
    },
    {
        "name": "Tamburo di Sanguine",
        "source": "1051",
        "ids": [1051],
        "category": "Daedra",
        "fantasy": "Strumento daedrico vivente il cui ritmo trasforma piacere, danza e perdita di controllo in un'arma.",
        "combat": "Sottrae PA in area, devia proiettili e sprigiona un colpo sonico Puro che recupera PF.",
        "archetype": "Controllore sonoro di Sanguine con danza, reazione difensiva e onda Puro.",
        "actions": TAMBURO_ACTIONS,
        "siblings": [
            ("Nebbia di zucchero lunare", "nearest", "Controllo sonoro stazionario invece di foschia mobile."),
            ("Bocca Vorace di Sanguine", "same-plane", "Controllo e deviazione invece di massa frontale."),
            ("Anomalia Magica di Sanguine", "contrast", "Ritmo ad area invece di teletrasporto e Mana burn."),
        ],
        "axes": [("ritmo corruttore", "Danza continua e perdita di PA"), ("strumento vivente", "Bacchetta Deviatrice e Colpo Sonico")],
        "must": ["Sanguine", "danza", "suono", "Puro"],
        "must_not": ["equipment", "Skill", "controllo mentale permanente", "volo"],
        "checkpoints": ["tamburo vivente", "danza", "deviazione", "colpo sonico", "ritmo della rovina"],
        "range_reason": "Le curve 1-20 sono preservate; il controllo viene espresso con Concentrazione e PA.",
        "at_least_one": ["Danza continua presente dal livello 1"],
    },
    {
        "name": "Verme Penico di Sanguine",
        "source": "1055",
        "ids": [1055],
        "category": "Daedra",
        "fantasy": "Verme grottesco del piano di Sanguine, rapido e invasivo, più umiliante che intelligente.",
        "combat": "Avanza a terra e si avvolge al bersaglio, infliggendo Contundente e sottraendo PA con energia daedrica.",
        "archetype": "Aberrazione terrestre di Sanguine con avvolgimento fisico e controllo dei PA.",
        "actions": [deepcopy(VERME_ASSAULT)],
        "siblings": [
            ("Pene Volante", "nearest", "Avvolgimento terrestre invece di volo, tiro e carica."),
            ("Slime di Alcol", "same-plane", "Corpo vermiforme rapido invece di massa assimilante."),
            ("Scrib", "contrast", "Aberrazione daedrica e Mana invece di fauna minore."),
        ],
        "axes": [("verme di Sanguine", "identità grottesca e natura daedrica"), ("presa terrestre", "Avvolgimento con Contundente e PA")],
        "must": ["Sanguine", "verme", "Contundente", "PA"],
        "must_not": ["equipment", "Skill", "volo", "lore inventato complesso"],
        "checkpoints": ["verme daedrico", "avvolgimento", "presa persistente", "aberrazione rapida", "verme maggiore"],
        "range_reason": "Le curve 1-20 sorgente sono preservate; una singola azione conservativa colma l'assenza totale di SkillNpc e lore.",
        "at_least_one": ["Avvolgimento di Sanguine presente dal livello 1"],
        "extra_deviations": [{
            "what": "azione offensiva minima",
            "from": "nessuna SkillNpc e nessun lore nella sorgente",
            "to": "Avvolgimento con Contundente e riduzione PA",
            "why": "Il nome e la famiglia di Sanguine sostengono soltanto un attacco vermiforme conservativo; non vengono inventate capacità ulteriori.",
        }],
    },
]


BATCH_CANDIDATES = [humanoid_candidate(spec) for spec in HUMANOID_SPECS] + [
    creature_candidate(spec) for spec in CREATURE_SPECS
]

base.OUTPUT_ROOT = OUTPUT_ROOT
base.ALL_CANDIDATES = BATCH_CANDIDATES
base.VARIANTS = tuple(f"final-batch-v2-{index}" for index in range(1, 9))
base.CONVERTER_VERSION = "elder-unit-charter-v2-final"


if __name__ == "__main__":
    base.main()

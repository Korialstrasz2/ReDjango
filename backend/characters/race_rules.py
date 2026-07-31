from __future__ import annotations

from typing import Any


RACE_CATALOG: dict[str, dict[str, Any]] = {
    "Bosmer": {
        "modifiers": {"resistenza": -2, "velocita": -1, "agilita": 2, "saggezza": 1, "fortuna": 1},
        "trait": "Immunità alle malattie; una volta al giorno può calmare un animale aggressivo entro 9 metri.",
        "subraces": {
            "Foreste": "Conoscenza di Natura e Geografia; la progressione aggiunge Percezione.",
            "Colline": {"note": "Punti Azione aggiuntivi; la progressione aggiunge perk minori.", "effects": {"pa": 1}},
            "Cacciatore": "Portata aumentata con archi, balestre e armi da lancio; un reroll a distanza al giorno.",
            "Erborista": "Le pozioni create ottengono un effetto aggiuntivo.",
            "Esploratore": "Può saltare un pasto al giorno; la progressione aggiunge Energia.",
        },
    },
    "Dunmer": {
        "modifiers": {"fortuna": -2, "personalita": -1, "intelligenza": 2, "saggezza": 2},
        "trait": {
            "note": "Resistenza naturale al fuoco; una volta al giorno può evocare un fantasma di livello inferiore.",
            "effects": {"res_fuoco": 1, "rd_fuoco": 2},
        },
        "subraces": {
            "Retaggio Mago": {"note": "Retaggio magico.", "effects": {"mana": 8}},
            "Retaggio Guerriero": {"note": "Retaggio guerriero.", "effects": {"pf": 8}},
            "Nobile di Vvardenfell": "Conoscenze storiche e nobiliari; progressione sociale.",
            "Esule di Solstheim": {"note": "Adattamento al gelo e progressione da esploratore.", "effects": {"res_gelo": 1}},
            "Servo del Tribunale": "Conoscenza delle religioni e progressione religiosa e strategica.",
        },
    },
    "Orsimer": {
        "modifiers": {"intelligenza": -2, "personalita": -2, "forza": 2, "resistenza": 2, "saggezza": 1},
        "trait": "Danno fisico incrementale; una volta al giorno può rigenerare il 25% dei Punti Ferita.",
        "subraces": {
            "Selvaggio": {"note": "Addestramento offensivo.", "effects": {"attacco": 2}},
            "Della Tribù": {"note": "Addestramento difensivo.", "effects": {"difesa": 2}},
            "Forgiatore d'Armi": "Un Punto Modifica aggiuntivo in Forgiatura.",
            "Guardiano delle Miniere": {"note": "Resistenza da minatore.", "effects": {"rd_fis": 1}},
            "Sciamano": {"note": "Potere sciamanico.", "effects": {"potere": 2}},
        },
    },
    "Altmer": {
        "modifiers": {"saggezza": -1, "forza": -1, "resistenza": -2, "intelligenza": 2, "concentrazione": 2, "velocita": 1},
        "trait": {
            "note": "Potere arcano crescente; una volta al giorno può potenziare un incantesimo.",
            "effects": {"potere": "personaggio.livello"},
        },
        "subraces": {
            "Sangue Nobile": {"note": "Disciplina nobiliare.", "effects": {"concentrazione": 1}},
            "Plebeo": {"note": "Costituzione robusta.", "effects": {"resistenza": 1}},
            "Accolito di Aetherius": "Potere aggiuntivo con gli incantesimi di Distruzione.",
            "Custode del Sole": {"note": "Affinità solare e progressione elementale.", "effects": {"res_fuoco": 1}},
            "Custode della Luna": "Visioni giornaliere che migliorano con la progressione.",
        },
    },
    "Imperiale": {
        "modifiers": {"velocita": -1, "saggezza": -1, "forza": -1, "personalita": 2, "fortuna": 1, "concentrazione": 1},
        "trait": "Ottiene PE aggiuntivi a ogni livello; una volta al giorno può calmare un umanoide aggressivo.",
        "subraces": {
            "Di Città": "Conosce una lingua aggiuntiva; la progressione aggiunge Intuizione.",
            "Di Campagna": {"note": "Vita rurale.", "effects": {"forza": 1}},
            "Apprendista": "Migliora due barre abilità iniziali.",
            "Sanguemisto": "Può scegliere una sottorazza appartenente a un'altra razza.",
            "Guaritore del Tempio": "Potere aggiuntivo con gli incantesimi di Recupero.",
        },
    },
    "Bretone": {
        "modifiers": {"forza": -1, "resistenza": -2, "fortuna": -1, "intelligenza": 1, "concentrazione": 2, "personalita": 1, "saggezza": 1},
        "trait": {
            "note": "Riserva di Mana crescente; dispone di un Dispel razziale.",
            "effects": {"mana": "personaggio.livello * 2.5"},
        },
        "subraces": {
            "Cavaliere": "Un reroll in combattimento.",
            "Mercante": "Bonus e reroll di Contrattazione con la progressione.",
            "Mago della Torre": {"note": "Formazione magica.", "effects": {"concentrazione": 1}},
            "Erudito di Daggerfall": "Migliora entrambe le barre di una conoscenza casuale.",
            "Soldato a Piedi": "Attacco aumentato dagli alleati vicini che partecipano al combattimento.",
        },
    },
    "Redguard": {
        "modifiers": {"saggezza": -2, "concentrazione": -1, "forza": 2, "velocita": 1, "fortuna": 1},
        "trait": {
            "note": "Punti Ferita crescenti; può ottenere temporaneamente modificatore generale.",
            "effects": {"pf": "personaggio.livello * 2"},
        },
        "subraces": {
            "Deserto": "Sopravvivenza e Saggezza aumentano con la progressione.",
            "Oasi": {"note": "Costituzione delle oasi.", "effects": {"resistenza": 1}},
            "Guerriero delle Dune": "Può convertire il danno di un attacco in Energia.",
            "Esploratore di Hammerfell": "Progressione in Nuotare, Veicoli, Scalare e Cavalcare.",
            "Lottatore di Stros M'Kai": "Bonus ai tiri di Forza e Resistenza.",
        },
    },
    "Argoniano": {
        "modifiers": {"concentrazione": -1, "intelligenza": -1, "personalita": -1, "fortuna": 2, "velocita": 2},
        "trait": "Respira sott'acqua; può spendere Energia per rigenerare Punti Ferita, Mana e PA.",
        "subraces": {
            "Fortunato": "Un reroll al giorno fuori dal combattimento.",
            "Paludoso": "Immunità alle malattie.",
            "Figlio di Hist": "Conoscenza di Natura e Geografia; progressione nel modificatore generale.",
            "Guerriero dell'Ombra": "Può aumentare il tiro di un attacco, anche trasformandolo in critico.",
            "Alchimista esploratore": "Trova un ingrediente aggiuntivo ogni 30 minuti.",
        },
    },
    "Khajiit": {
        "modifiers": {"resistenza": -2, "personalita": -1, "intelligenza": 1, "agilita": 2, "forza": 1},
        "trait": "Visione notturna; un reroll giornaliero su Furtività e Rapidità di Mano.",
        "subraces": {
            "Tribale": {"note": "Fortuna e progressione in Agilità.", "effects": {"fortuna": 1}},
            "Carovana": "Rapidità di Mano e progressione in Raggirare.",
            "Monaco": {"note": "Disciplina monastica.", "effects": {"potere": 1, "energia": 1}},
            "Cacciatore di Elsweyr": "Inizia il combattimento con PA ed Energia gratuiti.",
            "Ladro Corridore": {"note": "Velocità e progressione offensiva.", "effects": {"velocita": 1}},
        },
    },
    "Nord": {
        "modifiers": {"velocita": -1, "agilita": -1, "personalita": -1, "resistenza": 2, "fortuna": 2},
        "trait": {
            "note": "Resistenza naturale al gelo; ottiene Energia gratuita per due turni.",
            "effects": {"res_gelo": 1, "rd_gelo": 2},
        },
        "subraces": {
            "Tradizionale": {"note": "Forza e progressione in Resistenza.", "effects": {"forza": 1}},
            "Sud": {"note": "Personalità e progressione artistica e tecnica.", "effects": {"personalita": 1}},
            "Berserker": "Può spendere Stanchezza per rimuovere immediatamente status mentali.",
            "Custode della Parola": "Può spendere Potere per migliorare i tiri caratteristica.",
            "Stirpe di Sempliciotti": "Sostituzioni speciali per i tiri di Intelligenza e Concentrazione.",
        },
    },
    "Falmer": {
        "modifiers": {"velocita": -1, "resistenza": -2, "saggezza": 2, "agilita": 2},
        "trait": "Percezione aumentata; una volta al giorno rigenera il 25% del Mana.",
        "subraces": {
            "Caverna": {"note": "Potere iniziale e visione notturna crescente.", "effects": {"potere": 2}},
            "Rovina": "Ingegneria e progressione in Furtività.",
            "Osservatore del Sole": "Può aggiungere danno da fuoco a un attacco.",
            "Sciamano della Notte": "Potere aggiuntivo con le magie di Maledizione.",
            "Sangue Corrotto": "Immunità ai veleni e creazione di pozioni dal proprio sangue.",
        },
    },
    "Dremora": {
        "modifiers": {
            "personalita": -2,
            "fortuna": -2,
            "saggezza": -1,
            "forza": 2,
            "resistenza": 2,
            "concentrazione": 1,
        },
        "trait": {
            "note": (
                "Resistenza naturale al fuoco; una volta al giorno può ottenere un reroll "
                "a Intimidire contro una creatura mortale."
            ),
            "effects": {"res_fuoco": 1, "rd_fuoco": 2},
        },
        "subraces": {
            "Churl": {
                "note": "Fante di rango inferiore, temprato dal servizio nelle legioni daedriche.",
                "effects": {"energia": 1},
            },
            "Caitiff": {
                "note": "Soldato esperto, abituato ad assalti rapidi e combattimenti prolungati.",
                "effects": {"velocita": 1},
            },
            "Kynval": {
                "note": "Guerriero di rango elevato, premiato per la ferocia in battaglia.",
                "effects": {"attacco": 1},
            },
            "Kynreeve": {
                "note": "Ufficiale di clan responsabile della disciplina e della difesa.",
                "effects": {"difesa": 1},
            },
            "Kynmarcher": {
                "note": "Comandante operativo capace di guidare reparti e campagne.",
                "effects": {"concentrazione": 1},
            },
            "Markynaz": {
                "note": "Signore del consiglio Markyn, dotato di autorità e potere daedrico.",
                "effects": {"potere": 1},
            },
            "Valkynaz": {
                "note": "Principe guerriero al vertice della gerarchia Dremora.",
                "effects": {"resistenza": 1},
            },
        },
        "native": True,
    },
    "Xivilai": {
        "modifiers": {
            "personalita": -2,
            "fortuna": -2,
            "saggezza": -1,
            "forza": 2,
            "resistenza": 2,
            "intelligenza": 1,
        },
        "trait": {
            "note": (
                "Daedra maggiore dalla fisicità imponente e dall'innata affinità con "
                "l'Oblivion; resiste naturalmente al fuoco."
            ),
            "effects": {"res_fuoco": 1, "rd_fuoco": 2},
        },
        "subraces": {},
        "native": True,
    },
    "Non morto": {
        "modifiers": {
            "personalita": -2,
            "fortuna": -1,
            "saggezza": -1,
            "forza": 1,
            "resistenza": 2,
            "concentrazione": 1,
        },
        "trait": {
            "note": (
                "Non necessita di respirare, mangiare o dormire ed è immune a veleni e malattie; "
                "una volta al giorno può ignorare un effetto di paura."
            ),
            "effects": {"rd_fis": 1},
        },
        "subraces": {
            "Scheletro": {
                "note": "Ossa animate, leggere e prive di carne; vulnerabilità narrative al danno contundente.",
                "effects": {"agilita": 1},
            },
            "Draugr": {
                "note": "Guerriero nordico sepolto, temprato dal gelo e dalla custodia delle tombe.",
                "effects": {"res_gelo": 1},
            },
            "Revenant": {
                "note": "Cadavere richiamato da un giuramento incompiuto o dalla volontà di un necromante.",
                "effects": {"forza": 1},
            },
            "Mummia": {
                "note": "Corpo conservato da riti funerari e bende protettive.",
                "effects": {"rd_fis": 1},
            },
            "Vampiro": {
                "note": "Predatore notturno mosso dal sangue, rapido e socialmente pericoloso.",
                "effects": {"velocita": 1},
            },
            "Lich": {
                "note": "Necromante che ha vincolato la propria anima alla non morte.",
                "effects": {"potere": 1},
            },
            "Spettro": {
                "note": "Anima disincarnata legata a un luogo, un oggetto o un rancore.",
                "effects": {"difesa": 1},
            },
        },
        "native": True,
    },
}

RACE_NAMES = tuple(RACE_CATALOG)

# Valore sentinella con cui le tendine di razza offrono "altro, scritto a mano".
RACE_EXTRA_VALUE = "__extra__"


def subraces_for(race: str) -> tuple[str, ...]:
    return tuple(RACE_CATALOG.get(str(race or "").strip(), {}).get("subraces", {}))


def race_configuration_payload() -> dict[str, Any]:
    return {
        "races": [
            {
                "value": race,
                "label": race,
                "subraces": [{"value": subrace, "label": subrace} for subrace in subraces_for(race)],
            }
            for race in RACE_NAMES
        ],
        "extraValue": RACE_EXTRA_VALUE,
    }


def _operations(values: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "target": target,
            "operation": "add" if not isinstance(value, (int, float)) or value >= 0 else "subtract",
            "value": str(value if not isinstance(value, (int, float)) or value >= 0 else abs(value)),
        }
        for target, value in values.items()
    ]


def _entry(key: str, name: str, description: str, origin_type: str, origin_name: str, effects: dict[str, Any]) -> dict[str, Any]:
    operations = _operations(effects)
    return {
        "key": key,
        "name": name,
        "description": description,
        "originType": origin_type,
        "originName": origin_name,
        "icon": "stella",
        "payload": {"effects": operations} if operations else {},
        "operations": operations,
    }


def automatic_race_effects(race: str, subrace: str) -> list[dict[str, Any]]:
    race = str(race or "").strip()
    subrace = str(subrace or "").strip()
    definition = RACE_CATALOG.get(race)
    if not definition:
        return []

    entries = [
        _entry(
            f"race:{race}:base",
            f"RAZZA: {race}",
            "Modificatori automatici della razza primaria.",
            "razza",
            race,
            definition["modifiers"],
        )
    ]
    trait = definition.get("trait")
    if trait:
        trait_data = trait if isinstance(trait, dict) else {"note": trait}
        entries.append(
            _entry(
                f"race:{race}:trait",
                f"{race}: tratto razziale",
                str(trait_data.get("note") or ""),
                "razza",
                race,
                dict(trait_data.get("effects") or {}),
            )
        )

    subrace_definition = definition.get("subraces", {}).get(subrace)
    if subrace and subrace_definition:
        subrace_data = subrace_definition if isinstance(subrace_definition, dict) else {"note": subrace_definition}
        entries.append(
            _entry(
                f"subrace:{race}:{subrace}",
                f"SUBRAZZA: {subrace}",
                str(subrace_data.get("note") or ""),
                "subrazza",
                f"{race} - {subrace}",
                dict(subrace_data.get("effects") or {}),
            )
        )
    return entries

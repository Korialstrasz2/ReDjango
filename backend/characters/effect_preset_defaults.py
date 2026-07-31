"""Catalogo dei preset effetto ereditati da Elder Django.

Ogni voce descrive un effetto pronto all'uso: l'editor degli effetti la usa per
precompilare il modulo "Nuovo effetto". I preset senza operazioni restano
descrittivi: la regola vive nella descrizione e viene arbitrata al tavolo.
"""

from __future__ import annotations

from typing import Any


EFFECT_PRESET_CATEGORIES = ("Condizioni", "Malattie", "Cibo", "Bagni", "Bevande")


# "Tick Giallo" toglie 1 a ogni competenza, non al modificatore generale.
# L'elenco rispecchia COMPETENCE_DEFINITIONS ma resta letterale: questo modulo è
# importato dalle migrazioni e non deve dipendere da un'altra app al caricamento.
# EffectPresetTests.test_tick_giallo_covers_every_competence segnala eventuali derive.
TICK_GIALLO_COMPETENCE_KEYS = (
    "scalare", "manovrare_veicoli", "nuotare", "rapidita_di_mano", "suonare",
    "cavalcare", "furtivita", "sapienza_magica", "ingegneria", "strategia_militare",
    "conoscenze_naturaegeografia", "conoscenze_religioni", "conoscenze_storiaenobilta",
    "percezione", "diplomazia", "intimidire", "camuffare", "raggirare",
    "sopravvivenza", "gestione_risorse", "intuizione",
)


DEFAULT_EFFECT_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "name": "Scosso",
        "description": "-3 attacco, 10% di sbagliare cast",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 1,
        "operations": [
            {"target": "attacco", "operation": "subtract", "value": "3", "condition": ""},
        ],
    },
    {
        "name": "Impaurito",
        "description": "+2 difesa, -6 attacco, 20% di sbagliare cast",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 2,
        "operations": [
            {"target": "difesa", "operation": "add", "value": "2", "condition": ""},
            {"target": "attacco", "operation": "subtract", "value": "6", "condition": ""},
        ],
    },
    {
        "name": "Sanguinante",
        "description": "-1 pf per turno per 5 turni, minimo 0 pf",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 3,
        "operations": [],
    },
    {
        "name": "Abbagliato/Penombra",
        "description": "Puoi attaccare solo entro 1m, oltre -20% errore per casella",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 4,
        "operations": [],
    },
    {
        "name": "Nauseato",
        "description": "Spendi il doppio di energia",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 5,
        "operations": [],
    },
    {
        "name": "Rallentato",
        "description": "Dimezza i punti azione disponibili",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 6,
        "operations": [
            {"target": "pa", "operation": "multiply", "value": "0.5", "condition": ""},
        ],
    },
    {
        "name": "Terrorizzato",
        "description": "Fuggi, se non puoi combatti usando tutte le risorse",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 7,
        "operations": [],
    },
    {
        "name": "Accecato/Buio",
        "description": "50% di fallire colpi o cast entro 1m, oltre 100%",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 8,
        "operations": [],
    },
    {
        "name": "Muto",
        "description": "Non puoi parlare, dare comandi agli animali, etc.",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 9,
        "operations": [],
    },
    {
        "name": "Stordito",
        "description": "50% di fallire qualsiasi azione non di movimento",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 10,
        "operations": [],
    },
    {
        "name": "Paralizzato",
        "description": "Azzera i punti azione disponibili",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 11,
        "operations": [
            {"target": "pa", "operation": "set", "value": "0", "condition": ""},
        ],
    },
    {
        "name": "Comandato",
        "description": "Esegue ciò che decide l'autore dell'incantesimo",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 12,
        "operations": [],
    },
    {
        "name": "Frenetico",
        "description": "Attacca con tutte le risorse il pg o npc più vicino",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 13,
        "operations": [],
    },
    {
        "name": "Mindscaped",
        "description": "Mindscaped",
        "origin": "Preset",
        "icon": "effetto",
        "category": "Condizioni",
        "order": 14,
        "operations": [],
    },
    {
        "name": "Atassia",
        "description": "Non fai frasi di senso compiuto",
        "origin": "Preset",
        "icon": "malattia",
        "category": "Malattie",
        "order": 15,
        "operations": [],
    },
    {
        "name": "Brividi",
        "description": "15% di fallire azioni",
        "origin": "Preset",
        "icon": "malattia",
        "category": "Malattie",
        "order": 16,
        "operations": [],
    },
    {
        "name": "Vermi infetti",
        "description": "1 stanchezza ogni 12 ore",
        "origin": "Preset",
        "icon": "malattia",
        "category": "Malattie",
        "order": 17,
        "operations": [],
    },
    {
        "name": "Articolazioni di Roccia",
        "description": "-1 modifica generale",
        "origin": "Preset",
        "icon": "malattia",
        "category": "Malattie",
        "order": 18,
        "operations": [
            {"target": "modificatore_generale", "operation": "subtract", "value": "1", "condition": ""},
        ],
    },
    {
        "name": "Articolazioni Infernali",
        "description": "-2 modifica generale",
        "origin": "Preset",
        "icon": "malattia",
        "category": "Malattie",
        "order": 19,
        "operations": [
            {"target": "modificatore_generale", "operation": "subtract", "value": "2", "condition": ""},
        ],
    },
    {
        "name": "Demenza",
        "description": "Ogni turno, se fallisci tiro concentrazione 5, non fai azione",
        "origin": "Preset",
        "icon": "malattia",
        "category": "Malattie",
        "order": 20,
        "operations": [],
    },
    {
        "name": "Febbre Pesante",
        "description": "Raddoppia il costo in energia",
        "origin": "Preset",
        "icon": "malattia",
        "category": "Malattie",
        "order": 21,
        "operations": [],
    },
    {
        "name": "Sfuggimente",
        "description": "-4 intelligenza e concentrazione",
        "origin": "Preset",
        "icon": "malattia",
        "category": "Malattie",
        "order": 22,
        "operations": [
            {"target": "intelligenza", "operation": "subtract", "value": "4", "condition": ""},
            {"target": "concentrazione", "operation": "subtract", "value": "4", "condition": ""},
        ],
    },
    {
        "name": "Tick Giallo",
        "description": "-1 a tutte le abilità",
        "origin": "Preset",
        "icon": "malattia",
        "category": "Malattie",
        "order": 23,
        "operations": [
            {"target": f"competenza.{key}", "operation": "subtract", "value": "1", "condition": ""}
            for key in TICK_GIALLO_COMPETENCE_KEYS
        ],
    },
    {
        "name": "Spasmi",
        "description": "-1 a tutti i tiri",
        "origin": "Preset",
        "icon": "malattia",
        "category": "Malattie",
        "order": 24,
        # "Tutti i tiri" non è esprimibile: nessun bersaglio copre ogni tiro di dado.
        # Resta descrittivo e arbitrato al tavolo.
        "operations": [],
    },
    {
        "name": "C-Stufato di Carne",
        "description": "Uno stufato sostanzioso che aumenta la salute.",
        "origin": "Preset",
        "icon": "cibo",
        "category": "Cibo",
        "order": 25,
        "operations": [
            {"target": "pf", "operation": "add", "value": "personaggio.livello/1.5+5", "condition": ""},
        ],
    },
    {
        "name": "C-Spezzatino",
        "description": "Uno spezzatino ricco che ripristina salute e stamina.",
        "origin": "Preset",
        "icon": "cibo",
        "category": "Cibo",
        "order": 26,
        "operations": [
            {"target": "pf", "operation": "add", "value": "personaggio.livello+7", "condition": ""},
            {"target": "pa", "operation": "add", "value": "personaggio.livello/5+1", "condition": ""},
        ],
    },
    {
        "name": "C-Taglio Scelto",
        "description": "Un taglio di carne pregiato che aumenta significativamente salute e stamina.",
        "origin": "Preset",
        "icon": "cibo",
        "category": "Cibo",
        "order": 27,
        "operations": [
            {"target": "pf", "operation": "add", "value": "personaggio.livello*1.3+9", "condition": ""},
            {"target": "pa", "operation": "add", "value": "personaggio.livello/4+2", "condition": ""},
        ],
    },
    {
        "name": "C-Zuppa di Pesce",
        "description": "Una zuppa di pesce che ripristina il mana.",
        "origin": "Preset",
        "icon": "cibo",
        "category": "Cibo",
        "order": 28,
        "operations": [
            {"target": "mana", "operation": "add", "value": "personaggio.livello/1.5+5", "condition": ""},
        ],
    },
    {
        "name": "C-Pesce al Forno",
        "description": "Pesce al forno che ripristina mana e stamina.",
        "origin": "Preset",
        "icon": "cibo",
        "category": "Cibo",
        "order": 29,
        "operations": [
            {"target": "mana", "operation": "add", "value": "personaggio.livello+7", "condition": ""},
            {"target": "pa", "operation": "add", "value": "personaggio.livello/5+1", "condition": ""},
        ],
    },
    {
        "name": "C-Trancio di Pesce",
        "description": "Un grande trancio di pesce che aumenta notevolmente mana e stamina.",
        "origin": "Preset",
        "icon": "cibo",
        "category": "Cibo",
        "order": 30,
        "operations": [
            {"target": "mana", "operation": "add", "value": "personaggio.livello*1.3+9", "condition": ""},
            {"target": "pa", "operation": "add", "value": "personaggio.livello/4+2", "condition": ""},
        ],
    },
    {
        "name": "C-Stufato di Verdure",
        "description": "Uno stufato di verdure che ripristina energia.",
        "origin": "Preset",
        "icon": "cibo",
        "category": "Cibo",
        "order": 31,
        "operations": [
            {"target": "energia", "operation": "add", "value": "personaggio.livello/1.5+5", "condition": ""},
        ],
    },
    {
        "name": "C-Zuppa di Legumi",
        "description": "Una zuppa di legumi che ripristina energia e stamina.",
        "origin": "Preset",
        "icon": "cibo",
        "category": "Cibo",
        "order": 32,
        "operations": [
            {"target": "energia", "operation": "add", "value": "personaggio.livello+7", "condition": ""},
            {"target": "pa", "operation": "add", "value": "personaggio.livello/5+1", "condition": ""},
        ],
    },
    {
        "name": "C-Ratatouille",
        "description": "Un delizioso mix di verdure che aumenta notevolmente energia e stamina.",
        "origin": "Preset",
        "icon": "cibo",
        "category": "Cibo",
        "order": 33,
        "operations": [
            {"target": "energia", "operation": "add", "value": "personaggio.livello*1.3+9", "condition": ""},
            {"target": "pa", "operation": "add", "value": "personaggio.livello/4+2", "condition": ""},
        ],
    },
    {
        "name": "B-Bagno con Sali",
        "description": "Un bagno rilassante con sali per ripristinare l'energia.",
        "origin": "Preset",
        "icon": "cibo",
        "category": "Bagni",
        "order": 34,
        "operations": [
            {"target": "energia", "operation": "add", "value": "personaggio.livello/1.5+5", "condition": ""},
        ],
    },
    {
        "name": "B-Bagno Lussuoso",
        "description": "Un bagno lussuoso per rinfrescarsi e rinvigorirsi.",
        "origin": "Preset",
        "icon": "cibo",
        "category": "Bagni",
        "order": 35,
        "operations": [
            {"target": "energia", "operation": "add", "value": "personaggio.livello+7", "condition": ""},
        ],
    },
    # --- Bevande: bevande e droghe della curation "speciale" del 2026-08-01 --
    # Le bevande Elder descrivono un bonus a tempo seguito, quasi sempre 10
    # turni dopo, da una "sbornia" (-50% Energia massima): due preset separati,
    # non uno solo, perché non sono mai attivi insieme. Nessun preset codifica
    # la durata (i preset non hanno un concetto di tempo): il master applica e
    # rimuove a mano, come per ogni altro preset "temporaneo". Alcuni effetti
    # (risorsa "gratis a turno", conversione PA->Energia, "tutti i tiri") non
    # hanno un bersaglio che li esprima fedelmente e restano descrittivi,
    # sul modello di "Spasmi" e "Vermi infetti" qui sopra.
    {
        "name": "Sbornia",
        "description": "Dopo 10 turni, dimezza l'Energia massima (-50%).",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 36,
        "operations": [
            {"target": "energia", "operation": "percent", "value": "-50", "condition": ""},
        ],
    },
    {
        "name": "Idromele Nordico",
        "description": "+2 Forza per 10 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 37,
        "operations": [
            {"target": "forza", "operation": "add", "value": "2", "condition": ""},
        ],
    },
    {
        "name": "Vino Surilie",
        "description": "+2 Intelligenza per 10 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 38,
        "operations": [
            {"target": "intelligenza", "operation": "add", "value": "2", "condition": ""},
        ],
    },
    {
        "name": "Shein",
        "description": "+25% punti ferita temporanei per 10 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 39,
        "operations": [
            {"target": "pf", "operation": "percent", "value": "25", "condition": ""},
        ],
    },
    {
        "name": "Birra Rovo Nero",
        "description": "+2 Forza e Resistenza, -1 Velocità e Agilità per 10 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 40,
        "operations": [
            {"target": "forza", "operation": "add", "value": "2", "condition": ""},
            {"target": "resistenza", "operation": "add", "value": "2", "condition": ""},
            {"target": "velocita", "operation": "subtract", "value": "1", "condition": ""},
            {"target": "agilita", "operation": "subtract", "value": "1", "condition": ""},
        ],
    },
    {
        "name": "Brandy Coloviano",
        "description": "+2 Personalità per 1 ora.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 41,
        "operations": [
            {"target": "personalita", "operation": "add", "value": "2", "condition": ""},
        ],
    },
    {
        "name": "Vino delle Summerset",
        "description": "+25% mana temporaneo per 10 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 42,
        "operations": [
            {"target": "mana", "operation": "percent", "value": "25", "condition": ""},
        ],
    },
    {
        "name": "Sweet Roll",
        "description": "+1 al modificatore generale per 5 turni, nessun effetto collaterale.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 43,
        "operations": [
            {"target": "modificatore_generale", "operation": "add", "value": "1", "condition": ""},
        ],
    },
    {
        "name": "Vino Economico",
        "description": "+10% punti ferita temporanei per 10 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 44,
        "operations": [
            {"target": "pf", "operation": "percent", "value": "10", "condition": ""},
        ],
    },
    {
        "name": "Vino Pregiato",
        "description": "+10% punti ferita e mana temporanei per 10 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 45,
        "operations": [
            {"target": "pf", "operation": "percent", "value": "10", "condition": ""},
            {"target": "mana", "operation": "percent", "value": "10", "condition": ""},
        ],
    },
    {
        "name": "Distillato di Marshmarrow",
        "description": "+10% punti ferita, mana, PA e potere temporanei per 10 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 46,
        "operations": [
            {"target": "pf", "operation": "percent", "value": "10", "condition": ""},
            {"target": "mana", "operation": "percent", "value": "10", "condition": ""},
            {"target": "pa", "operation": "percent", "value": "10", "condition": ""},
            {"target": "potere", "operation": "percent", "value": "10", "condition": ""},
        ],
    },
    {
        "name": "Distillato Nord",
        "description": "+2 Attacco, +2 Riduzione danno fisica, +2 Resistenza al gelo per 10 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 47,
        "operations": [
            {"target": "attacco", "operation": "add", "value": "2", "condition": ""},
            {"target": "rd_fis", "operation": "add", "value": "2", "condition": ""},
            {"target": "res_gelo", "operation": "add", "value": "2", "condition": ""},
        ],
    },
    {
        "name": "Skooma",
        "description": "+1 ai tiri di Velocità, +4 PA, +1 al modificatore generale per 5 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 48,
        "operations": [
            {"target": "velocita", "operation": "add", "value": "1", "condition": ""},
            {"target": "pa", "operation": "add", "value": "4", "condition": ""},
            {"target": "modificatore_generale", "operation": "add", "value": "1", "condition": ""},
        ],
    },
    {
        "name": "Skooma (contraccolpo)",
        "description": "Dopo 5 turni, +2 stanchezza.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 49,
        "operations": [
            {"target": "stanchezza", "operation": "add", "value": "2", "condition": ""},
        ],
    },
    {
        "name": "Zucchero Lunare",
        "description": "+1 al modificatore generale per 5 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 50,
        "operations": [
            {"target": "modificatore_generale", "operation": "add", "value": "1", "condition": ""},
        ],
    },
    {
        "name": "Zucchero Lunare (contraccolpo)",
        "description": "Dopo 5 turni, +1 stanchezza.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 51,
        "operations": [
            {"target": "stanchezza", "operation": "add", "value": "1", "condition": ""},
        ],
    },
    {
        "name": "Zucchero Lunare (khajiit)",
        "description": "Solo per khajiit: +1 PA, +5 punti ferita e mana.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 52,
        "operations": [
            {"target": "pa", "operation": "add", "value": "1", "condition": ""},
            {"target": "pf", "operation": "add", "value": "5", "condition": ""},
            {"target": "mana", "operation": "add", "value": "5", "condition": ""},
        ],
    },
    {
        "name": "Vino Sangue di Sanguine",
        "description": "+1 al modificatore generale per 10 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 53,
        "operations": [
            {"target": "modificatore_generale", "operation": "add", "value": "1", "condition": ""},
        ],
    },
    {
        "name": "Vino Sangue di Sanguine (conversione)",
        "description": (
            "Per 10 turni, ogni 4 PA spesi costa anche 1 Energia; nessun bersaglio "
            "esprime il trigger, arbitrato al tavolo."
        ),
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 54,
        # Nessun bersaglio converte "PA spesi" in perdita di Energia: resta
        # descrittivo, come "Spasmi".
        "operations": [],
    },
    {
        "name": "Flin",
        "description": "+3 al modificatore generale per 3 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 55,
        "operations": [
            {"target": "modificatore_generale", "operation": "add", "value": "3", "condition": ""},
        ],
    },
    {
        "name": "Flin (contraccolpo)",
        "description": "Dopo 3 turni, -4 al modificatore generale per altri 3 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 56,
        "operations": [
            {"target": "modificatore_generale", "operation": "subtract", "value": "4", "condition": ""},
        ],
    },
    {
        "name": "Liquore Lacrime di Sanguine",
        "description": "+40% punti ferita temporanei per 10 turni.",
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 57,
        "operations": [
            {"target": "pf", "operation": "percent", "value": "40", "condition": ""},
        ],
    },
    {
        "name": "Cognac Bretone",
        "description": (
            "1 Potere gratuito ogni turno per 10 turni; non è un aumento di "
            "massimale, arbitrato al tavolo."
        ),
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 58,
        # "Potere" è un contatore di spesa, non un valore che si azzera ogni
        # turno come i PA: un +1 statico non renderebbe "gratis ogni turno".
        "operations": [],
    },
    {
        "name": "Mazte",
        "description": (
            "2 Energia e 2 Potere gratuiti ogni turno per 10 turni; non è un "
            "aumento di massimale, arbitrato al tavolo."
        ),
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 59,
        "operations": [],
    },
    {
        "name": "Distillato Del Tempio di Sanguine",
        "description": (
            "+1 a tutti i tiri per 10 turni (caratteristiche, abilità, tiri in "
            "combattimento); nessun bersaglio copre \"tutti i tiri\", arbitrato al tavolo."
        ),
        "origin": "Preset",
        "icon": "pozione",
        "category": "Bevande",
        "order": 60,
        "operations": [],
    },
)

"""Catalogo di razze e sottorazze, con i bonus che il sistema applica da solo.

Fonte unica per tre consumatori: ``automatic_race_effects`` (il calcolo di
riserva), le abilità razziali in banca dati sincronizzate da
``backend.core.race_skill_sync`` (il percorso davvero attivo su un personaggio
già importato) e i pannelli della creazione PG.

Ogni sottorazza dichiara ``effects`` per ciò che il motore applica e ``manual``
per ciò che resta da segnare a mano: la creazione mostra i due elenchi separati,
quindi una voce lasciata fuori da entrambi sparisce dalla scheda senza avvisare.

**Regola dei raddoppi.** Dalla guida Razze: «I bonus attivi e passivi non
aumentano, ma quelli di sottorazza si raddoppiano, se possibile, a lv 5, 10, 15,
20». Raddoppio significa un'altra volta il valore di partenza, non una
progressione esponenziale: +1 diventa +2 a livello 5, +3 a 10, +4 a 15, +5 a 20.
Lo conferma il testo delle sottorazze che alle soglie deviano l'incremento
altrove («a lv 5 e 15 invece, +1 Percezione»): la deviazione vale sempre un
singolo valore di partenza. Vale salvo diversa indicazione della sottorazza,
per questo esistono ``at_levels`` e i valori piatti.
"""

from __future__ import annotations

from typing import Any, Mapping


# Le soglie a cui un bonus di sottorazza guadagna un'altra volta il valore base.
DOUBLING_LEVELS = (5, 10, 15, 20)


def _reached(levels: tuple[int, ...]) -> str:
    return " + ".join(f"(personaggio.livello >= {level})" for level in levels)


def grows(value: float) -> str:
    """Bonus di sottorazza standard: valore pieno, poi di nuovo a ogni soglia.

    ``min`` blocca la crescita dopo l'ultima soglia: a livello 25 il bonus resta
    quello di livello 20.
    """
    return f"{value} * (1 + min({len(DOUBLING_LEVELS)}, floor(personaggio.livello / {DOUBLING_LEVELS[0]})))"


def at_levels(value: float, *levels: int) -> str:
    """Solo alle soglie indicate: nessun bonus di partenza.

    Serve alle sottorazze che a certi raddoppi spostano l'incremento su un'altra
    caratteristica invece di rinforzare la propria.
    """
    return f"{value} * ({_reached(levels)})"


def base_and_levels(value: float, *levels: int) -> str:
    """Valore di partenza più un incremento alle sole soglie indicate."""
    return f"{value} + {value} * ({_reached(levels)})"


def below_level(value: float, level: int) -> str:
    """Valore che vale solo finché il personaggio è sotto la soglia indicata."""
    return f"{value} * (personaggio.livello < {level})"


RACE_CATALOG: dict[str, dict[str, Any]] = {
    "Bosmer": {
        "modifiers": {"resistenza": -2, "velocita": -1, "agilita": 2, "saggezza": 1, "fortuna": 1},
        "trait": {
            "note": "Immunità alle malattie; una volta al giorno può calmare un animale aggressivo entro 9 metri.",
            "manual": "Immunità alle malattie e la calma animale giornaliera restano regole al tavolo.",
        },
        "subraces": {
            "Foreste": {
                "note": "+1 Conoscenze Natura e Geografia; a livello 5 e 15 l'incremento va invece su Percezione.",
                "effects": {
                    "competenza.conoscenze_naturaegeografia": base_and_levels(1, 10, 20),
                    "competenza.percezione": at_levels(1, 5, 15),
                },
            },
            "Colline": {
                "note": "+1 Punti Azione; a livello 5 e 15 l'incremento diventa un perk minore.",
                "effects": {"pa": base_and_levels(1, 10, 20)},
                "manual": "A livello 5 e 15 aggiungi un perk minore al posto del Punto Azione.",
            },
            "Cacciatore": {
                "note": "Portata aumentata con archi, balestre e armi da lancio; un reroll a distanza al giorno.",
                "manual": "+3 metri di portata con archi e balestre, +1 con le armi da lancio, e un reroll giornaliero sugli attacchi a distanza.",
            },
            "Erborista": {
                "note": "Le pozioni create ottengono un effetto aggiuntivo.",
                "manual": "Aggiungi un effetto alle pozioni che il personaggio prepara.",
            },
            "Esploratore": {
                "note": "Può saltare un pasto al giorno; i raddoppi diventano Energia.",
                "effects": {"energia": at_levels(1, *DOUBLING_LEVELS)},
                "manual": "Può saltare un pasto al giorno; questa parte non raddoppia.",
            },
        },
    },
    "Dunmer": {
        "modifiers": {"fortuna": -2, "personalita": -1, "intelligenza": 2, "saggezza": 2},
        "trait": {
            "note": "Resistenza naturale al fuoco; una volta al giorno può evocare un fantasma di livello inferiore.",
            "effects": {"res_fuoco": 1, "rd_fuoco": 2},
            "manual": "L'evocazione giornaliera del fantasma di livello -4 va gestita al tavolo.",
        },
        "subraces": {
            "Retaggio Mago": {"note": "+8 Mana.", "effects": {"mana": grows(8)}},
            "Retaggio Guerriero": {"note": "+8 Punti Ferita.", "effects": {"pf": grows(8)}},
            "Nobile di Vvardenfell": {
                "note": "+1 Conoscenze Storia e Nobiltà; ai raddoppi Intuizione, Raggirare, Diplomazia, Intimidire.",
                "effects": {
                    "competenza.conoscenze_storiaenobilta": 1,
                    "competenza.intuizione": at_levels(1, 5),
                    "competenza.raggirare": at_levels(1, 10),
                    "competenza.diplomazia": at_levels(1, 15),
                    "competenza.intimidire": at_levels(1, 20),
                },
            },
            "Esule di Solstheim": {
                "note": "+1 Resistenza al gelo; ai raddoppi Resistenza, Gestione risorse, Sopravvivenza, poi +5 PF e Mana.",
                "effects": {
                    "res_gelo": 1,
                    "resistenza": at_levels(1, 5),
                    "competenza.gestione_risorse": at_levels(1, 10),
                    "competenza.sopravvivenza": at_levels(1, 15),
                    "pf": at_levels(5, 20),
                    "mana": at_levels(5, 20),
                },
            },
            "Servo del Tribunale": {
                "note": "+1 Conoscenze Religioni; ai raddoppi Sapienza magica, Intimidire, Saggezza, Strategia militare.",
                "effects": {
                    "competenza.conoscenze_religioni": 1,
                    "competenza.sapienza_magica": at_levels(1, 5),
                    "competenza.intimidire": at_levels(1, 10),
                    "saggezza": at_levels(1, 15),
                    "competenza.strategia_militare": at_levels(1, 20),
                },
            },
        },
    },
    "Orsimer": {
        "modifiers": {"intelligenza": -2, "personalita": -2, "forza": 2, "resistenza": 2, "saggezza": 1},
        "trait": {
            # Il regolamento diceva "+1 danno ogni 3 livelli". ReDjango non ha un
            # bersaglio "danno": il danno di un attacco esce dalla formula del Tier,
            # quindi la progressione vive su Tier, che è il bersaglio che la sposta
            # davvero. Il passivo di razza non raddoppia: cresce solo col livello.
            "note": "Tier crescente sugli attacchi fisici; una volta al giorno può rigenerare il 25% dei Punti Ferita.",
            "effects": {"tier": "floor(personaggio.livello / 3)"},
            "manual": "La rigenerazione giornaliera del 25% dei Punti Ferita va gestita al tavolo.",
        },
        "powers": {
            "elder-racial-trait-200": {
                "name": "Orsimer - Tier fisico incrementale",
                "note": "+1 Tier agli attacchi fisici ogni 3 livelli.",
                "effects": {"tier": "floor(personaggio.livello / 3)"},
            },
        },
        "subraces": {
            "Selvaggio": {"note": "+2 Attacco.", "effects": {"attacco": grows(2)}},
            "Della Tribù": {"note": "+2 Difesa.", "effects": {"difesa": grows(2)}},
            "Forgiatore d'Armi": {
                "note": "+1 Punto Modifica a Forgiatura.",
                "manual": "Forgiatura non è fra le competenze e i Punti Modifica non sono un valore della scheda: segna il punto a mano.",
            },
            "Guardiano delle Miniere": {"note": "+1 Riduzione fisica.", "effects": {"rd_fis": grows(1)}},
            "Sciamano": {"note": "+2 Potere.", "effects": {"potere": grows(2)}},
        },
    },
    "Altmer": {
        "modifiers": {"saggezza": -1, "forza": -1, "resistenza": -2, "intelligenza": 2, "concentrazione": 2, "velocita": 1},
        "trait": {
            "note": "Potere arcano crescente; una volta al giorno può potenziare un incantesimo.",
            "effects": {"potere": "personaggio.livello"},
            "manual": "I +7 Potere giornalieri su un incantesimo vanno applicati al momento.",
        },
        "subraces": {
            "Sangue Nobile": {"note": "+1 Concentrazione.", "effects": {"concentrazione": grows(1)}},
            "Plebeo": {"note": "+1 Resistenza.", "effects": {"resistenza": grows(1)}},
            "Accolito di Aetherius": {
                "note": "Potere aggiuntivo con gli incantesimi di Distruzione.",
                "manual": "Il Potere per scuola di magia non è un valore della scheda: applicalo agli incantesimi di Distruzione.",
            },
            "Custode del Sole": {
                "note": "+1 Resistenza al fuoco; ai raddoppi elettro, gelo, Riduzione fisica e le tre resistenze fisiche.",
                "effects": {
                    "res_fuoco": 1,
                    "res_elettro": at_levels(1, 5),
                    "res_gelo": at_levels(1, 10),
                    "rd_fis": at_levels(1, 15),
                    "res_contundente": at_levels(1, 20),
                    "res_taglio": at_levels(1, 20),
                    "res_perforante": at_levels(1, 20),
                },
            },
            "Custode della Luna": {
                "note": "Visioni giornaliere che migliorano con la progressione.",
                "manual": "Una visione al giorno costando 1 Stanchezza; ai raddoppi diventa 10 Energia, visione media, 1 Energia, visione maggiore.",
            },
        },
    },
    "Imperiale": {
        "modifiers": {"velocita": -1, "saggezza": -1, "forza": -1, "personalita": 2, "fortuna": 1, "concentrazione": 1},
        "trait": {
            "note": "Ottiene PE aggiuntivi a ogni livello; una volta al giorno può calmare un umanoide aggressivo.",
            "manual": "+2 Punti Esperienza a ogni passaggio di livello, e la calma giornaliera su un umanoide.",
        },
        "subraces": {
            "Di Città": {
                "note": "Una lingua aggiuntiva; a livello 5 e 15 l'incremento va invece su Intuizione.",
                "effects": {"competenza.intuizione": at_levels(1, 5, 15)},
                "manual": "Le lingue conosciute non sono un valore della scheda: segnale a mano, anche ai raddoppi di livello 10 e 20.",
            },
            "Di Campagna": {"note": "+1 Forza.", "effects": {"forza": grows(1)}},
            "Apprendista": {
                "note": "Migliora due barre abilità iniziali.",
                "manual": "+1 a due barre abilità in cui hai da 0 a 3, fino a un massimo di 4.",
            },
            "Sanguemisto": {
                "note": "Può scegliere una sottorazza appartenente a un'altra razza.",
                "manual": "Scegli la sottorazza da un'altra razza: impostala come Razza 2 e i suoi bonus seguiranno quella sottorazza.",
            },
            "Guaritore del Tempio": {
                "note": "Potere aggiuntivo con gli incantesimi di Recupero.",
                "manual": "Il Potere per scuola di magia non è un valore della scheda: applicalo agli incantesimi di Recupero.",
            },
        },
    },
    "Bretone": {
        "modifiers": {"forza": -1, "resistenza": -2, "fortuna": -1, "intelligenza": 1, "concentrazione": 2, "personalita": 1, "saggezza": 1},
        "trait": {
            "note": "Riserva di Mana crescente; dispone di un Dispel razziale.",
            "effects": {"mana": "personaggio.livello * 2.5"},
            "manual": "Il Dispel giornaliero va usato al tavolo.",
        },
        "subraces": {
            "Cavaliere": {
                "note": "Un reroll in combattimento.",
                "manual": "Un reroll in combattimento; i reroll non sono un valore della scheda.",
            },
            "Mercante": {
                "note": "Bonus e reroll di Contrattazione con la progressione.",
                "manual": "+1 ai tiri di Contrattazione, che non è fra le competenze; a livello 5 e 15 diventa un reroll.",
            },
            "Mago della Torre": {"note": "+1 Concentrazione.", "effects": {"concentrazione": grows(1)}},
            "Erudito di Daggerfall": {
                "note": "Migliora entrambe le barre di una conoscenza casuale.",
                "manual": "Tira un dado per la conoscenza, poi +1 a entrambe le sue barre.",
            },
            "Soldato a Piedi": {
                "note": "Attacco aumentato dagli alleati vicini che partecipano al combattimento.",
                "manual": "+1 Attacco per ogni alleato entro 1 metro che stia combattendo: dipende dalla mappa, non dalla scheda.",
            },
        },
    },
    "Redguard": {
        "modifiers": {"saggezza": -2, "concentrazione": -1, "forza": 2, "velocita": 1, "fortuna": 1},
        "trait": {
            "note": "Punti Ferita crescenti; può ottenere temporaneamente modificatore generale.",
            "effects": {"pf": "personaggio.livello * 2"},
            "manual": "Il +1 modificatore generale per un turno va applicato al momento.",
        },
        "subraces": {
            "Deserto": {
                "note": "+1 Sopravvivenza; a livello 5 e 15 l'incremento va invece su Saggezza.",
                "effects": {
                    "competenza.sopravvivenza": base_and_levels(1, 10, 20),
                    "saggezza": at_levels(1, 5, 15),
                },
            },
            "Oasi": {"note": "+1 Resistenza.", "effects": {"resistenza": grows(1)}},
            "Guerriero delle Dune": {
                "note": "Può convertire il danno di un attacco in Energia.",
                "manual": "Assorbi il danno di un attacco convertendolo in Energia (10 danno → 2 Energia); ai raddoppi puoi farlo più volte al giorno.",
            },
            "Esploratore di Hammerfell": {
                "note": "+1 Nuotare e Manovrare veicoli; a livello 5 e 15 l'incremento va invece su Scalare e Cavalcare.",
                "effects": {
                    "competenza.nuotare": base_and_levels(1, 10, 20),
                    "competenza.manovrare_veicoli": base_and_levels(1, 10, 20),
                    "competenza.scalare": at_levels(1, 5, 15),
                    "competenza.cavalcare": at_levels(1, 5, 15),
                },
            },
            "Lottatore di Stros M'Kai": {
                "note": "Bonus ai tiri di Forza e Resistenza.",
                "manual": "+1 ai tiri di Forza e Resistenza: il modificatore di dado si ricava dalla caratteristica e non accetta effetti.",
            },
        },
    },
    "Argoniano": {
        "modifiers": {"concentrazione": -1, "intelligenza": -1, "personalita": -1, "fortuna": 2, "velocita": 2},
        "trait": {
            "note": "Respira sott'acqua; può spendere Energia per rigenerare Punti Ferita, Mana e PA.",
            "manual": "Respirare sott'acqua e la rigenerazione da 5 Energia (livello × 3 PF e Mana, 5 PA) restano regole al tavolo.",
        },
        "subraces": {
            "Fortunato": {
                "note": "Un reroll al giorno fuori dal combattimento.",
                "manual": "Un reroll giornaliero fuori dal combattimento.",
            },
            "Paludoso": {
                "note": "Immunità alle malattie.",
                "manual": "Immunità alle malattie: non esiste un bersaglio per le immunità.",
            },
            "Figlio di Hist": {
                "note": "+1 Conoscenze Natura e Geografia; a livello 5 e 15 l'incremento diventa modificatore generale temporaneo.",
                "effects": {"competenza.conoscenze_naturaegeografia": base_and_levels(1, 10, 20)},
                "manual": "A livello 5 e 15 guadagni invece +1 modificatore generale per un turno, da applicare al momento.",
            },
            "Guerriero dell'Ombra": {
                "note": "Può aumentare il tiro di un attacco, anche trasformandolo in critico.",
                "manual": "Alza di 1 il tiro di un attacco, anche fino al critico; ai raddoppi il bonus cresce.",
            },
            "Alchimista esploratore": {
                "note": "Trova un ingrediente aggiuntivo ogni 30 minuti.",
                "manual": "Un ingrediente in più ogni 30 minuti di esplorazione.",
            },
        },
    },
    "Khajiit": {
        "modifiers": {"resistenza": -2, "personalita": -1, "intelligenza": 1, "agilita": 2, "forza": 1},
        "trait": {
            "note": "Visione notturna; un reroll giornaliero su Furtività e Rapidità di Mano.",
            "manual": "Night Eye a 100 metri e un reroll giornaliero su Furtività e su Rapidità di mano.",
        },
        "subraces": {
            "Tribale": {
                "note": "+1 Fortuna; a livello 5 e 15 l'incremento va invece su Agilità.",
                "effects": {"fortuna": base_and_levels(1, 10, 20), "agilita": at_levels(1, 5, 15)},
            },
            "Carovana": {
                "note": "+1 Rapidità di mano; a livello 5 e 15 l'incremento va invece su Raggirare.",
                "effects": {
                    "competenza.rapidita_di_mano": base_and_levels(1, 10, 20),
                    "competenza.raggirare": at_levels(1, 5, 15),
                },
            },
            "Monaco": {
                "note": "+1 Potere ed Energia; a livello 5 e 15 l'incremento va sui tiri di Concentrazione.",
                "effects": {
                    "potere": base_and_levels(1, 10, 20),
                    "energia": base_and_levels(1, 10, 20),
                },
                "manual": "A livello 5 e 15 guadagni invece +1 ai tiri di Concentrazione, che non accettano effetti.",
            },
            "Cacciatore di Elsweyr": {
                "note": "Inizia il combattimento con PA ed Energia gratuiti.",
                "manual": "Primo turno di combattimento con +1 PA e 2 Energia gratis.",
            },
            "Ladro Corridore": {
                "note": "+1 Velocità; a livello 5 e 15 l'incremento va invece su Intimidire e Attacco.",
                "effects": {
                    "velocita": base_and_levels(1, 10, 20),
                    "competenza.intimidire": at_levels(1, 5, 15),
                    "attacco": at_levels(1, 5, 15),
                },
            },
        },
    },
    "Nord": {
        "modifiers": {"velocita": -1, "agilita": -1, "personalita": -1, "resistenza": 2, "fortuna": 2},
        "trait": {
            "note": "Resistenza naturale al gelo; ottiene Energia gratuita per due turni.",
            "effects": {"res_gelo": 1, "rd_gelo": 2},
            "manual": "Una volta al giorno, livello / 2 + 1 Energia gratuita a turno per due turni.",
        },
        "subraces": {
            "Tradizionale": {
                "note": "+1 Forza; a livello 5 e 15 l'incremento va invece su Resistenza.",
                "effects": {"forza": base_and_levels(1, 10, 20), "resistenza": at_levels(1, 5, 15)},
            },
            "Sud": {
                "note": "+1 Personalità; a livello 5 e 15 l'incremento va invece su Suonare e Manovrare veicoli.",
                "effects": {
                    "personalita": base_and_levels(1, 10, 20),
                    "competenza.suonare": at_levels(1, 5, 15),
                    "competenza.manovrare_veicoli": at_levels(1, 5, 15),
                },
            },
            "Berserker": {
                "note": "Può spendere Stanchezza per rimuovere immediatamente status mentali.",
                "manual": "1 punto Stanchezza per liberarti all'istante dagli status mentali, magici o no, anche senza saperne l'esistenza. Non raddoppia.",
            },
            "Custode della Parola": {
                "note": "Può spendere Potere per migliorare i tiri caratteristica.",
                "manual": "+1 ai tiri caratteristica spendendo un solo punto Potere, massimo 1; ai raddoppi massimo +1 ulteriore.",
            },
            "Stirpe di Sempliciotti": {
                "note": "Sostituzioni speciali per i tiri di Intelligenza e Concentrazione.",
                "manual": "Tira Intelligenza e Concentrazione con Forza e Resistenza a -1; da livello 10 aggiungi anche Saggezza e Personalità.",
            },
        },
    },
    "Falmer": {
        "modifiers": {"velocita": -1, "resistenza": -2, "saggezza": 2, "agilita": 2},
        "trait": {
            "note": "Percezione aumentata; una volta al giorno rigenera il 25% del Mana.",
            "effects": {"competenza.percezione": 1},
            "manual": "La rigenerazione giornaliera del 25% del Mana va gestita al tavolo.",
        },
        "powers": {
            "elder-racial-trait-258": {
                "note": "+1 Percezione.",
                "effects": {"competenza.percezione": 1},
            },
        },
        "subraces": {
            "Caverna": {
                "note": "+2 Potere che non cresce; i raddoppi allungano la visione notturna.",
                "effects": {"potere": 2},
                "manual": "Night Eye a 5 metri, poi 10, 25, 100 e 500 metri ai raddoppi.",
            },
            "Rovina": {
                "note": "+1 Ingegneria; a livello 5 e 15 l'incremento va invece su Furtività.",
                "effects": {
                    "competenza.ingegneria": base_and_levels(1, 10, 20),
                    "competenza.furtivita": at_levels(1, 5, 15),
                },
            },
            "Osservatore del Sole": {
                "note": "Può aggiungere danno da fuoco a un attacco.",
                "manual": "Aggiungi 1d10 danno da fuoco a un attacco.",
            },
            "Sciamano della Notte": {
                "note": "Potere aggiuntivo con le magie di Maledizione.",
                "manual": "Il Potere per scuola di magia non è un valore della scheda: applicalo alle magie di Maledizione.",
            },
            "Sangue Corrotto": {
                "note": "Immunità ai veleni e creazione di pozioni dal proprio sangue.",
                "manual": "Immune ai veleni; con il proprio sangue crea pozioni che infliggono danno pari al livello, al costo di metà Energia massima, valide 24 ore e senza valore.",
            },
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
                "effects": {"energia": grows(1)},
            },
            "Caitiff": {
                "note": "Soldato esperto, abituato ad assalti rapidi e combattimenti prolungati.",
                "effects": {"velocita": grows(1)},
            },
            "Kynval": {
                "note": "Guerriero di rango elevato, premiato per la ferocia in battaglia.",
                "effects": {"attacco": grows(1)},
            },
            "Kynreeve": {
                "note": "Ufficiale di clan responsabile della disciplina e della difesa.",
                "effects": {"difesa": grows(1)},
            },
            "Kynmarcher": {
                "note": "Comandante operativo capace di guidare reparti e campagne.",
                "effects": {"concentrazione": grows(1)},
            },
            "Markynaz": {
                "note": "Signore del consiglio Markyn, dotato di autorità e potere daedrico.",
                "effects": {"potere": grows(1)},
            },
            "Valkynaz": {
                "note": "Principe guerriero al vertice della gerarchia Dremora.",
                "effects": {"resistenza": grows(1)},
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
                "effects": {"agilita": grows(1)},
            },
            "Draugr": {
                "note": "Guerriero nordico sepolto, temprato dal gelo e dalla custodia delle tombe.",
                "effects": {"res_gelo": grows(1)},
            },
            "Revenant": {
                "note": "Cadavere richiamato da un giuramento incompiuto o dalla volontà di un necromante.",
                "effects": {"forza": grows(1)},
            },
            "Mummia": {
                "note": "Corpo conservato da riti funerari e bende protettive.",
                "effects": {"rd_fis": grows(1)},
            },
            "Vampiro": {
                "note": "Predatore notturno mosso dal sangue, rapido e socialmente pericoloso.",
                "effects": {"velocita": grows(1)},
            },
            "Lich": {
                "note": "Necromante che ha vincolato la propria anima alla non morte.",
                "effects": {"potere": grows(1)},
            },
            "Spettro": {
                "note": "Anima disincarnata legata a un luogo, un oggetto o un rancore.",
                "effects": {"difesa": grows(1)},
            },
        },
        "native": True,
    },
}

RACE_NAMES = tuple(RACE_CATALOG)

# Valore sentinella con cui le tendine di razza offrono "altro, scritto a mano".
RACE_EXTRA_VALUE = "__extra__"

# Grafie con cui una sottorazza è arrivata dall'import Elder e che non
# corrispondono al catalogo. Servono solo a ritrovare la voce giusta: il nome
# buono resta quello del catalogo, che è ciò che la creazione scrive su razza_2.
LEGACY_SUBRACE_ALIASES = {
    "apprensista": "Apprendista",
}


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


def race_bonus_operations(values: Mapping[str, Any]) -> list[dict[str, str]]:
    """Traduce una mappa bersaglio → valore nelle operazioni di un effetto.

    Solo i numeri negativi diventano ``subtract``: una formula resta una somma,
    perché il suo segno lo decide il calcolo, non il catalogo.
    """
    return [
        {
            "target": target,
            "operation": "add" if not isinstance(value, (int, float)) or value >= 0 else "subtract",
            "value": str(value if not isinstance(value, (int, float)) or value >= 0 else abs(value)),
        }
        for target, value in values.items()
    ]


_operations = race_bonus_operations


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

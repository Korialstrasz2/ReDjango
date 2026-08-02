"""Catalogo statico della Forgiatura, tradotto dalle regole Elder.

Le fasce dei materiali, i lingotti per categoria e il menu dei miglioramenti
sono regole di gioco, non dati editabili: vivono qui come vive
``alchemy_defaults`` per l'Alchimia. Quello che invece cambia da personaggio a
personaggio — quali materiali sa lavorare, quanti punti miglioramento ha — si
ricava dalle abilità e dai totali, mai da questo file.

Un dettaglio che vale la pena ricordare: i lingotti nel catalogo oggetti NON
dichiarano il proprio materiale. ``Ascia (ferro)`` ha ``tipo_2='ferro'``, ma
``Lingotto di ferro`` ha ``tipo_2='lingotto'`` e il materiale sta solo nel nome
italiano — con tre nomi che rompono lo schema (``Legno per armi``,
``Scheletro di dreugh``, ``Pelle conciata``). Per questo la mappa
lingotto → materiale è esplicita qui sotto invece di essere dedotta.
"""

from __future__ import annotations

from typing import Any


LIGHT = "leggero"
HEAVY = "pesante"

# key, etichetta, fascia 1-7, ramo, nome esatto della riga lingotto nel catalogo.
FORGE_MATERIALS: tuple[tuple[str, str, int, str, str], ...] = (
    ("legno", "Legno", 1, LIGHT, "Legno per armi"),
    ("pelle", "Pelle", 1, LIGHT, "Pelle conciata"),
    ("ferro", "Ferro", 1, HEAVY, "Lingotto di ferro"),
    ("chitina", "Chitina", 2, LIGHT, "Lingotto di chitina"),
    ("acciaio", "Acciaio", 2, HEAVY, "Lingotto di acciaio"),
    ("elfico", "Elfico", 3, LIGHT, "Lingotto di metallo elfico"),
    ("nordico", "Nordico", 3, HEAVY, "Lingotto di metallo nordico"),
    ("ossa", "Ossa dunmer", 4, LIGHT, "Lingotto di ossa"),
    ("orchesco", "Orchesco", 4, HEAVY, "Lingotto di metallo orchesco"),
    ("dreugh", "Dreugh", 5, LIGHT, "Scheletro di dreugh"),
    ("dwemer", "Dwemer", 5, HEAVY, "Lingotto di metallo dwemer"),
    ("vetro", "Vetro", 6, LIGHT, "Lingotto di vetro"),
    ("ebano", "Ebano", 6, HEAVY, "Lingotto di ebano"),
    ("adamantio", "Adamantio", 7, LIGHT, "Lingotto di adamantio"),
    ("daedrico", "Daedrico", 7, HEAVY, "Lingotto di metallo daedrico"),
)

MATERIAL_BY_KEY: dict[str, dict[str, Any]] = {
    key: {"key": key, "label": label, "tier": tier, "branch": branch, "ingotName": ingot}
    for key, label, tier, branch, ingot in FORGE_MATERIALS
}
INGOT_NAME_BY_MATERIAL = {key: ingot for key, _l, _t, _b, ingot in FORGE_MATERIALS}
MATERIAL_BY_INGOT_NAME = {ingot: key for key, _l, _t, _b, ingot in FORGE_MATERIALS}

# `Lingotto massiccio di oro` è tesoro, non materiale: sta fra i lingotti per
# tipo ma non compare in FORGE_MATERIALS, quindi non entra mai nelle scorte.

# Categoria dell'oggetto → lingotti richiesti. Le ore di lavorazione sono pari
# al numero di lingotti usati (le frecce restano un'ora sola: sono una resa).
FORGE_CATEGORIES: dict[str, dict[str, Any]] = {
    "armiPiccole": {"label": "Armi piccole", "ingots": 3, "kind": "weapon"},
    "armiMedie": {"label": "Armi medie", "ingots": 4, "kind": "weapon"},
    "armiLunghe": {"label": "Armi lunghe", "ingots": 6, "kind": "weapon"},
    "armature": {"label": "Armature", "ingots": 6, "kind": "armor"},
    "cotteDiMaglia": {"label": "Cotte di maglia", "ingots": 5, "kind": "armor"},
    "armiDaLancio": {"label": "Armi da lancio", "ingots": 2, "kind": "weapon"},
    "frecce": {"label": "Frecce", "ingots": 1, "kind": "ammo", "yield": 5},
}

# tipo_1 del catalogo oggetti → categoria di forgiatura.
CATEGORY_BY_ITEM_TYPE: dict[str, str] = {
    "coltello": "armiPiccole", "daga": "armiPiccole", "stiletto": "armiPiccole",
    "shiv": "armiPiccole", "tirapugni": "armiPiccole", "accetta": "armiPiccole",
    "ascia": "armiMedie", "spadalunga": "armiMedie", "mazza": "armiMedie",
    "martello": "armiMedie", "sciabola": "armiMedie", "fioretto": "armiMedie",
    "katana": "armiMedie", "kriss": "armiMedie", "rapier": "armiMedie",
    "estoc": "armiMedie", "armblade": "armiMedie", "tonfa": "armiMedie",
    "beccodicorvo": "armiMedie", "nunchaku": "armiMedie",
    "zweihander": "armiLunghe", "spadone": "armiLunghe", "asciaaduemani": "armiLunghe",
    "martellodaguerra": "armiLunghe", "lancia": "armiLunghe", "picca": "armiLunghe",
    "tridente": "armiLunghe", "bastone": "armiLunghe", "bastoneconpesi": "armiLunghe",
    "mazzafrusta": "armiLunghe", "kusarigama": "armiLunghe",
    "coltellodalancio": "armiDaLancio", "accettadalancio": "armiDaLancio",
    "shuriken": "armiDaLancio",
    "armatura": "armature", "armaturaanimale": "armature", "scudo": "armature",
    "chainmail": "cotteDiMaglia",
    "freccia": "frecce",
}

# Miglioramenti. `apply` dice al servizio come applicarlo:
#   effect  → operazione strutturata in Oggetto.effects (la legge già il motore)
#   column  → scrittura diretta su una colonna dell'istanza
#   rule    → testo in Oggetto.regole_speciali, arbitrato al tavolo
IMPROVEMENTS: tuple[dict[str, Any], ...] = (
    {"key": "attacco", "label": "+1 Attacco", "cost": 1, "kinds": ("weapon",),
     "apply": {"mode": "effect", "target": "attacco", "value": 1}},
    {"key": "tier", "label": "+1 Tier danno", "cost": 1, "kinds": ("weapon",),
     "apply": {"mode": "effect", "target": "tier", "value": 1}},
    {"key": "peso", "label": "−1 Peso", "cost": 1, "kinds": ("weapon", "armor"),
     "apply": {"mode": "column", "column": "peso", "delta": -1, "minimum": 0}},
    {"key": "sanguinamento", "label": "Effetto sanguinamento", "cost": 1, "kinds": ("weapon",),
     "apply": {"mode": "rule", "text": "Sanguinamento: l'effetto è arbitrato dal Master."}},
    {"key": "pa", "label": "+1 Punti azione", "cost": 2, "kinds": ("weapon", "armor"),
     "apply": {"mode": "effect", "target": "pa", "value": 1}},
    {"key": "reroll", "label": "1 Reroll per turno", "cost": 2, "kinds": ("weapon",),
     "apply": {"mode": "rule", "text": "Un reroll per turno con quest'arma."}},
    {"key": "difesa", "label": "+1 Difesa", "cost": 2, "kinds": ("weapon",),
     "apply": {"mode": "effect", "target": "difesa", "value": 1}},
    {"key": "costoPa", "label": "−1 Costo PA per attacco", "cost": 3, "kinds": ("weapon",),
     "twoHandedOnly": True,
     "apply": {"mode": "column", "column": "pa_per_attacco", "delta": -1, "minimum": 1}},
    {"key": "difesaArmatura", "label": "+1 Difesa", "cost": 1, "kinds": ("armor",),
     "apply": {"mode": "effect", "target": "difesa", "value": 1}},
    {"key": "rdFisica", "label": "+1 RD fisica", "cost": 1, "kinds": ("armor",),
     "apply": {"mode": "effect", "target": "rd_fis", "value": 1}},
    {"key": "energia", "label": "+1 Energia massima", "cost": 1, "kinds": ("armor",),
     "apply": {"mode": "effect", "target": "energia", "value": 1}},
    {"key": "attaccoArmatura", "label": "+1 Attacco", "cost": 2, "kinds": ("armor",),
     "apply": {"mode": "effect", "target": "attacco", "value": 1}},
)

# Resistenze e RD magiche: stessa voce ripetuta su elementi diversi non
# raddoppia, la stessa due volte sì. Per questo ogni elemento è una chiave
# distinta nel registro dei miglioramenti.
RESISTANCE_IMPROVEMENTS: tuple[dict[str, Any], ...] = (
    {"key": "res_contundente", "label": "+1 Resistenza contundente", "cost": 1},
    {"key": "res_taglio", "label": "+1 Resistenza taglio", "cost": 1},
    {"key": "res_perforante", "label": "+1 Resistenza perforante", "cost": 1},
    {"key": "res_fuoco", "label": "+1 Resistenza fuoco", "cost": 1},
    {"key": "res_gelo", "label": "+1 Resistenza gelo", "cost": 1},
    {"key": "res_elettro", "label": "+1 Resistenza elettricità", "cost": 1},
)
MAGIC_RD_IMPROVEMENTS: tuple[dict[str, Any], ...] = (
    {"key": "rd_fuoco", "label": "+3 RD fuoco", "cost": 2, "value": 3},
    {"key": "rd_gelo", "label": "+3 RD gelo", "cost": 2, "value": 3},
    {"key": "rd_elettro", "label": "+3 RD elettricità", "cost": 2, "value": 3},
)


def _armor_extras() -> tuple[dict[str, Any], ...]:
    entries = [
        {"key": entry["key"], "label": entry["label"], "cost": entry["cost"], "kinds": ("armor",),
         "apply": {"mode": "effect", "target": entry["key"], "value": 1}}
        for entry in RESISTANCE_IMPROVEMENTS
    ]
    entries += [
        {"key": entry["key"], "label": entry["label"], "cost": entry["cost"], "kinds": ("armor",),
         "apply": {"mode": "effect", "target": entry["key"], "value": entry["value"]}}
        for entry in MAGIC_RD_IMPROVEMENTS
    ]
    return tuple(entries)


IMPROVEMENT_CATALOG: tuple[dict[str, Any], ...] = IMPROVEMENTS + _armor_extras()
IMPROVEMENT_BY_KEY: dict[str, dict[str, Any]] = {entry["key"]: entry for entry in IMPROVEMENT_CATALOG}

# Elder: "Le chainmail e le vesti non possono essere migliorate."
UNIMPROVABLE_ITEM_TYPES = frozenset({"chainmail", "veste"})

# Uso pratico: 2 unità di pelle al livello 1, +2 per ogni livello successivo.
PRACTICAL_LEATHER_BASE = 2
PRACTICAL_LEATHER_PER_LEVEL = 2
PRACTICAL_ITEM_TYPES = ("portapozioni", "portapergamene", "faretra", "mantello")


def improvement_cost(base_cost: int, existing_stack: int) -> int:
    """Costo del prossimo acquisto: raddoppia a ogni ripetizione.

    Elder è esplicito: primo +1 Attacco 1 punto, secondo 2, terzo 4. Il totale
    speso cresce quindi 1, 3, 7 — ma qui torna solo il prezzo del prossimo.
    """
    return int(base_cost) * (2 ** max(0, int(existing_stack)))


def item_forge_category(tipo_1: str) -> str:
    return CATEGORY_BY_ITEM_TYPE.get((tipo_1 or "").strip().lower(), "")


def materials_for_tier(tier: int) -> list[str]:
    return [key for key, _l, material_tier, _b, _i in FORGE_MATERIALS if material_tier == tier]

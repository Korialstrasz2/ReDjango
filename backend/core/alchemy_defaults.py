from __future__ import annotations


ALCHEMY_COLOR_DEFINITIONS = (
    {"key": "rosso", "short": "r", "label": "Rosso"},
    {"key": "verde", "short": "v", "label": "Verde"},
    {"key": "blu", "short": "b", "label": "Blu"},
)

ALCHEMY_COLOR_BY_KEY = {entry["key"]: entry for entry in ALCHEMY_COLOR_DEFINITIONS}
ALCHEMY_COLOR_BY_SHORT = {entry["short"]: entry for entry in ALCHEMY_COLOR_DEFINITIONS}

ALCHEMY_POTION_EFFECTS = {
    "rosso": (
        "Cura",
        "Difesa",
        "Attacco",
        "Riduzione PA",
        "Danno alla vita",
        "Vita temporanea",
        "Energia spesa",
    ),
    "verde": (
        "Aumento PA",
        "Visione",
        "Cura effetti",
        "Esplosione",
        "Stanchezza spesa",
        "Fumogeno",
    ),
    "blu": (
        "Mana",
        "Danno al mana",
        "Potere speso",
        "Resistenza magica",
        "Volo",
        "Invisibilità",
        "Intangibilità",
    ),
}

# The 42 named ingredients from the elder project. Their color and level are
# authoritative; names are catalog flavor used when a reagent is extracted.
ALCHEMY_REAGENT_DEFAULTS = (
    ("Residuo magico", "blu", 1),
    ("Bacca Shein", "verde", 1),
    ("Ape", "rosso", 1),
    ("Spine di Heather", "rosso", 1),
    ("Polvere d'ossa", "verde", 1),
    ("Foglia azzurra", "blu", 1),
    ("Fungo di cenere", "verde", 1),
    ("Fiore del deserto", "rosso", 1),
    ("Polvere vulcanica", "rosso", 1),
    ("Radice di Trama", "verde", 1),
    ("Gold Kanet", "blu", 1),
    ("Marshmerrow", "rosso", 1),
    ("Coppa elfica", "blu", 1),
    ("Muschio rosso", "rosso", 1),
    ("Fiore di belladonna", "verde", 1),
    ("Campanula mortale", "rosso", 1),
    ("Fiori di montagna", "blu", 1),
    ("Farfalla blu", "blu", 1),
    ("Fungo di palude", "blu", 1),
    ("Semi bianchi", "verde", 1),
    ("Lingua di drago", "verde", 1),
    ("Libellula", "verde", 1),
    ("Fiore della rugiada", "blu", 1),
    ("Jazabay", "rosso", 1),
    ("Scarabeo magico", "blu", 2),
    ("Porcino topazio", "verde", 2),
    ("Insetto blu", "blu", 2),
    ("Fungo nero", "verde", 2),
    ("Insetto rosso", "rosso", 2),
    ("Radice di Mandragora", "verde", 2),
    ("Rosa spinosa", "rosso", 2),
    ("Fungo luminoso", "blu", 2),
    ("Fiore del sangue", "rosso", 2),
    ("Fiore luminoso", "blu", 3),
    ("Radice di Nirn", "verde", 3),
    ("Smeraldo", "verde", 3),
    ("Rubino", "rosso", 3),
    ("Zaffiro", "blu", 3),
    ("Ape Regina", "rosso", 3),
    ("Diamante", "verde", 4),
    ("Ambrosia", "blu", 4),
    ("Fiore di metallo", "rosso", 4),
)


def alchemy_stock_key(color: str, level: int) -> str:
    return f"{ALCHEMY_COLOR_BY_KEY[color]['short']}{level}"

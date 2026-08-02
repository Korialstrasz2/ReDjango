"""Catalogo statico dell'Incantamento, tradotto dalle regole Elder.

Il vero colpo di fortuna dell'Incantamento è che il risultato esiste già: il
catalogo accessori è una tabella completa e indicizzata per livello. 4.217
righe fra ``anello``, ``amuleto``, ``mantello``, ``fascia``, ``spilla``,
``cintura`` e ``orecchino``, dove ``tipo_2`` è il tipo di incantamento e
``lv_loot`` è il livello 1-10. Incantare non inventa un effetto: lo cerca.
"""

from __future__ import annotations

from typing import Any


# Slot incantabili. Elder: "Normalmente si incantano solo gioielli, fasce,
# mantelli... non armi, armature". Le armi restano fuori: le tre abilità che
# le incantano (Danno da impatto, Paralisi da impatto, Assorbi Anima) sono
# regole al tavolo finché il Master non decide diversamente.
ENCHANTABLE_SLOT_TYPES: tuple[str, ...] = (
    "anello", "amuleto", "orecchino", "mantello", "fascia", "spilla", "cintura",
)

MIN_ENCHANT_LEVEL = 1
MAX_ENCHANT_LEVEL = 10

# Elder: le anime riempiono le gemme di 1 livello ogni 15 pf.
SOUL_LEVEL_PER_HP = 15

# Nomi esatti delle righe gemma nel catalogo: "Gemma dell'anima lv N (piena)".
# L'apostrofo è quello tipografico salvato all'import, non l'ASCII.
SOUL_GEM_TYPE = "gemmaanima"
SOUL_GEM_FULL_MARKER = "(piena)"
SOUL_GEM_EMPTY_MARKER = "(vuota)"

ALTAR_TYPE = "altareincantamento"
# Il bonus vive solo come testo libero nella descrizione ("+ 10% mana"): qui
# diventa un numero, indicizzato per nome, così il calcolo non fa il parsing
# dell'italiano a ogni richiesta.
ALTAR_MANA_BONUS: dict[str, float] = {
    "Altare incantamento base": 0.10,
    "Altare incantamento base portatile": 0.10,
    "Altare incantamento da apprendista": 0.17,
    "Altare incantamento da apprendista portatile": 0.17,
    "Altare incantamento da qualificato": 0.25,
    "Altare incantamento da qualificato portatile": 0.25,
    "Altare incantamento avanzato": 0.32,
    "Altare incantamento da maestro": 0.40,
}

# Elder: "Il livello di una pergamena è determinato dalla forza dell'incantesimo
# che permette di castare: 12,22,34,46,58,70,82,94,106,118 mana."
SCROLL_MANA_LADDER: tuple[int, ...] = (12, 22, 34, 46, 58, 70, 82, 94, 106, 118)

# Una pergamena casta a metà del mana impresso.
SCROLL_EFFECT_RATIO = 0.5

SCROLL_TYPE = "pergamena"


def scroll_level_for_mana(mana: float) -> int:
    """Livello della pergamena che quel mana impresso permette di creare.

    Sotto la prima soglia non c'è pergamena: torna 0 così il servizio può
    rifiutare invece di creare una riga di livello zero.
    """
    level = 0
    for index, threshold in enumerate(SCROLL_MANA_LADDER, start=1):
        if mana >= threshold:
            level = index
    return level


def altar_bonus_for_name(name: str) -> float:
    return ALTAR_MANA_BONUS.get((name or "").strip(), 0.0)


def effective_enchant_mana(level: int, mana_per_level: float, altar_bonus: float) -> float:
    """Mana equivalente di un incantamento di quel livello.

    Elder: "Ogni livello dell'incantamento permette di castare come se usassi
    5 mana". Infusore 1-5 alza la base a 6..10; l'altare aggiunge una
    percentuale al risultato.
    """
    base = max(0, int(level)) * max(0.0, float(mana_per_level))
    return round(base * (1.0 + max(0.0, float(altar_bonus))), 2)


def charges_for_gem(level: int, bonus_percent: float) -> int:
    """Cariche di un oggetto incantato: pari al livello della gemma.

    Anima compressa 1 e 2 aggiungono +25% ciascuna. Si arrotonda per difetto
    ma mai sotto il livello nudo, così l'abilità non può togliere cariche.
    """
    base = max(0, int(level))
    boosted = int(base * (1.0 + max(0.0, float(bonus_percent)) / 100.0))
    return max(base, boosted)


def harmonic_gem_level(levels: list[int]) -> int:
    """Artigiano di anime: la prima gemma vale 1, la seconda 1/2, la terza 1/3.

    Le gemme si ordinano dalla più grande così la migliore prende il peso
    pieno. Il totale si tronca: il Master non regala mezzi livelli.
    """
    ordered = sorted((max(0, int(level)) for level in levels), reverse=True)
    total = sum(level / (index + 1) for index, level in enumerate(ordered))
    return min(MAX_ENCHANT_LEVEL, int(total))


def enchant_kind_label(kind: str) -> str:
    """Etichetta leggibile per un ``tipo_2`` del catalogo accessori."""
    key = (kind or "").strip()
    if not key:
        return ""
    known = {
        "attacco_item": "Attacco", "difesa_item": "Difesa", "pf_item": "Punti ferita",
        "mana_item": "Mana", "energia_item": "Energia", "potere_item": "Potere",
        "pa_item": "Punti azione", "rd_fis": "RD fisica",
        "barr_fis_item": "Barriera fisica", "barr_mag_item": "Barriera magica",
        "res_fuoco": "Resistenza fuoco", "res_gelo": "Resistenza gelo",
        "res_elettro": "Resistenza elettricità", "rigenerazionepf": "Rigenerazione PF",
        "rigenerazionemana": "Rigenerazione mana", "sifone_di_mana": "Sifone di mana",
        "mod.gen.": "Modificatore generale", "illusioneminore": "Illusione minore",
        "rangespell": "Gittata incantesimi", "rangespell(singola)": "Gittata singola",
    }
    if key in known:
        return known[key]
    if key.endswith("_extra"):
        return key[: -len("_extra")].replace("_", " ").capitalize()
    if key.startswith("+skill"):
        return f"Competenza {key[len('+skill'):]}"
    return key.replace("_", " ").capitalize()

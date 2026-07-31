"""Categorise unconvertible Elder effect texts from the 502 flagged items.

Reads db.sqlite3 directly, replicates the regex logic from
legacy_item_import.convert_effect and curate_item_special_rules.RULES,
and prints one category per blockable text family with example texts,
item counts and occurrence counts.

No Django dependency: sqlite3 + re only.
"""
from __future__ import annotations

import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Replicated from legacy_item_import.py
# ---------------------------------------------------------------------------
EMPTY_VALUES = {"", "vuoto"}
COMPETENCE_TARGETS = {
    "accorgere": "competenza_percezione",
    "acrobazia": "competenza_acrobazia",
    "addestrare": "competenza_addestramento",
    "affascinare": "competenza_diplomazia",
    "affare": "competenza_affare",
    "alchimia": "competenza_alchimia",
    "animale": "competenza_empatia",
    "arcano": "competenza_conoscenze_arcane",
    "armi": "competenza_armi",
    "arrampicare": "competenza_atletica",
    "artigianato": "competenza_artigianato",
    "atletica": "competenza_atletica",
    "autorita": "competenza_autorita",
    "bardo": "competenza_musica",
    "camuffare": "competenza_camuffare",
    "cammuffare": "competenza_camuffare",
    "cavalcare": "competenza_cavalcare",
    "concentrazione": "competenza_concentrazione",
    "conoscenze": "competenza_conoscenze",
    "conoscenze_arcane": "competenza_conoscenze_arcane",
    "conoscenze_natura": "competenza_conoscenze_natura",
    "conoscenze_religione": "competenza_conoscenze_religione",
    "curare": "competenza_medicina",
    "diplomazia": "competenza_diplomazia",
    "esibizione": "competenza_esibizione",
    "furtivita": "competenza_furtivita",
    "indagare": "competenza_indagare",
    "ingannare": "competenza_raggirare",
    "iniziativa": "competenza_iniziativa",
    "intimidire": "competenza_intimidire",
    "intrattenere": "competenza_intrattenere",
    "investigare": "competenza_indagare",
    "linguaggio_segreto": "competenza_linguaggio_segreto",
    "manolesta": "competenza_rapidita_mano",
    "medicina": "competenza_medicina",
    "musica": "competenza_musica",
    "nascondere": "competenza_furtivita",
    "natura": "competenza_conoscenze_natura",
    "navigare": "competenza_navigare",
    "nuotare": "competenza_atletica",
    "percezione": "competenza_percezione",
    "persuasione": "competenza_diplomazia",
    "raggirare": "competenza_raggirare",
    "rapidita_mano": "competenza_rapidita_mano",
    "religione": "competenza_conoscenze_religione",
    "sapere": "competenza_conoscenze",
    "sopravvivenza": "competenza_sopravvivenza",
    "storia": "competenza_conoscenze",
    "teologia": "competenza_conoscenze_religione",
}

NUMERIC_EFFECT_RE = re.compile(
    r"^(?:Personaggio\.)?([\w]+)\s*([+\-])\s*([+\-]?\d+(?:[.,]\d+)?)\s*$",
    re.IGNORECASE,
)
LEVEL_FORMULA_EFFECT_RE = re.compile(
    r"^(?:Personaggio\.)?(?P<target>[\w]+)\s*(?P<operation>[+\-])\s*"
    r"\(f\)\s*Personaggio\.livello\s*(?P<offset>[+\-]\s*\d+(?:[.,]\d+)?)?\s*$",
    re.IGNORECASE,
)
SIMPLE_BONUS_RE = re.compile(r"^(.+?)\s*([+\-])\s*([+\-]?\d+(?:[.,]\d+)?)\s*$")

KNOWN_TARGETS = {
    "attacco", "attacco_a_distanza", "attacco_magico", "attacco_mischia",
    "barr_fis", "barr_fis_item", "barr_mag", "barr_mag_item",
    "difesa", "difesa_extra", "difesa_fisica", "difesa_magica",
    "danno", "danno_base", "danno_extra",
    "destrezza", "energia", "energia_base", "energia_massimale", "energia_spesa",
    "forza", "intelligenza", "livello", "mana", "mana_base", "mana_corrente",
    "mana_massimale", "mana_speso",
    "ogni_en_x_mana", "ogni_pa_x_mana",
    "pa_per_attacco", "pa_totali",
    "potere", "potere_speso", "rd_fis", "rd_mag",
    "resistenza", "robustezza", "saggezza", "tempra", "velocita", "vista",
    "volonta",
}

LEGACY_TARGET_ALIASES = {
    "ogni_en_x_mana_ordine": "ogni_en_x_mana",
    "ogni_en_x_mana_caos": "ogni_en_x_mana",
    "ogni_pa_x_mana_ordine": "ogni_pa_x_mana",
    "ogni_pa_x_mana_caos": "ogni_pa_x_mana",
}


def clean_legacy_value(value: str | None) -> str:
    cleaned = str(value or "").strip()
    return "" if cleaned.casefold() in EMPTY_VALUES else cleaned


def convert_effect(raw: str | None) -> dict | None:
    text = clean_legacy_value(raw)
    if not text:
        return None
    match = NUMERIC_EFFECT_RE.fullmatch(text)
    if match:
        raw_target = match.group(1).strip().casefold()
        target = LEGACY_TARGET_ALIASES.get(raw_target, raw_target)
        if target in KNOWN_TARGETS:
            return {"converted": True}
        return None  # unknown target — still unconvertible
    match = LEVEL_FORMULA_EFFECT_RE.fullmatch(text)
    if match:
        raw_target = match.group("target").strip().casefold()
        target = LEGACY_TARGET_ALIASES.get(raw_target, raw_target)
        if target in KNOWN_TARGETS:
            return {"converted": True}
        return None
    match = SIMPLE_BONUS_RE.fullmatch(text)
    if match:
        label = match.group(1).strip().casefold()
        if label in COMPETENCE_TARGETS:
            return {"converted": True}
    return None


# ---------------------------------------------------------------------------
# Rule table — replicated from curate_item_special_rules.py
# ---------------------------------------------------------------------------
BLOCKED_RULES: dict[str, tuple[re.Pattern[str], str]] = {
    "ponte_di_mana": (re.compile(r"^ponte\s+di\s+mana\s*:?\s*si$", re.I),
                      "Ponte di Mana — il master deve definire l'effetto"),
    "mod_gen": (re.compile(r"^\+?\s*mod\s+gen\s*\d+\s*\(\s*\d+\s*\)$", re.I),
                "mod gen — shorthand non decodificato"),
    "teletrasporto": (re.compile(r"^teletrasporto\s+\d+\s*\(\s*\d+\s*\)$", re.I),
                      "Teletrasporto — non ancora curato"),
    "recast": (re.compile(r"^fino\s+a\s+x\s+mana\s*:\s*\d+\s*mana$", re.I),
               "Recast — non ancora curato"),
}

CURED_RULES: dict[str, tuple[re.Pattern[str], str]] = {
    "cast_silenzioso": (re.compile(r"^cast\s+silenzioso\s*:?\s*si$", re.I),
                        "Cast silenzioso"),
    "cast_immobile": (re.compile(r"^cast\s+immobile\s*:?\s*si$", re.I),
                      "Cast immobile"),
    "waterbreathing": (re.compile(r"^respiro\s+sott.?acqua\s*:?\s*si$", re.I),
                       "Respiro sott'acqua"),
    "sostentamento": (re.compile(r"^sostentamento\s*:?\s*si$", re.I),
                      "Sostentamento"),
    "rigenerazione": (re.compile(r"^rigenera\s+(\d+)\s*(pf|mana)\s+ogni\s+(\d+)\s*(sec|min|ora|ore|h)\.?$", re.I),
                      "Rigenerazione nel tempo"),
    "range_spell": (re.compile(r"^range\s+spell\s*\*\s*([\d.,]+)$", re.I),
                    "Moltiplicatore gittata spell"),
    "range_scuola": (re.compile(r"^range\s+scuola\s*\*\s*([\d.,]+)$", re.I),
                     "Moltiplicatore gittata scuola"),
    "range_tutte": (re.compile(r"^range\s+tutte\s*\*\s*([\d.,]+)$", re.I),
                    "Moltiplicatore gittata tutte"),
    "potere_free": (re.compile(r"^\+\s*(\d+)\s+potere\s+free\s+(.+)$", re.I),
                    "Potere gratuito per scuola"),
    "reroll": (re.compile(r"^(\d+)\s+reroll,\s*costo\s+en\s*:\s*(\d+)$", re.I),
               "Reroll con costo energia"),
    "estrazione_costo": (re.compile(r"^costo\s+estrazione\s*:\s*(\d+)\s*en$", re.I),
                         "Costo estrazione"),
    "estrazione_gratis": (re.compile(r"^costo\s+estrazione\s*:\s*gratis$", re.I),
                           "Estrazione gratis"),
    "counterspell": (re.compile(r"^costo\s+(\d+)\s*en\s+(\d+)\s*pa\s+(\d+)\s*magi[ae]$", re.I),
                     "Controincantesimo"),
    "scudo_arcano": (re.compile(r"^numero\s+attacchi\s*:\s*(\d+)$", re.I),
                     "Scudo arcano"),
    "contingenza": (re.compile(r"^contingenza\s+spell\s+(\d+)$", re.I),
                    "Contingenza"),
    "immagini": (re.compile(r"^immagini\s*:\s*(\d+)\s*imm\s*\(\s*(\d+)\s*en\s*(\d+)\s*pa\s*\)$", re.I),
                 "Immagini speculari"),
    "illusione_durata": (re.compile(r"^durata\s+illusione\s*:\s*(\d+)\s*turn[oi]$", re.I),
                         "Durata illusione"),
    "materializzazione": (re.compile(r"^grandezza\s+oggetto\s*:\s*fino\s+a\s+(.+)$", re.I),
                          "Materializzazione"),
    "telecinesi": (re.compile(r"^numero\s+kg\s*:\s*([\d.,]+)\s*kg$", re.I),
                   "Telecinesi"),
    "luce": (re.compile(r"^tempo\s+luce\s*:\s*(\d+)\s*(sec|min|ore?|h)$", re.I),
             "Produzione luce"),
    "darkvision": (re.compile(r"^raggio\s+darkvision\s*:\s*(\d+)\s*mt$", re.I),
                   "Darkvision"),
    "shapeshift": (re.compile(r"^tempo\s+shapeshift\s*:\s*(\d+)\s*(sec|min|ore?|h)$", re.I),
                   "Shapeshift"),
    "pozione_pf": (re.compile(r"^personaggio\.danno\s*-\s*(\d+)$", re.I),
                   "Pozione ripristina PF"),
    "pozione_mana": (re.compile(r"^personaggio\.mana_speso\s*-\s*(\d+)$", re.I),
                     "Pozione ripristina mana"),
    "pozione_energia": (re.compile(r"^personaggio\.energia_spesa\s*-\s*(\d+)$", re.I),
                        "Pozione ripristina energia"),
    "pozione_potere": (re.compile(r"^personaggio\.potere_speso\s*-\s*(\d+)$", re.I),
                       "Pozione ripristina potere"),
}


def categorise(text: str) -> tuple[str, str]:
    """Return (category, detail).

    Categories: CURED (rule exists, can be written), BLOCKED (rule exists but
    deliberately leaves items flagged), UNCOVERED (no rule matches), UNKNOWN_TARGET
    (structured but target missing), CONVERTIBLE (should not be here at all).
    """
    text = text.strip()

    # 1. Already convertible by the engine
    if convert_effect(text):
        return "CONVERTIBLE", "Effetto strutturato convertibile (non dovrebbe essere nella coda)"

    # 2. Blocked by design
    for key, (pattern, label) in BLOCKED_RULES.items():
        if pattern.fullmatch(text):
            return "BLOCKED", f"{label} [{key}]"

    # 3. Already cured (rule exists, found in first pass — these shouldn't appear either)
    for key, (pattern, label) in CURED_RULES.items():
        if pattern.fullmatch(text):
            return "CURED", f"{label} [{key}]"

    # 4. Unknown target — structured shape, missing stat
    if NUMERIC_EFFECT_RE.fullmatch(text) or LEVEL_FORMULA_EFFECT_RE.fullmatch(text):
        return "UNKNOWN_TARGET", "Stat sconosciuto al motore"

    # 5. Try SIMPLE_BONUS — competence-like but unknown
    if SIMPLE_BONUS_RE.fullmatch(text):
        label = SIMPLE_BONUS_RE.fullmatch(text).group(1).strip()
        return "UNKNOWN_TARGET", f"Competenza sconosciuta: {label}"

    # 6. Everything else
    return "UNCOVERED", "Nessuna regola corrisponde"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
DB = Path(__file__).resolve().parent / "db.sqlite3"

def main():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, nome, tipo_1, effetto_1, effetto_2, effetto_3, effetto_4, "
        "effetto_5, effetto_6, effetto_7, effetto_8 "
        "FROM core_oggetto "
        "WHERE speciale = 1 AND modello = 1 AND archiviato = 0 "
        "ORDER BY id"
    ).fetchall()
    conn.close()

    print(f"Item flagged attivi: {len(rows)}")
    print()

    # Collect all unconvertible texts
    cat_items: dict[str, set[int]] = defaultdict(set)  # category -> item ids
    cat_occurrences: dict[str, Counter] = defaultdict(Counter)  # category -> text counts
    cat_examples: dict[str, list[tuple[int, str, str]]] = defaultdict(list)  # category -> (id, nome, text)

    for row in rows:
        item_id = row["id"]
        nome = row["nome"]
        seen_any = False
        for i in range(1, 9):
            raw = row[f"effetto_{i}"]
            text = clean_legacy_value(raw)
            if not text:
                continue
            eff = convert_effect(text)
            if eff is not None:
                continue  # already convertible
            category, detail = categorise(text)
            cat_items[(category, detail)].add(item_id)
            cat_occurrences[(category, detail)][text] += 1
            if len(cat_examples[(category, detail)]) < 6:
                cat_examples[(category, detail)].append((item_id, nome, text))
            seen_any = True

    # Order: BLOCKED first (deliberate), then CURED (already handled, anomaly),
    # then UNKNOWN_TARGET, then UNCOVERED
    order = ["BLOCKED", "CURED", "UNKNOWN_TARGET", "CONVERTIBLE", "UNCOVERED"]

    for prefix in order:
        for (category, detail), item_ids in cat_items.items():
            if category != prefix:
                continue
            n_items = len(item_ids)
            n_texts = len(cat_occurrences[(category, detail)])
            n_occ = sum(cat_occurrences[(category, detail)].values())
            print(f"{'='*70}")
            print(f"  {category}: {detail}")
            print(f"  {n_items} item, {n_texts} testi distinti, {n_occ} occorrenze")
            print()
            for text, count in cat_occurrences[(category, detail)].most_common(15):
                print(f"    {count:4d}  {text}")
            print()
            print(f"  Esempi di item:")
            for iid, iname, itext in cat_examples[(category, detail)][:6]:
                print(f"    #{iid}  {iname[:60]:60s}  {itext}")
            print()

    # Summary
    print(f"{'='*70}")
    print("RIEPILOGO")
    print()
    for prefix in order:
        for (category, detail), item_ids in cat_items.items():
            if category != prefix:
                continue
            n_items = len(item_ids)
            n_texts = len(cat_occurrences[(category, detail)])
            n_occ = sum(cat_occurrences[(category, detail)].values())
            print(f"  {category:18s}  {n_items:4d} item  {n_texts:3d} testi  {n_occ:4d} occ.  {detail}")


if __name__ == "__main__":
    main()

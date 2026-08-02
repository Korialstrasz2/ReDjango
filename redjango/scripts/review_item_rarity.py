#!/usr/bin/env python
"""Create the editorial rarity-review report described in RARITA_REVIEW_LLM_GUIDE.

The command is deliberately read-only with respect to the game database.  It
reads the live catalogue and market settings, then writes a JSON proposal file
which a human can approve later through the editor or a dedicated migration.

Run from the project root:
    venv\\Scripts\\python.exe redjango\\scripts\\review_item_rarity.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = Path(__file__).resolve().parents[1] / "rarita_review_proposals.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "redjango.settings")

import django  # noqa: E402

django.setup()

from backend.core.models import Oggetto  # noqa: E402
from backend.market.config import configuration_payload  # noqa: E402
from backend.market.generator import parse_loot_levels  # noqa: E402


REVIEWED_RARITIES = (2, 3, 4)
RARITY_PROBABILITIES = {1: 0.68, 2: 0.15, 3: 0.10, 4: 0.05, 5: 0.02}
MATERIAL_RE = re.compile(r"\s*\([^)]*\)\s*$")
LEVEL_RE = re.compile(r"\blv\.?\s*\d+\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\b\d+\b")
THEMED_TYPES = {"armatura", "armaturaanimale", "spadalunga", "mazza", "bastone", "asciaaduemani", "lancia", "arcolungo"}
ORDINARY_TYPES = {
    "pozione", "pergamena", "anello", "amuleto", "orecchino", "spilla", "fascia", "cintura", "mantello",
    "martello", "tirapugni", "nunchaku", "coltello", "daga", "armblade", "stiletto", "shiv", "kriss",
    "mazzafrusta", "kusarigama", "sciabola", "katana", "fioretto", "estoc", "martellodaguerra",
    "bastoneconpesi", "zweihander", "picca", "beccodicorvo", "tonfa", "tridente", "coltellodalancio",
    "accettadalancio", "shuriken", "balestra", "balestraaripetizione", "arcocorto", "arcocomposito",
    "chukonu", "accetta", "scudo", "chainmail", "veste", "bastonemagico", "freccia", "gemmaanima",
    "pietrapreziosa", "sacca", "portapozioni", "libromagie", "setscassinamento", "reagente",
}


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _source(item: Oggetto) -> dict[str, Any]:
    """Keep every guide-required source field beside the editorial proposal."""
    return {
        "id": item.id,
        "nome": item.nome,
        "rarita": item.rarita,
        "modello": item.modello,
        "temporaneo": item.temporaneo,
        "archiviato": item.archiviato,
        "archived_at": item.archived_at,
        "speciale": item.speciale,
        "valore": item.valore,
        "peso": item.peso,
        "tipo_1": item.tipo_1,
        "tipo_2": item.tipo_2,
        "tipo_3": item.tipo_3,
        "tipo_4": item.tipo_4,
        "tipo_arma": {
            "id": item.tipo_arma_id,
            "nome": item.tipo_arma.nome if item.tipo_arma_id else None,
        },
        "pa_per_attacco": item.pa_per_attacco,
        "lv_loot": item.lv_loot,
        "regione_loot": item.regione_loot,
        "peso_regione": item.peso_regione,
        "descrizione": item.descrizione,
        "effetto_1": item.effetto_1,
        "effetto_2": item.effetto_2,
        "effetto_3": item.effetto_3,
        "effetto_4": item.effetto_4,
        "effetto_5": item.effetto_5,
        "effetto_6": item.effetto_6,
        "effetto_7": item.effetto_7,
        "effetto_8": item.effetto_8,
        "regole_speciali": item.regole_speciali,
        "effects": item.effects,
        "weapon_profile": item.weapon_profile,
        "metadata": item.metadata,
    }


def _valid_levels(item: Oggetto, rules: dict[str, Any]) -> list[int]:
    return sorted(level for level in parse_loot_levels(item.lv_loot) if rules["minLevel"] <= level <= rules["maxLevel"])


def _family_key(item: Oggetto) -> str:
    """Group material/slot variants without conflating different item types."""
    name = MATERIAL_RE.sub("", item.nome.casefold())
    name = LEVEL_RE.sub("lv", name)
    name = NUMBER_RE.sub("#", name)
    return f"{item.tipo_1.strip().casefold()}:{name.strip()}"


def _effect_signature(item: Oggetto) -> str:
    payload = item.effects or []
    if payload:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=_json_default)
    return "|".join(effect.strip().casefold() for effect in item.effetti_elder if effect.strip())


def _base_rarity(levels: list[int]) -> int:
    # The midpoint makes a 1-5 band less common than an item available only at
    # level 1, while preserving a clear progression for level-specific rows.
    midpoint = (levels[0] + levels[-1]) / 2
    if midpoint <= 2:
        return 1
    if midpoint <= 4:
        return 2
    if midpoint <= 6:
        return 3
    if midpoint <= 8:
        return 4
    return 5


def _named_theme(item: Oggetto) -> bool:
    if item.tipo_1.strip().casefold() not in THEMED_TYPES:
        return False
    return bool(MATERIAL_RE.search(item.nome)) and not item.nome.casefold().startswith(("armatura animale", "set "))


def _is_ambiguous(item: Oggetto) -> bool:
    has_legacy_effect = any(effect.strip() for effect in item.effetti_elder)
    has_structured_effect = bool(item.effects)
    has_rule = bool(item.regole_speciali.strip())
    # A non-ordinary item with no effect, description, or table rule has no
    # reliable mechanical identity to assess.  Leave its rarity unchanged.
    return (
        item.tipo_1.strip().casefold() not in ORDINARY_TYPES
        and not item.descrizione.strip()
        and not has_legacy_effect
        and not has_structured_effect
        and not has_rule
    )


def _market_eligibility(item: Oggetto, ranks: dict[str, list[int]], rules: dict[str, Any]) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    item_type = item.tipo_1.strip()
    if not item.modello:
        warnings.append("notTemplate")
    if item.archiviato or item.archived_at:
        warnings.append("archived")
    if item.speciale:
        warnings.append("special")
    if not _valid_levels(item, rules):
        warnings.append("noValidLootLevel")
    if not any(rank < 5 for rank in ranks.get(item_type, [])):
        warnings.append("noEnabledShopRankBelow5")
    return not warnings, warnings


def _price_adjustment(item: Oggetto, same_type_level_values: dict[tuple[str, int], list[int]], levels: list[int]) -> tuple[int, str | None]:
    value = item.valore or 0
    if value <= 0:
        return 0, None
    peer_values = [
        peer_value
        for level in levels
        for peer_value in same_type_level_values.get((item.tipo_1.strip(), level), [])
        if peer_value > 0
    ]
    if len(peer_values) < 4:
        return 0, None
    typical = median(peer_values)
    if typical <= 0:
        return 0, None
    # Price only moves a tier when it is an unmistakable outlier among real
    # same-type, same-loot peers.  Ordinary material progressions often rise
    # in price together, so a smaller multiplier must not dominate the review.
    if value >= typical * 10:
        return 1, f"Value {value} is at least 10x the same-type/loot median {typical:g}."
    return 0, None


def _effect_adjustment(item: Oggetto) -> tuple[int, str | None]:
    # Multiple structured effects and explicitly scaling/dynamic effects are
    # materially more impactful than a single normal stat bonus at the same
    # loot band.  Numeric magnitude alone is intentionally not used here: it
    # already tracks the generated level progressions.
    effects = item.effects if isinstance(item.effects, list) else []
    if len(effects) >= 3:
        return 1, f"It has {len(effects)} structured effects, so it receives one impact tier."
    text = " ".join([item.descrizione, item.regole_speciali, *item.effetti_elder]).casefold()
    if any(token in text for token in ("resurrez", "permanente", "per livello", "personaggio.livello")):
        return 1, "Its text includes a resurrection, permanent, or level-scaling effect."
    return 0, None


def _proposal(item: Oggetto, levels: list[int], same_type_level_values: dict[tuple[str, int], list[int]]) -> tuple[int, list[str]]:
    baseline = _base_rarity(levels)
    proposed = baseline
    reasons = [f"Loot levels {levels} have midpoint {(levels[0] + levels[-1]) / 2:g}, giving baseline rarity {baseline}."]
    price_adjustment, price_reason = _price_adjustment(item, same_type_level_values, levels)
    effect_adjustment, effect_reason = _effect_adjustment(item)
    proposed += price_adjustment + effect_adjustment
    if price_reason:
        reasons.append(price_reason)
    if effect_reason:
        reasons.append(effect_reason)
    if _named_theme(item):
        # A named faction/style item can remain distinctive even at low level,
        # but this is not enough on its own to make it very rare.
        if proposed < 2:
            proposed = 2
            reasons.append("The named themed equipment has a minimum distinctive-market tier of 2.")
    proposed = max(1, min(5, proposed))
    return proposed, reasons


def _comparables(item: Oggetto, by_type: dict[str, list[Oggetto]], rules: dict[str, Any]) -> list[int]:
    item_levels = _valid_levels(item, rules)
    item_family = _family_key(item)
    item_signature = _effect_signature(item)

    def score(candidate: Oggetto) -> tuple[int, int, int, int]:
        candidate_levels = _valid_levels(candidate, rules)
        distance = min((abs(a - b) for a in item_levels for b in candidate_levels), default=99)
        return (
            0 if _family_key(candidate) == item_family else 1,
            0 if _effect_signature(candidate) == item_signature else 1,
            distance,
            candidate.id,
        )

    candidates = [candidate for candidate in by_type[item.tipo_1.strip()] if candidate.id != item.id]
    return [candidate.id for candidate in sorted(candidates, key=score)[:3]]


def build_report() -> dict[str, Any]:
    configuration = configuration_payload()
    rules = configuration["generatorRules"]
    ranks: dict[str, list[int]] = defaultdict(list)
    for shop_type in configuration["shopTypes"]["types"]:
        if not shop_type["enabled"]:
            continue
        for item_type, rank in shop_type["itemTypeRanks"].items():
            ranks[item_type].append(int(rank))

    items = list(
        Oggetto.objects.filter(rarita__in=REVIEWED_RARITIES)
        .select_related("tipo_arma")
        .order_by("id")
    )
    by_type: dict[str, list[Oggetto]] = defaultdict(list)
    same_type_level_values: dict[tuple[str, int], list[int]] = defaultdict(list)
    for item in items:
        by_type[item.tipo_1.strip()].append(item)
        for level in _valid_levels(item, rules):
            if item.valore is not None:
                same_type_level_values[(item.tipo_1.strip(), level)].append(item.valore)

    proposals: list[dict[str, Any]] = []
    proposed_counts: Counter[str] = Counter()
    needs_human_count = 0
    market_ineligible_count = 0
    for item in items:
        levels = _valid_levels(item, rules)
        market_eligible, eligibility_warnings = _market_eligibility(item, ranks, rules)
        ambiguous = _is_ambiguous(item)
        needs_human = ambiguous or not market_eligible
        decision_reasons: list[str] = []
        if needs_human:
            proposed = item.rarita
        else:
            proposed, decision_reasons = _proposal(item, levels, same_type_level_values)
        warnings = list(eligibility_warnings)
        if ambiguous:
            warnings.append("ambiguousIdentityOrMechanics")
        min_rank = min((rank for rank in ranks.get(item.tipo_1.strip(), []) if rank < 5), default=None)
        reasons = [
            f"tipo_1={item.tipo_1!r}; lv_loot={item.lv_loot!r}; valid levels={levels}; valore={item.valore!r}.",
            f"Market rarity probabilities are 1=68%, 2=15%, 3=10%, 4=5%, 5=2%; best enabled shop rank for this type is {min_rank!r}.",
        ]
        reasons.extend(decision_reasons)
        comparable_ids = _comparables(item, by_type, rules)
        if comparable_ids:
            reasons.append(f"Compared with same-type, nearest-loot catalogue IDs {comparable_ids}.")
        if needs_human:
            reasons.append("Rarity retained because the available data does not support a safe editorial change.")
        confidence = "low" if needs_human else "medium" if _named_theme(item) or not item.tipo_1.strip() else "high"
        proposals.append({
            "id": item.id,
            "name": item.nome,
            "currentRarity": item.rarita,
            "proposedRarity": proposed,
            "confidence": confidence,
            "needsHumanReview": needs_human,
            "marketEligible": market_eligible,
            "comparables": comparable_ids,
            "reasons": reasons,
            "warnings": warnings,
            "source": _source(item),
        })
        proposed_counts[str(proposed)] += 1
        needs_human_count += needs_human
        market_ineligible_count += not market_eligible

    return {
        "scope": {"currentRarities": list(REVIEWED_RARITIES), "reviewedCount": len(proposals)},
        "summary": {
            "proposedCounts": {str(rarity): proposed_counts[str(rarity)] for rarity in range(6)},
            "needsHumanReviewCount": needs_human_count,
            "marketIneligibleCount": market_ineligible_count,
        },
        "marketConfiguration": configuration,
        "reviewPolicy": {
            "databaseWrites": False,
            "lootBandBaseline": {"1-2": 1, "3-4": 2, "5-6": 3, "7-8": 4, "9-10": 5},
            "humanReview": "Retain the current rarity when mechanics/identity are ambiguous or the item is ineligible for market generation.",
        },
        "proposals": proposals,
    }


def main() -> None:
    report = build_report()
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")
    print(json.dumps(report["scope"], ensure_ascii=False))
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(REPORT_PATH)


if __name__ == "__main__":
    main()

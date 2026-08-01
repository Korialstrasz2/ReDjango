from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from backend.core.models import Oggetto


def parse_loot_levels(raw: object) -> set[int]:
    """Return every level supported by Elder's compact ``1-4`` notation.

    Imported catalogues use both two-part ranges and chains such as ``4-5-6``.
    Treating them as an inclusive band is the useful compatibility behaviour and
    prevents those otherwise valid templates from silently disappearing.
    """
    text = str(raw or "").strip()
    if not text:
        return set()
    try:
        values = [int(piece.strip()) for piece in text.split("-")]
    except ValueError:
        return set()
    if not values or any(value < 0 for value in values):
        return set()
    return set(range(min(values), max(values) + 1))


def parse_loot_level(raw: object) -> int | None:
    """Compatibility helper for callers that only need the first eligible level."""
    levels = parse_loot_levels(raw)
    return min(levels) if levels else None


@dataclass(frozen=True)
class GenerationResult:
    seed: str
    entries: list[dict]
    diagnostics: dict


def generate_stock(
    *,
    seed: str,
    category: dict,
    level: int,
    region_key: str,
    rules: dict,
    candidates: list[Oggetto] | None = None,
    price_modifier_percent: int = 0,
) -> GenerationResult:
    rng = random.Random(seed)
    ranks = category["itemTypeRanks"]
    if candidates is None:
        candidates = list(Oggetto.objects.filter(modello=True, archiviato=False, archived_at__isnull=True, speciale=False).exclude(rarita=Oggetto.Rarita.UNICO))
    usable = []
    for item in candidates:
        item_levels = parse_loot_levels(item.lv_loot)
        item_type = item.tipo_1.strip()
        # An item without a rarity has no bucket to be drawn from. It used to be
        # folded into rarity 1, which made a missing value look like a choice;
        # skipping it here keeps the eligibility report the single explanation.
        if item.rarita is None:
            continue
        if not item_levels or item_type not in ranks or ranks[item_type] >= 5:
            continue
        usable.append((item, item_levels, ranks[item_type]))
    # quantityScale is the global size dial; 1 is the neutral value, so a rules
    # dict written before the key existed keeps its current shop sizes.
    target = max(0, round((rules["baseCount"] + level * rules["countPerLevel"]) * category["inventoryMultiplier"] * rules.get("quantityScale", 1) * (1 - rules["countVariance"] + rng.random() * rules["countVariance"] * 2)))
    counts: Counter[int] = Counter()
    missing: Counter[str] = Counter()
    deltas = rules["fallbackLevelDeltas"]
    rarity_rolls = [
        (rarity, probability)
        for rarity, probability in rules["rarityProbabilities"].items()
        if probability > 0
    ]
    rarity_counts: Counter[str] = Counter()
    for _ in range(target):
        if not rarity_rolls:
            missing["rarity"] += 1
            continue
        rarity_pick, roll = rarity_rolls[0][0], rng.random()
        acc = 0.0
        for rarity, probability in rarity_rolls:
            acc += probability
            if roll <= acc:
                rarity_pick = rarity
                break
        subset = []
        for delta in deltas:
            subset = [(item, rank) for item, item_levels, rank in usable if max(0, level + delta) in item_levels and item.rarita == int(rarity_pick) and counts[item.id] < rules["maximumCopies"]]
            if subset:
                break
        if not subset:
            missing["eligible"] += 1
            missing[f"rarity:{rarity_pick}"] += 1
            continue
        rarity_counts[rarity_pick] += 1
        weighted = []
        for item, rank in subset:
            weight = 2.5 ** (4 - rank)
            if item.regione_loot.strip().lower() == region_key.lower(): weight *= max(1, item.peso_regione or 1)
            elif not item.regione_loot.strip(): weight *= 1
            else: weight *= .35
            weighted.append((item, max(.01, weight)))
        chosen = rng.choices([item for item, _weight in weighted], weights=[weight for _item, weight in weighted], k=1)[0]
        counts[chosen.id] += 1
    entries = []
    for item_id, quantity in sorted(counts.items()):
        item = next(item for item, _levels, _rank in usable if item.id == item_id)
        price = max(0, round((item.valore or 0) * (rules["priceBasePercent"] + rules["priceLevelPercent"] * level) / 100 * (1 + price_modifier_percent / 100)))
        entries.append({"itemId": item_id, "quantity": quantity, "unitPrice": price, "source": "generated"})
    return GenerationResult(seed=seed, entries=entries, diagnostics={"requestedRolls": target, "fulfilledRolls": sum(counts.values()), "missingByItemType": dict(missing), "rarityMix": dict(rarity_counts), "candidatePoolSize": len(usable)})

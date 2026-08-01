from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from backend.core.models import Oggetto

# Rank 0 is the shop's signature merchandise and rank 4 its afterthought; the
# ratio between them is what makes a fabbro look like a fabbro.
RANK_WEIGHT_BASE = 2.5
FOREIGN_REGION_WEIGHT = .35


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


class _Shelf:
    """One rarity's draw pile, held as parallel arrays.

    The previous generator rebuilt the eligible subset inside every roll, which
    made a roll cost a full pass over the catalogue and, worse, made the copy
    cap the only thing keeping a heavy template from taking half the shop. Here
    a pick simply discounts the weight it just used, so spreading the stock over
    more templates costs nothing.
    """

    __slots__ = ("items", "weights", "remaining")

    def __init__(self) -> None:
        self.items: list[Oggetto] = []
        self.weights: list[float] = []
        self.remaining = 0

    def add(self, item: Oggetto, weight: float) -> None:
        self.items.append(item)
        self.weights.append(weight)
        self.remaining += 1

    def draw(self, rng: random.Random) -> int:
        return rng.choices(range(len(self.items)), weights=self.weights, k=1)[0]

    def take(self, index: int, factor: float, *, exhausted: bool) -> None:
        # A varietyBias of 0 zeroes the weight on the first copy, which retires
        # the template just as surely as the copy cap does; counting it as still
        # available would leave the shelf claiming stock it cannot draw.
        weight = 0.0 if exhausted else self.weights[index] * factor
        if weight <= 0:
            self.remaining -= 1
        self.weights[index] = weight


def _level_distance(item_levels: set[int], level: int, deltas: list[int]) -> int | None:
    """How many levels off the shop's grade the nearest usable band sits."""
    return min((abs(delta) for delta in deltas if max(0, level + delta) in item_levels), default=None)


def _shelves(
    candidates: list[Oggetto],
    ranks: dict[str, int],
    level: int,
    region_key: str,
    deltas: list[int],
    spread: int,
    spread_weight: float,
) -> tuple[dict[int, _Shelf], dict[int, _Shelf], int]:
    """Split the catalogue into a preferred and a fallback pile per rarity."""
    near: dict[int, _Shelf] = {}
    far: dict[int, _Shelf] = {}
    size = 0
    region = region_key.lower()
    for item in candidates:
        # An item without a rarity has no bucket to be drawn from. It used to be
        # folded into rarity 1, which made a missing value look like a choice;
        # skipping it here keeps the eligibility report the single explanation.
        if item.rarita is None:
            continue
        rank = ranks.get(item.tipo_1.strip())
        if rank is None or rank >= 5:
            continue
        distance = _level_distance(parse_loot_levels(item.lv_loot), level, deltas)
        if distance is None:
            continue
        weight = RANK_WEIGHT_BASE ** (4 - rank)
        item_region = item.regione_loot.strip().lower()
        if item_region == region:
            weight *= max(1, item.peso_regione or 1)
        elif item_region:
            weight *= FOREIGN_REGION_WEIGHT
        shelves = near if distance <= spread else far
        shelves.setdefault(int(item.rarita), _Shelf()).add(item, max(.01, weight * spread_weight ** distance))
        size += 1
    return near, far, size


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
    if candidates is None:
        candidates = list(Oggetto.objects.filter(modello=True, archiviato=False, archived_at__isnull=True, speciale=False).exclude(rarita=Oggetto.Rarita.UNICO))
    # Every dial below has a neutral default, so a rules dict written before the
    # key existed keeps producing the stock it produced yesterday.
    maximum_copies = int(rules["maximumCopies"])
    spread = int(rules.get("levelSpread", 0))
    spread_weight = float(rules.get("levelSpreadWeight", 1))
    variety_bias = float(rules.get("varietyBias", 1))
    near, far, pool_size = _shelves(candidates, category["itemTypeRanks"], level, region_key, rules["fallbackLevelDeltas"], spread, spread_weight)
    target = max(0, round((rules["baseCount"] + level * rules["countPerLevel"]) * category["inventoryMultiplier"] * rules.get("quantityScale", 1) * (1 - rules["countVariance"] + rng.random() * rules["countVariance"] * 2)))
    rarity_rolls = [
        (int(rarity), probability)
        for rarity, probability in rules["rarityProbabilities"].items()
        if probability > 0
    ]
    counts: Counter[int] = Counter()
    stocked: dict[int, Oggetto] = {}
    missing: Counter[str] = Counter()
    rarity_counts: Counter[str] = Counter()
    substitutions = 0
    for _ in range(target):
        if not rarity_rolls:
            missing["rarity"] += 1
            continue
        rolled, roll, acc = rarity_rolls[0][0], rng.random(), 0.0
        for rarity, probability in rarity_rolls:
            acc += probability
            if roll <= acc:
                rolled = rarity
                break
        # A rarity the catalogue cannot serve for this shop used to burn the roll
        # outright, which is most of why narrow shops came out short. Sliding to
        # the closest rarity that can be served keeps the roll and the intent.
        shelf = None
        served = rolled
        for rarity in sorted((rarity for rarity, _probability in rarity_rolls), key=lambda value: (abs(value - rolled), -value)):
            shelf = next((pile[rarity] for pile in (near, far) if rarity in pile and pile[rarity].remaining), None)
            if shelf:
                served = rarity
                break
        if shelf is None:
            missing["eligible"] += 1
            missing[f"rarity:{rolled}"] += 1
            continue
        substitutions += served != rolled
        rarity_counts[str(served)] += 1
        index = shelf.draw(rng)
        item = shelf.items[index]
        stocked[item.id] = item
        counts[item.id] += 1
        shelf.take(index, variety_bias, exhausted=counts[item.id] >= maximum_copies)
    entries = []
    for item_id, quantity in sorted(counts.items()):
        item = stocked[item_id]
        price = max(0, round((item.valore or 0) * (rules["priceBasePercent"] + rules["priceLevelPercent"] * level) / 100 * (1 + price_modifier_percent / 100)))
        entries.append({"itemId": item_id, "quantity": quantity, "unitPrice": price, "source": "generated"})
    return GenerationResult(seed=seed, entries=entries, diagnostics={"requestedRolls": target, "fulfilledRolls": sum(counts.values()), "distinctItems": len(entries), "raritySubstitutions": substitutions, "missingByItemType": dict(missing), "rarityMix": dict(rarity_counts), "candidatePoolSize": pool_size})

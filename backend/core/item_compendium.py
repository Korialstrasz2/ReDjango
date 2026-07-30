"""Player-facing read model for the "Oggetti" guide.

The management catalogue in :mod:`backend.core.item_selectors` answers "what may
an author edit"; this module answers "what may a player read". The two are kept
apart on purpose: the compendium never exposes authoring state (``speciale``,
``modello``, internal notes, import provenance) and it resolves every stored
code into readable Italian, so the guide can present an item without repeating
the rules behind it.
"""

from __future__ import annotations

import re
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet

from backend.characters.selectors import item_image_url
from backend.characters.services.custom_effects import (
    EFFECT_OPERATIONS,
    effect_target_options,
)
from backend.characters.services.inventory_rules import (
    EQUIPMENT_SLOT_LABELS,
    item_compatible_with_equipment_slot,
    item_weapon_profile,
)

# `lv_loot` uses Elder's compact band notation and the shop generator already
# owns the only correct reading of it; a second parser here would eventually
# disagree with the levels a shop actually rolls.
from backend.market.config import get_generator_rules
from backend.market.generator import parse_loot_levels

from .guides_it import WEAPON_TYPE_LABELS
from .item_selectors import CATALOG_SORT_OPTIONS, NONE_SENTINEL, weapon_type_profiles
from .models import Oggetto, OpzioneTipoOggetto
from .weapon_rules import (
    COST_BANDS,
    DAMAGE_MODIFIERS,
    HEAVINESS_MODIFIERS,
    LENGTH_MODIFIERS,
    SKILL_MAPPINGS,
)


COMPENDIUM_PAGE_SIZE = 48
COMPENDIUM_MAXIMUM_PAGE_SIZE = 200

# A player reads the catalogue of reusable models. Character-owned copies,
# archived rows and provisional drafts are authoring state, not game content.
PLAYER_SCOPE = {
    "modello": True,
    "temporaneo": False,
    "archiviato": False,
    "archived_at__isnull": True,
}

TYPE_POSITION_LABELS = {
    1: "Categoria",
    2: "Sottotipo",
    3: "Variante",
    4: "Grado",
}

TYPE_POSITION_NOTES = {
    1: "La classificazione principale: decide l'icona, lo slot di equipaggiamento e i negozi che possono venderlo.",
    2: "Precisa cosa fa l'oggetto dentro la sua categoria.",
    3: "Distinzione ulteriore, usata solo da alcune famiglie di oggetti.",
    4: "Fascia o livello del pezzo, quando la sua famiglia ne prevede una.",
}

RARITY_NOTES = {
    0: "Pezzo unico. Non viene mai generato nelle scorte di un negozio: esiste solo dove il Master lo mette.",
    1: "Fattura comune: la maggior parte del bottino e delle scorte di un negozio.",
    2: "Fattura buona, ancora facile da trovare.",
    3: "Pezzo pregiato: raro nelle scorte ordinarie.",
    4: "Pezzo eccellente: raramente esposto in un negozio.",
    5: "Fattura leggendaria: la fascia più rara fra quelle generabili.",
}

COMBAT_MODE_LABELS = {
    "melee": "Mischia",
    "throwable": "Da lancio",
    "ranged": "A distanza",
    "unarmed": "Mani nude",
    "magic": "Magica",
    "nature": "Forma naturale",
}

HANDLING_LABELS = {
    "one_handed": "Una mano",
    "two_handed": "Due mani",
    "special": "Impugnatura speciale",
}

AMMUNITION_LABELS = {
    "freccia": "Frecce",
    "dardo": "Dardi",
    "proiettile": "Proiettili",
}

LENGTH_NOTES = {
    "corta": "Una mano, 3 PA per attacco.",
    "media": "Una mano, 4 PA per attacco.",
    "lunga": "Due mani e slot Scudo libero, 6 PA per attacco.",
    "maninude": "Nessuna arma impugnata, 2 PA per attacco.",
}

MODIFIER_LABELS = {
    "attacco": "Attacco",
    "difesa": "Difesa",
    "pa": "Punti Azione",
    "paPerAttacco": "PA per attacco",
    "tier": "Tier del danno",
    "energia": "Energia",
    "ap": "Penetrazione armatura",
    "ap_percento": "Penetrazione armatura %",
}

GLOSSARY = (
    {
        "key": "valore",
        "title": "Valore",
        "text": (
            "Il prezzo di riferimento del regolamento, in monete. Un negozio parte da una "
            "percentuale di questo valore e la corregge in base al livello e alla contrattazione, "
            "quindi il prezzo esposto sul mercato può essere diverso."
        ),
    },
    {
        "key": "peso",
        "title": "Peso",
        "text": (
            "Peso trasportato. Gli oggetti nei primi slot magici dello zaino non pesano, e lo "
            "zaino tiene sempre i pezzi più pesanti in quegli slot."
        ),
    },
    {
        "key": "rarita",
        "title": "Rarità",
        "text": (
            "Da 1 a 5 indica la fattura del pezzo e quanto spesso finisce nelle scorte generate. "
            "Unico è fuori scala: non viene mai generato automaticamente."
        ),
    },
    {
        "key": "lv_loot",
        "title": "Livello di bottino",
        "text": (
            "La fascia di livello in cui l'oggetto può comparire. La notazione compatta 4-6 "
            "indica una fascia inclusiva: livelli 4, 5 e 6."
        ),
    },
    {
        "key": "regione",
        "title": "Regione",
        "text": (
            "La provenienza dell'oggetto. Un negozio della stessa regione ha più probabilità di "
            "averlo in magazzino; un oggetto senza regione può comparire ovunque."
        ),
    },
    {
        "key": "pa",
        "title": "PA per attacco",
        "text": (
            "I Punti Azione spesi per un attacco con quest'arma. Deriva dalla lunghezza della "
            "categoria e può essere corretto dagli effetti dell'oggetto."
        ),
    },
    {
        "key": "tier",
        "title": "Tier",
        "text": (
            "Tutto ciò che il regolamento chiama bonus al danno è salvato sul Tier, che sceglie "
            "la formula dei dadi di danno. Non esiste un bonus di danno fisso separato."
        ),
    },
    {
        "key": "effetti",
        "title": "Effetti automatici",
        "text": (
            "Le modifiche che il sistema applica davvero alla scheda quando l'oggetto è "
            "equipaggiato, nell'ordine indicato."
        ),
    },
    {
        "key": "effetti_elder",
        "title": "Effetti descritti a testo",
        "text": (
            "Testo del regolamento originale conservato così com'è. Sono regole valide da "
            "applicare al tavolo, ma il sistema non le calcola automaticamente."
        ),
    },
    {
        "key": "slot",
        "title": "Slot di equipaggiamento",
        "text": (
            "Dove il pezzo può essere indossato o impugnato. Gli slot extra accettano qualsiasi "
            "oggetto, quindi non compaiono fra le destinazioni suggerite."
        ),
    },
)

_NUMBERED_SLOT = re.compile(r"_\d+$")
_NUMBERED_LABEL = re.compile(r"\s+\d+$")


def _humanized(value: str) -> str:
    """Readable fallback for a stored code that has no configured label."""
    text = str(value or "").strip()
    if not text:
        return ""
    return WEAPON_TYPE_LABELS.get(text, text.replace("_", " ").replace("-", " ").capitalize())


def _slot_families() -> dict[str, str]:
    """Collapse the numbered slots into one entry per family.

    A player wants to read "Anello", not the eight interchangeable ring slots
    the character sheet happens to expose.
    """
    families: dict[str, str] = {}
    for slot, label in EQUIPMENT_SLOT_LABELS.items():
        families.setdefault(_NUMBERED_SLOT.sub("", slot), _NUMBERED_LABEL.sub("", label))
    return families


def _type_options() -> list[dict[str, Any]]:
    return [
        {
            "position": option.posizione,
            "value": option.valore,
            # The administrator's label wins; the humanized code is only a
            # fallback so an unlabelled option is still readable in the guide.
            "label": option.etichetta or _humanized(option.valore),
        }
        for option in OpzioneTipoOggetto.objects.filter(
            attiva=True,
            archived_at__isnull=True,
        ).order_by("posizione", "ordine", "etichetta", "valore")
    ]


def _rarity_probabilities() -> dict[int, float]:
    try:
        rules = get_generator_rules()
    except ValidationError:
        # A misconfigured generator must not take the whole guide down: the
        # rarity note simply loses its shop probability.
        return {}
    probabilities = rules.get("rarityProbabilities")
    if not isinstance(probabilities, dict):
        return {}
    resolved: dict[int, float] = {}
    for key, value in probabilities.items():
        try:
            resolved[int(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return resolved


def _rarity_choices() -> list[dict[str, Any]]:
    probabilities = _rarity_probabilities()
    return [
        {
            "value": value,
            "label": label,
            "note": RARITY_NOTES.get(value, ""),
            "shopShare": probabilities.get(value),
        }
        for value, label in Oggetto.Rarita.choices
    ]


def _modifier_notes(*sources: dict[str, Any]) -> list[str]:
    notes = []
    for modifiers in sources:
        for target, amount in modifiers.items():
            if not amount:
                continue
            notes.append(f"{MODIFIER_LABELS.get(target, _humanized(target))} {amount:+g}")
    return notes


def _weapon_category(entry: dict[str, Any]) -> dict[str, Any]:
    """One weapon category as the compendium shows it, unique power included."""
    name = str(entry.get("name") or "")
    combat_mode = str(entry.get("combatMode") or "")
    length = str(entry.get("length") or "")
    heaviness = str(entry.get("heaviness") or "")
    damage_type = str(entry.get("damageType") or "")
    power = str(entry.get("power") or "")
    handling = str(entry.get("handling") or "")
    band = str(entry.get("costBand") or "")
    length_rules = LENGTH_MODIFIERS.get(length, {})
    ammunition = str(entry.get("ammunitionType") or "")
    return {
        "id": entry.get("id"),
        "key": name,
        "label": _humanized(name),
        "combatMode": combat_mode,
        "combatModeLabel": COMBAT_MODE_LABELS.get(combat_mode, ""),
        "length": length,
        "lengthLabel": _humanized(length),
        "lengthNote": LENGTH_NOTES.get(length, ""),
        "lengthNotes": _modifier_notes(length_rules.get("effects", {})),
        "actionPointCost": length_rules.get("paPerAttacco"),
        "heaviness": heaviness,
        "heavinessLabel": _humanized(heaviness),
        "heavinessNotes": _modifier_notes(HEAVINESS_MODIFIERS.get(heaviness, {})),
        "power": power,
        "powerLabel": _humanized(power),
        # Precision/power changes nothing numerically: it only decides which
        # attack competence answers for the weapon.
        "powerSkill": SKILL_MAPPINGS["power"].get(power, ""),
        "damageType": damage_type,
        "damageTypeLabel": _humanized(damage_type),
        "damageNotes": _modifier_notes(DAMAGE_MODIFIERS.get(damage_type, {})),
        "handling": handling,
        "handlingLabel": HANDLING_LABELS.get(handling, ""),
        "costBand": band,
        "costBandLabel": str(COST_BANDS.get(band, {}).get("label") or ""),
        "baseRangeMeters": entry.get("baseRangeMeters") or None,
        "ammunitionType": ammunition,
        "ammunitionLabel": AMMUNITION_LABELS.get(ammunition, ""),
        "magazineSize": entry.get("magazineSize") or None,
        "reloadBaseCost": entry.get("reloadBaseCost") or None,
        "reloadPerProjectileCost": entry.get("reloadPerProjectileCost") or None,
        # The bonus notes are the category's unique power: the reason a player
        # picks a katana over a longsword.
        "uniquePowers": [str(note).strip() for note in entry.get("bonusNotes") or [] if str(note).strip()],
        "specialRules": [str(rule).strip() for rule in entry.get("specialRules") or [] if str(rule).strip()],
        "incomplete": bool(entry.get("incomplete")),
    }


def weapon_categories() -> list[dict[str, Any]]:
    return sorted(
        (_weapon_category(entry) for entry in weapon_type_profiles()),
        key=lambda entry: entry["label"],
    )


def _subtypes_by_category() -> dict[str, list[str]]:
    """Which `tipo_2` values actually occur under each `tipo_1`.

    The catalogue configures 188 subtypes but reuses most of them across
    families — every weapon material, for instance. Narrowing the second filter
    to the subtypes a category really has is what keeps that select usable.
    """
    pairs: dict[str, set[str]] = {}
    for category, subtype in (
        Oggetto.objects.filter(**PLAYER_SCOPE)
        .exclude(tipo_1="")
        .exclude(tipo_2="")
        .order_by()
        .values_list("tipo_1", "tipo_2")
        .distinct()
    ):
        pairs.setdefault(category, set()).add(subtype)
    return {category: sorted(values) for category, values in sorted(pairs.items())}


def _loot_levels() -> list[int]:
    levels: set[int] = set()
    for value in (
        Oggetto.objects.filter(**PLAYER_SCOPE)
        .exclude(lv_loot="")
        .order_by()
        .values_list("lv_loot", flat=True)
        .distinct()
    ):
        levels.update(parse_loot_levels(value))
    return sorted(levels)


def item_compendium_reference() -> dict[str, Any]:
    """Everything the guide needs once: filter vocabulary and connected rules."""
    options = _type_options()
    return {
        "typeGroups": [
            {
                "position": position,
                "label": label,
                "note": TYPE_POSITION_NOTES[position],
                "options": [option for option in options if option["position"] == position],
            }
            for position, label in TYPE_POSITION_LABELS.items()
        ],
        "subtypesByCategory": _subtypes_by_category(),
        "rarityChoices": _rarity_choices(),
        # `Oggetto` has a default ordering, and Django adds those columns to a
        # values_list SELECT: without clearing it, DISTINCT would run over
        # (numero_ordine, nome, regione_loot) and return every region repeated.
        "regions": sorted(
            value
            for value in Oggetto.objects.filter(**PLAYER_SCOPE)
            .exclude(regione_loot="")
            .order_by()
            .values_list("regione_loot", flat=True)
            .distinct()
        ),
        "lootLevels": _loot_levels(),
        "sortOptions": [
            {"value": value, "label": label}
            for value, label in (
                ("", "Ordine del catalogo"),
                ("name", "Nome (A → Z)"),
                ("name_desc", "Nome (Z → A)"),
                ("rarity_desc", "Rarità (dalla più alta)"),
                ("rarity", "Rarità (dalla più bassa)"),
                ("value_desc", "Valore (dal più alto)"),
                ("value", "Valore (dal più basso)"),
                ("weight", "Peso (dal più leggero)"),
                ("weight_desc", "Peso (dal più pesante)"),
            )
        ],
        "weaponCategories": weapon_categories(),
        "weaponAxes": {
            "heaviness": {
                "label": "Pesantezza",
                "note": "Quanto è massiccia l'arma: sposta Attacco, Tier ed Energia.",
                "options": [
                    {"value": key, "label": _humanized(key), "note": "", "notes": _modifier_notes(modifiers)}
                    for key, modifiers in HEAVINESS_MODIFIERS.items()
                ],
            },
            "length": {
                "label": "Lunghezza",
                "note": "Decide i PA per attacco e se servono due mani.",
                "options": [
                    {
                        "value": key,
                        "label": _humanized(key),
                        "note": LENGTH_NOTES.get(key, ""),
                        "notes": _modifier_notes(values.get("effects", {})),
                    }
                    for key, values in LENGTH_MODIFIERS.items()
                ],
            },
            "power": {
                "label": "Precisione / potenza",
                "note": "Non cambia le statistiche: sceglie quale competenza d'attacco si applica.",
                "options": [
                    {"value": key, "label": _humanized(key), "note": skill, "notes": []}
                    for key, skill in SKILL_MAPPINGS["power"].items()
                ],
            },
            "damageType": {
                "label": "Tipo di danno",
                "note": "Il tipo di ferita inflitta e la resistenza che la riduce.",
                "options": [
                    {"value": key, "label": _humanized(key), "note": "", "notes": _modifier_notes(modifiers)}
                    for key, modifiers in DAMAGE_MODIFIERS.items()
                ],
            },
        },
        "effectTargets": effect_target_options(),
        "effectOperations": [
            {"value": value, "label": details["label"], "description": details["description"]}
            for value, details in EFFECT_OPERATIONS.items()
        ],
        "equipmentSlots": [
            {"value": slot, "label": label}
            for slot, label in _slot_families().items()
        ],
        "glossary": list(GLOSSARY),
    }


def _loot_level_bands(level: int) -> list[str]:
    """Every stored ``lv_loot`` string whose band contains ``level``.

    The catalogue holds only a few dozen distinct bands, so resolving them in
    Python keeps the filter exact — Elder's ``4-5-6`` chains have no SQL
    equivalent — while the query itself stays a plain ``IN``.
    """
    return [
        value
        for value in Oggetto.objects.exclude(lv_loot="")
        .order_by()
        .values_list("lv_loot", flat=True)
        .distinct()
        if level in parse_loot_levels(value)
    ]


def _compendium_queryset(
    query: str,
    *,
    types: tuple[str, str, str, str],
    rarity: int | None,
    weapon_category: str,
    region: str,
    loot_level: int | None,
    weight_min: float | None,
    weight_max: float | None,
    value_min: int | None,
    value_max: int | None,
    with_effects: bool,
    sort: str,
) -> QuerySet[Oggetto]:
    queryset = Oggetto.objects.select_related("tipo_arma", "media").filter(**PLAYER_SCOPE)
    if query:
        queryset = queryset.filter(
            Q(nome__icontains=query)
            | Q(descrizione__icontains=query)
            | Q(tipo_1__icontains=query)
            | Q(tipo_2__icontains=query)
            | Q(tipo_3__icontains=query)
            | Q(tipo_4__icontains=query)
        )
    for field, value in zip(("tipo_1", "tipo_2", "tipo_3", "tipo_4"), types):
        if value == NONE_SENTINEL:
            queryset = queryset.filter(**{field: ""})
        elif value:
            queryset = queryset.filter(**{f"{field}__iexact": value})
    if rarity is not None:
        queryset = queryset.filter(rarita=rarity)
    if weapon_category:
        # Most weapons carry their category only as `tipo_1`: the TipoArma
        # relation was filled for a minority of rows, so matching the name too
        # is what makes the filter agree with what the player sees on the card.
        queryset = queryset.filter(
            Q(tipo_arma__nome__iexact=weapon_category) | Q(tipo_1__iexact=weapon_category)
        )
    if region == NONE_SENTINEL:
        queryset = queryset.filter(regione_loot="")
    elif region:
        queryset = queryset.filter(regione_loot__iexact=region)
    if loot_level is not None:
        queryset = queryset.filter(lv_loot__in=_loot_level_bands(loot_level))
    if weight_min is not None:
        queryset = queryset.filter(peso__gte=weight_min)
    if weight_max is not None:
        queryset = queryset.filter(peso__lte=weight_max)
    if value_min is not None:
        queryset = queryset.filter(valore__gte=value_min)
    if value_max is not None:
        queryset = queryset.filter(valore__lte=value_max)
    if with_effects:
        queryset = queryset.exclude(effects=[])
    return queryset.order_by(*CATALOG_SORT_OPTIONS.get(sort, CATALOG_SORT_OPTIONS[""]))


def _item_operations(item: Oggetto) -> list[dict[str, Any]]:
    """The item's structured operations, kept in their stored order."""
    raw = item.effects if isinstance(item.effects, list) else []
    return [
        {
            "target": str(entry.get("target") or ""),
            "operation": str(entry.get("operation") or ""),
            "value": str(entry.get("value")) if entry.get("value") is not None else "",
            "condition": str(entry.get("condition") or ""),
        }
        for entry in raw
        if isinstance(entry, dict)
    ]


def _compendium_item(item: Oggetto, *, weapon_keys: dict[str, str], slots: dict[str, str]) -> dict[str, Any]:
    type_values = [item.tipo_1, item.tipo_2, item.tipo_3, item.tipo_4]
    weapon_type_name = item.tipo_arma.nome if item.tipo_arma_id and item.tipo_arma else ""
    # An item is a weapon when it points at a category or when one of its own
    # types is one; the guide must reach the same answer either way.
    weapon_category = weapon_type_name or next(
        (weapon_keys[value.casefold()] for value in type_values if value.casefold() in weapon_keys),
        "",
    )
    profile = item_weapon_profile(item)
    return {
        "id": item.id,
        "name": item.nome,
        "imageUrl": item_image_url(item),
        "typeValues": type_values,
        "description": item.descrizione,
        "value": item.valore,
        "weight": item.peso,
        "rarity": item.rarita,
        "rarityLabel": item.get_rarita_display() if item.rarita is not None else "",
        "lootLevel": item.lv_loot,
        "lootLevels": sorted(parse_loot_levels(item.lv_loot)),
        "region": item.regione_loot,
        "regionWeight": item.peso_regione,
        "operations": _item_operations(item),
        "elderEffects": [text for text in item.effetti_elder if text],
        "weaponCategory": weapon_category,
        "weaponProfile": profile if isinstance(profile, dict) else {},
        "actionPointCost": item.pa_per_attacco,
        "alchemyProfile": item.alchemy_profile if isinstance(item.alchemy_profile, dict) else {},
        "craftingProfile": item.crafting_profile if isinstance(item.crafting_profile, dict) else {},
        "equipmentSlots": sorted(
            {
                slots[family]
                for slot in EQUIPMENT_SLOT_LABELS
                if not slot.startswith("extra_slot_")
                and (family := _NUMBERED_SLOT.sub("", slot)) in slots
                and item_compatible_with_equipment_slot(item, slot)
            }
        ),
    }


def item_compendium_page(
    query: str = "",
    *,
    limit: int = COMPENDIUM_PAGE_SIZE,
    offset: int = 0,
    type_1: str = "",
    type_2: str = "",
    type_3: str = "",
    type_4: str = "",
    rarity: int | None = None,
    weapon_category: str = "",
    region: str = "",
    loot_level: int | None = None,
    weight_min: float | None = None,
    weight_max: float | None = None,
    value_min: int | None = None,
    value_max: int | None = None,
    with_effects: bool = False,
    sort: str = "",
) -> dict[str, Any]:
    queryset = _compendium_queryset(
        query,
        types=(type_1, type_2, type_3, type_4),
        rarity=rarity,
        weapon_category=weapon_category,
        region=region,
        loot_level=loot_level,
        weight_min=weight_min,
        weight_max=weight_max,
        value_min=value_min,
        value_max=value_max,
        with_effects=with_effects,
        sort=sort,
    )
    page_size = max(1, min(limit, COMPENDIUM_MAXIMUM_PAGE_SIZE))
    offset = max(0, offset)
    total = queryset.count()
    rows = list(queryset[offset:offset + page_size])
    weapon_keys = {entry["key"].casefold(): entry["key"] for entry in weapon_categories() if entry["key"]}
    slots = _slot_families()
    return {
        "items": [_compendium_item(item, weapon_keys=weapon_keys, slots=slots) for item in rows],
        "total": total,
        "offset": offset,
        "limit": page_size,
        "hasMore": offset + len(rows) < total,
    }

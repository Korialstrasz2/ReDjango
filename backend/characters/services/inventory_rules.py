from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable

from backend.core.models import Oggetto

from ..models import Equip, Faretra, Personaggio, Zaino


EQUIPMENT_SLOT_LABELS: dict[str, str] = {
    "arma": "Arma",
    "armatura": "Armatura",
    "scudo": "Scudo",
    "chainmail": "Cotta di maglia",
    "veste": "Veste",
    "vestiti": "Vestiti",
    "fascia": "Fascia",
    "spilla": "Spilla",
    "amuleto": "Amuleto",
    "cintura": "Cintura",
    "mantello": "Mantello",
    "borsello": "Borsello",
    **{f"anello_{index}": f"Anello {index}" for index in range(1, 9)},
    **{f"orecchino_{index}": f"Orecchino {index}" for index in range(1, 7)},
    **{f"sacco_{index}": f"Sacco {index}" for index in range(1, 4)},
    **{f"faretra_{index}": f"Faretra {index}" for index in range(1, 3)},
    **{f"extra_slot_{index}": f"Slot extra {index}" for index in range(1, 5)},
}

EQUIPMENT_SLOT_ORDER = tuple(EQUIPMENT_SLOT_LABELS)
EXTRA_EQUIPMENT_SLOTS = {name for name in EQUIPMENT_SLOT_ORDER if name.startswith("extra_slot_")}
EQUIPMENT_SLOT_LIMITS = {
    "anello": "anelli_max",
    "orecchino": "orecchini_max",
    "sacco": "sacchi_max",
}

SLOT_ACCEPTS: dict[str, set[str]] = {
    "armatura": {"armatura", "armaturaanimale"},
    "scudo": {"scudo"},
    "chainmail": {"chainmail", "cotta", "cotta_di_maglia"},
    "veste": {"veste"},
    "vestiti": {"vestiti", "abito"},
    "fascia": {"fascia"},
    "spilla": {"spilla"},
    "amuleto": {"amuleto"},
    "cintura": {"cintura"},
    "mantello": {"mantello"},
    "borsello": {"borsello"},
    "anello": {"anello"},
    "orecchino": {"orecchino"},
    "sacco": {"sacco", "sacca"},
    "faretra": {"faretra", "astuccio"},
}

PROJECTILE_TYPES = {
    "freccia",
    "frecce",
    "dardo",
    "dardi",
    "proiettile",
    "proiettili",
    "munizione",
    "munizioni",
}

NON_WEAPON_TYPES = {
    *PROJECTILE_TYPES,
    "armatura",
    "armaturaanimale",
    "scudo",
    "chainmail",
    "cotta",
    "veste",
    "vestiti",
    "abito",
    "fascia",
    "spilla",
    "amuleto",
    "cintura",
    "mantello",
    "borsello",
    "anello",
    "orecchino",
    "sacco",
    "sacca",
    "faretra",
    "astuccio",
    "consumabile",
    "pozione",
    "reagente",
    "strumento",
    "tesoro",
    "placeholder",
}


class InventoryRuleError(ValueError):
    def __init__(self, code: str, message: str, *, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


@dataclass(frozen=True)
class SlotReference:
    group: str
    slot: str

    @property
    def key(self) -> str:
        return f"{self.group}:{self.slot}"


def normalize_item_types(item: Oggetto | None) -> set[str]:
    if item is None:
        return set()
    values = {
        str(value).strip().lower().replace(" ", "_")
        for value in (item.tipo_1, item.tipo_2, item.tipo_3, item.tipo_4)
        if value
    }
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    aliases = metadata.get("slotTypes", [])
    if isinstance(aliases, Iterable) and not isinstance(aliases, (str, bytes, dict)):
        values.update(str(value).strip().lower().replace(" ", "_") for value in aliases if value)
    return values


def equipment_slot_kind(slot: str) -> str:
    if slot.startswith("anello_"):
        return "anello"
    if slot.startswith("orecchino_"):
        return "orecchino"
    if slot.startswith("sacco_"):
        return "sacco"
    if slot.startswith("faretra_"):
        return "faretra"
    return slot


def equipment_slot_limit(slot: str, totals: dict[str, Any]) -> int | None:
    kind = equipment_slot_kind(slot)
    total_key = EQUIPMENT_SLOT_LIMITS.get(kind)
    if total_key is None:
        return None
    try:
        return max(0, int(float(totals.get(total_key, 0) or 0)))
    except (TypeError, ValueError):
        return 0


def equipment_slot_is_active(slot: str, totals: dict[str, Any]) -> bool:
    limit = equipment_slot_limit(slot, totals)
    if limit is None:
        return True
    try:
        index = int(slot.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        return False
    return index <= limit


def item_is_weapon(item: Oggetto | None) -> bool:
    if item is None:
        return False
    types = normalize_item_types(item)
    return bool(item.tipo_arma_id or "arma" in types or (item.tipo_1 and item.tipo_1.lower() not in NON_WEAPON_TYPES))


def item_is_projectile(item: Oggetto) -> bool:
    return bool(normalize_item_types(item) & PROJECTILE_TYPES)


def item_weapon_profile(item: Oggetto | None) -> dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item.weapon_profile, dict) and item.weapon_profile:
        return item.weapon_profile
    weapon_type = getattr(item, "tipo_arma", None)
    rules = weapon_type.rules if weapon_type is not None and isinstance(weapon_type.rules, dict) else {}
    profile = rules.get("profile")
    return profile if isinstance(profile, dict) else {}


def item_is_two_handed_weapon(item: Oggetto | None) -> bool:
    if item is None or not item_is_weapon(item):
        return False
    profile = item_weapon_profile(item)
    length = str(profile.get("length") or getattr(getattr(item, "tipo_arma", None), "lunghezza", "")).casefold()
    return length == "lunga"


def item_is_one_handed_weapon(item: Oggetto | None) -> bool:
    return bool(item is not None and item_is_weapon(item) and not item_is_two_handed_weapon(item))


def equipment_dual_wield(equip: Equip | None) -> bool:
    return bool(
        equip
        and item_is_one_handed_weapon(getattr(equip, "arma", None))
        and item_is_one_handed_weapon(getattr(equip, "scudo", None))
    )


def active_weapon_slot(equip: Equip | None) -> str:
    if equipment_dual_wield(equip) and getattr(equip, "arma_primaria_slot", "arma") == "scudo":
        return "scudo"
    return "arma"


def active_equipped_weapon(equip: Equip | None) -> Oggetto | None:
    return getattr(equip, active_weapon_slot(equip), None) if equip else None


def validate_hand_configuration(equip: Equip | None) -> None:
    if equip is None:
        return
    main = getattr(equip, "arma", None)
    offhand = getattr(equip, "scudo", None)
    if item_is_two_handed_weapon(main) and offhand is not None:
        raise InventoryRuleError(
            "inventory.two_handed_requires_free_offhand",
            "Un'arma lunga richiede entrambe le mani: libera prima lo slot Scudo.",
        )
    if item_is_weapon(offhand):
        if not item_is_one_handed_weapon(offhand):
            raise InventoryRuleError(
                "inventory.offhand_weapon_must_be_one_handed",
                "Nello slot Scudo puoi equipaggiare soltanto un'arma corta o media.",
            )
        if not item_is_one_handed_weapon(main):
            raise InventoryRuleError(
                "inventory.dual_wield_requires_primary",
                "Per la doppia impugnatura serve prima un'arma corta o media nello slot Arma.",
            )


def item_compatible_with_equipment_slot(item: Oggetto | None, slot: str) -> bool:
    if item is None:
        return True
    if slot not in EQUIPMENT_SLOT_LABELS:
        return False
    if slot in EXTRA_EQUIPMENT_SLOTS:
        return True
    if slot == "arma":
        return item_is_weapon(item)
    if slot == "scudo" and item_is_one_handed_weapon(item):
        return True
    kind = equipment_slot_kind(slot)
    return bool(normalize_item_types(item) & SLOT_ACCEPTS.get(kind, {kind}))


INVENTORY_GROUPS = frozenset({"equipment", "backpack", "quiver", "utility", "campaign"})


def item_fits_container(item: Oggetto | None, group: str, slot: str) -> bool:
    """Compatibility rule used to scope a catalogue search to one destination slot."""
    if item is None:
        return True
    if group == "equipment":
        return item_compatible_with_equipment_slot(item, slot)
    if group == "quiver":
        return item_is_projectile(item)
    return group in {"backpack", "utility", "campaign"}


def compatibility_message(item: Oggetto, reference: SlotReference) -> str:
    if reference.group == "quiver":
        return f"{item.nome} non è un proiettile e non può essere riposto nella faretra."
    if reference.group == "equipment":
        label = EQUIPMENT_SLOT_LABELS.get(reference.slot, reference.slot.replace("_", " ").title())
        if normalize_item_types(item) & {"anello"}:
            suggestion = "Prova uno slot Anello o uno Slot extra."
        elif normalize_item_types(item) & {"orecchino"}:
            suggestion = "Prova uno slot Orecchino o uno Slot extra."
        else:
            suggestion = "Scegli uno slot compatibile o uno Slot extra."
        return f"{item.nome} non può essere equipaggiato nello slot {label}. {suggestion}"
    return f"{item.nome} non può essere spostato nello spazio scelto."


def get_slot_item(personaggio: Personaggio, reference: SlotReference) -> Oggetto | None:
    if reference.group == "equipment":
        if personaggio.equip is None or reference.slot not in EQUIPMENT_SLOT_LABELS:
            raise InventoryRuleError("inventory.slot_not_found", "Lo slot equipaggiamento non esiste.")
        return getattr(personaggio.equip, reference.slot)
    if reference.group in {"backpack", "quiver"}:
        try:
            index = int(reference.slot)
        except (TypeError, ValueError) as exc:
            raise InventoryRuleError("inventory.slot_not_found", "Lo spazio dell'inventario non è valido.") from exc
        if not 1 <= index <= 50:
            raise InventoryRuleError("inventory.slot_not_found", "Lo spazio dell'inventario non esiste.")
        container = personaggio.zaino if reference.group == "backpack" else personaggio.faretra
        if container is None:
            raise InventoryRuleError("inventory.container_missing", "Il contenitore non è disponibile.")
        return getattr(container, f"slot_{index}")
    raise InventoryRuleError("inventory.group_not_found", "Il contenitore scelto non esiste.")


def set_slot_item(personaggio: Personaggio, reference: SlotReference, item: Oggetto | None) -> None:
    if reference.group == "equipment":
        setattr(personaggio.equip, reference.slot, item)
        return
    container = personaggio.zaino if reference.group == "backpack" else personaggio.faretra
    setattr(container, f"slot_{int(reference.slot)}", item)


def backpack_capacity(totals: dict[str, Any]) -> int:
    magical = max(0, int(float(totals.get("slot_magici", 0) or 0)))
    normal = max(0, int(float(totals.get("slot_non_magici", 0) or 0)))
    return min(50, magical + normal)


def item_container_capacity(item: Oggetto | None, container_kind: str) -> int:
    if item is None:
        return 0
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    container = metadata.get("container", {})
    if isinstance(container, dict) and str(container.get("kind", "")).lower() == container_kind:
        try:
            return max(0, int(container.get("capacity", 0)))
        except (TypeError, ValueError):
            return 0
    match = re.search(r"(\d+)\s+(?:frecce|dardi|proiettili|spazi|slot)", item.descrizione or "", re.IGNORECASE)
    return int(match.group(1)) if match else 0


def quiver_capacity(equip: Equip | None) -> int:
    if equip is None:
        return 0
    return min(50, sum(item_container_capacity(getattr(equip, f"faretra_{index}"), "quiver") for index in (1, 2)))


def occupied_slots_after(container: Zaino | Faretra | None, capacity: int) -> list[int]:
    if container is None:
        return []
    return [index for index in range(capacity + 1, 51) if getattr(container, f"slot_{index}") is not None]


def validate_reference_is_active(personaggio: Personaggio, reference: SlotReference, totals: dict[str, Any]) -> None:
    if reference.group == "equipment":
        if reference.slot not in EQUIPMENT_SLOT_LABELS:
            raise InventoryRuleError("inventory.slot_not_found", "Lo slot equipaggiamento non esiste.")
        if not equipment_slot_is_active(reference.slot, totals):
            limit = equipment_slot_limit(reference.slot, totals)
            label = EQUIPMENT_SLOT_LABELS[reference.slot]
            raise InventoryRuleError(
                "inventory.slot_locked",
                f"Lo slot {label} è bloccato. Limite attuale: {limit}.",
            )
        return
    if reference.group not in {"backpack", "quiver"}:
        raise InventoryRuleError("inventory.group_not_found", "Il contenitore scelto non esiste.")
    try:
        index = int(reference.slot)
    except (TypeError, ValueError) as exc:
        raise InventoryRuleError("inventory.slot_not_found", "Lo spazio dell'inventario non è valido.") from exc
    if not 1 <= index <= 50:
        raise InventoryRuleError("inventory.slot_not_found", "Lo spazio dell'inventario non esiste.")
    capacity = backpack_capacity(totals) if reference.group == "backpack" else quiver_capacity(personaggio.equip)
    if index > capacity:
        container_label = "zaino" if reference.group == "backpack" else "faretra"
        raise InventoryRuleError(
            "inventory.slot_locked",
            f"Lo spazio {index} dello {container_label} è bloccato. Capacità attuale: {capacity}.",
        )


def validate_item_for_reference(item: Oggetto | None, reference: SlotReference) -> None:
    if item is None or reference.group == "backpack":
        return
    if reference.group == "quiver" and not item_is_projectile(item):
        raise InventoryRuleError("inventory.incompatible_slot", compatibility_message(item, reference))
    if reference.group == "equipment" and not item_compatible_with_equipment_slot(item, reference.slot):
        raise InventoryRuleError("inventory.incompatible_slot", compatibility_message(item, reference))


def item_weight(item: Oggetto | None) -> float:
    try:
        return max(0.0, float(item.peso or 0)) if item else 0.0
    except (TypeError, ValueError):
        return 0.0


def sort_container_items_by_weight(
    container: Zaino | Faretra,
) -> tuple[dict[int, int], tuple[str, ...]]:
    """Compact a container and order its entries from heaviest to lightest.

    Equal-weight entries keep their current relative order.  The returned slot
    mapping lets callers continue tracking a specific entry even when several
    slots reference the same catalog item.
    """

    entries = [
        (index, item_id)
        for index in range(1, 51)
        if (item_id := getattr(container, f"slot_{index}_id", None)) is not None
    ]
    items = Oggetto.objects.filter(pk__in={item_id for _index, item_id in entries}).only("id", "peso").in_bulk()
    ordered_entries = sorted(entries, key=lambda entry: -item_weight(items.get(entry[1])))
    slot_mapping = {
        source_index: destination_index
        for destination_index, (source_index, _item_id) in enumerate(ordered_entries, start=1)
    }
    ordered_ids = [item_id for _source_index, item_id in ordered_entries]
    changed_fields = []
    for index in range(1, 51):
        field_name = f"slot_{index}"
        desired_id = ordered_ids[index - 1] if index <= len(ordered_ids) else None
        if getattr(container, f"{field_name}_id", None) != desired_id:
            setattr(container, f"{field_name}_id", desired_id)
            changed_fields.append(field_name)
    return slot_mapping, tuple(changed_fields)


def calculate_weight_breakdown(personaggio: Personaggio, totals: dict[str, Any]) -> dict[str, Any]:
    equipment_items = [getattr(personaggio.equip, slot) for slot in EQUIPMENT_SLOT_ORDER] if personaggio.equip else []
    equipment_raw = sum(item_weight(item) for item in equipment_items)
    discount = min(100.0, max(0.0, float(totals.get("mod_peso_equip", 0) or 0)))
    equipment_weight = equipment_raw * (1 - discount / 100)

    capacity = backpack_capacity(totals)
    magical_slots = min(capacity, max(0, int(float(totals.get("slot_magici", 0) or 0))))
    backpack_items = [getattr(personaggio.zaino, f"slot_{index}") for index in range(1, capacity + 1)] if personaggio.zaino else []
    magical_weight_ignored = sum(item_weight(item) for item in backpack_items[:magical_slots])
    backpack_weight = sum(item_weight(item) for item in backpack_items[magical_slots:])

    current_quiver_capacity = quiver_capacity(personaggio.equip)
    quiver_items = [getattr(personaggio.faretra, f"slot_{index}") for index in range(1, current_quiver_capacity + 1)] if personaggio.faretra else []
    quiver_weight = sum(item_weight(item) for item in quiver_items)

    total_weight = equipment_weight + backpack_weight + quiver_weight
    load_step = max(1.0, float(totals.get("mod_carico", 1) or 1))
    penalty = max(0, math.floor(total_weight / load_step))
    return {
        "equipmentRaw": round(equipment_raw, 2),
        "equipment": round(equipment_weight, 2),
        "equipmentDiscountPercent": round(discount, 2),
        "backpack": round(backpack_weight, 2),
        "magicalWeightIgnored": round(magical_weight_ignored, 2),
        "quiver": round(quiver_weight, 2),
        "total": round(total_weight, 2),
        "loadStep": round(load_step, 2),
        "penalty": penalty,
    }


def apply_encumbrance(totals: dict[str, Any], breakdown: dict[str, Any]) -> dict[str, Any]:
    updated = dict(totals)
    penalty = int(breakdown["penalty"])
    updated["malus_carico"] = penalty
    updated["pa"] = max(4, int(float(updated.get("pa", 0) or 0)) - penalty)
    return updated

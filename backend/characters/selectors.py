from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from django.contrib.staticfiles import finders
from django.db.models import Q
from django.templatetags.static import static

from backend.core.models import Effetto, Giocatore, Oggetto

from .models import (
    ContenitoreInventario,
    EffettiPersonaggio,
    Equip,
    Faretra,
    Personaggio,
    Zaino,
)
from .note_selectors import note_sections_payload
from .services.inventory_rules import (
    EQUIPMENT_SLOT_LABELS,
    EQUIPMENT_SLOT_ORDER,
    EXTRA_EQUIPMENT_SLOTS,
    backpack_capacity,
    calculate_weight_breakdown,
    active_weapon_slot,
    equipment_dual_wield,
    equipment_slot_is_active,
    equipment_slot_kind,
    item_compatible_with_equipment_slot,
    item_weapon_profile,
    normalize_item_types,
    quiver_capacity,
)
from .services.refresh_personaggio import collect_calculation_effects
from .services.extended_inventory import (
    PERSONAL_CONTAINER_CAPACITY,
    personal_container,
    personal_storage_usage,
    reagent_stock_for_container,
    reagent_storage_item,
)
from .race_rules import automatic_race_effects


PRIMARY_TOTAL_KEYS = ("pf", "mana", "energia", "potere", "pa", "attacco", "difesa")
CHARACTER_IMAGE_DIRECTORY = "frontend/images/characters"
CHARACTER_IMAGE_PLACEHOLDER = f"{CHARACTER_IMAGE_DIRECTORY}/placeholder.svg"
CHARACTERISTIC_KEYS = (
    "forza",
    "resistenza",
    "velocita",
    "agilita",
    "intelligenza",
    "concentrazione",
    "personalita",
    "saggezza",
    "fortuna",
)
DICE_MODIFIER_KEYS = tuple(f"mod_{key}" for key in CHARACTERISTIC_KEYS)
COMBAT_KEYS = (
    "attacco",
    "difesa",
    "pa",
    "tier",
    "stanchezza",
    "modificatore_generale",
    "atk_skill_taglio",
    "atk_skill_contundente",
    "atk_skill_perforante",
    "atk_skill_corte",
    "atk_skill_medie1",
    "atk_skill_lunghe",
    "atk_skill_precise",
    "atk_skill_medie2",
    "atk_skill_potenti",
    "atk_skill_maninude",
    "tier_skill_maninude",
    "def_skill_leggera",
    "def_skill_pesante",
    "def_skill_noarmatura",
    "def_skill_scudo",
)
RESISTANCE_KEYS = (
    "rd_fis",
    "res_contundente",
    "res_taglio",
    "res_perforante",
    "res_fuoco",
    "res_gelo",
    "res_elettro",
    "rd_fuoco",
    "rd_gelo",
    "rd_elettro",
)
CHARACTER_VALUE_GROUPS = (
    (
        "load_capacity",
        "Carico e capacità",
        (
            "malus_carico",
            "mod_carico",
            "mod_peso_equip",
            "slot_magici",
            "slot_non_magici",
            "monete_per_slot",
            "orecchini_max",
            "anelli_max",
            "sacchi_max",
        ),
    ),
    (
        "magic_conversions",
        "Magia e conversioni",
        (
            "sifone_di_mana",
            "en_per_mana",
            "pa_per_mana",
            "ogni_en_x_mana",
            "ogni_pa_x_mana",
            "sconto_mana_per_potere",
            "sconto_pa_per_potere",
        ),
    ),
    (
        "alchemy_multipliers",
        "Moltiplicatori alchimia",
        (
            "moltiplicatore_reagenti_rossi",
            "moltiplicatore_reagenti_verdi",
            "moltiplicatore_reagenti_blu",
            "moltiplicatore_reagenti_livello_1",
            "moltiplicatore_reagenti_livello_2",
            "moltiplicatore_reagenti_livello_3",
            "moltiplicatore_reagenti_livello_4",
        ),
    ),
    ("roll_modifiers", "Modificatori ai tiri", DICE_MODIFIER_KEYS),
    ("advanced_combat", "Combattimento avanzato", ("ap", "ap_percento")),
)

TOTAL_LABELS = {
    "pf": "Punti ferita",
    "mana": "Mana",
    "energia": "Energia",
    "potere": "Potere",
    "pa": "Punti azione",
    "attacco": "Attacco",
    "difesa": "Difesa",
    "tier": "Tier",
    "stanchezza": "Stanchezza",
    "modificatore_generale": "Modificatore generale",
    "forza": "Forza",
    "resistenza": "Resistenza",
    "velocita": "Velocità",
    "agilita": "Agilità",
    "intelligenza": "Intelligenza",
    "concentrazione": "Concentrazione",
    "personalita": "Personalità",
    "saggezza": "Saggezza",
    "fortuna": "Fortuna",
    "rd_fis": "Riduzione fisica",
    "res_contundente": "Resistenza contundente",
    "res_taglio": "Resistenza al taglio",
    "res_perforante": "Resistenza perforante",
    "res_fuoco": "Resistenza al fuoco",
    "res_gelo": "Resistenza al gelo",
    "res_elettro": "Resistenza elettrica",
    "rd_fuoco": "Riduzione fuoco",
    "rd_gelo": "Riduzione gelo",
    "rd_elettro": "Riduzione elettrica",
    "atk_skill_taglio": "Attacco taglio",
    "atk_skill_contundente": "Attacco contundente",
    "atk_skill_perforante": "Attacco perforante",
    "atk_skill_corte": "Attacco armi corte",
    "atk_skill_medie1": "Attacco armi medie",
    "atk_skill_lunghe": "Attacco armi lunghe",
    "atk_skill_precise": "Attacco armi precise",
    "atk_skill_medie2": "Attacco armi bilanciate",
    "atk_skill_potenti": "Attacco armi potenti",
    "atk_skill_maninude": "Attacco a mani nude",
    "tier_skill_maninude": "Tier mani nude",
    "def_skill_leggera": "Difesa armatura leggera",
    "def_skill_pesante": "Difesa armatura pesante",
    "def_skill_noarmatura": "Difesa senza armatura",
    "def_skill_scudo": "Difesa con scudo",
    "malus_carico": "Malus carico",
    "mod_carico": "Passo carico",
    "mod_peso_equip": "Sconto peso equipaggiamento (%)",
    "slot_magici": "Spazi magici",
    "slot_non_magici": "Spazi normali",
    "monete_per_slot": "Monete per spazio",
    "orecchini_max": "Orecchini massimi",
    "anelli_max": "Anelli massimi",
    "sacchi_max": "Sacchi massimi",
    "moltiplicatore_reagenti_rossi": "Moltiplicatore reagenti rossi",
    "moltiplicatore_reagenti_verdi": "Moltiplicatore reagenti verdi",
    "moltiplicatore_reagenti_blu": "Moltiplicatore reagenti blu",
    "moltiplicatore_reagenti_livello_1": "Effetto reagenti livello 1",
    "moltiplicatore_reagenti_livello_2": "Effetto reagenti livello 2",
    "moltiplicatore_reagenti_livello_3": "Effetto reagenti livello 3",
    "moltiplicatore_reagenti_livello_4": "Effetto reagenti livello 4",
    "sifone_di_mana": "Sifone di mana",
    "en_per_mana": "Energia per mana",
    "pa_per_mana": "PA per mana",
    "ogni_en_x_mana": "Mana ogni N energia",
    "ogni_pa_x_mana": "Mana ogni N PA",
    "sconto_mana_per_potere": "Sconto mana per potere",
    "sconto_pa_per_potere": "Sconto PA per potere",
    "ap": "Perforazione armatura",
    "ap_percento": "Perforazione armatura (%)",
}

REAGENT_COLOR_LABELS = {"r": "Rosso", "v": "Verde", "b": "Blu"}

CALCULATION_SOURCE_LABELS = (
    ("base", "Base"),
    ("items", "Oggetti"),
    ("effects", "Effetti"),
)


def ordered_personaggi_for(
    giocatore: Giocatore,
    *,
    include_all: bool = False,
) -> list[Personaggio]:
    raw_ids = giocatore.character_ids if isinstance(giocatore.character_ids, list) else []
    character_ids = []
    for raw_id in raw_ids:
        try:
            character_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    queryset = (
        Personaggio.objects.filter(archived_at__isnull=True)
        .filter(
            Q(metadata__seed_kind__isnull=True)
            | ~Q(metadata__seed_kind="empty_personaggio_template")
        )
        .select_related("campagna", "portrait", "equip", "zaino", "faretra", "note", "effetti")
        .prefetch_related(
            "effetti_personalizzati__operazioni",
            "skill_sbloccate__skill__famiglia",
            "skill_sbloccate__skill__prerequisiti",
        )
    )
    if giocatore.active_campaign_id:
        queryset = queryset.filter(campagna_id=giocatore.active_campaign_id)
    if character_ids:
        assigned = list(queryset.filter(id__in=character_ids))
        by_id = {personaggio.id: personaggio for personaggio in assigned}
        ordered_assigned = [by_id[personaggio_id] for personaggio_id in character_ids if personaggio_id in by_id]
        if not include_all:
            return ordered_assigned

        assigned_ids = set(by_id)
        other_characters = list(queryset.exclude(id__in=assigned_ids).order_by("nome", "id"))
        return [*ordered_assigned, *other_characters]

    if include_all:
        return list(queryset.order_by("nome", "id"))
    return list(queryset.filter(metadata__seed_kind="poc_personaggio").order_by("nome"))


def _related_item_ids(personaggio: Personaggio) -> set[int]:
    ids: set[int] = set()
    if personaggio.equip:
        ids.update(
            item_id
            for slot in EQUIPMENT_SLOT_ORDER
            if (item_id := getattr(personaggio.equip, f"{slot}_id", None))
        )
    for container in (personaggio.zaino, personaggio.faretra):
        if container:
            ids.update(
                item_id
                for index in range(1, 51)
                if (item_id := getattr(container, f"slot_{index}_id", None))
            )
    return ids


def _items_for(personaggio: Personaggio) -> dict[int, Oggetto]:
    return Oggetto.objects.filter(id__in=_related_item_ids(personaggio)).select_related("tipo_arma", "media").in_bulk()


def serialize_item(item: Oggetto | None, *, detailed: bool = False) -> dict | None:
    if item is None:
        return None
    weapon_profile = item_weapon_profile(item)
    type_values = [item.tipo_1, item.tipo_2, item.tipo_3, item.tipo_4]
    types = [value for value in type_values if value]
    payload = {
        "id": item.id,
        "name": item.nome,
        "icon": item.icona,
        "types": types,
        "typeValues": type_values,
        "description": item.descrizione,
        "value": item.valore,
        "weight": item.peso,
        "rarity": item.rarita,
        "rarityLabel": item.get_rarita_display() if item.rarita is not None else "",
        "lootLevel": item.lv_loot,
        "region": item.regione_loot,
        "effects": item.effects or [],
        "weaponTypeId": item.tipo_arma_id,
        "weaponType": item.tipo_arma.nome if item.tipo_arma_id and item.tipo_arma else "",
        "weaponLength": str(
            weapon_profile.get("length")
            or (item.tipo_arma.lunghezza if item.tipo_arma_id and item.tipo_arma else "")
        ),
        "weaponPower": str(
            weapon_profile.get("power")
            or (item.tipo_arma.potenza if item.tipo_arma_id and item.tipo_arma else "")
        ),
        "weaponTypeBonuses": [
            bonus
            for bonus in (
                item.tipo_arma.bonus_1 if item.tipo_arma_id and item.tipo_arma else "",
                item.tipo_arma.bonus_2 if item.tipo_arma_id and item.tipo_arma else "",
            )
            if bonus and bonus.casefold() not in {"vuoto", "empty"}
        ],
        "weaponRules": item.tipo_arma.rules if item.tipo_arma_id and item.tipo_arma else {},
        "weaponProfile": weapon_profile,
        "actionPointCost": item.pa_per_attacco,
        "imageUrl": item.media.file.url if item.media_id and item.media and item.media.file else "",
        "archived": item.archiviato,
        "special": item.speciale,
        "isProjectile": bool(
            normalize_item_types(item)
            & {"freccia", "frecce", "dardo", "dardi", "proiettile", "proiettili", "munizione", "munizioni"}
        ),
        "compatibleEquipmentSlots": [
            slot for slot in EQUIPMENT_SLOT_ORDER if item_compatible_with_equipment_slot(item, slot)
        ],
    }
    if detailed:
        payload.update(
            {
                "model": item.modello,
                "temporary": item.temporaneo,
                "order": item.numero_ordine,
                "regionWeight": item.peso_regione,
                "alchemyProfile": item.alchemy_profile or {},
                "craftingProfile": item.crafting_profile or {},
                "mediaId": item.media_id,
                "notes": item.notes,
                "elderEffects": item.effetti_elder,
                "metadata": item.metadata if isinstance(item.metadata, dict) else {},
            }
        )
    return payload


def _numeric_reagent_value(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _reagent_label(key: Any, *, multiplier: bool = False) -> str:
    raw = str(key or "").strip()
    normalized = raw.lower().replace(" ", "_")
    color_level = re.fullmatch(r"(?:ingredienti?_)?(rossi?|verdi?|blu)_?(?:livello_?)?([1-4])", normalized)
    if color_level:
        color = "Rosso" if color_level.group(1).startswith("ross") else "Verde" if color_level.group(1).startswith("verd") else "Blu"
        return f"{color} · livello {color_level.group(2)}"
    short_color_level = re.fullmatch(r"([rvb])([1-4])", normalized)
    if short_color_level:
        return f"{REAGENT_COLOR_LABELS[short_color_level.group(1)]} · livello {short_color_level.group(2)}"
    level_multiplier = re.fullmatch(r"(?:m|moltiplicatore_?(?:livello_?)?)([1-4])", normalized)
    if multiplier and level_multiplier:
        return f"Moltiplicatore livello {level_multiplier.group(1)}"
    color_multiplier = re.fullmatch(r"(?:m|moltiplicatore_?)([rvb])", normalized)
    if multiplier and color_multiplier:
        return f"Moltiplicatore {REAGENT_COLOR_LABELS[color_multiplier.group(1)].lower()}"
    return raw.replace("_", " ").strip() or "Senza nome"


def _reagent_bag_payload(
    personaggio: Personaggio,
    totals: dict[str, Any],
) -> dict[str, Any]:
    ingredients = {
        key: value
        for key, value in reagent_stock_for_container(personal_container(personaggio)).items()
        if value > 0
    }
    multiplier_keys = (
        "moltiplicatore_reagenti_rossi",
        "moltiplicatore_reagenti_verdi",
        "moltiplicatore_reagenti_blu",
        "moltiplicatore_reagenti_livello_1",
        "moltiplicatore_reagenti_livello_2",
        "moltiplicatore_reagenti_livello_3",
        "moltiplicatore_reagenti_livello_4",
    )
    multipliers = {key: _numeric_reagent_value(totals.get(key, 0)) for key in multiplier_keys}
    ingredient_rows = [
        {"key": str(key), "label": _reagent_label(key), "value": _numeric_reagent_value(value)}
        for key, value in ingredients.items()
    ]
    multiplier_rows = [
        {"key": str(key), "label": TOTAL_LABELS[key], "value": _numeric_reagent_value(value)}
        for key, value in multipliers.items()
    ]
    ingredient_rows.sort(key=lambda row: row["label"])
    multiplier_rows.sort(key=lambda row: row["label"])
    slot_max, occupied = personal_storage_usage(personaggio)
    return {
        "slotMax": slot_max,
        "occupied": occupied,
        "remaining": max(0.0, slot_max - occupied),
        "ingredients": ingredients,
        "multipliers": multipliers,
        "ingredientRows": ingredient_rows,
        "multiplierRows": multiplier_rows,
    }


def _slot_payload(group: str, index: int, capacity: int, item: Oggetto | None, *, magical: bool = False) -> dict:
    return {
        "id": f"{group}:{index}",
        "group": group,
        "slot": str(index),
        "label": f"Spazio {index}",
        "slotType": "projectile" if group == "quiver" else "storage",
        "accepts": ["projectile"] if group == "quiver" else ["any"],
        "isExtraSlot": False,
        "isLocked": index > capacity,
        "isMagical": magical,
        "quantity": 1,
        "stackable": False,
        "weightless": False,
        "item": serialize_item(item),
    }


def _container_payload(
    personaggio: Personaggio,
    group: str,
    container: Zaino | Faretra | None,
    items: dict[int, Oggetto],
) -> dict:
    totals = personaggio.tot if isinstance(personaggio.tot, dict) else {}
    capacity = backpack_capacity(totals) if group == "backpack" else quiver_capacity(personaggio.equip)
    magical_slots = min(capacity, max(0, int(float(totals.get("slot_magici", 0) or 0)))) if group == "backpack" else 0
    slots = []
    for index in range(1, 51):
        item_id = getattr(container, f"slot_{index}_id", None) if container else None
        slots.append(_slot_payload(group, index, capacity, items.get(item_id), magical=index <= magical_slots))
    occupied = sum(1 for slot in slots[:capacity] if slot["item"] is not None)
    return {
        "kind": group,
        "label": "Zaino" if group == "backpack" else "Faretra",
        "capacity": capacity,
        "occupied": occupied,
        "magicalSlots": magical_slots,
        "weightless": False,
        "shared": False,
        "available": True,
        "slots": slots,
    }


def _extended_container_payload(personaggio: Personaggio, group: str) -> dict[str, Any]:
    is_personal = group == "utility"
    if not is_personal and not personaggio.campagna_id:
        return {
            "kind": group,
            "label": "Risorse gruppo",
            "capacity": 0,
            "occupied": 0,
            "magicalSlots": 0,
            "weightless": True,
            "shared": True,
            "available": False,
            "slots": [],
        }
    filters = (
        {
            "scope": ContenitoreInventario.SCOPE_PERSONAL,
            "personaggio": personaggio,
        }
        if is_personal
        else {
            "scope": ContenitoreInventario.SCOPE_CAMPAIGN,
            "campagna_id": personaggio.campagna_id,
        }
    )
    container = (
        ContenitoreInventario.objects.filter(**filters)
        .prefetch_related("voci__oggetto__tipo_arma", "voci__oggetto__media")
        .first()
    )
    capacity = container.capacita if container else PERSONAL_CONTAINER_CAPACITY if is_personal else 30
    entries = {entry.slot: entry for entry in container.voci.all()} if container else {}
    fallback_rows = []
    slots = []
    for index in range(1, capacity + 1):
        entry = entries.get(index)
        fallback = fallback_rows[index - 1] if not entry and index <= len(fallback_rows) else None
        stock_key = entry.reagent_stock_key if entry else fallback[0] if fallback else ""
        quantity = entry.quantita if entry else fallback[1] if fallback else 1
        item_payload = (
            reagent_storage_item(stock_key)
            if stock_key
            else serialize_item(entry.oggetto) if entry and entry.oggetto_id else None
        )
        slots.append(
            {
                "id": f"{group}:{index}",
                "group": group,
                "slot": str(index),
                "label": f"Spazio {index}",
                "slotType": "storage",
                "accepts": ["any", "reagent"],
                "isExtraSlot": False,
                "isLocked": False,
                "isMagical": False,
                "quantity": quantity,
                "stackable": True,
                "weightless": True,
                "item": item_payload,
            }
        )
    return {
        "kind": group,
        "label": "Alchimia&Contenitori" if is_personal else "Risorse gruppo",
        "capacity": capacity,
        "occupied": sum(1 for slot in slots if slot["item"] is not None),
        "magicalSlots": 0,
        "weightless": True,
        "shared": not is_personal,
        "available": True,
        "slots": slots,
    }


def _equipment_payload(equip: Equip | None, items: dict[int, Oggetto], totals: dict[str, Any]) -> dict:
    slots = []
    for slot in EQUIPMENT_SLOT_ORDER:
        item_id = getattr(equip, f"{slot}_id", None) if equip else None
        item = items.get(item_id)
        kind = equipment_slot_kind(slot)
        accepts = ["any"] if slot in EXTRA_EQUIPMENT_SLOTS else (
            ["weapon"] if slot == "arma" else ["shield", "one_handed_weapon"] if slot == "scudo" else [kind]
        )
        slots.append(
            {
                "id": f"equipment:{slot}",
                "group": "equipment",
                "slot": slot,
                "label": EQUIPMENT_SLOT_LABELS[slot],
                "slotType": kind,
                "accepts": accepts,
                "isExtraSlot": slot in EXTRA_EQUIPMENT_SLOTS,
                "isLocked": not equipment_slot_is_active(slot, totals),
                "isMagical": False,
                "item": serialize_item(item),
            }
        )
    dual_wield = equipment_dual_wield(equip)
    primary_slot = active_weapon_slot(equip)
    primary_item = getattr(equip, primary_slot, None) if equip else None
    inactive_slot = "scudo" if primary_slot == "arma" else "arma"
    inactive_item = getattr(equip, inactive_slot, None) if dual_wield and equip else None
    return {
        "kind": "equipment",
        "label": "Equipaggiamento",
        "slots": slots,
        "dualWield": dual_wield,
        "primaryWeaponSlot": primary_slot,
        "primaryWeaponId": primary_item.id if primary_item else None,
        "inactiveWeaponId": inactive_item.id if inactive_item else None,
        "weaponState": (
            equip.metadata.get("weaponState", {})
            if equip and isinstance(equip.metadata, dict) and isinstance(equip.metadata.get("weaponState"), dict)
            else {}
        ),
    }


def _appearance_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "")).lower()
    without_marks = "".join(character for character in normalized if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9_-]+", "_", without_marks).strip("_-")[:80]


def _meaningful_appearance_value(value: Any) -> bool:
    return str(value or "").strip().lower() not in {"", "assente", "empty", "false", "none", "null", "vuoto"}


def _equipped_item(equip: Equip | None, items: dict[int, Oggetto], slot: str) -> Oggetto | None:
    item_id = getattr(equip, f"{slot}_id", None) if equip else None
    return items.get(item_id)


def _armor_appearance_key(equip: Equip | None, items: dict[int, Oggetto]) -> str:
    robe = _equipped_item(equip, items, "veste")
    # A robe's rank is encoded in its name in the legacy catalog.  Its
    # secondary type is commonly blank (for example, "Veste qualificato"),
    # so it must not decide whether the robe supplies the visual variant.
    if robe:
        metadata = robe.metadata if isinstance(robe.metadata, dict) else {}
        if override := _appearance_key(metadata.get("appearanceArmorKey")):
            return override
        robe_name = _appearance_key(robe.nome)
        robe_ranks = (
            ("gran_maestro", "veste-gm"),
            ("maestro", "veste-m"),
            ("esperto", "veste-e"),
            ("qualificato", "veste-q"),
            ("apprendista", "veste-a"),
            ("principiante", "veste-p"),
        )
        return next((key for label, key in robe_ranks if label in robe_name), "veste")

    armor = _equipped_item(equip, items, "armatura")
    if not armor:
        return ""
    metadata = armor.metadata if isinstance(armor.metadata, dict) else {}
    raw_key = metadata.get("appearanceArmorKey") or armor.tipo_2
    return _appearance_key(raw_key) if _meaningful_appearance_value(raw_key) else ""


def _character_appearance(personaggio: Personaggio, items: dict[int, Oggetto]) -> dict:
    metadata = personaggio.metadata if isinstance(personaggio.metadata, dict) else {}
    first_name = (personaggio.nome or "").strip().split(maxsplit=1)[0] if personaggio.nome else ""
    character_key = _appearance_key(metadata.get("appearanceKey") or first_name)
    armor_key = _armor_appearance_key(personaggio.equip, items)
    filenames = []
    if character_key and armor_key:
        filenames.extend((f"{character_key}_{armor_key}.webp", f"{character_key}_{armor_key}.png"))
    if character_key:
        filenames.extend((f"{character_key}_base.webp", f"{character_key}_base.png"))

    candidates = [f"{CHARACTER_IMAGE_DIRECTORY}/match/{filename}" for filename in filenames]
    selected = next((path for path in candidates if finders.find(path)), CHARACTER_IMAGE_PLACEHOLDER)
    selected_url = static(selected)
    portrait_url = (
        personaggio.portrait.file.url
        if personaggio.portrait_id and personaggio.portrait and personaggio.portrait.file
        else ""
    )
    preferred_filename = filenames[0] if filenames else ""
    return {
        "characterKey": character_key,
        "armorKey": armor_key,
        "imageUrl": selected_url,
        "portraitUrl": portrait_url,
        "fallbackUrl": static(CHARACTER_IMAGE_PLACEHOLDER),
        "fallbackIsPlaceholder": selected == CHARACTER_IMAGE_PLACEHOLDER,
        "preferredFilename": preferred_filename,
        "isPlaceholder": selected == CHARACTER_IMAGE_PLACEHOLDER,
    }


def _effect_expression(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value if value is not None else "")


def _effect_operations(payload: Any) -> list[dict]:
    collected = collect_calculation_effects([payload] if payload else [])
    rows = [
        {
            "target": operation.target,
            "operation": operation.operation,
            "value": _effect_expression(operation.value),
            "condition": _effect_expression(operation.condition) if operation.condition else "",
            "order": operation.order,
        }
        for operation in collected.operations
    ]
    rows.extend(
        {
            "target": override.target,
            "operation": "formula_override",
            "value": override.formula,
            "condition": "",
            "order": override.order,
        }
        for override in collected.formula_overrides
    )
    return [
        {key: value for key, value in row.items() if key != "order"}
        for row in sorted(rows, key=lambda row: row["order"])
    ]


def _temporary_marker(description: str) -> bool:
    return bool(re.search(r"(?:^|\s)\(t\)(?:\s|$)", description or "", re.IGNORECASE))


def _effects(personaggio: Personaggio) -> list[dict]:
    effetti = personaggio.effetti
    effect_ids = {
        effect_id
        for index in range(1, 51)
        if effetti is not None and (effect_id := getattr(effetti, f"effetto_{index}_id", None))
    }
    effects = Effetto.objects.filter(id__in=effect_ids).in_bulk()
    entries = []
    for index in range(1, 51):
        effect_id = getattr(effetti, f"effetto_{index}_id", None) if effetti is not None else None
        effect = effects.get(effect_id)
        if effect is None:
            continue
        entries.append(
            {
                "scope": "legacy",
                "editable": True,
                "slot": index,
                "id": effect.id,
                "name": effect.nome,
                "type": effect.tipo,
                "description": effect.descrizione,
                "payload": effect.effect_payload or {},
                "durationTurns": effect.durata_turni,
                "stackingRule": effect.stacking_rule,
                "icon": effect.icona,
                "originType": effect.origine_tipo,
                "originName": effect.origine_nome,
                "temporary": _temporary_marker(effect.descrizione),
                "operations": _effect_operations(effect.effect_payload),
                "order": index,
            }
        )

    custom_effects = personaggio.effetti_personalizzati.all()
    for custom_effect in custom_effects:
        operations = [
            {
                "target": operation.bersaglio,
                "operation": operation.operazione,
                "value": operation.valore,
                "condition": operation.condizione,
            }
            for operation in custom_effect.operazioni.all()
        ]
        payload_operations = [
            {
                "target": operation["target"],
                "operation": operation["operation"],
                "value": operation["value"],
                **({"condition": operation["condition"]} if operation["condition"] else {}),
            }
            for operation in operations
        ]
        entries.append(
            {
                "scope": "custom",
                "editable": True,
                "slot": None,
                "id": custom_effect.id,
                "name": custom_effect.nome,
                "type": "",
                "description": custom_effect.descrizione,
                "payload": {"effects": payload_operations},
                "durationTurns": None,
                "stackingRule": "",
                "icon": custom_effect.icona,
                "originType": "manuale",
                "originName": custom_effect.origine,
                "temporary": custom_effect.temporaneo,
                "operations": operations,
                "order": 50 + custom_effect.ordine,
            }
        )
    has_imported_racial_abilities = any(
        isinstance(ownership.metadata, dict) and ownership.metadata.get("source") == "race.auto"
        for ownership in personaggio.skill_sbloccate.all()
    )
    automatic_effects = (
        [] if has_imported_racial_abilities
        else automatic_race_effects(personaggio.razza_1, personaggio.razza_2)
    )
    for automatic_index, automatic_effect in enumerate(automatic_effects, start=1):
        entries.append(
            {
                "scope": "automatic",
                "editable": False,
                "slot": None,
                "id": -automatic_index,
                "name": automatic_effect["name"],
                "type": "Razziale automatico",
                "description": automatic_effect["description"],
                "payload": automatic_effect["payload"],
                "durationTurns": None,
                "stackingRule": "replace",
                "icon": automatic_effect["icon"],
                "originType": automatic_effect["originType"],
                "originName": automatic_effect["originName"],
                "temporary": False,
                "operations": automatic_effect["operations"],
                "order": -100 + automatic_index,
            }
        )
    return sorted(entries, key=lambda entry: entry["order"])


def effect_catalog_payload() -> list[dict]:
    return [
        {
            "id": effect.id,
            "name": effect.nome,
            "type": effect.tipo,
            "description": effect.descrizione,
            "payload": effect.effect_payload or {},
            "durationTurns": effect.durata_turni,
            "stackingRule": effect.stacking_rule,
            "icon": effect.icona,
            "originType": effect.origine_tipo,
            "originName": effect.origine_nome,
        }
        for effect in Effetto.objects.filter(archived_at__isnull=True).order_by("tipo", "nome")
    ]


def _abilities(personaggio: Personaggio) -> list[dict]:
    abilities = personaggio.abilita if isinstance(personaggio.abilita, dict) else {}
    return [ability for ability in abilities.get("known", []) if isinstance(ability, dict)]


def _skills(personaggio: Personaggio) -> list[dict]:
    from backend.core.skill_selectors import character_skill_summaries

    normalized = character_skill_summaries(personaggio)
    if normalized:
        return normalized
    abilities = personaggio.abilita if isinstance(personaggio.abilita, dict) else {}
    return [skill for skill in abilities.get("skills", []) if isinstance(skill, dict)]


def _display_number(value: Any) -> int | float:
    try:
        number = round(float(value or 0), 6)
    except (TypeError, ValueError):
        return 0
    return int(number) if number.is_integer() else number


def _calculation_parts(personaggio: Personaggio, key: str) -> list[dict]:
    totals = personaggio.tot if isinstance(personaggio.tot, dict) else {}
    report = personaggio.effetti_finali if isinstance(personaggio.effetti_finali, dict) else {}
    stored_sources = report.get("calculation_sources") or {}
    stored = stored_sources.get(key) if isinstance(stored_sources, dict) else None
    if isinstance(stored, dict):
        values = {source_key: _display_number(stored.get(source_key, 0)) for source_key, _label in CALCULATION_SOURCE_LABELS}
    else:
        item_delta = 0.0
        effect_delta = 0.0
        applied_operations = report.get("applied_operations") or {}
        operations = applied_operations.get(key, []) if isinstance(applied_operations, dict) else []
        for operation in operations if isinstance(operations, list) else []:
            if not isinstance(operation, dict):
                continue
            if operation.get("operation") == "strong_set":
                continue
            delta = float(operation.get("after", 0) or 0) - float(operation.get("before", 0) or 0)
            source = str(operation.get("source") or "")
            if source.startswith("equip."):
                item_delta += delta
            elif source.startswith("effetti."):
                effect_delta += delta
        total = float(totals.get(key, 0) or 0)
        values = {
            "base": _display_number(total - item_delta - effect_delta),
            "items": _display_number(item_delta),
            "effects": _display_number(effect_delta),
        }
    parts = [
        {"key": source_key, "label": label, "value": values[source_key]}
        for source_key, label in CALCULATION_SOURCE_LABELS
    ]
    quick_report = report.get("quick_stat_adjustment") or {}
    quick_applied = quick_report.get("applied") or {} if isinstance(quick_report, dict) else {}
    stat_adjustment = quick_applied.get(key) if isinstance(quick_applied, dict) else None
    if isinstance(stat_adjustment, dict):
        fatigue_value = _display_number(quick_report.get("fatigue_value", 0))
        fatigue_rate = _display_number(quick_report.get("fatigue_percent_per_point", 0))
        fatigue_fixed_rate = _display_number(
            quick_report.get("fatigue_fixed_per_point", 0)
        )
        general_value = _display_number(quick_report.get("general_modifier_value", 0))
        general_rate = _display_number(quick_report.get("general_modifier_percent_per_point", 0))
        general_fixed_rate = _display_number(
            quick_report.get("general_modifier_fixed_per_point", 0)
        )
        parts.extend(
            (
                {
                    "key": "stanchezza",
                    "label": (
                        f"Stanchezza ({fatigue_value} × −{fatigue_rate}% "
                        f"e −{fatigue_fixed_rate} fisso)"
                    ),
                    "value": _display_number(
                        float(stat_adjustment.get("fatigue", 0) or 0)
                        + float(stat_adjustment.get("fatigue_fixed", 0) or 0)
                    ),
                },
                {
                    "key": "modificatore_generale",
                    "label": (
                        f"Modificatore generale ({general_value} × +{general_rate}% "
                        f"e +{general_fixed_rate} fisso)"
                    ),
                    "value": _display_number(
                        float(stat_adjustment.get("general_modifier", 0) or 0)
                        + float(
                            stat_adjustment.get("general_modifier_fixed", 0) or 0
                        )
                    ),
                },
            )
        )
    strong_report = report.get("strong_set_adjustment") or {}
    strong_applied = strong_report.get("applied") or {} if isinstance(strong_report, dict) else {}
    strong_operations = strong_applied.get(key) if isinstance(strong_applied, dict) else None
    if isinstance(strong_operations, list) and strong_operations:
        strong_delta = sum(
            float(operation.get("after", 0) or 0) - float(operation.get("before", 0) or 0)
            for operation in strong_operations
            if isinstance(operation, dict)
        )
        parts.append(
            {
                "key": "imposta_forte",
                "label": "Imposta forte (valore finale bloccato)",
                "value": _display_number(strong_delta),
            }
        )
    action_point_minimum = report.get("action_point_minimum") or {}
    if key == "pa" and isinstance(action_point_minimum, dict) and action_point_minimum.get("applied"):
        before_minimum = float(action_point_minimum.get("before", 0) or 0)
        after_minimum = float(action_point_minimum.get("after", 4) or 4)
        parts.append(
            {
                "key": "pa_minimum",
                "label": "Limite minimo PA (4)",
                "value": _display_number(after_minimum - before_minimum),
            }
        )
    displayed_total = _display_number(totals.get(key, 0))
    rounding = _display_number(displayed_total - sum(float(part["value"]) for part in parts))
    if rounding:
        parts.append(
            {
                "key": "final_rounding",
                "label": "Limite e arrotondamento finale",
                "value": rounding,
            }
        )
    return parts


def _total_values(personaggio: Personaggio, keys: tuple[str, ...]) -> list[dict]:
    totals = personaggio.tot if isinstance(personaggio.tot, dict) else {}
    return [
        {
            "key": key,
            "label": TOTAL_LABELS.get(key, key.replace("_", " ").capitalize()),
            "value": totals.get(key, 0),
            "calculation": _calculation_parts(personaggio, key),
        }
        for key in keys
    ]


def _dice_modifier_values(personaggio: Personaggio) -> list[dict]:
    totals = personaggio.tot if isinstance(personaggio.tot, dict) else {}
    return [
        {
            "key": key,
            "label": TOTAL_LABELS.get(key.removeprefix("mod_"), key.replace("mod_", "").replace("_", " ").capitalize()),
            "value": int(float(totals.get(key, 0) or 0)),
            "calculation": _calculation_parts(personaggio, key),
        }
        for key in DICE_MODIFIER_KEYS
    ]


def _character_value_groups(personaggio: Personaggio) -> list[dict]:
    return [
        {
            "key": key,
            "label": label,
            "values": _total_values(personaggio, value_keys),
        }
        for key, label, value_keys in CHARACTER_VALUE_GROUPS
    ]


def _resources(personaggio: Personaggio) -> list[dict]:
    totals = personaggio.tot if isinstance(personaggio.tot, dict) else {}
    spent = {
        "pf": personaggio.danno,
        "mana": personaggio.mana_speso,
        "energia": personaggio.energia_spesa,
        "potere": personaggio.potere_speso,
    }
    resources = []
    for key in ("pf", "mana", "energia", "potere"):
        maximum = max(0, int(float(totals.get(key, 0) or 0)))
        current = maximum - int(spent[key] or 0)
        resources.append(
            {
                "key": key,
                "label": TOTAL_LABELS[key],
                "current": current,
                "maximum": maximum,
                "spent": int(spent[key] or 0),
                "percent": round((current / maximum) * 100, 1) if maximum else 0,
                "colorToken": f"--resource-{key}",
                "calculation": _calculation_parts(personaggio, key),
            }
        )
    return resources


def personaggio_summary(personaggio: Personaggio, active_character_id: int | None) -> dict:
    return {
        "id": personaggio.id,
        "name": personaggio.nome,
        "internalName": personaggio.nome_interno,
        "type": personaggio.tipologia,
        "campaignId": personaggio.campagna_id,
        "races": [race for race in (personaggio.razza_1, personaggio.razza_2, personaggio.razza_3) if race],
        "race1": personaggio.razza_1,
        "race2": personaggio.razza_2,
        "race3": personaggio.razza_3,
        "level": personaggio.livello,
        "coins": personaggio.monete,
        "details": personaggio.dettagli_personaggio,
        "isActive": personaggio.id == active_character_id,
        "primaryTotals": _total_values(personaggio, PRIMARY_TOTAL_KEYS),
    }


def personaggio_detail(
    personaggio: Personaggio | None,
    *,
    can_manage_items: bool = False,
    include_skills: bool = True,
) -> dict | None:
    if personaggio is None:
        return None
    items = _items_for(personaggio)
    totals = personaggio.tot if isinstance(personaggio.tot, dict) else {}
    weight = (personaggio.effetti_finali or {}).get("inventory_weight") or calculate_weight_breakdown(personaggio, totals)
    return {
        **personaggio_summary(personaggio, personaggio.id),
        "age": personaggio.eta,
        "sex": personaggio.sesso,
        "criticalThresholds": {
            "minor": personaggio.crit_min,
            "normal": personaggio.crit_nor,
            "major": personaggio.crit_mag,
        },
        "resources": _resources(personaggio),
        "xp": {
            "general": personaggio.pe_generali,
            "red": personaggio.pe_rossi,
            "green": personaggio.pe_verdi,
            "blue": personaggio.pe_blu,
            "ability": personaggio.pe_abilita,
        },
        "characteristics": _total_values(personaggio, CHARACTERISTIC_KEYS),
        "diceModifiers": _dice_modifier_values(personaggio),
        "combat": _total_values(personaggio, COMBAT_KEYS),
        "resistances": _total_values(personaggio, RESISTANCE_KEYS),
        "valueGroups": _character_value_groups(personaggio),
        "appearance": _character_appearance(personaggio, items),
        "equipment": _equipment_payload(personaggio.equip, items, totals),
        "inventory": _container_payload(personaggio, "backpack", personaggio.zaino, items),
        "quiver": _container_payload(personaggio, "quiver", personaggio.faretra, items),
        "utilityContainer": _extended_container_payload(personaggio, "utility"),
        "campaignContainer": _extended_container_payload(personaggio, "campaign"),
        "effects": _effects(personaggio),
        # Skill cards, pricing and prerequisite analysis belong to /skills.
        # The character sheet does not render them, and calculating them here
        # creates hundreds of queries for high-skill characters.
        "skills": _skills(personaggio) if include_skills else [],
        "abilities": _abilities(personaggio),
        "competencies": personaggio.competenze or {},
        "notes": note_sections_payload(personaggio.note),
        "reagents": _reagent_bag_payload(personaggio, totals),
        "modifiedStats": (personaggio.effetti_finali or {}).get("modified_stats", {}),
        "encumbrance": weight,
        "permissions": {
            "canManageItems": can_manage_items,
            "canShowLockedSlots": not can_manage_items,
        },
    }


def personaggi_payload_for(
    giocatore: Giocatore,
    *,
    can_manage_items: bool = False,
    include_all: bool = False,
) -> dict:
    personaggi = ordered_personaggi_for(giocatore, include_all=include_all)
    active = next((item for item in personaggi if item.id == giocatore.active_character_id), None)
    if active is None and personaggi:
        active = personaggi[0]
    active_id = active.id if active else None
    return {
        "giocatore": {
            "id": giocatore.id,
            "name": giocatore.nome,
            "displayName": giocatore.display_name or giocatore.nome,
            "role": giocatore.role,
            "activePersonaggioId": active_id,
        },
        "personaggi": [personaggio_summary(personaggio, active_id) for personaggio in personaggi],
        "activePersonaggio": personaggio_detail(
            active,
            can_manage_items=can_manage_items,
            include_skills=False,
        ),
    }

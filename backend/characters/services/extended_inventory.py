from __future__ import annotations

import re
from typing import Any

from django.db import transaction

from backend.core.api import ApiError
from backend.core.models import Oggetto

from ..models import (
    ContenitoreInventario,
    Personaggio,
    VoceContenitoreInventario,
)
from .alchemy import normalize_stock_key


EXTENDED_INVENTORY_GROUPS = {"utility", "campaign"}
PERSONAL_CONTAINER_CAPACITY = 15
CAMPAIGN_CONTAINER_CAPACITY = 30
STOCK_KEY_PATTERN = re.compile(r"^[rvb][1-4]$")
STOCK_COLORS = {
    "r": ("Rosso", "rosso"),
    "v": ("Verde", "verde"),
    "b": ("Blu", "blu"),
}


def reagent_storage_item(stock_key: str) -> dict[str, Any]:
    normalized = normalize_stock_key(stock_key) or ""
    color_label, color_key = STOCK_COLORS.get(normalized[:1], ("Reagente", ""))
    level = int(normalized[1]) if len(normalized) == 2 and normalized[1].isdigit() else 0
    synthetic_id = -(("rvb".find(normalized[:1]) + 1) * 10 + level)
    return {
        "id": synthetic_id,
        "name": f"Reagente {color_label} · livello {level}",
        "icon": "alchimia",
        "types": ["Reagente", "Alchimia"],
        "typeValues": ["Reagente", color_label, f"Livello {level}", ""],
        "description": (
            f"Scorta alchemica {color_key} di livello {level}. "
            "Gli esemplari uguali condividono un solo spazio."
        ),
        "value": 0,
        "weight": 0,
        "rarity": None,
        "rarityLabel": "",
        "lootLevel": str(level),
        "region": "",
        "effects": [],
        "elderEffects": [],
        "imageUrl": "",
        "archived": False,
        "special": False,
        "isProjectile": False,
        "compatibleEquipmentSlots": [],
        "metadata": {
            "storageOnly": True,
            "storageKind": "reagent",
            "storageStockKey": normalized,
        },
    }


def storage_catalog_payload() -> list[dict[str, Any]]:
    return [
        reagent_storage_item(f"{color}{level}")
        for color in ("r", "v", "b")
        for level in range(1, 5)
    ]


def _character_for_update(character_id: int) -> Personaggio:
    try:
        return (
            Personaggio.objects.select_for_update()
            .select_related("campagna")
            .get(pk=character_id)
        )
    except Personaggio.DoesNotExist as exc:
        raise ApiError("character.not_found", "Personaggio non trovato.", status=404) from exc


def _container_lookup(character: Personaggio, group: str) -> dict[str, Any]:
    if group == "utility":
        return {
            "scope": ContenitoreInventario.SCOPE_PERSONAL,
            "personaggio": character,
        }
    if group == "campaign":
        if not character.campagna_id:
            raise ApiError(
                "inventory.campaign_missing",
                "Il personaggio non è collegato a una campagna.",
                status=409,
            )
        return {
            "scope": ContenitoreInventario.SCOPE_CAMPAIGN,
            "campagna": character.campagna,
        }
    raise ApiError("inventory.group_not_found", "Il contenitore scelto non esiste.", status=404)


def _container_defaults(character: Personaggio, group: str) -> dict[str, Any]:
    if group == "utility":
        return {
            "nome": f"Alchimia&Contenitori · {character.nome}"[:160],
            "capacita": PERSONAL_CONTAINER_CAPACITY,
            "senza_peso": True,
        }
    return {
        "nome": f"Risorse gruppo · {character.campagna.nome}"[:160],
        "capacita": CAMPAIGN_CONTAINER_CAPACITY,
        "senza_peso": True,
    }


def _get_or_create_container(
    character: Personaggio,
    group: str,
    *,
    lock: bool = True,
) -> ContenitoreInventario:
    lookup = _container_lookup(character, group)
    queryset = ContenitoreInventario.objects
    if lock:
        queryset = queryset.select_for_update()
    container = queryset.filter(**lookup).first()
    if container is None:
        container = ContenitoreInventario.objects.create(
            **lookup,
            **_container_defaults(character, group),
        )
    return container


def _slot_number(container: ContenitoreInventario, raw_slot: Any) -> int:
    try:
        slot = int(raw_slot)
    except (TypeError, ValueError) as exc:
        raise ApiError("inventory.slot_invalid", "Lo spazio scelto non è valido.", "slot") from exc
    if not 1 <= slot <= container.capacita:
        raise ApiError(
            "inventory.slot_locked",
            f"Lo spazio {slot} non è disponibile in questo contenitore.",
            "slot",
            409,
        )
    return slot


def legacy_reagent_stock_key(item: Oggetto | None) -> str | None:
    """Translate imported Elder reagent objects into canonical container stock."""
    if item is None:
        return None
    text = " ".join(
        str(value or "")
        for value in (item.nome, item.tipo_1, item.tipo_2, item.tipo_3, item.tipo_4, item.lv_loot)
    ).casefold()
    if "reagent" not in text:
        return None
    short = "r" if "ross" in text else "v" if "verd" in text else "b" if "blu" in text else ""
    level_match = re.search(r"(?:lv|livello)?\s*([1-4])\b", text)
    return f"{short}{level_match.group(1)}" if short and level_match else None


def _same_content(
    entry: VoceContenitoreInventario,
    *,
    item_id: int | None,
    stock_key: str,
) -> bool:
    return (
        (item_id is not None and entry.oggetto_id == item_id)
        or (bool(stock_key) and entry.reagent_stock_key == stock_key)
    )


@transaction.atomic
def assign_extended_item(
    character_id: int,
    target: dict[str, Any],
    *,
    item_id: int | None = None,
    stock_key: str = "",
    quantity: int = 1,
) -> Personaggio:
    character = _character_for_update(character_id)
    group = str(target.get("group") or "")
    container = _get_or_create_container(character, group)
    slot = _slot_number(container, target.get("slot"))
    entries = container.voci.select_for_update().select_related("oggetto")
    target_entry = entries.filter(slot=slot).first()

    normalized_stock_key = normalize_stock_key(stock_key) or ""
    if stock_key and (
        not normalized_stock_key
        or not STOCK_KEY_PATTERN.fullmatch(normalized_stock_key)
    ):
        raise ApiError("inventory.reagent_invalid", "Il reagente scelto non è valido.", "stockKey")
    if item_id is not None and normalized_stock_key:
        raise ApiError(
            "inventory.content_ambiguous",
            "Scegli un oggetto oppure un reagente, non entrambi.",
            status=400,
        )

    if item_id is None and not normalized_stock_key:
        if target_entry:
            target_entry.delete()
        return character

    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ApiError("inventory.quantity_invalid", "La quantità deve essere un numero intero.", "quantity") from exc
    if not 1 <= quantity <= 9999:
        raise ApiError(
            "inventory.quantity_invalid",
            "La quantità deve essere compresa tra 1 e 9999.",
            "quantity",
        )
    item = None
    if item_id is not None:
        try:
            item = Oggetto.objects.get(pk=item_id, archiviato=False, archived_at__isnull=True)
        except Oggetto.DoesNotExist as exc:
            raise ApiError("inventory.item_not_found", "Oggetto non trovato.", "itemId", 404) from exc
        if isinstance(item.metadata, dict) and item.metadata.get("systemManaged"):
            raise ApiError(
                "inventory.system_item_managed",
                f"{item.nome} è gestito automaticamente e non può essere inserito manualmente.",
                "itemId",
                409,
            )
        if group == "utility" and (legacy_key := legacy_reagent_stock_key(item)):
            item_id = None
            item = None
            normalized_stock_key = legacy_key

    if target_entry and not _same_content(
        target_entry,
        item_id=item_id,
        stock_key=normalized_stock_key,
    ):
        raise ApiError(
            "inventory.slot_occupied",
            "Lo spazio contiene già un altro elemento. Svuotalo o scegli uno spazio libero.",
            "slot",
            409,
        )

    duplicate = entries.exclude(pk=target_entry.pk if target_entry else None).filter(
        oggetto_id=item_id
    ).first() if item_id is not None else entries.exclude(
        pk=target_entry.pk if target_entry else None
    ).filter(reagent_stock_key=normalized_stock_key).first()
    if duplicate:
        duplicate.quantita += quantity
        duplicate.save(update_fields=["quantita", "updated_at"])
    elif target_entry:
        target_entry.quantita = quantity
        target_entry.save(update_fields=["quantita", "updated_at"])
    else:
        VoceContenitoreInventario.objects.create(
            contenitore=container,
            slot=slot,
            oggetto=item,
            reagent_stock_key=normalized_stock_key,
            quantita=quantity,
        )
    return character


@transaction.atomic
def set_extended_quantity(
    character_id: int,
    target: dict[str, Any],
    quantity: int,
) -> Personaggio:
    character = _character_for_update(character_id)
    container = _get_or_create_container(character, str(target.get("group") or ""))
    slot = _slot_number(container, target.get("slot"))
    entry = container.voci.select_for_update().filter(slot=slot).first()
    if entry is None:
        raise ApiError("inventory.empty_source", "Lo spazio scelto è vuoto.", "slot", 409)
    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ApiError("inventory.quantity_invalid", "La quantità deve essere un numero intero.", "quantity") from exc
    if quantity <= 0:
        entry.delete()
    elif quantity <= 9999:
        entry.quantita = quantity
        entry.save(update_fields=["quantita", "updated_at"])
    else:
        raise ApiError(
            "inventory.quantity_invalid",
            "La quantità massima è 9999.",
            "quantity",
        )
    return character


def _entry_content_filter(entry: VoceContenitoreInventario) -> dict[str, Any]:
    if entry.oggetto_id:
        return {"oggetto_id": entry.oggetto_id}
    return {"reagent_stock_key": entry.reagent_stock_key}


@transaction.atomic
def swap_extended_items(
    character_id: int,
    source: dict[str, Any],
    target: dict[str, Any],
) -> Personaggio:
    character = _character_for_update(character_id)
    source_group = str(source.get("group") or "")
    target_group = str(target.get("group") or "")
    if source_group not in EXTENDED_INVENTORY_GROUPS or target_group not in EXTENDED_INVENTORY_GROUPS:
        raise ApiError(
            "inventory.container_boundary",
            "Gli oggetti impilati si spostano tra Alchimia e Risorse gruppo. "
            "Per Zaino, Faretra ed equipaggiamento usa Inserisci e Svuota.",
            status=409,
        )
    source_container = _get_or_create_container(character, source_group)
    target_container = (
        source_container
        if source_group == target_group
        else _get_or_create_container(character, target_group)
    )
    source_slot = _slot_number(source_container, source.get("slot"))
    target_slot = _slot_number(target_container, target.get("slot"))
    if source_container.pk == target_container.pk and source_slot == target_slot:
        return character

    source_entry = (
        source_container.voci.select_for_update()
        .select_related("oggetto")
        .filter(slot=source_slot)
        .first()
    )
    if source_entry is None:
        raise ApiError("inventory.empty_source", "Lo spazio di partenza è vuoto.", status=409)
    target_entry = (
        target_container.voci.select_for_update()
        .select_related("oggetto")
        .filter(slot=target_slot)
        .first()
    )

    if source_container.pk == target_container.pk:
        source_entry.slot = 0
        source_entry.save(update_fields=["slot", "updated_at"])
        if target_entry:
            target_entry.slot = source_slot
            target_entry.save(update_fields=["slot", "updated_at"])
        source_entry.slot = target_slot
        source_entry.save(update_fields=["slot", "updated_at"])
        return character

    source_duplicate = target_container.voci.select_for_update().filter(
        **_entry_content_filter(source_entry)
    ).exclude(pk=target_entry.pk if target_entry else None).first()
    if source_duplicate:
        if target_entry:
            raise ApiError(
                "inventory.duplicate_stack",
                "Nel contenitore di destinazione esiste già questa pila.",
                status=409,
            )
        source_duplicate.quantita += source_entry.quantita
        source_duplicate.save(update_fields=["quantita", "updated_at"])
        source_entry.delete()
    else:
        if target_entry:
            target_duplicate = source_container.voci.select_for_update().filter(
                **_entry_content_filter(target_entry)
            ).exclude(pk=source_entry.pk).exists()
            if target_duplicate:
                raise ApiError(
                    "inventory.duplicate_stack",
                    "Nel contenitore di partenza esiste già la pila che verrebbe scambiata.",
                    status=409,
                )
        source_entry.slot = 0
        source_entry.save(update_fields=["slot", "updated_at"])
        if target_entry:
            target_entry.contenitore = source_container
            target_entry.slot = source_slot
            target_entry.save(update_fields=["contenitore", "slot", "updated_at"])
        source_entry.contenitore = target_container
        source_entry.slot = target_slot
        source_entry.save(update_fields=["contenitore", "slot", "updated_at"])

    return character


def personal_container(character: Personaggio, *, lock: bool = False) -> ContenitoreInventario:
    return _get_or_create_container(character, "utility", lock=lock)


def reagent_stock_for_container(container: ContenitoreInventario) -> dict[str, int]:
    stock = {f"{color}{level}": 0 for color in "rvb" for level in range(1, 5)}
    for key, quantity in container.voci.exclude(reagent_stock_key="").values_list(
        "reagent_stock_key", "quantita"
    ):
        normalized = normalize_stock_key(key)
        if normalized:
            stock[normalized] += max(0, int(quantity))
    return stock


def personal_storage_usage(character: Personaggio) -> tuple[int, int]:
    container = ContenitoreInventario.objects.filter(
        scope=ContenitoreInventario.SCOPE_PERSONAL,
        personaggio=character,
    ).first()
    if container:
        return container.capacita, container.voci.count()
    return PERSONAL_CONTAINER_CAPACITY, 0

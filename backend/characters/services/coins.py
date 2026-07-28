from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from backend.core.api import ApiError
from backend.core.models import DatiCampagna, Oggetto

from ..models import Personaggio, Zaino
from .inventory_rules import backpack_capacity, sort_container_items_by_weight
from .refresh_personaggio import refresh_personaggio


COIN_SYSTEM_KEY = "currency.coins"
MAX_COIN_BALANCE = 2_147_483_647
DEFAULT_COINS_PER_SLOT = 300


@dataclass(frozen=True)
class CoinBalanceResult:
    character: Personaggio
    transferred: int = 0


def _coin_queryset():
    return Oggetto.objects.filter(archived_at__isnull=True)


def coin_item() -> Oggetto | None:
    return (
        _coin_queryset().filter(metadata__systemKey=COIN_SYSTEM_KEY).first()
        or _coin_queryset().filter(nome__iexact="Monete").first()
    )


def ensure_coin_item() -> Oggetto:
    queryset = Oggetto.objects.select_for_update()
    item = (
        queryset.filter(metadata__systemKey=COIN_SYSTEM_KEY).first()
        or queryset.filter(nome__iexact="Monete").first()
    )
    if item is None:
        item = Oggetto(nome="Monete")

    metadata = dict(item.metadata or {})
    metadata.update({"systemKey": COIN_SYSTEM_KEY, "systemManaged": True})
    desired = {
        "nome": "Monete",
        "modello": True,
        "archiviato": False,
        "archived_at": None,
        "tipo_1": "Valuta",
        "descrizione": "Monete trasportate dal personaggio. Gli spazi occupati sono gestiti automaticamente.",
        "peso": 1,
        "metadata": metadata,
    }
    changed = []
    for field, value in desired.items():
        if getattr(item, field) != value:
            setattr(item, field, value)
            changed.append(field)
    if item.pk is None:
        item.save()
    elif changed:
        item.save(update_fields=[*changed, "updated_at"])
    return item


def _positive_balance(value: object, field: str = "coins") -> int:
    try:
        balance = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError("character.coins_invalid", "Le monete devono essere un numero intero.", field) from exc
    if not 0 <= balance <= MAX_COIN_BALANCE:
        raise ApiError(
            "character.coins_invalid",
            f"Le monete devono essere comprese tra 0 e {MAX_COIN_BALANCE}.",
            field,
        )
    return balance


def coins_per_slot(totals: dict[str, Any]) -> int:
    raw_value = totals.get("monete_per_slot")
    if raw_value in (None, "", 0, 0.0):
        return DEFAULT_COINS_PER_SLOT
    try:
        value = math.floor(float(raw_value))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ApiError(
            "character.coins_per_slot_invalid",
            "La variabile Monete per spazio non è configurata correttamente.",
            "monete_per_slot",
            409,
        ) from exc
    if value <= 0:
        raise ApiError(
            "character.coins_per_slot_invalid",
            "La variabile Monete per spazio deve essere maggiore di zero.",
            "monete_per_slot",
            409,
        )
    return value


def coin_storage_payload(character: Personaggio, *, requested_coins: int | None = None) -> dict[str, Any]:
    totals = character.tot if isinstance(character.tot, dict) else {}
    per_slot = coins_per_slot(totals)
    capacity = backpack_capacity(totals)
    canonical = coin_item()
    coin_item_id = canonical.id if canonical else None
    non_coin_occupied = 0
    placed_slots = 0
    if character.zaino:
        for index in range(1, capacity + 1):
            item_id = getattr(character.zaino, f"slot_{index}_id", None)
            if item_id is None:
                continue
            if coin_item_id is not None and item_id == coin_item_id:
                placed_slots += 1
            else:
                non_coin_occupied += 1
    available_slots = max(0, capacity - non_coin_occupied)
    balance = character.monete if requested_coins is None else _positive_balance(requested_coins)
    required_slots = math.ceil(balance / per_slot) if balance else 0
    max_carryable = min(MAX_COIN_BALANCE, available_slots * per_slot)
    return {
        "coinsPerSlot": per_slot,
        "requiredSlots": required_slots,
        "placedSlots": placed_slots,
        "availableSlots": available_slots,
        "maxCarryableCoins": max_carryable,
        "fits": required_slots <= available_slots,
        "coinItemId": coin_item_id,
        "sharedCoins": character.campagna.monete_condivise if character.campagna_id else 0,
        "canTransferToShared": bool(character.campagna_id),
    }


def _lock_character(character_id: int) -> Personaggio:
    character = (
        Personaggio.objects.select_for_update()
        .select_related("zaino", "campagna")
        .get(pk=character_id)
    )
    if character.zaino_id:
        character.zaino = Zaino.objects.select_for_update().get(pk=character.zaino_id)
    if character.campagna_id:
        character.campagna = DatiCampagna.objects.select_for_update().get(pk=character.campagna_id)
    return character


def apply_carried_coin_balance_locked(
    character: Personaggio,
    requested_coins: object,
    *,
    transfer_overflow: bool = False,
    expected_coins: object | None = None,
    expected_shared_coins: object | None = None,
    refresh: bool = True,
) -> CoinBalanceResult:
    requested = _positive_balance(requested_coins)
    if expected_coins is not None and character.monete != _positive_balance(expected_coins, "expectedCoins"):
        raise ApiError(
            "character.coins_stale",
            f"Il saldo è cambiato nel frattempo: ora hai {character.monete} monete. Controlla il valore e riprova.",
            "expectedCoins",
            409,
        )
    if character.zaino is None:
        raise ApiError("inventory.backpack_missing", "Il personaggio non ha uno zaino.", "characterId", 409)

    canonical = ensure_coin_item()
    storage = coin_storage_payload(character, requested_coins=requested)
    carried = requested
    transferred = 0
    if not storage["fits"]:
        if not transfer_overflow:
            raise ApiError(
                "character.coins_over_capacity",
                (
                    f"Servono {storage['requiredSlots']} spazi, disponibili {storage['availableSlots']}. "
                    f"Puoi trasportare al massimo {storage['maxCarryableCoins']} monete."
                ),
                "coins",
                409,
            )
        if not character.campagna_id:
            raise ApiError(
                "campaign.shared_coins_unavailable",
                "Il personaggio non appartiene a una campagna con monete condivise.",
                "coins",
                409,
            )
        if expected_shared_coins is not None and character.campagna.monete_condivise != _positive_balance(
            expected_shared_coins, "expectedSharedCoins"
        ):
            raise ApiError(
                "campaign.shared_coins_stale",
                (
                    "Le monete condivise sono cambiate nel frattempo: "
                    f"ora sono {character.campagna.monete_condivise}. Controlla il valore e riprova."
                ),
                "expectedSharedCoins",
                409,
            )
        carried = storage["maxCarryableCoins"]
        transferred = requested - carried
        shared_total = character.campagna.monete_condivise + transferred
        if shared_total > MAX_COIN_BALANCE:
            raise ApiError(
                "campaign.shared_coins_limit",
                "Il trasferimento supererebbe il limite delle monete condivise.",
                "coins",
                409,
            )
        character.campagna.monete_condivise = shared_total
        character.campagna.save(update_fields=["monete_condivise", "updated_at"])

    required_slots = math.ceil(carried / storage["coinsPerSlot"]) if carried else 0
    changed_fields: list[str] = []
    for index in range(1, 51):
        field = f"slot_{index}"
        if getattr(character.zaino, f"{field}_id", None) == canonical.id:
            setattr(character.zaino, field, None)
            changed_fields.append(field)

    capacity = backpack_capacity(character.tot if isinstance(character.tot, dict) else {})
    empty_active_slots = [
        index
        for index in range(1, capacity + 1)
        if getattr(character.zaino, f"slot_{index}_id", None) is None
    ]
    # The arithmetic guard above guarantees this slice is bounded and large enough.
    for index in empty_active_slots[:required_slots]:
        field = f"slot_{index}"
        setattr(character.zaino, field, canonical)
        if field not in changed_fields:
            changed_fields.append(field)

    _mapping, sorted_fields = sort_container_items_by_weight(character.zaino)
    changed_fields.extend(field for field in sorted_fields if field not in changed_fields)
    if changed_fields:
        character.zaino.save(update_fields=[*changed_fields, "updated_at"])
    if character.monete != carried:
        character.monete = carried
        character.save(update_fields=["monete", "updated_at"])
    if refresh:
        refresh_personaggio(character)
        character.refresh_from_db()
    return CoinBalanceResult(character=character, transferred=transferred)


@transaction.atomic
def update_carried_coins(
    character_id: int,
    coins: object,
    *,
    transfer_overflow: bool = False,
    expected_coins: object | None = None,
    expected_shared_coins: object | None = None,
) -> CoinBalanceResult:
    character = _lock_character(character_id)
    return apply_carried_coin_balance_locked(
        character,
        coins,
        transfer_overflow=transfer_overflow,
        expected_coins=expected_coins,
        expected_shared_coins=expected_shared_coins,
    )


@transaction.atomic
def update_shared_coins(character_id: int, coins: object, *, expected_coins: object | None = None) -> Personaggio:
    character = _lock_character(character_id)
    if not character.campagna_id:
        raise ApiError(
            "campaign.shared_coins_unavailable",
            "Il personaggio non appartiene a una campagna con monete condivise.",
            "characterId",
            409,
        )
    requested = _positive_balance(coins)
    if expected_coins is not None and character.campagna.monete_condivise != _positive_balance(
        expected_coins, "expectedCoins"
    ):
        raise ApiError(
            "campaign.shared_coins_stale",
            (
                "Le monete condivise sono cambiate nel frattempo: "
                f"ora sono {character.campagna.monete_condivise}. Controlla il valore e riprova."
            ),
            "expectedCoins",
            409,
        )
    if character.campagna.monete_condivise != requested:
        character.campagna.monete_condivise = requested
        character.campagna.save(update_fields=["monete_condivise", "updated_at"])
    return character

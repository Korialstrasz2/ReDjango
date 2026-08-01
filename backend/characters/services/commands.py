from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from backend.core.api import ApiError
from backend.core.models import Effetto, Oggetto

from ..models import EffettiPersonaggio, Equip, Faretra, Personaggio, Zaino
from .inventory_rules import (
    InventoryRuleError,
    SlotReference,
    backpack_capacity,
    get_slot_item,
    equipment_dual_wield,
    occupied_slots_after,
    quiver_capacity,
    set_slot_item,
    sort_container_items_by_weight,
    validate_item_for_reference,
    validate_hand_configuration,
    validate_reference_is_active,
)
from .refresh_personaggio import refresh_personaggio
from .resources import accrue_mana_siphon, recover_mana_siphon, spend_energy


RESOURCE_FIELDS = {
    "pf": "danno",
    "mana": "mana_speso",
    "energia": "energia_spesa",
    "potere": "potere_speso",
}
QUICK_STATS = {"stanchezza", "modificatore_generale"}


@dataclass(frozen=True)
class ItemAssignmentResult:
    personaggio: Personaggio
    assigned_item: Oggetto | None = None
    replaced_item: Oggetto | None = None
    backpack_slot: int | None = None
    backpack_slot_locked: bool = False
    replaced_item_lost: bool = False


def _locked_personaggio(personaggio_id: int) -> Personaggio:
    personaggio = (
        Personaggio.objects.select_for_update()
        .select_related("equip", "zaino", "faretra", "effetti", "note")
        .get(pk=personaggio_id)
    )
    if personaggio.equip_id:
        personaggio.equip = Equip.objects.select_for_update().get(pk=personaggio.equip_id)
    if personaggio.zaino_id:
        personaggio.zaino = Zaino.objects.select_for_update().get(pk=personaggio.zaino_id)
    if personaggio.faretra_id:
        personaggio.faretra = Faretra.objects.select_for_update().get(pk=personaggio.faretra_id)
    if personaggio.effetti_id:
        personaggio.effetti = EffettiPersonaggio.objects.select_for_update().get(pk=personaggio.effetti_id)
    return personaggio


def _api_error(error: InventoryRuleError) -> ApiError:
    return ApiError(error.code, error.message, error.field, status=409)


def _reject_system_managed_item(item: Oggetto | None) -> None:
    metadata = item.metadata if item and isinstance(item.metadata, dict) else {}
    if metadata.get("systemManaged"):
        raise ApiError(
            "inventory.system_item_managed",
            f"{item.nome} è gestito automaticamente e non può essere spostato o sostituito.",
            status=409,
        )


def _save_changed_containers(personaggio: Personaggio, references: tuple[SlotReference, SlotReference]) -> None:
    groups = {reference.group for reference in references}
    if "equipment" in groups and personaggio.equip:
        personaggio.equip.save()
    if "backpack" in groups and personaggio.zaino:
        personaggio.zaino.save()
    if "quiver" in groups and personaggio.faretra:
        personaggio.faretra.save()


def _sort_changed_containers(
    personaggio: Personaggio,
    groups: set[str],
) -> tuple[dict[str, dict[int, int]], bool]:
    mappings: dict[str, dict[int, int]] = {}
    changed = False
    for group, container in (("backpack", personaggio.zaino), ("quiver", personaggio.faretra)):
        if group not in groups or container is None:
            continue
        mapping, changed_fields = sort_container_items_by_weight(container)
        mappings[group] = mapping
        if changed_fields:
            container.save(update_fields=[*changed_fields, "updated_at"])
            changed = True
    return mappings, changed


def _reload_inventory_relations(personaggio: Personaggio) -> None:
    personaggio.refresh_from_db()
    personaggio.equip = Equip.objects.get(pk=personaggio.equip_id) if personaggio.equip_id else None
    personaggio.zaino = Zaino.objects.get(pk=personaggio.zaino_id) if personaggio.zaino_id else None
    personaggio.faretra = Faretra.objects.get(pk=personaggio.faretra_id) if personaggio.faretra_id else None


def _validate_capacity_after_refresh(
    personaggio: Personaggio,
    totals: dict[str, Any],
    *,
    allowed_backpack_overflow: set[int] | None = None,
) -> None:
    backpack_overflow = occupied_slots_after(personaggio.zaino, backpack_capacity(totals))
    if len(backpack_overflow) > len(allowed_backpack_overflow or set()):
        raise ApiError(
            "inventory.backpack_capacity_reduced",
            "Lo spostamento ridurrebbe la capacità dello zaino lasciando oggetti in spazi bloccati. "
            "Libera prima gli ultimi spazi.",
            status=409,
        )
    quiver_overflow = occupied_slots_after(personaggio.faretra, quiver_capacity(personaggio.equip))
    if quiver_overflow:
        raise ApiError(
            "inventory.quiver_capacity_reduced",
            "Lo spostamento ridurrebbe la capacità della faretra lasciando proiettili senza spazio. "
            "Svuota prima gli ultimi spazi della faretra.",
            status=409,
        )


def _first_empty_backpack_slot(personaggio: Personaggio, capacity: int) -> tuple[int, bool] | None:
    if personaggio.zaino is None:
        return None
    for index in (*range(1, capacity + 1), *range(capacity + 1, 51)):
        if getattr(personaggio.zaino, f"slot_{index}") is None:
            return index, index > capacity
    return None


@transaction.atomic
def swap_items(personaggio_id: int, source: dict[str, Any], target: dict[str, Any]) -> Personaggio:
    personaggio = _locked_personaggio(personaggio_id)
    existing_backpack_overflow = set(
        occupied_slots_after(personaggio.zaino, backpack_capacity(personaggio.tot or {}))
    )
    source_ref = SlotReference(str(source.get("group", "")), str(source.get("slot", "")))
    target_ref = SlotReference(str(target.get("group", "")), str(target.get("slot", "")))
    if source_ref == target_ref:
        return personaggio

    try:
        validate_reference_is_active(personaggio, source_ref, personaggio.tot or {})
        validate_reference_is_active(personaggio, target_ref, personaggio.tot or {})
        source_item = get_slot_item(personaggio, source_ref)
        target_item = get_slot_item(personaggio, target_ref)
        _reject_system_managed_item(source_item)
        _reject_system_managed_item(target_item)
        if source_item is None:
            raise InventoryRuleError("inventory.empty_source", "Lo spazio di partenza è vuoto.")
        validate_item_for_reference(source_item, target_ref)
        validate_item_for_reference(target_item, source_ref)
        set_slot_item(personaggio, source_ref, target_item)
        set_slot_item(personaggio, target_ref, source_item)
        validate_hand_configuration(personaggio.equip)
        if personaggio.equip and not equipment_dual_wield(personaggio.equip):
            personaggio.equip.arma_primaria_slot = "arma"
    except InventoryRuleError as error:
        raise _api_error(error) from error

    _save_changed_containers(personaggio, (source_ref, target_ref))
    result = refresh_personaggio(personaggio)
    _reload_inventory_relations(personaggio)
    _validate_capacity_after_refresh(
        personaggio,
        result.totals,
        allowed_backpack_overflow=existing_backpack_overflow,
    )
    _mappings, order_changed = _sort_changed_containers(
        personaggio,
        {source_ref.group, target_ref.group},
    )
    if order_changed:
        result = refresh_personaggio(personaggio)
        _reload_inventory_relations(personaggio)
        _validate_capacity_after_refresh(
            personaggio,
            result.totals,
            allowed_backpack_overflow=existing_backpack_overflow,
        )
    return personaggio


@transaction.atomic
def assign_item(personaggio_id: int, target: dict[str, Any], item_id: int | None) -> ItemAssignmentResult:
    personaggio = _locked_personaggio(personaggio_id)
    target_ref = SlotReference(str(target.get("group", "")), str(target.get("slot", "")))
    item = None if item_id is None else Oggetto.objects.get(pk=item_id, archiviato=False, archived_at__isnull=True)
    _reject_system_managed_item(item)
    existing_backpack_overflow = set(
        occupied_slots_after(personaggio.zaino, backpack_capacity(personaggio.tot or {}))
    )
    try:
        validate_reference_is_active(personaggio, target_ref, personaggio.tot or {})
        validate_item_for_reference(item, target_ref)
        replaced_item = get_slot_item(personaggio, target_ref)
        _reject_system_managed_item(replaced_item)
        if replaced_item == item:
            _mappings, order_changed = _sort_changed_containers(personaggio, {target_ref.group})
            if order_changed:
                refresh_personaggio(personaggio)
                _reload_inventory_relations(personaggio)
            return ItemAssignmentResult(personaggio=personaggio, assigned_item=item)
        set_slot_item(personaggio, target_ref, item)
        validate_hand_configuration(personaggio.equip)
        if personaggio.equip and not equipment_dual_wield(personaggio.equip):
            personaggio.equip.arma_primaria_slot = "arma"
    except InventoryRuleError as error:
        raise _api_error(error) from error

    _save_changed_containers(personaggio, (target_ref, target_ref))
    result = refresh_personaggio(personaggio)
    _reload_inventory_relations(personaggio)

    backpack_slot = None
    backpack_slot_locked = False
    replaced_item_lost = False
    if item is not None and replaced_item is not None:
        capacity = backpack_capacity(result.totals)
        destination = _first_empty_backpack_slot(personaggio, capacity)
        if destination is None:
            replaced_item_lost = True
        else:
            backpack_slot, backpack_slot_locked = destination
            set_slot_item(personaggio, SlotReference("backpack", str(backpack_slot)), replaced_item)
            personaggio.zaino.save()
            if backpack_slot_locked:
                existing_backpack_overflow.add(backpack_slot)
            result = refresh_personaggio(personaggio)
            _reload_inventory_relations(personaggio)

    _validate_capacity_after_refresh(
        personaggio,
        result.totals,
        allowed_backpack_overflow=existing_backpack_overflow,
    )
    changed_groups = {target_ref.group}
    if backpack_slot is not None:
        changed_groups.add("backpack")
    mappings, order_changed = _sort_changed_containers(personaggio, changed_groups)
    if backpack_slot is not None:
        backpack_slot = mappings.get("backpack", {}).get(backpack_slot, backpack_slot)
        backpack_slot_locked = backpack_slot > backpack_capacity(result.totals)
    if order_changed:
        result = refresh_personaggio(personaggio)
        _reload_inventory_relations(personaggio)
        _validate_capacity_after_refresh(
            personaggio,
            result.totals,
            allowed_backpack_overflow=existing_backpack_overflow,
        )
    return ItemAssignmentResult(
        personaggio=personaggio,
        assigned_item=item,
        replaced_item=replaced_item,
        backpack_slot=backpack_slot,
        backpack_slot_locked=backpack_slot_locked,
        replaced_item_lost=replaced_item_lost,
    )


@transaction.atomic
def switch_primary_weapon(personaggio_id: int) -> Personaggio:
    personaggio = _locked_personaggio(personaggio_id)
    if not equipment_dual_wield(personaggio.equip):
        raise ApiError(
            "inventory.dual_wield_required",
            "Puoi cambiare arma primaria soltanto con due armi corte o medie equipaggiate.",
            status=409,
        )
    personaggio.equip.arma_primaria_slot = (
        "scudo" if personaggio.equip.arma_primaria_slot == "arma" else "arma"
    )
    personaggio.equip.save(update_fields=["arma_primaria_slot", "updated_at"])
    refresh_personaggio(personaggio)
    _reload_inventory_relations(personaggio)
    return personaggio


@transaction.atomic
def update_resource(personaggio_id: int, resource: str, current: int) -> Personaggio:
    personaggio = _locked_personaggio(personaggio_id)
    field_name = RESOURCE_FIELDS.get(resource)
    if field_name is None:
        raise ApiError("character.unknown_resource", "La risorsa scelta non è disponibile.", "resource")
    maximum = max(0, int(float((personaggio.tot or {}).get(resource, 0) or 0)))
    if resource == "energia" and int(current) < 0:
        current_before = maximum - int(personaggio.energia_spesa or 0)
        additional_spend = current_before - int(current)
        if additional_spend > 0:
            spend_energy(personaggio, additional_spend)
            return personaggio
    spent_before = int(getattr(personaggio, field_name) or 0)
    setattr(personaggio, field_name, maximum - current)
    personaggio.save(update_fields=[field_name, "updated_at"])
    # Solo una spesa vera alimenta il sifone: rialzare la barra non lo riempie.
    if resource == "mana":
        additional_spend = int(getattr(personaggio, field_name) or 0) - spent_before
        if additional_spend > 0:
            accrue_mana_siphon(personaggio, additional_spend)
    return personaggio


@transaction.atomic
def recover_mana_from_siphon(personaggio_id: int) -> Personaggio:
    personaggio = _locked_personaggio(personaggio_id)
    recover_mana_siphon(personaggio)
    return personaggio


@transaction.atomic
def adjust_quick_stat(personaggio_id: int, stat: str, delta: int) -> Personaggio:
    personaggio = _locked_personaggio(personaggio_id)
    if stat not in QUICK_STATS:
        raise ApiError("character.unknown_quick_stat", "Il valore scelto non è modificabile qui.", "stat")
    if int(delta) not in (-1, 1):
        raise ApiError("character.invalid_quick_stat_delta", "Usa soltanto -1 o +1.", "delta")

    report = personaggio.effetti_finali if isinstance(personaggio.effetti_finali, dict) else {}
    sources = report.get("calculation_sources") if isinstance(report.get("calculation_sources"), dict) else {}
    stat_sources = sources.get(stat) if isinstance(sources.get(stat), dict) else {}
    try:
        base_value = float(stat_sources.get("base", (personaggio.tot or {}).get(stat, 0)) or 0)
    except (TypeError, ValueError):
        base_value = 0
    updated_value = base_value + int(delta)

    if stat == "stanchezza" and int(delta) > 0:
        personaggio.stanchezza_accumulata = int(personaggio.stanchezza_accumulata or 0) + 1
        personaggio.save(update_fields=["stanchezza_accumulata", "updated_at"])
        refresh_personaggio(personaggio)
        personaggio.refresh_from_db()
        return personaggio
    if stat == "stanchezza" and int(delta) < 0 and int(personaggio.stanchezza_accumulata or 0) > 0:
        personaggio.stanchezza_accumulata = int(personaggio.stanchezza_accumulata or 0) - 1
        personaggio.save(update_fields=["stanchezza_accumulata", "updated_at"])
        refresh_personaggio(personaggio)
        personaggio.refresh_from_db()
        return personaggio

    extra = dict(personaggio.extra) if isinstance(personaggio.extra, dict) else {}
    extra[stat] = int(updated_value) if updated_value.is_integer() else updated_value
    personaggio.extra = extra
    personaggio.save(update_fields=["extra", "updated_at"])
    refresh_personaggio(personaggio)
    personaggio.refresh_from_db()
    return personaggio


@transaction.atomic
def rest_character(personaggio_id: int, fatigue_recovery: int) -> Personaggio:
    personaggio = _locked_personaggio(personaggio_id)
    fatigue_recovery = min(5, max(0, int(fatigue_recovery)))
    personaggio.danno = 0
    personaggio.mana_speso = 0
    personaggio.potere_speso = 0
    accumulated_recovery = min(fatigue_recovery, max(0, int(personaggio.stanchezza_accumulata or 0)))
    personaggio.stanchezza_accumulata = int(personaggio.stanchezza_accumulata or 0) - accumulated_recovery
    personaggio.save(update_fields=["danno", "mana_speso", "potere_speso", "stanchezza_accumulata", "updated_at"])

    remaining_recovery = fatigue_recovery - accumulated_recovery
    recovered_from_effects = 0
    if remaining_recovery and personaggio.effetti:
        for index in range(1, 51):
            effect = getattr(personaggio.effetti, f"effetto_{index}")
            if effect is None:
                continue
            payload_text = str(effect.effect_payload).lower()
            if "stanchezza" not in payload_text:
                continue
            setattr(personaggio.effetti, f"effetto_{index}", None)
            recovered_from_effects += 1
            if recovered_from_effects >= remaining_recovery:
                break
        if recovered_from_effects:
            personaggio.effetti.save()

    # Elder restores Energia only after the fatigue minimum has been reached,
    # and only if the selected recovery still has points left afterwards.
    if remaining_recovery - recovered_from_effects > 0:
        personaggio.energia_spesa = 0
        personaggio.save(update_fields=["energia_spesa", "updated_at"])

    refresh_personaggio(personaggio)
    personaggio.refresh_from_db()
    return personaggio


@transaction.atomic
def update_overview(personaggio_id: int, payload: dict[str, Any]) -> Personaggio:
    from .coins import update_carried_coins

    personaggio = _locked_personaggio(personaggio_id)
    coin_value = payload.get("coins") if "coins" in payload else None
    allowed = {
        "name": ("nome", str),
        "race1": ("razza_1", str),
        "race2": ("razza_2", str),
        "race3": ("razza_3", str),
        "level": ("livello", int),
        "age": ("eta", int),
        "sex": ("sesso", str),
        "details": ("dettagli_personaggio", str),
        "critMin": ("crit_min", str),
        "critNormal": ("crit_nor", str),
        "critMajor": ("crit_mag", str),
    }
    changed = []
    for key, (field_name, converter) in allowed.items():
        if key not in payload:
            continue
        raw_value = payload[key]
        if field_name == "eta" and raw_value in (None, ""):
            value = None
        else:
            try:
                value = converter(raw_value)
            except (TypeError, ValueError) as exc:
                raise ApiError("character.invalid_value", f"Il valore di {key} non è valido.", key) from exc
        if isinstance(value, str):
            value = value.strip()
        if field_name == "nome" and not value:
            raise ApiError("character.name_required", "Il nome del personaggio è obbligatorio.", key)
        if field_name == "livello" and value < 1:
            raise ApiError("character.level_invalid", "Il livello deve essere almeno 1.", key)
        if field_name == "monete" and value < 0:
            raise ApiError("character.coins_invalid", "Le monete non possono essere negative.", key)
        if getattr(personaggio, field_name) != value:
            setattr(personaggio, field_name, value)
            changed.append(field_name)
    if changed:
        personaggio.save(update_fields=[*changed, "updated_at"])
        refresh_personaggio(personaggio)
        personaggio.refresh_from_db()
    if coin_value is not None:
        personaggio = update_carried_coins(personaggio_id, coin_value).character
    return personaggio


@transaction.atomic
def apply_effect(personaggio_id: int, effect_id: int) -> Personaggio:
    personaggio = _locked_personaggio(personaggio_id)
    if personaggio.effetti is None:
        personaggio.effetti = EffettiPersonaggio.objects.create(nome=f"Effetti - {personaggio.nome}")
        personaggio.save(update_fields=["effetti", "updated_at"])
    effect = Effetto.objects.get(pk=effect_id, archived_at__isnull=True)
    existing_slots = [
        index for index in range(1, 51) if getattr(personaggio.effetti, f"effetto_{index}_id") == effect.id
    ]
    if existing_slots and effect.stacking_rule in {"unique", "refresh_duration", "replace"}:
        return personaggio
    empty_slot = next((index for index in range(1, 51) if getattr(personaggio.effetti, f"effetto_{index}") is None), None)
    if empty_slot is None:
        raise ApiError("effects.no_free_slot", "Non ci sono spazi liberi per un nuovo effetto.", status=409)
    setattr(personaggio.effetti, f"effetto_{empty_slot}", effect)
    personaggio.effetti.save()
    refresh_personaggio(personaggio)
    personaggio.refresh_from_db()
    return personaggio


@transaction.atomic
def remove_effect(personaggio_id: int, slot: int) -> Personaggio:
    personaggio = _locked_personaggio(personaggio_id)
    if personaggio.effetti is None or not 1 <= int(slot) <= 50:
        raise ApiError("effects.slot_not_found", "Lo spazio effetto non esiste.", "slot", 404)
    field_name = f"effetto_{int(slot)}"
    if getattr(personaggio.effetti, field_name) is None:
        raise ApiError("effects.slot_empty", "Lo spazio effetto è già vuoto.", "slot", 404)
    setattr(personaggio.effetti, field_name, None)
    personaggio.effetti.save()
    refresh_personaggio(personaggio)
    personaggio.refresh_from_db()
    return personaggio

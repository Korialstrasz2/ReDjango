from __future__ import annotations

from typing import Any

from backend.core.api import ApiError

from .changes.registry import get_change_handler
from .changes.serializers import serialize_change_set
from .changes.services import (
    add_change_operation,
    delete_change_operation,
    entity_catalog,
    get_change_set_for_user,
    search_change_entities,
)
from .models import AIChangeSet
from .tool_context import AIToolExecutionContext


def _change_set(user, context: AIToolExecutionContext | None) -> AIChangeSet:
    if context is None or context.change_set is None:
        raise ApiError(
            "ai.change_context_required",
            "Questo strumento richiede una proposta modificabile collegata all'esecuzione.",
            status=409,
        )
    change_set = get_change_set_for_user(user, context.change_set.id)
    if change_set.status not in AIChangeSet.EDITABLE_STATUSES:
        raise ApiError("ai.change_set_immutable", "La proposta non è più modificabile.", status=409)
    return change_set


def list_editable_entities(user, giocatore, context: AIToolExecutionContext | None) -> dict[str, Any]:
    _change_set(user, context)
    return {"entita": entity_catalog(user, giocatore)}


def search_manageable_records(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    tipo: str,
    query: str = "",
    limite: int = 10,
) -> dict[str, Any]:
    _change_set(user, context)
    return {
        "tipo": str(tipo or "").strip().lower(),
        "risultati": search_change_entities(user, giocatore, tipo, query, limite),
    }


def read_manageable_record(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    tipo: str,
    id: int,
) -> dict[str, Any]:
    _change_set(user, context)
    handler = get_change_handler(tipo)
    handler.require_access(user, giocatore, "update")
    return {
        "record": handler.snapshot(user, giocatore, id),
        "fields": handler.field_schema(user, giocatore, action="update"),
    }


def propose_create(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    tipo: str,
    valori: dict[str, Any],
    sorgenteId: int | None = None,
) -> dict[str, Any]:
    change_set = _change_set(user, context)
    operation = add_change_operation(
        user,
        giocatore,
        change_set.id,
        entity_type=tipo,
        action="create",
        values=valori,
        source_id=sorgenteId,
    )
    return {
        "propostaId": str(change_set.id),
        "operazioneId": operation.id,
        "tipo": operation.entity_type,
        "azione": operation.action,
        "etichetta": operation.display_label,
        "stato": operation.status,
    }


def propose_update(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    tipo: str,
    id: int,
    valori: dict[str, Any],
) -> dict[str, Any]:
    change_set = _change_set(user, context)
    operation = add_change_operation(
        user,
        giocatore,
        change_set.id,
        entity_type=tipo,
        action="update",
        values=valori,
        target_id=id,
    )
    return {
        "propostaId": str(change_set.id),
        "operazioneId": operation.id,
        "tipo": operation.entity_type,
        "azione": operation.action,
        "etichetta": operation.display_label,
        "stato": operation.status,
    }


def propose_archive(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    tipo: str,
    id: int,
) -> dict[str, Any]:
    change_set = _change_set(user, context)
    operation = add_change_operation(
        user,
        giocatore,
        change_set.id,
        entity_type=tipo,
        action="archive",
        target_id=id,
    )
    return {
        "propostaId": str(change_set.id),
        "operazioneId": operation.id,
        "tipo": operation.entity_type,
        "azione": operation.action,
        "etichetta": operation.display_label,
        "stato": operation.status,
    }


def remove_proposed_operation(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    operazioneId: int,
) -> dict[str, Any]:
    change_set = _change_set(user, context)
    delete_change_operation(user, change_set.id, operazioneId)
    return {
        "propostaId": str(change_set.id),
        "operazioneRimossa": operazioneId,
        "proposta": serialize_change_set(get_change_set_for_user(user, change_set.id)),
    }


def summarize_proposal(user, giocatore, context: AIToolExecutionContext | None) -> dict[str, Any]:
    change_set = _change_set(user, context)
    return {"proposta": serialize_change_set(change_set)}

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.core import signing
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from backend.ai.models import AIChangeOperation, AIChangeSet
from backend.core.api import ApiError
from backend.core.item_services import require_item_author

from .contracts import PreparedChange
from .handlers.base import canonical_digest, field_error
from .registry import change_entity_catalog, get_change_handler
from .serializers import serialize_change_set


TOKEN_SALT = "backend.ai.change-set.apply.v1"
TOKEN_MAX_AGE_SECONDS = 15 * 60
MAX_OPERATIONS = 50
MAX_REQUEST_TEXT = 8000


def _ensure_mutable(change_set: AIChangeSet) -> None:
    if change_set.status not in AIChangeSet.EDITABLE_STATUSES:
        raise ApiError(
            "ai.change_set_immutable",
            "La proposta non può più essere modificata.",
            status=409,
        )


def _invalidate_validation(change_set: AIChangeSet, *, increment_revision: bool = True) -> None:
    if increment_revision:
        change_set.revision += 1
    change_set.status = AIChangeSet.STATUS_DRAFT
    change_set.validation_summary = {}
    change_set.validation_token = ""
    change_set.validated_at = None
    change_set.save(
        update_fields=[
            "revision",
            "status",
            "validation_summary",
            "validation_token",
            "validated_at",
            "updated_at",
        ]
    )


def create_change_set(
    user,
    giocatore,
    *,
    title: str = "",
    request_text: str = "",
    context: dict[str, Any] | None = None,
    conversation=None,
    agent=None,
) -> AIChangeSet:
    require_item_author(user, giocatore)
    return AIChangeSet.objects.create(
        user=user,
        conversation=conversation,
        agent=agent,
        title=str(title or "").strip()[:160],
        request_text=str(request_text or "").strip()[:MAX_REQUEST_TEXT],
        context=context if isinstance(context, dict) else {},
    )


def get_change_set_for_user(user, change_set_id, *, for_update: bool = False) -> AIChangeSet:
    queryset = AIChangeSet.objects.select_related("conversation", "agent", "applied_by").prefetch_related("operations")
    if for_update:
        queryset = queryset.select_for_update()
    try:
        return queryset.get(id=change_set_id, user=user)
    except (ValueError, AIChangeSet.DoesNotExist) as exc:
        raise ApiError("ai.change_set_not_found", "La proposta richiesta non esiste.", status=404) from exc


def list_change_sets_for_user(user, *, limit: int = 10) -> list[AIChangeSet]:
    now = timezone.now()
    return list(
        AIChangeSet.objects.filter(user=user)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .exclude(status=AIChangeSet.STATUS_EXPIRED)
        .order_by("-updated_at")[: max(1, min(limit, 25))]
    )


@transaction.atomic
def update_change_set(user, change_set_id, values: dict[str, Any]) -> AIChangeSet:
    change_set = get_change_set_for_user(user, change_set_id, for_update=True)
    _ensure_mutable(change_set)
    changed = False
    if "title" in values:
        change_set.title = str(values.get("title") or "").strip()[:160]
        changed = True
    if "requestText" in values:
        change_set.request_text = str(values.get("requestText") or "").strip()[:MAX_REQUEST_TEXT]
        changed = True
    if "context" in values:
        context = values.get("context")
        if not isinstance(context, dict):
            raise ApiError("ai.change_context_invalid", "Il contesto deve essere un oggetto JSON.", "context")
        change_set.context = context
        changed = True
    unknown = set(values) - {"title", "requestText", "context"}
    if unknown:
        raise ApiError("ai.change_set_field_unknown", f"Campi proposta non riconosciuti: {', '.join(sorted(unknown))}.")
    if changed:
        _invalidate_validation(change_set)
    return change_set


def _prepare_operation(
    operation: AIChangeOperation,
    user,
    giocatore,
    *,
    for_update: bool = False,
) -> PreparedChange:
    handler = get_change_handler(operation.entity_type)
    if operation.action == AIChangeOperation.ACTION_CREATE:
        return handler.prepare_create(user, giocatore, operation.effective_values, source_id=operation.source_id)
    if operation.action == AIChangeOperation.ACTION_UPDATE:
        return handler.prepare_update(
            user,
            giocatore,
            operation.target_id,
            operation.effective_values,
            for_update=for_update,
        )
    if operation.action == AIChangeOperation.ACTION_ARCHIVE:
        return handler.prepare_archive(
            user,
            giocatore,
            operation.target_id,
            for_update=for_update,
        )
    raise ApiError("ai.change_action_unsupported", "Azione proposta non supportata.", "action")


@transaction.atomic
def add_change_operation(
    user,
    giocatore,
    change_set_id,
    *,
    entity_type: str,
    action: str,
    values: dict[str, Any] | None = None,
    target_id: int | None = None,
    source_id: int | None = None,
    selected: bool = True,
) -> AIChangeOperation:
    change_set = get_change_set_for_user(user, change_set_id, for_update=True)
    _ensure_mutable(change_set)
    if change_set.operations.count() >= MAX_OPERATIONS:
        raise ApiError("ai.change_operation_limit", f"Una proposta può contenere al massimo {MAX_OPERATIONS} operazioni.", status=409)
    handler = get_change_handler(entity_type)
    action = str(action or "").strip().lower()
    handler.require_access(user, giocatore, action)
    if action == AIChangeOperation.ACTION_CREATE:
        if target_id not in (None, ""):
            raise ApiError("ai.change_target_forbidden", "Una creazione non può avere un record di destinazione.", "targetId")
        target = None
    else:
        try:
            target = int(target_id)
        except (TypeError, ValueError) as exc:
            raise ApiError("ai.change_target_required", "La destinazione è obbligatoria.", "targetId") from exc
    source = None
    if source_id not in (None, ""):
        if action != AIChangeOperation.ACTION_CREATE:
            raise ApiError("ai.change_source_forbidden", "La sorgente è ammessa soltanto per una creazione.", "sourceId")
        try:
            source = int(source_id)
        except (TypeError, ValueError) as exc:
            raise ApiError("ai.change_source_invalid", "La sorgente non è valida.", "sourceId") from exc
    if not isinstance(selected, bool):
        raise ApiError("ai.change_selected_invalid", "selected deve essere vero oppure falso.", "selected")
    raw_values = values if isinstance(values, dict) else {}

    temporary = AIChangeOperation(
        change_set=change_set,
        entity_type=handler.entity_type,
        action=action,
        target_id=target,
        source_id=source,
        selected=selected,
        proposed_values=raw_values,
    )
    prepared = _prepare_operation(temporary, user, giocatore)
    max_position = change_set.operations.aggregate(value=Max("position"))["value"]
    position = 0 if max_position is None else max_position + 1
    operation = AIChangeOperation.objects.create(
        change_set=change_set,
        position=position,
        entity_type=handler.entity_type,
        action=action,
        target_id=target,
        source_id=source,
        display_label=prepared.display_label,
        selected=selected,
        status=AIChangeOperation.STATUS_PROPOSED,
        original_snapshot=prepared.original_snapshot,
        proposed_values=prepared.values,
        edited_values={},
        field_schema=prepared.field_schema,
        base_updated_at=prepared.base_updated_at,
        base_digest=prepared.base_digest,
        validation_errors=[],
        validation_warnings=prepared.warnings,
    )
    _invalidate_validation(change_set)
    return operation


def _operation_for_update(change_set: AIChangeSet, operation_id: int) -> AIChangeOperation:
    try:
        return AIChangeOperation.objects.select_for_update().get(id=operation_id, change_set=change_set)
    except AIChangeOperation.DoesNotExist as exc:
        raise ApiError("ai.change_operation_not_found", "L'operazione richiesta non esiste.", status=404) from exc


def _allowed_edit_names(operation: AIChangeOperation) -> set[str]:
    return {
        str(field.get("name"))
        for field in operation.field_schema
        if isinstance(field, dict) and field.get("name") and not field.get("readOnly")
    }


def _reorder_operations(change_set: AIChangeSet, operation: AIChangeOperation, requested_position: int) -> None:
    operations = list(change_set.operations.select_for_update().order_by("position", "id"))
    if operation not in operations:
        return
    requested_position = max(0, min(requested_position, len(operations) - 1))
    operations.remove(operation)
    operations.insert(requested_position, operation)
    for index, entry in enumerate(operations):
        entry.position = index + MAX_OPERATIONS + 1
        entry.save(update_fields=["position", "updated_at"])
    for index, entry in enumerate(operations):
        entry.position = index
        entry.save(update_fields=["position", "updated_at"])


@transaction.atomic
def update_change_operation(
    user,
    change_set_id,
    operation_id: int,
    values: dict[str, Any],
) -> AIChangeOperation:
    change_set = get_change_set_for_user(user, change_set_id, for_update=True)
    _ensure_mutable(change_set)
    operation = _operation_for_update(change_set, operation_id)
    unknown = set(values) - {"editedValues", "selected", "position"}
    if unknown:
        raise ApiError("ai.change_operation_field_unknown", f"Campi operazione non riconosciuti: {', '.join(sorted(unknown))}.")

    if "editedValues" in values:
        patch = values.get("editedValues")
        if not isinstance(patch, dict):
            raise ApiError("ai.change_values_invalid", "I valori modificati devono essere un oggetto JSON.", "editedValues")
        allowed = _allowed_edit_names(operation)
        hidden = set(patch) - allowed
        if hidden:
            raise ApiError(
                "ai.change_field_unknown",
                f"Campi non modificabili: {', '.join(sorted(hidden))}.",
                "editedValues",
            )
        operation.edited_values = {**operation.effective_values, **patch}
        operation.status = AIChangeOperation.STATUS_PROPOSED
        operation.validation_errors = []
        operation.validation_warnings = []
    if "selected" in values:
        selected = values.get("selected")
        if not isinstance(selected, bool):
            raise ApiError("ai.change_selected_invalid", "selected deve essere vero oppure falso.", "selected")
        operation.selected = selected
        operation.status = AIChangeOperation.STATUS_PROPOSED
    operation.save(
        update_fields=[
            "edited_values",
            "selected",
            "status",
            "validation_errors",
            "validation_warnings",
            "updated_at",
        ]
    )
    if "position" in values:
        try:
            requested_position = int(values.get("position"))
        except (TypeError, ValueError) as exc:
            raise ApiError("ai.change_position_invalid", "La posizione non è valida.", "position") from exc
        _reorder_operations(change_set, operation, requested_position)
        operation.refresh_from_db()
    _invalidate_validation(change_set)
    return operation


@transaction.atomic
def delete_change_operation(user, change_set_id, operation_id: int) -> None:
    change_set = get_change_set_for_user(user, change_set_id, for_update=True)
    _ensure_mutable(change_set)
    operation = _operation_for_update(change_set, operation_id)
    operation.delete()
    for index, entry in enumerate(change_set.operations.select_for_update().order_by("position", "id")):
        if entry.position != index:
            entry.position = index
            entry.save(update_fields=["position", "updated_at"])
    _invalidate_validation(change_set)


def _append_operation_error(operation: AIChangeOperation, error: dict[str, Any]) -> None:
    errors = list(operation.validation_errors or [])
    errors.append(error)
    operation.validation_errors = errors
    operation.status = AIChangeOperation.STATUS_INVALID


def _cross_operation_checks(operations: list[AIChangeOperation]) -> None:
    target_groups: dict[tuple[str, int], list[AIChangeOperation]] = defaultdict(list)
    create_names: dict[tuple[str, str], list[AIChangeOperation]] = defaultdict(list)
    for operation in operations:
        if not operation.selected:
            continue
        if operation.action in {AIChangeOperation.ACTION_UPDATE, AIChangeOperation.ACTION_ARCHIVE} and operation.target_id:
            target_groups[(operation.entity_type, operation.target_id)].append(operation)
        if operation.action == AIChangeOperation.ACTION_CREATE:
            name = str(operation.effective_values.get("nome") or "").strip().casefold()
            if name:
                create_names[(operation.entity_type, name)].append(operation)

    for group in target_groups.values():
        if len(group) < 2:
            continue
        for operation in group:
            _append_operation_error(
                operation,
                {
                    "code": "ai.change_target_conflict",
                    "message": "Più operazioni selezionate agiscono sullo stesso record.",
                },
            )
    for group in create_names.values():
        if len(group) < 2:
            continue
        for operation in group:
            _append_operation_error(
                operation,
                {
                    "code": "ai.change_create_name_conflict",
                    "message": "Due creazioni selezionate usano lo stesso nome.",
                    "field": "nome",
                },
            )


def _token_payload(change_set: AIChangeSet, operations: list[AIChangeOperation]) -> dict[str, Any]:
    selected = []
    for operation in operations:
        if not operation.selected:
            continue
        selected.append(
            {
                "id": operation.id,
                "position": operation.position,
                "entityType": operation.entity_type,
                "action": operation.action,
                "targetId": operation.target_id,
                "sourceId": operation.source_id,
                "valuesDigest": canonical_digest(operation.effective_values),
                "baseUpdatedAt": operation.base_updated_at.isoformat() if operation.base_updated_at else None,
                "baseDigest": operation.base_digest,
            }
        )
    return {
        "setId": str(change_set.id),
        "revision": change_set.revision,
        "selected": selected,
    }


@transaction.atomic
def validate_change_set(user, giocatore, change_set_id) -> AIChangeSet:
    change_set = get_change_set_for_user(user, change_set_id, for_update=True)
    _ensure_mutable(change_set)
    operations = list(change_set.operations.select_for_update().order_by("position", "id"))
    selected = [operation for operation in operations if operation.selected]
    if not selected:
        raise ApiError("ai.change_selection_required", "Seleziona almeno un'operazione da convalidare.", status=409)

    for operation in operations:
        operation.validation_errors = []
        operation.validation_warnings = []
        if not operation.selected:
            operation.status = AIChangeOperation.STATUS_SKIPPED
            operation.save(update_fields=["status", "validation_errors", "validation_warnings", "updated_at"])
            continue
        try:
            prepared = _prepare_operation(operation, user, giocatore)
            source_changed = (
                operation.action == AIChangeOperation.ACTION_CREATE
                and operation.source_id
                and operation.base_digest
                and prepared.base_digest
                and operation.base_digest != prepared.base_digest
            )
            if operation.edited_values:
                operation.edited_values = prepared.values
            else:
                operation.proposed_values = prepared.values
            operation.field_schema = prepared.field_schema
            operation.display_label = prepared.display_label
            if operation.action != AIChangeOperation.ACTION_CREATE or not operation.base_digest:
                operation.original_snapshot = prepared.original_snapshot
                operation.base_updated_at = prepared.base_updated_at
                operation.base_digest = prepared.base_digest
            operation.validation_warnings = list(prepared.warnings)
            if source_changed:
                operation.validation_warnings.append(
                    {
                        "code": "ai.change_source_changed",
                        "message": "La sorgente è cambiata dopo la creazione della proposta; i valori materializzati restano invariati.",
                    }
                )
            operation.status = AIChangeOperation.STATUS_VALID
        except ApiError as error:
            operation.status = AIChangeOperation.STATUS_INVALID
            operation.validation_errors = [field_error(error)]
        operation.save(
            update_fields=[
                "proposed_values",
                "edited_values",
                "field_schema",
                "display_label",
                "original_snapshot",
                "base_updated_at",
                "base_digest",
                "validation_errors",
                "validation_warnings",
                "status",
                "updated_at",
            ]
        )

    _cross_operation_checks(operations)
    for operation in operations:
        operation.save(update_fields=["status", "validation_errors", "updated_at"])

    errors = [
        {"operationId": operation.id, **error}
        for operation in operations
        for error in (operation.validation_errors or [])
        if operation.selected
    ]
    warnings = [
        {"operationId": operation.id, **warning}
        for operation in operations
        for warning in (operation.validation_warnings or [])
        if operation.selected
    ]
    change_set.validation_summary = {
        "selectedCount": len(selected),
        "errorCount": len(errors),
        "warningCount": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    change_set.validated_at = timezone.now()
    if errors:
        change_set.status = AIChangeSet.STATUS_DRAFT
        change_set.validation_token = ""
    else:
        change_set.status = AIChangeSet.STATUS_READY
        change_set.validation_token = signing.dumps(
            _token_payload(change_set, operations),
            salt=TOKEN_SALT,
            compress=True,
        )
    change_set.save(
        update_fields=[
            "validation_summary",
            "validated_at",
            "status",
            "validation_token",
            "updated_at",
        ]
    )
    return change_set


def _verify_token(change_set: AIChangeSet, operations: list[AIChangeOperation], token: str) -> None:
    if not token or token != change_set.validation_token:
        raise ApiError("ai.change_token_invalid", "Il token di applicazione non è valido.", "token", 409)
    try:
        signed_payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE_SECONDS)
    except signing.SignatureExpired as exc:
        raise ApiError("ai.change_token_expired", "La convalida è scaduta: convalida di nuovo la proposta.", "token", 409) from exc
    except signing.BadSignature as exc:
        raise ApiError("ai.change_token_invalid", "Il token di applicazione non è valido.", "token", 409) from exc
    if signed_payload != _token_payload(change_set, operations):
        raise ApiError("ai.change_token_stale", "La proposta è cambiata dopo la convalida.", "token", 409)


@transaction.atomic
def apply_change_set(user, giocatore, change_set_id, token: str) -> AIChangeSet:
    change_set = get_change_set_for_user(user, change_set_id, for_update=True)
    if change_set.status != AIChangeSet.STATUS_READY:
        raise ApiError("ai.change_set_not_ready", "La proposta deve essere convalidata prima dell'applicazione.", status=409)
    operations = list(change_set.operations.select_for_update().order_by("position", "id"))
    selected = [operation for operation in operations if operation.selected]
    if not selected:
        raise ApiError("ai.change_selection_required", "Seleziona almeno un'operazione da applicare.", status=409)
    _verify_token(change_set, operations, str(token or ""))

    prepared_by_id: dict[int, PreparedChange] = {}
    lock_order = sorted(
        [operation for operation in selected if operation.action != AIChangeOperation.ACTION_CREATE],
        key=lambda operation: (operation.entity_type, operation.target_id or 0, operation.id),
    )
    for operation in lock_order:
        handler = get_change_handler(operation.entity_type)
        current_snapshot = handler.snapshot(user, giocatore, operation.target_id, for_update=True)
        current_updated_at = current_snapshot.get("updatedAt")
        expected_updated_at = operation.base_updated_at.isoformat() if operation.base_updated_at else None
        if expected_updated_at != current_updated_at or operation.base_digest != current_snapshot.get("digest", ""):
            raise ApiError(
                "ai.change_target_stale",
                f"«{operation.display_label}» è cambiato dopo la convalida. Convalida di nuovo la proposta.",
                status=409,
            )
        prepared_by_id[operation.id] = _prepare_operation(operation, user, giocatore, for_update=False)
    for operation in selected:
        if operation.id not in prepared_by_id:
            prepared_by_id[operation.id] = _prepare_operation(operation, user, giocatore)
        operation.validation_errors = []
        operation.status = AIChangeOperation.STATUS_VALID

    _cross_operation_checks(selected)
    conflict = next((operation for operation in selected if operation.validation_errors), None)
    if conflict is not None:
        raise ApiError(
            conflict.validation_errors[0].get("code", "ai.change_conflict"),
            conflict.validation_errors[0].get("message", "La proposta contiene operazioni incompatibili."),
            conflict.validation_errors[0].get("field"),
            409,
        )

    for operation in selected:
        handler = get_change_handler(operation.entity_type)
        prepared = prepared_by_id[operation.id]
        if operation.action == AIChangeOperation.ACTION_CREATE:
            result = handler.apply_create(user, giocatore, prepared.values)
        elif operation.action == AIChangeOperation.ACTION_UPDATE:
            result = handler.apply_update(user, giocatore, operation.target_id, prepared.values)
        else:
            result = handler.apply_archive(user, giocatore, operation.target_id)
        operation.application_result = result
        operation.status = AIChangeOperation.STATUS_APPLIED
        operation.validation_errors = []
        operation.save(
            update_fields=[
                "application_result",
                "status",
                "validation_errors",
                "updated_at",
            ]
        )
    for operation in operations:
        if not operation.selected:
            operation.status = AIChangeOperation.STATUS_SKIPPED
            operation.save(update_fields=["status", "updated_at"])

    change_set.status = AIChangeSet.STATUS_APPLIED
    change_set.applied_by = user
    change_set.applied_at = timezone.now()
    change_set.validation_token = ""
    change_set.save(
        update_fields=[
            "status",
            "applied_by",
            "applied_at",
            "validation_token",
            "updated_at",
        ]
    )
    return change_set


@transaction.atomic
def discard_change_set(user, change_set_id) -> AIChangeSet:
    change_set = get_change_set_for_user(user, change_set_id, for_update=True)
    _ensure_mutable(change_set)
    change_set.status = AIChangeSet.STATUS_DISCARDED
    change_set.discarded_at = timezone.now()
    change_set.validation_token = ""
    change_set.validated_at = None
    change_set.save(
        update_fields=[
            "status",
            "discarded_at",
            "validation_token",
            "validated_at",
            "updated_at",
        ]
    )
    return change_set


def serialize_user_change_set(user, change_set_id) -> dict[str, Any]:
    return serialize_change_set(get_change_set_for_user(user, change_set_id))


def entity_catalog(user, giocatore) -> list[dict[str, Any]]:
    return change_entity_catalog(user, giocatore)


def search_change_entities(user, giocatore, entity_type: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    handler = get_change_handler(entity_type)
    return handler.search(user, giocatore, query, limit)

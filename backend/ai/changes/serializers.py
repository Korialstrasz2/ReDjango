from __future__ import annotations

from typing import Any

from backend.ai.models import AIChangeOperation, AIChangeSet

from .registry import get_change_handler


def _field_map(operation: AIChangeOperation) -> dict[str, dict[str, Any]]:
    return {
        str(field.get("name")): field
        for field in operation.field_schema
        if isinstance(field, dict) and field.get("name")
    }


def operation_diff(operation: AIChangeOperation) -> list[dict[str, Any]]:
    if operation.action == AIChangeOperation.ACTION_ARCHIVE:
        return []
    fields = _field_map(operation)
    original_values = operation.original_snapshot.get("values", {}) if isinstance(operation.original_snapshot, dict) else {}
    effective_values = operation.effective_values
    result = []
    for name, field in fields.items():
        if operation.action == AIChangeOperation.ACTION_CREATE:
            # A plain create compares against an empty record. A clone compares
            # against the captured source snapshot so the reviewer sees exactly
            # which fields the new record keeps and which ones diverge.
            before = original_values.get(name) if operation.source_id else None
        else:
            before = original_values.get(name)
        after = effective_values.get(name)
        result.append(
            {
                "field": name,
                "label": field.get("label") or name,
                "before": before,
                "after": after,
                "changed": before != after,
            }
        )
    return result


def serialize_change_operation(operation: AIChangeOperation) -> dict[str, Any]:
    try:
        entity_label = get_change_handler(operation.entity_type).label
    except Exception:
        entity_label = operation.entity_type
    intent = "clone" if operation.action == AIChangeOperation.ACTION_CREATE and operation.source_id else operation.action
    return {
        "id": operation.id,
        "position": operation.position,
        "entityType": operation.entity_type,
        "entityLabel": entity_label,
        "action": operation.action,
        "intent": intent,
        "targetId": operation.target_id,
        "sourceId": operation.source_id,
        "displayLabel": operation.display_label,
        "selected": operation.selected,
        "status": operation.status,
        "original": operation.original_snapshot,
        "proposedValues": operation.proposed_values,
        "editedValues": operation.edited_values,
        "effectiveValues": operation.effective_values,
        "fields": operation.field_schema,
        "diff": operation_diff(operation),
        "errors": operation.validation_errors,
        "warnings": operation.validation_warnings,
        "result": operation.application_result,
        "baseUpdatedAt": operation.base_updated_at.isoformat() if operation.base_updated_at else None,
        "baseDigest": operation.base_digest,
    }


def serialize_change_set(change_set: AIChangeSet, *, include_operations: bool = True) -> dict[str, Any]:
    editable = change_set.status in AIChangeSet.EDITABLE_STATUSES
    payload = {
        "id": str(change_set.id),
        "title": change_set.title,
        "status": change_set.status,
        "revision": change_set.revision,
        "requestText": change_set.request_text,
        "context": change_set.context,
        "conversationId": change_set.conversation_id,
        "agentId": change_set.agent_id,
        "canEdit": editable,
        "canValidate": editable,
        "canApply": change_set.status == AIChangeSet.STATUS_READY and bool(change_set.validation_token),
        "canDiscard": editable,
        "validation": {
            "token": change_set.validation_token,
            "validatedAt": change_set.validated_at.isoformat() if change_set.validated_at else None,
            "summary": change_set.validation_summary,
            "errors": change_set.validation_summary.get("errors", []) if isinstance(change_set.validation_summary, dict) else [],
            "warnings": change_set.validation_summary.get("warnings", []) if isinstance(change_set.validation_summary, dict) else [],
        },
        "appliedBy": change_set.applied_by_id,
        "appliedAt": change_set.applied_at.isoformat() if change_set.applied_at else None,
        "discardedAt": change_set.discarded_at.isoformat() if change_set.discarded_at else None,
        "expiresAt": change_set.expires_at.isoformat() if change_set.expires_at else None,
        "createdAt": change_set.created_at.isoformat() if change_set.created_at else None,
        "updatedAt": change_set.updated_at.isoformat() if change_set.updated_at else None,
    }
    if include_operations:
        payload["operations"] = [
            serialize_change_operation(operation)
            for operation in change_set.operations.all().order_by("position", "id")
        ]
    return payload

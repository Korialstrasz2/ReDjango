from __future__ import annotations

from django.views.decorators.http import require_http_methods

from backend.core.api import ApiError, api_error_response, api_response, request_payload
from backend.core.security import get_or_create_giocatore_for_user
from backend.core.views import get_authenticated_user

from .changes.serializers import serialize_change_set
from .changes.services import (
    add_change_operation,
    apply_change_set,
    create_change_set,
    delete_change_operation,
    discard_change_set,
    entity_catalog,
    get_change_set_for_user,
    list_change_sets_for_user,
    search_change_entities,
    update_change_operation,
    update_change_set,
    validate_change_set,
)


def _context(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    return user, giocatore


@require_http_methods(["GET", "POST"])
def ai_change_sets(request):
    user, giocatore = _context(request)
    try:
        if request.method == "GET":
            return api_response(
                request,
                {
                    "changeSets": [
                        serialize_change_set(change_set, include_operations=False)
                        for change_set in list_change_sets_for_user(user)
                    ]
                },
            )
        payload = request_payload(request)
        change_set = create_change_set(
            user,
            giocatore,
            title=payload.get("title", ""),
            request_text=payload.get("requestText", ""),
            context=payload.get("context"),
        )
        return api_response(
            request,
            {"changeSet": serialize_change_set(change_set)},
            status=201,
            events=[{"type": "ai.change_set_created", "message": "Proposta creata."}],
        )
    except ApiError as error:
        return api_error_response(request, error)


@require_http_methods(["GET", "PATCH", "DELETE"])
def ai_change_set_detail(request, change_set_id):
    user, _giocatore = _context(request)
    try:
        if request.method == "GET":
            change_set = get_change_set_for_user(user, change_set_id)
        elif request.method == "PATCH":
            change_set = update_change_set(user, change_set_id, request_payload(request))
        else:
            change_set = discard_change_set(user, change_set_id)
        return api_response(request, {"changeSet": serialize_change_set(change_set)})
    except ApiError as error:
        return api_error_response(request, error)


@require_http_methods(["POST"])
def ai_change_operations(request, change_set_id):
    user, giocatore = _context(request)
    try:
        payload = request_payload(request)
        operation = add_change_operation(
            user,
            giocatore,
            change_set_id,
            entity_type=payload.get("entityType", ""),
            action=payload.get("action", ""),
            values=payload.get("values", {}),
            target_id=payload.get("targetId"),
            source_id=payload.get("sourceId"),
            selected=payload.get("selected", True),
        )
        change_set = get_change_set_for_user(user, change_set_id)
        return api_response(
            request,
            {"changeSet": serialize_change_set(change_set), "operationId": operation.id},
            status=201,
            events=[{"type": "ai.change_operation_added", "message": "Operazione aggiunta alla proposta."}],
        )
    except ApiError as error:
        return api_error_response(request, error)


@require_http_methods(["PATCH", "DELETE"])
def ai_change_operation_detail(request, change_set_id, operation_id):
    user, _giocatore = _context(request)
    try:
        if request.method == "PATCH":
            update_change_operation(user, change_set_id, operation_id, request_payload(request))
        else:
            delete_change_operation(user, change_set_id, operation_id)
        change_set = get_change_set_for_user(user, change_set_id)
        return api_response(request, {"changeSet": serialize_change_set(change_set)})
    except ApiError as error:
        return api_error_response(request, error)


@require_http_methods(["POST"])
def ai_change_set_validate(request, change_set_id):
    user, giocatore = _context(request)
    try:
        change_set = validate_change_set(user, giocatore, change_set_id)
        return api_response(
            request,
            {"changeSet": serialize_change_set(change_set)},
            events=[{"type": "ai.change_set_validated", "message": "Proposta convalidata."}],
        )
    except ApiError as error:
        return api_error_response(request, error)


@require_http_methods(["POST"])
def ai_change_set_apply(request, change_set_id):
    user, giocatore = _context(request)
    try:
        payload = request_payload(request)
        change_set = apply_change_set(user, giocatore, change_set_id, payload.get("token", ""))
        return api_response(
            request,
            {"changeSet": serialize_change_set(change_set)},
            events=[{"type": "ai.change_set_applied", "message": "Proposta applicata."}],
        )
    except ApiError as error:
        return api_error_response(request, error)


@require_http_methods(["GET"])
def ai_change_entities(request):
    user, giocatore = _context(request)
    try:
        return api_response(request, {"entities": entity_catalog(user, giocatore)})
    except ApiError as error:
        return api_error_response(request, error)


@require_http_methods(["GET"])
def ai_change_entity_search(request, entity_type):
    user, giocatore = _context(request)
    try:
        raw_limit = request.GET.get("limit", "10")
        try:
            limit = int(raw_limit)
        except ValueError as exc:
            raise ApiError("ai.change_search_limit_invalid", "Il limite di ricerca non è valido.", "limit") from exc
        query = str(request.GET.get("q", ""))[:160]
        results = search_change_entities(user, giocatore, entity_type, query, limit)
        return api_response(request, {"results": results})
    except ApiError as error:
        return api_error_response(request, error)

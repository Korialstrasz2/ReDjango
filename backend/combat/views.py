from __future__ import annotations

import asyncio
import json
import time

from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from django.db import close_old_connections
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET, require_POST

from backend.core.api import ApiError
from backend.core.security import get_or_create_giocatore_for_user
from backend.core.views import get_authenticated_user

from .models import CombatEvent
from .selectors import combat_workspace_payload
from .services import (
    apply_direct_damage,
    apply_enemy_effect,
    activate_character,
    calculate_paths,
    commit_plan_action,
    create_map_snapshot,
    create_map_type,
    create_or_update_map,
    create_plan_action,
    deactivate_participant,
    delete_plan_action,
    duplicate_map,
    generate_unit,
    import_character,
    ensure_viewer_character,
    move_participant,
    paint_hexes,
    resolve_attack,
    reload_active_weapon,
    remove_quiver_item,
    restore_map_snapshot,
    set_active_character,
    switch_combat_primary_weapon,
    take_control,
    toggle_modifier,
    update_action_settings,
    update_combat_resource,
    update_fog,
    update_hex,
)

EVENT_STREAM_POLL_SECONDS = 1.0
EVENT_STREAM_KEEPALIVE_SECONDS = 15.0
EVENT_STREAM_MAX_SECONDS = 300.0


def _request_id(request, fallback=""):
    return request.headers.get("X-ReDjango-Request-Id", "") or fallback


def _ok(request, data, *, request_id="", message="", event_type="combat.updated"):
    return JsonResponse({
        "ok": True,
        "requestId": _request_id(request, request_id),
        "data": data,
        "events": [{"type": event_type, "message": message}] if message else [],
        "warnings": [],
        "errors": [],
    })


def _error(request, error, request_id=""):
    return JsonResponse({
        "ok": False,
        "requestId": _request_id(request, request_id),
        "data": {},
        "events": [],
        "warnings": [],
        "errors": [{"code": error.code, "message": error.message, **({"field": error.field} if error.field else {})}],
    }, status=error.status)


def _identity(request):
    user = get_authenticated_user(request)
    return user, get_or_create_giocatore_for_user(user)


def _body(request):
    try:
        envelope = json.loads(request.body or "{}")
    except json.JSONDecodeError as error:
        raise ApiError("combat.invalid_json", "Richiesta JSON non valida.") from error
    return envelope, envelope.get("payload") or {}


@require_GET
def workspace(request: HttpRequest):
    user, giocatore = _identity(request)
    map_id = request.GET.get("map_id")
    try:
        return _ok(request, combat_workspace_payload(user, giocatore, int(map_id) if map_id else None))
    except ObjectDoesNotExist:
        return _error(request, ApiError("combat.map_not_found", "Mappa non trovata.", status=404))


@require_POST
def actions(request: HttpRequest):
    user, giocatore = _identity(request)
    request_id = ""
    try:
        envelope, payload = _body(request)
        action = str(envelope.get("action") or "")
        request_id = str(envelope.get("requestId") or "")
        selected_map_id = payload.get("mapId")
        message = "Stato del combattimento aggiornato."
        extra = {}
        if action == "maps.save":
            map_obj = create_or_update_map(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Mappa salvata."
        elif action == "maps.createType":
            map_type = create_map_type(user, giocatore, payload)
            message = f"Tipo mappa {map_type.name} creato."
        elif action == "combat.importCharacter":
            character = import_character(user, giocatore, payload)
            message = f"{character.nome} importato come copia del personaggio."
        elif action == "combat.generateUnit":
            character = generate_unit(user, giocatore, payload)
            message = f"{character.nome} generato e aggiunto alla mappa."
        elif action == "combat.ensureViewerCharacter":
            map_obj, added = ensure_viewer_character(giocatore, payload)
            selected_map_id = map_obj.id
            message = "Il personaggio selezionato è ora attivo sulla mappa." if added else ""
        elif action == "combat.activateCharacter":
            map_obj, added = activate_character(user, giocatore, payload)
            selected_map_id = map_obj.id
            message = "Personaggio aggiunto alla mappa." if added else "Il personaggio è già attivo."
        elif action == "combat.moveParticipant":
            map_obj = move_participant(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Personaggio spostato mantenendo la sagoma."
        elif action == "combat.selectCharacter":
            map_obj = set_active_character(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Personaggio attivo aggiornato."
        elif action == "combat.deactivateParticipant":
            map_obj = deactivate_participant(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Personaggio rimosso dalla mappa; la copia è ancora gestibile."
        elif action == "maps.updateHex":
            map_obj = update_hex(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Esagono e terreno salvati."
        elif action == "maps.paintHexes":
            map_obj = paint_hexes(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Pittura della mappa aggiornata."
        elif action == "maps.updateFog":
            map_obj = update_fog(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Nebbia di guerra aggiornata."
        elif action == "maps.createSnapshot":
            map_obj = create_map_snapshot(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Backup della mappa creato."
        elif action == "maps.restoreSnapshot":
            map_obj = restore_map_snapshot(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Backup della mappa ripristinato."
        elif action == "maps.duplicate":
            map_obj = duplicate_map(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Mappa duplicata."
        elif action == "maps.calculatePaths":
            extra["paths"] = calculate_paths(payload)
            message = "Percorsi calcolati."
        elif action == "combat.toggleModifier":
            map_obj = toggle_modifier(payload)
            selected_map_id, message = map_obj.id, "Modificatore aggiornato."
        elif action == "combat.resolveAttack":
            map_obj, result = resolve_attack(user, giocatore, payload)
            selected_map_id, extra["attackResult"] = map_obj.id, result
            message = "Attacco applicato." if result["applied"] else ""
        elif action == "combat.applyDirectDamage":
            map_obj, result = apply_direct_damage(user, giocatore, payload)
            selected_map_id, extra["directDamageResult"] = map_obj.id, result
            message = f"Applicati {result['finalDamage']} danni {result['damageType']}."
        elif action == "equipment.switchPrimaryWeapon":
            map_obj = switch_combat_primary_weapon(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Arma primaria cambiata senza spendere Punti Azione."
        elif action == "combat.reloadWeapon":
            map_obj, reload_result = reload_active_weapon(user, giocatore, payload)
            selected_map_id, extra["reloadResult"] = map_obj.id, reload_result
            message = "Arma ricaricata."
        elif action == "combat.removeQuiverItem":
            map_obj = remove_quiver_item(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Proiettile rimosso dalla faretra."
        elif action == "combat.applyEnemyEffect":
            map_obj = apply_enemy_effect(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Effetto applicato al bersaglio."
        elif action == "combat.takeControl":
            map_obj = take_control(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Controllo del personaggio aggiornato."
        elif action == "combat.updateResource":
            map_obj = update_combat_resource(user, giocatore, payload)
            selected_map_id, message = map_obj.id, "Risorsa del combattente aggiornata."
        elif action == "combat.updateActionSettings":
            # Configurazione personale: nessun messaggio, si salva a ogni clic sui tag.
            map_obj = update_action_settings(user, giocatore, payload)
            selected_map_id, message = map_obj.id, ""
        elif action == "combat.planAction":
            map_obj = create_plan_action(payload)
            selected_map_id, message = map_obj.id, "Azione aggiunta al piano."
        elif action == "combat.commitPlannedAction":
            map_obj = commit_plan_action(payload)
            selected_map_id, message = map_obj.id, "Costi dell'azione pagati."
        elif action == "combat.deletePlannedAction":
            map_obj = delete_plan_action(payload)
            selected_map_id, message = map_obj.id, "Azione rimossa dal piano."
        else:
            raise ApiError("combat.unknown_action", "Azione di combattimento non riconosciuta.", "action", 404)
        data = combat_workspace_payload(user, giocatore, selected_map_id)
        data.update(extra)
        return _ok(request, data, request_id=request_id, message=message, event_type=action)
    except ApiError as error:
        return _error(request, error, request_id)
    except ObjectDoesNotExist:
        return _error(request, ApiError("combat.resource_not_found", "La risorsa richiesta non esiste.", status=404), request_id)
    except (KeyError, TypeError, ValueError) as error:
        return _error(request, ApiError("combat.invalid_payload", f"Dati non validi: {error}"), request_id)


@require_GET
def event_stream(request: HttpRequest, map_id: int):
    _identity(request)
    try:
        # EventSource keeps the original query string when it reconnects and
        # reports its newer cursor in Last-Event-ID. Prefer that header so a
        # reconnect never replays the whole page session.
        cursor = int(request.headers.get("Last-Event-ID") or request.GET.get("after") or 0)
    except ValueError:
        cursor = 0

    def pending_events(after: int):
        close_old_connections()
        try:
            return list(
                CombatEvent.objects
                .filter(map_id=map_id, id__gt=after)
                .order_by("id")
                .values("id", "event_type", "message", "payload")[:100]
            )
        finally:
            close_old_connections()

    async def stream():
        nonlocal cursor
        deadline = time.monotonic() + EVENT_STREAM_MAX_SECONDS
        next_keepalive = time.monotonic() + EVENT_STREAM_KEEPALIVE_SECONDS
        yield "retry: 2000\n\n"
        while time.monotonic() < deadline:
            rows = await sync_to_async(pending_events, thread_sensitive=True)(cursor)
            if rows:
                for row in rows:
                    cursor = row["id"]
                    payload = json.dumps({
                        "id": row["id"],
                        "type": row["event_type"],
                        "message": row["message"],
                        "payload": row["payload"],
                    }, ensure_ascii=False)
                    yield f"id: {row['id']}\nevent: combat\ndata: {payload}\n\n"
                next_keepalive = time.monotonic() + EVENT_STREAM_KEEPALIVE_SECONDS
            elif time.monotonic() >= next_keepalive:
                yield ": keepalive\n\n"
                next_keepalive = time.monotonic() + EVENT_STREAM_KEEPALIVE_SECONDS
            await asyncio.sleep(EVENT_STREAM_POLL_SECONDS)

    response = StreamingHttpResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response

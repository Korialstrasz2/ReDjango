"""Coda locale, cancellazione e conservazione breve delle conversazioni AI."""

from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from backend.core.api import ApiError
from backend.core.models import Giocatore
from backend.media_library.models import UploadedImage
from backend.media_library.selectors import serialize_uploaded_image

from .agent import RunBudget
from .models import AIConversation, AIExecutionRun, AIProvider
from .selectors import serialize_conversation
from .services import (
    _resolve_provider,
    ask_assistant,
    generate_image,
    require_ai_manager,
    resolve_assistant_agent,
    sanitize_history,
)


MAXIMUM_CONVERSATIONS_PER_USER = 3
MAXIMUM_RUN_SECONDS = 120
MAXIMUM_RUN_TOKENS = 64000
MAXIMUM_RUN_TOOL_CALLS = 24
MAXIMUM_TRANSCRIPT_BUBBLES = 80

logger = logging.getLogger("redjango.ai.runs")
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="redjango-ai")


def _active_run_for(user):
    return AIExecutionRun.objects.filter(
        user=user,
        status__in=[AIExecutionRun.STATUS_QUEUED, AIExecutionRun.STATUS_RUNNING],
        archived_at__isnull=True,
    ).first()


def _expire_stale_runs(user) -> None:
    """Un riavvio non deve lasciare l'account bloccato da un run fantasma."""

    now = timezone.now()
    stale = AIExecutionRun.objects.filter(user=user, status=AIExecutionRun.STATUS_RUNNING, updated_at__lt=now - timedelta(seconds=150))
    for run in stale:
        run.status = AIExecutionRun.STATUS_FAILED
        run.progress = "Interrotta dal riavvio del server"
        run.error = {"code": "ai.run_interrupted", "message": "L'esecuzione è stata interrotta. Riprova."}
        run.completed_at = now
        run.save(update_fields=["status", "progress", "error", "completed_at", "updated_at"])
        _discard_empty_conversation(run)
    queued = AIExecutionRun.objects.filter(user=user, status=AIExecutionRun.STATUS_QUEUED, updated_at__lt=now - timedelta(minutes=30))
    for run in queued:
        run.status = AIExecutionRun.STATUS_FAILED
        run.progress = "Coda interrotta dal riavvio del server"
        run.error = {"code": "ai.queue_interrupted", "message": "La richiesta in coda è stata interrotta. Riprova."}
        run.completed_at = now
        run.save(update_fields=["status", "progress", "error", "completed_at", "updated_at"])
        _discard_empty_conversation(run)


def _ensure_no_active_run(user) -> None:
    _expire_stale_runs(user)
    if _active_run_for(user):
        raise ApiError("ai.run_active", "Hai già un'esecuzione AI in corso. Attendi o annullala.", status=409)


def active_execution_run_for(user) -> AIExecutionRun | None:
    _expire_stale_runs(user)
    return _active_run_for(user)


def _prune_conversations(user, keep_id: int) -> None:
    kept = list(
        AIConversation.objects.filter(user=user, archived_at__isnull=True)
        .order_by("-updated_at", "-id")
        .values_list("id", flat=True)[:MAXIMUM_CONVERSATIONS_PER_USER]
    )
    if keep_id not in kept:
        kept = [keep_id, *kept[: MAXIMUM_CONVERSATIONS_PER_USER - 1]]
    AIConversation.objects.filter(user=user, archived_at__isnull=True).exclude(id__in=kept).delete()


def _conversation_for(user, payload: dict[str, Any], agent) -> AIConversation:
    conversation_id = payload.get("conversationId")
    if conversation_id not in (None, ""):
        try:
            return AIConversation.objects.get(pk=int(conversation_id), user=user, archived_at__isnull=True)
        except (TypeError, ValueError, AIConversation.DoesNotExist) as exc:
            raise ApiError("ai.conversation_not_found", "Conversazione AI non trovata.", "conversationId", 404) from exc
    title = str(payload.get("message") or "").strip().replace("\n", " ")[:80] or "Nuova conversazione"
    conversation = AIConversation.objects.create(user=user, agent=agent, title=title)
    _prune_conversations(user, conversation.id)
    return conversation


def _cleanup_runs(user) -> None:
    cutoff = timezone.now() - timedelta(days=1)
    AIExecutionRun.objects.filter(
        user=user,
        status__in=[AIExecutionRun.STATUS_COMPLETED, AIExecutionRun.STATUS_FAILED, AIExecutionRun.STATUS_CANCELLED],
        created_at__lt=cutoff,
    ).delete()


def _discard_empty_conversation(run: AIExecutionRun) -> None:
    if run.conversation_id:
        AIConversation.objects.filter(pk=run.conversation_id, transcript=[]).delete()


def _submit(run: AIExecutionRun) -> None:
    _executor.submit(_execute_run, str(run.id))


def start_chat_run(user, giocatore: Giocatore, payload: dict[str, Any]) -> AIExecutionRun:
    message = str(payload.get("message") or "").strip()
    if not message:
        raise ApiError("ai.message_required", "Scrivi una domanda per l'assistente.", "message")
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=user.pk)
            _ensure_no_active_run(user)
            agent, provider = resolve_assistant_agent(user, giocatore, payload.get("agentId"))
            history = sanitize_history(payload.get("history"))
            conversation = _conversation_for(user, payload, agent)
            _cleanup_runs(user)
            run = AIExecutionRun.objects.create(
                user=user,
                conversation=conversation,
                agent=agent,
                provider=provider,
                kind=AIExecutionRun.KIND_CHAT,
                progress="In coda…",
                request_payload={"message": message[:8000], "history": history, "agentId": agent.id},
            )
            transaction.on_commit(lambda: _submit(run))
    except IntegrityError as error:
        raise ApiError("ai.run_active", "Hai già un'esecuzione AI in corso. Attendi o annullala.", status=409) from error
    return run


def start_image_run(user, giocatore: Giocatore, payload: dict[str, Any]) -> AIExecutionRun:
    require_ai_manager(user, giocatore)
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ApiError("ai.prompt_required", "Descrivi l'immagine da generare.", "prompt")
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=user.pk)
            _ensure_no_active_run(user)
            provider = _resolve_provider(AIProvider.PURPOSE_IMAGE, payload.get("providerId"))
            _cleanup_runs(user)
            safe_payload = dict(payload)
            safe_payload["prompt"] = prompt[:2000]
            run = AIExecutionRun.objects.create(
                user=user,
                provider=provider,
                kind=AIExecutionRun.KIND_IMAGE,
                progress="In coda…",
                request_payload=safe_payload,
            )
            transaction.on_commit(lambda: _submit(run))
    except IntegrityError as error:
        raise ApiError("ai.run_active", "Hai già un'esecuzione AI in corso. Attendi o annullala.", status=409) from error
    return run


def _cancel_requested(run_id: str) -> bool:
    return AIExecutionRun.objects.filter(pk=run_id, cancel_requested=True).exists()


def _progress(run_id: str, message: str) -> None:
    AIExecutionRun.objects.filter(
        pk=run_id,
        status=AIExecutionRun.STATUS_RUNNING,
    ).update(progress=message, updated_at=timezone.now())


def _complete_chat(run: AIExecutionRun, result: dict[str, Any]) -> None:
    conversation = AIConversation.objects.get(pk=run.conversation_id, user=run.user)
    transcript = list(conversation.transcript if isinstance(conversation.transcript, list) else [])
    transcript.extend(
        [
            {"id": uuid.uuid4().hex, "role": "user", "text": run.request_payload.get("message", ""), "tools": []},
            {"id": uuid.uuid4().hex, "role": "assistant", "text": result.get("reply", ""), "tools": result.get("toolTrace", [])},
        ]
    )
    conversation.agent = run.agent
    conversation.history = result.get("history", [])
    conversation.transcript = transcript[-MAXIMUM_TRANSCRIPT_BUBBLES:]
    conversation.save(update_fields=["agent", "history", "transcript", "updated_at"])
    _prune_conversations(run.user, conversation.id)


def _execute_run(run_id: str) -> None:
    close_old_connections()
    try:
        run = AIExecutionRun.objects.select_related("user", "agent", "provider", "conversation").get(pk=run_id)
        if run.cancel_requested or run.status == AIExecutionRun.STATUS_CANCELLED:
            return
        run.status = AIExecutionRun.STATUS_RUNNING
        run.progress = "Preparazione della richiesta…"
        run.started_at = timezone.now()
        run.save(update_fields=["status", "progress", "started_at", "updated_at"])
        giocatore = Giocatore.objects.select_related("active_campaign").get(user=run.user)
        budget = RunBudget(
            maximum_seconds=MAXIMUM_RUN_SECONDS,
            maximum_tokens=MAXIMUM_RUN_TOKENS,
            maximum_tool_calls=MAXIMUM_RUN_TOOL_CALLS,
            cancel_check=lambda: _cancel_requested(run_id),
        )
        progress = lambda message: _progress(run_id, message)
        if run.kind == AIExecutionRun.KIND_CHAT:
            result = ask_assistant(run.user, giocatore, run.request_payload, budget=budget, progress=progress)
            _complete_chat(run, result)
        else:
            asset = generate_image(run.user, giocatore, run.request_payload, budget=budget, progress=progress)
            result = {"assetId": asset.id}
        run.result = result
        run.status = AIExecutionRun.STATUS_COMPLETED
        run.progress = "Completata"
        usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
        run.input_tokens = int(usage.get("inputTokens") or 0)
        run.output_tokens = int(usage.get("outputTokens") or 0)
        run.tool_calls = len(result.get("toolTrace") or [])
        run.completed_at = timezone.now()
        run.save(
            update_fields=[
                "result", "status", "progress", "input_tokens", "output_tokens", "tool_calls", "completed_at", "updated_at",
            ]
        )
    except ApiError as error:
        status = AIExecutionRun.STATUS_CANCELLED if error.code == "ai.run_cancelled" else AIExecutionRun.STATUS_FAILED
        AIExecutionRun.objects.filter(pk=run_id).update(
            status=status,
            progress="Annullata" if status == AIExecutionRun.STATUS_CANCELLED else "Non riuscita",
            error=error.as_dict(),
            completed_at=timezone.now(),
            updated_at=timezone.now(),
        )
        if "run" in locals():
            _discard_empty_conversation(run)
    except Exception:
        logger.exception("ai_background_run_failed id=%s", run_id)
        AIExecutionRun.objects.filter(pk=run_id).update(
            status=AIExecutionRun.STATUS_FAILED,
            progress="Non riuscita",
            error={"code": "ai.run_failed", "message": "L'esecuzione AI non è riuscita. Riprova."},
            completed_at=timezone.now(),
            updated_at=timezone.now(),
        )
        if "run" in locals():
            _discard_empty_conversation(run)
    finally:
        close_old_connections()


def execution_run_for(user, run_id: object) -> AIExecutionRun:
    try:
        return AIExecutionRun.objects.select_related("conversation", "agent", "provider").get(pk=run_id, user=user)
    except (ValueError, AIExecutionRun.DoesNotExist) as exc:
        raise ApiError("ai.run_not_found", "Esecuzione AI non trovata.", status=404) from exc


def cancel_execution_run(user, run_id: object) -> AIExecutionRun:
    run = execution_run_for(user, run_id)
    if run.status in {AIExecutionRun.STATUS_COMPLETED, AIExecutionRun.STATUS_FAILED, AIExecutionRun.STATUS_CANCELLED}:
        return run
    run.cancel_requested = True
    run.progress = "Annullamento richiesto…"
    fields = ["cancel_requested", "progress", "updated_at"]
    if run.status == AIExecutionRun.STATUS_QUEUED:
        run.status = AIExecutionRun.STATUS_CANCELLED
        run.completed_at = timezone.now()
        fields.extend(["status", "completed_at"])
    run.save(update_fields=fields)
    if run.status == AIExecutionRun.STATUS_CANCELLED:
        _discard_empty_conversation(run)
        run.conversation = None
        run.conversation_id = None
    return run


def serialize_execution_run(run: AIExecutionRun, user) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if run.status == AIExecutionRun.STATUS_COMPLETED:
        if run.kind == AIExecutionRun.KIND_IMAGE:
            asset = UploadedImage.objects.filter(pk=run.result.get("assetId")).first()
            if asset:
                result = {"asset": serialize_uploaded_image(asset, user)}
        else:
            result = run.result
    return {
        "id": str(run.id),
        "kind": run.kind,
        "status": run.status,
        "progress": run.progress,
        "cancelRequested": run.cancel_requested,
        "request": {
            "message": str(run.request_payload.get("message") or "") if run.kind == AIExecutionRun.KIND_CHAT else "",
            "prompt": str(run.request_payload.get("prompt") or "") if run.kind == AIExecutionRun.KIND_IMAGE else "",
        },
        "result": result,
        "error": run.error if isinstance(run.error, dict) else {},
        "conversation": serialize_conversation(run.conversation) if run.conversation_id and run.conversation else None,
        "budgets": {
            "maximumSeconds": MAXIMUM_RUN_SECONDS,
            "maximumTokens": MAXIMUM_RUN_TOKENS,
            "maximumToolCalls": MAXIMUM_RUN_TOOL_CALLS,
        },
    }

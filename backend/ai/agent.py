"""Runtime agentico provider-neutral, vincolato da un profilo configurabile."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from backend.core.api import ApiError
from backend.core.models import Giocatore

from .providers import chat_provider_for
from .tools import execute_tool, tool_definitions


MAXIMUM_ITERATIONS = 6
MAXIMUM_HISTORY_MESSAGES = 40
logger = logging.getLogger("redjango.ai.runs")

SYSTEM_PROMPT = """Sei un assistente di ReDjango, la postazione di gioco di una campagna di ruolo ambientata nel mondo di The Elder Scrolls.

Obiettivo: rispondi in italiano con informazioni corrette, utili e verificabili sulla campagna.

Vincoli: per i dati della campagna consulta gli strumenti pertinenti; il database è la fonte di verità. Non inventare dati mancanti.

Permessi: puoi usare soltanto gli strumenti esposti in questo turno. Sono di sola lettura e applicano i permessi dell'utente.

Risultati vuoti: distingui sempre `nessun_dato` da `filtro_senza_risultati`. Se un filtro non produce risultati, riprova una volta senza filtro o con un termine più ampio. Non dedurre mai che il Master non abbia inserito dati, che il gruppo non abbia incontrato qualcosa o altre spiegazioni non presenti nel risultato.

Risposte fondate: riporta i valori e le etichette disponibili nel risultato. Se affermi che qualcosa non esiste, fallo soltanto quando lo strumento restituisce esplicitamente `nessun_dato`.

Stop: appena hai prove sufficienti, rispondi senza chiamate ulteriori. Se mancano dati necessari, dichiaralo.

Non puoi modificare il database. Se ti viene chiesto di cambiare qualcosa, spiega dove farlo nell'interfaccia."""


def _trim(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(history) <= MAXIMUM_HISTORY_MESSAGES:
        return history
    trimmed = history[-MAXIMUM_HISTORY_MESSAGES:]
    while trimmed and trimmed[0].get("role") == "tool":
        trimmed = trimmed[1:]
    return trimmed


def _system_prompt(profile) -> str:
    instructions = str(getattr(profile, "instructions", "") or "").strip()
    return SYSTEM_PROMPT + (f"\n\nCompetenza specifica dell'agente:\n{instructions}" if instructions else "")


def run_agent(provider, history: list[dict[str, Any]], user, giocatore: Giocatore, profile=None) -> dict[str, Any]:
    """Esegue un turno completo secondo provider, strumenti e limiti del profilo."""

    client = chat_provider_for(provider)
    allowed_tools = list(getattr(profile, "allowed_tools", []) or []) if profile is not None else None
    tools = tool_definitions(user, giocatore, allowed_tools)
    maximum_iterations = max(1, min(int(getattr(profile, "max_iterations", MAXIMUM_ITERATIONS)), 12))
    conversation = _trim(list(history))
    trace: list[dict[str, Any]] = []
    usage = {"inputTokens": 0, "outputTokens": 0}
    run_id = uuid.uuid4().hex[:12]
    started = time.monotonic()

    for iteration in range(maximum_iterations):
        try:
            turn = client.complete(system=_system_prompt(profile), history=conversation, tools=tools)
        except Exception as error:
            logger.warning(
                "agent_run id=%s profile=%s provider=%s model=%s role=%s iterations=%s duration_ms=%s status=provider_error error=%s",
                run_id,
                getattr(profile, "slug", "legacy"),
                provider.slug,
                provider.model,
                giocatore.role,
                iteration + 1,
                round((time.monotonic() - started) * 1000),
                type(error).__name__,
            )
            raise
        usage["inputTokens"] += int(turn.usage.get("inputTokens") or 0)
        usage["outputTokens"] += int(turn.usage.get("outputTokens") or 0)
        conversation.append(
            {
                "role": "assistant",
                "content": turn.text,
                "toolCalls": [{"id": call.id, "name": call.name, "arguments": call.arguments} for call in turn.tool_calls],
                "raw": turn.raw,
            }
        )

        if not turn.tool_calls:
            result = {
                "reply": turn.text,
                "history": [{key: value for key, value in entry.items() if key != "raw"} for entry in conversation],
                "toolTrace": trace,
                "usage": usage,
                "stopReason": turn.stop_reason,
                "runId": run_id,
            }
            logger.info(
                "agent_run id=%s profile=%s provider=%s model=%s role=%s tools=%s iterations=%s input_tokens=%s output_tokens=%s duration_ms=%s status=ok",
                run_id,
                getattr(profile, "slug", "legacy"),
                provider.slug,
                provider.model,
                giocatore.role,
                ",".join(item["name"] for item in trace) or "-",
                iteration + 1,
                usage["inputTokens"],
                usage["outputTokens"],
                round((time.monotonic() - started) * 1000),
            )
            return result

        for call in turn.tool_calls:
            result, is_error = execute_tool(
                call.name,
                call.arguments,
                user,
                giocatore,
                allowed_names=allowed_tools,
            )
            trace.append({"name": call.name, "arguments": call.arguments, "isError": is_error})
            conversation.append(
                {
                    "role": "tool",
                    "toolCallId": call.id,
                    "name": call.name,
                    "content": result,
                    "isError": is_error,
                }
            )

    logger.warning(
        "agent_run id=%s profile=%s provider=%s role=%s tools=%s duration_ms=%s status=iteration_limit",
        run_id,
        getattr(profile, "slug", "legacy"),
        provider.slug,
        giocatore.role,
        ",".join(item["name"] for item in trace) or "-",
        round((time.monotonic() - started) * 1000),
    )
    raise ApiError(
        "ai.iteration_limit",
        "L'assistente ha consultato troppi strumenti senza concludere. Riformula la domanda in modo più specifico.",
        status=409,
    )

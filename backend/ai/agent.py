"""Il ciclo dell'agente.

Chiedi al modello, esegui gli strumenti che chiede, rimanda i risultati, ripeti
finché smette di chiederne. È tutto qui: con strumenti che sono già i selettori del
progetto, un framework di agenti aggiungerebbe una dipendenza e un'astrazione in più
senza togliere una riga di questo file.

Il ciclo è limitato in modo esplicito — un modello che continuasse a chiamare
strumenti non può far girare il server all'infinito.
"""

from __future__ import annotations

from typing import Any

from backend.core.api import ApiError
from backend.core.models import Giocatore

from .providers import chat_provider_for
from .tools import execute_tool, tool_definitions


MAXIMUM_ITERATIONS = 6
MAXIMUM_HISTORY_MESSAGES = 40

SYSTEM_PROMPT = """Sei l'assistente di ReDjango, la postazione di gioco di una campagna di ruolo ambientata nel mondo di The Elder Scrolls.

Rispondi sempre in italiano, in modo diretto e conciso.

Per qualunque domanda sui dati della campagna — oggetti, personaggi, abilità, competenze, fazioni, negozi, regole — consulta prima gli strumenti invece di rispondere a memoria: il database è la fonte di verità e le tue conoscenze generali non contengono questa campagna.

Gli strumenti mostrano soltanto ciò che chi ti sta parlando è già autorizzato a vedere. Se uno strumento non restituisce qualcosa, dì che non risulta accessibile: non dedurlo, non inventarlo e non lasciare intendere che esista dell'altro.

Non hai strumenti di scrittura: puoi leggere e spiegare, non modificare la campagna. Se ti viene chiesto di cambiare qualcosa, spiega dove farlo nell'interfaccia."""


def _trim(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tiene la coda della conversazione, senza spezzare una coppia richiesta/risultato."""

    if len(history) <= MAXIMUM_HISTORY_MESSAGES:
        return history
    trimmed = history[-MAXIMUM_HISTORY_MESSAGES:]
    while trimmed and trimmed[0].get("role") == "tool":
        trimmed = trimmed[1:]
    return trimmed


def run_agent(provider, history: list[dict[str, Any]], user, giocatore: Giocatore) -> dict[str, Any]:
    """Esegue un turno completo e restituisce la risposta più la traccia degli strumenti."""

    client = chat_provider_for(provider)
    tools = tool_definitions()
    conversation = _trim(list(history))
    trace: list[dict[str, Any]] = []
    usage = {"inputTokens": 0, "outputTokens": 0}

    for _ in range(MAXIMUM_ITERATIONS):
        turn = client.complete(system=SYSTEM_PROMPT, history=conversation, tools=tools)
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
            return {
                "reply": turn.text,
                "history": conversation,
                "toolTrace": trace,
                "usage": usage,
                "stopReason": turn.stop_reason,
            }

        for call in turn.tool_calls:
            result, is_error = execute_tool(call.name, call.arguments, user, giocatore)
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

    raise ApiError(
        "ai.iteration_limit",
        "L'assistente ha consultato troppi strumenti senza concludere. Riformula la domanda in modo più specifico.",
        status=409,
    )

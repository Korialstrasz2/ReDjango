"""Adattatore compatibile OpenAI.

Un solo adattatore copre OpenAI, DeepSeek e qualsiasi server locale che parli lo
stesso dialetto: cambia soltanto `base_url`. È il motivo per cui il progetto non
ha bisogno di un framework di agenti — i formati di rete da conoscere sono due.
"""

from __future__ import annotations

import json
from typing import Any

from backend.core.api import ApiError

from .base import ChatTurn, ToolCall, post_json


DEFAULT_MAX_TOKENS = 4000


class OpenAICompatibleChatProvider:
    def __init__(self, provider):
        self.provider = provider

    def _endpoint(self) -> str:
        base = (self.provider.base_url or "").rstrip("/")
        if not base:
            raise ApiError("ai.base_url_missing", "Configura l'indirizzo del provider.", status=409)
        return f"{base}/chat/completions"

    def _headers(self) -> dict[str, str]:
        from ..models import AIProvider

        if self.provider.auth_strategy == AIProvider.AUTH_NONE:
            return {}
        secret = self.provider.read_secret()
        if not secret:
            raise ApiError("ai.secret_missing", "Configura la chiave API di questo provider.", status=409)
        return {"Authorization": f"Bearer {secret}"}

    def _messages(self, system: str, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for entry in history:
            role = entry.get("role")
            if role == "user":
                messages.append({"role": "user", "content": entry.get("content", "")})
            elif role == "assistant":
                raw = entry.get("raw")
                if isinstance(raw, dict):
                    messages.append(raw)
                    continue
                message: dict[str, Any] = {"role": "assistant", "content": entry.get("content", "") or None}
                calls = entry.get("toolCalls") or []
                if calls:
                    message["tool_calls"] = [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {"name": call["name"], "arguments": json.dumps(call.get("arguments") or {})},
                        }
                        for call in calls
                    ]
                messages.append(message)
            elif role == "tool":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": entry.get("toolCallId", ""),
                        "content": entry.get("content", ""),
                    }
                )
        return messages

    def complete(self, *, system: str, history: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatTurn:
        options = self.provider.options if isinstance(self.provider.options, dict) else {}
        payload: dict[str, Any] = {
            "model": self.provider.model or "",
            "messages": self._messages(system, history),
            "max_tokens": int(options.get("maxTokens") or DEFAULT_MAX_TOKENS),
        }
        if not payload["model"]:
            raise ApiError("ai.model_missing", "Configura il modello di questo provider.", status=409)
        # I modelli «reasoner» di alcuni fornitori non accettano le funzioni: in quel
        # caso l'agente resta utile, ma risponde senza consultare il database.
        if tools and not options.get("disableTools"):
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
                for tool in tools
            ]

        body = post_json(self._endpoint(), payload, self._headers())
        choices = body.get("choices") or []
        if not choices:
            raise ApiError("ai.provider_error", "Il provider non ha restituito alcuna risposta.", status=502)
        message = choices[0].get("message") or {}

        tool_calls: list[ToolCall] = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except ValueError:
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=str(call.get("id") or ""),
                    name=str(function.get("name") or ""),
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )

        usage = body.get("usage") or {}
        return ChatTurn(
            text=str(message.get("content") or "").strip(),
            tool_calls=tool_calls,
            stop_reason=str(choices[0].get("finish_reason") or ""),
            raw=message,
            usage={
                "inputTokens": usage.get("prompt_tokens", 0),
                "outputTokens": usage.get("completion_tokens", 0),
            },
        )

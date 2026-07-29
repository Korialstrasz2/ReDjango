"""Adattatore per l'API Messages di Anthropic.

Usa l'SDK ufficiale, importato pigramente: chi configura soltanto un provider
compatibile OpenAI non deve installare nulla in più.

Nota sui modelli recenti: `temperature`, `top_p`, `top_k` e `budget_tokens` sono
rifiutati con 400 su Claude Opus 5 e successivi, quindi non vengono mai inviati.
`max_tokens` limita ragionamento e risposta insieme, perciò va tenuto generoso.
"""

from __future__ import annotations

from typing import Any

from backend.core.api import ApiError

from .base import ChatTurn, ToolCall


DEFAULT_MODEL = "claude-opus-4-1-20250805"
DEFAULT_MAX_TOKENS = 8000


class AnthropicChatProvider:
    def __init__(self, provider):
        self.provider = provider

    def _client(self):
        try:
            import anthropic  # noqa: PLC0415 - import pigro voluto
        except ImportError as error:
            raise ApiError(
                "ai.anthropic_sdk_missing",
                "Installa il pacchetto Python «anthropic» per usare questo provider.",
                status=409,
            ) from error

        secret = self.provider.read_secret()
        if not secret:
            raise ApiError("ai.secret_missing", "Configura la chiave API di questo provider.", status=409)
        options: dict[str, Any] = {"api_key": secret}
        if self.provider.base_url:
            options["base_url"] = self.provider.base_url
        return anthropic.Anthropic(**options)

    def _messages(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for entry in history:
            role = entry.get("role")
            if role == "user":
                messages.append({"role": "user", "content": entry.get("content", "")})
            elif role == "assistant":
                raw = entry.get("raw")
                if raw:
                    messages.append({"role": "assistant", "content": raw})
                else:
                    blocks: list[dict[str, Any]] = []
                    if entry.get("content"):
                        blocks.append({"type": "text", "text": entry.get("content", "")})
                    blocks.extend(
                        {
                            "type": "tool_use",
                            "id": call.get("id", ""),
                            "name": call.get("name", ""),
                            "input": call.get("arguments") or {},
                        }
                        for call in entry.get("toolCalls") or []
                    )
                    messages.append({"role": "assistant", "content": blocks or ""})
            elif role == "tool":
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": entry.get("toolCallId", ""),
                                "content": entry.get("content", ""),
                                "is_error": bool(entry.get("isError")),
                            }
                        ],
                    }
                )
        return messages

    def complete(self, *, system: str, history: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatTurn:
        client = self._client()
        options = self.provider.options if isinstance(self.provider.options, dict) else {}
        request: dict[str, Any] = {
            "model": self.provider.model or DEFAULT_MODEL,
            "max_tokens": int(options.get("maxTokens") or DEFAULT_MAX_TOKENS),
            "system": system,
            "messages": self._messages(history),
        }
        if tools and not options.get("disableTools"):
            request["tools"] = tools
        effort = str(options.get("effort") or "").strip()
        if effort:
            request["output_config"] = {"effort": effort}

        try:
            response = client.messages.create(**request)
        except Exception as error:  # noqa: BLE001 - l'SDK espone molte eccezioni tipizzate
            raise ApiError("ai.provider_error", f"Anthropic: {error}", status=502) from error

        if getattr(response, "stop_reason", "") == "refusal":
            raise ApiError(
                "ai.refused",
                "Il modello ha rifiutato la richiesta per motivi di sicurezza.",
                status=422,
            )

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        raw_blocks: list[dict[str, Any]] = []
        for block in getattr(response, "content", []) or []:
            block_type = getattr(block, "type", "")
            raw_blocks.append(block.model_dump() if hasattr(block, "model_dump") else dict(block))
            if block_type == "text":
                text_parts.append(getattr(block, "text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=getattr(block, "id", ""),
                        name=getattr(block, "name", ""),
                        arguments=dict(getattr(block, "input", {}) or {}),
                    )
                )

        usage = getattr(response, "usage", None)
        return ChatTurn(
            text="\n".join(part for part in text_parts if part).strip(),
            tool_calls=tool_calls,
            stop_reason=str(getattr(response, "stop_reason", "") or ""),
            raw=raw_blocks,
            usage={
                "inputTokens": getattr(usage, "input_tokens", 0) if usage else 0,
                "outputTokens": getattr(usage, "output_tokens", 0) if usage else 0,
            },
        )

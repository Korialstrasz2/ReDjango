"""Adattatori OpenAI Responses e Chat Completions compatibile."""

from __future__ import annotations

import json
from typing import Any

from backend.core.api import ApiError

from .base import ChatTurn, ToolCall, post_json


DEFAULT_MAX_TOKENS = 8000


class _OpenAIBase:
    def __init__(self, provider):
        self.provider = provider

    def _endpoint(self, path: str) -> str:
        base = (self.provider.base_url or "").rstrip("/")
        if not base:
            raise ApiError("ai.base_url_missing", "Configura l'indirizzo del provider.", status=409)
        return f"{base}/{path}"

    def _headers(self) -> dict[str, str]:
        from ..models import AIProvider

        if self.provider.auth_strategy == AIProvider.AUTH_NONE:
            return {}
        secret = self.provider.read_secret()
        if not secret:
            raise ApiError("ai.secret_missing", "Configura la chiave API di questo provider.", status=409)
        return {"Authorization": f"Bearer {secret}"}

    def _timeout(self) -> int:
        return max(1, int(getattr(self, "request_timeout", 180) or 180))


class OpenAIResponsesChatProvider(_OpenAIBase):
    """Responses API: percorso OpenAI moderno per ragionamento e strumenti."""

    def _input(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for entry in history:
            role = entry.get("role")
            if role in {"user", "assistant"}:
                raw = entry.get("raw")
                if role == "assistant" and isinstance(raw, list):
                    items.extend(raw)
                    continue
                items.append({"role": role, "content": entry.get("content", "")})
                if role == "assistant":
                    for call in entry.get("toolCalls") or []:
                        items.append(
                            {
                                "type": "function_call",
                                "call_id": call.get("id", ""),
                                "name": call.get("name", ""),
                                "arguments": json.dumps(call.get("arguments") or {}),
                            }
                        )
            elif role == "tool":
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": entry.get("toolCallId", ""),
                        "output": entry.get("content", ""),
                    }
                )
        return items

    def complete(self, *, system: str, history: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatTurn:
        options = self.provider.options if isinstance(self.provider.options, dict) else {}
        if not self.provider.model:
            raise ApiError("ai.model_missing", "Configura il modello di questo provider.", status=409)
        payload: dict[str, Any] = {
            "model": self.provider.model,
            "instructions": system,
            "input": self._input(history),
            "max_output_tokens": int(options.get("maxTokens") or DEFAULT_MAX_TOKENS),
            "store": False,
        }
        effort = str(options.get("effort") or "").strip()
        if effort:
            payload["reasoning"] = {"effort": effort}
        verbosity = str(options.get("verbosity") or "").strip()
        if verbosity:
            payload["text"] = {"verbosity": verbosity}
        if tools and not options.get("disableTools"):
            payload["tools"] = [
                {
                    "type": "function",
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                }
                for tool in tools
            ]

        body = post_json(self._endpoint("responses"), payload, self._headers(), timeout=self._timeout())
        output = body.get("output") or []
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for item in output:
            if item.get("type") == "message":
                for part in item.get("content") or []:
                    if part.get("type") == "output_text":
                        text_parts.append(str(part.get("text") or ""))
            elif item.get("type") == "function_call":
                try:
                    arguments = json.loads(item.get("arguments") or "{}")
                except ValueError:
                    arguments = {}
                tool_calls.append(
                    ToolCall(
                        id=str(item.get("call_id") or item.get("id") or ""),
                        name=str(item.get("name") or ""),
                        arguments=arguments if isinstance(arguments, dict) else {},
                    )
                )
        usage = body.get("usage") or {}
        return ChatTurn(
            text="\n".join(part for part in text_parts if part).strip(),
            tool_calls=tool_calls,
            stop_reason=str(body.get("status") or ""),
            raw=output,
            usage={
                "inputTokens": usage.get("input_tokens", 0),
                "outputTokens": usage.get("output_tokens", 0),
            },
        )


class OpenAICompatibleChatProvider(_OpenAIBase):
    """Chat Completions per DeepSeek, Ollama, LM Studio e endpoint equivalenti."""

    def _messages(self, system: str, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for entry in history:
            role = entry.get("role")
            if role == "user":
                messages.append({"role": "user", "content": entry.get("content", "")})
            elif role == "assistant":
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
                    {"role": "tool", "tool_call_id": entry.get("toolCallId", ""), "content": entry.get("content", "")}
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
        body = post_json(self._endpoint("chat/completions"), payload, self._headers(), timeout=self._timeout())
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
            usage={"inputTokens": usage.get("prompt_tokens", 0), "outputTokens": usage.get("completion_tokens", 0)},
        )

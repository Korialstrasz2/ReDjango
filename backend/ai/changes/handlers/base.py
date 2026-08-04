from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from backend.core.api import ApiError


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def field_error(error: ApiError) -> dict[str, Any]:
    payload = {"code": error.code, "message": error.message}
    if error.field:
        payload["field"] = error.field
    return payload

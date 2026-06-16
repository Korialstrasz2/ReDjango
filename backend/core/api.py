import json
from dataclasses import dataclass

from django.http import JsonResponse


ENVELOPE_KEYS = {"action", "requestId", "context", "payload", "meta"}


@dataclass
class ApiError(Exception):
    code: str
    message: str
    field: str | None = None
    status: int = 400

    def as_dict(self) -> dict:
        error = {"code": self.code, "message": self.message}
        if self.field:
            error["field"] = self.field
        return error


def request_id_from(request) -> str:
    return getattr(request, "redjango_request_id", "") or request.headers.get("X-ReDjango-Request-Id", "")


def api_response(
    request,
    data: dict | None = None,
    *,
    status: int = 200,
    ok: bool = True,
    events: list[dict] | None = None,
    warnings: list[dict] | None = None,
    errors: list[dict] | None = None,
):
    return JsonResponse(
        {
            "ok": ok,
            "requestId": request_id_from(request),
            "data": data or {},
            "events": events or [],
            "warnings": warnings or [],
            "errors": errors or [],
        },
        status=status,
    )


def api_error_response(request, error: ApiError):
    return api_response(
        request,
        ok=False,
        status=error.status,
        errors=[error.as_dict()],
    )


def _decode_json(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError("request.invalid_json", "Request body must be valid JSON.") from exc
    if not isinstance(data, dict):
        raise ApiError("request.invalid_json", "Request body must be a JSON object.")
    return data


def request_payload(request) -> dict:
    if not request.body:
        return {}

    body = _decode_json(request.body.decode("utf-8"))
    if body.get("requestId"):
        request.redjango_request_id = str(body["requestId"])

    if ENVELOPE_KEYS.intersection(body):
        payload = body.get("payload", {})
        if not isinstance(payload, dict):
            raise ApiError("request.invalid_payload", "Envelope payload must be an object.", "payload")
        return payload

    return body


def multipart_payload(request) -> dict:
    raw_envelope = request.POST.get("envelope")
    if not raw_envelope:
        return {key: request.POST.get(key, "") for key in request.POST if key != "envelope"}

    envelope = _decode_json(raw_envelope)
    if envelope.get("requestId"):
        request.redjango_request_id = str(envelope["requestId"])

    payload = envelope.get("payload", {})
    if not isinstance(payload, dict):
        raise ApiError("request.invalid_payload", "Envelope payload must be an object.", "payload")
    return payload

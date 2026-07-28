from functools import lru_cache
from ipaddress import ip_address, ip_network

from django.conf import settings


def peer_ip(request) -> str:
    candidate = str(request.META.get("REMOTE_ADDR") or "").split("%", 1)[0].strip()
    try:
        return str(ip_address(candidate))
    except ValueError:
        return "unknown"


@lru_cache(maxsize=16)
def _proxy_networks(values: tuple[str, ...]):
    return tuple(ip_network(value, strict=False) for value in values)


def is_trusted_proxy(candidate: str) -> bool:
    try:
        address = ip_address(candidate)
    except ValueError:
        return False
    configured = tuple(getattr(settings, "REDJANGO_TRUSTED_PROXIES", ()))
    return any(address in network for network in _proxy_networks(configured))


def client_ip(request) -> str:
    """Resolve a client IP only through an explicitly trusted proxy chain."""

    peer = peer_ip(request)
    if not is_trusted_proxy(peer):
        return peer

    forwarded = []
    for raw_value in str(request.META.get("HTTP_X_FORWARDED_FOR") or "").split(","):
        candidate = raw_value.strip().split("%", 1)[0]
        if not candidate:
            continue
        try:
            forwarded.append(str(ip_address(candidate)))
        except ValueError:
            continue

    for candidate in reversed([*forwarded, peer]):
        if not is_trusted_proxy(candidate):
            return candidate
    return peer


def strip_untrusted_proxy_headers(request) -> None:
    if is_trusted_proxy(peer_ip(request)):
        return
    for header in (
        "HTTP_FORWARDED",
        "HTTP_X_FORWARDED_FOR",
        "HTTP_X_FORWARDED_HOST",
        "HTTP_X_FORWARDED_PORT",
        "HTTP_X_FORWARDED_PROTO",
    ):
        request.META.pop(header, None)

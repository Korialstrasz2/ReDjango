from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class PublicOrigin:
    origin: str
    allowed_host: str


def parse_public_origin(value: str) -> PublicOrigin | None:
    """Validate and normalize the public HTTPS origin of a reverse proxy."""
    raw = str(value or "").strip()
    if not raw:
        return None

    parsed = urlsplit(raw)
    if parsed.scheme.lower() != "https":
        raise ValueError("REDJANGO_PUBLIC_ORIGIN deve usare https://.")
    if not parsed.hostname:
        raise ValueError("REDJANGO_PUBLIC_ORIGIN deve contenere un nome host valido.")
    if parsed.username or parsed.password:
        raise ValueError("REDJANGO_PUBLIC_ORIGIN non può contenere credenziali.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("REDJANGO_PUBLIC_ORIGIN deve essere un'origine senza percorso, query o frammento.")

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("REDJANGO_PUBLIC_ORIGIN contiene una porta non valida.") from exc

    hostname = parsed.hostname.rstrip(".").lower()
    if not hostname:
        raise ValueError("REDJANGO_PUBLIC_ORIGIN deve contenere un nome host valido.")
    origin_host = f"[{hostname}]" if ":" in hostname else hostname
    port_suffix = f":{port}" if port is not None and port != 443 else ""
    return PublicOrigin(
        origin=f"https://{origin_host}{port_suffix}",
        allowed_host=hostname,
    )

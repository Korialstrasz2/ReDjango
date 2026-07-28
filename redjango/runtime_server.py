from __future__ import annotations

import argparse
from urllib.parse import urlsplit

import uvicorn


def parse_bind(value: str) -> tuple[str, int]:
    parsed = urlsplit(f"//{value.strip()}")
    if not parsed.hostname or parsed.port is None:
        raise ValueError("L'indirizzo di ascolto deve avere il formato host:porta.")
    if not 1 <= parsed.port <= 65535:
        raise ValueError("La porta di ascolto deve essere compresa tra 1 e 65535.")
    return parsed.hostname, parsed.port


def main() -> None:
    parser = argparse.ArgumentParser(description="Avvia ReDjango sul server ASGI.")
    parser.add_argument("--bind", required=True, help="Indirizzo host:porta, per esempio 127.0.0.1:8003.")
    parser.add_argument("--ssl-keyfile")
    parser.add_argument("--ssl-certfile")
    arguments = parser.parse_args()

    try:
        host, port = parse_bind(arguments.bind)
    except ValueError as error:
        parser.error(str(error))

    uvicorn.run(
        "redjango.asgi:application",
        host=host,
        port=port,
        ssl_keyfile=arguments.ssl_keyfile,
        ssl_certfile=arguments.ssl_certfile,
    )


if __name__ == "__main__":
    main()

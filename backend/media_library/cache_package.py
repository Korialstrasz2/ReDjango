from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import re
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.utils import timezone

from .cache_manifest import media_cache_manifest


PACKAGE_FORMAT = "redjango-media-package"
PACKAGE_VERSION = 1
PACKAGE_MANIFEST_PATH = "redjango-media-package.json"
SIGNATURE_DOMAIN = b"redjango-media-package-v1\0"
TRAVEL_TILE_URL = re.compile(
    r"^/media/travel-tiles/(?P<map>\d+)/(?P<revision>[0-9a-f]{64})/"
    r"(?P<level>\d+)/(?P<column>\d+)/(?P<row>\d+)\.webp$"
)


class PackageBuildError(Exception):
    pass


class PackageValidationError(Exception):
    pass


def _canonical_payload(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _signature(payload: dict) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        SIGNATURE_DOMAIN + _canonical_payload(payload),
        hashlib.sha256,
    ).hexdigest()


def _inside(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(resolved_root):
        raise PackageBuildError("Un percorso del pacchetto esce dalla directory consentita.")
    return resolved


def source_path_for_url(url: str) -> Path:
    path = unquote(urlsplit(url).path)
    tile_match = TRAVEL_TILE_URL.fullmatch(path)
    if tile_match:
        values = tile_match.groupdict()
        relative = Path(
            ".derived",
            "travel_tiles",
            values["map"],
            values["revision"],
            values["level"],
            f"{values['column']}-{values['row']}.webp",
        )
        return _inside(Path(settings.MEDIA_ROOT), Path(settings.MEDIA_ROOT) / relative)

    media_prefix = urlsplit(settings.MEDIA_URL).path.rstrip("/") + "/"
    if path.startswith(media_prefix):
        return _inside(Path(settings.MEDIA_ROOT), Path(settings.MEDIA_ROOT) / path[len(media_prefix):])

    static_prefix = "/static/frontend/"
    if path.startswith(static_prefix):
        if settings.STATIC_ROOT:
            collected_root = Path(settings.STATIC_ROOT)
            collected = collected_root / path.removeprefix("/static/")
            if collected.is_file():
                return _inside(collected_root, collected)
        static_root = Path(settings.BASE_DIR) / "frontend" / "static" / "frontend"
        return _inside(static_root, static_root / path[len(static_prefix):])

    raise PackageBuildError(f"URL non supportato nel pacchetto: {url}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_document(user, giocatore) -> tuple[dict, list[tuple[Path, str]]]:
    manifest = media_cache_manifest(user, giocatore)
    if manifest["campaign"] is None:
        raise PackageBuildError("Seleziona una campagna prima di esportare i media.")

    files: list[dict] = []
    sources: list[tuple[Path, str]] = []
    for index, entry in enumerate(manifest["entries"]):
        try:
            source = source_path_for_url(entry["url"])
        except (OSError, PackageBuildError) as error:
            raise PackageBuildError(f"File non disponibile per l'esportazione: {entry['label']}.") from error
        suffix = source.suffix.casefold() if len(source.suffix) <= 12 else ""
        archive_path = f"files/{index:06d}{suffix}"
        try:
            size = source.stat().st_size
        except OSError as error:
            raise PackageBuildError(f"File scomparso durante l'esportazione: {entry['label']}.") from error
        if size >= 0xFFFFFFFF:
            raise PackageBuildError(f"Il singolo file supera il limite ZIP importabile: {entry['label']}.")
        try:
            digest = _sha256(source)
        except OSError as error:
            raise PackageBuildError(f"Impossibile leggere il file durante l'esportazione: {entry['label']}.") from error
        files.append({
            **entry,
            "size": size,
            "archivePath": archive_path,
            "sha256": digest,
            "contentType": mimetypes.guess_type(source.name)[0] or "application/octet-stream",
        })
        sources.append((source, archive_path))

    payload = {
        "campaign": manifest["campaign"],
        "createdAt": timezone.now().isoformat(),
        "files": files,
        "totalBytes": sum(entry["size"] for entry in files),
    }
    document = {
        "format": PACKAGE_FORMAT,
        "version": PACKAGE_VERSION,
        "payload": payload,
        "signature": {
            "algorithm": "hmac-sha256",
            "value": _signature(payload),
        },
    }
    return document, sources


def build_package_archive(user, giocatore):
    document, sources = package_document(user, giocatore)
    target = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024, mode="w+b")
    try:
        with zipfile.ZipFile(target, mode="w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            archive.writestr(
                PACKAGE_MANIFEST_PATH,
                json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                compress_type=zipfile.ZIP_STORED,
            )
            for source, archive_path in sources:
                archive.write(source, archive_path, compress_type=zipfile.ZIP_STORED)
        target.seek(0)
        return target, document
    except (OSError, zipfile.LargeZipFile) as error:
        target.close()
        raise PackageBuildError("Il pacchetto non può essere completato: controlla spazio e file media.") from error
    except Exception:
        target.close()
        raise


def verify_package_document(document: object, *, campaign_id: int | None, allowed_entries: dict[str, dict]) -> dict:
    if not isinstance(document, dict):
        raise PackageValidationError("Manifest del pacchetto non valido.")
    if document.get("format") != PACKAGE_FORMAT or document.get("version") != PACKAGE_VERSION:
        raise PackageValidationError("Formato o versione del pacchetto non supportati.")
    payload = document.get("payload")
    signature = document.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature, dict):
        raise PackageValidationError("Firma del pacchetto mancante.")
    supplied = str(signature.get("value") or "")
    if signature.get("algorithm") != "hmac-sha256" or not hmac.compare_digest(supplied, _signature(payload)):
        raise PackageValidationError("Firma del pacchetto non valida: non importare questo file.")

    campaign = payload.get("campaign")
    if not isinstance(campaign, dict) or campaign.get("id") != campaign_id or campaign_id is None:
        raise PackageValidationError("Il pacchetto appartiene a una campagna diversa da quella selezionata.")
    files = payload.get("files")
    if not isinstance(files, list) or len(files) > 100_000:
        raise PackageValidationError("Elenco dei file del pacchetto non valido.")
    seen_urls: set[str] = set()
    seen_paths: set[str] = set()
    resolved_files: list[dict] = []
    total_bytes = 0
    for entry in files:
        if not isinstance(entry, dict):
            raise PackageValidationError("Voce del pacchetto non valida.")
        url = str(entry.get("url") or "")
        cache_key = str(entry.get("cacheKey") or "")
        archive_path = str(entry.get("archivePath") or "")
        digest = str(entry.get("sha256") or "")
        size = entry.get("size")
        current = allowed_entries.get(cache_key)
        if current is None:
            raise PackageValidationError("Il pacchetto contiene media non disponibili per questa campagna.")
        if url in seen_urls or archive_path in seen_paths or not re.fullmatch(r"files/\d{6,}[^/]*", archive_path):
            raise PackageValidationError("Il pacchetto contiene percorsi duplicati o non validi.")
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or not isinstance(size, int) or size < 0:
            raise PackageValidationError("Dimensione o impronta di un file non valida.")
        seen_urls.add(url)
        seen_paths.add(archive_path)
        total_bytes += size
        resolved_files.append({
            "archivePath": archive_path,
            "url": current["url"],
            "revision": current["revision"],
        })
    if payload.get("totalBytes") != total_bytes:
        raise PackageValidationError("La dimensione totale dichiarata non corrisponde ai file.")
    return {**payload, "resolvedFiles": resolved_files}

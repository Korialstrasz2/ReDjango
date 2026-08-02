import hashlib
import mimetypes
import re
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.utils.http import http_date, parse_http_date_safe
from django.views.decorators.http import require_GET

from backend.core.security import get_or_create_giocatore_for_user
from backend.core.views import get_authenticated_user

from .models import UploadedImage
from .selectors import user_can_view_limited_images
from .travel_services import get_travel_map
from .travel_tiles import travel_tile_path


INLINE_MEDIA_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".flac",
    ".gif",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mp3",
    ".mp4",
    ".oga",
    ".ogg",
    ".opus",
    ".png",
    ".wav",
    ".webm",
    ".webp",
}

# Django's FileResponse still streams the whole file, so a player could not seek
# inside a long track. Range support is limited to media that is actually played.
RANGE_MEDIA_EXTENSIONS = {".flac", ".m4a", ".mp3", ".mp4", ".oga", ".ogg", ".opus", ".wav", ".webm"}
RANGE_PATTERN = re.compile(r"^bytes=(\d*)-(\d*)$")
IMMUTABLE_CACHE_CONTROL = "private, max-age=31536000, immutable"
RESTRICTED_CACHE_CONTROL = "private, no-store"


def _resolved_media_path(media_path: str) -> tuple[Path, str]:
    relative = PurePosixPath(media_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise Http404

    media_root = Path(settings.MEDIA_ROOT).resolve()
    candidate = media_root.joinpath(*relative.parts).resolve()
    try:
        candidate.relative_to(media_root)
    except ValueError as exc:
        raise Http404 from exc
    if not candidate.is_file():
        raise Http404
    return candidate, relative.as_posix()


def _requested_range(header: str, size: int) -> tuple[int, int] | None:
    """Resolve one `bytes=` range, or `None` when the whole file should be sent."""

    match = RANGE_PATTERN.match(header.strip())
    if not match:
        return None
    raw_start, raw_end = match.groups()
    if raw_start:
        start = int(raw_start)
        end = min(int(raw_end), size - 1) if raw_end else size - 1
    elif raw_end:
        # A suffix range asks for the last N bytes.
        start = max(size - int(raw_end), 0)
        end = size - 1
    else:
        return None
    if start > end or start >= size:
        return None
    return start, end


def _stream_range(path: Path, start: int, end: int, block_size: int = 64 * 1024):
    """Yield exactly the requested bytes so `Content-Length` stays truthful."""

    remaining = end - start + 1
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining > 0:
            chunk = handle.read(min(block_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _metadata_sha256(image: UploadedImage | None, storage_name: str) -> str:
    if image is None or not image.file or image.file.name != storage_name:
        return ""
    metadata = image.metadata if isinstance(image.metadata, dict) else {}
    digest = str(metadata.get("sha256") or "").casefold()
    return digest if re.fullmatch(r"[0-9a-f]{64}", digest) else ""


def _strong_etag(candidate: Path, image: UploadedImage | None, storage_name: str) -> str:
    digest = _metadata_sha256(image, storage_name)
    if not digest:
        stat = candidate.stat()
        identity = f"{storage_name}\0{stat.st_size}\0{stat.st_mtime_ns}".encode("utf-8")
        digest = hashlib.sha256(identity).hexdigest()
    return f'"{digest}"'


def _etag_matches(header: str, etag: str) -> bool:
    for raw_value in header.split(","):
        value = raw_value.strip()
        if value == "*" or value == etag or value.removeprefix("W/") == etag:
            return True
    return False


def _not_modified(request, etag: str, modified_at: int) -> bool:
    if_none_match = request.headers.get("If-None-Match", "")
    if if_none_match:
        return _etag_matches(if_none_match, etag)
    if_modified_since = parse_http_date_safe(request.headers.get("If-Modified-Since", ""))
    return if_modified_since is not None and modified_at <= if_modified_since


def _secure_media_headers(
    response,
    candidate: Path,
    *,
    immutable: bool,
    etag: str = "",
    modified_at: int | None = None,
) -> None:
    response.headers["Cache-Control"] = IMMUTABLE_CACHE_CONTROL if immutable else RESTRICTED_CACHE_CONTROL
    response.headers["X-ReDjango-Cacheability"] = "immutable" if immutable else "restricted-no-store"
    response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if etag:
        response.headers["ETag"] = etag
    if modified_at is not None:
        response.headers["Last-Modified"] = http_date(modified_at)
    if candidate.suffix.casefold() in RANGE_MEDIA_EXTENSIONS:
        response.headers["Accept-Ranges"] = "bytes"


@require_GET
def protected_media(request, media_path: str):
    """Stream local uploads through Django's session and game-role checks."""

    candidate, storage_name = _resolved_media_path(media_path)
    image = UploadedImage.objects.filter(
        Q(file=storage_name) | Q(thumbnail=storage_name),
    ).first()
    if image is not None and image.archived_at is not None:
        raise Http404
    if (
        image is not None
        and image.visibilita_limitata
        and not user_can_view_limited_images(request.user)
    ):
        # Do not disclose whether a hidden asset exists.
        raise Http404

    immutable = image is None or not image.visibilita_limitata
    stat = candidate.stat()
    modified_at = int(stat.st_mtime)
    etag = _strong_etag(candidate, image, storage_name) if immutable else ""
    if immutable and _not_modified(request, etag, modified_at):
        response = HttpResponse(status=304)
        _secure_media_headers(
            response,
            candidate,
            immutable=True,
            etag=etag,
            modified_at=modified_at,
        )
        return response

    content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
    extension = candidate.suffix.casefold()
    as_attachment = extension not in INLINE_MEDIA_EXTENSIONS

    range_header = request.headers.get("Range", "")
    if range_header and extension in RANGE_MEDIA_EXTENSIONS:
        size = stat.st_size
        requested = _requested_range(range_header, size)
        if requested is None:
            response = HttpResponse(status=416, content_type=content_type)
            response.headers["Content-Range"] = f"bytes */{size}"
            _secure_media_headers(
                response,
                candidate,
                immutable=immutable,
                etag=etag,
                modified_at=modified_at if immutable else None,
            )
            return response
        start, end = requested
        response = StreamingHttpResponse(
            _stream_range(candidate, start, end),
            status=206,
            content_type=content_type,
        )
        response.headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        response.headers["Content-Length"] = str(end - start + 1)
        _secure_media_headers(
            response,
            candidate,
            immutable=immutable,
            etag=etag,
            modified_at=modified_at if immutable else None,
        )
        return response

    response = FileResponse(
        candidate.open("rb"),
        as_attachment=as_attachment,
        filename=candidate.name,
        content_type=content_type,
    )
    _secure_media_headers(
        response,
        candidate,
        immutable=immutable,
        etag=etag,
        modified_at=modified_at if immutable else None,
    )
    return response


@require_GET
def travel_tile(request, map_id: int, revision: str, level: int, column: int, row: int):
    """Serve one immutable tile after the same campaign and role checks as Viaggio."""

    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    travel_map = get_travel_map(giocatore, map_id)
    if travel_map.image.visibilita_limitata and not user_can_view_limited_images(user):
        raise Http404
    candidate = travel_tile_path(travel_map, revision, level, column, row)
    if candidate is None:
        raise Http404

    stat = candidate.stat()
    modified_at = int(stat.st_mtime)
    etag = _strong_etag(candidate, None, candidate.as_posix())
    if _not_modified(request, etag, modified_at):
        response = HttpResponse(status=304)
    else:
        response = FileResponse(candidate.open("rb"), content_type="image/webp")
    _secure_media_headers(
        response,
        candidate,
        immutable=not travel_map.image.visibilita_limitata,
        etag=etag,
        modified_at=modified_at,
    )
    return response

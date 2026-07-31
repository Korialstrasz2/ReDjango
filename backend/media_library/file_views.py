import mimetypes
import re
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET

from .models import UploadedImage
from .selectors import user_can_view_limited_images


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


def _secure_media_headers(response, candidate: Path) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
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

    content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
    extension = candidate.suffix.casefold()
    as_attachment = extension not in INLINE_MEDIA_EXTENSIONS

    range_header = request.headers.get("Range", "")
    if range_header and extension in RANGE_MEDIA_EXTENSIONS:
        size = candidate.stat().st_size
        requested = _requested_range(range_header, size)
        if requested is None:
            response = HttpResponse(status=416, content_type=content_type)
            response.headers["Content-Range"] = f"bytes */{size}"
            _secure_media_headers(response, candidate)
            return response
        start, end = requested
        response = StreamingHttpResponse(
            _stream_range(candidate, start, end),
            status=206,
            content_type=content_type,
        )
        response.headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        response.headers["Content-Length"] = str(end - start + 1)
        _secure_media_headers(response, candidate)
        return response

    response = FileResponse(
        candidate.open("rb"),
        as_attachment=as_attachment,
        filename=candidate.name,
        content_type=content_type,
    )
    _secure_media_headers(response, candidate)
    return response

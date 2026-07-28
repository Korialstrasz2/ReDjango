import mimetypes
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

from .models import UploadedImage
from .selectors import user_can_view_limited_images


INLINE_MEDIA_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".mp3",
    ".ogg",
    ".png",
    ".wav",
    ".webp",
}


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
    as_attachment = candidate.suffix.casefold() not in INLINE_MEDIA_EXTENSIONS
    response = FileResponse(
        candidate.open("rb"),
        as_attachment=as_attachment,
        filename=candidate.name,
        content_type=content_type,
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

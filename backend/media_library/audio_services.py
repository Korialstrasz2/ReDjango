import hashlib
from pathlib import Path

from django.db import transaction

from backend.core.api import ApiError
from backend.core.models import Giocatore

from .audio_defaults import AUDIO_TAG_VALUES
from .audio_selectors import can_manage_audio_tracks
from .models import AudioFile


MAXIMUM_AUDIO_BYTES = 50 * 1024 * 1024
MAXIMUM_AUDIO_TAGS = 8
MAXIMUM_AUDIO_DURATION_SECONDS = 24 * 60 * 60

# Browsers disagree on the content type of the less common containers: Windows
# Chrome happily reports an empty type or `application/octet-stream` for .flac,
# .opus and .m4a. The extension is therefore the gate, and a declared type only
# has to be plausible when the browser bothers to send one.
ALLOWED_AUDIO_TYPES = {
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".ogg": {"audio/ogg", "application/ogg"},
    ".oga": {"audio/ogg", "application/ogg"},
    ".opus": {"audio/opus", "audio/ogg"},
    ".wav": {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"},
    ".m4a": {"audio/mp4", "audio/x-m4a", "audio/m4a"},
    ".flac": {"audio/flac", "audio/x-flac"},
    ".webm": {"audio/webm"},
}
UNDECLARED_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}


def _require_manager(user, giocatore: Giocatore) -> None:
    if not can_manage_audio_tracks(user, giocatore):
        raise ApiError(
            "audio.master_required",
            "Solo Master e Amministratori possono gestire la colonna sonora.",
            status=403,
        )


def _checksum(uploaded_file) -> str:
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    uploaded_file.seek(0)
    return hasher.hexdigest()


def sanitize_tags(raw: object) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ApiError("audio.tags_invalid", "I tag devono essere un elenco di valori.", "tags")
    tags: list[str] = []
    for value in raw:
        tag = str(value).strip()
        if not tag or tag in tags:
            continue
        if tag not in AUDIO_TAG_VALUES:
            raise ApiError("audio.tag_unknown", f"Il tag «{tag}» non esiste nel catalogo.", "tags")
        tags.append(tag)
    if len(tags) > MAXIMUM_AUDIO_TAGS:
        raise ApiError(
            "audio.tags_too_many",
            f"Una traccia può avere al massimo {MAXIMUM_AUDIO_TAGS} tag.",
            "tags",
        )
    return tags


def sanitize_title(raw: object, fallback: str = "") -> str:
    title = str(raw or fallback).strip()[:180]
    if not title:
        raise ApiError("audio.title_required", "Inserisci un nome per la traccia.", "title")
    return title


def sanitize_duration(raw: object) -> float | None:
    if raw in (None, ""):
        return None
    try:
        duration = float(raw)
    except (TypeError, ValueError):
        return None
    if duration <= 0:
        return None
    return min(duration, MAXIMUM_AUDIO_DURATION_SECONDS)


def _validate_upload(uploaded_file) -> str:
    if not uploaded_file:
        raise ApiError("audio.file_required", "Seleziona un file audio da caricare.", "file")

    extension = Path(uploaded_file.name).suffix.casefold()
    allowed_types = ALLOWED_AUDIO_TYPES.get(extension)
    if allowed_types is None:
        raise ApiError(
            "audio.format_unsupported",
            "Formati accettati: MP3, OGG, OPUS, WAV, M4A, FLAC e WebM.",
            "file",
        )
    mime_type = (uploaded_file.content_type or "").casefold()
    if mime_type not in UNDECLARED_MIME_TYPES and mime_type not in allowed_types:
        raise ApiError("audio.audio_required", "Il file caricato non è una traccia audio.", "file")
    if uploaded_file.size > MAXIMUM_AUDIO_BYTES:
        raise ApiError("audio.file_too_large", "La traccia non può superare 50 MB.", "file")
    return mime_type


@transaction.atomic
def create_audio_track(user, giocatore: Giocatore, uploaded_file, payload: dict) -> AudioFile:
    _require_manager(user, giocatore)
    mime_type = _validate_upload(uploaded_file)
    title = sanitize_title(payload.get("title"), Path(uploaded_file.name).stem)
    tags = sanitize_tags(payload.get("tags"))

    track = AudioFile(
        title=title,
        tags=tags,
        primary_tag=tags[0] if tags else "",
        source="local_upload",
        duration_seconds=sanitize_duration(payload.get("durationSeconds")),
        notes=str(payload.get("notes") or "")[:2000],
        metadata={
            "ownerUserId": user.id,
            "originalName": Path(uploaded_file.name).name[:255],
            "mimeType": mime_type[:120],
            "sizeBytes": uploaded_file.size or 0,
            "sha256": _checksum(uploaded_file),
        },
    )
    track.file = uploaded_file
    track.save()
    return track


def get_audio_track(track_id: int) -> AudioFile:
    try:
        return AudioFile.objects.get(pk=track_id, archived_at__isnull=True)
    except AudioFile.DoesNotExist as exc:
        raise ApiError("audio.track_not_found", "Traccia audio non trovata.", status=404) from exc


@transaction.atomic
def update_audio_track(user, giocatore: Giocatore, track: AudioFile, payload: dict) -> AudioFile:
    _require_manager(user, giocatore)
    fields = ["updated_at"]
    if "title" in payload:
        track.title = sanitize_title(payload.get("title"), track.title)
        fields.append("title")
    if "tags" in payload:
        tags = sanitize_tags(payload.get("tags"))
        track.tags = tags
        track.primary_tag = tags[0] if tags else ""
        fields.extend(["tags", "primary_tag"])
    if "notes" in payload:
        track.notes = str(payload.get("notes") or "")[:2000]
        fields.append("notes")
    if "durationSeconds" in payload:
        # The browser is the only place that knows how long a track actually is.
        duration = sanitize_duration(payload.get("durationSeconds"))
        if duration is not None:
            track.duration_seconds = duration
            fields.append("duration_seconds")
    track.save(update_fields=fields)
    return track


@transaction.atomic
def delete_audio_track(user, giocatore: Giocatore, track: AudioFile) -> str:
    _require_manager(user, giocatore)
    title = track.title
    stored_file = track.file
    track.delete()
    if stored_file:
        stored_file.delete(save=False)
    return title

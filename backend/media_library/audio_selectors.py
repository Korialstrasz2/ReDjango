from pathlib import Path

from backend.core.models import Giocatore
from backend.core.security import effective_role, get_or_create_giocatore_for_user, has_minimum_role

from .audio_defaults import AUDIO_TAG_CHOICES, AUDIO_TAG_LABELS
from .models import AudioFile


def can_manage_audio_tracks(user, giocatore: Giocatore | None = None) -> bool:
    """Only Master and Admin curate the shared soundtrack; everybody may listen."""

    if not user:
        return False
    giocatore = giocatore or get_or_create_giocatore_for_user(user)
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)


def track_tags(track: AudioFile) -> list[str]:
    tags = track.tags if isinstance(track.tags, list) else []
    return [str(tag) for tag in tags if isinstance(tag, str)]


def serialize_audio_track(track: AudioFile) -> dict:
    metadata = track.metadata if isinstance(track.metadata, dict) else {}
    tags = track_tags(track)
    return {
        "id": track.id,
        "title": track.title,
        "tags": tags,
        "tagLabels": [AUDIO_TAG_LABELS.get(tag, tag) for tag in tags],
        "url": track.file.url if track.file else "",
        "originalName": metadata.get("originalName") or (Path(track.file.name).name if track.file else ""),
        "mimeType": metadata.get("mimeType", ""),
        "sizeBytes": metadata.get("sizeBytes", 0),
        "durationSeconds": track.duration_seconds,
        "notes": track.notes,
        "createdAt": track.created_at.isoformat() if track.created_at else None,
    }


def list_audio_tracks():
    return AudioFile.objects.filter(archived_at__isnull=True).order_by("title", "id")


def audio_library_payload(user, giocatore: Giocatore | None = None) -> dict:
    return {
        "tracks": [serialize_audio_track(track) for track in list_audio_tracks()],
        "tags": list(AUDIO_TAG_CHOICES),
        "canManage": can_manage_audio_tracks(user, giocatore),
    }

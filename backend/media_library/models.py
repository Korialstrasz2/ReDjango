from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models

from backend.core.models import V2Model


def user_media_upload_path(instance, filename: str) -> str:
    username = getattr(instance.owner, "username", "anonymous") or "anonymous"
    safe_name = Path(filename).name.replace(" ", "_")
    return f"user_media/{username}/{uuid4().hex}_{safe_name}"


def v2_image_upload_path(instance, filename: str) -> str:
    safe_name = Path(filename).name.replace(" ", "_")
    folder = getattr(instance, "folder", "") or "general"
    return f"v2/images/{folder}/{uuid4().hex}_{safe_name}"


def v2_audio_upload_path(instance, filename: str) -> str:
    safe_name = Path(filename).name.replace(" ", "_")
    tag = getattr(instance, "primary_tag", "") or "general"
    return f"v2/audio/{tag}/{uuid4().hex}_{safe_name}"


class UserMediaAsset(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="redjango_media_assets")
    title = models.CharField(max_length=160)
    original_name = models.CharField(max_length=255)
    file = models.FileField(upload_to=user_media_upload_path)
    mime_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "created_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    @classmethod
    def checksum(cls, uploaded_file) -> str:
        digest = sha256()
        for chunk in uploaded_file.chunks():
            digest.update(chunk)
        uploaded_file.seek(0)
        return digest.hexdigest()

    def to_dict(self) -> dict:
        url = self.file.url if self.file else ""
        return {
            "id": self.id,
            "title": self.title,
            "originalName": self.original_name,
            "url": url,
            "mimeType": self.mime_type,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
            "notes": self.notes,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class UploadedImage(V2Model):
    title = models.CharField(max_length=180)
    folder = models.CharField(max_length=160, blank=True)
    file = models.FileField(upload_to=v2_image_upload_path)
    thumbnail = models.FileField(upload_to=v2_image_upload_path, null=True, blank=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="versions")
    usage_type = models.CharField(max_length=80, default="generic")
    campagna = models.ForeignKey(
        "core.DatiCampagna",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_images",
    )
    is_default_for_usage = models.BooleanField(default=False)
    source = models.CharField(max_length=80, blank=True)
    prompt = models.TextField(blank=True)

    class Meta:
        ordering = ["folder", "title"]
        indexes = [
            models.Index(fields=["usage_type", "is_default_for_usage"]),
            models.Index(fields=["campagna", "folder"]),
        ]

    def __str__(self) -> str:
        return self.title

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "folder": self.folder,
            "url": self.file.url if self.file else "",
            "thumbnailUrl": self.thumbnail.url if self.thumbnail else "",
            "usageType": self.usage_type,
            "source": self.source,
        }


class DatiMappa(V2Model):
    TYPE_CHOICES = [
        ("globale", "Globale"),
        ("viaggio", "Viaggio"),
        ("combattimento", "Combattimento"),
        ("dungeon", "Dungeon"),
        ("altro", "Altro"),
    ]

    nome = models.CharField(max_length=180)
    campagna = models.ForeignKey(
        "core.DatiCampagna",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mappe",
    )
    image = models.ForeignKey(UploadedImage, on_delete=models.CASCADE, related_name="mappe")
    tipo = models.CharField(max_length=40, choices=TYPE_CHOICES, default="altro")
    fog_image = models.ForeignKey(
        UploadedImage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fog_mappe",
    )
    progressi = models.JSONField(default=dict, blank=True)
    grid_data = models.JSONField(default=dict, blank=True)
    markers = models.JSONField(default=list, blank=True)
    hex_effects = models.JSONField(default=dict, blank=True)
    canvas_state = models.JSONField(default=dict, blank=True)
    dimensioni = models.JSONField(default=dict, blank=True)
    default_for_campaign = models.BooleanField(default=False)

    class Meta:
        ordering = ["tipo", "nome"]
        indexes = [
            models.Index(fields=["campagna", "tipo", "default_for_campaign"]),
        ]

    def __str__(self) -> str:
        return self.nome


class AudioFile(V2Model):
    title = models.CharField(max_length=180)
    file = models.FileField(upload_to=v2_audio_upload_path)
    primary_tag = models.CharField(max_length=80, blank=True)
    secondary_tags = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=80, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["primary_tag", "title"]
        indexes = [models.Index(fields=["primary_tag", "title"])]

    def __str__(self) -> str:
        return self.title

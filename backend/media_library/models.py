from pathlib import Path
from uuid import uuid4

from django.db import models
from django.utils.text import slugify

from backend.core.models import V2Model


def user_media_upload_path(instance, filename: str) -> str:
    safe_name = Path(filename).name.replace(" ", "_")
    return f"user_media/migration_compat/{uuid4().hex}_{safe_name}"


def v2_image_upload_path(instance, filename: str) -> str:
    safe_name = Path(filename).name.replace(" ", "_")
    folder = getattr(instance, "folder", "") or "general"
    return f"v2/images/{folder}/{uuid4().hex}_{safe_name}"


def v2_video_upload_path(instance, filename: str) -> str:
    safe_name = Path(filename).name.replace(" ", "_")
    usage = getattr(instance, "usage_type", "") or "generic"
    return f"v2/video/{slugify(usage) or 'generic'}/{uuid4().hex}_{safe_name}"


def v2_audio_upload_path(instance, filename: str) -> str:
    safe_name = Path(filename).name.replace(" ", "_")
    tag = getattr(instance, "primary_tag", "") or "general"
    return f"v2/audio/{slugify(tag) or 'general'}/{uuid4().hex}_{safe_name}"


class ImageCategory(V2Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    usage_types = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "categoria immagine"
        verbose_name_plural = "categorie immagini"
        indexes = [models.Index(fields=["is_active", "order", "name"])]

    def __str__(self) -> str:
        return self.name


class UploadedImage(V2Model):
    title = models.CharField(max_length=180)
    folder = models.CharField(max_length=160, blank=True)
    file = models.FileField(upload_to=v2_image_upload_path)
    thumbnail = models.FileField(upload_to=v2_image_upload_path, null=True, blank=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="versions")
    usage_type = models.CharField(max_length=80, default="generic")
    category = models.ForeignKey(
        ImageCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="images",
    )
    group = models.CharField(max_length=160, blank=True)
    campagna = models.ForeignKey(
        "core.DatiCampagna",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_images",
    )
    is_default_for_usage = models.BooleanField(default=False)
    visibilita_limitata = models.BooleanField(
        default=False,
        verbose_name="Visibilità limitata",
        help_text="Nell'Archivio immagini è visibile soltanto a Master e Amministratori.",
    )
    source = models.CharField(max_length=80, blank=True)
    prompt = models.TextField(blank=True)

    class Meta:
        ordering = ["folder", "title"]
        indexes = [
            models.Index(fields=["usage_type", "is_default_for_usage"]),
            models.Index(fields=["campagna", "folder"]),
            models.Index(fields=["category", "group", "title"]),
            models.Index(fields=["visibilita_limitata", "archived_at"], name="media_img_limited_idx"),
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
            "categoryId": self.category_id,
            "category": self.category.name if self.category_id and self.category else "",
            "group": self.group,
            "source": self.source,
            "limitedVisibility": self.visibilita_limitata,
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
        constraints = [
            models.UniqueConstraint(
                fields=["campagna"],
                condition=models.Q(
                    tipo="globale",
                    default_for_campaign=True,
                    archived_at__isnull=True,
                    campagna__isnull=False,
                ),
                name="one_default_global_map_per_campaign",
            ),
        ]

    def __str__(self) -> str:
        return self.nome


class VideoClip(V2Model):
    """Una clip breve e senza audio, mostrata accanto a un'immagine.

    Non è un `UploadedImage`: l'Archivio immagini renderizza ogni riga come
    `<img>`, quindi un mp4 archiviato lì comparirebbe come miniatura rotta. È un
    tipo di media nuovo, con il suo modello, come l'audio ha il suo.
    """

    title = models.CharField(max_length=180)
    file = models.FileField(upload_to=v2_video_upload_path)
    usage_type = models.CharField(max_length=80, default="generic")
    poster = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_clips",
        help_text="Fotogramma statico mostrato prima della riproduzione.",
    )
    source = models.CharField(max_length=80, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["usage_type", "title"]
        verbose_name = "clip video"
        verbose_name_plural = "clip video"
        indexes = [models.Index(fields=["usage_type", "title"])]

    def __str__(self) -> str:
        return self.title


class AudioFile(V2Model):
    """One playable track of the shared campaign soundtrack.

    ``tags`` is the source of truth for the multi-select picklist. ``primary_tag``
    is kept in sync with its first entry because the storage folder, the default
    ordering and the database index are built on it; ``secondary_tags`` remains
    the earlier V2 compatibility column and is never read by the audio library.
    """

    title = models.CharField(max_length=180)
    file = models.FileField(upload_to=v2_audio_upload_path)
    tags = models.JSONField(default=list, blank=True)
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

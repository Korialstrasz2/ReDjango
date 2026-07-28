"""Idempotent importer for the Lore > Timeline section.

The legacy table and its files are read-only inputs. Five neighbouring,
source-backed TES milestones are added as curated records without artwork.
This module deliberately targets ``core.TimelineEvent`` only; reputation
events, campaign audit logs, quests, and Hall of Fame data are separate
domains.
"""
from __future__ import annotations

import mimetypes
import sqlite3
from pathlib import Path
from typing import Any

from django.core.files import File
from django.core.management.base import CommandError
from django.db import transaction

from backend.core.models import DatiCampagna, TimelineEvent
from backend.media_library.models import ImageCategory, UploadedImage

SOURCE_PROJECT = "the_elder_django"
CURATED_SOURCE_PROJECT = "tes_lore_curated"
LEGACY_TABLE = "django_slim_timelineevent"
CURATED_TABLE = "curated_tes_timeline"
DEFAULT_SOURCE_ROOT = Path(r"C:\Users\alexo\PycharmProjects\firstDjango\the_elder_django")
SOURCE_CAMPAIGN_NAME = "Sanguine"

# The old Timeline uses Dagoth Ur's defeat in 3E 427 as year zero. Fourth Era
# dates therefore continue at +7 for 4E 1.
CURATED_TIMELINE_EVENTS: tuple[dict[str, Any], ...] = (
    {
        "sourceId": "warp-in-the-west-3e417",
        "title": "Il Warp in the West",
        "year": -10,
        "description": (
            "3E 417 – L'attivazione del Numidium provoca una Frattura del Drago nella Baia di Iliac. "
            "Esiti politici incompatibili diventano simultaneamente reali e decine di domini vengono "
            "ricomposti in quattro grandi potenze regionali."
        ),
        "tags": ["TES", "Terza Era", "Baia di Iliac", "Frattura del Drago"],
        "sourceUrls": ["https://www.imperial-library.info/content/warp-west"],
    },
    {
        "sourceId": "fourth-era-begins-4e1",
        "title": "Inizio della Quarta Era",
        "year": 7,
        "description": (
            "4E 1 – Dopo la fine della Crisi dell'Oblivion e della dinastia Septim, il calendario "
            "imperiale entra nella Quarta Era. Il Potentato di Ocato tenta di mantenere unito l'Impero "
            "mentre le province reagiscono al vuoto di potere."
        ),
        "tags": ["TES", "Quarta Era", "Impero", "Ocato"],
        "sourceUrls": [
            "https://elderscrolls.fandom.com/wiki/Timeline",
            "https://www.imperial-library.info/content/fourth-era",
        ],
    },
    {
        "sourceId": "accession-war-4e6",
        "title": "Guerra d'Accessione",
        "year": 12,
        "description": (
            "4E 6 – Gli eserciti argoniani invadono Morrowind dopo l'Anno Rosso, devastano il sud "
            "della provincia e raggiungono i territori Telvanni. La controffensiva di Casa Redoran "
            "impedisce la completa occupazione del paese."
        ),
        "tags": ["TES", "Quarta Era", "Morrowind", "Argoniani"],
        "sourceUrls": ["https://www.imperial-library.info/content/fourth-era"],
    },
    {
        "sourceId": "ocato-assassinated-4e10",
        "title": "Assassinio del Potentato Ocato",
        "year": 16,
        "description": (
            "4E 10 – Ocato viene assassinato, il Consiglio degli Anziani si frammenta e diversi "
            "pretendenti si contendono il trono imperiale. Inizia l'Interregno della Corona Tempestosa."
        ),
        "tags": ["TES", "Quarta Era", "Impero", "Interregno"],
        "sourceUrls": ["https://www.imperial-library.info/content/fourth-era"],
    },
    {
        "sourceId": "titus-mede-i-4e17",
        "title": "Ascesa di Titus Mede I",
        "year": 23,
        "description": (
            "4E 17 – Il condottiero coloviano Titus Mede conquista la Città Imperiale e assume il "
            "controllo dell'Impero, ponendo fine all'Interregno e fondando la dinastia Mede."
        ),
        "tags": ["TES", "Quarta Era", "Impero", "Dinastia Mede"],
        "sourceUrls": ["https://www.imperial-library.info/content/fourth-era"],
    },
)


def _connect_read_only(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


class TimelineImporter:
    def __init__(self, source_root: Path):
        self.source_root = source_root
        database = source_root / "db.sqlite3"
        if not database.is_file():
            raise CommandError(f"Database Elder non trovato in {source_root}")
        self.connection = _connect_read_only(database)
        self.campaign = DatiCampagna.objects.filter(
            nome=SOURCE_CAMPAIGN_NAME,
            archived_at__isnull=True,
        ).first()
        if self.campaign is None:
            raise CommandError(
                f"Campagna '{SOURCE_CAMPAIGN_NAME}' non trovata in ReDjango. "
                "Importa prima la campagna con import_elder_characters."
            )

    def close(self) -> None:
        self.connection.close()

    def _legacy_rows(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            f"SELECT id, nome, data_evento, immagine, descrizione FROM {LEGACY_TABLE} "
            "ORDER BY data_evento, id"
        ).fetchall()

    @staticmethod
    def _existing_source_ids(source_project: str, source_table: str) -> set[str]:
        return {
            str(value)
            for value in TimelineEvent.objects.filter(
                metadata__sourceProject=source_project,
                metadata__sourceTable=source_table,
            ).values_list("metadata__sourceId", flat=True)
        }

    def preview(self) -> dict[str, Any]:
        rows = self._legacy_rows()
        existing_legacy = self._existing_source_ids(SOURCE_PROJECT, LEGACY_TABLE)
        existing_curated = self._existing_source_ids(CURATED_SOURCE_PROJECT, CURATED_TABLE)
        missing_images = [
            str(row["immagine"])
            for row in rows
            if row["immagine"] and not (self.source_root / "media" / str(row["immagine"])).is_file()
        ]
        return {
            "mode": "dry-run",
            "campaign": self.campaign.nome,
            "legacy": {
                "total": len(rows),
                "alreadyImported": sum(str(row["id"]) in existing_legacy for row in rows),
                "missingImages": missing_images,
            },
            "curatedTesLore": {
                "total": len(CURATED_TIMELINE_EVENTS),
                "alreadyImported": sum(
                    event["sourceId"] in existing_curated
                    for event in CURATED_TIMELINE_EVENTS
                ),
                "withImages": 0,
            },
        }

    def _timeline_image(self, row: sqlite3.Row) -> UploadedImage | None:
        relative = str(row["immagine"] or "").strip().lstrip("/")
        if not relative:
            return None
        existing = UploadedImage.objects.filter(
            metadata__sourceProject=SOURCE_PROJECT,
            metadata__sourceTable=LEGACY_TABLE,
            metadata__sourceId=str(row["id"]),
        ).first()
        if existing is not None:
            return existing

        file_path = self.source_root / "media" / relative
        if not file_path.is_file():
            raise CommandError(f"Immagine Timeline Elder mancante: {relative}")
        category = ImageCategory.objects.filter(
            slug="scene-di-gioco",
            is_active=True,
            archived_at__isnull=True,
        ).first()
        if category is None:
            raise CommandError("Categoria immagini 'scene-di-gioco' non configurata.")

        asset = UploadedImage(
            title=str(row["nome"] or file_path.stem)[:180],
            folder="scene-di-gioco",
            usage_type="scene",
            category=category,
            group="Timeline",
            source=SOURCE_PROJECT,
            metadata={
                "sourceProject": SOURCE_PROJECT,
                "sourceTable": LEGACY_TABLE,
                "sourceId": str(row["id"]),
                "legacyImagePath": relative,
                "originalName": file_path.name,
                "sizeBytes": file_path.stat().st_size,
                "mimeType": mimetypes.guess_type(file_path.name)[0] or "image/*",
            },
        )
        with file_path.open("rb") as handle:
            asset.file.save(file_path.name, File(handle), save=False)
        asset.save()
        return asset

    @transaction.atomic
    def apply(self) -> dict[str, Any]:
        rows = self._legacy_rows()
        existing_legacy = self._existing_source_ids(SOURCE_PROJECT, LEGACY_TABLE)
        imported_legacy = 0
        imported_images = 0

        for row in rows:
            source_id = str(row["id"])
            if source_id in existing_legacy:
                continue
            image = self._timeline_image(row)
            imported_images += int(image is not None)
            year = int(row["data_evento"])
            TimelineEvent.objects.create(
                campagna=self.campaign,
                nome=str(row["nome"] or "").strip()[:180] or "Evento",
                data_evento=str(year),
                ordine_cronologico=year,
                immagine=image,
                descrizione=str(row["descrizione"] or ""),
                tags=["TES", "Timeline Elder"],
                metadata={
                    "sourceProject": SOURCE_PROJECT,
                    "sourceTable": LEGACY_TABLE,
                    "sourceId": source_id,
                },
            )
            imported_legacy += 1

        existing_curated = self._existing_source_ids(CURATED_SOURCE_PROJECT, CURATED_TABLE)
        imported_curated = 0
        for event in CURATED_TIMELINE_EVENTS:
            source_id = str(event["sourceId"])
            if source_id in existing_curated:
                continue
            TimelineEvent.objects.create(
                campagna=self.campaign,
                nome=event["title"],
                data_evento=str(event["year"]),
                ordine_cronologico=event["year"],
                immagine=None,
                descrizione=event["description"],
                tags=event["tags"],
                metadata={
                    "sourceProject": CURATED_SOURCE_PROJECT,
                    "sourceTable": CURATED_TABLE,
                    "sourceId": source_id,
                    "sourceUrls": event["sourceUrls"],
                },
            )
            imported_curated += 1

        return {
            "mode": "apply",
            "campaign": self.campaign.nome,
            "legacyImported": imported_legacy,
            "curatedImported": imported_curated,
            "imagesImported": imported_images,
            "totalActive": TimelineEvent.objects.filter(
                campagna=self.campaign,
                archived_at__isnull=True,
            ).count(),
        }


__all__ = [
    "CURATED_TIMELINE_EVENTS",
    "DEFAULT_SOURCE_ROOT",
    "SOURCE_CAMPAIGN_NAME",
    "TimelineImporter",
]

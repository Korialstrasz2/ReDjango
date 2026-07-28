import sqlite3
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from backend.core.models import DatiCampagna, TimelineEvent
from backend.lore.timeline_import import CURATED_TIMELINE_EVENTS, TimelineImporter
from backend.media_library.models import ImageCategory, UploadedImage


class TimelineImporterTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.media_override = override_settings(MEDIA_ROOT=self.root / "target-media")
        self.media_override.enable()
        DatiCampagna.objects.create(nome="Sanguine")
        ImageCategory.objects.create(
            name="Scene di gioco",
            slug="scene-di-gioco",
            usage_types=["scene"],
            is_active=True,
        )
        source_media = self.root / "media" / "timeline_events"
        source_media.mkdir(parents=True)
        (source_media / "evento.jpg").write_bytes(b"timeline-image")
        connection = sqlite3.connect(self.root / "db.sqlite3")
        try:
            connection.execute(
                "CREATE TABLE django_slim_timelineevent "
                "(id INTEGER PRIMARY KEY, nome TEXT, data_evento INTEGER, immagine TEXT, descrizione TEXT)"
            )
            connection.execute(
                "INSERT INTO django_slim_timelineevent VALUES (?, ?, ?, ?, ?)",
                (7, "Evento Elder", -3, "timeline_events/evento.jpg", "Descrizione Elder"),
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        self.media_override.disable()
        self.temporary.cleanup()

    def _apply(self):
        importer = TimelineImporter(self.root)
        try:
            return importer.apply()
        finally:
            importer.close()

    def test_import_is_idempotent_and_curated_events_have_no_images(self):
        first = self._apply()
        second = self._apply()

        self.assertEqual(first["legacyImported"], 1)
        self.assertEqual(first["curatedImported"], 5)
        self.assertEqual(second["legacyImported"], 0)
        self.assertEqual(second["curatedImported"], 0)
        self.assertEqual(TimelineEvent.objects.count(), 6)
        self.assertEqual(UploadedImage.objects.count(), 1)
        self.assertEqual(
            TimelineEvent.objects.filter(metadata__sourceProject="tes_lore_curated", immagine__isnull=True).count(),
            5,
        )

    def test_curated_events_are_unique_ordered_and_source_backed(self):
        self.assertEqual([event["year"] for event in CURATED_TIMELINE_EVENTS], [-10, 7, 12, 16, 23])
        self.assertEqual(len({event["sourceId"] for event in CURATED_TIMELINE_EVENTS}), 5)
        self.assertTrue(all(event["sourceUrls"] for event in CURATED_TIMELINE_EVENTS))

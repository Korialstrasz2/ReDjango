import json
import sqlite3
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from PIL import Image

from backend.core.models import Unit

from .models import ImageCategory, UploadedImage


class LegacyUnitPortraitImportTests(TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.media_root = self.root / "media"
        self.source_directory = self.root / "pgs"
        self.source_directory.mkdir()
        self.legacy_database = self.root / "elder.sqlite3"
        self.staging_directory = self.root / "staging"
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        ImageCategory.objects.create(
            name="Personaggi",
            slug="personaggi",
            usage_types=["character_portrait"],
            is_active=True,
        )

    def tearDown(self):
        self.override.disable()
        self.temporary.cleanup()

    def create_source_database(self, rows):
        connection = sqlite3.connect(self.legacy_database)
        try:
            connection.execute(
                "CREATE TABLE django_slim_unit (id INTEGER PRIMARY KEY, nome TEXT NOT NULL)"
            )
            connection.executemany(
                "INSERT INTO django_slim_unit (id, nome) VALUES (?, ?)",
                rows,
            )
            connection.commit()
        finally:
            connection.close()

    def create_portrait(self, name="Lupo", *, valid=True, color=(10, 20, 30, 0)):
        path = self.source_directory / f"{name}.png"
        if valid:
            Image.new("RGBA", (7, 11), color).save(path, format="PNG")
        else:
            path.write_bytes(b"not-an-image")
        return path

    def command(self, *extra, stdout=None):
        call_command(
            "import_legacy_unit_portraits",
            "--source-dir",
            str(self.source_directory),
            "--legacy-database",
            str(self.legacy_database),
            "--staging-dir",
            str(self.staging_directory),
            "--expected-count",
            "1",
            *extra,
            stdout=stdout or StringIO(),
        )

    def command_with_expected_count(self, expected_count, *extra, stdout=None):
        call_command(
            "import_legacy_unit_portraits",
            "--source-dir",
            str(self.source_directory),
            "--legacy-database",
            str(self.legacy_database),
            "--staging-dir",
            str(self.staging_directory),
            "--expected-count",
            str(expected_count),
            *extra,
            stdout=stdout or StringIO(),
        )

    def test_dry_run_stages_valid_webp_and_manifest_without_database_writes(self):
        Unit.objects.create(
            nome="Lupo",
            metadata={"sourceProject": "the_elder_django", "sourceIds": [10]},
        )
        self.create_source_database([(10, "Lupo")])
        self.create_portrait()

        output = StringIO()
        self.command(stdout=output)

        self.assertEqual(UploadedImage.objects.count(), 0)
        manifest = json.loads((self.staging_directory / "manifest.json").read_text("utf-8"))
        self.assertEqual(manifest["summary"]["validated"], 1)
        self.assertEqual(manifest["summary"]["blocked"], 0)
        converted = Path(manifest["entries"][0]["convertedPath"])
        with Image.open(converted) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertEqual(image.size, (7, 11))
            self.assertEqual(image.mode, "RGBA")
        self.assertIn("Dry run completato", output.getvalue())

    def test_apply_links_unit_and_rerun_reuses_same_uploaded_image(self):
        unit = Unit.objects.create(
            nome="Lupo",
            metadata={"sourceProject": "the_elder_django", "sourceIds": [10]},
        )
        self.create_source_database([(10, "Lupo")])
        self.create_portrait()

        self.command("--apply")

        unit.refresh_from_db()
        asset = UploadedImage.objects.get()
        self.assertEqual(unit.lore_image_id, asset.id)
        self.assertEqual(asset.usage_type, "character_portrait")
        self.assertEqual(asset.category.slug, "personaggi")
        self.assertEqual(asset.group, "Unit e NPC")
        self.assertFalse(asset.visibilita_limitata)
        self.assertEqual(asset.source, "elder_django")
        self.assertEqual(asset.metadata["sourceIds"], [10])
        self.assertEqual(asset.metadata["conversion"]["quality"], 70)
        original_asset_id = asset.id
        original_file_name = asset.file.name

        self.command("--apply")

        unit.refresh_from_db()
        asset = UploadedImage.objects.get()
        self.assertEqual(asset.id, original_asset_id)
        self.assertEqual(asset.file.name, original_file_name)
        self.assertEqual(unit.lore_image_id, original_asset_id)

    def test_apply_refuses_missing_or_invalid_portrait_without_partial_records(self):
        Unit.objects.create(
            nome="Lupo",
            metadata={"sourceProject": "the_elder_django", "sourceIds": [10]},
        )
        self.create_source_database([(10, "Lupo")])

        with self.assertRaises(CommandError):
            self.command("--apply")
        self.assertEqual(UploadedImage.objects.count(), 0)

        self.create_portrait(valid=False)
        with self.assertRaises(CommandError):
            self.command("--apply")
        self.assertEqual(UploadedImage.objects.count(), 0)
        manifest = json.loads((self.staging_directory / "manifest.json").read_text("utf-8"))
        self.assertIn("conversion_failed", manifest["entries"][0]["blockers"])

    def test_explicit_partial_apply_imports_valid_portraits_and_leaves_missing_unit_unlinked(self):
        valid_unit = Unit.objects.create(
            nome="Lupo",
            metadata={"sourceProject": "the_elder_django", "sourceIds": [10]},
        )
        missing_unit = Unit.objects.create(
            nome="Sfera Dwemer",
            metadata={"sourceProject": "the_elder_django", "sourceIds": [11]},
        )
        self.create_source_database([(10, "Lupo"), (11, "Sfera Dwemer")])
        self.create_portrait()

        self.command_with_expected_count(2, "--apply", "--allow-partial")

        valid_unit.refresh_from_db()
        missing_unit.refresh_from_db()
        self.assertIsNotNone(valid_unit.lore_image_id)
        self.assertIsNone(missing_unit.lore_image_id)
        self.assertEqual(UploadedImage.objects.count(), 1)

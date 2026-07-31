import io
import shutil
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings
from PIL import Image

from backend.core.legacy_race_media_import import (
    MAXIMUM_EDGE,
    import_race_media,
    plan_race_media,
    to_webp,
)
from backend.core.models import NomiRazzeInfo
from backend.core.naming_selectors import name_catalog_payload
from backend.media_library.models import UploadedImage, VideoClip


def _png(path: Path, size: tuple[int, int] = (1024, 1024)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (90, 40, 30)).save(path, "PNG")


def _fake_clip(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Non serve un mp4 valido: l'importatore copia byte, non decodifica.
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 512)


class WebpConversionTests(TestCase):
    def test_a_large_png_becomes_a_much_smaller_capped_webp(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "nord-gen.png"
            _png(source, (1600, 1200))
            converted = to_webp(source)
        with Image.open(io.BytesIO(converted)) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertLessEqual(max(image.size), MAXIMUM_EDGE)
        self.assertLess(len(converted), source.stat().st_size if source.exists() else 10**9)

    def test_transparency_survives_the_conversion(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "clear.png"
            source.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGBA", (800, 800), (10, 20, 30, 0)).save(source, "PNG")
            converted = to_webp(source)
        with Image.open(io.BytesIO(converted)) as image:
            self.assertIn("A", image.mode)


class RaceMediaImportTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, True)
        self.source = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.source, True)

        assets = self.source / "static" / "media" / "images" / "razze"
        # Il progetto Elder mescola le maiuscole: «orco-gen.png» minuscolo,
        # «Ashlander-m.png» capitalizzato. La ricerca deve ignorare il caso.
        _png(assets / "orco-gen.png")
        _png(assets / "gruppi" / "Orsimer-m.png")
        _png(assets / "gruppi" / "Orsimer-f.png")
        _fake_clip(assets / "gruppi" / "video" / "Orsimer-m-1.mp4")
        _fake_clip(assets / "gruppi" / "video" / "Orsimer-f-1.mp4")

        self.culture = NomiRazzeInfo.objects.create(
            name="Orsimer",
            race="Orsimer",
            names_male=["Mog"],
            names_female=["Atub"],
            surnames=["Burz"],
            metadata={"legacyName": "Orco"},
        )
        self.stronghold = NomiRazzeInfo.objects.create(
            name="Stronghold", race="Orsimer", names_male=["Hadrug"], names_female=["Bagrak"]
        )

    def test_the_plan_finds_assets_despite_mixed_case_and_the_race_alias(self):
        plan = plan_race_media(self.source)
        entry = plan["Orsimer"]
        # Il ritratto di razza è salvato col nome Elder «orco-gen.png».
        self.assertEqual(entry["racePortrait"].name, "orco-gen.png")
        self.assertEqual(entry["image_m"].name, "Orsimer-m.png")
        self.assertEqual(entry["clip_f"].name, "Orsimer-f-1.mp4")

    def test_a_culture_without_assets_is_reported_not_invented(self):
        plan = plan_race_media(self.source)
        self.assertIsNone(plan["Stronghold"]["image_m"])
        # La razza è la stessa, quindi il ritratto di razza c'è comunque.
        self.assertIsNotNone(plan["Stronghold"]["racePortrait"])

    def test_import_links_images_clips_and_the_shared_race_portrait(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            report = import_race_media(self.source)
        self.assertEqual(report.races, 1)
        self.assertEqual(report.culture_images, 2)
        self.assertEqual(report.clips, 2)

        culture = NomiRazzeInfo.objects.get(pk=self.culture.pk)
        self.assertTrue(culture.immagine_maschile.file.name.endswith(".webp"))
        self.assertEqual(culture.immagine_maschile.usage_type, "race_portrait")
        self.assertTrue(culture.clip_maschile.file.name.endswith(".mp4"))
        # Il poster della clip è il ritratto dello stesso sesso.
        self.assertEqual(culture.clip_maschile.poster_id, culture.immagine_maschile_id)

        # Il ritratto di razza è ripetuto su tutte le culture della razza, perché
        # la razza non ha una tabella propria da cui leggerlo.
        stronghold = NomiRazzeInfo.objects.get(pk=self.stronghold.pk)
        self.assertEqual(stronghold.immagine_razza_id, culture.immagine_razza_id)
        self.assertIsNone(stronghold.immagine_maschile)

    def test_reimporting_updates_instead_of_duplicating(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            import_race_media(self.source)
            first = UploadedImage.objects.count()
            first_clips = VideoClip.objects.count()
            import_race_media(self.source)
        self.assertEqual(UploadedImage.objects.count(), first)
        self.assertEqual(VideoClip.objects.count(), first_clips)

    def test_the_catalog_exposes_urls_for_every_level(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            import_race_media(self.source)
            payload = name_catalog_payload()
        race = next(entry for entry in payload["races"] if entry["race"] == "Orsimer")
        self.assertTrue(race["image"].endswith(".webp"))
        orsimer = next(entry for entry in race["cultures"] if entry["name"] == "Orsimer")
        self.assertTrue(orsimer["images"]["maschile"].endswith(".webp"))
        self.assertTrue(orsimer["clips"]["femminile"].endswith(".mp4"))
        # Una cultura senza asset restituisce stringhe vuote, non URL rotti.
        stronghold = next(entry for entry in race["cultures"] if entry["name"] == "Stronghold")
        self.assertEqual(stronghold["images"], {"maschile": "", "femminile": ""})

    def test_the_catalog_stays_one_query_with_media_joined(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            import_race_media(self.source)
            with self.assertNumQueries(1):
                name_catalog_payload()

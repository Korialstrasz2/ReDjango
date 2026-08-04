import copy
import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from backend.core.models import DatiCampagna, Giocatore

from .models import AudioFile, DatiMappa, UploadedImage, VideoClip
from .cache_package import verify_package_document


class MediaCacheManifestTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = TemporaryDirectory()
        cls.base_root = TemporaryDirectory()
        static_root = Path(cls.base_root.name) / "frontend" / "static" / "frontend"
        (static_root / "images" / "items").mkdir(parents=True)
        (static_root / "images" / "items" / "icona.webp").write_bytes(b"static-icon")
        (static_root / "audio").mkdir()
        (static_root / "audio" / "avviso.m4a").write_bytes(b"static-audio")
        (static_root / "service-worker.js").write_text("self.addEventListener('fetch', () => {});", encoding="utf-8")
        cls.override = override_settings(MEDIA_ROOT=cls.media_root.name, BASE_DIR=Path(cls.base_root.name))
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        cls.base_root.cleanup()
        cls.media_root.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.campaign = DatiCampagna.objects.create(nome="Cache Test", attiva=True)
        self.other_campaign = DatiCampagna.objects.create(nome="Altra")
        self.user = get_user_model().objects.create_user(username="cache_player")
        self.player = Giocatore.objects.create(
            user=self.user,
            nome=self.user.username,
            role=Giocatore.ROLE_USER,
            active_campaign=self.campaign,
        )
        self.client.force_login(self.user)

    def image(self, title: str, *, campaign=None, limited=False, rendered=False):
        content = b"image"
        if rendered:
            output = BytesIO()
            Image.new("RGB", (600, 520), "#466f85").save(output, format="WEBP")
            content = output.getvalue()
        return UploadedImage.objects.create(
            title=title,
            folder="cache-test",
            campagna=campaign,
            visibilita_limitata=limited,
            file=SimpleUploadedFile(f"{title}.webp", content, content_type="image/webp"),
        )

    def test_manifest_is_scoped_deduplicated_and_never_contains_restricted_media(self):
        shared = self.image("Condivisa")
        campaign_image = self.image("Campagna", campaign=self.campaign)
        other = self.image("Altra campagna", campaign=self.other_campaign)
        restricted = self.image("Riservata", campaign=self.campaign, limited=True)
        map_image = self.image("Mappa", campaign=self.campaign, rendered=True)
        DatiMappa.objects.create(nome="Mappa globale", campagna=self.campaign, image=map_image, tipo="globale")
        audio = AudioFile.objects.create(title="Tema")
        audio.file.save("tema.mp3", SimpleUploadedFile("tema.mp3", b"audio", content_type="audio/mpeg"))
        video = VideoClip.objects.create(title="Clip")
        video.file.save("clip.mp4", SimpleUploadedFile("clip.mp4", b"video", content_type="video/mp4"))

        response = self.client.get("/api/media/cache-manifest/")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["scope"], f"user-{self.user.id}-campaign-{self.campaign.id}")
        urls = [entry["url"] for entry in data["entries"]]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertIn(shared.file.url, urls)
        self.assertIn(campaign_image.file.url, urls)
        self.assertIn(map_image.file.url, urls)
        self.assertIn(audio.file.url, urls)
        self.assertIn(video.file.url, urls)
        self.assertIn("/static/frontend/images/items/icona.webp", urls)
        self.assertIn("/static/frontend/audio/avviso.m4a", urls)
        self.assertNotIn(other.file.url, urls)
        self.assertNotIn(restricted.file.url, urls)
        self.assertTrue(any(entry["kind"] == "map_tile" for entry in data["entries"]))
        self.assertEqual(data["totalBytes"], sum(entry["size"] for entry in data["entries"]))

    def test_manifest_and_service_worker_require_the_expected_access_contract(self):
        self.client.logout()
        self.assertEqual(self.client.get("/api/media/cache-manifest/").status_code, 401)
        worker = self.client.get("/service-worker.js")
        self.assertEqual(worker.status_code, 200)
        self.assertEqual(worker.headers["Service-Worker-Allowed"], "/")
        self.assertEqual(worker.headers["Cache-Control"], "no-cache")

    def test_admin_can_export_and_player_can_verify_a_signed_stored_package(self):
        self.player.role = Giocatore.ROLE_ADMIN
        self.player.save(update_fields=["role", "updated_at"])
        shared = self.image("Da esportare", campaign=self.campaign)
        restricted = self.image("Mai esportare", campaign=self.campaign, limited=True)

        response = self.client.get("/api/media/cache-package/")

        self.assertEqual(response.status_code, 200)
        archive_bytes = b"".join(response.streaming_content)
        response.close()
        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist()))
            document = json.loads(archive.read("redjango-media-package.json"))
            urls = {entry["url"] for entry in document["payload"]["files"]}
            self.assertIn(shared.file.url, urls)
            self.assertIn("/static/frontend/images/items/icona.webp", urls)
            self.assertNotIn(restricted.file.url, urls)
            for entry in document["payload"]["files"]:
                content = archive.read(entry["archivePath"])
                self.assertEqual(len(content), entry["size"])
                self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])

        allowed = {
            entry["cacheKey"]: entry
            for entry in self.client.get("/api/media/cache-manifest/").json()["data"]["entries"]
        }
        static_entry = next(entry for entry in document["payload"]["files"] if entry["kind"] == "static_media")
        fingerprinted_url = "/static/frontend/images/items/icona.123456789abc.webp"
        allowed[static_entry["cacheKey"]] = {**allowed[static_entry["cacheKey"]], "url": fingerprinted_url}
        resolved = verify_package_document(
            document,
            campaign_id=self.campaign.id,
            allowed_entries=allowed,
        )
        resolved_static = next(entry for entry in resolved["resolvedFiles"] if entry["archivePath"] == static_entry["archivePath"])
        self.assertEqual(resolved_static["url"], fingerprinted_url)

        verify = self.client.post(
            "/api/media/cache-package/verify/",
            data=json.dumps({"package": document}),
            content_type="application/json",
        )
        self.assertEqual(verify.status_code, 200)
        self.assertEqual(len(verify.json()["data"]["files"]), len(document["payload"]["files"]))

        tampered = copy.deepcopy(document)
        tampered["payload"]["files"][0]["label"] = "Alterato"
        rejected = self.client.post(
            "/api/media/cache-package/verify/",
            data=json.dumps({"package": tampered}),
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.json()["errors"][0]["code"], "media.package_invalid")

    def test_package_export_is_admin_only_and_old_restricted_content_is_rejected(self):
        self.assertEqual(self.client.get("/api/media/cache-package/").status_code, 403)
        self.player.role = Giocatore.ROLE_ADMIN
        self.player.save(update_fields=["role", "updated_at"])
        image = self.image("Diventa riservata", campaign=self.campaign)
        response = self.client.get("/api/media/cache-package/")
        archive_bytes = b"".join(response.streaming_content)
        response.close()
        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            document = json.loads(archive.read("redjango-media-package.json"))

        image.visibilita_limitata = True
        image.save(update_fields=["visibilita_limitata", "updated_at"])
        rejected = self.client.post(
            "/api/media/cache-package/verify/",
            data=json.dumps({"package": document}),
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("non disponibili", rejected.json()["errors"][0]["message"])

from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from backend.core.models import DatiCampagna, Giocatore

from .models import AudioFile, DatiMappa, UploadedImage, VideoClip


class MediaCacheManifestTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = TemporaryDirectory()
        cls.override = override_settings(MEDIA_ROOT=cls.media_root.name)
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
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

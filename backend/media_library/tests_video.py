import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from backend.core.models import Giocatore

from .models import VideoClip


class ProtectedVideoServingTests(TestCase):
    """Le clip del generatore nomi devono riprodursi, non scaricarsi."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.TemporaryDirectory()
        cls.override = override_settings(MEDIA_ROOT=cls.media_root.name)
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        cls.media_root.cleanup()
        super().tearDownClass()

    def setUp(self):
        user = get_user_model().objects.create_user(username="video_viewer")
        Giocatore.objects.create(user=user, nome=user.username, display_name="Spettatore", role=Giocatore.ROLE_USER)
        self.client.force_login(user)
        clip = VideoClip.objects.create(title="Telvanni · Maschile", usage_type="race_clip")
        clip.file.save("telvanni-m.mp4", SimpleUploadedFile("telvanni-m.mp4", b"0123456789", content_type="video/mp4"))
        self.clip = clip

    def test_an_mp4_is_served_inline_so_the_browser_can_play_it(self):
        response = self.client.get(self.clip.file.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "video/mp4")
        # Con `attachment` il browser scaricherebbe il file invece di riprodurlo.
        self.assertNotIn("attachment", response.headers.get("Content-Disposition", ""))
        self.assertEqual(response.headers["Accept-Ranges"], "bytes")

    def test_seeking_inside_a_clip_returns_only_the_requested_bytes(self):
        response = self.client.get(self.clip.file.url, headers={"range": "bytes=2-5"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["Content-Range"], "bytes 2-5/10")
        self.assertEqual(response.headers["Content-Length"], "4")
        self.assertEqual(b"".join(response.streaming_content), b"2345")

    def test_an_anonymous_visitor_cannot_read_a_clip(self):
        self.client.logout()
        self.assertIn(self.client.get(self.clip.file.url).status_code, (302, 403, 404))

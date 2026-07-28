import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from backend.core.models import Giocatore

from .models import AudioFile


def audio_envelope(request_id: str, payload: dict | None = None) -> str:
    return json.dumps(
        {
            "action": "audio.uploadTrack",
            "requestId": request_id,
            "context": {"screen": "audio"},
            "payload": payload or {},
            "meta": {"clientVersion": "test"},
        }
    )


def action_envelope(action: str, request_id: str, payload: dict) -> str:
    return json.dumps(
        {
            "action": action,
            "requestId": request_id,
            "context": {"screen": "audio"},
            "payload": payload,
            "meta": {"clientVersion": "test"},
        }
    )


class AudioLibraryApiTests(TestCase):
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
        self.master = self.login("audio_master", Giocatore.ROLE_MASTER)

    def login(self, username: str, role: str):
        user = get_user_model().objects.create_user(username=username)
        Giocatore.objects.create(user=user, nome=username, display_name=username, role=role)
        self.client.force_login(user)
        return user

    def upload(self, name: str = "taverna.mp3", title: str = "Taverna del Cinghiale", tags=("musica", "taverna"), content_type: str = "audio/mpeg"):
        uploaded = SimpleUploadedFile(name, b"ID3-not-really-audio", content_type=content_type)
        return self.client.post(
            "/api/audio/tracks/",
            data={
                "envelope": audio_envelope("audio-upload-1", {"title": title, "tags": list(tags), "durationSeconds": 184.5}),
                "file": uploaded,
            },
            HTTP_X_REDJANGO_ACTION="audio.uploadTrack",
            HTTP_X_REDJANGO_REQUEST_ID="audio-upload-1",
        )

    def test_master_uploads_and_lists_a_track(self):
        response = self.upload()

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["requestId"], "audio-upload-1")
        track = body["data"]["track"]
        self.assertEqual(track["title"], "Taverna del Cinghiale")
        self.assertEqual(track["tags"], ["musica", "taverna"])
        self.assertEqual(track["tagLabels"], ["Musica", "Taverna"])
        self.assertAlmostEqual(track["durationSeconds"], 184.5)
        self.assertTrue(track["url"].startswith("/media/v2/audio/musica/"))

        stored = AudioFile.objects.get()
        self.assertEqual(stored.primary_tag, "musica")

        listing = self.client.get("/api/audio/tracks/")
        self.assertEqual(listing.status_code, 200)
        data = listing.json()["data"]
        self.assertEqual(len(data["tracks"]), 1)
        self.assertTrue(data["canManage"])
        self.assertIn({"value": "ambient", "label": "Ambient"}, data["tags"])

    def test_player_may_listen_but_not_manage(self):
        self.upload()
        self.login("audio_player", Giocatore.ROLE_USER)

        listing = self.client.get("/api/audio/tracks/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()["data"]["tracks"]), 1)
        self.assertFalse(listing.json()["data"]["canManage"])

        denied = self.upload(name="vietata.mp3", title="Vietata")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["errors"][0]["code"], "audio.master_required")
        self.assertEqual(AudioFile.objects.count(), 1)

    def test_unknown_tag_and_unsupported_format_are_rejected(self):
        rejected_tag = self.client.post(
            "/api/audio/tracks/",
            data={
                "envelope": audio_envelope("audio-upload-2", {"title": "Ignota", "tags": ["sconosciuto"]}),
                "file": SimpleUploadedFile("ignota.mp3", b"bytes", content_type="audio/mpeg"),
            },
        )
        self.assertEqual(rejected_tag.status_code, 400)
        self.assertEqual(rejected_tag.json()["errors"][0]["code"], "audio.tag_unknown")

        rejected_format = self.client.post(
            "/api/audio/tracks/",
            data={
                "envelope": audio_envelope("audio-upload-3", {"title": "Documento"}),
                "file": SimpleUploadedFile("appunti.txt", b"testo", content_type="text/plain"),
            },
        )
        self.assertEqual(rejected_format.status_code, 400)
        self.assertEqual(rejected_format.json()["errors"][0]["code"], "audio.format_unsupported")
        self.assertEqual(AudioFile.objects.count(), 0)

    def test_master_renames_retags_and_deletes_a_track(self):
        track_id = self.upload().json()["data"]["track"]["id"]
        stored_path = Path(AudioFile.objects.get(pk=track_id).file.path)
        self.assertTrue(stored_path.is_file())

        renamed = self.client.patch(
            f"/api/audio/tracks/{track_id}/",
            data=action_envelope("audio.updateTrack", "audio-update-1", {"title": "Taverna silenziosa", "tags": ["ambient"]}),
            content_type="application/json",
        )
        self.assertEqual(renamed.status_code, 200)
        updated = renamed.json()["data"]["track"]
        self.assertEqual(updated["title"], "Taverna silenziosa")
        self.assertEqual(updated["tags"], ["ambient"])
        self.assertEqual(AudioFile.objects.get(pk=track_id).primary_tag, "ambient")

        deleted = self.client.delete(f"/api/audio/tracks/{track_id}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["data"]["tracks"], [])
        self.assertEqual(AudioFile.objects.count(), 0)
        self.assertFalse(stored_path.is_file())

    def test_missing_track_answers_with_a_friendly_error(self):
        response = self.client.delete("/api/audio/tracks/9999/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["errors"][0]["code"], "audio.track_not_found")


class ProtectedAudioStreamTests(TestCase):
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
        user = get_user_model().objects.create_user(username="audio_listener")
        Giocatore.objects.create(user=user, nome=user.username, display_name="Ascoltatore", role=Giocatore.ROLE_USER)
        self.client.force_login(user)
        track = AudioFile.objects.create(title="Bosco", tags=["ambient"], primary_tag="ambient")
        track.file.save("bosco.mp3", SimpleUploadedFile("bosco.mp3", b"0123456789", content_type="audio/mpeg"))
        self.track = track

    def test_full_response_advertises_range_support(self):
        response = self.client.get(self.track.file.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Accept-Ranges"], "bytes")
        self.assertEqual(response.headers["Content-Type"], "audio/mpeg")
        self.assertNotIn("attachment", response.headers.get("Content-Disposition", ""))
        self.assertEqual(b"".join(response.streaming_content), b"0123456789")

    def test_seeking_returns_only_the_requested_bytes(self):
        response = self.client.get(self.track.file.url, headers={"range": "bytes=4-6"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["Content-Range"], "bytes 4-6/10")
        self.assertEqual(response.headers["Content-Length"], "3")
        self.assertEqual(b"".join(response.streaming_content), b"456")

    def test_open_ended_and_suffix_ranges_are_understood(self):
        open_ended = self.client.get(self.track.file.url, headers={"range": "bytes=8-"})
        self.assertEqual(open_ended.status_code, 206)
        self.assertEqual(open_ended.headers["Content-Range"], "bytes 8-9/10")
        self.assertEqual(b"".join(open_ended.streaming_content), b"89")

        suffix = self.client.get(self.track.file.url, headers={"range": "bytes=-3"})
        self.assertEqual(suffix.status_code, 206)
        self.assertEqual(suffix.headers["Content-Range"], "bytes 7-9/10")
        self.assertEqual(b"".join(suffix.streaming_content), b"789")

    def test_unsatisfiable_range_is_refused(self):
        response = self.client.get(self.track.file.url, headers={"range": "bytes=50-60"})
        self.assertEqual(response.status_code, 416)
        self.assertEqual(response.headers["Content-Range"], "bytes */10")

    def test_anonymous_visitors_never_reach_the_stream(self):
        self.client.logout()
        response = self.client.get(self.track.file.url)
        self.assertIn(response.status_code, {302, 403})

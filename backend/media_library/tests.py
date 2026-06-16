import json
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import UserMediaAsset


def media_envelope(request_id: str, payload: dict | None = None) -> str:
    return json.dumps(
        {
            "action": "media.upload",
            "requestId": request_id,
            "context": {"screen": "media"},
            "payload": payload or {},
            "meta": {"clientVersion": "test"},
        }
    )


class MediaApiContractTests(TestCase):
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

    def test_upload_accepts_multipart_envelope_and_returns_envelope(self):
        uploaded = SimpleUploadedFile("map.txt", b"north gate", content_type="text/plain")

        response = self.client.post(
            "/api/media/",
            data={
                "envelope": media_envelope("media-upload-1", {"title": "Gate Map", "notes": "Starter note"}),
                "file": uploaded,
            },
            HTTP_X_REDJANGO_ACTION="media.upload",
            HTTP_X_REDJANGO_REQUEST_ID="media-upload-1",
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["requestId"], "media-upload-1")
        self.assertEqual(body["events"][0]["type"], "media.uploaded")
        asset = body["data"]["asset"]
        self.assertEqual(asset["title"], "Gate Map")
        self.assertEqual(asset["notes"], "Starter note")
        self.assertEqual(asset["mimeType"], "text/plain")
        self.assertEqual(UserMediaAsset.objects.count(), 1)

    def test_missing_upload_returns_structured_error(self):
        response = self.client.post(
            "/api/media/",
            data={"envelope": media_envelope("media-missing-1", {"title": "No File"})},
            HTTP_X_REDJANGO_ACTION="media.upload",
            HTTP_X_REDJANGO_REQUEST_ID="media-missing-1",
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["requestId"], "media-missing-1")
        self.assertEqual(body["errors"][0]["code"], "media.file_required")
        self.assertEqual(body["errors"][0]["field"], "file")

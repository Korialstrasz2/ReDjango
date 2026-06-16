from django.test import TestCase


ENVELOPE_KEYS = {"ok", "requestId", "data", "events", "warnings", "errors"}


class CoreContractTests(TestCase):
    def test_health_uses_response_envelope(self):
        response = self.client.get("/api/health/", HTTP_X_REDJANGO_REQUEST_ID="health-1")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(ENVELOPE_KEYS.issubset(body))
        self.assertTrue(body["ok"])
        self.assertEqual(body["requestId"], "health-1")
        self.assertEqual(body["data"]["service"], "ReDjango")
        self.assertEqual(body["data"]["status"], "ready")

    def test_shell_declares_component_identity(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        for marker in [
            'data-component-type="app-shell"',
            'data-component-type="nav"',
            'data-component-type="view"',
            'data-component-type="form"',
            'data-theme="media"',
        ]:
            with self.subTest(marker=marker):
                self.assertIn(marker, html)

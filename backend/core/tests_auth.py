import json
import os
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from redjango.public_origin import parse_public_origin

from .access import online_configuration_errors, schedule_managed_restart
from .models import Giocatore, LoginThrottle, SettingDefinition, SettingOverride
from .request_security import client_ip


def create_access_mode_setting(value="locked"):
    return SettingDefinition.objects.create(
        key="security.access_mode",
        label="Modalità di accesso",
        category="sicurezza",
        description="Modalità di esposizione del server.",
        minimum_role=Giocatore.ROLE_ADMIN,
        value_type=SettingDefinition.TYPE_SELECT,
        default_value="locked",
        value=value,
        choices=[
            {"value": "locked", "label": "Bloccata"},
            {"value": "lan", "label": "LAN"},
            {"value": "online", "label": "Online"},
        ],
    )


@override_settings(REDJANGO_ACCESS_MODE="locked")
class AuthenticationBoundaryTests(TestCase):
    def setUp(self):
        create_access_mode_setting()
        self.user = get_user_model().objects.create_user(
            username="player-one",
            password="correct-horse-battery",
        )

    def login(self, username="player-one", password="correct-horse-battery", **extra):
        self.client.get("/api/auth/session/", **extra)
        return self.client.post(
            "/api/auth/login/",
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json",
            **extra,
        )

    def test_anonymous_requests_only_receive_the_login_surface(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 302)
        self.assertEqual(page.headers["Location"], "/login/?next=/")

        api = self.client.get("/api/bootstrap/", HTTP_ACCEPT="application/json")
        self.assertEqual(api.status_code, 401)
        self.assertEqual(api.json()["errors"][0]["code"], "auth.login_required")

        login_page = self.client.get("/login/")
        self.assertEqual(login_page.status_code, 200)
        self.assertContains(login_page, 'id="app"')

        admin = self.client.get("/admin/")
        self.assertEqual(admin.status_code, 302)
        self.assertTrue(admin.headers["Location"].startswith("/admin/login/"))

        session = self.client.get("/api/auth/session/")
        self.assertEqual(session.status_code, 200)
        self.assertFalse(session.json()["data"]["authenticated"])
        self.assertIn("csrftoken", session.cookies)

    def test_login_creates_a_linked_player_session_and_logout_closes_it(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["authenticated"])
        profile = Giocatore.objects.get(user=self.user)
        self.assertEqual(profile.nome, self.user.username)

        self.assertEqual(self.client.get("/api/bootstrap/").status_code, 200)
        logged_out = self.client.post("/api/auth/logout/")
        self.assertEqual(logged_out.status_code, 200)
        self.assertFalse(logged_out.json()["data"]["authenticated"])
        self.assertEqual(self.client.get("/api/bootstrap/").status_code, 401)

    def test_failed_logins_are_rate_limited_without_revealing_the_account(self):
        for _ in range(5):
            response = self.login(password="wrong-password")
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["errors"][0]["code"], "auth.invalid_credentials")
        limited = self.login(password="wrong-password")
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["errors"][0]["code"], "auth.too_many_attempts")
        self.assertEqual(LoginThrottle.objects.count(), 1)

    def test_django_admin_login_uses_the_same_shared_throttle(self):
        get_user_model().objects.create_superuser(
            username="admin-throttle",
            password="correct-horse-battery",
        )
        for _ in range(2):
            response = self.login(
                username="admin-throttle",
                password="wrong-password",
            )
            self.assertEqual(response.status_code, 401)
        for _ in range(3):
            response = self.client.post(
                "/admin/login/",
                {"username": "admin-throttle", "password": "wrong-password"},
            )
            self.assertEqual(response.status_code, 200)

        limited = self.client.post(
            "/admin/login/",
            {"username": "admin-throttle", "password": "wrong-password"},
        )
        self.assertEqual(limited.status_code, 429)
        self.assertIn("Retry-After", limited.headers)

    @override_settings(REDJANGO_TRUSTED_PROXIES=["10.0.0.0/8"])
    def test_client_ip_uses_forwarding_only_from_a_trusted_proxy(self):
        trusted_request = self.client.request().wsgi_request
        trusted_request.META.update({
            "REMOTE_ADDR": "10.0.0.5",
            "HTTP_X_FORWARDED_FOR": "198.51.100.25, 10.0.0.4",
        })
        self.assertEqual(client_ip(trusted_request), "198.51.100.25")

        direct_request = self.client.request().wsgi_request
        direct_request.META.update({
            "REMOTE_ADDR": "198.51.100.30",
            "HTTP_X_FORWARDED_FOR": "198.51.100.25",
        })
        self.assertEqual(client_ip(direct_request), "198.51.100.30")

    def test_locked_mode_rejects_even_the_login_surface_from_remote_addresses(self):
        page = self.client.get("/login/", REMOTE_ADDR="192.168.1.50")
        self.assertEqual(page.status_code, 403)
        api = self.client.get(
            "/api/auth/session/",
            REMOTE_ADDR="192.168.1.50",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(api.status_code, 403)
        self.assertEqual(api.json()["errors"][0]["code"], "security.locked_mode_remote")

    def test_spoofed_forwarded_headers_cannot_bypass_locked_mode(self):
        response = self.client.get(
            "/login/",
            REMOTE_ADDR="192.168.1.50",
            HTTP_X_FORWARDED_FOR="127.0.0.1",
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(REDJANGO_ACCESS_MODE="lan")
    def test_lan_mode_exposes_only_login_until_the_remote_user_authenticates(self):
        remote = {"REMOTE_ADDR": "192.168.1.50"}
        self.assertEqual(self.client.get("/login/", **remote).status_code, 200)
        self.assertEqual(
            self.client.get("/api/bootstrap/", HTTP_ACCEPT="application/json", **remote).status_code,
            401,
        )
        self.assertEqual(self.login(**remote).status_code, 200)
        self.assertEqual(self.client.get("/api/bootstrap/", **remote).status_code, 200)


@override_settings(REDJANGO_ACCESS_MODE="locked")
class AccessModeAdministrationTests(TestCase):
    def setUp(self):
        self.setting = create_access_mode_setting()
        self.user = get_user_model().objects.create_superuser(
            username="security-admin",
            password="correct-horse-battery",
        )
        self.profile = Giocatore.objects.create(
            user=self.user,
            nome=self.user.username,
            display_name="Security Admin",
            role=Giocatore.ROLE_ADMIN,
        )
        self.client.force_login(self.user)

    def test_access_mode_is_saved_globally_and_reports_a_pending_restart(self):
        with TemporaryDirectory() as temporary_directory, override_settings(
            BASE_DIR=Path(temporary_directory),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    "/api/settings/",
                    data=json.dumps({
                        "action": "settings.save",
                        "payload": {"settings": {"security.access_mode": "lan"}},
                    }),
                    content_type="application/json",
                )
            self.assertEqual(
                (Path(temporary_directory) / ".redjango-access-mode").read_text(
                    encoding="utf-8",
                ).strip(),
                "lan",
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.setting.refresh_from_db()
        self.assertEqual(self.setting.value, "lan")
        self.assertFalse(SettingOverride.objects.filter(setting=self.setting).exists())
        runtime = response.json()["data"]["runtime"]
        self.assertEqual(runtime["activeAccessMode"], "locked")
        self.assertEqual(runtime["configuredAccessMode"], "lan")
        self.assertTrue(runtime["restartRequired"])

    @patch("backend.core.system_views.schedule_managed_restart", return_value=True)
    def test_admin_can_request_a_controlled_restart_after_the_mode_changes(self, restart):
        self.setting.value = "lan"
        self.setting.save(update_fields=["value", "updated_at"])
        response = self.client.post("/api/system/restart/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["accepted"])
        restart.assert_called_once_with()

    def test_non_admin_cannot_restart_the_server(self):
        self.profile.role = Giocatore.ROLE_USER
        self.profile.save(update_fields=["role", "updated_at"])
        self.setting.value = "lan"
        self.setting.save(update_fields=["value", "updated_at"])
        response = self.client.post("/api/system/restart/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["errors"][0]["code"], "system.restart_forbidden")

    def test_online_mode_requires_production_secret_and_allowed_hosts(self):
        response = self.client.post(
            "/api/settings/",
            data=json.dumps({
                "action": "settings.save",
                "payload": {"settings": {"security.access_mode": "online"}},
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["errors"][0]["code"],
            "security.online_configuration_incomplete",
        )


class ManagedDeploymentTests(TestCase):
    def test_public_origin_is_normalized_for_reverse_proxy_configuration(self):
        origin = parse_public_origin(" HTTPS://Game-Host.Example.ts.net.:443/ ")
        self.assertIsNotNone(origin)
        self.assertEqual(origin.origin, "https://game-host.example.ts.net")
        self.assertEqual(origin.allowed_host, "game-host.example.ts.net")

    def test_public_origin_rejects_non_origin_and_insecure_values(self):
        for value in (
            "http://game.example.ts.net",
            "https://game.example.ts.net/path",
            "https://user:secret@game.example.ts.net",
            "https://game.example.ts.net?debug=1",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_public_origin(value)

    def test_online_configuration_accepts_public_origin_instead_of_host_lists(self):
        with patch.dict(os.environ, {
            "REDJANGO_SECRET_KEY": "s" * 60,
            "REDJANGO_PUBLIC_ORIGIN": "https://game.example.ts.net",
            "REDJANGO_ALLOWED_HOSTS": "",
        }):
            self.assertEqual(online_configuration_errors(), [])

    def test_online_configuration_rejects_an_invalid_public_origin(self):
        with patch.dict(os.environ, {
            "REDJANGO_SECRET_KEY": "s" * 60,
            "REDJANGO_PUBLIC_ORIGIN": "http://game.example.ts.net/path",
            "REDJANGO_ALLOWED_HOSTS": "",
        }):
            self.assertIn("REDJANGO_PUBLIC_ORIGIN valido", online_configuration_errors())

    def test_lan_certificate_is_generated_and_reused(self):
        with TemporaryDirectory() as temporary_directory, override_settings(
            BASE_DIR=Path(temporary_directory),
        ):
            output = StringIO()
            call_command("ensure_lan_certificate", stdout=output)
            ca_certificate = Path(temporary_directory) / ".redjango" / "tls" / "lan-ca.pem"
            certificate = Path(temporary_directory) / ".redjango" / "tls" / "lan-cert.pem"
            private_key = Path(temporary_directory) / ".redjango" / "tls" / "lan-key.pem"
            first_ca_certificate = ca_certificate.read_bytes()
            first_certificate = certificate.read_bytes()

            self.assertTrue(first_ca_certificate.startswith(b"-----BEGIN CERTIFICATE-----"))
            self.assertTrue(first_certificate.startswith(b"-----BEGIN CERTIFICATE-----"))
            self.assertTrue(private_key.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----"))
            self.assertIn("CA SHA-256:", output.getvalue())

            call_command("ensure_lan_certificate", stdout=StringIO())
            self.assertEqual(ca_certificate.read_bytes(), first_ca_certificate)
            self.assertEqual(certificate.read_bytes(), first_certificate)

    def test_managed_restart_writes_a_marker_before_interrupting_main(self):
        with TemporaryDirectory() as temporary_directory, override_settings(
            BASE_DIR=Path(temporary_directory),
        ), patch.dict(os.environ, {"REDJANGO_MANAGED_LAUNCHER": "1"}), patch(
            "backend.core.access.threading.Timer"
        ) as timer:
            self.assertTrue(schedule_managed_restart(delay_seconds=0.1))
            marker = Path(temporary_directory) / ".redjango-restart-requested"
            self.assertEqual(marker.read_text(encoding="utf-8"), "restart\n")
            timer.assert_called_once()
            timer.return_value.start.assert_called_once_with()

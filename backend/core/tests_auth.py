import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from .models import Giocatore, SettingDefinition, SettingOverride


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
        cache.clear()
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

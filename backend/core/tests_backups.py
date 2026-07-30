import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from backend.core.api import ApiError
from backend.core.backup_scheduler import BackupScheduler
from backend.core.backup_services import prune_backups, save_backup_configuration
from backend.core.models import Giocatore


class BackupManagementTests(TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.backup_directory = Path(self.temporary_directory.name) / "backups"
        self.settings_override = override_settings(
            REDJANGO_BACKUP_DIRECTORY=self.backup_directory,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.admin_user = get_user_model().objects.create_user(username="backup-admin")
        self.admin = Giocatore.objects.create(
            user=self.admin_user,
            nome="backup_admin",
            display_name="Admin Backup",
            role=Giocatore.ROLE_ADMIN,
        )
        self.master_user = get_user_model().objects.create_user(username="backup-master")
        self.master = Giocatore.objects.create(
            user=self.master_user,
            nome="backup_master",
            role=Giocatore.ROLE_MASTER,
        )
        self.client.force_login(self.admin_user)
        self.source_database = Path(self.temporary_directory.name) / "source.sqlite3"
        self._create_source_database()

    def _create_source_database(self):
        connection = sqlite3.connect(self.source_database)
        try:
            connection.executescript(
                """
                CREATE TABLE characters_personaggio (
                    id INTEGER PRIMARY KEY,
                    nome TEXT NOT NULL,
                    tipologia TEXT,
                    livello INTEGER,
                    monete INTEGER,
                    danno INTEGER,
                    tot TEXT,
                    zaino_id INTEGER,
                    archived_at TEXT
                );
                CREATE TABLE characters_zaino (
                    id INTEGER PRIMARY KEY,
                    slot_1_id INTEGER
                );
                CREATE TABLE core_oggetto (
                    id INTEGER PRIMARY KEY,
                    nome TEXT
                );
                CREATE TABLE characters_contenitoreinventario (
                    id INTEGER PRIMARY KEY,
                    nome TEXT,
                    capacita INTEGER,
                    personaggio_id INTEGER
                );
                CREATE TABLE characters_vocecontenitoreinventario (
                    id INTEGER PRIMARY KEY,
                    contenitore_id INTEGER,
                    slot INTEGER,
                    quantita INTEGER,
                    reagent_stock_key TEXT,
                    oggetto_id INTEGER
                );
                """
            )
            connection.executemany(
                "INSERT INTO core_oggetto (id, nome) VALUES (?, ?)",
                [(10, "Spada lunga"), (11, "Pozione maggiore")],
            )
            connection.execute(
                "INSERT INTO characters_zaino (id, slot_1_id) VALUES (?, ?)",
                [3, 10],
            )
            connection.execute(
                """
                INSERT INTO characters_personaggio
                    (id, nome, tipologia, livello, monete, danno, tot, zaino_id, archived_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [7, "Illaoi", "giocabile", 8, 125, 3, json.dumps({"pf": 42, "mana": 7}), 3, None],
            )
            connection.execute(
                """
                INSERT INTO characters_personaggio
                    (id, nome, tipologia, livello, monete, danno, tot, zaino_id, archived_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [8, "Archiviato", "npc", 1, 0, 0, "{}", None, "2026-07-01T00:00:00Z"],
            )
            connection.execute(
                """
                INSERT INTO characters_contenitoreinventario (id, nome, capacita, personaggio_id)
                VALUES (?, ?, ?, ?)
                """,
                [4, "Sacca personale", 15, 7],
            )
            connection.executemany(
                """
                INSERT INTO characters_vocecontenitoreinventario
                    (id, contenitore_id, slot, quantita, reagent_stock_key, oggetto_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (1, 4, 1, 2, "", 11),
                    (2, 4, 2, 4, "b3", None),
                ],
            )
            connection.commit()
        finally:
            connection.close()

    def command(self, action, payload):
        return self.client.post(
            "/api/v1/actions",
            data=json.dumps({
                "action": action,
                "requestId": "backup-test",
                "payload": payload,
            }),
            content_type="application/json",
        )

    def test_overview_and_actions_are_reserved_to_admins(self):
        response = self.client.get("/api/v1/management/backups")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["configuration"]["intervalMinutes"], 30)

        self.client.force_login(self.master_user)
        self.assertEqual(self.client.get("/api/v1/management/backups").status_code, 403)
        forbidden = self.command(
            "management.backups.saveSettings",
            {
                "configuration": {
                    "enabled": True,
                    "onStartup": True,
                    "intervalMinutes": 15,
                    "retentionCount": 5,
                }
            },
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_configuration_enforces_the_interval_and_retention_bounds(self):
        with self.assertRaises(ApiError) as error:
            save_backup_configuration(
                self.admin_user,
                self.admin,
                {
                    "enabled": True,
                    "onStartup": False,
                    "intervalMinutes": 4,
                    "retentionCount": 5,
                },
            )

        self.assertEqual(error.exception.code, "settings.below_minimum")

        response = self.command(
            "management.backups.saveSettings",
            {
                "configuration": {
                    "enabled": True,
                    "onStartup": False,
                    "intervalMinutes": 15,
                    "retentionCount": 2,
                }
            },
        )
        self.assertEqual(response.status_code, 200)
        configuration = response.json()["data"]["management"]["configuration"]
        self.assertEqual(configuration["intervalMinutes"], 15)
        self.assertEqual(configuration["retentionCount"], 2)

    def test_manual_backup_can_be_created_and_inspected(self):
        with patch(
            "backend.core.backup_services._sqlite_database_path",
            return_value=self.source_database,
        ):
            created = self.command(
                "management.backups.create",
                {"label": "Prima della battaglia"},
            )

        self.assertEqual(created.status_code, 200)
        management = created.json()["data"]["management"]
        backup_id = management["createdBackupId"]
        backup = next(entry for entry in management["backups"] if entry["id"] == backup_id)
        self.assertEqual(backup["label"], "Prima della battaglia")
        self.assertEqual(backup["createdBy"], "Admin Backup")
        self.assertTrue((self.backup_directory / f"{backup_id}.sqlite3").is_file())

        opened = self.command(
            "management.backups.inspect",
            {"backupId": backup_id, "characterId": 7},
        )

        self.assertEqual(opened.status_code, 200)
        inspection = opened.json()["data"]["management"]["inspection"]
        self.assertEqual(inspection["characterCount"], 1)
        self.assertEqual(inspection["characters"][0]["name"], "Illaoi")
        character = inspection["selectedCharacter"]
        self.assertEqual(character["backpack"][0]["name"], "Spada lunga")
        self.assertEqual(character["containers"][0]["entries"][0]["name"], "Pozione maggiore")
        self.assertEqual(character["containers"][0]["entries"][1]["name"], "Reagente Blu · livello 3")
        values = {entry["key"]: entry["value"] for entry in character["coreValues"]}
        self.assertEqual(values["pf"], 42)
        self.assertEqual(values["mana"], 7)

        deleted = self.command(
            "management.backups.delete",
            {"backupId": backup_id},
        )
        self.assertEqual(deleted.status_code, 200)
        remaining_ids = {
            entry["id"]
            for entry in deleted.json()["data"]["management"]["backups"]
        }
        self.assertNotIn(backup_id, remaining_ids)
        self.assertFalse((self.backup_directory / f"{backup_id}.sqlite3").exists())

    def test_retention_removes_only_managed_backup_files(self):
        self.backup_directory.mkdir(parents=True, exist_ok=True)
        backup_ids = [
            "redjango-backup-manual-20260730T100000000001Z-11111111",
            "redjango-backup-manual-20260730T110000000002Z-22222222",
            "redjango-backup-automatic-20260730T120000000003Z-33333333",
        ]
        for backup_id in backup_ids:
            (self.backup_directory / f"{backup_id}.sqlite3").write_bytes(b"snapshot")
        oldest_metadata = self.backup_directory / f"{backup_ids[0]}.json"
        oldest_metadata.write_text("{}", encoding="utf-8")
        legacy_backup = self.backup_directory / "db.before_timeline.sqlite3"
        legacy_backup.write_bytes(b"legacy")

        removed = prune_backups(2)

        self.assertEqual(removed, 1)
        self.assertFalse((self.backup_directory / f"{backup_ids[0]}.sqlite3").exists())
        self.assertFalse(oldest_metadata.exists())
        self.assertTrue((self.backup_directory / f"{backup_ids[1]}.sqlite3").exists())
        self.assertTrue((self.backup_directory / f"{backup_ids[2]}.sqlite3").exists())
        self.assertTrue(legacy_backup.exists())

    def test_scheduler_uses_server_uptime_for_startup_and_periodic_backups(self):
        class StopAfterFirstCheck:
            def __init__(self):
                self.calls = []

            def wait(self, timeout):
                self.calls.append(timeout)
                return len(self.calls) > 1

        scheduler = BackupScheduler()
        stop_event = StopAfterFirstCheck()
        scheduler._stop_event = stop_event
        scheduler._create_automatic_backup = Mock()
        configuration = {
            "enabled": True,
            "onStartup": True,
            "intervalMinutes": 5,
            "retentionCount": 12,
        }

        with patch(
            "backend.core.backup_scheduler.backup_configuration",
            side_effect=[configuration, configuration],
        ), patch(
            "backend.core.backup_scheduler.time.monotonic",
            side_effect=[0, 1, 302, 303],
        ):
            scheduler._run()

        self.assertEqual(scheduler._create_automatic_backup.call_count, 2)
        self.assertEqual(stop_event.calls, [30, 30])

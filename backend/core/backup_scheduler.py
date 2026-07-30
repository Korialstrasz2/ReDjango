from __future__ import annotations

import atexit
import logging
import threading
import time

from django.db import close_old_connections

from .backup_services import backup_configuration, create_backup


logger = logging.getLogger(__name__)


class BackupScheduler:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="redjango-backup-scheduler",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _create_automatic_backup(self) -> None:
        try:
            close_old_connections()
            create_backup(kind="automatic")
        except Exception:
            logger.exception("Backup automatico di ReDjango non riuscito")
        finally:
            close_old_connections()

    def _run(self) -> None:
        last_periodic_backup = time.monotonic()
        previously_enabled = False
        try:
            configuration = backup_configuration()
            if configuration["enabled"] and configuration["onStartup"]:
                self._create_automatic_backup()
                last_periodic_backup = time.monotonic()
            previously_enabled = bool(configuration["enabled"])
        except Exception:
            logger.exception("Impossibile inizializzare la pianificazione dei backup")

        while not self._stop_event.wait(30):
            try:
                configuration = backup_configuration()
                enabled = bool(configuration["enabled"])
                now = time.monotonic()
                if not enabled:
                    last_periodic_backup = now
                elif not previously_enabled:
                    last_periodic_backup = now
                elif now - last_periodic_backup >= int(configuration["intervalMinutes"]) * 60:
                    self._create_automatic_backup()
                    last_periodic_backup = time.monotonic()
                previously_enabled = enabled
            except Exception:
                logger.exception("Impossibile verificare la pianificazione dei backup")


_scheduler_lock = threading.Lock()
_scheduler: BackupScheduler | None = None


def start_backup_scheduler() -> None:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            return
        _scheduler = BackupScheduler()
        _scheduler.start()
        atexit.register(_scheduler.stop)

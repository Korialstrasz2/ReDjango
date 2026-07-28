import _thread
import os
import threading
from pathlib import Path

from django.conf import settings
from django.db import OperationalError, ProgrammingError


ACCESS_MODE_LOCKED = "locked"
ACCESS_MODE_LAN = "lan"
ACCESS_MODE_ONLINE = "online"
ACCESS_MODES = (ACCESS_MODE_LOCKED, ACCESS_MODE_LAN, ACCESS_MODE_ONLINE)
ACCESS_MODE_SETTING_KEY = "security.access_mode"
RESTART_MARKER_NAME = ".redjango-restart-requested"


def normalize_access_mode(value: object, fallback: str = ACCESS_MODE_LOCKED) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in ACCESS_MODES else fallback


def active_access_mode() -> str:
    return normalize_access_mode(getattr(settings, "REDJANGO_ACCESS_MODE", ACCESS_MODE_LOCKED))


def configured_access_mode() -> str:
    from .models import SettingDefinition

    try:
        setting = SettingDefinition.objects.filter(
            key=ACCESS_MODE_SETTING_KEY,
            active=True,
            archived_at__isnull=True,
        ).first()
    except (OperationalError, ProgrammingError):
        return ACCESS_MODE_LOCKED
    if setting is None:
        return ACCESS_MODE_LOCKED
    return normalize_access_mode(setting.base_value)


def restart_available() -> bool:
    return os.environ.get("REDJANGO_MANAGED_LAUNCHER", "0") == "1"


def persist_access_mode(value: object) -> str:
    mode = normalize_access_mode(value)
    state_path = Path(settings.BASE_DIR) / ".redjango-access-mode"
    temporary_path = state_path.with_suffix(".tmp")
    temporary_path.write_text(f"{mode}\n", encoding="utf-8")
    temporary_path.replace(state_path)
    return mode


def online_configuration_errors() -> list[str]:
    missing = []
    secret_key = os.environ.get("REDJANGO_SECRET_KEY", "").strip()
    if len(secret_key) < 50 or secret_key == "dev-only-redjango-secret-key":
        missing.append("REDJANGO_SECRET_KEY")
    if not os.environ.get("REDJANGO_ALLOWED_HOSTS", "").strip():
        missing.append("REDJANGO_ALLOWED_HOSTS")
    return missing


def runtime_access_payload() -> dict:
    active = active_access_mode()
    configured = configured_access_mode()
    return {
        "activeAccessMode": active,
        "configuredAccessMode": configured,
        "restartRequired": active != configured,
        "restartAvailable": restart_available(),
        "onlineReady": not online_configuration_errors(),
    }


def schedule_managed_restart(delay_seconds: float = 0.8) -> bool:
    if not restart_available():
        return False

    marker_path = Path(settings.BASE_DIR) / RESTART_MARKER_NAME
    marker_path.write_text("restart\n", encoding="utf-8")
    timer = threading.Timer(delay_seconds, _thread.interrupt_main)
    timer.daemon = True
    timer.start()
    return True

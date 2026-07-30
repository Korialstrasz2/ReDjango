from __future__ import annotations

import json
import logging
import re
import secrets
import sqlite3
import threading
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .api import ApiError
from .backup_defaults import (
    BACKUP_ENABLED_SETTING_KEY,
    BACKUP_INTERVAL_SETTING_KEY,
    BACKUP_ON_STARTUP_SETTING_KEY,
    BACKUP_RETENTION_SETTING_KEY,
    BACKUP_SETTING_DEFINITIONS,
)
from .models import Giocatore, SettingDefinition
from .security import effective_role, has_minimum_role
from .settings_services import validate_setting_value


logger = logging.getLogger(__name__)

BACKUP_ID_RE = re.compile(
    r"^redjango-backup-(automatic|manual)-(\d{8}T\d{12}Z)-([0-9a-f]{8})$"
)
BACKUP_FILE_GLOB = "redjango-backup-*.sqlite3"
BACKUP_KINDS = {"automatic", "manual"}
BACKUP_OPERATION_LOCK = threading.RLock()
CORE_VALUE_LABELS = (
    ("pf", "Punti ferita"),
    ("mana", "Mana"),
    ("energia", "Energia"),
    ("potere", "Potere"),
    ("pa", "Punti azione"),
    ("attacco", "Attacco"),
    ("difesa", "Difesa"),
    ("tier", "Tier"),
    ("forza", "Forza"),
    ("resistenza", "Resistenza"),
    ("velocita", "Velocità"),
    ("agilita", "Agilità"),
    ("intelligenza", "Intelligenza"),
    ("concentrazione", "Concentrazione"),
    ("personalita", "Personalità"),
    ("saggezza", "Saggezza"),
    ("fortuna", "Fortuna"),
    ("stanchezza", "Stanchezza"),
)


def _synchronized_backup_operation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with BACKUP_OPERATION_LOCK:
            return function(*args, **kwargs)

    return wrapped


def require_backup_admin(user, giocatore: Giocatore) -> None:
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_ADMIN):
        raise ApiError(
            "management.backups.forbidden",
            "Solo gli amministratori possono gestire e consultare i backup.",
            status=403,
        )


def backup_directory() -> Path:
    configured = getattr(settings, "REDJANGO_BACKUP_DIRECTORY", None)
    directory = Path(configured) if configured else Path(settings.BASE_DIR) / "backups"
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ApiError(
            "backups.directory_unavailable",
            "La cartella dei backup non è disponibile.",
            status=500,
        ) from exc
    return directory.resolve()


def _sqlite_database_path() -> Path:
    database = settings.DATABASES.get("default", {})
    if database.get("ENGINE") != "django.db.backends.sqlite3":
        raise ApiError(
            "backups.database_unsupported",
            "I backup automatici richiedono il database SQLite configurato da ReDjango.",
            status=409,
        )
    raw_name = str(database.get("NAME") or "")
    if not raw_name or raw_name == ":memory:" or raw_name.startswith("file:"):
        raise ApiError(
            "backups.database_unavailable",
            "Il database attivo non può essere copiato in un backup persistente.",
            status=409,
        )
    database_path = Path(raw_name).resolve()
    if not database_path.is_file():
        raise ApiError(
            "backups.database_not_found",
            "Il file del database non è stato trovato.",
            status=404,
        )
    return database_path


def _setting_defaults() -> dict[str, dict[str, Any]]:
    return {definition["key"]: definition for definition in BACKUP_SETTING_DEFINITIONS}


def _backup_settings() -> dict[str, SettingDefinition]:
    definitions = _setting_defaults()
    existing = {
        setting.key: setting
        for setting in SettingDefinition.objects.filter(key__in=definitions).all()
    }
    for key, definition in definitions.items():
        if key in existing:
            continue
        setting, _created = SettingDefinition.objects.get_or_create(
            key=key,
            defaults={
                **{field: value for field, value in definition.items() if field not in {"key", "validation"}},
                "value": definition["default_value"],
                "metadata": {
                    "seed_kind": "setting_definition",
                    "seed_version": "backup",
                    **definition.get("validation", {}),
                },
            },
        )
        existing[key] = setting
    return existing


def _setting_value(setting: SettingDefinition, fallback: Any) -> Any:
    if setting.value is not None:
        return setting.value
    return setting.default_value if setting.default_value is not None else fallback


def _bounded_int(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return fallback
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return fallback
    return numeric if minimum <= numeric <= maximum else fallback


def backup_configuration() -> dict[str, Any]:
    definitions = _setting_defaults()
    settings_by_key = _backup_settings()
    return {
        "enabled": _setting_value(
            settings_by_key[BACKUP_ENABLED_SETTING_KEY],
            definitions[BACKUP_ENABLED_SETTING_KEY]["default_value"],
        ) is True,
        "onStartup": _setting_value(
            settings_by_key[BACKUP_ON_STARTUP_SETTING_KEY],
            definitions[BACKUP_ON_STARTUP_SETTING_KEY]["default_value"],
        ) is True,
        "intervalMinutes": _bounded_int(
            _setting_value(
                settings_by_key[BACKUP_INTERVAL_SETTING_KEY],
                definitions[BACKUP_INTERVAL_SETTING_KEY]["default_value"],
            ),
            int(definitions[BACKUP_INTERVAL_SETTING_KEY]["default_value"]),
            5,
            120,
        ),
        "retentionCount": _bounded_int(
            _setting_value(
                settings_by_key[BACKUP_RETENTION_SETTING_KEY],
                definitions[BACKUP_RETENTION_SETTING_KEY]["default_value"],
            ),
            int(definitions[BACKUP_RETENTION_SETTING_KEY]["default_value"]),
            1,
            100,
        ),
    }


def save_backup_configuration(user, giocatore: Giocatore, values: Any) -> dict[str, Any]:
    require_backup_admin(user, giocatore)
    if not isinstance(values, dict):
        raise ApiError(
            "backups.configuration_invalid",
            "La configurazione dei backup non è valida.",
            "configuration",
        )

    settings_by_key = _backup_settings()
    fields = {
        "enabled": BACKUP_ENABLED_SETTING_KEY,
        "onStartup": BACKUP_ON_STARTUP_SETTING_KEY,
        "intervalMinutes": BACKUP_INTERVAL_SETTING_KEY,
        "retentionCount": BACKUP_RETENTION_SETTING_KEY,
    }
    prepared: dict[str, Any] = {}
    for field, setting_key in fields.items():
        if field not in values:
            raise ApiError(
                "backups.configuration_field_required",
                "Completa tutti i campi della configurazione backup.",
                field,
            )
        prepared[setting_key] = validate_setting_value(settings_by_key[setting_key], values[field])

    with transaction.atomic():
        for setting_key, value in prepared.items():
            setting = settings_by_key[setting_key]
            if setting.value != value:
                setting.value = value
                setting.save(update_fields=["value", "updated_at"])

    prune_backups(int(prepared[BACKUP_RETENTION_SETTING_KEY]))
    return backup_management_overview()


def _timestamp_from_backup_id(backup_id: str) -> datetime:
    match = BACKUP_ID_RE.fullmatch(backup_id)
    if not match:
        raise ApiError("backups.not_found", "Il backup richiesto non esiste.", "backupId", 404)
    return datetime.strptime(match.group(2), "%Y%m%dT%H%M%S%fZ").replace(tzinfo=UTC)


def _backup_path(backup_id: str) -> Path:
    _timestamp_from_backup_id(backup_id)
    directory = backup_directory()
    path = (directory / f"{backup_id}.sqlite3").resolve()
    if path.parent != directory or not path.is_file():
        raise ApiError("backups.not_found", "Il backup richiesto non esiste.", "backupId", 404)
    return path


def _metadata_path(snapshot_path: Path) -> Path:
    return snapshot_path.with_suffix(".json")


def _read_metadata(snapshot_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_metadata_path(snapshot_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_metadata(snapshot_path: Path, metadata: dict[str, Any]) -> None:
    metadata_path = _metadata_path(snapshot_path)
    temporary_path = metadata_path.with_name(f"{metadata_path.name}.{secrets.token_hex(4)}.tmp")
    try:
        temporary_path.write_text(
            json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        temporary_path.replace(metadata_path)
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise ApiError(
            "backups.metadata_write_failed",
            "Il backup è stato creato, ma non è stato possibile salvare i suoi dettagli.",
            status=500,
        ) from exc


def _serialize_backup(snapshot_path: Path) -> dict[str, Any]:
    backup_id = snapshot_path.stem
    match = BACKUP_ID_RE.fullmatch(backup_id)
    if not match:
        raise ValueError(f"Nome backup non gestito: {snapshot_path.name}")
    metadata = _read_metadata(snapshot_path)
    timestamp = _timestamp_from_backup_id(backup_id)
    created_at = str(metadata.get("createdAt") or timestamp.isoformat())
    return {
        "id": backup_id,
        "kind": match.group(1),
        "label": str(metadata.get("label") or ""),
        "createdAt": created_at,
        "createdBy": str(metadata.get("createdBy") or "Sistema"),
        "sizeBytes": snapshot_path.stat().st_size,
    }


def list_backups() -> list[dict[str, Any]]:
    snapshots = []
    for snapshot_path in backup_directory().glob(BACKUP_FILE_GLOB):
        if not BACKUP_ID_RE.fullmatch(snapshot_path.stem):
            continue
        try:
            snapshots.append(_serialize_backup(snapshot_path))
        except OSError:
            continue
    return sorted(snapshots, key=lambda entry: (entry["createdAt"], entry["id"]), reverse=True)


def _copy_sqlite_database(source_path: Path, destination_path: Path) -> None:
    temporary_path = destination_path.with_name(f"{destination_path.name}.{secrets.token_hex(4)}.tmp")
    source_connection = None
    destination_connection = None
    copy_error: OSError | sqlite3.DatabaseError | None = None
    try:
        source_connection = sqlite3.connect(f"{source_path.as_uri()}?mode=ro", uri=True)
        source_connection.execute("PRAGMA busy_timeout = 5000")
        destination_connection = sqlite3.connect(temporary_path)
        source_connection.backup(destination_connection)
        destination_connection.commit()
        integrity = destination_connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise sqlite3.DatabaseError("integrity_check non riuscito")
    except (OSError, sqlite3.DatabaseError) as exc:
        copy_error = exc
    finally:
        if destination_connection is not None:
            destination_connection.close()
        if source_connection is not None:
            source_connection.close()

    if copy_error is not None:
        temporary_path.unlink(missing_ok=True)
        raise ApiError(
            "backups.create_failed",
            "Non è stato possibile creare una copia coerente del database.",
            status=500,
        ) from copy_error

    try:
        temporary_path.replace(destination_path)
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise ApiError(
            "backups.create_failed",
            "Non è stato possibile finalizzare il file di backup.",
            status=500,
        ) from exc


@_synchronized_backup_operation
def prune_backups(retention_count: int | None = None) -> int:
    retention = retention_count if retention_count is not None else backup_configuration()["retentionCount"]
    retained = max(1, min(int(retention), 100))
    snapshots = list_backups()
    removed = 0
    for backup in snapshots[retained:]:
        snapshot_path = _backup_path(backup["id"])
        try:
            snapshot_path.unlink(missing_ok=True)
            removed += 1
        except OSError:
            logger.warning("Impossibile rimuovere il backup scaduto %s", snapshot_path)
            continue
        try:
            _metadata_path(snapshot_path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Impossibile rimuovere i dettagli del backup scaduto %s", snapshot_path)
    return removed


@_synchronized_backup_operation
def create_backup(*, kind: str, label: Any = "", actor: Giocatore | None = None) -> dict[str, Any]:
    if kind not in BACKUP_KINDS:
        raise ValueError(f"Tipo backup non supportato: {kind}")
    cleaned_label = str(label or "").strip()
    if len(cleaned_label) > 120:
        raise ApiError(
            "backups.label_too_long",
            "L'etichetta del backup può contenere al massimo 120 caratteri.",
            "label",
        )
    timestamp = timezone.now().astimezone(UTC)
    backup_id = (
        f"redjango-backup-{kind}-{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}-"
        f"{secrets.token_hex(4)}"
    )
    snapshot_path = backup_directory() / f"{backup_id}.sqlite3"
    _copy_sqlite_database(_sqlite_database_path(), snapshot_path)
    try:
        _write_metadata(
            snapshot_path,
            {
                "kind": kind,
                "label": cleaned_label,
                "createdAt": timestamp.isoformat(),
                "createdBy": (actor.display_name or actor.nome) if actor else "Sistema",
            },
        )
    except ApiError:
        snapshot_path.unlink(missing_ok=True)
        raise
    prune_backups()
    return _serialize_backup(snapshot_path)


def create_manual_backup(user, giocatore: Giocatore, label: Any = "") -> dict[str, Any]:
    require_backup_admin(user, giocatore)
    return create_backup(kind="manual", label=label, actor=giocatore)


@_synchronized_backup_operation
def delete_backup(user, giocatore: Giocatore, backup_id: str) -> None:
    require_backup_admin(user, giocatore)
    snapshot_path = _backup_path(backup_id)
    try:
        snapshot_path.unlink()
    except OSError as exc:
        raise ApiError(
            "backups.delete_failed",
            "Non è stato possibile eliminare il backup selezionato.",
            status=500,
        ) from exc
    try:
        _metadata_path(snapshot_path).unlink(missing_ok=True)
    except OSError:
        logger.warning("Impossibile rimuovere i dettagli del backup eliminato %s", snapshot_path)


def backup_management_overview(*, created_backup_id: str | None = None) -> dict[str, Any]:
    backups = list_backups()
    return {
        "configuration": backup_configuration(),
        "backups": backups,
        "createdBackupId": created_backup_id,
        "storage": {
            "count": len(backups),
            "usedBytes": sum(int(backup["sizeBytes"]) for backup in backups),
            "content": "Ogni copia contiene il database SQLite: personaggi, inventari, campagne, cataloghi e impostazioni. I file media restano nella cartella media del server.",
        },
    }


def _readonly_connection(snapshot_path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(f"{snapshot_path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.DatabaseError as exc:
        raise ApiError(
            "backups.inspect_failed",
            "Il backup selezionato non può essere letto.",
            "backupId",
        ) from exc


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        [table_name],
    ).fetchone()
    if table is None:
        return set()
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _safe_value(value: Any) -> int | float | str:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        return value
    return 0


def _character_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    columns = _table_columns(connection, "characters_personaggio")
    required = {"id", "nome"}
    if not required <= columns:
        raise ApiError(
            "backups.inspect_incompatible",
            "Il backup non contiene una struttura personaggi compatibile.",
            "backupId",
        )
    available = [
        column
        for column in ("id", "nome", "tipologia", "livello", "monete", "danno", "tot", "zaino_id", "archived_at")
        if column in columns
    ]
    where = " WHERE archived_at IS NULL" if "archived_at" in columns else ""
    rows = connection.execute(
        f"SELECT {', '.join(available)} FROM characters_personaggio{where} ORDER BY nome COLLATE NOCASE, id"
    ).fetchall()
    characters = []
    for row in rows:
        totals = _json_object(row["tot"] if "tot" in row.keys() else {})
        characters.append(
            {
                "id": int(row["id"]),
                "name": str(row["nome"] or "Personaggio senza nome"),
                "type": str(row["tipologia"] or "") if "tipologia" in row.keys() else "",
                "level": int(row["livello"] or 0) if "livello" in row.keys() else 0,
                "coins": int(row["monete"] or 0) if "monete" in row.keys() else 0,
                "damage": int(row["danno"] or 0) if "danno" in row.keys() else 0,
                "backpackId": int(row["zaino_id"]) if "zaino_id" in row.keys() and row["zaino_id"] else None,
                "coreValues": [
                    {"key": key, "label": label, "value": _safe_value(totals.get(key, 0))}
                    for key, label in CORE_VALUE_LABELS
                ],
            }
        )
    return characters


def _item_names(connection: sqlite3.Connection, item_ids: list[int]) -> dict[int, str]:
    item_columns = _table_columns(connection, "core_oggetto")
    if not item_ids or not {"id", "nome"} <= item_columns:
        return {}
    placeholders = ", ".join("?" for _item_id in item_ids)
    rows = connection.execute(
        f"SELECT id, nome FROM core_oggetto WHERE id IN ({placeholders})",
        item_ids,
    ).fetchall()
    return {int(row["id"]): str(row["nome"] or "Oggetto senza nome") for row in rows}


def _legacy_backpack(connection: sqlite3.Connection, backpack_id: int | None) -> list[dict[str, Any]]:
    if not backpack_id:
        return []
    columns = _table_columns(connection, "characters_zaino")
    slot_columns = [f"slot_{index}_id" for index in range(1, 51) if f"slot_{index}_id" in columns]
    if not slot_columns:
        return []
    row = connection.execute(
        f"SELECT {', '.join(slot_columns)} FROM characters_zaino WHERE id = ?",
        [backpack_id],
    ).fetchone()
    if row is None:
        return []
    item_ids = [int(row[column]) for column in slot_columns if row[column]]
    names = _item_names(connection, item_ids)
    return [
        {
            "slot": int(column.removeprefix("slot_").removesuffix("_id")),
            "name": names.get(int(row[column]), "Oggetto rimosso dal catalogo"),
            "quantity": 1,
        }
        for column in slot_columns
        if row[column]
    ]


def _reagent_label(stock_key: str) -> str:
    colors = {"r": "Rosso", "v": "Verde", "b": "Blu"}
    color = colors.get(stock_key[:1].lower(), "")
    level = stock_key[1:] if len(stock_key) > 1 else ""
    return f"Reagente {color} · livello {level}" if color and level else "Reagente"


def _extended_containers(connection: sqlite3.Connection, character_id: int) -> list[dict[str, Any]]:
    container_columns = _table_columns(connection, "characters_contenitoreinventario")
    entry_columns = _table_columns(connection, "characters_vocecontenitoreinventario")
    if not {"id", "nome", "personaggio_id"} <= container_columns or not {"contenitore_id", "slot"} <= entry_columns:
        return []
    item_columns = _table_columns(connection, "core_oggetto")
    item_table_available = {"id", "nome"} <= item_columns and "oggetto_id" in entry_columns
    capacity_value = "c.capacita" if "capacita" in container_columns else "0"
    quantity_value = "v.quantita" if "quantita" in entry_columns else "1"
    reagent_value = "v.reagent_stock_key" if "reagent_stock_key" in entry_columns else "''"
    entry_name = "o.nome" if item_table_available else "NULL"
    item_join = "LEFT JOIN core_oggetto o ON o.id = v.oggetto_id " if item_table_available else ""
    rows = connection.execute(
        f"SELECT c.id, c.nome, {capacity_value} AS capacita, v.slot, "
        f"{quantity_value} AS quantita, {reagent_value} AS reagent_stock_key, "
        f"{entry_name} AS item_name "
        "FROM characters_contenitoreinventario c "
        "LEFT JOIN characters_vocecontenitoreinventario v ON v.contenitore_id = c.id "
        f"{item_join}"
        "WHERE c.personaggio_id = ? "
        "ORDER BY c.nome COLLATE NOCASE, v.slot",
        [character_id],
    ).fetchall()
    containers: dict[int, dict[str, Any]] = {}
    for row in rows:
        container_id = int(row["id"])
        container = containers.setdefault(
            container_id,
            {
                "name": str(row["nome"] or "Contenitore"),
                "capacity": int(row["capacita"] or 0),
                "entries": [],
            },
        )
        if row["slot"] is None:
            continue
        stock_key = str(row["reagent_stock_key"] or "")
        container["entries"].append(
            {
                "slot": int(row["slot"]),
                "name": str(row["item_name"] or _reagent_label(stock_key)),
                "quantity": int(row["quantita"] or 1),
            }
        )
    return list(containers.values())


@_synchronized_backup_operation
def inspect_backup(backup_id: str, character_id: int | None = None) -> dict[str, Any]:
    snapshot_path = _backup_path(backup_id)
    connection = _readonly_connection(snapshot_path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise ApiError(
                "backups.inspect_failed",
                "Il backup selezionato non supera il controllo di integrità.",
                "backupId",
            )
        characters = _character_rows(connection)
        selected_character = None
        if character_id is not None:
            selected_character = next((entry for entry in characters if entry["id"] == character_id), None)
            if selected_character is None:
                raise ApiError(
                    "backups.character_not_found",
                    "Il personaggio non è presente nel backup selezionato.",
                    "characterId",
                    404,
                )
            backpack_id = selected_character.pop("backpackId", None)
            selected_character = {
                **selected_character,
                "backpack": _legacy_backpack(connection, backpack_id),
                "containers": _extended_containers(connection, character_id),
            }
        for character in characters:
            character.pop("backpackId", None)
        return {
            "backupId": backup_id,
            "characterCount": len(characters),
            "characters": characters,
            "selectedCharacter": selected_character,
        }
    except sqlite3.DatabaseError as exc:
        raise ApiError(
            "backups.inspect_failed",
            "Il backup selezionato non può essere letto.",
            "backupId",
        ) from exc
    finally:
        connection.close()

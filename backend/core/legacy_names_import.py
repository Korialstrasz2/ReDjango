"""Importa i bacini di nomi Elder in ``NomiRazzeInfo``.

Il generatore Elder teneva gli stessi dati in due posti: una tabella
``GroupNames`` e 485 righe di liste Python usate come fallback. Qui importiamo
soltanto la tabella. Le liste hardcoded non vengono portate: un bacino assente
deve diventare un errore leggibile, non un risultato silenziosamente diverso da
quello che il Master ha configurato.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from django.db import transaction

from backend.core.models import NomiRazzeInfo


LEGACY_TABLE = "django_slim_groupnames"

# Elder chiamava «Orco» la razza che in ReDjango si chiama «Orsimer»: senza
# questa mappa il bacino non verrebbe mai trovato partendo dal catalogo razze.
RACE_ALIASES = {
    "Orco": "Orsimer",
}


def _connect_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _string_list(raw: Any) -> list[str]:
    """I campi Elder sono JSONField su SQLite: testo JSON, non liste native."""

    value = raw
    if isinstance(value, (str, bytes)):
        try:
            value = json.loads(value or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if not isinstance(value, list):
        return []
    cleaned = []
    for entry in value:
        text = str(entry if entry is not None else "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def normalized_race(raw: Any) -> str:
    race = str(raw if raw is not None else "").strip()
    return RACE_ALIASES.get(race, race)


def normalized_culture_name(raw: Any) -> str:
    """La cultura omonima della razza va rinominata insieme alla razza.

    Elder chiamava «Orco» sia la razza sia il suo bacino generico. Lasciando il
    bacino con il vecchio nome, la modalità rapida non lo riconoscerebbe più
    come cultura predefinita di Orsimer e mostrerebbe «Orsimer · Orco».
    """

    name = str(raw if raw is not None else "").strip()
    return RACE_ALIASES.get(name, name)


def read_legacy_name_rows(source: Path) -> list[dict[str, Any]]:
    with _connect_read_only(source) as connection:
        try:
            rows = connection.execute(
                f"SELECT name, race, namesMale, namesFemale, surnames, description "
                f"FROM {LEGACY_TABLE} ORDER BY race, name"
            ).fetchall()
        except sqlite3.DatabaseError as exc:  # tabella assente o database di altra forma
            raise ValueError(f"La tabella Elder «{LEGACY_TABLE}» non è leggibile: {exc}") from exc
    parsed = []
    for row in rows:
        name = normalized_culture_name(row["name"])
        if not name:
            continue
        parsed.append(
            {
                "name": name[:160],
                "legacyName": str(row["name"] or "").strip()[:160],
                "race": normalized_race(row["race"])[:120],
                "names_male": _string_list(row["namesMale"]),
                "names_female": _string_list(row["namesFemale"]),
                "surnames": _string_list(row["surnames"]),
                "description": str(row["description"] or "").replace("\r\n", "\n").strip(),
            }
        )
    return parsed


@transaction.atomic
def import_legacy_names(source: Path) -> dict[str, int]:
    """`name` è la chiave naturale, come per gli altri importatori Elder."""

    rows = read_legacy_name_rows(source)
    created = 0
    updated = 0
    renamed = 0
    for row in rows:
        _, was_created = NomiRazzeInfo.objects.update_or_create(
            name=row["name"],
            defaults={
                "race": row["race"],
                "names_male": row["names_male"],
                "names_female": row["names_female"],
                "surnames": row["surnames"],
                "description": row["description"],
                "archived_at": None,
                "metadata": {
                    "sourceProject": "the_elder_django",
                    "sourceTable": LEGACY_TABLE,
                    "legacyName": row["legacyName"],
                },
            },
        )
        created += int(was_created)
        updated += int(not was_created)
        # Un'importazione precedente può aver scritto la cultura con il nome
        # Elder: rimuoviamo il duplicato invece di lasciare due bacini identici.
        if row["legacyName"] != row["name"]:
            renamed += NomiRazzeInfo.objects.filter(name=row["legacyName"]).delete()[0]
    return {
        "cultures": len(rows),
        "created": created,
        "updated": updated,
        "renamed": renamed,
        "races": len({row["race"] for row in rows if row["race"]}),
    }

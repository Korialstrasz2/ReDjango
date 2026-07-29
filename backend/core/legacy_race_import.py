from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from django.db import transaction
from django.utils.text import slugify

from backend.characters.models import Personaggio
from backend.characters.race_rules import RACE_CATALOG, RACE_NAMES
from backend.core.models import FamigliaSkill, GruppoFamiglieSkill, Guida, Skill
from backend.core.guides_it import race_guide_html


RACE_GROUP_NAME = "Razze/Sottorazze"
RACE_GROUP_SLUG = "razze-sottorazze"
BASE_SKILL_NUMBER = 890_000
LEGACY_SKILL_NUMBER = 900_000
CATALOG_SKILL_NUMBER = 895_000


def _connect_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _clean_formula(value: Any) -> str:
    cleaned = str(value if value is not None else "").strip()
    cleaned = cleaned.replace("(f)", "")
    cleaned = re.sub(r"\bPersonaggio\.", "personaggio.", cleaned, flags=re.IGNORECASE)
    return cleaned


def _passive_from_proposal(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    try:
        proposal = json.loads(row["effetto_proposto"] or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    effect = proposal.get("effetto_extra") if isinstance(proposal, dict) else None
    if proposal.get("tipo") != "effetto_extra" or not isinstance(effect, dict):
        return []
    operations = []
    operation_names = {"+": "add", "-": "subtract", "*": "multiply", "=": "set"}
    for raw in effect.get("effetti", []):
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        operations.append(
            {
                "target": str(raw["name"]).removesuffix("_extra"),
                "operation": operation_names.get(str(raw.get("operation") or "+"), "add"),
                "value": _clean_formula(raw.get("value")),
                "condition": "",
            }
        )
    if not operations:
        return []
    return [
        {
            "id": f"elder-race-passive-{row['id']}",
            "name": str(effect.get("nome") or row["nome"])[:180],
            "description": str(effect.get("descrizione") or row["note_proposte"] or row["nome"]),
            "origin": str(effect.get("origine") or row["fonte_nome"] or row["nome"])[:180],
            "icon": "stella",
            "temporary": False,
            "operations": operations,
        }
    ]


def _action_from_row(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    description = str(row["attivabile_descrizione"] or "").strip()
    if not description:
        return []
    costs = {
        key: int(row[column] or 0)
        for key, column in (
            ("energia", "costo_en"),
            ("mana", "costo_man"),
            ("pa", "costo_pa"),
            ("pf", "costo_pf"),
            ("potere", "costo_pow"),
            ("stanchezza", "costo_st"),
        )
        if int(row[column] or 0) > 0
    }
    duration = str(row["durata_turni"] or "").strip()
    return [
        {
            "id": f"elder-race-action-{row['id']}",
            "name": str(row["attivabile_nome"] or row["nome"])[:180],
            "description": description,
            "trigger": "",
            "duration": f"{duration} turni" if duration else "",
            "usageNotes": str(row["note_proposte"] or "").strip(),
            "costs": costs,
            "icon": "stella",
        }
    ]


def _base_passive(race: str, index: int) -> dict[str, Any]:
    operations = [
        {
            "target": target,
            "operation": "add" if value >= 0 else "subtract",
            "value": str(abs(value)),
            "condition": "",
        }
        for target, value in RACE_CATALOG[race]["modifiers"].items()
    ]
    return {
        "id": f"elder-race-base-{slugify(race)}",
        "name": f"Caratteristiche razziali: {race}",
        "description": "Bonus e penalità di caratteristica della razza primaria, importati dalla guida Elder Razze.",
        "origin": f"Razza: {race}",
        "icon": "stella",
        "temporary": False,
        "operations": operations,
    }


def _catalog_passive(
    *,
    race: str,
    name: str,
    description: str,
    effects: Mapping[str, Any],
    suffix: str,
) -> dict[str, Any]:
    operations = [
        {
            "target": target,
            "operation": "add" if not isinstance(value, (int, float)) or value >= 0 else "subtract",
            "value": str(value if not isinstance(value, (int, float)) or value >= 0 else abs(value)),
            "condition": "",
        }
        for target, value in effects.items()
    ]
    return {
        "id": f"redjango-race-{slugify(race)}-{slugify(suffix)}",
        "name": name,
        "description": description,
        "origin": f"Razza: {race}",
        "icon": "stella",
        "temporary": False,
        "operations": operations,
    }


def read_legacy_race_rows(source: Path) -> tuple[str, list[dict[str, Any]]]:
    with _connect_read_only(source) as connection:
        guide = connection.execute(
            "SELECT contenuto FROM django_slim_guida WHERE lower(nome) = 'razze' LIMIT 1"
        ).fetchone()
        if guide is None:
            raise ValueError("La guida Elder 'Razze' non è presente.")
        rows = connection.execute(
            """
            SELECT e.*,
                   a.nome AS attivabile_nome,
                   a.descrizione AS attivabile_descrizione,
                   a.costo_en, a.costo_man, a.costo_pa, a.costo_pf, a.costo_pow, a.costo_st,
                   a.durata_turni
            FROM django_slim_effettisbloccabili e
            LEFT JOIN django_slim_attivabile a ON a.id = e.attivabile_collegato_id
            WHERE e.fonte_tipo IN ('razza', 'subrazza')
            ORDER BY e.id
            """
        ).fetchall()
    return str(guide["contenuto"]), [dict(row) for row in rows]


def _race_from_name(name: str) -> str:
    prefix = str(name or "").split(" - ", 1)[0].strip()
    return "Orsimer" if prefix == "Orco" else prefix


def _stable_skill_number(slug: str, preferred: int, *, step: int = 1) -> int:
    """Preserve generated numbers and avoid collisions when the race catalog grows."""
    existing = Skill.objects.filter(slug=slug).values_list("numero", flat=True).first()
    if existing is not None:
        return int(existing)
    candidate = int(preferred)
    while Skill.objects.filter(numero=candidate).exclude(slug=slug).exists():
        candidate += int(step)
    return candidate


@transaction.atomic
def import_legacy_races(source: Path) -> dict[str, int]:
    guide_content, raw_rows = read_legacy_race_rows(source)
    Guida.objects.update_or_create(
        nome="Razze",
        defaults={
            "contenuto": json.dumps([{"type": "legacy_html", "html": race_guide_html(guide_content)}]),
            "categoria": "Regolamento",
            # Kept clear of the seeded guides so the sidebar order is stable.
            "ordine": 25,
            "metadata": {"sourceProject": "the_elder_django", "sourceTable": "django_slim_guida"},
        },
    )
    group, _created = GruppoFamiglieSkill.objects.update_or_create(
        slug=RACE_GROUP_SLUG,
        defaults={
            "nome": RACE_GROUP_NAME,
            # Keep racial abilities with the optional character-build material:
            # the SPA renders this immediately after Perk and before Search.
            "ordine": 41,
            "note": "Tratti razziali e sottorazze importati dalla guida e dagli EffettiSbloccabili Elder.",
            "metadata": {"sourceProject": "the_elder_django", "domain": "races"},
        },
    )
    families: dict[str, FamigliaSkill] = {}
    generated = 0
    for index, race in enumerate(RACE_NAMES, start=1):
        family, _ = FamigliaSkill.objects.update_or_create(
            nome=race,
            defaults={
                "gruppo": group,
                "ordine": index,
                "note": f"Razza e sottorazze {race}.",
                "metadata": {"sourceProject": "the_elder_django", "race": race},
            },
        )
        families[race] = family
        base_slug = f"elder-race-{slugify(race)}-base"
        Skill.objects.update_or_create(
            slug=base_slug,
            defaults={
                "nome": f"{race} - Caratteristiche razziali",
                "numero": _stable_skill_number(base_slug, BASE_SKILL_NUMBER + index),
                "famiglia": family,
                "ordine_famiglia": 0,
                "costo_pe": 0,
                "tipo_pe": "all",
                "costo_testuale": "Automatico con Razza 1",
                "descrizione": f"Bonus e penalità caratteristici di {race}.",
                "requisiti": f"Razza 1: {race}",
                "effetti_passivi": [_base_passive(race, index)],
                "azioni_attive": [],
                "icona": "stella",
                "metadata": {
                    "sourceProject": "the_elder_django",
                    "race": race,
                    "raceUnlockKind": "base",
                    "automaticRaceUnlock": True,
                },
            },
        )
        definition = RACE_CATALOG[race]
        if definition.get("native"):
            trait = definition.get("trait") or {}
            trait_data = trait if isinstance(trait, Mapping) else {"note": str(trait)}
            trait_slug = f"redjango-race-{slugify(race)}-trait"
            trait_number = _stable_skill_number(
                trait_slug,
                CATALOG_SKILL_NUMBER + index * 100,
                step=100,
            )
            Skill.objects.update_or_create(
                slug=trait_slug,
                defaults={
                    "nome": f"{race} - Tratto razziale",
                    "numero": trait_number,
                    "famiglia": family,
                    "ordine_famiglia": 1,
                    "costo_pe": 0,
                    "tipo_pe": "all",
                    "costo_testuale": "Automatico con Razza 1",
                    "descrizione": str(trait_data.get("note") or ""),
                    "requisiti": f"Razza 1: {race}",
                    "effetti_passivi": [
                        _catalog_passive(
                            race=race,
                            name=f"{race}: tratto razziale",
                            description=str(trait_data.get("note") or ""),
                            effects=dict(trait_data.get("effects") or {}),
                            suffix="trait",
                        )
                    ],
                    "azioni_attive": [],
                    "icona": "stella",
                    "metadata": {
                        "sourceProject": "redjango",
                        "race": race,
                        "raceUnlockKind": "razza",
                        "automaticRaceUnlock": True,
                    },
                },
            )
            generated += 1
            for subrace_index, (subrace, raw_subrace) in enumerate(
                definition.get("subraces", {}).items(),
                start=2,
            ):
                subrace_data = (
                    raw_subrace
                    if isinstance(raw_subrace, Mapping)
                    else {"note": str(raw_subrace)}
                )
                subrace_slug = f"redjango-race-{slugify(race)}-{slugify(subrace)}"
                Skill.objects.update_or_create(
                    slug=subrace_slug,
                    defaults={
                        "nome": f"{race} - {subrace}",
                        "numero": _stable_skill_number(
                            subrace_slug,
                            trait_number + subrace_index,
                        ),
                        "famiglia": family,
                        "ordine_famiglia": subrace_index,
                        "costo_pe": 0,
                        "tipo_pe": "all",
                        "costo_testuale": "Automatico dalla sottorazza",
                        "descrizione": str(subrace_data.get("note") or ""),
                        "requisiti": f"Razza 1: {race}; Razza 2: {subrace}",
                        "effetti_passivi": [
                            _catalog_passive(
                                race=race,
                                name=f"SUBRAZZA: {subrace}",
                                description=str(subrace_data.get("note") or ""),
                                effects=dict(subrace_data.get("effects") or {}),
                                suffix=subrace,
                            )
                        ],
                        "azioni_attive": [],
                        "icona": "stella",
                        "metadata": {
                            "sourceProject": "redjango",
                            "race": race,
                            "subrace": subrace,
                            "raceUnlockKind": "subrazza",
                            "automaticRaceUnlock": True,
                        },
                    },
                )
                generated += 1

    imported = 0
    skipped = 0
    for raw in raw_rows:
        race = _race_from_name(raw["nome"])
        if race not in families:
            skipped += 1
            continue
        passives = _passive_from_proposal(raw)
        actions = _action_from_row(raw)
        subrace = str(raw["nome"]).split(" - ", 1)[1].strip() if raw["fonte_tipo"] == "subrazza" else ""
        Skill.objects.update_or_create(
            slug=f"elder-racial-trait-{raw['id']}",
            defaults={
                "nome": str(raw["nome"])[:180],
                "numero": LEGACY_SKILL_NUMBER + int(raw["id"]),
                "famiglia": families[race],
                "ordine_famiglia": int(raw["id"]),
                "costo_pe": 0,
                "tipo_pe": "all",
                "costo_testuale": "Automatico dalla razza" if raw["fonte_tipo"] == "razza" else "Automatico dalla sottorazza",
                "descrizione": str(raw["attivabile_descrizione"] or raw["note_proposte"] or raw["nome"]),
                "requisiti": f"Razza 1: {race}" if raw["fonte_tipo"] == "razza" else f"Razza 1: {race}; Razza 2: {subrace}",
                "effetti_passivi": passives,
                "azioni_attive": actions,
                "icona": "stella",
                "note": str(raw["note_proposte"] or ""),
                "metadata": {
                    "sourceProject": "the_elder_django",
                    "sourceTable": "django_slim_effettisbloccabili",
                    "sourceId": int(raw["id"]),
                    "race": race,
                    "subrace": subrace,
                    "raceUnlockKind": str(raw["fonte_tipo"]),
                    "automaticRaceUnlock": True,
                },
            },
        )
        imported += 1
    from backend.characters.services.refresh_personaggio import refresh_personaggio

    synchronized = 0
    for character_id in Personaggio.objects.exclude(razza_1="").values_list("id", flat=True):
        refresh_personaggio(character_id)
        synchronized += 1
    return {
        "guide": 1,
        "group": 1,
        "families": len(families),
        "skills": imported + len(families) + generated,
        "generated": generated,
        "skipped": skipped,
        "synchronized": synchronized,
    }

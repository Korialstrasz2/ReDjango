"""Porta i bonus di ``RACE_CATALOG`` sulle abilità razziali in banca dati.

Un personaggio già importato non legge ``automatic_race_effects``: quel percorso
è la riserva per chi non ha abilità razziali. Chi le ha — cioè chiunque sia
passato dall'import Elder o dal generatore di Unit — prende i bonus dalle righe
``Skill`` del gruppo ``razze-sottorazze``, che li materializzano come
``EffettoPersonalizzato`` sulla scheda.

Finché le due fonti divergono, correggere il catalogo non cambia nulla in gioco.
Questo modulo le riallinea: proietta gli ``effects`` del catalogo negli
``effetti_passivi`` delle abilità e lascia gli ``manual`` come nota d'uso
dell'azione, così la scheda applica ciò che è automatico e il tavolo vede
scritto ciò che resta a mano.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from django.db import transaction

from backend.characters.race_rules import (
    LEGACY_SUBRACE_ALIASES,
    RACE_CATALOG,
    race_bonus_operations,
)
from backend.core.models import Skill


RACE_SKILL_GROUP_SLUG = "razze-sottorazze"
PASSIVE_ID_PREFIX = "redjango-race-passive"
MANUAL_NOTE_PREFIX = "Da segnare a mano:"


def _normalized(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _catalog_entry(skill: Skill, race: str, subrace: str, kind: str) -> Mapping[str, Any] | None:
    """Trova la voce di catalogo corrispondente all'abilità.

    Le abilità ``base`` tengono i modificatori di caratteristica e le ``razza``
    sono un potere ciascuna: sono già granulari e corrette, quindi si toccano
    solo quando il catalogo le rivendica esplicitamente in ``powers``, per slug.
    Riscriverle dal ``trait``, che è un blocco unico, cancellerebbe i loro
    effetti e ne duplicherebbe altri.
    """
    definition = next(
        (value for name, value in RACE_CATALOG.items() if _normalized(name) == _normalized(race)),
        None,
    )
    if definition is None:
        return None
    if kind == "base":
        return None
    if kind == "razza":
        power = (definition.get("powers") or {}).get(skill.slug)
        return power if isinstance(power, Mapping) else None
    # I nomi arrivati da Elder non combaciano sempre col catalogo: «Forgiatore
    # D'Armi» contro «Forgiatore d'Armi», e qualche refuso vero come «Apprensista».
    wanted = _normalized(LEGACY_SUBRACE_ALIASES.get(_normalized(subrace), subrace))
    entry = next(
        (
            value
            for name, value in (definition.get("subraces") or {}).items()
            if _normalized(name) == wanted
        ),
        None,
    )
    return entry if isinstance(entry, Mapping) else None


def _passive_payload(skill: Skill, entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    operations = race_bonus_operations(entry.get("effects") or {})
    if not operations:
        return []
    return [
        {
            "id": f"{PASSIVE_ID_PREFIX}-{skill.id}",
            "name": skill.nome,
            "description": str(entry.get("note") or skill.descrizione or "")[:400],
            "origin": skill.nome,
            "icon": "stella",
            "temporary": False,
            "operations": [
                {
                    "target": operation["target"],
                    "operation": operation["operation"],
                    "value": operation["value"],
                    "condition": "",
                }
                for operation in operations
            ],
        }
    ]


def _actions_payload(skill: Skill, entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Tiene un'azione solo per ciò che resta manuale.

    Le azioni esistenti vengono riscritte, non accumulate: la nota d'uso deve
    dire esattamente cosa il motore non applica, altrimenti il tavolo continua a
    sommare a mano un bonus che la scheda ha già.
    """
    manual = str(entry.get("manual") or "").strip()
    if not manual:
        return []
    existing = skill.azioni_attive if isinstance(skill.azioni_attive, list) else []
    action_id = next(
        (
            str(action.get("id"))
            for action in existing
            if isinstance(action, Mapping) and action.get("id")
        ),
        f"redjango-race-action-{skill.id}",
    )
    return [
        {
            "id": action_id,
            "name": skill.nome,
            "description": str(entry.get("note") or "")[:400],
            "trigger": "",
            "duration": "",
            "usageNotes": f"{MANUAL_NOTE_PREFIX} {manual}",
        }
    ]


def race_skills() -> Iterable[Skill]:
    return (
        Skill.objects.filter(
            archived_at__isnull=True,
            famiglia__gruppo__slug=RACE_SKILL_GROUP_SLUG,
            metadata__automaticRaceUnlock=True,
        )
        .select_related("famiglia")
        .order_by("id")
    )


def plan_race_skill_sync() -> list[dict[str, Any]]:
    """Cosa cambierebbe la sincronizzazione, senza scrivere nulla."""
    planned = []
    for skill in race_skills():
        metadata = skill.metadata if isinstance(skill.metadata, dict) else {}
        kind = str(metadata.get("raceUnlockKind") or "")
        entry = _catalog_entry(
            skill,
            str(metadata.get("race") or ""),
            str(metadata.get("subrace") or ""),
            kind,
        )
        if entry is None:
            status = "non gestita" if kind in {"base", "razza"} else "senza voce di catalogo"
            planned.append({"skill": skill, "status": status, "passives": None, "actions": None})
            continue
        passives = _passive_payload(skill, entry)
        actions = _actions_payload(skill, entry)
        name = str(entry.get("name") or skill.nome)[:180]
        description = str(entry.get("note") or skill.descrizione or "")[:400]
        unchanged = (
            passives == (skill.effetti_passivi or [])
            and actions == (skill.azioni_attive or [])
            and name == skill.nome
            and description == (skill.descrizione or "")
        )
        planned.append(
            {
                "skill": skill,
                "status": "invariata" if unchanged else "da aggiornare",
                "passives": passives,
                "actions": actions,
                "name": name,
                "description": description,
            }
        )
    return planned


def sync_race_guide_text() -> int:
    """Applica le correzioni ReDjango alla guida Razze già salvata.

    Il testo è HTML importato da Elder e congelato al momento dell'import: la
    correzione in ``race_guide_html`` vale per i futuri import, non per la riga
    già in banca dati.
    """
    from backend.core.guides_it import apply_race_guide_corrections
    from backend.core.models import Guida

    changed = 0
    for guide in Guida.objects.filter(nome="Razze"):
        corrected = apply_race_guide_corrections(guide.contenuto or "")
        if corrected != guide.contenuto:
            guide.contenuto = corrected
            guide.save(update_fields=["contenuto", "updated_at"])
            changed += 1
    return changed


@transaction.atomic
def sync_race_skills() -> dict[str, int]:
    """Riscrive passivi e note delle abilità razziali dal catalogo.

    Non tocca le schede: i personaggi rileggono i passivi al successivo
    ``sync_racial_abilities``/``refresh_personaggio``, che il chiamante esegue.
    """
    updated = skipped = unmatched = 0
    for planned in plan_race_skill_sync():
        skill = planned["skill"]
        if planned["status"] == "senza voce di catalogo":
            unmatched += 1
            continue
        if planned["status"] in {"invariata", "non gestita"}:
            skipped += 1
            continue
        skill.effetti_passivi = planned["passives"]
        skill.azioni_attive = planned["actions"]
        skill.nome = planned["name"]
        skill.descrizione = planned["description"]
        skill.save(update_fields=["effetti_passivi", "azioni_attive", "nome", "descrizione", "updated_at"])
        updated += 1
    return {"updated": updated, "unchanged": skipped, "unmatched": unmatched}

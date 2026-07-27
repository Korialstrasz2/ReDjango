from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import models
from django.db.models import Q

from backend.characters.models import (
    EffettiPersonaggio,
    Equip,
    Faretra,
    Note,
    Personaggio,
    Zaino,
)
from backend.core.models import Effetto, Oggetto


PROFILE_FIELDS = [
    {"key": "nome", "label": "Nome", "type": "text", "group": "Identità"},
    {
        "key": "tipologia",
        "label": "Tipologia",
        "type": "select",
        "group": "Identità",
        "choices": [{"value": value, "label": label} for value, label in Personaggio.TYPE_CHOICES],
    },
    {"key": "nome_interno", "label": "Nome interno", "type": "text", "group": "Identità"},
    {"key": "razza_1", "label": "Razza 1", "type": "text", "group": "Identità"},
    {"key": "razza_2", "label": "Razza 2", "type": "text", "group": "Identità"},
    {"key": "razza_3", "label": "Razza 3", "type": "text", "group": "Identità"},
    {"key": "livello", "label": "Livello", "type": "integer", "group": "Identità", "minimum": 1},
    {"key": "eta", "label": "Età", "type": "integer", "group": "Identità", "nullable": True},
    {"key": "sesso", "label": "Sesso", "type": "text", "group": "Identità"},
    {
        "key": "dettagli_personaggio",
        "label": "Dettagli del personaggio",
        "type": "textarea",
        "group": "Identità",
    },
    {"key": "monete", "label": "Monete", "type": "integer", "group": "Risorse"},
    {"key": "danno", "label": "Danno subito", "type": "integer", "group": "Risorse", "minimum": 0},
    {"key": "stanchezza_accumulata", "label": "Stanchezza accumulata", "type": "integer", "group": "Risorse", "minimum": 0},
    {"key": "mana_speso", "label": "Mana speso", "type": "integer", "group": "Risorse", "minimum": 0},
    {"key": "energia_spesa", "label": "Energia spesa", "type": "integer", "group": "Risorse", "minimum": 0},
    {"key": "potere_speso", "label": "Potere speso", "type": "integer", "group": "Risorse", "minimum": 0},
    {"key": "mana_in_sifone", "label": "Mana nel sifone", "type": "integer", "group": "Risorse", "minimum": 0},
    {"key": "pe_generali", "label": "PE generali", "type": "integer", "group": "Esperienza"},
    {"key": "pe_rossi", "label": "PE rossi", "type": "integer", "group": "Esperienza"},
    {"key": "pe_verdi", "label": "PE verdi", "type": "integer", "group": "Esperienza"},
    {"key": "pe_blu", "label": "PE blu", "type": "integer", "group": "Esperienza"},
    {"key": "pe_abilita", "label": "PE abilita", "type": "integer", "group": "Esperienza"},
    {"key": "crit_min", "label": "Critico minimo", "type": "text", "group": "Regole"},
    {"key": "crit_nor", "label": "Critico normale", "type": "text", "group": "Regole"},
    {"key": "crit_mag", "label": "Critico magico", "type": "text", "group": "Regole"},
    {"key": "competenze", "label": "Competenze", "type": "json", "group": "Dati avanzati"},
    {"key": "abilita", "label": "Abilità", "type": "json", "group": "Dati avanzati"},
    {"key": "abilita_desiderate", "label": "Abilità desiderate", "type": "json", "group": "Dati avanzati"},
    {"key": "extra", "label": "Dati extra", "type": "json", "group": "Dati avanzati"},
    {"key": "bottoni", "label": "Bottoni", "type": "json", "group": "Dati avanzati"},
    {"key": "custom_overrides", "label": "Override formule", "type": "json", "group": "Dati avanzati"},
]


RELATION_CONFIG = {
    "equip": {"label": "Equipaggiamento", "model": Equip},
    "zaino": {"label": "Zaino", "model": Zaino},
    "faretra": {"label": "Faretra", "model": Faretra},
    "note": {"label": "Note", "model": Note},
    "effetti": {"label": "Effetti legacy", "model": EffettiPersonaggio},
}


FIELD_LABELS = {
    "nome": "Nome del record",
    "notes": "Note tecniche",
    "combat": "Combattimento",
    "crafting": "Crafting",
    "viaggio": "Viaggio",
    "appunti": "Appunti",
    "missioni": "Missioni",
    "background": "Background",
    "zaino": "Zaino",
}


def _humanize(value: str) -> str:
    return FIELD_LABELS.get(value, value.replace("_", " ").capitalize())


def _relation_field_specs(kind: str, model: type[models.Model]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for field in model._meta.fields:
        if field.name in {"id", "created_at", "updated_at", "archived_at", "metadata", "personaggio"}:
            continue
        if isinstance(field, models.ForeignKey):
            if field.related_model is Oggetto:
                field_type = "item"
            elif field.related_model is Effetto:
                field_type = "effect"
            else:
                continue
        elif isinstance(field, models.JSONField):
            field_type = "json"
        elif isinstance(field, models.TextField):
            field_type = "textarea"
        elif isinstance(field, (models.IntegerField, models.PositiveIntegerField)):
            field_type = "integer"
        elif isinstance(field, models.BooleanField):
            field_type = "boolean"
        else:
            field_type = "text"
        specs.append(
            {
                "key": field.name,
                "label": _humanize(field.name),
                "type": field_type,
                "group": "Contenuto" if field.name.startswith(("slot_", "effetto_")) else "Dati del record",
                "nullable": bool(getattr(field, "null", False)),
            }
        )
    return specs


RELATION_FIELDS = {
    kind: _relation_field_specs(kind, config["model"])
    for kind, config in RELATION_CONFIG.items()
}


def _profile_values(character: Personaggio) -> dict[str, Any]:
    return {field["key"]: getattr(character, field["key"]) for field in PROFILE_FIELDS}


def _relation_payload(character: Personaggio, kind: str) -> dict[str, Any]:
    config = RELATION_CONFIG[kind]
    instance = getattr(character, kind)
    specs = RELATION_FIELDS[kind]
    values: dict[str, Any] = {}
    if instance is not None:
        for spec in specs:
            key = spec["key"]
            values[key] = getattr(instance, f"{key}_id") if spec["type"] in {"item", "effect"} else getattr(instance, key)
    return {
        "kind": kind,
        "label": config["label"],
        "present": instance is not None,
        "id": instance.id if instance else None,
        "name": str(instance) if instance else "Record mancante",
        "fields": specs,
        "values": values,
    }


def _related_snapshot(character: Personaggio) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for kind, config in RELATION_CONFIG.items():
        instance = getattr(character, kind)
        if instance is None:
            records.append(
                {
                    "kind": kind,
                    "label": config["label"],
                    "id": None,
                    "name": "Non collegato",
                    "willDelete": False,
                    "status": "missing",
                    "detail": "Nessun record collegato a questo personaggio.",
                }
            )
            continue
        other_users = instance.personaggi.exclude(pk=character.pk).count()
        records.append(
            {
                "kind": kind,
                "label": config["label"],
                "id": instance.id,
                "name": str(instance),
                "willDelete": other_users == 0,
                "status": "delete" if other_users == 0 else "shared",
                "detail": (
                    "Sarà eliminato insieme al personaggio."
                    if other_users == 0
                    else f"Condiviso con {other_users} altri personaggi: verrà conservato."
                ),
            }
        )
    custom_effect_count = character.effetti_personalizzati.count()
    records.append(
        {
            "kind": "effetti_personalizzati",
            "label": "Effetti personali",
            "id": None,
            "name": f"{custom_effect_count} record",
            "willDelete": custom_effect_count > 0,
            "status": "delete" if custom_effect_count else "empty",
            "detail": "Eliminati automaticamente dal database." if custom_effect_count else "Nessun effetto personale.",
        }
    )
    private_button_count = character.bottoni_combat.filter(pubblico=False).count()
    public_button_count = character.bottoni_combat.filter(pubblico=True).count()
    records.extend([
        {
            "kind": "bottoni_combat_privati",
            "label": "Bottoni combat privati",
            "id": None,
            "name": f"{private_button_count} record",
            "willDelete": private_button_count > 0,
            "status": "delete" if private_button_count else "empty",
            "detail": "Eliminati insieme al personaggio." if private_button_count else "Nessun bottone combat privato.",
        },
        {
            "kind": "bottoni_combat_pubblici",
            "label": "Bottoni combat pubblici",
            "id": None,
            "name": f"{public_button_count} record",
            "willDelete": False,
            "status": "shared" if public_button_count else "empty",
            "detail": (
                "Conservati e assegnati al personaggio usato più di recente."
                if public_button_count
                else "Nessun bottone combat pubblico."
            ),
        },
    ])
    metadata = character.metadata if isinstance(character.metadata, dict) else {}
    cloned_item_ids = [int(value) for value in metadata.get("combat_cloned_item_ids", []) if str(value).isdigit()]
    cloned_effect_ids = [int(value) for value in metadata.get("combat_cloned_effect_ids", []) if str(value).isdigit()]
    if cloned_item_ids:
        records.append({
            "kind": "oggetti_copia_combattimento",
            "label": "Oggetti della copia",
            "id": None,
            "name": f"{Oggetto.objects.filter(id__in=cloned_item_ids).count()} record",
            "willDelete": True,
            "status": "delete",
            "detail": "Catalogo indipendente creato con la copia; sarà eliminato con il personaggio.",
        })
    if cloned_effect_ids:
        records.append({
            "kind": "effetti_copia_combattimento",
            "label": "Effetti della copia",
            "id": None,
            "name": f"{Effetto.objects.filter(id__in=cloned_effect_ids).count()} record",
            "willDelete": True,
            "status": "delete",
            "detail": "Definizioni indipendenti create con la copia; saranno eliminate con il personaggio.",
        })
    return records


def deletion_preview_token(character: Personaggio) -> str:
    snapshot = {
        "character": character.id,
        "updatedAt": character.updated_at.isoformat() if character.updated_at else "",
        "relations": [
            {
                "kind": record["kind"],
                "id": record["id"],
                "willDelete": record["willDelete"],
            }
            for record in _related_snapshot(character)
        ],
    }
    raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def deletion_preview_payload(character: Personaggio) -> dict[str, Any]:
    return {
        "token": deletion_preview_token(character),
        "confirmation": character.nome,
        "records": [
            {
                "kind": "personaggio",
                "label": "Personaggio",
                "id": character.id,
                "name": character.nome,
                "willDelete": True,
                "status": "delete",
                "detail": "Record principale e collegamenti dei giocatori.",
            },
            *_related_snapshot(character),
        ],
    }


def character_management_detail(character_id: int) -> dict[str, Any]:
    character = (
        Personaggio.objects.select_related(*RELATION_CONFIG.keys())
        .prefetch_related("effetti_personalizzati", "bottoni_combat")
        .get(pk=character_id)
    )
    return {
        "character": _character_summary(character),
        "profileFields": PROFILE_FIELDS,
        "profile": _profile_values(character),
        "relations": [_relation_payload(character, kind) for kind in RELATION_CONFIG],
        "options": {
            "items": [
                {"id": item.id, "name": item.nome, "archived": item.archiviato}
                for item in Oggetto.objects.order_by("nome")
            ],
            "effects": [
                {"id": effect.id, "name": effect.nome}
                for effect in Effetto.objects.order_by("nome")
            ],
        },
        "deletionPreview": deletion_preview_payload(character),
    }


def _character_summary(character: Personaggio) -> dict[str, Any]:
    missing = [kind for kind in RELATION_CONFIG if getattr(character, f"{kind}_id") is None]
    return {
        "id": character.id,
        "name": character.nome,
        "internalName": character.nome_interno,
        "type": character.get_tipologia_display(),
        "level": character.livello,
        "missingRelations": missing,
        "updatedAt": character.updated_at.isoformat() if character.updated_at else None,
    }


def _orphan_payload(kind: str, instance: models.Model) -> dict[str, Any]:
    owner_id = None
    reason = "Non è collegato ad alcun personaggio."
    if owner_id:
        reason = f"Indica il personaggio #{owner_id} come proprietario, ma non è collegato alla sua scheda."
    return {
        "kind": kind,
        "label": RELATION_CONFIG[kind]["label"],
        "id": instance.id,
        "name": str(instance),
        "reason": reason,
        "ownerCharacterId": owner_id,
        "updatedAt": instance.updated_at.isoformat() if instance.updated_at else None,
    }


def character_management_overview(query: str = "", orphan_kind: str = "") -> dict[str, Any]:
    characters = Personaggio.objects.select_related(*RELATION_CONFIG.keys()).order_by("nome")
    if query:
        characters = characters.filter(
            Q(nome__icontains=query)
            | Q(nome_interno__icontains=query)
            | Q(razza_1__icontains=query)
            | Q(razza_2__icontains=query)
            | Q(razza_3__icontains=query)
        )
    orphans: list[dict[str, Any]] = []
    for kind, config in RELATION_CONFIG.items():
        if orphan_kind and orphan_kind != kind:
            continue
        queryset = config["model"].objects.filter(personaggi__isnull=True).distinct().order_by("nome", "id")
        if query:
            queryset = queryset.filter(nome__icontains=query)
        orphans.extend(_orphan_payload(kind, instance) for instance in queryset)
    return {
        "characters": [_character_summary(character) for character in characters],
        "orphans": orphans,
        "relationKinds": [
            {"value": kind, "label": config["label"]}
            for kind, config in RELATION_CONFIG.items()
        ],
    }

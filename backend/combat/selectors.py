from __future__ import annotations

import re
from collections.abc import Mapping

from django.db.models import Prefetch
from django.templatetags.static import static

from backend.characters.models import BottoneCombat, Personaggio, SkillPersonaggio
from backend.characters.race_rules import automatic_race_effects
from backend.characters.selectors import (
    CHARACTERISTIC_KEYS,
    COMBAT_KEYS,
    RESISTANCE_KEYS,
    _container_payload,
    _equipment_payload,
    effect_catalog_payload,
)
from backend.characters.services.combat_buttons import serialize_combat_button
from backend.characters.services.inventory_rules import EQUIPMENT_SLOT_ORDER
from backend.core.models import Effetto, Giocatore, Oggetto, Unit
from backend.core.security import effective_role, has_minimum_role
from backend.core.settings_selectors import global_setting_value
from backend.core.spell_services import SPELL_ECONOMY_KEYS, serialize_spell

from .models import CharacterTemplate, CombatModifier, HexType, MapMetadata, MapType
from .unit_generation import unit_catalog_entry


RESOURCE_LABELS = {
    "pf": "Punti ferita",
    "mana": "Mana",
    "energia": "Energia",
    "potere": "Potere",
    "pa": "Punti Azione",
}

# Etichette con cui il giocatore filtra le azioni rapide. "no tag" non viene mai
# memorizzato: appartiene automaticamente a ogni azione rimasta senza etichette.
ACTION_TAGS = (
    "preferito",
    "incantesimo",
    "utility",
    "combat",
    "non combat",
    "distanza",
    "melee",
    "modalità",
    "no tag",
)
UNTAGGED_ACTION_TAG = "no tag"
STORABLE_ACTION_TAGS = tuple(tag for tag in ACTION_TAGS if tag != UNTAGGED_ACTION_TAG)
DEFAULT_ACTION_TAG_FILTERS = ("preferito", "combat", UNTAGGED_ACTION_TAG)


def _number(value):
    try:
        number = round(float(value or 0), 6)
    except (TypeError, ValueError):
        return 0
    return int(number) if number.is_integer() else number


def _combat_resources(character: Personaggio) -> list[dict]:
    totals = character.tot if isinstance(character.tot, dict) else {}
    spent = {
        "pf": character.danno,
        "mana": character.mana_speso,
        "energia": character.energia_spesa,
        "potere": character.potere_speso,
        "pa": 0,
    }
    resources = []
    for key in ("pf", "mana", "energia", "potere", "pa"):
        maximum = max(0, int(float(totals.get(key, 0) or 0)))
        current = max(0, maximum - int(spent[key] or 0))
        resources.append(
            {
                "key": key,
                "label": RESOURCE_LABELS[key],
                "current": current,
                "maximum": maximum,
                "spent": int(spent[key] or 0),
                "percent": round((current / maximum) * 100, 1) if maximum else 0,
                "colorToken": f"--resource-{key}",
            }
        )
    return resources


def normalized_action_tags(raw) -> list[str]:
    """Etichette memorizzabili, senza duplicati e nell'ordine canonico."""
    if not isinstance(raw, (list, tuple)):
        return []
    chosen = {str(tag).strip().lower() for tag in raw}
    return [tag for tag in STORABLE_ACTION_TAGS if tag in chosen]


def normalized_tag_filters(raw) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return list(DEFAULT_ACTION_TAG_FILTERS)
    chosen = {str(tag).strip().lower() for tag in raw}
    return [tag for tag in ACTION_TAGS if tag in chosen]


def _combat_action_settings(character: Personaggio) -> dict:
    stored = character.impostazioni_combat if isinstance(character.impostazioni_combat, dict) else {}
    raw_tags = stored.get("actionTags")
    tags = {}
    if isinstance(raw_tags, Mapping):
        for key, values in raw_tags.items():
            normalized = normalized_action_tags(values)
            if normalized:
                tags[str(key)] = normalized
    return {
        "tags": tags,
        "tagFilters": normalized_tag_filters(stored.get("tagFilters")),
    }


def _spell_economy(totals: Mapping) -> dict:
    return {name: _number(totals.get(key)) for name, key in SPELL_ECONOMY_KEYS.items()}


def _combat_skill_ownerships(character: Personaggio) -> list[SkillPersonaggio]:
    prefetched = getattr(character, "_combat_skill_ownerships", None)
    if prefetched is not None:
        return prefetched
    return list(
        SkillPersonaggio.objects.filter(
            personaggio=character,
            archived_at__isnull=True,
            skill__archived_at__isnull=True,
        ).select_related(
            "skill",
            "skill__famiglia",
            "skill__famiglia__gruppo",
            "skill__spell_definition",
        )
    )


def _combat_skills(character: Personaggio) -> list[dict]:
    result = []
    for ownership in _combat_skill_ownerships(character):
        skill = ownership.skill
        spell = serialize_spell(skill)
        result.append(
            {
                "id": skill.id,
                "name": skill.nome,
                "description": skill.descrizione,
                "magic": spell is not None,
                "spell": spell,
                "activeReminders": (
                    skill.azioni_attive
                    if isinstance(skill.azioni_attive, list)
                    else []
                ),
            }
        )
    if result:
        return result
    abilities = character.abilita if isinstance(character.abilita, dict) else {}
    return [
        skill
        for skill in abilities.get("skills", [])
        if isinstance(skill, dict)
    ]


def _combat_buttons(character: Personaggio) -> list[dict]:
    buttons = getattr(character, "_active_combat_buttons", None)
    if buttons is None:
        buttons = list(
            character.bottoni_combat.filter(attivo=True)
            .select_related("personaggio")[:12]
        )
    return [
        serialize_combat_button(button, can_edit=False)
        for button in buttons[:12]
    ]


def _effect_ids(character: Personaggio) -> set[int]:
    effetti = character.effetti
    return {
        effect_id
        for index in range(1, 51)
        if effetti is not None
        and (effect_id := getattr(effetti, f"effetto_{index}_id", None))
    }


def _temporary_effect(description: str) -> bool:
    return bool(
        re.search(
            r"(?:^|\s)\(t\)(?:\s|$)",
            description or "",
            re.IGNORECASE,
        )
    )


def _combat_effects(
    character: Personaggio,
    legacy_effects: Mapping[int, Effetto],
) -> list[dict]:
    entries = []
    effetti = character.effetti
    for index in range(1, 51):
        effect_id = (
            getattr(effetti, f"effetto_{index}_id", None)
            if effetti is not None
            else None
        )
        effect = legacy_effects.get(effect_id)
        if effect is None:
            continue
        entries.append(
            {
                "scope": "legacy",
                "slot": index,
                "id": effect.id,
                "name": effect.nome,
                "type": effect.tipo,
                "description": effect.descrizione,
                "durationTurns": effect.durata_turni,
                "icon": effect.icona,
                "originName": effect.origine_nome,
                "temporary": _temporary_effect(effect.descrizione),
                "order": index,
            }
        )

    custom_effects = getattr(character, "_combat_custom_effects", None)
    if custom_effects is None:
        custom_effects = list(character.effetti_personalizzati.all())
    for custom in custom_effects:
        entries.append(
            {
                "scope": "custom",
                "slot": None,
                "id": custom.id,
                "name": custom.nome,
                "type": "",
                "description": custom.descrizione,
                "durationTurns": None,
                "icon": custom.icona,
                "originName": custom.origine,
                "temporary": custom.temporaneo,
                "order": 50 + custom.ordine,
            }
        )

    has_imported_racial_abilities = any(
        isinstance(ownership.metadata, dict)
        and ownership.metadata.get("source") == "race.auto"
        for ownership in _combat_skill_ownerships(character)
    )
    if not has_imported_racial_abilities:
        for index, effect in enumerate(
            automatic_race_effects(character.razza_1, character.razza_2),
            start=1,
        ):
            entries.append(
                {
                    "scope": "automatic",
                    "slot": None,
                    "id": -index,
                    "name": effect["name"],
                    "type": "Razziale automatico",
                    "description": effect["description"],
                    "durationTurns": None,
                    "icon": effect["icon"],
                    "originName": effect["originName"],
                    "temporary": False,
                    "order": -100 + index,
                }
            )
    return sorted(entries, key=lambda entry: entry["order"])


def _combat_item_ids(character: Personaggio) -> set[int]:
    item_ids = set()
    if character.equip:
        item_ids.update(
            item_id
            for slot in EQUIPMENT_SLOT_ORDER
            if (item_id := getattr(character.equip, f"{slot}_id", None))
        )
    if character.faretra:
        item_ids.update(
            item_id
            for index in range(1, 51)
            if (item_id := getattr(character.faretra, f"slot_{index}_id", None))
        )
    return item_ids


def _prime_equipment_items(
    character: Personaggio,
    items: Mapping[int, Oggetto],
) -> None:
    if character.equip is None:
        return
    for slot in EQUIPMENT_SLOT_ORDER:
        item_id = getattr(character.equip, f"{slot}_id", None)
        if item_id and item_id in items:
            character.equip._state.fields_cache[slot] = items[item_id]


def _combat_quiver_payload(
    character: Personaggio,
    items: Mapping[int, Oggetto],
) -> dict:
    payload = _container_payload(
        character,
        "quiver",
        character.faretra,
        dict(items),
    )
    occupied_indexes = [
        index
        for index, slot in enumerate(payload["slots"], start=1)
        if slot["item"] is not None
    ]
    visible_slots = max(
        int(payload["capacity"] or 0),
        max(occupied_indexes, default=0),
    )
    payload["slots"] = payload["slots"][:visible_slots]
    return payload


def _character_payload(
    character: Personaggio,
    *,
    items: Mapping[int, Oggetto] | None = None,
    legacy_effects: Mapping[int, Effetto] | None = None,
) -> dict:
    if items is None:
        items = Oggetto.objects.filter(
            id__in=_combat_item_ids(character)
        ).select_related("tipo_arma", "media").in_bulk()
    if legacy_effects is None:
        legacy_effects = Effetto.objects.filter(
            id__in=_effect_ids(character)
        ).in_bulk()
    _prime_equipment_items(character, items)
    totals = character.tot if isinstance(character.tot, dict) else {}
    equipment = _equipment_payload(character.equip, dict(items), totals)
    portrait = (
        character.portrait.file.url
        if character.portrait_id
        and character.portrait
        and character.portrait.file
        else static("frontend/images/characters/placeholder.svg")
    )
    abilities = character.abilita if isinstance(character.abilita, dict) else {}
    return {
        "id": character.id,
        "name": character.nome,
        "internalName": character.nome_interno,
        "type": character.tipologia,
        "level": character.livello,
        "races": [value for value in (character.razza_1, character.razza_2, character.razza_3) if value],
        "portrait": portrait,
        "resources": _combat_resources(character),
        "combat": {key: _number(totals.get(key)) for key in COMBAT_KEYS},
        "resistances": {
            key: _number(totals.get(key))
            for key in RESISTANCE_KEYS
        },
        "characteristics": {
            key: _number(totals.get(key))
            for key in CHARACTERISTIC_KEYS
        },
        "criticalThresholds": {
            "minor": character.crit_min,
            "normal": character.crit_nor,
            "major": character.crit_mag,
        },
        "equipment": equipment,
        "quiver": _combat_quiver_payload(character, items),
        "effects": _combat_effects(character, legacy_effects),
        "skills": _combat_skills(character),
        "abilities": [
            ability
            for ability in abilities.get("known", [])
            if isinstance(ability, dict)
        ],
        "combatButtons": _combat_buttons(character),
        "spellEconomy": _spell_economy(totals),
        "actionSettings": _combat_action_settings(character),
    }


def _map_summary(map_obj, *, include_revision: bool):
    summary = {
        "id": map_obj.id,
        "name": map_obj.name,
        "mapType": map_obj.map_type.name,
        "imageUrl": map_obj.image.file.url if map_obj.image_id and map_obj.image.file else "",
        "updatedAt": map_obj.updated_at.isoformat(),
        "isDefault": map_obj.is_default,
    }
    if include_revision:
        summary["revision"] = map_obj.revision
    return summary


def _map_payload(map_obj: MapMetadata, *, can_manage: bool, viewer_character_id: int | None):
    participant_rows = list(
        map_obj.participants.filter(active=True)
        .select_related(
            "character",
            "character__portrait",
            "character__equip",
            "character__faretra",
            "character__effetti",
        )
        .prefetch_related(
            "footprint",
            Prefetch(
                "character__skill_sbloccate",
                queryset=SkillPersonaggio.objects.filter(
                    archived_at__isnull=True,
                    skill__archived_at__isnull=True,
                ).select_related(
                    "skill",
                    "skill__famiglia",
                    "skill__famiglia__gruppo",
                    "skill__spell_definition",
                ),
                to_attr="_combat_skill_ownerships",
            ),
            Prefetch(
                "character__bottoni_combat",
                queryset=BottoneCombat.objects.filter(attivo=True)
                .select_related("personaggio")
                .order_by("ordine", "id"),
                to_attr="_active_combat_buttons",
            ),
            Prefetch(
                "character__effetti_personalizzati",
                to_attr="_combat_custom_effects",
            ),
        )
        .order_by("order", "id")
    )
    hex_rows = list(map_obj.hexes.prefetch_related("terrain_types").all())
    if map_obj.fog_enabled and not can_manage:
        revealed_cells = {(entry.q, entry.r) for entry in hex_rows if entry.revealed}
        participant_rows = [
            row for row in participant_rows
            if row.character_id == viewer_character_id or (row.anchor_q, row.anchor_r) in revealed_cells
        ]
        hex_rows = [entry for entry in hex_rows if entry.revealed]
    characters = {row.character_id: row.character for row in participant_rows}
    item_ids = set().union(
        *(_combat_item_ids(character) for character in characters.values())
    ) if characters else set()
    items = Oggetto.objects.filter(id__in=item_ids).select_related(
        "tipo_arma",
        "media",
    ).in_bulk()
    effect_ids = set().union(
        *(_effect_ids(character) for character in characters.values())
    ) if characters else set()
    legacy_effects = Effetto.objects.filter(id__in=effect_ids).in_bulk()
    character_cache = {
        character_id: _character_payload(
            character,
            items=items,
            legacy_effects=legacy_effects,
        )
        for character_id, character in characters.items()
    }
    modifier_states = {state.modifier_id: state.enabled for state in map_obj.modifier_states.all()}
    return {
        **_map_summary(map_obj, include_revision=can_manage),
        "mapTypeId": map_obj.map_type_id,
        "imageId": map_obj.image_id,
        "orientation": map_obj.orientation,
        "rows": map_obj.rows,
        "columns": map_obj.columns,
        "hexSize": float(map_obj.hex_size),
        "gridOffsetX": float(map_obj.grid_offset_x),
        "gridOffsetY": float(map_obj.grid_offset_y),
        "imageScale": float(map_obj.image_scale),
        "imageOffsetX": float(map_obj.image_offset_x),
        "imageOffsetY": float(map_obj.image_offset_y),
        "viewportScale": float(map_obj.viewport_scale),
        "viewportOffsetX": float(map_obj.viewport_offset_x),
        "viewportOffsetY": float(map_obj.viewport_offset_y),
        "fogEnabled": map_obj.fog_enabled,
        "fogOpacity": float(map_obj.fog_opacity),
        "viewerCanSeeAll": can_manage,
        "activeCharacterId": map_obj.active_character_id,
        "activeCharacterIds": [row.character_id for row in participant_rows],
        "participants": [
            {
                "id": row.id,
                "character": character_cache[row.character_id],
                "anchor": {"q": row.anchor_q, "r": row.anchor_r},
                "footprint": [{"q": cell.q, "r": cell.r} for cell in row.footprint.all()] or [{"q": 0, "r": 0}],
                "tokenColor": row.token_color,
                "order": row.order,
            }
            for row in participant_rows
        ],
        "hexes": [
            {
                "id": row.id,
                "q": row.q,
                "r": row.r,
                "overlayColor": row.overlay_color,
                "overlayOpacity": float(row.overlay_opacity),
                "blocked": row.blocked,
                "revealed": row.revealed,
                "fogEffect": row.fog_effect,
                "terrainTypeIds": [terrain.id for terrain in row.terrain_types.all()],
            }
            for row in hex_rows
        ],
        "modifiers": [
            {
                "id": modifier.id,
                "name": modifier.name,
                "scope": modifier.scope,
                "attackBonus": modifier.attack_bonus,
                "damageBonus": modifier.damage_bonus,
                "penetrationFlat": modifier.penetration_flat,
                "penetrationPercent": modifier.penetration_percent,
                "description": modifier.description,
                "color": modifier.color,
                "enabled": modifier_states.get(modifier.id, False),
            }
            for modifier in CombatModifier.objects.filter(active=True, archived_at__isnull=True)
        ],
        "plannedActions": [
            {
                "id": action.id,
                "characterId": action.character_id,
                "actionType": action.action_type,
                "name": action.name,
                "description": action.description,
                "order": action.order,
                "costs": {
                    "pf": action.cost_pf,
                    "mana": action.cost_mana,
                    "energia": action.cost_energy,
                    "potere": action.cost_power,
                    "pa": action.cost_ap,
                    "stanchezza": action.cost_fatigue,
                },
                "committedAt": action.committed_at.isoformat() if action.committed_at else None,
                "sourceSkillId": action.source_skill_id,
                "path": [{"q": step.q, "r": step.r} for step in action.path.all()],
            }
            for action in map_obj.planned_actions.select_related("character", "source_skill").prefetch_related("path").all()
        ],
        "events": [
            {
                "id": event.id,
                "type": event.event_type,
                "message": event.message,
                "payload": event.payload,
                "createdAt": event.created_at.isoformat(),
            }
            for event in map_obj.events.all()[:50]
        ],
        "snapshots": [
            {
                "id": snapshot.id,
                "revision": snapshot.revision,
                "label": snapshot.label,
                "createdAt": snapshot.created_at.isoformat(),
                "createdBy": snapshot.created_by.display_name if snapshot.created_by_id else "Sistema",
            }
            for snapshot in map_obj.snapshots.select_related("created_by").all()[:30]
        ] if can_manage else [],
    }


def combat_workspace_payload(user, giocatore: Giocatore, map_id=None):
    maps = MapMetadata.objects.select_related("map_type", "image").filter(archived_at__isnull=True)
    selected = maps.filter(pk=map_id).first() if map_id else maps.filter(is_default=True).first() or maps.first()
    can_manage = has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)
    characters = Personaggio.objects.filter(archived_at__isnull=True).order_by("nome")
    focus_character = characters.filter(pk=giocatore.active_character_id).first()
    if selected and selected.active_character_id:
        focus_character = characters.filter(pk=selected.active_character_id).first() or focus_character
    selected_map_payload = (
        _map_payload(
            MapMetadata.objects.select_related(
                "map_type",
                "image",
                "active_character",
            )
            .prefetch_related(
                "hexes__terrain_types",
                "modifier_states__modifier",
                "planned_actions__path",
                "events",
                "snapshots__created_by",
            )
            .get(pk=selected.pk),
            can_manage=can_manage,
            viewer_character_id=giocatore.active_character_id,
        )
        if selected
        else None
    )
    focus_payload = next(
        (
            participant["character"]
            for participant in (
                (selected_map_payload or {}).get("participants") or []
            )
            if focus_character
            and participant["character"]["id"] == focus_character.id
        ),
        None,
    )
    if focus_payload is None and focus_character:
        focus_payload = _character_payload(focus_character)
    return {
        "maps": [_map_summary(entry, include_revision=can_manage) for entry in maps],
        "map": selected_map_payload,
        "focusCharacter": focus_payload,
        "viewerCharacterId": giocatore.active_character_id,
        "mapTypes": [
            {
                "id": entry.id,
                "name": entry.name,
                "slug": entry.slug,
                "description": entry.description,
                "orientation": entry.default_orientation,
                "rows": entry.default_rows,
                "columns": entry.default_columns,
            }
            for entry in MapType.objects.filter(active=True, archived_at__isnull=True)
        ],
        "hexTypes": [
            {
                "id": entry.id,
                "name": entry.name,
                "slug": entry.slug,
                "description": entry.description,
                "movementMultiplier": float(entry.movement_multiplier),
                "color": entry.color,
                "impassable": entry.impassable,
            }
            for entry in HexType.objects.filter(active=True, archived_at__isnull=True)
        ],
        "characterCatalog": [
            {
                "id": entry.id,
                "name": entry.nome,
                "type": entry.tipologia,
                "level": entry.livello,
                "races": [value for value in (entry.razza_1, entry.razza_2, entry.razza_3) if value],
            }
            for entry in characters
        ] if can_manage else [],
        "templates": [
            {
                "id": entry.id,
                "name": entry.name,
                "description": entry.description,
                "imageUrl": entry.image.file.url if entry.image_id and entry.image.file else "",
                "version": (entry.blueprint or {}).get("version", 1),
            }
            for entry in CharacterTemplate.objects.filter(active=True, archived_at__isnull=True).select_related("image")
        ] if can_manage else [],
        "unitCatalog": [
            unit_catalog_entry(entry)
            for entry in Unit.objects.filter(archived_at__isnull=True).order_by("categoria", "nome")
        ] if can_manage else [],
        "baseMovementAp": float(global_setting_value("combat.base_movement_ap", 1) or 1),
        "effectCatalog": effect_catalog_payload() if can_manage else [],
        "permissions": {
            "canManageMaps": can_manage,
            "canImportCharacters": can_manage,
            "canControlCharacters": can_manage,
            "canApplyEnemyEffects": can_manage,
        },
    }

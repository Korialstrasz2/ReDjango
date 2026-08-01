from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from uuid import uuid4

from django.db import models, transaction
from django.utils import timezone

from backend.characters.models import (
    BottoneCombat,
    ContenitoreInventario,
    EffettiPersonaggio,
    EffettoPersonalizzato,
    Equip,
    Faretra,
    Note,
    OperazioneEffettoPersonalizzato,
    Personaggio,
    SkillPersonaggio,
    VoceContenitoreInventario,
    Zaino,
)
from backend.characters.services.commands import apply_effect, switch_primary_weapon
from backend.characters.services.inventory_rules import active_equipped_weapon, equipment_dual_wield, item_weapon_profile, normalize_item_types, sort_container_items_by_weight
from backend.characters.services.refresh_personaggio import refresh_personaggio
from backend.characters.services.resources import accrue_mana_siphon, calculate_energy_spend
from backend.core.api import ApiError
from backend.core.models import Effetto, Giocatore, Oggetto, Skill, Unit
from backend.core.security import effective_role, has_minimum_role
from backend.core.settings_selectors import global_setting_value

from .models import (
    CharacterTemplate,
    CombatEvent,
    CombatModifier,
    CombatModifierState,
    HexType,
    MapHex,
    MapMetadata,
    MapParticipant,
    MapParticipantFootprint,
    MapSnapshot,
    MapType,
    TurnPlanAction,
    TurnPlanStep,
)
from .selectors import normalized_action_tags, normalized_tag_filters
from .rules import (
    axial_to_offset,
    direct_hex_line,
    fastest_path,
    hex_distance,
    offset_to_axial,
    resolve_attack_values,
    resolve_direct_damage_values,
)
from .unit_generation import create_unit_character


MAP_BACKUP_INTERVAL = 4
MAP_BACKUP_LIMIT = 3


def require_master(user, giocatore: Giocatore):
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER):
        raise ApiError("combat.permission_denied", "Questa operazione richiede il Master.", status=403)


def _event(map_obj, event_type, message, *, actor=None, payload=None):
    return CombatEvent.objects.create(
        map=map_obj,
        event_type=event_type,
        message=message,
        actor=actor,
        payload=payload or {},
    )


def _bump(map_obj, giocatore: Giocatore | None = None):
    # Persist any dirty map fields before the revision is advanced so an
    # automatic snapshot always represents the state the user just produced.
    map_obj.save()
    map_obj.revision = models.F("revision") + 1
    map_obj.save(update_fields=["revision", "updated_at"])
    map_obj.refresh_from_db(fields=["revision", "updated_at"])
    latest_backup_revision = map_obj.snapshots.order_by("-revision", "-id").values_list("revision", flat=True).first() or 0
    if map_obj.revision % MAP_BACKUP_INTERVAL == 0 or map_obj.revision - latest_backup_revision >= MAP_BACKUP_INTERVAL:
        _create_map_snapshot(map_obj, giocatore, f"Backup automatico · revisione {map_obj.revision}")


def _weapon_state(equip: Equip | None) -> dict[str, dict[str, int]]:
    metadata = equip.metadata if equip and isinstance(equip.metadata, dict) else {}
    raw = metadata.get("weaponState")
    return copy.deepcopy(raw) if isinstance(raw, dict) else {}


def _loaded_projectiles(equip: Equip | None, weapon: Oggetto | None, magazine_size: int) -> int:
    if not equip or not weapon or magazine_size <= 0:
        return 0
    entry = _weapon_state(equip).get(str(weapon.id), {})
    try:
        return max(0, min(magazine_size, int(entry.get("loaded", magazine_size))))
    except (TypeError, ValueError):
        return magazine_size


def _save_loaded_projectiles(equip: Equip, weapon: Oggetto, loaded: int) -> None:
    state = _weapon_state(equip)
    state[str(weapon.id)] = {"loaded": max(0, int(loaded))}
    metadata = dict(equip.metadata) if isinstance(equip.metadata, dict) else {}
    equip.metadata = {**metadata, "weaponState": state}
    equip.save(update_fields=["metadata", "updated_at"])


def _ammunition_slot(character: Personaggio, ammunition_type: str) -> int | None:
    if not character.faretra:
        return None
    aliases = {
        "freccia": {"freccia", "frecce"},
        "dardo": {"dardo", "dardi"},
        "proiettile": {"proiettile", "proiettili", "munizione", "munizioni"},
    }.get(ammunition_type, {ammunition_type})
    for index in range(1, 51):
        projectile = getattr(character.faretra, f"slot_{index}", None)
        if projectile and normalize_item_types(projectile) & aliases:
            return index
    return None


def _clone_row(instance, *, overrides=None):
    values = {}
    overrides = overrides or {}
    for field in instance._meta.concrete_fields:
        if field.primary_key or field.name in ("created_at", "updated_at", "archived_at"):
            continue
        if field.name in overrides:
            values[field.name] = overrides[field.name]
        elif field.is_relation:
            values[field.name] = getattr(instance, field.name)
        else:
            values[field.name] = copy.deepcopy(getattr(instance, field.name))
    values.update({key: value for key, value in overrides.items() if key not in values})
    return instance.__class__.objects.create(**values)


def _unique_name(model, base, field="nome"):
    base = (base or model.__name__)[:150]
    candidate = f"{base} (copia)"
    index = 2
    while model.objects.filter(**{field: candidate}).exists():
        candidate = f"{base} (copia {index})"
        index += 1
    return candidate


MAP_SNAPSHOT_FIELDS = (
    "name", "map_type_id", "image_id", "orientation", "rows", "columns", "hex_size",
    "grid_offset_x", "grid_offset_y", "image_scale", "image_offset_x", "image_offset_y",
    "viewport_scale", "viewport_offset_x", "viewport_offset_y", "fog_enabled", "fog_opacity",
    "active_character_id", "is_default",
)


def _map_snapshot_state(map_obj: MapMetadata) -> dict:
    map_obj = (
        MapMetadata.objects.select_related("map_type", "image", "active_character")
        .prefetch_related("hexes__terrain_types", "participants__footprint", "modifier_states")
        .get(pk=map_obj.pk)
    )
    decimal_fields = {
        "hex_size", "grid_offset_x", "grid_offset_y", "image_scale", "image_offset_x",
        "image_offset_y", "viewport_scale", "viewport_offset_x", "viewport_offset_y", "fog_opacity",
    }
    metadata = {
        field: float(getattr(map_obj, field)) if field in decimal_fields else getattr(map_obj, field)
        for field in MAP_SNAPSHOT_FIELDS
    }
    return {
        "metadata": metadata,
        "hexes": [
            {
                "q": entry.q,
                "r": entry.r,
                "overlay_color": entry.overlay_color,
                "overlay_opacity": float(entry.overlay_opacity),
                "blocked": entry.blocked,
                "revealed": entry.revealed,
                "fog_effect": entry.fog_effect,
                "terrain_type_ids": [terrain.id for terrain in entry.terrain_types.all()],
            }
            for entry in map_obj.hexes.all()
        ],
        "participants": [
            {
                "character_id": entry.character_id,
                "active": entry.active,
                "anchor_q": entry.anchor_q,
                "anchor_r": entry.anchor_r,
                "token_color": entry.token_color,
                "order": entry.order,
                "footprint": [{"q": cell.q, "r": cell.r} for cell in entry.footprint.all()],
            }
            for entry in map_obj.participants.all()
        ],
        "modifier_states": [
            {"modifier_id": entry.modifier_id, "enabled": entry.enabled}
            for entry in map_obj.modifier_states.all()
        ],
    }


def _create_map_snapshot(map_obj: MapMetadata, giocatore: Giocatore | None, label: str = "") -> MapSnapshot:
    snapshot = MapSnapshot.objects.create(
        map=map_obj,
        revision=map_obj.revision,
        label=(label or f"Revisione {map_obj.revision}").strip()[:180],
        state=_map_snapshot_state(map_obj),
        created_by=giocatore,
    )
    retained_ids = list(map_obj.snapshots.order_by("-id").values_list("id", flat=True)[:MAP_BACKUP_LIMIT])
    map_obj.snapshots.exclude(id__in=retained_ids).delete()
    return snapshot


def _clone_character_graph(source: Personaggio) -> Personaggio:
    # Containers are character-owned state, while the Oggetto and Effetto rows
    # stored in their slots are shared catalogue definitions.  This mirrors the
    # Elder clone methods: duplicate the container row and keep every FK target.
    equip = _clone_row(source.equip, overrides={"nome": f"{source.nome} · Equip"}) if source.equip else None
    zaino = _clone_row(source.zaino, overrides={"nome": f"{source.nome} · Zaino"}) if source.zaino else None
    faretra = _clone_row(source.faretra, overrides={"nome": f"{source.nome} · Faretra"}) if source.faretra else None
    effects = _clone_row(source.effetti, overrides={"nome": f"{source.nome} · Effetti"}) if source.effetti else None
    note = _clone_row(source.note, overrides={"nome": f"{source.nome} · Note"}) if source.note else None
    metadata = copy.deepcopy(source.metadata or {})
    for key in ("combat_owned_item_ids", "combat_cloned_item_ids", "combat_cloned_effect_ids"):
        metadata.pop(key, None)
    metadata.update({"combat_clone_source_id": source.id})
    clone = _clone_row(
        source,
        overrides={
            "nome": _unique_name(Personaggio, source.nome),
            "nome_interno": f"{source.nome_interno}-combat-{uuid4().hex[:10]}",
            "equip": equip,
            "zaino": zaino,
            "faretra": faretra,
            "effetti": effects,
            "note": note,
            "metadata": metadata,
        },
    )
    source_container = source.contenitori_inventario.filter(scope="personal").first()
    if source_container:
        clone_container = ContenitoreInventario.objects.create(
            nome=f"Alchimia&Contenitori · {clone.nome}"[:160],
            scope="personal",
            personaggio=clone,
            capacita=source_container.capacita,
            senza_peso=True,
            metadata=copy.deepcopy(source_container.metadata),
        )
        VoceContenitoreInventario.objects.bulk_create([
            VoceContenitoreInventario(
                contenitore=clone_container,
                slot=entry.slot,
                oggetto=entry.oggetto,
                reagent_stock_key=entry.reagent_stock_key,
                quantita=entry.quantita,
                metadata=copy.deepcopy(entry.metadata),
            )
            for entry in source_container.voci.all()
        ])
    for ownership in source.skill_sbloccate.all():
        SkillPersonaggio.objects.create(
            personaggio=clone,
            skill=ownership.skill,
            spesa_pe=copy.deepcopy(ownership.spesa_pe),
            passivi_accettati=copy.deepcopy(ownership.passivi_accettati),
            configurazione_azioni=copy.deepcopy(ownership.configurazione_azioni),
            note=ownership.note,
            metadata=copy.deepcopy(ownership.metadata),
        )
    for effect in source.effetti_personalizzati.prefetch_related("operazioni"):
        new_effect = EffettoPersonalizzato.objects.create(
            personaggio=clone,
            nome=effect.nome,
            descrizione=effect.descrizione,
            origine=effect.origine,
            icona=effect.icona,
            temporaneo=effect.temporaneo,
            ordine=effect.ordine,
        )
        OperazioneEffettoPersonalizzato.objects.bulk_create([
            OperazioneEffettoPersonalizzato(
                effetto=new_effect,
                ordine=operation.ordine,
                bersaglio=operation.bersaglio,
                operazione=operation.operazione,
                valore=operation.valore,
                condizione=operation.condizione,
            )
            for operation in effect.operazioni.all()
        ])
    return clone


def _character_from_template(template: CharacterTemplate) -> Personaggio:
    blueprint = template.blueprint if isinstance(template.blueprint, dict) else {}
    profile = copy.deepcopy(blueprint.get("profile") or {})
    allowed = {field.name for field in Personaggio._meta.concrete_fields if field.editable and not field.primary_key}
    profile = {key: value for key, value in profile.items() if key in allowed and key not in {"equip", "zaino", "faretra", "effetti", "note"}}
    base_name = str(profile.get("nome") or template.name)
    profile.update({
        "nome": _unique_name(Personaggio, base_name),
        "nome_interno": f"{template.slug}-{uuid4().hex[:10]}",
        "tipologia": profile.get("tipologia") or "nemico",
        "tot": copy.deepcopy(blueprint.get("totals") or profile.get("tot") or {}),
        "competenze": copy.deepcopy(blueprint.get("competencies") or profile.get("competenze") or {}),
        "abilita": copy.deepcopy(blueprint.get("abilities") or profile.get("abilita") or {}),
        "metadata": {"combat_template_id": template.id, "combat_template_version": blueprint.get("version", 1)},
    })
    equip = Equip.objects.create(nome=f"{profile['nome']} · Equip")
    zaino = Zaino.objects.create(nome=f"{profile['nome']} · Zaino")
    faretra = Faretra.objects.create(nome=f"{profile['nome']} · Faretra")
    effects = EffettiPersonaggio.objects.create(nome=f"{profile['nome']} · Effetti")
    note_values = blueprint.get("notes") or {}
    note = Note.objects.create(nome=f"{profile['nome']} · Note", **{key: str(value) for key, value in note_values.items() if hasattr(Note, key)})
    reagent_values = blueprint.get("reagents") or {}
    character = Personaggio.objects.create(
        **profile,
        equip=equip,
        zaino=zaino,
        faretra=faretra,
        effetti=effects,
        note=note,
    )
    reagent_container = ContenitoreInventario.objects.create(
        nome=f"Alchimia&Contenitori · {profile['nome']}"[:160],
        scope="personal",
        personaggio=character,
        capacita=max(15, int(reagent_values.get("capacity") or 0)),
        senza_peso=True,
    )
    for slot, (stock_key, quantity) in enumerate(
        sorted((reagent_values.get("ingredients") or {}).items()),
        start=1,
    ):
        if int(quantity or 0) > 0:
            VoceContenitoreInventario.objects.create(
                contenitore=reagent_container,
                slot=slot,
                reagent_stock_key=stock_key,
                quantita=int(quantity),
            )
    cloned_item_ids = []

    def provision_item(entry):
        if not isinstance(entry, dict):
            entry = {"itemId": entry}
        source = Oggetto.objects.filter(pk=entry.get("itemId")).first()
        if source:
            item = _clone_row(
                source,
                overrides={
                    "nome": _unique_name(Oggetto, source.nome),
                    "modello": False,
                    "metadata": {**copy.deepcopy(source.metadata or {}), "combat_template_id": template.id},
                },
            )
        else:
            definition = entry.get("item") if isinstance(entry.get("item"), dict) else {}
            allowed_item_fields = {
                field.name for field in Oggetto._meta.concrete_fields
                if field.editable and not field.primary_key and not field.is_relation
            }
            values = {key: copy.deepcopy(value) for key, value in definition.items() if key in allowed_item_fields}
            base_item_name = str(values.pop("nome", "") or entry.get("name") or "Oggetto")
            item = Oggetto.objects.create(
                **values,
                nome=_unique_name(Oggetto, base_item_name),
                modello=False,
                metadata={"combat_template_id": template.id},
            )
        cloned_item_ids.append(item.id)
        return item

    for blueprint_key, container in (("equipment", equip), ("inventory", zaino), ("quiver", faretra)):
        for index, entry in enumerate(blueprint.get(blueprint_key) or [], start=1):
            normalized = entry if isinstance(entry, dict) else {"itemId": entry}
            fallback = f"slot_{index}"
            slot = str(normalized.get("slot") or fallback)
            if hasattr(container, slot):
                setattr(container, slot, provision_item(normalized))
        container.save()
    cloned_effect_ids = []
    for index, entry in enumerate(blueprint.get("effects") or [], start=1):
        if index > 50:
            break
        normalized = entry if isinstance(entry, dict) else {"effectId": entry}
        source = Effetto.objects.filter(pk=normalized.get("effectId")).first()
        if source:
            effect = _clone_row(
                source,
                overrides={
                    "nome": _unique_name(Effetto, source.nome),
                    "metadata": {**copy.deepcopy(source.metadata or {}), "combat_template_id": template.id},
                },
            )
        else:
            definition = normalized.get("effect") if isinstance(normalized.get("effect"), dict) else {}
            allowed_effect_fields = {
                field.name for field in Effetto._meta.concrete_fields
                if field.editable and not field.primary_key and not field.is_relation
            }
            values = {key: copy.deepcopy(value) for key, value in definition.items() if key in allowed_effect_fields}
            base_effect_name = str(values.pop("nome", "") or normalized.get("name") or "Effetto")
            effect = Effetto.objects.create(
                **values,
                nome=_unique_name(Effetto, base_effect_name),
                metadata={"combat_template_id": template.id},
            )
        setattr(effects, str(normalized.get("slot") or f"effetto_{index}"), effect)
        cloned_effect_ids.append(effect.id)
    effects.save()
    for entry in blueprint.get("skills") or []:
        skill_id = entry.get("skillId") if isinstance(entry, dict) else entry
        skill = Skill.objects.filter(pk=skill_id).first()
        if skill:
            SkillPersonaggio.objects.create(personaggio=character, skill=skill, configurazione_azioni=copy.deepcopy(entry.get("actions") or {}) if isinstance(entry, dict) else {})
    for index, definition in enumerate(blueprint.get("customEffects") or []):
        if not isinstance(definition, dict) or not definition.get("name"):
            continue
        custom = EffettoPersonalizzato.objects.create(
            personaggio=character,
            nome=str(definition["name"]),
            descrizione=str(definition.get("description") or ""),
            origine=str(definition.get("origin") or template.name),
            icona=str(definition.get("icon") or "runa"),
            temporaneo=bool(definition.get("temporary")),
            ordine=index,
        )
        OperazioneEffettoPersonalizzato.objects.bulk_create([
            OperazioneEffettoPersonalizzato(
                effetto=custom,
                ordine=operation_index,
                bersaglio=str(operation.get("target") or ""),
                operazione=str(operation.get("operation") or "add"),
                valore=str(operation.get("value") or "0"),
                condizione=str(operation.get("condition") or ""),
            )
            for operation_index, operation in enumerate(definition.get("operations") or [])
            if isinstance(operation, dict) and operation.get("target")
        ])
    character.metadata.update({
        "combat_cloned_item_ids": cloned_item_ids,
        "combat_cloned_effect_ids": cloned_effect_ids,
        "combat_template_coverage": [
            "profile", "totals", "competencies", "abilities", "skills", "equipment",
            "inventory", "quiver", "effects", "customEffects", "notes", "reagents",
        ],
    })
    character.save(update_fields=["metadata", "updated_at"])
    return character


@transaction.atomic
def create_or_update_map(user, giocatore, payload: dict):
    require_master(user, giocatore)
    map_id = payload.get("mapId")
    map_obj = MapMetadata.objects.select_for_update().filter(pk=map_id).first() if map_id else None
    map_type = MapType.objects.filter(pk=payload.get("mapTypeId"), active=True).first()
    if not map_type:
        raise ApiError("combat.map_type_required", "Scegli un tipo di mappa.", "mapTypeId")
    values = {
        "name": str(payload.get("name") or "Nuova mappa").strip(),
        "map_type": map_type,
        "image_id": payload.get("imageId") or None,
        "orientation": payload.get("orientation") if payload.get("orientation") in ("pointy", "flat") else map_type.default_orientation,
        "rows": max(1, min(200, int(payload.get("rows") or map_type.default_rows))),
        "columns": max(1, min(200, int(payload.get("columns") or map_type.default_columns))),
        "hex_size": max(4, float(payload.get("hexSize") or 34)),
        "grid_offset_x": float(payload.get("gridOffsetX") or 0),
        "grid_offset_y": float(payload.get("gridOffsetY") or 0),
        "image_scale": max(.05, float(payload.get("imageScale") or 1)),
        "image_offset_x": float(payload.get("imageOffsetX") or 0),
        "image_offset_y": float(payload.get("imageOffsetY") or 0),
        "viewport_scale": max(.05, float(payload.get("viewportScale") or 1)),
        "viewport_offset_x": float(payload.get("viewportOffsetX") or 0),
        "viewport_offset_y": float(payload.get("viewportOffsetY") or 0),
        "fog_enabled": bool(payload.get("fogEnabled", map_obj.fog_enabled if map_obj else False)),
        "fog_opacity": max(0, min(1, float(payload.get("fogOpacity", map_obj.fog_opacity if map_obj else .88)))),
    }
    if map_obj:
        for key, value in values.items():
            setattr(map_obj, key, value)
        _bump(map_obj, giocatore)
        message = f"Mappa {map_obj.name} aggiornata."
    else:
        map_obj = MapMetadata.objects.create(created_by=giocatore, **values)
        if giocatore.active_character_id:
            participant = MapParticipant.objects.create(
                map=map_obj,
                character_id=giocatore.active_character_id,
                anchor_q=0,
                anchor_r=0,
                order=0,
            )
            MapParticipantFootprint.objects.create(participant=participant, q=0, r=0)
            map_obj.active_character_id = giocatore.active_character_id
            map_obj.save(update_fields=["active_character", "updated_at"])
        message = f"Mappa {map_obj.name} creata."
    _event(map_obj, "map.saved", message)
    return map_obj


@transaction.atomic
def create_map_type(user, giocatore, payload):
    require_master(user, giocatore)
    name = str(payload.get("name") or "").strip()
    slug = str(payload.get("slug") or "").strip().lower().replace(" ", "-")
    if not name or not slug:
        raise ApiError("combat.map_type_invalid", "Nome e chiave del tipo mappa sono obbligatori.")
    return MapType.objects.create(
        name=name,
        slug=slug,
        description=str(payload.get("description") or ""),
        default_orientation=payload.get("orientation") if payload.get("orientation") in ("pointy", "flat") else "pointy",
        default_rows=max(1, int(payload.get("rows") or 24)),
        default_columns=max(1, int(payload.get("columns") or 32)),
    )


@transaction.atomic
def import_character(user, giocatore, payload):
    require_master(user, giocatore)
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    if payload.get("templateId"):
        template = CharacterTemplate.objects.get(pk=payload["templateId"], active=True)
        character = _character_from_template(template)
    else:
        source = Personaggio.objects.get(pk=payload["characterId"])
        character = _clone_character_graph(source)
    raw_ids = giocatore.character_ids if isinstance(giocatore.character_ids, list) else []
    giocatore.character_ids = [*raw_ids, character.id]
    giocatore.save(update_fields=["character_ids", "updated_at"])
    participant = MapParticipant.objects.create(
        map=map_obj,
        character=character,
        anchor_q=int(payload.get("q") or 0),
        anchor_r=int(payload.get("r") or 0),
        order=map_obj.participants.count(),
    )
    footprint = payload.get("footprint") or [{"q": 0, "r": 0}]
    MapParticipantFootprint.objects.bulk_create([
        MapParticipantFootprint(participant=participant, q=int(cell.get("q") or 0), r=int(cell.get("r") or 0))
        for cell in footprint
    ])
    if not map_obj.active_character_id:
        map_obj.active_character = character
    _bump(map_obj)
    map_obj.save()
    _event(map_obj, "character.imported", f"{character.nome} importato come copia del personaggio.", actor=character)
    return character


@transaction.atomic
def generate_unit(user, giocatore, payload):
    require_master(user, giocatore)
    try:
        map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    except (KeyError, MapMetadata.DoesNotExist) as exc:
        raise ApiError("combat.map_not_found", "Mappa non trovata.", "mapId", 404) from exc
    try:
        unit = Unit.objects.get(pk=payload["unitId"], archived_at__isnull=True)
    except (KeyError, Unit.DoesNotExist) as exc:
        raise ApiError("combat.unit_not_found", "Unit non trovata.", "unitId", 404) from exc
    try:
        level = int(payload.get("level") or 1)
    except (TypeError, ValueError) as exc:
        raise ApiError("combat.unit_level_invalid", "Inserisci un livello valido.", "level") from exc
    if not 1 <= level <= 20:
        raise ApiError("combat.unit_level_invalid", "Il livello deve essere compreso tra 1 e 20.", "level")
    variant = str(payload.get("variant") or "auto").strip()[:80] or "auto"
    character = create_unit_character(unit, level, variant)
    if giocatore.active_campaign_id and not character.campagna_id:
        character.campagna_id = giocatore.active_campaign_id
        character.save(update_fields=["campagna", "updated_at"])
    raw_ids = giocatore.character_ids if isinstance(giocatore.character_ids, list) else []
    giocatore.character_ids = [*raw_ids, character.id]
    giocatore.save(update_fields=["character_ids", "updated_at"])
    participant = MapParticipant.objects.create(
        map=map_obj,
        character=character,
        anchor_q=int(payload.get("q") or 0),
        anchor_r=int(payload.get("r") or 0),
        order=map_obj.participants.count(),
    )
    footprint = payload.get("footprint") or [{"q": 0, "r": 0}]
    MapParticipantFootprint.objects.bulk_create(
        [
            MapParticipantFootprint(
                participant=participant,
                q=int(cell.get("q") or 0),
                r=int(cell.get("r") or 0),
            )
            for cell in footprint
            if isinstance(cell, Mapping)
        ]
    )
    if not participant.footprint.exists():
        MapParticipantFootprint.objects.create(participant=participant, q=0, r=0)
    if not map_obj.active_character_id:
        map_obj.active_character = character
    _bump(map_obj)
    map_obj.save()
    _event(
        map_obj,
        "character.generated",
        f"{character.nome} generato dalla Unit {unit.nome} al livello {level}.",
        actor=character,
        payload={"unitId": unit.id, "level": level, "variant": variant},
    )
    return character


def _occupied_cells(map_obj, exclude_participant_id=None):
    occupied = set()
    participants = map_obj.participants.filter(active=True).prefetch_related("footprint")
    if exclude_participant_id:
        participants = participants.exclude(pk=exclude_participant_id)
    for participant in participants:
        occupied.update(_participant_cells(participant, (participant.anchor_q, participant.anchor_r)))
    return occupied


def _participant_cells(participant, anchor):
    cells = list(participant.footprint.all()) or [MapParticipantFootprint(q=0, r=0)]
    anchor_axial = offset_to_axial(anchor, participant.map.orientation)
    return [
        axial_to_offset((anchor_axial[0] + cell.q, anchor_axial[1] + cell.r), participant.map.orientation)
        for cell in cells
    ]


def _in_bounds(map_obj, cell):
    return 0 <= cell[0] < map_obj.columns and 0 <= cell[1] < map_obj.rows


def _first_available_anchor(map_obj, participant):
    blocked = _occupied_cells(map_obj, participant.id)
    for r in range(map_obj.rows):
        for q in range(map_obj.columns):
            anchor = (q, r)
            cells = _participant_cells(participant, anchor)
            if all(_in_bounds(map_obj, cell) and cell not in blocked for cell in cells):
                return anchor
    raise ApiError("combat.map_full", "Non c'è spazio libero per aggiungere questo personaggio alla mappa.", status=409)


@transaction.atomic
def ensure_viewer_character(giocatore, payload):
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    character = giocatore.active_character
    if not character or character.archived_at:
        return map_obj, False
    existing = map_obj.participants.filter(character=character).first()
    if existing:
        # An inactive row is intentional: it records that a Master removed this
        # character and prevents a later page visit from silently restoring it.
        if existing.active and map_obj.active_character_id != character.id:
            map_obj.active_character = character
            map_obj.save(update_fields=["active_character", "updated_at"])
            _bump(map_obj)
        return map_obj, False
    participant = MapParticipant.objects.create(
        map=map_obj,
        character=character,
        active=False,
        order=map_obj.participants.count(),
    )
    MapParticipantFootprint.objects.create(participant=participant, q=0, r=0)
    participant.anchor_q, participant.anchor_r = _first_available_anchor(map_obj, participant)
    participant.active = True
    participant.save(update_fields=["anchor_q", "anchor_r", "active", "updated_at"])
    # Il personaggio appena entrato diventa quello attivo della mappa, anche se
    # la mappa ne ricordava già un altro. Senza questo, chi apre Combattimento
    # con un personaggio nuovo vede ancora nell'inspector, nel token evidenziato
    # e nel pannello d'attacco il PG che occupava la mappa dalla sessione prima.
    # Vale solo alla prima entrata: dopo, la scelta resta al Master tramite
    # combat.activateCharacter.
    map_obj.active_character = character
    map_obj.save(update_fields=["active_character", "updated_at"])
    _bump(map_obj)
    _event(map_obj, "participant.joined", f"{character.nome} è entrato nella mappa.", actor=character)
    return map_obj, True


@transaction.atomic
def activate_character(user, giocatore, payload):
    require_master(user, giocatore)
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    character = Personaggio.objects.get(pk=payload["characterId"], archived_at__isnull=True)
    participant, created = MapParticipant.objects.get_or_create(
        map=map_obj,
        character=character,
        defaults={"active": False, "order": map_obj.participants.count()},
    )
    if participant.active:
        return map_obj, False
    if created or not participant.footprint.exists():
        MapParticipantFootprint.objects.get_or_create(participant=participant, q=0, r=0)
    requested_footprint = payload.get("footprint") or []
    if requested_footprint:
        participant.footprint.all().delete()
        MapParticipantFootprint.objects.bulk_create([
            MapParticipantFootprint(participant=participant, q=int(cell.get("q") or 0), r=int(cell.get("r") or 0))
            for cell in requested_footprint
        ])
    participant.anchor_q, participant.anchor_r = _first_available_anchor(map_obj, participant)
    participant.active = True
    participant.save(update_fields=["anchor_q", "anchor_r", "active", "updated_at"])
    if not map_obj.active_character_id:
        map_obj.active_character = character
        map_obj.save(update_fields=["active_character", "updated_at"])
    _bump(map_obj)
    _event(map_obj, "participant.activated", f"{character.nome} aggiunto ai personaggi attivi.", actor=character)
    return map_obj, True


@transaction.atomic
def move_participant(user, giocatore, payload):
    participant = MapParticipant.objects.select_for_update().select_related("map", "character").prefetch_related("footprint").get(pk=payload["participantId"])
    can_manage = has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)
    if not can_manage and participant.character_id != giocatore.active_character_id:
        raise ApiError("combat.participant_not_controlled", "Puoi spostare soltanto il personaggio che controlli.", status=403)
    anchor = int(payload["q"]), int(payload["r"])
    blocked = _occupied_cells(participant.map, participant.id)
    cells = _participant_cells(participant, anchor)
    if any(not _in_bounds(participant.map, cell) or cell in blocked for cell in cells):
        raise ApiError("combat.invalid_placement", "La sagoma non entra nella posizione scelta.", status=409)
    participant.anchor_q, participant.anchor_r = anchor
    participant.active = True
    participant.save(update_fields=["anchor_q", "anchor_r", "active", "updated_at"])
    _bump(participant.map)
    _event(participant.map, "participant.moved", f"{participant.character.nome} spostato.", actor=participant.character, payload={"q": anchor[0], "r": anchor[1]})
    return participant.map


@transaction.atomic
def update_combat_resource(user, giocatore, payload):
    participant = (
        MapParticipant.objects.select_for_update()
        .select_related("map", "character")
        .get(map_id=payload["mapId"], character_id=payload["characterId"], active=True)
    )
    character = Personaggio.objects.select_for_update().get(pk=participant.character_id)
    can_manage = has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)
    if not can_manage and participant.character_id != giocatore.active_character_id:
        raise ApiError("combat.character_not_controlled", "Puoi modificare soltanto le risorse del personaggio che controlli.", status=403)

    resource = str(payload["resource"])
    if resource == "pa":
        raise ApiError(
            "combat.action_points_local_only",
            "I Punti Azione del combattimento esistono soltanto in questa pagina e non vengono salvati.",
            "resource",
        )
    storage_fields = {
        "pf": "danno",
        "mana": "mana_speso",
        "energia": "energia_spesa",
        "potere": "potere_speso",
        "stanchezza": "stanchezza_accumulata",
    }
    field_name = storage_fields.get(resource)
    if field_name is None:
        raise ApiError("combat.unknown_resource", "La risorsa scelta non è disponibile.", "resource")

    totals = character.tot if isinstance(character.tot, dict) else {}
    maximum = max(10, int(float(totals.get(resource) or 0))) if resource == "stanchezza" else max(0, int(float(totals.get(resource) or 0)))
    current = max(0, min(maximum, int(payload["current"])))
    stored_value = current if resource == "stanchezza" else maximum - current
    spent_before = int(getattr(character, field_name) or 0)
    setattr(character, field_name, stored_value)
    character.save(update_fields=[field_name, "updated_at"])
    # Solo una spesa vera alimenta il sifone: rialzare la barra non lo riempie.
    if resource == "mana" and stored_value - spent_before > 0:
        accrue_mana_siphon(character, stored_value - spent_before)
    if resource == "stanchezza":
        refresh_personaggio(character)
        character.refresh_from_db()
    _event(
        participant.map,
        "character.resource_updated",
        f"{character.nome}: {resource.upper()} aggiornato a {current}/{maximum}.",
        actor=character,
        payload={"resource": resource, "current": current, "maximum": maximum},
    )
    return participant.map


@transaction.atomic
def update_action_settings(user, giocatore, payload):
    """Salva sul personaggio le etichette delle azioni e i filtri delle Azioni rapide."""
    participant = (
        MapParticipant.objects.select_related("map", "character")
        .get(map_id=payload["mapId"], character_id=payload["characterId"], active=True)
    )
    character = Personaggio.objects.select_for_update().get(pk=participant.character_id)
    can_manage = has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)
    if not can_manage and participant.character_id != giocatore.active_character_id:
        raise ApiError(
            "combat.character_not_controlled",
            "Puoi configurare soltanto le azioni del personaggio che controlli.",
            status=403,
        )

    stored = dict(character.impostazioni_combat) if isinstance(character.impostazioni_combat, dict) else {}
    if "tags" in payload:
        raw_tags = payload["tags"]
        if not isinstance(raw_tags, Mapping):
            raise ApiError("combat.action_tags_invalid", "Le etichette delle azioni non sono valide.", "tags")
        # Un'azione senza etichette memorizzate vale "no tag": non la salviamo.
        stored["actionTags"] = {
            str(key): normalized
            for key, raw in raw_tags.items()
            if (normalized := normalized_action_tags(raw))
        }
    if "tagFilters" in payload:
        raw_filters = payload["tagFilters"]
        if not isinstance(raw_filters, (list, tuple)):
            raise ApiError("combat.tag_filters_invalid", "I filtri delle etichette non sono validi.", "tagFilters")
        stored["tagFilters"] = normalized_tag_filters(raw_filters)
    character.impostazioni_combat = stored
    character.save(update_fields=["impostazioni_combat", "updated_at"])
    return participant.map


@transaction.atomic
def set_active_character(payload):
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    participant = map_obj.participants.filter(character_id=payload["characterId"], active=True).first()
    if not participant:
        raise ApiError("combat.participant_missing", "Il personaggio non è attivo su questa mappa.", status=404)
    map_obj.active_character_id = participant.character_id
    _bump(map_obj)
    map_obj.save()
    _event(map_obj, "participant.selected", f"{participant.character.nome} è ora il personaggio in primo piano.", actor=participant.character)
    return map_obj


@transaction.atomic
def deactivate_participant(user, giocatore, payload):
    require_master(user, giocatore)
    participant = MapParticipant.objects.select_for_update().select_related("map", "character").get(pk=payload["participantId"])
    participant.active = False
    participant.save(update_fields=["active", "updated_at"])
    if participant.map.active_character_id == participant.character_id:
        replacement = participant.map.participants.filter(active=True).exclude(pk=participant.pk).first()
        participant.map.active_character_id = replacement.character_id if replacement else None
    _bump(participant.map)
    participant.map.save()
    _event(participant.map, "participant.deactivated", f"{participant.character.nome} rimosso dalla mappa; la copia resta in Gestione Personaggi.", actor=participant.character)
    return participant.map


@transaction.atomic
def update_hex(user, giocatore, payload):
    require_master(user, giocatore)
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    q, r = int(payload["q"]), int(payload["r"])
    if not _in_bounds(map_obj, (q, r)):
        raise ApiError("combat.hex_outside_map", "L'esagono non appartiene alla mappa.")
    map_hex, _ = MapHex.objects.get_or_create(map=map_obj, q=q, r=r)
    color = str(payload.get("overlayColor") or "")
    map_hex.overlay_color = color if color.startswith("#") and len(color) == 7 else ""
    map_hex.overlay_opacity = max(0, min(1, float(payload.get("overlayOpacity", .35))))
    map_hex.blocked = bool(payload.get("blocked"))
    if "fogEffect" in payload:
        map_hex.fog_effect = bool(payload.get("fogEffect"))
    if "revealed" in payload:
        map_hex.revealed = bool(payload.get("revealed"))
    map_hex.save()
    terrain_ids = [int(value) for value in payload.get("terrainTypeIds") or []]
    map_hex.terrain_types.set(HexType.objects.filter(id__in=terrain_ids, active=True))
    _bump(map_obj)
    _event(map_obj, "hex.updated", f"Esagono {q},{r} aggiornato.", payload={"q": q, "r": r})
    return map_obj


def _hexes_in_radius(map_obj: MapMetadata, center: tuple[int, int], radius: int) -> list[tuple[int, int]]:
    radius = max(0, min(20, int(radius)))
    return [
        (q, r)
        for r in range(map_obj.rows)
        for q in range(map_obj.columns)
        if hex_distance(center, (q, r), map_obj.orientation) <= radius
    ]


@transaction.atomic
def paint_hexes(user, giocatore, payload):
    require_master(user, giocatore)
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    raw_cells = payload.get("cells") or []
    if payload.get("center") is not None:
        center = payload["center"]
        cells = _hexes_in_radius(map_obj, (int(center["q"]), int(center["r"])), int(payload.get("radius") or 0))
    else:
        cells = [(int(cell["q"]), int(cell["r"])) for cell in raw_cells[:5000]]
    cells = list(dict.fromkeys(cell for cell in cells if _in_bounds(map_obj, cell)))
    if not cells:
        raise ApiError("combat.paint_empty", "Scegli almeno un esagono da colorare.")
    color_supplied = "overlayColor" in payload or bool(payload.get("clear"))
    color = str(payload.get("overlayColor") or "")
    color = color if color.startswith("#") and len(color) == 7 else ""
    opacity = max(0, min(1, float(payload.get("overlayOpacity", .35))))
    clear = bool(payload.get("clear"))
    terrain_supplied = "terrainTypeIds" in payload
    terrain_ids = [int(value) for value in payload.get("terrainTypeIds") or []]
    terrain_types = list(HexType.objects.filter(id__in=terrain_ids, active=True)) if terrain_supplied else []
    for q, r in cells:
        map_hex, _ = MapHex.objects.get_or_create(map=map_obj, q=q, r=r)
        changed_fields = []
        if color_supplied:
            map_hex.overlay_color = "" if clear else color
            map_hex.overlay_opacity = 0 if clear else opacity
            changed_fields.extend(["overlay_color", "overlay_opacity"])
        if "fogEffect" in payload:
            map_hex.fog_effect = bool(payload.get("fogEffect"))
            changed_fields.append("fog_effect")
        if "blocked" in payload:
            map_hex.blocked = bool(payload.get("blocked"))
            changed_fields.append("blocked")
        if "revealed" in payload:
            map_hex.revealed = bool(payload.get("revealed"))
            changed_fields.append("revealed")
        if changed_fields:
            map_hex.save(update_fields=[*changed_fields, "updated_at"])
        if terrain_supplied:
            map_hex.terrain_types.set(terrain_types)
    _bump(map_obj)
    operation = "tipologia aggiornata" if terrain_supplied else "nebbia aggiornata" if "fogEffect" in payload else "ripuliti" if clear else "colorati"
    _event(map_obj, "hexes.painted", f"{len(cells)} esagoni: {operation}.", payload={"cells": len(cells), "clear": clear})
    return map_obj


@transaction.atomic
def update_fog(user, giocatore, payload):
    require_master(user, giocatore)
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    if "enabled" in payload:
        map_obj.fog_enabled = bool(payload.get("enabled"))
    if "opacity" in payload:
        map_obj.fog_opacity = max(0, min(1, float(payload.get("opacity") or 0)))
    mode = str(payload.get("mode") or "")
    cells: list[tuple[int, int]] = []
    if mode == "reset":
        map_obj.hexes.update(revealed=False)
    elif mode in {"reveal", "hide"}:
        center = payload.get("center") or {}
        center_cell = int(center.get("q") or 0), int(center.get("r") or 0)
        cells = _hexes_in_radius(map_obj, center_cell, int(payload.get("radius") or 0))
        for q, r in cells:
            map_hex, _ = MapHex.objects.get_or_create(map=map_obj, q=q, r=r)
            map_hex.revealed = mode == "reveal"
            map_hex.save(update_fields=["revealed", "updated_at"])
    map_obj.save(update_fields=["fog_enabled", "fog_opacity", "updated_at"])
    _bump(map_obj)
    message = "Nebbia di guerra aggiornata."
    if cells:
        message = f"{len(cells)} esagoni {'rivelati' if mode == 'reveal' else 'nascosti'}."
    _event(map_obj, "fog.updated", message, payload={"mode": mode, "cells": len(cells)})
    return map_obj


def calculate_paths(payload):
    map_obj = MapMetadata.objects.prefetch_related("hexes__terrain_types", "participants__footprint").get(pk=payload["mapId"])
    start = int(payload["start"]["q"]), int(payload["start"]["r"])
    end = int(payload["end"]["q"]), int(payload["end"]["r"])
    direct = direct_hex_line(start, end, map_obj.orientation)
    edited = {(entry.q, entry.r): entry for entry in map_obj.hexes.all()}
    occupied = _occupied_cells(map_obj, payload.get("participantId"))

    def step_cost(cell):
        entry = edited.get(cell)
        if cell in occupied or (entry and entry.blocked):
            return None
        multiplier = 1.0
        if entry:
            for terrain in entry.terrain_types.all():
                if terrain.impassable:
                    return None
                multiplier *= float(terrain.movement_multiplier)
        return multiplier

    base = float(global_setting_value("combat.base_movement_ap", 1) or 1)
    result = fastest_path(
        start,
        end,
        in_bounds=lambda cell: _in_bounds(map_obj, cell),
        step_cost=step_cost,
        base_cost=base,
        orientation=map_obj.orientation,
    )
    fastest, cost = result if result else ([], None)
    return {
        "direct": {
            "path": [{"q": q, "r": r} for q, r in direct],
            "distance": hex_distance(start, end, map_obj.orientation),
            "cost": hex_distance(start, end, map_obj.orientation),
        },
        "fastest": {
            "path": [{"q": q, "r": r} for q, r in fastest],
            "distance": max(0, len(fastest) - 1) if fastest else None,
            "cost": cost,
            "actionPoints": math.ceil(cost) if cost is not None else None,
        },
    }


@transaction.atomic
def toggle_modifier(payload):
    state, _ = CombatModifierState.objects.update_or_create(
        map_id=payload["mapId"],
        modifier_id=payload["modifierId"],
        defaults={"enabled": bool(payload.get("enabled"))},
    )
    _bump(state.map)
    _event(state.map, "modifier.toggled", f"Modificatore {state.modifier.name} aggiornato.")
    return state.map


@transaction.atomic
def switch_combat_primary_weapon(user, giocatore, payload):
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    character = Personaggio.objects.get(pk=payload["characterId"])
    if not map_obj.participants.filter(character=character, active=True).exists():
        raise ApiError("combat.participant_missing", "Il personaggio non è attivo sulla mappa.", status=409)
    can_manage = has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)
    if not can_manage and character.id != giocatore.active_character_id:
        raise ApiError("combat.attacker_not_controlled", "Puoi cambiare arma soltanto al personaggio che controlli.", status=403)
    switch_primary_weapon(character.id)
    character.refresh_from_db()
    weapon = active_equipped_weapon(character.equip)
    _bump(map_obj)
    _event(
        map_obj,
        "equipment.primary_weapon_switched",
        f"{character.nome} impugna ora {weapon.nome if weapon else 'le mani nude'} come arma primaria.",
        actor=character,
        payload={"characterId": character.id, "weaponId": weapon.id if weapon else None, "actionPointCost": 0},
    )
    return map_obj


@transaction.atomic
def reload_active_weapon(user, giocatore, payload):
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    character = Personaggio.objects.select_for_update().select_related("equip", "faretra").get(pk=payload["characterId"])
    if not map_obj.participants.filter(character=character, active=True).exists():
        raise ApiError("combat.participant_missing", "Il personaggio non è attivo sulla mappa.", status=409)
    can_manage = has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)
    if not can_manage and character.id != giocatore.active_character_id:
        raise ApiError("combat.attacker_not_controlled", "Puoi ricaricare soltanto per il personaggio che controlli.", status=403)
    weapon = active_equipped_weapon(character.equip)
    profile = item_weapon_profile(weapon)
    magazine_size = max(0, int(profile.get("magazineSize") or 0))
    if weapon is None or magazine_size <= 0:
        raise ApiError("combat.weapon_not_reloadable", "L'arma primaria non usa un caricatore.", status=409)
    loaded = _loaded_projectiles(character.equip, weapon, magazine_size)
    missing = magazine_size - loaded
    if missing <= 0:
        raise ApiError("combat.weapon_already_loaded", "Il caricatore è già pieno.", status=409)
    base_cost = max(0, int(profile.get("reloadBaseCost") or 0))
    per_projectile = max(0, int(profile.get("reloadPerProjectileCost") or 0))
    action_point_cost = base_cost + per_projectile * missing
    _save_loaded_projectiles(character.equip, weapon, magazine_size)

    participant = map_obj.participants.get(character=character, active=True)
    provokes_opportunity = any(
        hex_distance(
            (participant.anchor_q, participant.anchor_r),
            (other.anchor_q, other.anchor_r),
            map_obj.orientation,
        ) <= 1
        for other in map_obj.participants.filter(active=True).exclude(character=character)
    )
    result = {
        "characterId": character.id,
        "weaponId": weapon.id,
        "weaponName": weapon.nome,
        "loaded": magazine_size,
        "actionPointCost": action_point_cost,
        "provokesOpportunityAttack": provokes_opportunity,
    }
    _bump(map_obj)
    message = f"{character.nome} ricarica {weapon.nome} spendendo {action_point_cost} PA."
    if provokes_opportunity:
        message += " La ricarica in mischia espone a un attacco di opportunità."
    _event(map_obj, "combat.weapon_reloaded", message, actor=character, payload=result)
    return map_obj, result


@transaction.atomic
def remove_quiver_item(user, giocatore, payload):
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    character = Personaggio.objects.select_for_update().select_related("faretra").get(pk=payload["characterId"])
    if not map_obj.participants.filter(character=character, active=True).exists():
        raise ApiError("combat.participant_missing", "Il personaggio non e attivo sulla mappa.", status=409)
    can_manage = has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)
    if not can_manage and character.id != giocatore.active_character_id:
        raise ApiError("combat.character_not_controlled", "Puoi usare soltanto la faretra del personaggio che controlli.", status=403)
    slot = str(payload.get("slot") or "")
    try:
        slot_index = int(slot)
    except (TypeError, ValueError) as error:
        raise ApiError("combat.invalid_quiver_slot", "Lo spazio della faretra non e valido.", "slot") from error
    item = getattr(character.faretra, f"slot_{slot_index}", None) if character.faretra and 1 <= slot_index <= 50 else None
    if item is None:
        raise ApiError("combat.quiver_slot_empty", "Questo spazio della faretra e gia vuoto.", status=409)
    setattr(character.faretra, f"slot_{slot_index}", None)
    character.faretra.save(update_fields=[f"slot_{slot_index}", "updated_at"])
    _mapping, changed_fields = sort_container_items_by_weight(character.faretra)
    if changed_fields:
        character.faretra.save(update_fields=[*changed_fields, "updated_at"])
    refresh_personaggio(character)
    _bump(map_obj, giocatore)
    _event(
        map_obj,
        "combat.quiver_item_removed",
        f"{item.nome} rimosso dalla faretra di {character.nome}.",
        actor=character,
        payload={"characterId": character.id, "slot": slot, "itemId": item.id},
    )
    return map_obj


@transaction.atomic
def resolve_attack(user, giocatore, payload):
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    attacker = Personaggio.objects.select_for_update().get(pk=payload["attackerId"])
    defender = Personaggio.objects.select_for_update().get(pk=payload["defenderId"])
    if attacker.equip_id:
        attacker.equip = Equip.objects.select_for_update().get(pk=attacker.equip_id)
    if attacker.faretra_id:
        attacker.faretra = Faretra.objects.select_for_update().get(pk=attacker.faretra_id)
    if attacker.id == defender.id:
        raise ApiError("combat.same_combatant", "Attaccante e difensore devono essere due personaggi diversi.")
    active_ids = set(map_obj.participants.filter(active=True).values_list("character_id", flat=True))
    if attacker.id not in active_ids or defender.id not in active_ids:
        raise ApiError("combat.participant_missing", "Attaccante e difensore devono essere attivi sulla mappa.", status=409)
    can_manage = has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)
    if not can_manage and attacker.id != giocatore.active_character_id:
        raise ApiError("combat.attacker_not_controlled", "Puoi attaccare soltanto con il personaggio che controlli.", status=403)
    weapon = active_equipped_weapon(attacker.equip)
    weapon_profile = item_weapon_profile(weapon)
    weapon_mode = str(weapon_profile.get("combatMode") or "melee")
    ammunition_type = str(weapon_profile.get("ammunitionType") or "")
    magazine_size = max(0, int(weapon_profile.get("magazineSize") or 0))
    loaded_before = _loaded_projectiles(attacker.equip, weapon, magazine_size)
    ammunition_slot = _ammunition_slot(attacker, ammunition_type) if weapon_mode == "ranged" and ammunition_type else None
    if weapon_mode == "ranged" and ammunition_type and ammunition_slot is None:
        raise ApiError("combat.ammunition_missing", f"Serve una munizione di tipo {ammunition_type} nella faretra.", status=409)
    if weapon_mode == "ranged" and magazine_size and loaded_before <= 0:
        raise ApiError("combat.weapon_reload_required", f"{weapon.nome} deve essere ricaricata prima di attaccare.", status=409)
    attacker_participant = map_obj.participants.get(character=attacker, active=True)
    defender_participant = map_obj.participants.get(character=defender, active=True)
    attack_distance = hex_distance(
        (attacker_participant.anchor_q, attacker_participant.anchor_r),
        (defender_participant.anchor_q, defender_participant.anchor_r),
        map_obj.orientation,
    )
    range_attack_penalty = 0
    if weapon_mode in {"ranged", "throwable"}:
        base_range = int(weapon_profile.get("baseRangeMeters") or (4 if weapon_mode == "throwable" else 9))
        if attack_distance > base_range:
            range_attack_penalty -= 2 * (attack_distance - base_range)
        if weapon_mode == "throwable":
            maximum_range = max(1, int(float((attacker.tot or {}).get("forza") or 0)))
            if attack_distance > maximum_range:
                raise ApiError(
                    "combat.throw_range_exceeded",
                    f"Gittata massima superata: {maximum_range} m (Forza).",
                    status=409,
                )
            if attack_distance <= 1:
                range_attack_penalty -= 4
        elif attack_distance <= 1:
            notes = " ".join(str(value) for value in weapon_profile.get("bonusNotes", []))
            if "nessun malus" not in notes.casefold():
                range_attack_penalty -= 7
    enabled = CombatModifier.objects.filter(states__map=map_obj, states__enabled=True)
    requested_button_ids: list[int] = []
    raw_button_ids = payload.get("combatButtonIds") or []
    if not isinstance(raw_button_ids, list):
        raise ApiError("combat_buttons.invalid_selection", "La selezione dei bottoni combat non è valida.", "combatButtonIds")
    try:
        requested_button_ids = list(dict.fromkeys(int(value) for value in raw_button_ids))
    except (TypeError, ValueError) as error:
        raise ApiError("combat_buttons.invalid_selection", "La selezione dei bottoni combat non è valida.", "combatButtonIds") from error
    if len(requested_button_ids) > 12:
        raise ApiError("combat_buttons.too_many_selected", "Puoi usare al massimo 12 bottoni combat per attacco.", "combatButtonIds")
    selected_buttons = list(
        BottoneCombat.objects.select_for_update()
        .filter(id__in=requested_button_ids, personaggio=attacker, attivo=True)
        .order_by("ordine", "id")
    )
    if len(selected_buttons) != len(requested_button_ids):
        raise ApiError(
            "combat_buttons.unavailable",
            "Uno dei bottoni selezionati non è più attivo o non appartiene all'attaccante.",
            "combatButtonIds",
            409,
        )
    augmented = dict(payload)
    for field, model_field in (("attackBonus", "attack_bonus"), ("damageBonus", "damage_bonus"), ("penetrationFlat", "penetration_flat"), ("penetrationPercent", "penetration_percent")):
        augmented[field] = int(payload.get(field) or 0) + sum(getattr(modifier, model_field) for modifier in enabled)
    augmented["attackBonus"] += sum(button.bonus_attacco for button in selected_buttons)
    augmented["damageBonus"] += sum(button.bonus_danno for button in selected_buttons)
    augmented["damageTierBonus"] = int(payload.get("damageTierBonus") or 0) + sum(button.bonus_tier for button in selected_buttons)
    augmented["penetrationFlat"] += sum(button.perforazione for button in selected_buttons)
    augmented["penetrationPercent"] += sum(button.perforazione_percentuale for button in selected_buttons)
    augmented["attackBonus"] = int(augmented.get("attackBonus") or 0) + range_attack_penalty
    if not payload.get("damageType") and weapon_profile.get("damageType") in {"perforante", "taglio", "contundente"}:
        augmented["damageType"] = str(weapon_profile["damageType"]).title()
    try:
        result = resolve_attack_values(attacker, defender, augmented)
    except ValueError as error:
        raise ApiError("combat.invalid_attack", str(error))
    applied = bool(payload.get("apply"))
    resource_costs = payload.get("resourceCosts") if isinstance(payload.get("resourceCosts"), dict) else {}
    previous_attack = map_obj.events.filter(event_type="combat.attack_resolved", payload__applied=True).first()
    previous_weapon_id = (previous_attack.payload or {}).get("weaponId") if previous_attack else None
    dual_wield_discount = int(
        equipment_dual_wield(attacker.equip)
        and previous_attack is not None
        and previous_attack.actor_id == attacker.id
        and previous_weapon_id != (weapon.id if weapon else None)
    )
    weapon_action_point_cost = max(0, int(weapon.pa_per_attacco if weapon and weapon.pa_per_attacco is not None else 2))
    normalized_costs = {
        "pf": max(0, int(resource_costs.get("pf") or 0)),
        "mana": max(0, int(resource_costs.get("mana") or 0)),
        "energia": max(0, int(resource_costs.get("energia") or 0)),
        "potere": max(0, int(resource_costs.get("potere") or 0)),
        "pa": max(0, int(resource_costs.get("pa") or 0)) + max(0, weapon_action_point_cost - dual_wield_discount),
        "stanchezza": max(0, int(resource_costs.get("stanchezza") or 0)),
    }
    if applied and any(normalized_costs.values()):
        attacker_tot = attacker.tot if isinstance(attacker.tot, dict) else {}
        energy_spend = calculate_energy_spend(
            int(attacker_tot.get("energia") or 0),
            int(attacker.energia_spesa or 0),
            normalized_costs["energia"],
        ) if normalized_costs["energia"] else None
        checks = (
            ("PF", int(attacker_tot.get("pf") or 0) - attacker.danno, normalized_costs["pf"]),
            ("Mana", int(attacker_tot.get("mana") or 0) - attacker.mana_speso, normalized_costs["mana"]),
            ("Potere", int(attacker_tot.get("potere") or 0) - attacker.potere_speso, normalized_costs["potere"]),
        )
        missing = [name for name, available, cost in checks if available < cost]
        if missing:
            raise ApiError("combat.insufficient_resources", f"Risorse insufficienti: {', '.join(missing)}.", status=409)
        attacker.danno += normalized_costs["pf"]
        attacker.mana_speso += normalized_costs["mana"]
        if energy_spend:
            attacker.energia_spesa = energy_spend.spent_after
        attacker.potere_speso += normalized_costs["potere"]
        attacker.stanchezza_accumulata += normalized_costs["stanchezza"] + (energy_spend.fatigue_added if energy_spend else 0)
        attacker.save(update_fields=["danno", "mana_speso", "energia_spesa", "potere_speso", "stanchezza_accumulata", "updated_at"])
        if normalized_costs["stanchezza"] or (energy_spend and energy_spend.fatigue_added):
            refresh_personaggio(attacker)
            attacker.refresh_from_db()
    if applied and result["hit"] and result["finalDamage"]:
        defender.danno += result["finalDamage"]
        defender.save(update_fields=["danno", "updated_at"])
    loaded_after = loaded_before
    ammunition_name = ""
    if applied and weapon_mode == "ranged" and ammunition_slot is not None and attacker.faretra:
        projectile = getattr(attacker.faretra, f"slot_{ammunition_slot}")
        ammunition_name = projectile.nome if projectile else ""
        setattr(attacker.faretra, f"slot_{ammunition_slot}", None)
        attacker.faretra.save(update_fields=[f"slot_{ammunition_slot}", "updated_at"])
        if magazine_size and weapon:
            loaded_after = max(0, loaded_before - 1)
            _save_loaded_projectiles(attacker.equip, weapon, loaded_after)
    result["applied"] = applied
    result["attackerId"] = attacker.id
    result["defenderId"] = defender.id
    result["powerName"] = str(payload.get("powerName") or "")
    result["resourceCosts"] = normalized_costs
    result["weaponId"] = weapon.id if weapon else None
    result["weaponName"] = weapon.nome if weapon else "Mani nude"
    result["weaponActionPointCost"] = weapon_action_point_cost
    result["dualWieldDiscount"] = dual_wield_discount
    result["attackDistance"] = attack_distance
    result["rangeAttackPenalty"] = range_attack_penalty
    result["ammunitionType"] = ammunition_type
    result["ammunitionName"] = ammunition_name
    result["loadedBefore"] = loaded_before if magazine_size else None
    result["loadedAfter"] = loaded_after if magazine_size else None
    result["magazineSize"] = magazine_size if magazine_size else None
    result["reloadRequired"] = bool(magazine_size and loaded_after <= 0)
    result["combatButtonIds"] = [button.id for button in selected_buttons]
    result["combatButtonNames"] = [button.nome for button in selected_buttons]
    _bump(map_obj)
    verb = "infligge" if result["hit"] else "manca"
    message = f"{attacker.nome} {verb} {defender.nome}"
    if result["hit"]:
        message += f": {result['finalDamage']} danni {result['damageType']}."
    if result["powerName"]:
        message += f" Potere attivo: {result['powerName']}."
    _event(map_obj, "combat.attack_resolved", message, actor=attacker, payload=result)
    return map_obj, result


@transaction.atomic
def apply_direct_damage(user, giocatore, payload):
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    attacker = Personaggio.objects.select_for_update().get(pk=payload["attackerId"])
    defender = Personaggio.objects.select_for_update().get(pk=payload["defenderId"])
    if attacker.id == defender.id:
        raise ApiError("combat.same_combatant", "Attaccante e difensore devono essere due personaggi diversi.")
    active_ids = set(map_obj.participants.filter(active=True).values_list("character_id", flat=True))
    if attacker.id not in active_ids or defender.id not in active_ids:
        raise ApiError("combat.participant_missing", "Attaccante e difensore devono essere attivi sulla mappa.", status=409)
    can_manage = has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)
    if not can_manage and attacker.id != giocatore.active_character_id:
        raise ApiError("combat.attacker_not_controlled", "Puoi applicare danni soltanto con il personaggio che controlli.", status=403)
    try:
        result = resolve_direct_damage_values(attacker, defender, payload)
    except ValueError as error:
        raise ApiError("combat.invalid_damage", str(error)) from error
    if result["rawDamage"] <= 0:
        raise ApiError("combat.damage_required", "Inserisci un danno maggiore di zero.", "rawDamage")
    if result["finalDamage"]:
        defender.danno += result["finalDamage"]
        defender.save(update_fields=["danno", "updated_at"])
    result.update({"attackerId": attacker.id, "defenderId": defender.id, "applied": True})
    _bump(map_obj, giocatore)
    _event(
        map_obj,
        "combat.direct_damage_applied",
        f"{attacker.nome} applica {result['finalDamage']} danni {result['damageType']} a {defender.nome}.",
        actor=attacker,
        payload=result,
    )
    return map_obj, result


@transaction.atomic
def create_plan_action(payload):
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    character = Personaggio.objects.get(pk=payload["characterId"])
    costs = payload.get("costs") or {}
    action = TurnPlanAction.objects.create(
        map=map_obj,
        character=character,
        action_type=payload.get("actionType") or "other",
        name=str(payload.get("name") or "Azione"),
        description=str(payload.get("description") or ""),
        order=map_obj.planned_actions.filter(character=character, committed_at__isnull=True).count(),
        cost_pf=max(0, int(costs.get("pf") or 0)),
        cost_mana=max(0, int(costs.get("mana") or 0)),
        cost_energy=max(0, int(costs.get("energia") or 0)),
        cost_power=max(0, int(costs.get("potere") or 0)),
        cost_ap=max(0, int(costs.get("pa") or 0)),
        cost_fatigue=max(0, int(costs.get("stanchezza") or 0)),
        source_skill_id=payload.get("sourceSkillId") or None,
    )
    TurnPlanStep.objects.bulk_create([
        TurnPlanStep(action=action, order=index, q=int(cell["q"]), r=int(cell["r"]))
        for index, cell in enumerate(payload.get("path") or [])
    ])
    _bump(map_obj)
    _event(map_obj, "plan.created", f"{character.nome} pianifica: {action.name}.", actor=character)
    return map_obj


@transaction.atomic
def commit_plan_action(payload):
    action = TurnPlanAction.objects.select_for_update().select_related("map", "character").get(pk=payload["actionId"])
    if action.committed_at:
        raise ApiError("combat.action_already_committed", "Questa azione è già stata pagata.", status=409)
    character = Personaggio.objects.select_for_update().get(pk=action.character_id)
    totals = character.tot if isinstance(character.tot, dict) else {}
    energy_spend = calculate_energy_spend(
        int(totals.get("energia") or 0),
        int(character.energia_spesa or 0),
        action.cost_energy,
    ) if action.cost_energy else None
    checks = (
        ("PF", int(totals.get("pf") or 0) - character.danno, action.cost_pf),
        ("Mana", int(totals.get("mana") or 0) - character.mana_speso, action.cost_mana),
        ("Potere", int(totals.get("potere") or 0) - character.potere_speso, action.cost_power),
    )
    missing = [name for name, available, cost in checks if available < cost]
    if missing:
        raise ApiError("combat.insufficient_resources", f"Risorse insufficienti: {', '.join(missing)}.", status=409)
    character.danno += action.cost_pf
    character.mana_speso += action.cost_mana
    if energy_spend:
        character.energia_spesa = energy_spend.spent_after
    character.potere_speso += action.cost_power
    character.stanchezza_accumulata += action.cost_fatigue + (energy_spend.fatigue_added if energy_spend else 0)
    character.save(update_fields=["danno", "mana_speso", "energia_spesa", "potere_speso", "stanchezza_accumulata", "updated_at"])
    if action.cost_mana:
        accrue_mana_siphon(character, action.cost_mana)
    if action.cost_fatigue or (energy_spend and energy_spend.fatigue_added):
        refresh_personaggio(character)
        character.refresh_from_db()
    action.committed_at = timezone.now()
    action.save(update_fields=["committed_at", "updated_at"])
    _bump(action.map)
    _event(action.map, "plan.committed", f"{character.nome} paga i costi di {action.name}.", actor=character)
    return action.map


@transaction.atomic
def delete_plan_action(payload):
    action = TurnPlanAction.objects.select_for_update().select_related("map", "character").get(pk=payload["actionId"])
    if action.committed_at:
        raise ApiError("combat.committed_action_locked", "Un'azione già pagata resta nello storico.", status=409)
    map_obj, character, name = action.map, action.character, action.name
    action.delete()
    _bump(map_obj)
    _event(map_obj, "plan.deleted", f"{character.nome} rimuove {name} dal piano.", actor=character)
    return map_obj


@transaction.atomic
def create_map_snapshot(user, giocatore, payload):
    require_master(user, giocatore)
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    snapshot = _create_map_snapshot(map_obj, giocatore, str(payload.get("label") or "Backup manuale"))
    _event(map_obj, "map.snapshot_created", f"Backup creato: {snapshot.label}.")
    return map_obj


@transaction.atomic
def restore_map_snapshot(user, giocatore, payload):
    require_master(user, giocatore)
    snapshot = MapSnapshot.objects.select_for_update().select_related("map").get(pk=payload["snapshotId"])
    map_obj = MapMetadata.objects.select_for_update().get(pk=snapshot.map_id)
    _create_map_snapshot(map_obj, giocatore, "Backup automatico prima del ripristino")
    state = snapshot.state if isinstance(snapshot.state, dict) else {}
    metadata = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
    for field in MAP_SNAPSHOT_FIELDS:
        if field in metadata:
            setattr(map_obj, field, metadata[field])
    map_obj.hexes.all().delete()
    map_obj.participants.all().delete()
    map_obj.modifier_states.all().delete()
    for row in state.get("hexes") or []:
        map_hex = MapHex.objects.create(
            map=map_obj,
            q=int(row.get("q") or 0),
            r=int(row.get("r") or 0),
            overlay_color=str(row.get("overlay_color") or ""),
            overlay_opacity=max(0, min(1, float(row.get("overlay_opacity", .35)))),
            blocked=bool(row.get("blocked")),
            revealed=bool(row.get("revealed")),
            fog_effect=bool(row.get("fog_effect")),
        )
        map_hex.terrain_types.set(HexType.objects.filter(id__in=row.get("terrain_type_ids") or [], active=True))
    valid_character_ids = set(Personaggio.objects.filter(archived_at__isnull=True).values_list("id", flat=True))
    for row in state.get("participants") or []:
        character_id = int(row.get("character_id") or 0)
        if character_id not in valid_character_ids:
            continue
        participant = MapParticipant.objects.create(
            map=map_obj,
            character_id=character_id,
            active=bool(row.get("active", True)),
            anchor_q=int(row.get("anchor_q") or 0),
            anchor_r=int(row.get("anchor_r") or 0),
            token_color=str(row.get("token_color") or "#d6a64b"),
            order=max(0, int(row.get("order") or 0)),
        )
        footprint = row.get("footprint") or [{"q": 0, "r": 0}]
        MapParticipantFootprint.objects.bulk_create([
            MapParticipantFootprint(participant=participant, q=int(cell.get("q") or 0), r=int(cell.get("r") or 0))
            for cell in footprint
        ])
    valid_modifier_ids = set(CombatModifier.objects.filter(active=True).values_list("id", flat=True))
    CombatModifierState.objects.bulk_create([
        CombatModifierState(map=map_obj, modifier_id=int(row["modifier_id"]), enabled=bool(row.get("enabled")))
        for row in state.get("modifier_states") or []
        if int(row.get("modifier_id") or 0) in valid_modifier_ids
    ])
    if map_obj.active_character_id not in valid_character_ids:
        map_obj.active_character_id = None
    map_obj.save()
    _bump(map_obj, giocatore)
    _event(map_obj, "map.snapshot_restored", f"Ripristinato backup: {snapshot.label}.")
    return map_obj


@transaction.atomic
def duplicate_map(user, giocatore, payload):
    require_master(user, giocatore)
    source = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    duplicate = _clone_row(
        source,
        overrides={
            "name": str(payload.get("name") or _unique_name(MapMetadata, source.name, field="name"))[:180],
            "created_by": giocatore,
            "revision": 1,
            "is_default": False,
        },
    )
    for source_hex in source.hexes.prefetch_related("terrain_types"):
        target_hex = _clone_row(source_hex, overrides={"map": duplicate})
        target_hex.terrain_types.set(source_hex.terrain_types.all())
    for source_participant in source.participants.prefetch_related("footprint"):
        target_participant = _clone_row(source_participant, overrides={"map": duplicate})
        MapParticipantFootprint.objects.bulk_create([
            MapParticipantFootprint(participant=target_participant, q=cell.q, r=cell.r)
            for cell in source_participant.footprint.all()
        ])
    CombatModifierState.objects.bulk_create([
        CombatModifierState(map=duplicate, modifier=state.modifier, enabled=state.enabled)
        for state in source.modifier_states.select_related("modifier")
    ])
    _event(duplicate, "map.duplicated", f"Mappa duplicata da {source.name}.")
    return duplicate


@transaction.atomic
def apply_enemy_effect(user, giocatore, payload):
    require_master(user, giocatore)
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    defender = Personaggio.objects.get(pk=payload["defenderId"], archived_at__isnull=True)
    if not map_obj.participants.filter(character=defender, active=True).exists():
        raise ApiError("combat.participant_missing", "Il bersaglio non e attivo sulla mappa.", status=409)
    effect = Effetto.objects.get(pk=payload["effectId"], archived_at__isnull=True)
    apply_effect(defender.id, effect.id)
    _bump(map_obj)
    _event(map_obj, "combat.effect_applied", f"{effect.nome} applicato a {defender.nome}.", actor=defender, payload={"effectId": effect.id})
    return map_obj


@transaction.atomic
def take_control(user, giocatore, payload):
    require_master(user, giocatore)
    map_obj = MapMetadata.objects.select_for_update().get(pk=payload["mapId"])
    participant = map_obj.participants.select_related("character").get(character_id=payload["characterId"], active=True)
    if giocatore.active_campaign_id and not participant.character.campagna_id:
        participant.character.campagna_id = giocatore.active_campaign_id
        participant.character.save(update_fields=["campagna", "updated_at"])
    locked_player = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    character_ids = locked_player.character_ids if isinstance(locked_player.character_ids, list) else []
    if participant.character_id not in character_ids:
        character_ids = [*character_ids, participant.character_id]
    locked_player.character_ids = character_ids
    locked_player.active_character_id = participant.character_id
    locked_player.save(update_fields=["character_ids", "active_character", "updated_at"])
    # ``combat_workspace_payload`` is built with the identity object loaded at
    # the start of the request, not with ``locked_player``. Keep that instance
    # in sync so the successful response immediately exposes the new viewer
    # character instead of requiring a page reload.
    giocatore.character_ids = list(character_ids)
    giocatore.active_character_id = participant.character_id
    map_obj.active_character_id = participant.character_id
    _bump(map_obj)
    map_obj.save(update_fields=["active_character", "updated_at"])
    _event(map_obj, "participant.controlled", f"Controllo assunto su {participant.character.nome}.", actor=participant.character)
    return map_obj

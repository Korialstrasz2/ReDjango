from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.text import slugify

from backend.characters.models import (
    EffettoPersonalizzato,
    OperazioneEffettoPersonalizzato,
    Personaggio,
    SkillPersonaggio,
)
from backend.characters.services.custom_effects import EFFECT_ICONS, validate_effect_values
from backend.characters.services.refresh_personaggio import refresh_personaggio
from backend.core.api import ApiError
from backend.core.management_services import require_game_manager
from backend.core.models import FamigliaSkill, Giocatore, Skill, SpellDefinition
from backend.core.security import effective_role, has_minimum_role

from .skill_pricing import skill_price
from .skill_requirements import structured_requirement_reasons
from .skill_selectors import XP_FIELDS, allowed_xp_pools, character_xp_payload, serialize_skill
from .spell_services import save_spell_definition


MAX_FEATURES_PER_SKILL = 20
ACTIVE_COST_KEYS = ("pf", "mana", "energia", "potere", "pa", "stanchezza")
XP_TYPE_ALIASES = {
    "all": "all",
    "tutti": "all",
    "tutto": "all",
    "general": "general",
    "generali": "general",
    "red": "red",
    "rossi": "red",
    "green": "green",
    "verdi": "green",
    "blue": "blue",
    "blu": "blue",
}


def _text(values: Mapping[str, Any], key: str, limit: int | None = None) -> str:
    value = str(values.get(key) or "").strip()
    return value[:limit] if limit else value


def _integer(
    values: Mapping[str, Any],
    key: str,
    *,
    minimum: int = 0,
    maximum: int = 1_000_000,
) -> int:
    try:
        value = int(values.get(key, 0) or 0)
    except (TypeError, ValueError) as exc:
        raise ApiError("skills.integer_required", "Inserisci un numero intero valido.", key) from exc
    if not minimum <= value <= maximum:
        raise ApiError(
            "skills.integer_out_of_range",
            f"Il valore deve essere compreso tra {minimum} e {maximum}.",
            key,
        )
    return value


def _stable_feature_id(prefix: str, raw_id: Any, name: str, used: set[str]) -> str:
    candidate = slugify(str(raw_id or "").strip()) or f"{prefix}-{slugify(name) or 'regola'}"
    candidate = candidate[:80]
    base = candidate
    suffix = 2
    while candidate in used:
        candidate = f"{base[:74]}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _passive_features(raw_features: Any) -> list[dict[str, Any]]:
    if raw_features in (None, ""):
        return []
    if not isinstance(raw_features, list):
        raise ApiError("skills.passives_invalid", "Gli effetti passivi devono essere una lista.", "passiveEffects")
    if len(raw_features) > MAX_FEATURES_PER_SKILL:
        raise ApiError(
            "skills.passives_limit",
            f"Una abilità può contenere al massimo {MAX_FEATURES_PER_SKILL} effetti passivi.",
            "passiveEffects",
        )
    result: list[dict[str, Any]] = []
    used: set[str] = set()
    for index, raw in enumerate(raw_features):
        if not isinstance(raw, Mapping):
            raise ApiError("skills.passive_invalid", "Un effetto passivo non è valido.", "passiveEffects")
        try:
            validated = validate_effect_values(raw)
        except ApiError as exc:
            exc.field = f"passiveEffects.{index}.{exc.field or 'value'}"
            raise
        result.append(
            {
                "id": _stable_feature_id("passivo", raw.get("id"), validated["nome"], used),
                "name": validated["nome"],
                "description": validated["descrizione"],
                "icon": validated["icona"],
                "operations": [
                    {
                        "target": operation["bersaglio"],
                        "operation": operation["operazione"],
                        "value": operation["valore"],
                        "condition": operation["condizione"],
                    }
                    for operation in validated["operazioni"]
                ],
            }
        )
    return result


def _active_features(raw_features: Any) -> list[dict[str, Any]]:
    if raw_features in (None, ""):
        return []
    if not isinstance(raw_features, list):
        raise ApiError("skills.actions_invalid", "Le azioni attive devono essere una lista.", "activeReminders")
    if len(raw_features) > MAX_FEATURES_PER_SKILL:
        raise ApiError(
            "skills.actions_limit",
            f"Una abilità può contenere al massimo {MAX_FEATURES_PER_SKILL} azioni attive.",
            "activeReminders",
        )
    allowed_icons = {value for value, _label, _category, _keywords in EFFECT_ICONS}
    result: list[dict[str, Any]] = []
    used: set[str] = set()
    for index, raw in enumerate(raw_features):
        if not isinstance(raw, Mapping):
            raise ApiError("skills.action_invalid", "Una azione attiva non è valida.", "activeReminders")
        name = str(raw.get("name") or "").strip()
        description = str(raw.get("description") or "").strip()
        if not name:
            raise ApiError("skills.action_name_required", "Inserisci il nome dell'azione.", f"activeReminders.{index}.name")
        if not description:
            raise ApiError(
                "skills.action_description_required",
                "Descrivi quando e come si usa l'azione.",
                f"activeReminders.{index}.description",
            )
        icon = str(raw.get("icon") or "runa").strip().lower()
        if icon not in allowed_icons:
            raise ApiError("skills.action_icon_invalid", "Scegli un'icona disponibile.", f"activeReminders.{index}.icon")
        raw_costs = raw.get("costs") or {}
        if not isinstance(raw_costs, Mapping):
            raise ApiError("skills.action_costs_invalid", "I costi dell'azione non sono validi.", f"activeReminders.{index}.costs")
        costs = {}
        for key in ACTIVE_COST_KEYS:
            try:
                value = int(raw_costs.get(key, 0) or 0)
            except (TypeError, ValueError) as exc:
                raise ApiError(
                    "skills.action_cost_invalid",
                    "Ogni costo deve essere un numero intero.",
                    f"activeReminders.{index}.costs.{key}",
                ) from exc
            if not 0 <= value <= 999:
                raise ApiError(
                    "skills.action_cost_invalid",
                    "Ogni costo deve essere compreso tra 0 e 999.",
                    f"activeReminders.{index}.costs.{key}",
                )
            if value:
                costs[key] = value
        result.append(
            {
                "id": _stable_feature_id("azione", raw.get("id"), name, used),
                "name": name[:180],
                "description": description,
                "trigger": str(raw.get("trigger") or "").strip()[:280],
                "duration": str(raw.get("duration") or "").strip()[:160],
                "usageNotes": str(raw.get("usageNotes") or "").strip(),
                "costs": costs,
                "icon": icon,
            }
        )
    return result


def validate_skill_values(values: Mapping[str, Any], *, instance: Skill | None = None) -> dict[str, Any]:
    name = _text(values, "name", 180)
    if not name:
        raise ApiError("skills.name_required", "Il nome dell'abilità è obbligatorio.", "name")
    duplicate_names = Skill.objects.filter(nome__iexact=name)
    if instance and instance.pk:
        duplicate_names = duplicate_names.exclude(pk=instance.pk)
    if duplicate_names.exists():
        raise ApiError(
            "skills.name_duplicate",
            "Esiste già un'abilità con questo nome. Scegli un nome diverso.",
            "name",
            409,
        )
    try:
        family = FamigliaSkill.objects.get(pk=int(values.get("familyId")), archived_at__isnull=True)
    except (TypeError, ValueError, FamigliaSkill.DoesNotExist) as exc:
        raise ApiError("skills.family_not_found", "Famiglia non trovata.", "familyId", 404) from exc

    xp_type = XP_TYPE_ALIASES.get(_text(values, "xpType").lower())
    if xp_type is None:
        raise ApiError("skills.xp_type_invalid", "Scegli un tipo di PE valido.", "xpType")
    profile_tags = values.get("profileTags") or {}
    metadata = values.get("metadata") or {}
    if not isinstance(profile_tags, Mapping):
        raise ApiError("skills.profile_tags_invalid", "I tag profilo devono essere un oggetto.", "profileTags")
    if not isinstance(metadata, Mapping):
        raise ApiError("skills.metadata_invalid", "I metadati devono essere un oggetto.", "metadata")

    raw_prerequisites = values.get("prerequisiteIds") or []
    if not isinstance(raw_prerequisites, list):
        raise ApiError("skills.prerequisites_invalid", "I prerequisiti devono essere una lista.", "prerequisiteIds")
    try:
        prerequisite_ids = list(dict.fromkeys(int(value) for value in raw_prerequisites))
    except (TypeError, ValueError) as exc:
        raise ApiError("skills.prerequisites_invalid", "Un prerequisito non è valido.", "prerequisiteIds") from exc
    if instance and instance.id in prerequisite_ids:
        raise ApiError("skills.self_prerequisite", "Una abilità non può richiedere se stessa.", "prerequisiteIds")
    prerequisites = list(Skill.objects.filter(pk__in=prerequisite_ids, archived_at__isnull=True))
    if len(prerequisites) != len(prerequisite_ids):
        raise ApiError("skills.prerequisite_not_found", "Uno dei prerequisiti non esiste.", "prerequisiteIds", 404)

    raw_slug = _text(values, "slug", 180)
    clean_slug = slugify(raw_slug or (instance.slug if instance else "") or name)
    if not clean_slug:
        raise ApiError("skills.slug_invalid", "Lo slug dell'abilità non è valido.", "slug")

    magic = bool(values.get("magic"))
    return {
        "fields": {
            "nome": name,
            "slug": clean_slug,
            "numero": _integer(values, "number", minimum=1, maximum=2_147_483_647),
            "famiglia": family,
            "ordine_famiglia": _integer(values, "familyOrder", minimum=0),
            "costo_pe": _integer(values, "baseXpCost", minimum=0, maximum=9999),
            "tipo_pe": xp_type,
            "costo_testuale": _text(values, "rulesCost", 255),
            "descrizione": _text(values, "description"),
            "requisiti": _text(values, "requirementsText"),
            "profile_tags": dict(profile_tags),
            "profile_notes": _text(values, "profileNotes"),
            "effetti_passivi": _passive_features(values.get("passiveEffects")),
            "azioni_attive": _active_features(values.get("activeReminders")),
            "icona": _text(values, "icon", 80) or "runa",
            "note": _text(values, "notes"),
            "metadata": dict(metadata),
        },
        "prerequisites": prerequisites,
        "spell": values.get("spell") if magic else None,
        "magic": magic,
    }


def _save_skill(instance: Skill, values: Mapping[str, Any]) -> Skill:
    validated = validate_skill_values(values, instance=instance if instance.pk else None)
    for field, value in validated["fields"].items():
        setattr(instance, field, value)
    try:
        instance.save()
        instance.prerequisiti.set(validated["prerequisites"])
        if validated["magic"]:
            save_spell_definition(instance, validated["spell"])
        else:
            SpellDefinition.objects.filter(skill=instance).delete()
    except IntegrityError as exc:
        raise ApiError(
            "skills.identity_duplicate",
            "Nome, numero e slug devono essere univoci.",
            "name",
            409,
        ) from exc
    return instance


@transaction.atomic
def create_skill(user, giocatore: Giocatore, values: Mapping[str, Any]) -> Skill:
    require_game_manager(user, giocatore)
    return _save_skill(Skill(), values)


@transaction.atomic
def update_skill(user, giocatore: Giocatore, skill_id: int, values: Mapping[str, Any]) -> Skill:
    require_game_manager(user, giocatore)
    try:
        skill = Skill.objects.select_for_update().get(pk=skill_id)
    except Skill.DoesNotExist as exc:
        raise ApiError("skills.not_found", "Abilità non trovata.", status=404) from exc
    return _save_skill(skill, values)


@transaction.atomic
def upsert_imported_skill(values: Mapping[str, Any]) -> Skill:
    """Idempotent importer entry point; never purchases a Skill for a character."""

    metadata = values.get("metadata") if isinstance(values.get("metadata"), Mapping) else {}
    source_project = str(metadata.get("sourceProject") or "").strip()
    source_id = metadata.get("sourceId")
    if not source_project or source_id in (None, ""):
        raise ApiError(
            "skills.import_provenance_required",
            "Il record importato deve conservare progetto e ID sorgente.",
            "metadata",
        )
    skill = Skill.objects.filter(
        metadata__sourceProject=source_project,
        metadata__sourceId=source_id,
    ).first()
    if skill is not None:
        skill.archived_at = None
    return _save_skill(skill or Skill(), values)


@transaction.atomic
def archive_skill(user, giocatore: Giocatore, skill_id: int) -> Skill:
    require_game_manager(user, giocatore)
    try:
        skill = Skill.objects.select_for_update().get(pk=skill_id)
    except Skill.DoesNotExist as exc:
        raise ApiError("skills.not_found", "Abilità non trovata.", status=404) from exc
    if skill.archived_at is None:
        skill.archived_at = timezone.now()
        skill.save(update_fields=["archived_at", "updated_at"])
    return skill


@transaction.atomic
def reorder_skills(
    user,
    giocatore: Giocatore,
    family_id: int,
    raw_skill_ids: Any,
) -> dict[int, int]:
    require_game_manager(user, giocatore)
    if not isinstance(raw_skill_ids, list):
        raise ApiError("skills.order_invalid", "L'ordine delle abilità non è valido.", "skillIds")
    try:
        skill_ids = [int(value) for value in raw_skill_ids]
    except (TypeError, ValueError) as exc:
        raise ApiError("skills.order_invalid", "L'ordine delle abilità non è valido.", "skillIds") from exc
    if len(skill_ids) != len(set(skill_ids)):
        raise ApiError("skills.order_duplicate", "Ogni abilità può comparire una sola volta.", "skillIds")
    try:
        family = FamigliaSkill.objects.select_for_update().get(pk=family_id, archived_at__isnull=True)
    except FamigliaSkill.DoesNotExist as exc:
        raise ApiError("skills.family_not_found", "Famiglia non trovata.", "familyId", 404) from exc

    family_skills = list(
        Skill.objects.select_for_update()
        .filter(famiglia=family, archived_at__isnull=True)
        .order_by("ordine_famiglia", "numero", "nome")
    )
    expected_ids = {skill.id for skill in family_skills}
    if set(skill_ids) != expected_ids:
        raise ApiError(
            "skills.order_incomplete",
            "Riordina tutte e soltanto le abilità attive della famiglia.",
            "skillIds",
        )
    order_by_id = {skill_id: index * 10 for index, skill_id in enumerate(skill_ids)}
    updated_at = timezone.now()
    for skill in family_skills:
        skill.ordine_famiglia = order_by_id[skill.id]
        skill.updated_at = updated_at
    Skill.objects.bulk_update(family_skills, ["ordine_famiglia", "updated_at"])
    return order_by_id


@transaction.atomic
def delete_skill(user, giocatore: Giocatore, skill_id: int, confirmation: str) -> str:
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_ADMIN):
        raise ApiError(
            "skills.delete_forbidden",
            "Solo un amministratore può eliminare definitivamente un'abilità.",
            status=403,
        )
    try:
        skill = Skill.objects.select_for_update().get(pk=skill_id)
    except Skill.DoesNotExist as exc:
        raise ApiError("skills.not_found", "Abilità non trovata.", status=404) from exc
    if str(confirmation or "").strip() != skill.nome:
        raise ApiError(
            "skills.delete_confirmation_invalid",
            "La conferma non corrisponde al nome dell'abilità.",
            "confirmation",
        )

    ownerships = list(
        SkillPersonaggio.objects.select_for_update()
        .filter(skill=skill)
        .select_related("personaggio")
    )
    affected_characters: dict[int, Personaggio] = {}
    for ownership in ownerships:
        character = ownership.personaggio
        affected_characters[character.id] = character
        if ownership.archived_at is None:
            spend = ownership.spesa_pe if isinstance(ownership.spesa_pe, dict) else {}
            for key, field in XP_FIELDS.items():
                setattr(character, field, int(getattr(character, field) or 0) + int(spend.get(key, 0) or 0))
            character.save(update_fields=[*XP_FIELDS.values(), "updated_at"])
        _remove_passive_instances(character, skill, ownership)
        ownership.delete()

    skill_name = skill.nome
    skill.delete()
    for character in affected_characters.values():
        refresh_personaggio(character)
    return skill_name


@transaction.atomic
def configure_character_actions(character_id: int, raw_actions: Any) -> Personaggio:
    try:
        character = Personaggio.objects.select_for_update().get(pk=character_id)
    except Personaggio.DoesNotExist as exc:
        raise ApiError("character.not_found", "Personaggio non trovato.", status=404) from exc
    if not isinstance(raw_actions, list):
        raise ApiError(
            "skills.character_actions_invalid",
            "La configurazione delle azioni non è valida.",
            "actions",
        )
    if len(raw_actions) > 200:
        raise ApiError(
            "skills.character_actions_limit",
            "Puoi configurare al massimo 200 azioni per personaggio.",
            "actions",
        )

    ownerships = list(
        SkillPersonaggio.objects.select_for_update()
        .filter(personaggio=character, archived_at__isnull=True, skill__archived_at__isnull=True)
        .select_related("skill")
    )
    ownership_by_skill = {ownership.skill_id: ownership for ownership in ownerships}
    known_actions: set[tuple[int, str]] = set()
    for ownership in ownerships:
        for action in ownership.skill.azioni_attive if isinstance(ownership.skill.azioni_attive, list) else []:
            if isinstance(action, Mapping) and action.get("id"):
                known_actions.add((ownership.skill_id, str(action["id"])))

    parsed: dict[tuple[int, str], dict[str, Any]] = {}
    for index, raw_action in enumerate(raw_actions):
        if not isinstance(raw_action, Mapping):
            raise ApiError(
                "skills.character_action_invalid",
                "Una configurazione azione non è valida.",
                f"actions.{index}",
            )
        try:
            skill_id = int(raw_action.get("skillId"))
            order = int(raw_action.get("order", index))
        except (TypeError, ValueError) as exc:
            raise ApiError(
                "skills.character_action_invalid",
                "Skill e ordine dell'azione devono essere validi.",
                f"actions.{index}",
            ) from exc
        action_id = str(raw_action.get("actionId") or "").strip()
        key = (skill_id, action_id)
        if key not in known_actions:
            raise ApiError(
                "skills.character_action_unknown",
                "Una delle azioni non appartiene alle skill del personaggio.",
                f"actions.{index}.actionId",
                404,
            )
        if key in parsed:
            raise ApiError(
                "skills.character_action_duplicate",
                "Ogni azione può comparire una sola volta.",
                f"actions.{index}.actionId",
            )
        if not 0 <= order < 200:
            raise ApiError(
                "skills.character_action_order_invalid",
                "L'ordine dell'azione deve essere compreso tra 0 e 199.",
                f"actions.{index}.order",
            )
        parsed[key] = {
            "enabled": bool(raw_action.get("enabled", True)),
            "order": order,
            "note": str(raw_action.get("note") or "").strip()[:1000],
        }
    if set(parsed) != known_actions:
        raise ApiError(
            "skills.character_actions_incomplete",
            "Salva una configurazione per ogni azione disponibile.",
            "actions",
        )

    for skill_id, ownership in ownership_by_skill.items():
        configuration = {
            action_id: values
            for (configured_skill_id, action_id), values in parsed.items()
            if configured_skill_id == skill_id
        }
        ownership.configurazione_azioni = configuration
        ownership.save(update_fields=["configurazione_azioni", "updated_at"])
    return character


def _unlock_requirements(
    character: Personaggio,
    skill: Skill,
    *,
    bypass_prerequisites: bool = False,
) -> tuple[list[int], list[str]]:
    owned_ids = set(
        SkillPersonaggio.objects.filter(personaggio=character, archived_at__isnull=True).values_list("skill_id", flat=True)
    )
    missing = [entry for entry in skill.prerequisiti.all() if entry.id not in owned_ids]
    reasons: list[str] = []
    if missing and not bypass_prerequisites:
        reasons.append("Mancano i prerequisiti: " + ", ".join(entry.nome for entry in missing) + ".")
    structured_reasons = structured_requirement_reasons(character, skill)
    if structured_reasons and not bypass_prerequisites:
        reasons.extend(structured_reasons)
    return [entry.id for entry in missing], reasons


def preview_skill_unlock(
    character: Personaggio,
    skill_id: int,
    *,
    bypass_prerequisites: bool = False,
) -> dict[str, Any]:
    try:
        skill = Skill.objects.prefetch_related("prerequisiti").select_related("famiglia").get(
            pk=skill_id,
            archived_at__isnull=True,
        )
    except Skill.DoesNotExist as exc:
        raise ApiError("skills.not_found", "Abilità non trovata.", status=404) from exc
    missing_ids, reasons = _unlock_requirements(
        character,
        skill,
        bypass_prerequisites=bypass_prerequisites,
    )
    xp = character_xp_payload(character)
    allowed = allowed_xp_pools(skill)
    pricing = skill_price(skill, character)
    cost = pricing["calculatedCost"]
    return {
        "skill": serialize_skill(
            skill,
            character=character,
            bypass_prerequisites=bypass_prerequisites,
        ),
        "cost": cost,
        "pricing": pricing,
        "xp": xp,
        "allowedXpPools": allowed,
        "missingPrerequisiteIds": missing_ids,
        "passiveConfirmations": [
            {
                "id": passive.get("id", ""),
                "name": passive.get("name", ""),
                "description": passive.get("description", ""),
                "operations": passive.get("operations", []),
            }
            for passive in skill.effetti_passivi
            if isinstance(passive, Mapping)
        ],
        "canConfirm": not reasons,
        "prerequisitesBypassed": bool(bypass_prerequisites and (missing_ids or structured_requirement_reasons(character, skill))),
        "blockedReasons": reasons,
    }


def _validated_spend(
    character: Personaggio,
    skill: Skill,
    raw_spend: Any,
    previous_spend: Mapping[str, Any] | None = None,
) -> dict[str, int]:
    if not isinstance(raw_spend, Mapping):
        raise ApiError("skills.spend_invalid", "La distribuzione dei PE non è valida.", "spend")
    spend: dict[str, int] = {}
    allowed = set(allowed_xp_pools(skill))
    available = character_xp_payload(character)
    previous_spend = previous_spend if isinstance(previous_spend, Mapping) else {}
    for key in XP_FIELDS:
        try:
            value = int(raw_spend.get(key, 0) or 0)
        except (TypeError, ValueError) as exc:
            raise ApiError("skills.spend_invalid", "La spesa PE deve usare numeri interi.", f"spend.{key}") from exc
        if value < 0:
            raise ApiError("skills.spend_negative", "La spesa PE non può essere negativa.", f"spend.{key}")
        if key not in allowed and value:
            raise ApiError("skills.pool_not_allowed", "Questo gruppo di PE non può pagare l'abilità.", f"spend.{key}")
        try:
            refundable = max(0, int(previous_spend.get(key, 0) or 0))
        except (TypeError, ValueError):
            refundable = 0
        if value > available[key] + refundable:
            raise ApiError("skills.xp_insufficient", "I PE indicati non sono disponibili.", f"spend.{key}")
        spend[key] = value
    return spend


def _assert_passive_acceptance(skill: Skill, raw_ids: Any) -> list[str]:
    if not isinstance(raw_ids, list):
        raise ApiError(
            "skills.passive_acceptance_required",
            "Conferma esplicitamente gli effetti passivi dell'abilità.",
            "acceptedPassiveIds",
        )
    expected = [
        str(passive.get("id"))
        for passive in skill.effetti_passivi
        if isinstance(passive, Mapping) and passive.get("id")
    ]
    accepted = list(dict.fromkeys(str(value) for value in raw_ids))
    if set(accepted) != set(expected):
        raise ApiError(
            "skills.passive_acceptance_incomplete",
            "Accetta tutti gli effetti passivi mostrati prima di completare lo sblocco.",
            "acceptedPassiveIds",
        )
    return accepted


def _available_passive_effect_name(character: Personaggio, skill: Skill, passive_name: str) -> str:
    """Keep generated passive snapshots distinct from user-authored effects."""

    base_name = f"{skill.nome} · {passive_name}"[:180]
    if not EffettoPersonalizzato.objects.filter(personaggio=character, nome=base_name).exists():
        return base_name

    qualified_name = f"{base_name[:150]} · abilità {skill.pk}"[:180]
    if not EffettoPersonalizzato.objects.filter(personaggio=character, nome=qualified_name).exists():
        return qualified_name

    suffix = 2
    while True:
        candidate = f"{qualified_name[:170]} ({suffix})"[:180]
        if not EffettoPersonalizzato.objects.filter(personaggio=character, nome=candidate).exists():
            return candidate
        suffix += 1


def _create_passive_instances(character: Personaggio, skill: Skill) -> list[int]:
    next_order = (
        EffettoPersonalizzato.objects.filter(personaggio=character).aggregate(value=Max("ordine"))["value"] or 0
    ) + 1
    created_ids: list[int] = []
    for offset, passive in enumerate(skill.effetti_passivi if isinstance(skill.effetti_passivi, list) else []):
        if not isinstance(passive, Mapping):
            continue
        validated = validate_effect_values(passive)
        effect_name = _available_passive_effect_name(character, skill, validated["nome"])
        effect = EffettoPersonalizzato.objects.create(
            personaggio=character,
            nome=effect_name,
            descrizione=validated["descrizione"],
            origine=f"Abilità: {skill.nome}"[:180],
            icona=validated["icona"],
            temporaneo=False,
            ordine=next_order + offset,
        )
        OperazioneEffettoPersonalizzato.objects.bulk_create(
            [OperazioneEffettoPersonalizzato(effetto=effect, **operation) for operation in validated["operazioni"]]
        )
        created_ids.append(effect.id)
    return created_ids


def _remove_passive_instances(character: Personaggio, skill: Skill, ownership: SkillPersonaggio) -> None:
    metadata = ownership.metadata if isinstance(ownership.metadata, dict) else {}
    raw_ids = metadata.get("passive_effect_ids", [])
    effect_ids = [value for value in raw_ids if isinstance(value, int)] if isinstance(raw_ids, list) else []
    effects = EffettoPersonalizzato.objects.filter(personaggio=character)
    if effect_ids:
        effects.filter(pk__in=effect_ids).delete()
        return
    # Compatibility for unlock records created before generated effect ids were stored.
    effects.filter(
        origine=f"Abilità: {skill.nome}"[:180],
        nome__startswith=f"{skill.nome} · ",
    ).delete()


def sync_automatic_racial_skills(character: Personaggio) -> bool:
    """Keep zero-cost Elder racial abilities aligned with Razza 1 and Razza 2.

    This intentionally does not call refresh_personaggio: it is invoked by the
    refresh transaction before calculation payloads are collected.
    """

    race = str(character.razza_1 or "").strip()
    subrace = str(character.razza_2 or "").strip()
    racial_skills = []
    for skill in Skill.objects.filter(
        archived_at__isnull=True,
        famiglia__gruppo__slug="razze-sottorazze",
    ).order_by("famiglia__ordine", "ordine_famiglia", "id"):
        metadata = skill.metadata if isinstance(skill.metadata, dict) else {}
        if not metadata.get("automaticRaceUnlock") or metadata.get("race") != race:
            continue
        kind = metadata.get("raceUnlockKind")
        if kind in {"base", "razza"} or (kind == "subrazza" and metadata.get("subrace") == subrace):
            racial_skills.append(skill)

    desired_ids = {skill.id for skill in racial_skills}
    ownerships = list(
        SkillPersonaggio.objects.select_for_update()
        .filter(personaggio=character, archived_at__isnull=True)
        .select_related("skill")
    )
    automatic = {
        ownership.skill_id: ownership
        for ownership in ownerships
        if isinstance(ownership.metadata, dict) and ownership.metadata.get("source") == "race.auto"
    }
    changed = False
    for skill_id, ownership in automatic.items():
        if skill_id in desired_ids:
            continue
        _remove_passive_instances(character, ownership.skill, ownership)
        ownership.delete()
        changed = True

    for skill in racial_skills:
        if skill.id in automatic:
            continue
        accepted = [
            str(passive.get("id"))
            for passive in skill.effetti_passivi
            if isinstance(passive, Mapping) and passive.get("id")
        ]
        ownership = SkillPersonaggio.objects.create(
            personaggio=character,
            skill=skill,
            spesa_pe={key: 0 for key in XP_FIELDS},
            passivi_accettati=accepted,
            note="Sblocco automatico da Razza 1/Razza 2.",
            configurazione_azioni={
                str(action.get("id")): {"enabled": True, "order": index, "note": ""}
                for index, action in enumerate(skill.azioni_attive if isinstance(skill.azioni_attive, list) else [])
                if isinstance(action, Mapping) and action.get("id")
            },
            metadata={
                "source": "race.auto",
                "skill_slug": skill.slug,
                "race": race,
                "subrace": subrace,
            },
        )
        effect_ids = _create_passive_instances(character, skill)
        ownership.metadata = {**ownership.metadata, "passive_effect_ids": effect_ids}
        ownership.save(update_fields=["metadata", "updated_at"])
        changed = True
    return changed


@transaction.atomic
def update_character_xp(character_id: int, raw_xp: Any) -> Personaggio:
    try:
        character = Personaggio.objects.select_for_update().get(pk=character_id)
    except Personaggio.DoesNotExist as exc:
        raise ApiError("character.not_found", "Personaggio non trovato.", status=404) from exc
    if not isinstance(raw_xp, Mapping):
        raise ApiError("skills.xp_invalid", "I Punti Esperienza indicati non sono validi.", "xp")
    fields = {**XP_FIELDS, "ability": "pe_abilita"}
    for key, field in fields.items():
        try:
            value = int(raw_xp.get(key, 0) or 0)
        except (TypeError, ValueError) as exc:
            raise ApiError("skills.xp_invalid", "Inserisci soltanto numeri interi.", f"xp.{key}") from exc
        if not 0 <= value <= 1_000_000:
            raise ApiError(
                "skills.xp_out_of_range",
                "I Punti Esperienza devono essere compresi tra 0 e 1000000.",
                f"xp.{key}",
            )
        setattr(character, field, value)
    character.save(update_fields=[*fields.values(), "updated_at"])
    return character


@transaction.atomic
def unlock_skill(
    character_id: int,
    skill_id: int,
    raw_spend: Any,
    accepted_passive_ids: Any,
    note: str = "",
    *,
    bypass_prerequisites: bool = False,
) -> Personaggio:
    try:
        character = Personaggio.objects.select_for_update().get(pk=character_id)
        skill = Skill.objects.select_for_update().prefetch_related("prerequisiti").get(
            pk=skill_id,
            archived_at__isnull=True,
        )
    except Personaggio.DoesNotExist as exc:
        raise ApiError("character.not_found", "Personaggio non trovato.", status=404) from exc
    except Skill.DoesNotExist as exc:
        raise ApiError("skills.not_found", "Abilità non trovata.", status=404) from exc

    ownership = (
        SkillPersonaggio.objects.select_for_update()
        .filter(personaggio=character, skill=skill, archived_at__isnull=True)
        .first()
    )
    previous_spend = ownership.spesa_pe if ownership and isinstance(ownership.spesa_pe, dict) else {}
    spend = _validated_spend(character, skill, raw_spend, previous_spend)
    unlock_note = str(note or "").strip()[:4000]
    should_be_owned = sum(spend.values()) > 0 or bool(unlock_note)

    # Empty spending and an empty note mean that the unlock never happened.
    if not should_be_owned:
        if ownership is None:
            return character
        for key, field in XP_FIELDS.items():
            setattr(character, field, int(getattr(character, field) or 0) + int(previous_spend.get(key, 0) or 0))
        _remove_passive_instances(character, skill, ownership)
        ownership.delete()
        character.save(update_fields=[*XP_FIELDS.values(), "updated_at"])
        refresh_personaggio(character)
        character.refresh_from_db()
        return character

    _missing_ids, _reasons = _unlock_requirements(
        character,
        skill,
        bypass_prerequisites=bypass_prerequisites,
    )
    if _reasons:
        raise ApiError(
            "skills.prerequisites_missing",
            " ".join(_reasons),
            "skillId",
            409,
        )
    structured_requirements_missing = bool(structured_requirement_reasons(character, skill))
    pricing = skill_price(skill, character, lock_ownerships=True)
    accepted = _assert_passive_acceptance(skill, accepted_passive_ids)

    for key, field in XP_FIELDS.items():
        previous = int(previous_spend.get(key, 0) or 0)
        setattr(character, field, int(getattr(character, field) or 0) + previous - spend[key])
    character.save(update_fields=[*XP_FIELDS.values(), "updated_at"])

    if ownership is None:
        ownership = SkillPersonaggio.objects.create(
            personaggio=character,
            skill=skill,
            spesa_pe=spend,
            passivi_accettati=accepted,
            note=unlock_note,
            configurazione_azioni={
                str(action.get("id")): {"enabled": True, "order": index, "note": ""}
                for index, action in enumerate(
                    skill.azioni_attive if isinstance(skill.azioni_attive, list) else []
                )
                if isinstance(action, Mapping) and action.get("id")
            },
            metadata={
                "source": "skills.unlock",
                "skill_slug": skill.slug,
                "pricing": pricing,
                "prerequisites_bypassed": bool(_missing_ids or structured_requirements_missing),
            },
        )
        effect_ids = _create_passive_instances(character, skill)
        ownership.metadata = {**ownership.metadata, "passive_effect_ids": effect_ids}
        ownership.save(update_fields=["metadata", "updated_at"])
    else:
        ownership.spesa_pe = spend
        ownership.passivi_accettati = accepted
        ownership.note = unlock_note
        ownership.metadata = {
            **(ownership.metadata if isinstance(ownership.metadata, dict) else {}),
            "pricing": pricing,
            "prerequisites_bypassed": bool(_missing_ids or structured_requirements_missing),
        }
        ownership.save(update_fields=["spesa_pe", "passivi_accettati", "note", "metadata", "updated_at"])

    refresh_personaggio(character)
    character.refresh_from_db()
    return character

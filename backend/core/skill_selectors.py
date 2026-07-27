from __future__ import annotations

import json
from typing import Any

from django.db.models import Count, Q

from backend.characters.models import Personaggio, SkillPersonaggio
from backend.characters.services.combat_buttons import combat_button_configuration_payload
from backend.characters.services.custom_effects import effect_configuration_payload
from backend.core.models import FamigliaSkill, GruppoFamiglieSkill, Skill

from .skill_pricing import skill_price
from .skill_requirements import structured_requirement_reasons
from .spell_services import serialize_spell


XP_FIELDS = {
    "general": "pe_generali",
    "red": "pe_rossi",
    "green": "pe_verdi",
    "blue": "pe_blu",
}

XP_LABELS = {
    "general": "Generali",
    "red": "Rossi",
    "green": "Verdi",
    "blue": "Blu",
}

XP_TYPE_LABELS = dict(Skill.XP_TYPE_CHOICES)
SEED_FAMILY_NOTES = {
    "Categoria iniziale per l'organizzazione delle abilità V2.",
    "Seed category for v2 skill organization.",
}


def allowed_xp_pools(skill: Skill) -> list[str]:
    if skill.tipo_pe == "all":
        return list(XP_FIELDS)
    if skill.tipo_pe in {"red", "green", "blue"}:
        return ["general", skill.tipo_pe]
    return ["general"]


def _skill_modifies_target(skill: Skill, target: str) -> bool:
    passives = skill.effetti_passivi if isinstance(skill.effetti_passivi, list) else []
    for passive in passives:
        if not isinstance(passive, dict):
            continue
        operations = passive.get("operations", [])
        if not isinstance(operations, list):
            continue
        if any(isinstance(operation, dict) and str(operation.get("target") or "") == target for operation in operations):
            return True
    return False


def character_xp_payload(character: Personaggio | None) -> dict[str, int]:
    if character is None:
        return {key: 0 for key in XP_FIELDS}
    return {key: int(getattr(character, field, 0) or 0) for key, field in XP_FIELDS.items()}


def serialize_skill_family(family: FamigliaSkill, *, selected: bool = False) -> dict[str, Any]:
    image_url = ""
    if family.immagine_id and family.immagine and family.immagine.file:
        image_url = family.immagine.file.url
    return {
        "id": family.id,
        "name": family.nome,
        "groupId": family.gruppo_id,
        "group": family.gruppo.nome,
        "groupSlug": family.gruppo.slug,
        "order": family.ordine,
        "isClass": family.is_classe,
        "isReligion": family.is_religione,
        "isPerk": family.is_perk,
        "notes": "" if family.note in SEED_FAMILY_NOTES else family.note,
        "additionalNotes": family.note_addizionali,
        "imageUrl": image_url,
        "skillCount": int(getattr(family, "skill_count", 0) or 0),
        "selected": selected,
    }


def _ownership_map(character: Personaggio | None) -> dict[int, SkillPersonaggio]:
    if character is None:
        return {}
    return {
        ownership.skill_id: ownership
        for ownership in SkillPersonaggio.objects.filter(
            personaggio=character,
            archived_at__isnull=True,
        ).select_related("skill", "skill__famiglia", "skill__famiglia__gruppo")
    }


def _unlock_state(
    skill: Skill,
    character: Personaggio | None,
    ownerships: dict[int, SkillPersonaggio],
    *,
    bypass_prerequisites: bool = False,
) -> dict[str, Any]:
    ownership = ownerships.get(skill.id)
    prerequisite_ids = [entry.id for entry in skill.prerequisiti.all()]
    missing = [entry for entry in skill.prerequisiti.all() if entry.id not in ownerships]
    structured_reasons = structured_requirement_reasons(character, skill) if character is not None else []
    xp = character_xp_payload(character)
    allowed = allowed_xp_pools(skill)
    pricing = skill_price(skill, character)
    reasons: list[str] = []
    if character is None:
        reasons.append("Seleziona un personaggio per sbloccare l'abilità.")
    elif skill.archived_at is not None:
        reasons.append("Questa abilità è archiviata e non può essere sbloccata.")
    elif ownership:
        reasons.append("Questa abilità è già sbloccata.")
    else:
        if missing and not bypass_prerequisites:
            reasons.append("Mancano: " + ", ".join(entry.nome for entry in missing) + ".")
        if structured_reasons and not bypass_prerequisites:
            reasons.extend(structured_reasons)
        if sum(xp[key] for key in allowed) < pricing["calculatedCost"]:
            reasons.append("I PE disponibili nei gruppi consentiti non sono sufficienti.")
    return {
        "owned": ownership is not None,
        "canUnlock": character is not None and ownership is None and not reasons,
        "blockedReasons": reasons,
        "prerequisiteIds": prerequisite_ids,
        "missingPrerequisiteIds": [entry.id for entry in missing],
        "prerequisitesBypassed": bool(bypass_prerequisites and (missing or structured_reasons)),
        "allowedXpPools": allowed,
        "acceptedPassiveIds": list(ownership.passivi_accettati or []) if ownership else [],
        "spentXp": dict(ownership.spesa_pe or {}) if ownership else {},
        "note": ownership.note if ownership else "",
        "unlockedAt": ownership.created_at.isoformat() if ownership else None,
    }


def serialize_skill(
    skill: Skill,
    *,
    character: Personaggio | None = None,
    ownerships: dict[int, SkillPersonaggio] | None = None,
    bypass_prerequisites: bool = False,
) -> dict[str, Any]:
    ownerships = ownerships if ownerships is not None else _ownership_map(character)
    spell = serialize_spell(skill)
    pricing = skill_price(skill, character)
    return {
        "id": skill.id,
        "slug": skill.slug,
        "number": skill.numero,
        "name": skill.nome,
        "description": skill.descrizione,
        "familyId": skill.famiglia_id,
        "familyName": skill.famiglia.nome,
        "familyGroup": skill.famiglia.gruppo.nome,
        "familyOrder": skill.ordine_famiglia,
        "magic": spell is not None,
        "baseXpCost": skill.costo_pe,
        "xpCost": pricing["calculatedCost"],
        "pricing": pricing,
        "xpType": skill.tipo_pe,
        "xpTypeLabel": XP_TYPE_LABELS.get(skill.tipo_pe, skill.tipo_pe),
        "rulesCost": skill.costo_testuale,
        "requirementsText": skill.requisiti,
        "spell": spell,
        "profileTags": skill.profile_tags if isinstance(skill.profile_tags, dict) else {},
        "profileNotes": skill.profile_notes,
        "passiveEffects": skill.effetti_passivi if isinstance(skill.effetti_passivi, list) else [],
        "activeReminders": skill.azioni_attive if isinstance(skill.azioni_attive, list) else [],
        "icon": skill.icona,
        "notes": skill.note,
        "metadata": skill.metadata if isinstance(skill.metadata, dict) else {},
        "archived": skill.archived_at is not None,
        "unlock": _unlock_state(
            skill,
            character,
            ownerships,
            bypass_prerequisites=bypass_prerequisites,
        ),
    }


def owned_action_reminders(character: Personaggio | None) -> list[dict[str, Any]]:
    if character is None:
        return []
    result: list[dict[str, Any]] = []
    ownerships = SkillPersonaggio.objects.filter(
        personaggio=character,
        archived_at__isnull=True,
        skill__archived_at__isnull=True,
    ).select_related("skill", "skill__famiglia", "skill__famiglia__gruppo")
    for ownership in ownerships:
        configuration = ownership.configurazione_azioni if isinstance(ownership.configurazione_azioni, dict) else {}
        for default_order, reminder in enumerate(
            ownership.skill.azioni_attive if isinstance(ownership.skill.azioni_attive, list) else []
        ):
            if not isinstance(reminder, dict):
                continue
            action_id = str(reminder.get("id") or "")
            action_configuration = configuration.get(action_id, {})
            if not isinstance(action_configuration, dict):
                action_configuration = {}
            try:
                action_order = int(action_configuration.get("order", default_order))
            except (TypeError, ValueError):
                action_order = default_order
            result.append(
                {
                    **reminder,
                    "skillId": ownership.skill_id,
                    "skillName": ownership.skill.nome,
                    "familyName": ownership.skill.famiglia.nome,
                    "familyGroup": ownership.skill.famiglia.gruppo.nome,
                    "enabled": bool(action_configuration.get("enabled", True)),
                    "order": action_order,
                    "characterNote": str(action_configuration.get("note") or ""),
                }
            )
    return sorted(result, key=lambda action: (action["order"], action["skillName"], action["name"]))


def skill_character_analysis(
    character: Personaggio | None,
    ownerships: dict[int, SkillPersonaggio] | None = None,
) -> dict[str, Any]:
    ownerships = ownerships if ownerships is not None else _ownership_map(character)
    by_group: dict[str, dict[str, int]] = {}
    by_family: dict[tuple[str, str], dict[str, int | str]] = {}
    passive_count = 0
    action_count = 0
    xp_spent = 0
    for ownership in ownerships.values():
        skill = ownership.skill
        passives = skill.effetti_passivi if isinstance(skill.effetti_passivi, list) else []
        actions = skill.azioni_attive if isinstance(skill.azioni_attive, list) else []
        passive_count += len(passives)
        action_count += len(actions)
        if isinstance(ownership.spesa_pe, dict):
            xp_spent += sum(int(value or 0) for value in ownership.spesa_pe.values())
        group_name = skill.famiglia.gruppo.nome
        group_row = by_group.setdefault(group_name, {"skills": 0, "passives": 0, "actions": 0})
        group_row["skills"] += 1
        group_row["passives"] += len(passives)
        group_row["actions"] += len(actions)
        family_key = (group_name, skill.famiglia.nome)
        family_row = by_family.setdefault(
            family_key,
            {"group": group_name, "family": skill.famiglia.nome, "skills": 0},
        )
        family_row["skills"] = int(family_row["skills"]) + 1
    current_level = max(1, int(character.livello or 1)) if character else 1
    spent_before_level = sum(20 + level for level in range(1, current_level))
    xp_for_next_level = 20 + current_level
    xp_into_level = max(0, xp_spent - spent_before_level)
    xp_until_next_level = max(0, spent_before_level + xp_for_next_level - xp_spent)
    expected_level = 1
    expected_remaining = xp_spent
    while expected_remaining >= 20 + expected_level:
        expected_remaining -= 20 + expected_level
        expected_level += 1

    group_order = dict(GruppoFamiglieSkill.objects.values_list("nome", "ordine"))
    return {
        "ownedSkills": len(ownerships),
        "passiveEffects": passive_count,
        "activeActions": action_count,
        "xpSpent": xp_spent,
        "progression": {
            "currentLevel": current_level,
            "expectedLevel": expected_level,
            "xpIntoLevel": min(xp_for_next_level, xp_into_level),
            "xpForNextLevel": xp_for_next_level,
            "xpUntilNextLevel": xp_until_next_level,
            "progressPercent": round(min(100, xp_into_level / xp_for_next_level * 100), 1),
        },
        "byGroup": [
            {"group": group_name, **values}
            for group_name, values in sorted(
                by_group.items(),
                key=lambda item: (group_order.get(item[0], 999), item[0]),
            )
        ],
        "byFamily": [
            values
            for _key, values in sorted(
                by_family.items(),
                key=lambda item: (group_order.get(item[0][0], 999), item[0][1]),
            )
        ],
    }


def skill_catalog_payload(
    character: Personaggio | None,
    *,
    group: str = "",
    family_id: int | None = None,
    query: str = "",
    search_mode: bool = False,
    name_query: str = "",
    card_query: str = "",
    filter_group: str = "",
    filter_family_id: int | None = None,
    effect_target: str = "",
    unlock_status: str = "",
    include_archived: bool = False,
    owned_only: bool = False,
    can_manage: bool = False,
    can_delete: bool = False,
    bypass_prerequisites: bool = False,
) -> dict[str, Any]:
    family_filter = Q(skills__archived_at__isnull=True)
    if include_archived and can_manage:
        family_filter = Q()
    families = list(
        FamigliaSkill.objects.filter(archived_at__isnull=True, gruppo__archived_at__isnull=True)
        .select_related("immagine", "gruppo")
        .annotate(skill_count=Count("skills", filter=family_filter))
        .order_by("gruppo__ordine", "ordine", "nome")
    )
    families_by_id = {family.id: family for family in families}
    available_groups = list(dict.fromkeys(family.gruppo.nome for family in families))
    selected_family = families_by_id.get(family_id)
    selected_group = selected_family.gruppo.nome if selected_family else group.strip()
    if selected_group not in available_groups:
        first_populated_group = next(
            (family.gruppo.nome for family in families if family.skill_count),
            available_groups[0] if available_groups else "",
        )
        selected_group = first_populated_group
    group_families = [family for family in families if family.gruppo.nome == selected_group]
    if selected_family is None or selected_family.gruppo.nome != selected_group:
        selected_family = next(
            (family for family in group_families if family.skill_count),
            group_families[0] if group_families else None,
        )
    family_id = selected_family.id if selected_family else None
    ownerships = _ownership_map(character)

    skills = Skill.objects.select_related("famiglia", "famiglia__gruppo", "spell_definition").prefetch_related("prerequisiti").order_by(
        "famiglia__ordine", "ordine_famiglia", "numero", "nome"
    )
    if not (include_archived and can_manage):
        skills = skills.filter(archived_at__isnull=True)
    normalized_query = query.strip()
    normalized_name_query = name_query.strip()
    normalized_card_query = card_query.strip().casefold()
    normalized_filter_group = filter_group.strip()
    normalized_effect_target = effect_target.strip()
    normalized_unlock_status = unlock_status.strip()
    if search_mode:
        has_search_criteria = any((
            normalized_name_query,
            normalized_card_query,
            normalized_filter_group,
            filter_family_id,
            normalized_effect_target,
            normalized_unlock_status,
        ))
        if not has_search_criteria:
            skills = skills.none()
        else:
            if normalized_name_query:
                skills = skills.filter(nome__icontains=normalized_name_query)
            if normalized_filter_group:
                skills = skills.filter(famiglia__gruppo__nome=normalized_filter_group)
            if filter_family_id:
                skills = skills.filter(famiglia_id=filter_family_id)
            if normalized_unlock_status == "owned":
                skills = skills.filter(pk__in=ownerships.keys())
            elif normalized_unlock_status in {"available", "locked"}:
                skills = skills.exclude(pk__in=ownerships.keys())
    elif owned_only:
        skills = skills.filter(pk__in=ownerships.keys())
        if normalized_query:
            skills = skills.filter(
                Q(nome__icontains=normalized_query)
                | Q(descrizione__icontains=normalized_query)
                | Q(requisiti__icontains=normalized_query)
                | Q(note__icontains=normalized_query)
                | Q(famiglia__nome__icontains=normalized_query)
                | Q(famiglia__gruppo__nome__icontains=normalized_query)
            )
    elif normalized_query:
        skills = skills.filter(
            Q(nome__icontains=normalized_query)
            | Q(descrizione__icontains=normalized_query)
            | Q(requisiti__icontains=normalized_query)
            | Q(note__icontains=normalized_query)
            | Q(famiglia__nome__icontains=normalized_query)
            | Q(famiglia__gruppo__nome__icontains=normalized_query)
        )
    elif family_id is not None and not search_mode:
        skills = skills.filter(famiglia_id=family_id)

    skill_rows = list(skills[:2000])
    if normalized_card_query:
        skill_rows = [
            skill
            for skill in skill_rows
            if normalized_card_query in " ".join((
                skill.nome,
                skill.descrizione,
                skill.requisiti,
                skill.costo_testuale,
                str(skill.costo_pe),
                skill.tipo_pe,
                XP_TYPE_LABELS.get(skill.tipo_pe, skill.tipo_pe),
                skill.profile_notes,
                skill.note,
                skill.famiglia.nome,
                skill.famiglia.gruppo.nome,
                json.dumps(skill.profile_tags, ensure_ascii=False, default=str),
                json.dumps(skill.effetti_passivi, ensure_ascii=False, default=str),
                json.dumps(skill.azioni_attive, ensure_ascii=False, default=str),
                json.dumps(skill.metadata, ensure_ascii=False, default=str),
            )).casefold()
        ]
    if normalized_effect_target:
        skill_rows = [skill for skill in skill_rows if _skill_modifies_target(skill, normalized_effect_target)]

    serialized_skills = [
        serialize_skill(
            skill,
            character=character,
            ownerships=ownerships,
            bypass_prerequisites=bypass_prerequisites,
        )
        for skill in skill_rows
    ]
    if normalized_unlock_status == "available":
        serialized_skills = [skill for skill in serialized_skills if skill["unlock"]["canUnlock"]]
    elif normalized_unlock_status == "locked":
        serialized_skills = [
            skill for skill in serialized_skills
            if not skill["unlock"]["owned"] and not skill["unlock"]["canUnlock"]
        ]

    skill_options = list(
        Skill.objects.filter(archived_at__isnull=True)
        .select_related("famiglia", "famiglia__gruppo")
        .order_by("famiglia__gruppo__ordine", "famiglia__ordine", "ordine_famiglia", "nome")
        .values("id", "numero", "nome", "famiglia__nome", "famiglia__gruppo__nome")
    )
    group_records = {
        entry.nome: entry
        for entry in GruppoFamiglieSkill.objects.filter(archived_at__isnull=True)
    }
    return {
        "groups": [
            {
                "key": group_name,
                "name": group_name,
                "order": group_records[group_name].ordine if group_name in group_records else 999,
                "familyCount": sum(1 for family in families if family.gruppo.nome == group_name),
                "skillCount": sum(family.skill_count for family in families if family.gruppo.nome == group_name),
                "selected": group_name == selected_group,
            }
            for group_name in sorted(available_groups, key=lambda name: (group_records[name].ordine if name in group_records else 999, name))
        ],
        "families": [serialize_skill_family(family, selected=family.id == family_id) for family in families],
        "skills": serialized_skills,
        "skillOptions": [
            {
                "id": option["id"],
                "number": option["numero"],
                "name": option["nome"],
                "familyName": option["famiglia__nome"],
                "familyGroup": option["famiglia__gruppo__nome"],
            }
            for option in skill_options
        ],
        "selectedFamilyId": family_id,
        "selectedGroup": selected_group,
        "query": normalized_query,
        "character": (
            {
                "id": character.id,
                "name": character.nome,
                "level": character.livello,
                "xp": character_xp_payload(character),
                "competenceXp": int(character.pe_abilita or 0),
            }
            if character
            else None
        ),
        "activeReminders": owned_action_reminders(character),
        "combatButtons": combat_button_configuration_payload(character),
        "characterAnalysis": skill_character_analysis(character, ownerships),
        "effectConfiguration": effect_configuration_payload(),
        "permissions": {
            "canManageSkills": can_manage,
            "canDeleteSkills": can_delete,
            "canUnlockSkills": character is not None,
            "canBypassPrerequisites": bypass_prerequisites,
        },
    }


def character_skill_summaries(character: Personaggio) -> list[dict[str, Any]]:
    ownerships = _ownership_map(character)
    return [
        serialize_skill(ownership.skill, character=character, ownerships=ownerships)
        for ownership in ownerships.values()
        if ownership.skill.archived_at is None
    ]

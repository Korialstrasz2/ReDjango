from __future__ import annotations

from typing import Any

from django.db.models import Count, Q

from backend.characters.services.custom_effects import effect_configuration_payload
from backend.core.models import (
    FamigliaSkill,
    GruppoFamiglieSkill,
    Skill,
)

from .skill_selectors import XP_TYPE_LABELS, serialize_skill, serialize_skill_family


def serialize_managed_group(group: GruppoFamiglieSkill) -> dict[str, Any]:
    return {
        "id": group.id,
        "name": group.nome,
        "slug": group.slug,
        "order": group.ordine,
        "notes": group.note,
        "archived": group.archived_at is not None,
        "familyCount": int(getattr(group, "family_count", 0) or 0),
        "skillCount": int(getattr(group, "skill_count", 0) or 0),
    }


def serialize_managed_family(family: FamigliaSkill) -> dict[str, Any]:
    payload = serialize_skill_family(family)
    payload.update({
        "imageId": family.immagine_id,
        "archived": family.archived_at is not None,
        "activeSkillCount": int(getattr(family, "active_skill_count", 0) or 0),
        "archivedSkillCount": int(getattr(family, "archived_skill_count", 0) or 0),
        "spellCount": int(getattr(family, "spell_count", 0) or 0),
    })
    return payload


def serialize_managed_skill(skill: Skill) -> dict[str, Any]:
    spell = getattr(skill, "spell_definition", None)
    metadata = skill.metadata if isinstance(skill.metadata, dict) else {}
    return {
        "id": skill.id,
        "number": skill.numero,
        "name": skill.nome,
        "slug": skill.slug,
        "familyId": skill.famiglia_id,
        "familyName": skill.famiglia.nome,
        "groupId": skill.famiglia.gruppo_id,
        "groupName": skill.famiglia.gruppo.nome,
        "baseXpCost": skill.costo_pe,
        "xpType": skill.tipo_pe,
        "xpTypeLabel": XP_TYPE_LABELS.get(skill.tipo_pe, skill.tipo_pe),
        "magic": spell is not None,
        "spellTier": spell.tier if spell else None,
        "passiveCount": len(skill.effetti_passivi) if isinstance(skill.effetti_passivi, list) else 0,
        "actionCount": len(skill.azioni_attive) if isinstance(skill.azioni_attive, list) else 0,
        "prerequisiteCount": int(getattr(skill, "prerequisite_count", 0) or 0),
        # Characters that already bought this skill. Changing a cost or a
        # prerequisite rewrites what they paid for, so the count has to be
        # visible before the editor opens.
        "ownerCount": int(getattr(skill, "owner_count", 0) or 0),
        "archived": skill.archived_at is not None,
        "sourceProject": str(metadata.get("sourceProject") or ""),
        "sourceId": metadata.get("sourceId"),
        "updatedAt": skill.updated_at.isoformat() if skill.updated_at else None,
    }


def _groups_and_families() -> tuple[list[GruppoFamiglieSkill], list[FamigliaSkill]]:
    groups = list(
        GruppoFamiglieSkill.objects.annotate(
            family_count=Count("famiglie", filter=Q(famiglie__archived_at__isnull=True), distinct=True),
            skill_count=Count(
                "famiglie__skills",
                filter=Q(
                    famiglie__archived_at__isnull=True,
                    famiglie__skills__archived_at__isnull=True,
                ),
                distinct=True,
            ),
        ).order_by("ordine", "nome")
    )
    families = list(
        FamigliaSkill.objects.select_related("gruppo", "immagine")
        .annotate(
            active_skill_count=Count("skills", filter=Q(skills__archived_at__isnull=True), distinct=True),
            archived_skill_count=Count("skills", filter=Q(skills__archived_at__isnull=False), distinct=True),
            spell_count=Count(
                "skills__spell_definition",
                filter=Q(skills__archived_at__isnull=True),
                distinct=True,
            ),
        )
        .order_by("gruppo__ordine", "ordine", "nome")
    )
    return groups, families


SKILL_PAGE_SIZE = 100


def _skill_queryset(query: str, group_id: int | None, family_id: int | None, state: str, kind: str):
    skills = (
        Skill.objects.select_related("famiglia", "famiglia__gruppo", "spell_definition")
        .annotate(
            prerequisite_count=Count("prerequisiti", distinct=True),
            owner_count=Count("personaggi_sbloccati", distinct=True),
        )
        .order_by("famiglia__gruppo__ordine", "famiglia__ordine", "ordine_famiglia", "numero", "nome")
    )
    if query:
        skills = skills.filter(
            Q(nome__icontains=query)
            | Q(slug__icontains=query)
            | Q(famiglia__nome__icontains=query)
            | Q(famiglia__gruppo__nome__icontains=query)
        )
    if group_id:
        skills = skills.filter(famiglia__gruppo_id=group_id)
    if family_id:
        skills = skills.filter(famiglia_id=family_id)
    if state == "active":
        skills = skills.filter(archived_at__isnull=True)
    elif state == "archived":
        skills = skills.filter(archived_at__isnull=False)
    if kind == "spell":
        skills = skills.filter(spell_definition__isnull=False)
    elif kind == "skill":
        skills = skills.filter(spell_definition__isnull=True)
    return skills


def skill_management_overview(
    query: str = "",
    *,
    group_id: int | None = None,
    family_id: int | None = None,
    state: str = "",
    kind: str = "",
    offset: int = 0,
    limit: int = SKILL_PAGE_SIZE,
) -> dict[str, Any]:
    groups, families = _groups_and_families()
    # Metrics are counted in the database: the page used to load all 1500+ rows
    # just to add them up.
    totals = Skill.objects.aggregate(
        total=Count("id", distinct=True),
        archived=Count("id", filter=Q(archived_at__isnull=False), distinct=True),
        spells=Count("id", filter=Q(archived_at__isnull=True, spell_definition__isnull=False), distinct=True),
    )
    page = _skill_queryset(query, group_id, family_id, state, kind)
    total = page.count()
    offset = max(0, offset)
    rows = list(page[offset:offset + limit])
    return {
        "metrics": {
            "activeSkills": totals["total"] - totals["archived"],
            "archivedSkills": totals["archived"],
            "spells": totals["spells"],
            "families": sum(1 for family in families if family.archived_at is None),
            "groups": sum(1 for group in groups if group.archived_at is None),
        },
        "groups": [serialize_managed_group(group) for group in groups],
        "families": [serialize_managed_family(family) for family in families],
        "skills": [serialize_managed_skill(skill) for skill in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
        "hasMore": offset + len(rows) < total,
        "skillOptions": [
            {
                "id": skill.id,
                "number": skill.numero,
                "name": skill.nome,
                "familyName": skill.famiglia.nome,
                "familyGroup": skill.famiglia.gruppo.nome,
            }
            for skill in Skill.objects.filter(archived_at__isnull=True)
            .select_related("famiglia", "famiglia__gruppo")
            .order_by("numero", "nome")
        ],
        "effectConfiguration": effect_configuration_payload(),
    }


def managed_skill_detail(skill_id: int) -> dict[str, Any]:
    skill = (
        Skill.objects.select_related("famiglia", "famiglia__gruppo", "spell_definition")
        .prefetch_related("prerequisiti")
        .get(pk=skill_id)
    )
    owners = list(
        skill.personaggi_sbloccati.select_related("personaggio")
        .order_by("personaggio__nome")
        .values_list("personaggio__nome", flat=True)
    )
    return {"skill": serialize_skill(skill), "owners": owners}

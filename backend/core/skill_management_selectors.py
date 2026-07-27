from __future__ import annotations

from typing import Any

from django.db.models import Count, Q

from backend.characters.services.custom_effects import effect_configuration_payload
from backend.core.models import (
    FamigliaSkill,
    GruppoFamiglieSkill,
    Skill,
    SkillMigrationReview,
)

from .skill_selectors import XP_TYPE_LABELS, serialize_skill, serialize_skill_family


BLOCKER_LABELS = {
    "active_cost_conflict": "Il costo dell'azione non coincide tra le fonti Elder.",
    "no_structured_feature": "Non è stato riconosciuto un effetto, un'azione o un incantesimo strutturato.",
    "passive_has_no_valid_operations": "Il passivo non contiene modifiche applicabili in sicurezza.",
    "passive_value_not_evidenced_in_prose": "Il valore proposto non è confermato dal testo della skill.",
    "prerequisite_not_in_auto_import_queue": "Un prerequisito è ancora nella coda di revisione.",
    "requirement_not_exact_skill_name": "Il requisito non indica esattamente il nome di una skill.",
    "spell_base_mana_conflicts_with_active_cost": "Il Mana base non coincide con il costo dell'azione Elder.",
    "spell_base_mana_conflicts_with_rules_cost": "Il Mana base non coincide con il costo scritto nelle regole.",
    "spell_formula_conflicts_with_active_effect": "La formula magica non coincide con l'effetto attivo proposto.",
    "source_changed_since_last_import": "La sorgente Elder è cambiata dopo l'ultima importazione.",
    "target_family_missing": "La famiglia di destinazione non esiste.",
    "target_name_collision": "Il nome è già usato da un'altra skill.",
    "target_number_collision": "Il numero è già usato da un'altra skill.",
    "multiple_proposals_for_skill": "Esistono più proposte Elder per la stessa skill.",
    "prerequisite_cycle": "I prerequisiti formano un ciclo.",
}

WARNING_LABELS = {
    "active_icon_fell_back_to_runa": "L'icona Elder non era utilizzabile: è stata proposta la runa.",
}


def issue_label(code: str) -> str:
    if code in BLOCKER_LABELS:
        return BLOCKER_LABELS[code]
    if code in WARNING_LABELS:
        return WARNING_LABELS[code]
    if code.startswith("passive_target_unsupported:"):
        return f"Bersaglio passivo non ancora supportato: {code.split(':', 1)[1]}."
    if code.startswith("target_validation:"):
        return f"La proposta non supera la validazione ReDjango ({code.split(':', 1)[1]})."
    return code.replace("_", " ").capitalize()


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
        "archived": skill.archived_at is not None,
        "sourceProject": str(metadata.get("sourceProject") or ""),
        "sourceId": metadata.get("sourceId"),
        "updatedAt": skill.updated_at.isoformat() if skill.updated_at else None,
    }


def serialize_review_summary(review: SkillMigrationReview) -> dict[str, Any]:
    return {
        "id": review.id,
        "sourceProject": review.source_project,
        "sourceId": review.source_id,
        "name": review.nome,
        "severity": review.severity,
        "decision": review.decision,
        "status": review.status,
        "blockers": list(review.blockers) if isinstance(review.blockers, list) else [],
        "blockerLabels": [issue_label(code) for code in review.blockers if isinstance(code, str)],
        "warnings": list(review.warnings) if isinstance(review.warnings, list) else [],
        "warningLabels": [issue_label(code) for code in review.warnings if isinstance(code, str)],
        "edited": review.edited,
        "liveSkillId": review.resolved_skill_id,
        "updatedAt": review.updated_at.isoformat() if review.updated_at else None,
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


def skill_management_overview() -> dict[str, Any]:
    groups, families = _groups_and_families()
    skills = list(
        Skill.objects.select_related("famiglia", "famiglia__gruppo", "spell_definition")
        .annotate(prerequisite_count=Count("prerequisiti", distinct=True))
        .order_by("famiglia__gruppo__ordine", "famiglia__ordine", "ordine_famiglia", "numero", "nome")
    )
    reviews = list(
        SkillMigrationReview.objects.filter(archived_at__isnull=True)
        .select_related("resolved_skill")
        .order_by("status", "severity", "nome", "source_id")
    )
    active_skills = [skill for skill in skills if skill.archived_at is None]
    return {
        "metrics": {
            "activeSkills": len(active_skills),
            "archivedSkills": len(skills) - len(active_skills),
            "spells": sum(1 for skill in active_skills if getattr(skill, "spell_definition", None)),
            "families": sum(1 for family in families if family.archived_at is None),
            "groups": sum(1 for group in groups if group.archived_at is None),
            "openReviews": sum(1 for review in reviews if review.status == SkillMigrationReview.STATUS_OPEN),
            "blockedReviews": sum(
                1 for review in reviews
                if review.status == SkillMigrationReview.STATUS_OPEN
                and review.severity == SkillMigrationReview.SEVERITY_BLOCKED
            ),
        },
        "groups": [serialize_managed_group(group) for group in groups],
        "families": [serialize_managed_family(family) for family in families],
        "skills": [serialize_managed_skill(skill) for skill in skills],
        "skillOptions": [
            {
                "id": skill.id,
                "number": skill.numero,
                "name": skill.nome,
                "familyName": skill.famiglia.nome,
                "familyGroup": skill.famiglia.gruppo.nome,
            }
            for skill in active_skills
        ],
        "reviews": [serialize_review_summary(review) for review in reviews],
        "effectConfiguration": effect_configuration_payload(),
    }


def managed_skill_detail(skill_id: int) -> dict[str, Any]:
    skill = (
        Skill.objects.select_related("famiglia", "famiglia__gruppo", "spell_definition")
        .prefetch_related("prerequisiti")
        .get(pk=skill_id)
    )
    return {"skill": serialize_skill(skill)}


def migration_review_detail(review_id: int) -> dict[str, Any]:
    review = SkillMigrationReview.objects.select_related("resolved_skill").get(pk=review_id)
    return {
        "review": {
            **serialize_review_summary(review),
            "suggestedValues": review.suggested_values if isinstance(review.suggested_values, dict) else {},
            "workingValues": review.working_values if isinstance(review.working_values, dict) else {},
            "source": review.source_snapshot if isinstance(review.source_snapshot, dict) else {},
            "resolutionNotes": review.resolution_notes,
        }
    }

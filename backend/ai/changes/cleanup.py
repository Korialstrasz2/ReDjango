from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from backend.ai.models import AIChangeSet


@transaction.atomic
def cleanup_abandoned_change_sets(
    *,
    review_days: int = 14,
    empty_days: int = 2,
    dry_run: bool = False,
    now=None,
) -> dict[str, int]:
    """Expire abandoned proposals and remove only old empty drafts.

    Applied and discarded audit rows are deliberately retained. This function
    never touches Item, Skill, Spell, Theme, conversation, or provider records.
    """

    review_days = max(1, int(review_days))
    empty_days = max(1, min(int(empty_days), review_days))
    current = now or timezone.now()
    review_cutoff = current - timedelta(days=review_days)
    empty_cutoff = current - timedelta(days=empty_days)

    empty_ids = list(
        AIChangeSet.objects.filter(
            status=AIChangeSet.STATUS_DRAFT,
            updated_at__lt=empty_cutoff,
            operations__isnull=True,
        ).values_list("id", flat=True)
    )
    expirable_ids = list(
        AIChangeSet.objects.filter(
            status__in=AIChangeSet.EDITABLE_STATUSES,
            updated_at__lt=review_cutoff,
        )
        .exclude(id__in=empty_ids)
        .values_list("id", flat=True)
    )

    if dry_run:
        return {"deletedEmptyDrafts": len(empty_ids), "expiredProposals": len(expirable_ids)}

    deleted = 0
    if empty_ids:
        deleted, _detail = AIChangeSet.objects.filter(id__in=empty_ids).delete()
    expired = 0
    if expirable_ids:
        expired = AIChangeSet.objects.filter(id__in=expirable_ids).update(
            status=AIChangeSet.STATUS_EXPIRED,
            validation_token="",
            validated_at=None,
            expires_at=current,
            updated_at=current,
        )
    return {"deletedEmptyDrafts": deleted, "expiredProposals": expired}

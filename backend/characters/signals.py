from django.db.models import Count
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from backend.characters.models import Personaggio
from backend.characters.services.combat_buttons import MAX_COMBAT_BUTTONS_PER_CHARACTER
from backend.core.models import Giocatore


def _recent_replacement_character(deleted_character_id: int) -> Personaggio | None:
    recently_active_ids = (
        Giocatore.objects.exclude(active_character_id__isnull=True)
        .exclude(active_character_id=deleted_character_id)
        .order_by("-updated_at", "-id")
        .values_list("active_character_id", flat=True)
    )
    seen: set[int] = set()
    for character_id in recently_active_ids:
        if character_id in seen:
            continue
        seen.add(character_id)
        candidate = (
            Personaggio.objects.filter(pk=character_id, archived_at__isnull=True)
            .annotate(combat_button_count=Count("bottoni_combat"))
            .filter(combat_button_count__lt=MAX_COMBAT_BUTTONS_PER_CHARACTER)
            .first()
        )
        if candidate:
            return candidate
    return (
        Personaggio.objects.exclude(pk=deleted_character_id)
        .filter(archived_at__isnull=True)
        .annotate(combat_button_count=Count("bottoni_combat"))
        .filter(combat_button_count__lt=MAX_COMBAT_BUTTONS_PER_CHARACTER)
        .order_by("-updated_at", "-id")
        .first()
    )


@receiver(pre_delete, sender=Personaggio)
def preserve_public_combat_buttons(sender, instance: Personaggio, using, **kwargs):
    """Private buttons follow their character; public ones move to the most recent viable character."""

    buttons = instance.bottoni_combat.using(using)
    buttons.filter(pubblico=False).delete()
    replacement = _recent_replacement_character(instance.pk)
    buttons.filter(pubblico=True).update(personaggio=replacement)


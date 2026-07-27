from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from backend.core.api import ApiError

from ..models import Personaggio
from .refresh_personaggio import refresh_personaggio


@dataclass(frozen=True)
class EnergySpendResult:
    maximum: int
    current_before: int
    spent_after: int
    fatigue_added: int


def calculate_energy_spend(maximum: int, spent: int, cost: int) -> EnergySpendResult:
    """Apply the legacy energy cycle: crossing below zero refills once and adds fatigue."""
    normalized_maximum = max(0, int(maximum))
    normalized_spent = int(spent)
    normalized_cost = int(cost)
    if normalized_cost < 0:
        raise ValueError("Energy cost cannot be negative.")

    current = normalized_maximum - normalized_spent
    if normalized_cost <= current:
        return EnergySpendResult(
            maximum=normalized_maximum,
            current_before=current,
            spent_after=normalized_spent + normalized_cost,
            fatigue_added=0,
        )
    if normalized_maximum <= 0:
        raise ApiError(
            "character.energy_unavailable",
            "Il personaggio non ha Energia massima da ripristinare.",
            "energia",
            409,
        )

    return EnergySpendResult(
        maximum=normalized_maximum,
        current_before=current,
        spent_after=normalized_cost - current,
        fatigue_added=1,
    )


@transaction.atomic
def spend_energy(personaggio: Personaggio, cost: int) -> EnergySpendResult:
    maximum = int(float((personaggio.tot or {}).get("energia", 0) or 0))
    result = calculate_energy_spend(maximum, int(personaggio.energia_spesa or 0), cost)
    personaggio.energia_spesa = result.spent_after
    update_fields = ["energia_spesa", "updated_at"]
    if result.fatigue_added:
        personaggio.stanchezza_accumulata = int(personaggio.stanchezza_accumulata or 0) + result.fatigue_added
        update_fields.insert(1, "stanchezza_accumulata")
    personaggio.save(update_fields=update_fields)

    if result.fatigue_added:
        refresh_personaggio(personaggio)
        personaggio.refresh_from_db()
    return result

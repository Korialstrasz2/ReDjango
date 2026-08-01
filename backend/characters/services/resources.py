from __future__ import annotations

import math
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


def calculate_mana_siphon(mana_spent: int, siphon_percent: float) -> int:
    """Elder's siphon share: the percentage is floored, then the product truncated.

    Ported verbatim from Elder Django's `gestisci_sifone`, so a character keeps
    banking exactly what the legacy sheet banked.
    """
    normalized_spent = int(mana_spent)
    if normalized_spent <= 0:
        return 0
    percent = math.floor(float(siphon_percent or 0))
    if percent <= 0:
        return 0
    return int(normalized_spent / 100 * percent)


@transaction.atomic
def accrue_mana_siphon(personaggio: Personaggio, mana_spent: int) -> int:
    """Bank a share of freshly spent Mana. Returns how much was siphoned."""
    siphoned = calculate_mana_siphon(mana_spent, (personaggio.tot or {}).get("sifone_di_mana", 0))
    if not siphoned:
        return 0
    personaggio.mana_in_sifone = int(personaggio.mana_in_sifone or 0) + siphoned
    personaggio.save(update_fields=["mana_in_sifone", "updated_at"])
    return siphoned


@transaction.atomic
def recover_mana_siphon(personaggio: Personaggio) -> int:
    """Empty the reserve back into spent Mana. Returns how much was actually recovered.

    All-or-nothing like Elder: the whole reserve is spent at once and any surplus
    beyond the Mana beforehand is lost.
    """
    reserve = int(personaggio.mana_in_sifone or 0)
    if reserve <= 0:
        raise ApiError(
            "character.mana_siphon_empty",
            "Non c'è Mana nel sifone da recuperare.",
            "mana",
            409,
        )
    spent_before = int(personaggio.mana_speso or 0)
    personaggio.mana_speso = max(0, spent_before - reserve)
    personaggio.mana_in_sifone = 0
    personaggio.save(update_fields=["mana_speso", "mana_in_sifone", "updated_at"])
    return spent_before - personaggio.mana_speso

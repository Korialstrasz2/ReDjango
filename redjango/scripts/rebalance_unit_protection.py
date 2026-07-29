"""Apply the authored armour, chainmail, and robe balance policy to live Units.

Run without ``--apply`` to audit the proposed changes.  ``--apply`` only edits
the ten Units listed below and is safe to run again.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "redjango.settings")

import django  # noqa: E402

django.setup()

from backend.core.models import Unit  # noqa: E402


DROP_SLOTS = {
    "Berserker Nord": {"chainmail"},
    "Ordinatore": {"veste"},
    "Alto Stregone Telvanni": {"chainmail"},
    "Mago da Battaglia Imperiale": {"chainmail"},
    "Stregone Bretone": {"chainmail"},
    "Stregone Dunmer": {"chainmail"},
}
ELITE_CHAINMAIL_AT_15 = {
    "Ordinatore",
    "Comandante della Legione Imperiale",
    "Principe Dremora",
    "Signore della Guerra Orco",
    "Signore Dremora",
}


def rebalance_profile(name: str, profile: dict) -> tuple[dict, list[str]]:
    profile = dict(profile or {})
    slots = {slot: list(entries) for slot, entries in (profile.get("slots") or {}).items()}
    changes: list[str] = []
    for slot in DROP_SLOTS.get(name, set()):
        if slot in slots:
            slots.pop(slot)
            changes.append(f"removed {slot}")
    if name in ELITE_CHAINMAIL_AT_15:
        adjusted = []
        for entry in slots.get("chainmail", []):
            copy = dict(entry)
            if int(copy.get("minLevel", 1)) < 15:
                copy["minLevel"] = 15
                changes.append("chainmail starts at level 15")
            adjusted.append(copy)
        if adjusted:
            slots["chainmail"] = adjusted
    profile["slots"] = slots
    layers = {"armatura", "chainmail", "veste"} & set(slots)
    if len(layers) == 3:
        raise RuntimeError(f"{name} still has all three protection layers")
    return profile, changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    names = sorted(set(DROP_SLOTS) | ELITE_CHAINMAIL_AT_15)
    changed = 0
    for unit in Unit.objects.filter(nome__in=names, archived_at__isnull=True).order_by("nome"):
        profile, changes = rebalance_profile(unit.nome, unit.equipment_profiles)
        if not changes:
            continue
        changed += 1
        print(f"{unit.nome}: {', '.join(changes)}")
        if args.apply:
            unit.equipment_profiles = profile
            unit.save(update_fields=["equipment_profiles", "updated_at"])
    print(f"{'applied' if args.apply else 'would change'}: {changed}")


if __name__ == "__main__":
    main()

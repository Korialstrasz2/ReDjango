"""Read model del banco Incantamento."""

from __future__ import annotations

from typing import Any

from backend.core.enchant_defaults import (
    MAX_ENCHANT_LEVEL,
    SCROLL_MANA_LADDER,
    effective_enchant_mana,
)
from backend.core.models import SpellDefinition

from .crafting_capability import enchant_capabilities, enchant_table_rules
from .models import Personaggio
from .services.enchant import (
    available_kinds,
    enchantable_targets,
    owned_altars,
    owned_gems,
)
from .services.item_instances import instance_block, owned_instances


def _known_spells(character: Personaggio) -> list[dict[str, Any]]:
    """Incantesimi che il personaggio conosce davvero.

    Una pergamena si può imprimere solo con ciò che si sa lanciare: l'elenco
    parte dalle abilità sbloccate, non dai 102 incantesimi del catalogo.
    """
    skill_ids = list(
        character.skill_sbloccate.filter(archived_at__isnull=True).values_list("skill_id", flat=True)
    )
    if not skill_ids:
        return []
    queryset = (
        SpellDefinition.objects.filter(skill_id__in=skill_ids, archived_at__isnull=True)
        .select_related("skill", "skill__famiglia")
        .order_by("skill__famiglia__nome", "skill__nome")
    )
    return [
        {
            "spellId": spell.id,
            "name": spell.skill.nome,
            "school": spell.skill.famiglia.nome,
            "tier": spell.tier,
            "minimumMana": float(spell.minimum_mana or 0),
            "formula": spell.legacy_formula,
            "effectUnit": spell.effect_unit,
        }
        for spell in queryset
    ]


def _enchanted_items(character: Personaggio) -> list[dict[str, Any]]:
    rows = []
    for item in owned_instances(character, kinds=("enchanted", "scroll")):
        block = instance_block(item)
        enchantments = block.get("enchantments", [])
        rows.append(
            {
                "instanceId": item.id,
                "name": item.nome,
                "icon": item.icona,
                "type": item.tipo_1,
                "kind": block.get("kind", ""),
                "effects": [
                    {
                        "kind": entry.get("kind", ""),
                        "label": entry.get("label", ""),
                        "level": int(entry.get("level", 0)),
                        "charges": int(entry.get("charges", 0)),
                        "chargesMax": int(entry.get("chargesMax", 0)),
                        "mana": float(entry.get("mana", 0)),
                    }
                    for entry in enchantments
                ],
                "spell": block.get("spellName", ""),
                "scrollLevel": int(block.get("level", 0)) if block.get("kind") == "scroll" else 0,
                "castEffect": float(block.get("castEffect", 0)),
                "tableRules": [line for line in (item.regole_speciali or "").splitlines() if line.strip()],
            }
        )
    return rows


def enchant_payload(character: Personaggio, *, slot_type: str = "", level: int = 0) -> dict[str, Any]:
    capability = enchant_capabilities(character)
    gems = owned_gems(character)
    altars = owned_altars(character)
    best_altar = altars[0] if altars else None
    targets = enchantable_targets(character)

    # Le combinazioni possibili sono ~70 per slot per livello: si calcolano solo
    # per la coppia che il banco sta guardando, non per tutte.
    preview_slot = slot_type or (targets[0]["type"] if targets else "")
    preview_level = level or max((gem["level"] for gem in gems if gem["filled"]), default=0)
    preview_level = max(0, min(MAX_ENCHANT_LEVEL, preview_level))
    kinds = (
        available_kinds(preview_slot, preview_level)
        if preview_slot and preview_level
        else []
    )

    mana_preview = [
        {
            "level": entry_level,
            "mana": effective_enchant_mana(
                entry_level, capability["manaPerLevel"], best_altar["bonus"] if best_altar else 0.0
            ),
        }
        for entry_level in range(1, MAX_ENCHANT_LEVEL + 1)
    ]

    return {
        "character": {
            "id": character.id,
            "name": character.nome,
            "level": character.livello,
            "fatigue": int(character.stanchezza_accumulata or 0),
        },
        "capability": capability,
        "gems": gems,
        "altars": altars,
        "targets": targets,
        "preview": {"slotType": preview_slot, "level": preview_level, "kinds": kinds},
        "manaLadder": mana_preview,
        "spells": _known_spells(character),
        "scrollLadder": list(SCROLL_MANA_LADDER),
        "enchanted": _enchanted_items(character),
        "tableRules": enchant_table_rules(character),
        "notes": character.note.crafting if character.note else "",
        "rules": {
            "mana": "Ogni livello vale il mana per livello, più la percentuale dell'altare.",
            "charges": "Le cariche sono pari al livello della gemma e si ricaricano al 100% ogni giorno.",
            "scroll": "Una pergamena casta a metà del mana impresso; estrarla e lanciarla costa 3 PA.",
            "targets": "Si incantano gioielli, fasce, spille, cinture e mantelli: non armi o armature.",
        },
    }

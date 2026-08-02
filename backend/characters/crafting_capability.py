"""Cosa un personaggio sa fare al banco, letto dalle abilità sbloccate.

I permessi non sono numeri — «fascia 2» più «fascia 3» non fa «fascia 5», e i
materiali oltre la terza fascia si sbloccano a rami separati — quindi vivono in
``Skill.metadata`` e si leggono da qui. Le grandezze restano in
``Personaggio.tot`` e si leggono con ``total()``.
"""

from __future__ import annotations

from typing import Any

from backend.core.crafting_skill_rules import ENCHANT_RULE_KEY, FORGE_RULE_KEY
from backend.core.forge_defaults import MATERIAL_BY_KEY

from .models import Personaggio


def total(character: Personaggio, key: str, default: float = 0.0) -> float:
    totals = character.tot if isinstance(character.tot, dict) else {}
    try:
        return float(totals.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _rules(character: Personaggio, metadata_key: str) -> list[tuple[str, dict[str, Any]]]:
    found: list[tuple[str, dict[str, Any]]] = []
    ownerships = character.skill_sbloccate.filter(archived_at__isnull=True).select_related("skill")
    for ownership in ownerships:
        metadata = ownership.skill.metadata if isinstance(ownership.skill.metadata, dict) else {}
        rule = metadata.get(metadata_key)
        if isinstance(rule, dict) and rule.get("type"):
            found.append((ownership.skill.nome, rule))
    return found


def unlocked_materials(character: Personaggio) -> dict[str, str]:
    """Materiale → nome dell'abilità che lo sblocca."""
    unlocked: dict[str, str] = {}
    for skill_name, rule in _rules(character, FORGE_RULE_KEY):
        if rule.get("type") != "material_unlock":
            continue
        for material in rule.get("materials", []):
            if material in MATERIAL_BY_KEY:
                unlocked.setdefault(material, skill_name)
    return unlocked


def material_unlock_sources() -> dict[str, str]:
    """Materiale → abilità che lo sbloccherebbe, per i materiali ancora chiusi."""
    from backend.core.crafting_skill_rules import MATERIAL_UNLOCKS

    return {
        material: skill_name
        for skill_name, materials in MATERIAL_UNLOCKS.items()
        for material in materials
    }


def specialist_material(character: Personaggio) -> str:
    """Materiale scelto con Specialista, conservato in ``Personaggio.extra``.

    Non può stare nei totali: quelli sono float, e questo è una stringa.
    """
    extra = character.extra if isinstance(character.extra, dict) else {}
    forge = extra.get("forgia") if isinstance(extra.get("forgia"), dict) else {}
    material = str(forge.get("specialistaMateriale") or "")
    return material if material in MATERIAL_BY_KEY else ""


def improvement_budget(character: Personaggio, material_key: str) -> dict[str, Any]:
    """Punti miglioramento disponibili su un oggetto di quel materiale.

    Elder: Potenziato N alza il tetto a N+1 e da lì si sottrae la fascia del
    materiale; Specialista aggiunge punti solo sul materiale scelto.
    """
    base = int(total(character, "forgia_tetto_miglioramenti"))
    tier = MATERIAL_BY_KEY.get(material_key, {}).get("tier", 0)
    specialist = int(total(character, "forgia_miglioramenti_specialista"))
    specialist_applies = bool(specialist) and specialist_material(character) == material_key
    fatigue_bonus = int(total(character, "forgia_miglioramenti_stanchezza"))
    maximum = max(0, base - tier) + (specialist if specialist_applies else 0)
    return {
        "base": base,
        "materialTier": tier,
        "specialist": specialist if specialist_applies else 0,
        "specialistMaterial": specialist_material(character),
        "fatigueBonus": fatigue_bonus,
        "max": maximum,
        "formula": f"Potenziato ({base}) − fascia ({tier})"
        + (f" + specialista ({specialist})" if specialist_applies else ""),
    }


def forge_capabilities(character: Personaggio) -> dict[str, Any]:
    return {
        "canMelt": total(character, "forgia_puo_fondere") > 0,
        "canReshape": total(character, "forgia_puo_riplasmare") > 0,
        "canForgeAnywhere": total(character, "forgia_puo_ovunque") > 0,
        "arrowBonus": int(total(character, "forgia_bonus_frecce")),
        "practicalLevel": int(total(character, "forgia_uso_pratico")),
        "fatigueForExtraPoint": int(total(character, "forgia_miglioramenti_stanchezza")),
    }


def enchant_capabilities(character: Personaggio) -> dict[str, Any]:
    return {
        "maxItemLevel": int(total(character, "incanta_livello_max_oggetti")),
        "maxScrollLevel": int(total(character, "incanta_livello_max_pergamene")),
        "manaPerLevel": total(character, "incanta_mana_per_livello", 5.0) or 5.0,
        "chargeBonusPercent": total(character, "incanta_cariche_percento"),
        "maxEffects": max(1, int(total(character, "incanta_max_effetti", 1.0))),
        "canReenchant": total(character, "incanta_puo_reincantare") > 0,
        "canCombineGems": total(character, "incanta_puo_sommare_gemme") > 0,
        "canDisenchant": total(character, "incanta_puo_disincantare") > 0,
        "fatigueLevelBonus": int(total(character, "incanta_bonus_livello_stanchezza")),
    }


def table_rules(character: Personaggio, metadata_key: str) -> list[dict[str, str]]:
    """Regole che il motore non applica ma che il personaggio possiede."""
    return [
        {"skill": skill_name, "text": rule.get("text", "")}
        for skill_name, rule in _rules(character, metadata_key)
        if rule.get("type") == "table_rule" and rule.get("text")
    ]


def forge_table_rules(character: Personaggio) -> list[dict[str, str]]:
    return table_rules(character, FORGE_RULE_KEY)


def enchant_table_rules(character: Personaggio) -> list[dict[str, str]]:
    return table_rules(character, ENCHANT_RULE_KEY)

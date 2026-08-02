"""Il banco dell'Incantamento: infondere oggetti, imprimere pergamene.

Il catalogo accessori è già la tabella dei risultati: per ogni slot, tipo di
effetto e livello 1-10 esiste una riga con i suoi ``effects`` corretti. Quindi
incantare non inventa un effetto, lo cerca — e l'esemplare eredita gli effetti
della riga trovata.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from backend.core.api import ApiError
from backend.core.enchant_defaults import (
    ALTAR_TYPE,
    ENCHANTABLE_SLOT_TYPES,
    MAX_ENCHANT_LEVEL,
    SCROLL_EFFECT_RATIO,
    SOUL_GEM_FULL_MARKER,
    SOUL_GEM_TYPE,
    altar_bonus_for_name,
    charges_for_gem,
    effective_enchant_mana,
    harmonic_gem_level,
    scroll_level_for_mana,
)
from backend.core.models import Oggetto, SpellDefinition

from ..crafting_capability import enchant_capabilities
from ..models import Personaggio, Zaino
from .item_instances import (
    append_table_rule,
    create_instance,
    instance_block,
    is_instance,
    rebuild_effects,
    store_in_backpack,
    write_instance_block,
)


def _locked_character(character_id: int) -> Personaggio:
    try:
        return (
            Personaggio.objects.select_for_update()
            .select_related("zaino", "equip", "note")
            .get(pk=character_id)
        )
    except Personaggio.DoesNotExist as exc:
        raise ApiError("enchant.character_not_found", "Personaggio non trovato.", status=404) from exc


def _backpack_items(character: Personaggio) -> list[tuple[int, Oggetto]]:
    zaino: Zaino | None = character.zaino
    if zaino is None:
        return []
    rows = []
    for slot in range(1, 51):
        item = getattr(zaino, f"slot_{slot}", None)
        if item is not None:
            rows.append((slot, item))
    return rows


def gem_level(item: Oggetto) -> int:
    """Livello di una gemma dal suo ``lv_loot``, o dal nome come ripiego."""
    if item.tipo_1 != SOUL_GEM_TYPE:
        return 0
    if item.lv_loot and item.lv_loot.strip().isdigit():
        return int(item.lv_loot.strip())
    digits = "".join(character for character in item.nome if character.isdigit())
    return int(digits) if digits else 0


def gem_is_full(item: Oggetto) -> bool:
    return SOUL_GEM_FULL_MARKER in item.nome


def owned_gems(character: Personaggio) -> list[dict[str, Any]]:
    rows = []
    for slot, item in _backpack_items(character):
        if item.tipo_1 != SOUL_GEM_TYPE:
            continue
        rows.append(
            {
                "slot": slot,
                "itemId": item.id,
                "name": item.nome,
                "level": gem_level(item),
                "filled": gem_is_full(item),
            }
        )
    return sorted(rows, key=lambda row: (not row["filled"], -row["level"]))


def owned_altars(character: Personaggio) -> list[dict[str, Any]]:
    rows = []
    seen: set[int] = set()
    for _slot, item in _backpack_items(character):
        if item.tipo_1 != ALTAR_TYPE or item.id in seen:
            continue
        seen.add(item.id)
        rows.append(
            {
                "itemId": item.id,
                "name": item.nome,
                "bonus": altar_bonus_for_name(item.nome),
                "bonusPercent": round(altar_bonus_for_name(item.nome) * 100),
                "portable": "portatile" in item.nome.lower(),
            }
        )
    return sorted(rows, key=lambda row: -row["bonus"])


def enchantable_targets(character: Personaggio) -> list[dict[str, Any]]:
    """Oggetti dello zaino che si possono incantare.

    Elder limita l'incantamento a gioielli, fasce e mantelli: armi e armature
    restano fuori. Un oggetto già incantato ricompare solo se il personaggio ha
    Multi Incantamento o Incantatore Esperto.
    """
    capability = enchant_capabilities(character)
    rows = []
    for slot, item in _backpack_items(character):
        if (item.tipo_1 or "").lower() not in ENCHANTABLE_SLOT_TYPES:
            continue
        block = instance_block(item) if is_instance(item) else {}
        existing = len(block.get("enchantments", []))
        if existing and existing >= capability["maxEffects"]:
            continue
        if existing and not capability["canReenchant"] and not block.get("kind") == "enchanted":
            continue
        rows.append(
            {
                "slot": slot,
                "itemId": item.id,
                "name": item.nome,
                "type": item.tipo_1,
                "isInstance": bool(block),
                "existingEffects": existing,
            }
        )
    return rows


def available_kinds(slot_type: str, level: int) -> list[dict[str, Any]]:
    """Effetti incantabili su quello slot a quel livello.

    Alcuni tipi (i ``*_extra`` di caratteristica) partono dal livello 3: se il
    livello non li copre semplicemente non compaiono, invece di comparire e
    fallire al momento del comando.
    """
    queryset = (
        Oggetto.objects.filter(
            modello=True,
            archiviato=False,
            archived_at__isnull=True,
            tipo_1=slot_type,
            lv_loot=str(level),
        )
        .exclude(tipo_2="")
        .only("id", "nome", "tipo_2", "valore", "effects")
        .order_by("tipo_2")
    )
    from backend.core.enchant_defaults import enchant_kind_label

    return [
        {
            "kind": item.tipo_2,
            "label": enchant_kind_label(item.tipo_2),
            "resultItemId": item.id,
            "resultName": item.nome,
            "value": item.valore or 0,
            "hasEffects": bool(item.effects),
        }
        for item in queryset
    ]


def _consume_gems(character: Personaggio, gem_slots: list[int]) -> list[int]:
    """Toglie le gemme usate e torna i loro livelli.

    Le gemme si identificano per **slot dello zaino**, non per id d'oggetto: due
    gemme identiche sono la stessa riga di catalogo in due slot diversi, e
    sceglierne una per id ne consumerebbe due.
    """
    zaino: Zaino | None = character.zaino
    if zaino is None:
        raise ApiError("enchant.no_backpack", "Il personaggio non ha uno zaino.", status=409)
    wanted = sorted({int(slot) for slot in gem_slots})
    levels: list[int] = []
    updates: list[str] = []
    for slot in wanted:
        if not 1 <= slot <= 50:
            raise ApiError("enchant.gem_missing", "Slot della gemma non valido.", "gemSlots", 409)
        item = getattr(zaino, f"slot_{slot}", None)
        if item is None or item.tipo_1 != SOUL_GEM_TYPE:
            raise ApiError(
                "enchant.gem_missing",
                "Una delle gemme scelte non è più nello zaino.",
                "gemSlots",
                409,
            )
        if not gem_is_full(item):
            raise ApiError(
                "enchant.gem_empty",
                f"«{item.nome}» è vuota: serve un'anima dentro.",
                "gemSlots",
                409,
            )
        levels.append(gem_level(item))
        setattr(zaino, f"slot_{slot}", None)
        updates.append(f"slot_{slot}")
    zaino.save(update_fields=[*updates, "updated_at"])
    return levels


@transaction.atomic
def enchant_item(
    character_id: int,
    target_item_id: int,
    gem_slots: list[int],
    kind: str,
    altar_item_id: int | None = None,
    use_fatigue: bool = False,
) -> tuple[Personaggio, dict[str, Any]]:
    character = _locked_character(character_id)
    capability = enchant_capabilities(character)
    if capability["maxItemLevel"] <= 0:
        raise ApiError(
            "enchant.not_an_enchanter",
            "Ti manca «Incantatore 1»: non puoi ancora incantare oggetti.",
            status=409,
        )
    if not gem_slots:
        raise ApiError("enchant.gem_required", "Serve almeno una gemma dell'anima piena.", "gemSlots")
    if len(set(gem_slots)) > 1 and not capability["canCombineGems"]:
        raise ApiError(
            "enchant.cannot_combine",
            "Ti manca «Artigiano di anime»: puoi usare una sola gemma per volta.",
            "gemSlots",
            409,
        )

    try:
        target = Oggetto.objects.select_for_update().get(pk=target_item_id)
    except Oggetto.DoesNotExist as exc:
        raise ApiError("enchant.target_not_found", "Oggetto non trovato.", "targetItemId", 404) from exc
    slot_type = (target.tipo_1 or "").lower()
    if slot_type not in ENCHANTABLE_SLOT_TYPES:
        raise ApiError(
            "enchant.target_invalid",
            "Si incantano gioielli, fasce, spille, cinture e mantelli: non armi o armature.",
            "targetItemId",
            409,
        )

    altar_bonus, altar_name = 0.0, ""
    if altar_item_id:
        altar = Oggetto.objects.filter(pk=altar_item_id, tipo_1=ALTAR_TYPE).first()
        if altar is None:
            raise ApiError("enchant.altar_not_found", "Altare non trovato.", "altarItemId", 404)
        altar_bonus, altar_name = altar_bonus_for_name(altar.nome), altar.nome

    levels = _consume_gems(character, gem_slots)
    level = harmonic_gem_level(levels) if len(levels) > 1 else levels[0]
    if use_fatigue:
        if capability["fatigueLevelBonus"] <= 0:
            raise ApiError(
                "enchant.fatigue_unavailable",
                "Ti manca «Mana e anima»: non puoi spendere Stanchezza per un livello extra.",
                "useFatigue",
                409,
            )
        level = min(MAX_ENCHANT_LEVEL, level + capability["fatigueLevelBonus"])
    level = max(1, min(MAX_ENCHANT_LEVEL, level))
    if level > capability["maxItemLevel"]:
        raise ApiError(
            "enchant.level_too_high",
            f"Puoi incantare fino al livello {capability['maxItemLevel']}, ma questa gemma vale {level}.",
            "gemSlots",
            409,
        )

    matches = [entry for entry in available_kinds(slot_type, level) if entry["kind"] == kind]
    if not matches:
        raise ApiError(
            "enchant.kind_unavailable",
            "Questo effetto non esiste per quello slot a quel livello.",
            "kind",
            409,
        )
    result_item = Oggetto.objects.get(pk=matches[0]["resultItemId"])
    charges = charges_for_gem(level, capability["chargeBonusPercent"])
    mana = effective_enchant_mana(level, capability["manaPerLevel"], altar_bonus)

    if is_instance(target):
        instance = target
    else:
        instance = create_instance(target, character, kind="enchanted", extra={"enchantments": []})
        _replace_in_backpack(character, target, instance)

    block = instance_block(instance)
    enchantments = [dict(entry) for entry in block.get("enchantments", [])]
    enchantments.append(
        {
            "kind": kind,
            "label": matches[0]["label"],
            "level": level,
            "charges": charges,
            "chargesMax": charges,
            "mana": mana,
            "altar": altar_name,
            "effects": [dict(effect) for effect in (result_item.effects or [])],
            "sourceItemId": result_item.id,
        }
    )
    block["enchantments"] = enchantments
    block["kind"] = block.get("kind") or "enchanted"
    write_instance_block(instance, block)
    rebuild_effects(instance)
    append_table_rule(
        instance,
        f"{matches[0]['label']} lv {level}: {charges} cariche, ricarica al 100% ogni giorno.",
    )
    instance.save(update_fields=["metadata", "effects", "regole_speciali", "updated_at"])

    if use_fatigue:
        character.stanchezza_accumulata = int(character.stanchezza_accumulata or 0) + 1
        character.save(update_fields=["stanchezza_accumulata", "updated_at"])

    from .refresh_personaggio import refresh_personaggio

    refresh_personaggio(character)
    character.refresh_from_db()
    return character, {
        "itemId": instance.id,
        "name": instance.nome,
        "kind": kind,
        "label": matches[0]["label"],
        "level": level,
        "charges": charges,
        "mana": mana,
        "altar": altar_name,
        "gemsUsed": len(levels),
        "effectCount": len(enchantments),
    }


def _replace_in_backpack(character: Personaggio, template: Oggetto, instance: Oggetto) -> None:
    """Sostituisce il modello con l'esemplare nello stesso slot dello zaino."""
    zaino: Zaino | None = character.zaino
    if zaino is None:
        return
    for slot in range(1, 51):
        if getattr(zaino, f"slot_{slot}_id", None) == template.id:
            setattr(zaino, f"slot_{slot}", instance)
            zaino.save(update_fields=[f"slot_{slot}", "updated_at"])
            return
    store_in_backpack(character, instance)


@transaction.atomic
def inscribe_scroll(
    character_id: int,
    spell_id: int,
    mana_spent: float,
    altar_item_id: int | None = None,
) -> tuple[Personaggio, dict[str, Any]]:
    """Imprime un incantesimo in una pergamena.

    Elder: l'effetto della pergamena è la metà di quello impresso, e il livello
    lo decide la scala 12/22/34/…/118 mana.
    """
    character = _locked_character(character_id)
    capability = enchant_capabilities(character)
    if capability["maxScrollLevel"] <= 0:
        raise ApiError(
            "enchant.not_a_scribe",
            "Ti manca «Incantatore 1»: non puoi ancora creare pergamene.",
            status=409,
        )
    try:
        spell = SpellDefinition.objects.select_related("skill", "skill__famiglia").get(pk=spell_id)
    except SpellDefinition.DoesNotExist as exc:
        raise ApiError("enchant.spell_not_found", "Incantesimo non trovato.", "spellId", 404) from exc
    if not character.skill_sbloccate.filter(skill=spell.skill, archived_at__isnull=True).exists():
        raise ApiError(
            "enchant.spell_unknown",
            f"Non conosci «{spell.skill.nome}»: non puoi imprimerlo.",
            "spellId",
            409,
        )

    altar_bonus, altar_name = 0.0, ""
    if altar_item_id:
        altar = Oggetto.objects.filter(pk=altar_item_id, tipo_1=ALTAR_TYPE).first()
        if altar is None:
            raise ApiError("enchant.altar_not_found", "Altare non trovato.", "altarItemId", 404)
        altar_bonus, altar_name = altar_bonus_for_name(altar.nome), altar.nome

    try:
        impressed = float(mana_spent)
    except (TypeError, ValueError) as exc:
        raise ApiError("enchant.mana_invalid", "Il mana deve essere un numero.", "manaSpent") from exc
    if impressed <= 0:
        raise ApiError("enchant.mana_invalid", "Serve del mana per imprimere l'incantesimo.", "manaSpent")

    boosted = round(impressed * (1.0 + altar_bonus), 2)
    level = scroll_level_for_mana(boosted)
    if level <= 0:
        raise ApiError(
            "enchant.mana_too_low",
            "Servono almeno 12 mana per una pergamena di livello 1.",
            "manaSpent",
            409,
        )
    if level > capability["maxScrollLevel"]:
        raise ApiError(
            "enchant.scroll_level_too_high",
            f"Puoi scrivere pergamene fino al livello {capability['maxScrollLevel']}, "
            f"ma con {boosted:g} mana ne uscirebbe una di livello {level}.",
            "manaSpent",
            409,
        )

    cast_effect = round(boosted * SCROLL_EFFECT_RATIO, 2)
    school = spell.skill.famiglia.nome
    template = (
        Oggetto.objects.filter(
            modello=True,
            archiviato=False,
            tipo_1="pergamena",
            lv_loot=str(level),
            tipo_2__istartswith=school[:6].lower(),
        )
        .order_by("nome")
        .first()
    )
    if template is None:
        template = (
            Oggetto.objects.filter(modello=True, archiviato=False, tipo_1="pergamena", lv_loot=str(level))
            .order_by("nome")
            .first()
        )
    if template is None:
        raise ApiError(
            "enchant.scroll_template_missing",
            f"Il catalogo non ha una pergamena di livello {level}.",
            status=409,
        )

    instance = create_instance(
        template,
        character,
        kind="scroll",
        extra={
            "spellId": spell.id,
            "spellName": spell.skill.nome,
            "school": school,
            "manaImpressed": impressed,
            "manaEffective": boosted,
            "castEffect": cast_effect,
            "level": level,
            "altar": altar_name,
        },
    )
    append_table_rule(
        instance,
        f"{spell.skill.nome}: impressa con {boosted:g} mana, casta a metà ({cast_effect:g} mana). "
        "Estrarre e castare costa 3 punti azione.",
    )
    instance.save(update_fields=["regole_speciali", "updated_at"])
    slot = store_in_backpack(character, instance)
    return character, {
        "itemId": instance.id,
        "name": instance.nome,
        "spell": spell.skill.nome,
        "school": school,
        "level": level,
        "manaImpressed": impressed,
        "manaEffective": boosted,
        "castEffect": cast_effect,
        "altar": altar_name,
        "slot": slot,
        "stored": bool(slot),
    }


@transaction.atomic
def recharge_item(character_id: int, instance_id: int) -> tuple[Personaggio, dict[str, Any]]:
    """Riporta le cariche al massimo. Manuale: nessun orologio le consuma ancora."""
    character = _locked_character(character_id)
    try:
        item = Oggetto.objects.select_for_update().get(pk=instance_id)
    except Oggetto.DoesNotExist as exc:
        raise ApiError("enchant.instance_not_found", "Esemplare non trovato.", "instanceId", 404) from exc
    block = instance_block(item)
    enchantments = [dict(entry) for entry in block.get("enchantments", [])]
    if not enchantments:
        raise ApiError("enchant.not_enchanted", "Questo oggetto non ha incantamenti.", "instanceId", 409)
    for entry in enchantments:
        entry["charges"] = int(entry.get("chargesMax", entry.get("charges", 0)))
    block["enchantments"] = enchantments
    write_instance_block(item, block)
    item.save(update_fields=["metadata", "updated_at"])
    return character, {"itemId": item.id, "name": item.nome, "recharged": len(enchantments)}


@transaction.atomic
def disenchant_item(character_id: int, instance_id: int) -> tuple[Personaggio, dict[str, Any]]:
    """Riciclo di anime: svuota un oggetto incantato, al costo di 1 Stanchezza."""
    character = _locked_character(character_id)
    capability = enchant_capabilities(character)
    if not capability["canDisenchant"]:
        raise ApiError(
            "enchant.cannot_disenchant",
            "Ti manca «Riciclo di anime»: non puoi disincantare.",
            status=409,
        )
    try:
        item = Oggetto.objects.select_for_update().get(pk=instance_id)
    except Oggetto.DoesNotExist as exc:
        raise ApiError("enchant.instance_not_found", "Esemplare non trovato.", "instanceId", 404) from exc
    block = instance_block(item)
    enchantments = block.get("enchantments", [])
    if not enchantments:
        raise ApiError("enchant.not_enchanted", "Questo oggetto non ha incantamenti.", "instanceId", 409)

    recovered = max((int(entry.get("level", 0)) for entry in enchantments), default=0)
    block["enchantments"] = []
    write_instance_block(item, block)
    rebuild_effects(item)
    item.regole_speciali = ""
    item.save(update_fields=["metadata", "effects", "regole_speciali", "updated_at"])

    character.stanchezza_accumulata = int(character.stanchezza_accumulata or 0) + 1
    character.save(update_fields=["stanchezza_accumulata", "updated_at"])

    from .refresh_personaggio import refresh_personaggio

    refresh_personaggio(character)
    character.refresh_from_db()
    return character, {
        "itemId": item.id,
        "name": item.nome,
        "soulLevelRecovered": recovered,
        "cleared": len(enchantments),
    }

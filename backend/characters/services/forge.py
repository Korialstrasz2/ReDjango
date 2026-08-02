"""Il banco della Forgiatura: creare, migliorare, fondere.

Ogni comando è atomico e valida da solo: l'anteprima del client è una comodità,
non una fonte di verità. Il registro dei miglioramenti vive sull'esemplare
(vedi ``item_instances``), non sul modello di catalogo.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from backend.core.api import ApiError
from backend.core.forge_defaults import (
    CATEGORY_BY_ITEM_TYPE,
    FORGE_CATEGORIES,
    IMPROVEMENT_BY_KEY,
    INGOT_NAME_BY_MATERIAL,
    MATERIAL_BY_KEY,
    PRACTICAL_LEATHER_BASE,
    PRACTICAL_LEATHER_PER_LEVEL,
    UNIMPROVABLE_ITEM_TYPES,
    item_forge_category,
)
from backend.core.models import Oggetto

from ..crafting_capability import (
    improvement_budget,
    specialist_material,
    total,
    unlocked_materials,
)
from ..models import Personaggio, Zaino
from .item_instances import (
    apply_improvement,
    create_instance,
    instance_block,
    is_instance,
    rebuild_effects,
    release_instance,
    store_in_backpack,
)


SMITH_TOOL_TYPE = "strumentidafabbro"


def _locked_character(character_id: int) -> Personaggio:
    try:
        return (
            Personaggio.objects.select_for_update()
            .select_related("zaino", "equip", "note")
            .get(pk=character_id)
        )
    except Personaggio.DoesNotExist as exc:
        raise ApiError("forge.character_not_found", "Personaggio non trovato.", status=404) from exc


def _backpack_items(character: Personaggio) -> list[Oggetto]:
    zaino: Zaino | None = character.zaino
    if zaino is None:
        return []
    items = []
    for slot in range(1, 51):
        item = getattr(zaino, f"slot_{slot}", None)
        if item is not None:
            items.append(item)
    return items


def ingot_stock(character: Personaggio) -> dict[str, int]:
    """Lingotti nello zaino, contati per materiale.

    I lingotti non dichiarano il proprio materiale in ``tipo_2`` (vale
    ``'lingotto'`` per tutti), quindi si risale dal nome tramite la mappa
    esplicita in ``forge_defaults``. `Lingotto massiccio di oro` non è in
    quella mappa e resta correttamente fuori dal conteggio.
    """
    from backend.core.forge_defaults import MATERIAL_BY_INGOT_NAME

    stock = {key: 0 for key in MATERIAL_BY_KEY}
    for item in _backpack_items(character):
        material = MATERIAL_BY_INGOT_NAME.get(item.nome)
        if material:
            stock[material] += 1
    return stock


def best_smith_tools(character: Personaggio) -> dict[str, Any]:
    """Migliori strumenti da fabbro posseduti: la fascia forgiabile ha un tetto."""
    best_level, best_name = 0, ""
    for item in _backpack_items(character):
        if item.tipo_1 != SMITH_TOOL_TYPE:
            continue
        digits = "".join(character for character in item.nome if character.isdigit())
        level = int(digits) if digits else 0
        if level > best_level:
            best_level, best_name = level, item.nome
    return {"level": best_level, "name": best_name}


def _consume_ingots(character: Personaggio, material_key: str, quantity: int) -> None:
    """Toglie ``quantity`` lingotti di quel materiale dallo zaino."""
    ingot_name = INGOT_NAME_BY_MATERIAL.get(material_key, "")
    zaino: Zaino | None = character.zaino
    if zaino is None:
        raise ApiError("forge.no_backpack", "Il personaggio non ha uno zaino.", status=409)
    removed = 0
    updates: list[str] = []
    for slot in range(1, 51):
        if removed >= quantity:
            break
        item = getattr(zaino, f"slot_{slot}", None)
        if item is not None and item.nome == ingot_name:
            setattr(zaino, f"slot_{slot}", None)
            updates.append(f"slot_{slot}")
            removed += 1
    if removed < quantity:
        raise ApiError(
            "forge.ingots_insufficient",
            f"Servono {quantity} unità di {MATERIAL_BY_KEY[material_key]['label']}: ne hai {removed}.",
            "materialKey",
            409,
        )
    zaino.save(update_fields=[*updates, "updated_at"])


def _grant_ingots(character: Personaggio, material_key: str, quantity: int) -> int:
    """Rimette lingotti nello zaino. Torna quanti sono entrati davvero."""
    template = Oggetto.objects.filter(nome=INGOT_NAME_BY_MATERIAL.get(material_key, "")).first()
    zaino: Zaino | None = character.zaino
    if template is None or zaino is None:
        return 0
    granted, updates = 0, []
    for slot in range(1, 51):
        if granted >= quantity:
            break
        if getattr(zaino, f"slot_{slot}_id", None) is None:
            setattr(zaino, f"slot_{slot}", template)
            updates.append(f"slot_{slot}")
            granted += 1
    if updates:
        zaino.save(update_fields=[*updates, "updated_at"])
    return granted


def blueprint_material(item: Oggetto) -> str:
    return (item.tipo_2 or "").strip().lower()


def _assert_can_work(character: Personaggio, material_key: str) -> None:
    unlocked = unlocked_materials(character)
    if material_key not in unlocked:
        label = MATERIAL_BY_KEY.get(material_key, {}).get("label", material_key)
        raise ApiError(
            "forge.material_locked",
            f"Non hai l'abilità per lavorare {label}.",
            "materialKey",
            409,
        )
    tier = MATERIAL_BY_KEY[material_key]["tier"]
    tools = best_smith_tools(character)
    if tools["level"] < tier:
        raise ApiError(
            "forge.tools_insufficient",
            f"Servono strumenti da fabbro di livello {tier}: "
            + (f"hai solo il livello {tools['level']}." if tools["level"] else "non ne hai."),
            "materialKey",
            409,
        )


@transaction.atomic
def craft_item(character_id: int, blueprint_item_id: int) -> tuple[Personaggio, dict[str, Any]]:
    character = _locked_character(character_id)
    try:
        template = Oggetto.objects.get(pk=blueprint_item_id, archived_at__isnull=True)
    except Oggetto.DoesNotExist as exc:
        raise ApiError("forge.blueprint_not_found", "Oggetto non trovato.", "blueprintItemId", 404) from exc

    category_key = item_forge_category(template.tipo_1)
    if not category_key:
        raise ApiError(
            "forge.blueprint_invalid",
            f"«{template.nome}» non è un oggetto forgiabile.",
            "blueprintItemId",
            409,
        )
    material_key = blueprint_material(template)
    if material_key not in MATERIAL_BY_KEY:
        raise ApiError(
            "forge.material_unknown",
            f"«{template.nome}» non dichiara un materiale lavorabile.",
            "blueprintItemId",
            409,
        )
    _assert_can_work(character, material_key)

    category = FORGE_CATEGORIES[category_key]
    ingots = int(category["ingots"])
    _consume_ingots(character, material_key, ingots)

    produced = int(category.get("yield", 1))
    instance = create_instance(
        template,
        character,
        kind="forged",
        extra={
            "material": material_key,
            "materialTier": MATERIAL_BY_KEY[material_key]["tier"],
            "category": category_key,
            "ingotsSpent": ingots,
            "hours": ingots,
            "quantity": produced,
        },
    )
    # Le frecce escono in gruppo: la resa vive nel registro perché il catalogo
    # non ha un concetto di pila per gli esemplari.
    if produced > 1:
        instance.descrizione = f"{instance.descrizione}\nGruppo di {produced} unità.".strip()
        instance.save(update_fields=["descrizione", "updated_at"])

    slot = store_in_backpack(character, instance)
    return character, {
        "itemId": instance.id,
        "name": instance.nome,
        "material": material_key,
        "materialLabel": MATERIAL_BY_KEY[material_key]["label"],
        "category": category_key,
        "categoryLabel": category["label"],
        "ingotsSpent": ingots,
        "hours": ingots,
        "quantity": produced,
        "slot": slot,
        "stored": bool(slot),
    }


@transaction.atomic
def improve_item(
    character_id: int,
    instance_id: int,
    improvement_key: str,
    use_fatigue: bool = False,
) -> tuple[Personaggio, dict[str, Any]]:
    character = _locked_character(character_id)
    try:
        item = Oggetto.objects.select_for_update().get(pk=instance_id)
    except Oggetto.DoesNotExist as exc:
        raise ApiError("forge.instance_not_found", "Esemplare non trovato.", "instanceId", 404) from exc
    if not is_instance(item):
        raise ApiError(
            "forge.not_an_instance",
            "Solo gli oggetti forgiati al banco possono essere migliorati.",
            "instanceId",
            409,
        )
    if (item.tipo_1 or "").lower() in UNIMPROVABLE_ITEM_TYPES:
        raise ApiError(
            "forge.item_unimprovable",
            "Le cotte di maglia e le vesti non possono essere migliorate.",
            "instanceId",
            409,
        )

    definition = IMPROVEMENT_BY_KEY.get(improvement_key)
    if definition is None:
        raise ApiError("forge.improvement_unknown", "Miglioramento non riconosciuto.", "improvementKey")

    block = instance_block(item)
    material_key = block.get("material", "")
    category_key = block.get("category", "") or item_forge_category(item.tipo_1)
    kind = FORGE_CATEGORIES.get(category_key, {}).get("kind", "weapon")
    if kind not in definition["kinds"]:
        raise ApiError(
            "forge.improvement_not_applicable",
            f"«{definition['label']}» non si applica a questo tipo di oggetto.",
            "improvementKey",
            409,
        )
    if definition.get("twoHandedOnly"):
        from .inventory_rules import item_is_two_handed_weapon

        if not item_is_two_handed_weapon(item):
            raise ApiError(
                "forge.two_handed_only",
                "Questo miglioramento è riservato alle armi a due mani.",
                "improvementKey",
                409,
            )

    _assert_can_work(character, material_key)

    budget = improvement_budget(character, material_key)
    fatigue_bonus = budget["fatigueBonus"] if use_fatigue else 0
    if use_fatigue and not fatigue_bonus:
        raise ApiError(
            "forge.fatigue_unavailable",
            "Non hai «Il meglio che posso»: non puoi spendere Stanchezza per un punto extra.",
            "useFatigue",
            409,
        )
    available = budget["max"] + fatigue_bonus
    spent = int(block.get("pointsSpent", 0))
    from .item_instances import next_improvement_cost

    cost = next_improvement_cost(item, improvement_key)
    if spent + cost > available:
        raise ApiError(
            "forge.budget_exceeded",
            f"Servono {cost} punti miglioramento ma ne restano {max(0, available - spent)}.",
            "improvementKey",
            409,
        )

    result = apply_improvement(item, improvement_key)
    item.save(update_fields=[
        "metadata", "effects", "peso", "pa_per_attacco", "regole_speciali", "updated_at",
    ])

    if use_fatigue:
        character.stanchezza_accumulata = int(character.stanchezza_accumulata or 0) + 1
        character.save(update_fields=["stanchezza_accumulata", "updated_at"])

    from .refresh_personaggio import refresh_personaggio

    refresh_personaggio(character)
    character.refresh_from_db()
    return character, {
        **result,
        "itemId": item.id,
        "name": item.nome,
        "pointsSpent": spent + cost,
        "pointsMax": available,
        "fatigueSpent": 1 if use_fatigue else 0,
    }


@transaction.atomic
def melt_item(character_id: int, instance_id: int) -> tuple[Personaggio, dict[str, Any]]:
    character = _locked_character(character_id)
    if total(character, "forgia_puo_fondere") <= 0:
        raise ApiError(
            "forge.cannot_melt",
            "Ti manca «Scioglitore»: non puoi fondere oggetti per recuperarne il materiale.",
            status=409,
        )
    try:
        item = Oggetto.objects.select_for_update().get(pk=instance_id)
    except Oggetto.DoesNotExist as exc:
        raise ApiError("forge.instance_not_found", "Esemplare non trovato.", "instanceId", 404) from exc
    if not is_instance(item):
        raise ApiError(
            "forge.not_an_instance",
            "Solo gli oggetti forgiati al banco possono essere fusi.",
            "instanceId",
            409,
        )

    block = instance_block(item)
    material_key = block.get("material", "")
    # Elder non promette una resa piena: si recupera il metallo speso per
    # crearlo, non i lingotti versati nei miglioramenti.
    recovered = int(block.get("ingotsSpent", 0))
    name = item.nome
    release_instance(item)
    granted = _grant_ingots(character, material_key, recovered) if recovered else 0

    from .refresh_personaggio import refresh_personaggio

    refresh_personaggio(character)
    character.refresh_from_db()
    return character, {
        "name": name,
        "material": material_key,
        "materialLabel": MATERIAL_BY_KEY.get(material_key, {}).get("label", material_key),
        "recovered": granted,
        "expected": recovered,
        "backpackFull": granted < recovered,
    }


@transaction.atomic
def set_specialist_material(character_id: int, material_key: str) -> tuple[Personaggio, dict[str, Any]]:
    """Lega Specialista a un materiale. Cambiarlo dopo costa 3 Stanchezza."""
    character = _locked_character(character_id)
    if material_key not in MATERIAL_BY_KEY:
        raise ApiError("forge.material_unknown", "Materiale non riconosciuto.", "materialKey")
    if total(character, "forgia_miglioramenti_specialista") <= 0:
        raise ApiError(
            "forge.no_specialist",
            "Ti manca «Specialista»: non hai un materiale da scegliere.",
            status=409,
        )
    previous = specialist_material(character)
    fatigue = 0
    if previous and previous != material_key:
        fatigue = 3
        character.stanchezza_accumulata = int(character.stanchezza_accumulata or 0) + fatigue

    extra = dict(character.extra) if isinstance(character.extra, dict) else {}
    forge = dict(extra.get("forgia")) if isinstance(extra.get("forgia"), dict) else {}
    forge["specialistaMateriale"] = material_key
    extra["forgia"] = forge
    character.extra = extra
    character.save(update_fields=["extra", "stanchezza_accumulata", "updated_at"])
    return character, {
        "material": material_key,
        "materialLabel": MATERIAL_BY_KEY[material_key]["label"],
        "previous": previous,
        "fatigueSpent": fatigue,
    }


@transaction.atomic
def craft_practical_item(character_id: int, blueprint_item_id: int, level: int) -> tuple[Personaggio, dict[str, Any]]:
    """Uso pratico: faretre, porta pozioni, porta pergamene e mantelli in pelle."""
    character = _locked_character(character_id)
    allowed = int(total(character, "forgia_uso_pratico"))
    if allowed <= 0:
        raise ApiError(
            "forge.no_practical",
            "Ti manca «Uso pratico 1»: non puoi creare oggetti di questo tipo.",
            status=409,
        )
    level = max(1, int(level))
    if level > 1 and allowed < 2:
        raise ApiError(
            "forge.practical_level_locked",
            "«Uso pratico 2» sblocca i livelli oltre il primo.",
            "level",
            409,
        )
    try:
        template = Oggetto.objects.get(pk=blueprint_item_id, archived_at__isnull=True)
    except Oggetto.DoesNotExist as exc:
        raise ApiError("forge.blueprint_not_found", "Oggetto non trovato.", "blueprintItemId", 404) from exc

    leather = PRACTICAL_LEATHER_BASE + PRACTICAL_LEATHER_PER_LEVEL * (level - 1)
    _consume_ingots(character, "pelle", leather)
    instance = create_instance(
        template,
        character,
        kind="forged",
        extra={
            "material": "pelle",
            "materialTier": 1,
            "category": "usoPratico",
            "ingotsSpent": leather,
            "hours": leather,
            "practicalLevel": level,
        },
    )
    slot = store_in_backpack(character, instance)
    return character, {
        "itemId": instance.id,
        "name": instance.nome,
        "leatherSpent": leather,
        "level": level,
        "slot": slot,
        "stored": bool(slot),
    }

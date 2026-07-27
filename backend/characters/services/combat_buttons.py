from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Max

from backend.characters.models import BottoneCombat, Personaggio
from backend.core.api import ApiError


MAX_COMBAT_BUTTONS_PER_CHARACTER = 12
COMBAT_BUTTON_MODIFIER_FIELDS = (
    "bonus_attacco",
    "bonus_danno",
    "bonus_tier",
    "perforazione",
    "perforazione_percentuale",
)


def serialize_combat_button(button: BottoneCombat, *, can_edit: bool) -> dict[str, Any]:
    return {
        "id": button.id,
        "characterId": button.personaggio_id,
        "characterName": button.personaggio.nome if button.personaggio_id else "Personaggio eliminato",
        "name": button.nome,
        "helpText": button.testo_da_mostrare,
        "modifiers": {
            "attackBonus": button.bonus_attacco,
            "damageBonus": button.bonus_danno,
            "damageTierBonus": button.bonus_tier,
            "penetrationFlat": button.perforazione,
            "penetrationPercent": button.perforazione_percentuale,
        },
        "public": button.pubblico,
        "active": button.attivo,
        "keepActiveInCombat": button.tieni_attivo_in_combat,
        "order": button.ordine,
        "canEdit": can_edit,
    }


def combat_button_configuration_payload(character: Personaggio | None) -> dict[str, Any]:
    if character is None:
        return {"limit": MAX_COMBAT_BUTTONS_PER_CHARACTER, "availableSlots": 0, "own": [], "public": []}
    own_rows = list(character.bottoni_combat.select_related("personaggio").all())
    public_rows = list(
        BottoneCombat.objects.filter(pubblico=True)
        .exclude(personaggio=character)
        .select_related("personaggio")
        .order_by("personaggio__nome", "ordine", "id")
    )
    return {
        "limit": MAX_COMBAT_BUTTONS_PER_CHARACTER,
        "availableSlots": max(0, MAX_COMBAT_BUTTONS_PER_CHARACTER - len(own_rows)),
        "own": [serialize_combat_button(button, can_edit=True) for button in own_rows],
        "public": [serialize_combat_button(button, can_edit=False) for button in public_rows],
    }


def active_combat_buttons_payload(character: Personaggio) -> list[dict[str, Any]]:
    return [
        serialize_combat_button(button, can_edit=False)
        for button in character.bottoni_combat.filter(attivo=True).select_related("personaggio")[:MAX_COMBAT_BUTTONS_PER_CHARACTER]
    ]


def _clean_boolean(values: dict[str, Any], key: str, default: bool) -> bool:
    value = values.get(key, default)
    if not isinstance(value, bool):
        raise ApiError("combat_buttons.boolean_required", "Scegli Sì oppure No.", key)
    return value


def _clean_integer(values: dict[str, Any], key: str) -> int:
    try:
        value = int(values.get(key, 0) or 0)
    except (TypeError, ValueError) as error:
        raise ApiError("combat_buttons.integer_required", "Inserisci un modificatore intero valido.", key) from error
    if not -999 <= value <= 999:
        raise ApiError("combat_buttons.modifier_range", "Il modificatore deve essere compreso tra -999 e 999.", key)
    return value


def _clean_values(values: dict[str, Any]) -> dict[str, Any]:
    name = str(values.get("name") or "").strip()
    if not name:
        raise ApiError("combat_buttons.name_required", "Il nome del bottone è obbligatorio.", "name")
    if len(name) > 80:
        raise ApiError("combat_buttons.name_too_long", "Il nome può contenere al massimo 80 caratteri.", "name")
    help_text = str(values.get("helpText") or "").strip()
    if len(help_text) > 1000:
        raise ApiError("combat_buttons.help_too_long", "Il testo da mostrare può contenere al massimo 1000 caratteri.", "helpText")
    modifiers = values.get("modifiers") if isinstance(values.get("modifiers"), dict) else {}
    return {
        "nome": name,
        "testo_da_mostrare": help_text,
        "bonus_attacco": _clean_integer(modifiers, "attackBonus"),
        "bonus_danno": _clean_integer(modifiers, "damageBonus"),
        "bonus_tier": _clean_integer(modifiers, "damageTierBonus"),
        "perforazione": _clean_integer(modifiers, "penetrationFlat"),
        "perforazione_percentuale": _clean_integer(modifiers, "penetrationPercent"),
        "pubblico": _clean_boolean(values, "public", False),
        "attivo": _clean_boolean(values, "active", True),
        "tieni_attivo_in_combat": _clean_boolean(values, "keepActiveInCombat", False),
    }


@transaction.atomic
def create_combat_button(character_id: int, values: dict[str, Any]) -> BottoneCombat:
    try:
        character = Personaggio.objects.select_for_update().get(pk=character_id)
    except Personaggio.DoesNotExist as error:
        raise ApiError("combat_buttons.character_not_found", "Personaggio non trovato.", status=404) from error
    if character.bottoni_combat.count() >= MAX_COMBAT_BUTTONS_PER_CHARACTER:
        raise ApiError(
            "combat_buttons.limit_reached",
            f"Ogni personaggio può configurare al massimo {MAX_COMBAT_BUTTONS_PER_CHARACTER} bottoni combat.",
            status=409,
        )
    order = (character.bottoni_combat.aggregate(max_order=Max("ordine"))["max_order"] or -1) + 1
    button = BottoneCombat(personaggio=character, ordine=order, **_clean_values(values))
    button.full_clean()
    button.save()
    return button


@transaction.atomic
def update_combat_button(character_id: int, button_id: int, values: dict[str, Any]) -> BottoneCombat:
    try:
        button = BottoneCombat.objects.select_for_update().select_related("personaggio").get(
            pk=button_id,
            personaggio_id=character_id,
        )
    except BottoneCombat.DoesNotExist as error:
        raise ApiError("combat_buttons.not_found", "Bottone combat non trovato per questo personaggio.", status=404) from error
    for field, value in _clean_values(values).items():
        setattr(button, field, value)
    button.full_clean()
    button.save()
    return button


@transaction.atomic
def delete_combat_button(character_id: int, button_id: int) -> str:
    try:
        button = BottoneCombat.objects.select_for_update().get(pk=button_id, personaggio_id=character_id)
    except BottoneCombat.DoesNotExist as error:
        raise ApiError("combat_buttons.not_found", "Bottone combat non trovato per questo personaggio.", status=404) from error
    name = button.nome
    button.delete()
    return name


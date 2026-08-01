from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest
from ninja import NinjaAPI
from ninja.security import APIKeyCookie

from backend.characters.models import Personaggio
from backend.characters.race_rules import race_configuration_payload
from backend.characters.competence_selectors import competence_catalog_payload
from backend.characters.alchemy_selectors import alchemy_creation_payload
from backend.characters.note_selectors import character_notes_payload
from backend.characters.selectors import effect_catalog_payload, ordered_personaggi_for, personaggio_detail, serialize_item
from backend.characters.services.commands import adjust_quick_stat, apply_effect, assign_item, recover_mana_from_siphon, rest_character, swap_items, switch_primary_weapon, update_overview, update_resource
from backend.characters.services.inventory_rules import INVENTORY_GROUPS
from backend.characters.services.coins import update_carried_coins, update_shared_coins
from backend.characters.services.extended_inventory import (
    EXTENDED_INVENTORY_GROUPS,
    assign_extended_item,
    set_extended_quantity,
    storage_catalog_payload,
    swap_extended_items,
)
from backend.characters.services.custom_effects import (
    create_custom_effect,
    effect_configuration_payload,
    move_custom_effect,
    remove_custom_or_legacy_effect,
    update_custom_effect,
)
from backend.characters.services.creation import create_personaggio, creation_options_payload
from backend.characters.services.notes import update_note_section
from backend.characters.services.competencies import (
    reroll_competence,
    roll_competence,
    serialized_roll,
    update_competence_extra,
    updated_competence_payload,
    upgrade_competence,
)
from backend.characters.services.alchemy import brew_alchemy, extract_alchemy_reagent
from backend.characters.services.combat_buttons import create_combat_button, delete_combat_button, update_combat_button
from backend.core.api import ApiError
from backend.core.campaigns import (
    reroll_campaign_weather,
    select_campaign,
    update_campaign_clock,
    update_shared_campaign_notes,
)
from backend.core.item_compendium import (
    COMPENDIUM_PAGE_SIZE,
    item_compendium_page,
    item_compendium_reference,
)
from backend.core.item_bulk_services import apply_bulk_items, bulk_field_catalog, preview_bulk_items
from backend.core.item_selectors import item_catalog_payload
from backend.core.item_services import (
    archive_item,
    create_item,
    recheck_items_special,
    save_compared_item,
    set_items_special,
    update_item,
)
from backend.core.management_selectors import character_management_detail, character_management_overview
from backend.core.naming_selectors import name_catalog_payload
from backend.core.naming_services import generate_name
from backend.core.management_services import (
    attach_orphan_record,
    delete_managed_character,
    delete_orphan_record,
    require_game_manager,
    update_managed_character,
)
from backend.core.player_management_selectors import player_management_overview
from backend.core.player_management_services import (
    assign_player_characters,
    create_player,
    require_player_manager,
    set_player_password,
    update_player,
)
from backend.core.game_variable_selectors import game_variables_payload
from backend.core.game_variable_services import (
    require_game_variable_admin,
    save_game_variables,
    validate_game_variables,
)
from backend.core.backup_services import (
    backup_management_overview,
    create_manual_backup,
    delete_backup,
    inspect_backup,
    require_backup_admin,
    save_backup_configuration,
)
from backend.core.models import Giocatore, Skill
from backend.core.theme_selectors import themes_management_payload
from backend.core.theme_services import (
    archive_theme,
    create_theme,
    require_theme_admin,
    save_theme,
    set_default_theme,
)
from backend.lore.selectors import lore_payload
from backend.lore.services import (
    archive_timeline_event as archive_lore_timeline_event,
    delete_event as delete_lore_event,
    delete_faction as delete_lore_faction,
    delete_npc as delete_lore_npc,
    record_event as record_lore_event,
    save_faction as save_lore_faction,
    save_npc as save_lore_npc,
    save_relations as save_lore_relations,
    save_timeline_event as save_lore_timeline_event,
    update_event as update_lore_event,
)
from backend.core.skill_management_selectors import (
    managed_skill_detail,
    serialize_managed_family,
    serialize_managed_group,
    skill_management_overview,
)
from backend.core.skill_management_services import (
    save_skill_family,
    save_skill_group,
    set_managed_skill_archived,
    set_skill_family_archived,
    reorder_skill_structure,
    set_skill_group_archived,
)
from backend.core.security import effective_role, get_or_create_giocatore_for_user, has_minimum_role
from backend.core.skill_selectors import serialize_skill, skill_catalog_payload
from backend.core.skill_services import (
    archive_skill,
    configure_character_actions,
    create_skill,
    delete_skill,
    preview_skill_unlock,
    reorder_skills,
    unlock_skill,
    update_character_xp,
    update_skill,
)
from backend.core.spell_services import preview_spell_cast
from backend.core.views import get_authenticated_user
from backend.dice_tools.selectors import dice_history_payload, dice_sets_payload, serialize_dice_set
from backend.dice_tools.services import (
    archive_dice_set,
    create_dice_set,
    duplicate_dice_set,
    purge_dice_history,
    record_competence_dice_roll,
    record_quick_dice_roll,
    roll_dice,
    update_dice_set,
)
from backend.combat.unit_management_selectors import (
    serialize_managed_unit,
    unit_management_overview,
    unit_option_search,
)
from backend.combat.unit_management_services import (
    managed_unit_detail,
    preview_managed_unit,
    require_unit_manager,
    save_managed_unit,
    set_managed_unit_archived,
)
from backend.combat.damage_rule_management import (
    damage_rules_payload,
    save_damage_rules,
    validate_damage_rules,
)
from backend.market.selectors import management_overview as market_management_overview, market_overview
from backend.market.services import (
    create_batch as create_market_batch,
    preview_batch as preview_market_batch,
    preview_generation as preview_market_generation,
    purchase as purchase_from_market,
    quote_purchase as quote_market_purchase,
    regenerate_shop as regenerate_market_shop,
    save_market_settings,
    save_shop as save_market_shop,
    set_shop_state as set_market_shop_state,
)

from .schemas import ActionEnvelopeResponseSchema, ActionEnvelopeSchema, AlchemyCreationEnvelopeSchema, CharacterNotesEnvelopeSchema, CharacterSheetEnvelopeSchema, CompetenceCatalogEnvelopeSchema, DiceHistoryEnvelopeSchema, DiceSetsEnvelopeSchema, ErrorEnvelopeSchema, ItemCatalogEnvelopeSchema, ItemCompendiumPageEnvelopeSchema, ItemCompendiumReferenceEnvelopeSchema, LoreEnvelopeSchema, ManagementEnvelopeSchema, MarketEnvelopeSchema, NameCatalogEnvelopeSchema, SkillCatalogEnvelopeSchema


class SessionCookieAuth(APIKeyCookie):
    param_name = settings.SESSION_COOKIE_NAME

    def authenticate(self, request: HttpRequest, key: str | None):
        return request.user if request.user.is_authenticated else None


api = NinjaAPI(
    title="ReDjango API",
    version="1.0.0",
    description="Contratti tipizzati per la SPA ReDjango.",
    urls_namespace="api-v1",
    auth=SessionCookieAuth(csrf=True),
)


def _request_id(request: HttpRequest, fallback: str = "") -> str:
    return request.headers.get("X-ReDjango-Request-Id", "") or fallback


def _envelope(request: HttpRequest, data: dict[str, Any], *, request_id: str = "", events=None, warnings=None):
    return {"ok": True, "requestId": _request_id(request, request_id), "data": data, "events": events or [], "warnings": warnings or [], "errors": []}


def _error_envelope(request: HttpRequest, error: ApiError, *, request_id: str = ""):
    payload = {"code": error.code, "message": error.message}
    if error.field:
        payload["field"] = error.field
    return api.create_response(request, {"ok": False, "requestId": _request_id(request, request_id), "data": {}, "events": [], "warnings": [], "errors": [payload]}, status=error.status)


@api.exception_handler(ApiError)
def api_error_handler(request: HttpRequest, error: ApiError):
    return _error_envelope(request, error)


def _identity(request: HttpRequest):
    user = get_authenticated_user(request)
    return user, get_or_create_giocatore_for_user(user)


def _can_manage_items(user, giocatore: Giocatore) -> bool:
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)


def _can_control_all_characters(user, giocatore: Giocatore) -> bool:
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)


def _can_manage_dice_sets(user, giocatore: Giocatore) -> bool:
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_ADMIN)


def _can_manage_skills(user, giocatore: Giocatore) -> bool:
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_ADMIN)


def _can_delete_skills(user, giocatore: Giocatore) -> bool:
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_ADMIN)


def _can_bypass_skill_prerequisites(user, giocatore: Giocatore) -> bool:
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)


def _allowed_character(user, giocatore: Giocatore, character_id: int) -> Personaggio:
    allowed_ids = {
        personaggio.id
        for personaggio in ordered_personaggi_for(
            giocatore,
            include_all=_can_control_all_characters(user, giocatore),
        )
    }
    if character_id not in allowed_ids:
        raise ApiError("character.not_available", "Questo personaggio non è disponibile.", status=404)
    try:
        return (
            Personaggio.objects.select_related(
                "equip", "zaino", "faretra", "note", "effetti"
            )
            .prefetch_related(
                "effetti_personalizzati__operazioni",
                "skill_sbloccate__skill__famiglia",
                "skill_sbloccate__skill__prerequisiti",
            )
            .get(pk=character_id)
        )
    except Personaggio.DoesNotExist as exc:
        raise ApiError("character.not_found", "Personaggio non trovato.", status=404) from exc


def _sheet_data(user, giocatore: Giocatore, character_id: int) -> dict[str, Any]:
    character = _allowed_character(user, giocatore, character_id)
    return {
        "character": _character_sheet_payload(character, user, giocatore),
        "effectCatalog": effect_catalog_payload(),
        "effectConfiguration": effect_configuration_payload(),
        "raceConfiguration": race_configuration_payload(),
        "storageCatalog": storage_catalog_payload(),
    }


def _character_sheet_payload(
    character: Personaggio,
    user,
    giocatore: Giocatore,
) -> dict[str, Any]:
    return personaggio_detail(
        character,
        can_manage_items=_can_manage_items(user, giocatore),
        include_skills=False,
    ) or {}


@api.get("/characters/{character_id}/sheet", response={200: CharacterSheetEnvelopeSchema, 404: ErrorEnvelopeSchema}, tags=["characters"])
def character_sheet(request: HttpRequest, character_id: int):
    user, giocatore = _identity(request)
    return _envelope(request, _sheet_data(user, giocatore, character_id))


@api.get("/characters/creation-options", response={200: ManagementEnvelopeSchema}, tags=["characters"])
def character_creation_options(request: HttpRequest):
    """Cataloghi della procedura "Nuovo PG": razze, sottorazze, caratteristiche, quota."""
    _user, giocatore = _identity(request)
    return _envelope(request, creation_options_payload(giocatore))


@api.get("/items", response={200: ItemCatalogEnvelopeSchema}, tags=["items"])
def items(
    request: HttpRequest,
    query: str = "",
    include_archived: bool = False,
    limit: int = 100,
    type_1: str = "",
    type_2: str = "",
    type_3: str = "",
    rarity: int | None = None,
    weapon_type_id: int | None = None,
    group: str = "",
    slot: str = "",
):
    user, giocatore = _identity(request)
    include_archived = bool(include_archived and _can_manage_items(user, giocatore))
    if group and group not in INVENTORY_GROUPS:
        raise ApiError("items.group_not_found", "Il contenitore scelto non esiste.", status=400)
    return _envelope(request, item_catalog_payload(
        query.strip(),
        include_archived=include_archived,
        limit=limit,
        type_1=type_1.strip(),
        type_2=type_2.strip(),
        type_3=type_3.strip(),
        rarity=rarity,
        weapon_type_id=weapon_type_id,
        group=group,
        slot=slot.strip(),
    ))


@api.get(
    "/compendium/items/reference",
    response={200: ItemCompendiumReferenceEnvelopeSchema},
    tags=["compendium"],
)
def compendium_reference(request: HttpRequest):
    """Filter vocabulary and connected rules for the "Oggetti" guide.

    Readable by every authenticated player: the compendium is game knowledge,
    not campaign information, so it carries no per-character or hidden data.
    """
    _identity(request)
    return _envelope(request, item_compendium_reference())


@api.get(
    "/compendium/items",
    response={200: ItemCompendiumPageEnvelopeSchema},
    tags=["compendium"],
)
def compendium_items(
    request: HttpRequest,
    query: str = "",
    limit: int = COMPENDIUM_PAGE_SIZE,
    offset: int = 0,
    type_1: str = "",
    type_2: str = "",
    type_3: str = "",
    type_4: str = "",
    rarity: int | None = None,
    weapon_category: str = "",
    region: str = "",
    loot_level: int | None = None,
    weight_min: float | None = None,
    weight_max: float | None = None,
    value_min: int | None = None,
    value_max: int | None = None,
    with_effects: bool = False,
    sort: str = "",
):
    _identity(request)
    return _envelope(
        request,
        item_compendium_page(
            query.strip(),
            limit=limit,
            offset=offset,
            type_1=type_1.strip(),
            type_2=type_2.strip(),
            type_3=type_3.strip(),
            type_4=type_4.strip(),
            rarity=rarity,
            weapon_category=weapon_category.strip(),
            region=region.strip(),
            loot_level=loot_level,
            weight_min=weight_min,
            weight_max=weight_max,
            value_min=value_min,
            value_max=value_max,
            with_effects=with_effects,
            sort=sort.strip(),
        ),
    )


@api.get("/market", response={200: MarketEnvelopeSchema}, tags=["market"])
def market(request: HttpRequest, selected_shop_id: int | None = None, character_id: int | None = None, include_archived: bool = False):
    user, giocatore = _identity(request)
    if character_id is not None:
        _allowed_character(user, giocatore, character_id)
    return _envelope(request, market_overview(giocatore, selected_shop_id=selected_shop_id, character_id=character_id, include_archived=include_archived))


@api.get("/market/shops/{shop_id}", response={200: MarketEnvelopeSchema, 404: ErrorEnvelopeSchema}, tags=["market"])
def market_shop(request: HttpRequest, shop_id: int, character_id: int | None = None):
    user, giocatore = _identity(request)
    if character_id is not None:
        _allowed_character(user, giocatore, character_id)
    payload = market_overview(giocatore, selected_shop_id=shop_id, character_id=character_id)
    if payload["selectedShop"] is None:
        raise ApiError("market.shop_not_found", "Negozio non trovato.", status=404)
    return _envelope(request, payload)


@api.get("/lore", response={200: LoreEnvelopeSchema}, tags=["lore"])
def lore(request: HttpRequest):
    user, giocatore = _identity(request)
    return _envelope(request, lore_payload(user, giocatore))


@api.get("/names", response={200: NameCatalogEnvelopeSchema}, tags=["names"])
def names(request: HttpRequest):
    """Catalogo dei bacini di nomi: nessun provider AI è richiesto per leggerlo."""

    _identity(request)
    return _envelope(request, name_catalog_payload())


@api.get("/management/shops", response={200: MarketEnvelopeSchema, 403: ErrorEnvelopeSchema}, tags=["management"])
def managed_shops(request: HttpRequest):
    user, giocatore = _identity(request)
    require_game_manager(user, giocatore)
    return _envelope(request, market_management_overview(giocatore))


@api.get(
    "/management/items",
    response={200: ItemCatalogEnvelopeSchema, 403: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_items(
    request: HttpRequest,
    query: str = "",
    limit: int = 100,
    offset: int = 0,
    type_1: str = "",
    type_2: str = "",
    type_3: str = "",
    region: str = "",
    state: str = "",
    special: str = "",
    rarity: int | None = None,
    weapon_type_id: int | None = None,
    weight_min: float | None = None,
    weight_max: float | None = None,
    value_min: int | None = None,
    value_max: int | None = None,
    sort: str = "",
):
    user, giocatore = _identity(request)
    require_game_manager(user, giocatore)
    return _envelope(
        request,
        item_catalog_payload(
            query.strip(),
            include_archived=True,
            limit=limit,
            offset=offset,
            type_1=type_1.strip(),
            type_2=type_2.strip(),
            type_3=type_3.strip(),
            region=region.strip(),
            state=state.strip(),
            special=None if special not in {"special", "standard"} else special == "special",
            rarity=rarity,
            weapon_type_id=weapon_type_id,
            weight_min=weight_min,
            weight_max=weight_max,
            value_min=value_min,
            value_max=value_max,
            sort=sort.strip(),
        ),
    )


@api.get(
    "/management/items/bulk-fields",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_item_bulk_fields(request: HttpRequest):
    """Field, operator and choice metadata for the batch editor.

    Served instead of hard-coded in the client so the item types, weapon types
    and rarities offered by the batch editor are always the ones the catalogue
    actually accepts.
    """
    user, giocatore = _identity(request)
    require_game_manager(user, giocatore)
    return _envelope(request, bulk_field_catalog())


@api.get(
    "/management/characters",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_characters(request: HttpRequest, query: str = "", orphan_kind: str = "", campaign: str = ""):
    user, giocatore = _identity(request)
    require_game_manager(user, giocatore)
    return _envelope(request, character_management_overview(query.strip(), orphan_kind.strip(), campaign.strip()))


@api.get(
    "/management/characters/{character_id}",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema, 404: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_character_detail(request: HttpRequest, character_id: int):
    user, giocatore = _identity(request)
    require_game_manager(user, giocatore)
    try:
        return _envelope(request, character_management_detail(character_id))
    except Personaggio.DoesNotExist as exc:
        raise ApiError("management.character_not_found", "Personaggio non trovato.", status=404) from exc


@api.get(
    "/management/players",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_players(request: HttpRequest):
    user, giocatore = _identity(request)
    require_player_manager(user, giocatore)
    return _envelope(request, player_management_overview(giocatore))


@api.get(
    "/management/skills",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_skills(
    request: HttpRequest,
    query: str = "",
    group_id: int = 0,
    family_id: int = 0,
    state: str = "",
    kind: str = "",
    offset: int = 0,
    limit: int = 100,
):
    user, giocatore = _identity(request)
    require_game_manager(user, giocatore)
    return _envelope(request, skill_management_overview(
        query.strip(),
        group_id=group_id or None,
        family_id=family_id or None,
        state=state.strip(),
        kind=kind.strip(),
        offset=offset,
        limit=limit,
    ))


@api.get(
    "/management/skills/{skill_id}",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema, 404: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_skill(request: HttpRequest, skill_id: int):
    user, giocatore = _identity(request)
    require_game_manager(user, giocatore)
    try:
        return _envelope(request, managed_skill_detail(skill_id))
    except Skill.DoesNotExist as exc:
        raise ApiError("skills.not_found", "Abilità non trovata.", status=404) from exc


@api.get(
    "/management/units",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_units(request: HttpRequest):
    user, giocatore = _identity(request)
    require_unit_manager(user, giocatore)
    return _envelope(request, unit_management_overview())


@api.get(
    "/management/units/options",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_unit_options(request: HttpRequest, kind: str, query: str = "", limit: int = 80):
    user, giocatore = _identity(request)
    require_unit_manager(user, giocatore)
    if kind not in {"item", "skill"}:
        raise ApiError(
            "management.units.option_kind_invalid",
            "Puoi cercare soltanto Skill oppure oggetti.",
            "kind",
        )
    return _envelope(request, unit_option_search(kind, query, limit))


@api.get(
    "/management/units/{unit_id}",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema, 404: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_unit(request: HttpRequest, unit_id: int):
    user, giocatore = _identity(request)
    require_unit_manager(user, giocatore)
    return _envelope(request, managed_unit_detail(unit_id))


@api.get(
    "/management/game-variables",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_game_variables(request: HttpRequest):
    user, giocatore = _identity(request)
    require_game_variable_admin(user, giocatore)
    return _envelope(request, game_variables_payload())


@api.get(
    "/management/backups",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_backups(request: HttpRequest):
    user, giocatore = _identity(request)
    require_backup_admin(user, giocatore)
    return _envelope(request, backup_management_overview())


@api.get(
    "/management/themes",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_themes(request: HttpRequest):
    user, giocatore = _identity(request)
    require_theme_admin(user, giocatore)
    return _envelope(request, themes_management_payload())


@api.get(
    "/management/damage-rules",
    response={200: ManagementEnvelopeSchema, 403: ErrorEnvelopeSchema},
    tags=["management"],
)
def managed_damage_rules(request: HttpRequest):
    user, giocatore = _identity(request)
    require_game_variable_admin(user, giocatore)
    return _envelope(request, damage_rules_payload())


@api.get("/dice-sets", response={200: DiceSetsEnvelopeSchema}, tags=["dice"])
def dice_sets(request: HttpRequest, include_inactive: bool = False):
    user, giocatore = _identity(request)
    return _envelope(request, dice_sets_payload(include_inactive=bool(include_inactive and _can_manage_dice_sets(user, giocatore))))


@api.get(
    "/dice-history",
    response={200: DiceHistoryEnvelopeSchema, 403: ErrorEnvelopeSchema},
    tags=["dice"],
)
def dice_history(
    request: HttpRequest,
    player: str = "",
    character_id: int = 0,
    source: str = "",
    since_days: int = 0,
    limit: int = 100,
    offset: int = 0,
    statistics: bool = False,
):
    user, giocatore = _identity(request)
    return _envelope(request, dice_history_payload(
        user, giocatore,
        player=player.strip(),
        character_id=character_id or None,
        source=source.strip(),
        since_days=since_days,
        limit=limit,
        offset=offset,
        include_statistics=statistics,
    ))


@api.get("/characters/{character_id}/notes", response={200: CharacterNotesEnvelopeSchema, 404: ErrorEnvelopeSchema}, tags=["notes"])
def character_notes(request: HttpRequest, character_id: int):
    user, giocatore = _identity(request)
    character = _allowed_character(user, giocatore, character_id)
    return _envelope(request, character_notes_payload(character))


@api.get(
    "/characters/{character_id}/creation",
    response={200: AlchemyCreationEnvelopeSchema, 404: ErrorEnvelopeSchema},
    tags=["creation"],
)
def character_creation(request: HttpRequest, character_id: int):
    user, giocatore = _identity(request)
    character = _allowed_character(user, giocatore, character_id)
    return _envelope(request, alchemy_creation_payload(character))


@api.get(
    "/characters/{character_id}/competencies",
    response={200: CompetenceCatalogEnvelopeSchema, 404: ErrorEnvelopeSchema},
    tags=["competencies"],
)
def character_competencies(request: HttpRequest, character_id: int):
    user, giocatore = _identity(request)
    character = _allowed_character(user, giocatore, character_id)
    return _envelope(request, competence_catalog_payload(character))


@api.get(
    "/skills",
    response={200: SkillCatalogEnvelopeSchema, 404: ErrorEnvelopeSchema},
    tags=["skills"],
)
def skills(
    request: HttpRequest,
    character_id: int | None = None,
    group: str = "",
    family_id: int | None = None,
    query: str = "",
    search_mode: bool = False,
    name_query: str = "",
    card_query: str = "",
    filter_group: str = "",
    filter_family_id: int | None = None,
    effect_target: str = "",
    unlock_status: str = "",
    include_archived: bool = False,
    owned_only: bool = False,
):
    user, giocatore = _identity(request)
    selected_character_id = character_id or giocatore.active_character_id
    character = _allowed_character(user, giocatore, selected_character_id) if selected_character_id else None
    can_manage = _can_manage_skills(user, giocatore)
    return _envelope(
        request,
        skill_catalog_payload(
            character,
            group=group,
            family_id=family_id,
            query=query,
            search_mode=search_mode,
            name_query=name_query,
            card_query=card_query,
            filter_group=filter_group,
            filter_family_id=filter_family_id,
            effect_target=effect_target,
            unlock_status=unlock_status,
            include_archived=bool(include_archived and can_manage),
            owned_only=owned_only,
            can_manage=can_manage,
            can_delete=_can_delete_skills(user, giocatore),
            bypass_prerequisites=_can_bypass_skill_prerequisites(user, giocatore),
        ),
    )


@api.post(
    "/actions",
    response={200: ActionEnvelopeResponseSchema, 400: ErrorEnvelopeSchema, 403: ErrorEnvelopeSchema, 404: ErrorEnvelopeSchema, 409: ErrorEnvelopeSchema},
    tags=["actions"],
)
def actions(request: HttpRequest, command: ActionEnvelopeSchema):
    user, giocatore = _identity(request)
    action = command.action
    payload = command.payload.model_dump()
    request_id = command.requestId
    warnings: list[dict[str, str]] = []
    try:
        if (
            payload.get("characterId") is not None
            and not action.startswith("management.characters.")
            and action != "management.backups.inspect"
        ):
            _allowed_character(user, giocatore, int(payload["characterId"]))

        if action == "inventory.swapItems":
            groups = {payload["source"]["group"], payload["target"]["group"]}
            character = (
                swap_extended_items(payload["characterId"], payload["source"], payload["target"])
                if groups & EXTENDED_INVENTORY_GROUPS
                else swap_items(payload["characterId"], payload["source"], payload["target"])
            )
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Oggetti scambiati."
        elif action == "inventory.assignItem":
            if payload["target"]["group"] in EXTENDED_INVENTORY_GROUPS:
                character = assign_extended_item(
                    payload["characterId"],
                    payload["target"],
                    item_id=payload.get("itemId"),
                    stock_key=payload.get("stockKey", ""),
                    quantity=payload.get("quantity", 1),
                )
                data = {"character": _character_sheet_payload(character, user, giocatore)}
                message = (
                    "Spazio svuotato."
                    if payload.get("itemId") is None and not payload.get("stockKey")
                    else "Elemento inserito nel contenitore."
                )
            else:
                assignment = assign_item(payload["characterId"], payload["target"], payload.get("itemId"))
                character = assignment.personaggio
                data = {"character": _character_sheet_payload(character, user, giocatore)}
                if assignment.assigned_item is None:
                    message = "Spazio svuotato."
                elif assignment.replaced_item_lost and assignment.replaced_item:
                    message = f"{assignment.assigned_item.nome} inserito."
                    warnings.append({
                        "code": "inventory.displaced_item_lost",
                        "message": (
                            f"{message} Lo zaino non ha spazi liberi: "
                            f"{assignment.replaced_item.nome} è stato perso."
                        ),
                    })
                elif assignment.backpack_slot_locked and assignment.replaced_item:
                    message = (
                        f"{assignment.assigned_item.nome} inserito. {assignment.replaced_item.nome} "
                        f"è stato spostato nello spazio bloccato {assignment.backpack_slot} dello zaino."
                    )
                elif assignment.backpack_slot and assignment.replaced_item:
                    message = (
                        f"{assignment.assigned_item.nome} inserito. {assignment.replaced_item.nome} "
                        f"è stato spostato nello spazio {assignment.backpack_slot} dello zaino."
                    )
                else:
                    message = f"{assignment.assigned_item.nome} inserito."
        elif action == "inventory.setQuantity":
            character = set_extended_quantity(
                payload["characterId"],
                payload["target"],
                payload["quantity"],
            )
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Quantità aggiornata."
        elif action == "equipment.switchPrimaryWeapon":
            character = switch_primary_weapon(payload["characterId"])
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Arma primaria cambiata senza spendere Punti Azione."
        elif action == "character.updateResource":
            character = update_resource(payload["characterId"], payload["resource"], payload["current"])
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Risorsa aggiornata."
        elif action == "character.recoverManaSiphon":
            character = recover_mana_from_siphon(payload["characterId"])
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Mana recuperato dal sifone."
        elif action == "character.adjustQuickStat":
            character = adjust_quick_stat(payload["characterId"], payload["stat"], payload["delta"])
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Valore aggiornato."
        elif action == "character.rest":
            character = rest_character(payload["characterId"], payload["fatigueRecovery"])
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Riposo completato."
        elif action == "character.updateOverview":
            character = update_overview(payload["characterId"], payload["values"])
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Personaggio aggiornato."
        elif action == "characters.create":
            character = create_personaggio(giocatore, payload)
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            # Formulazione neutra: il messaggio vale per qualunque sesso scelto.
            message = f"{character.nome} entra in gioco."
        elif action == "character.updateCoins":
            result = update_carried_coins(
                payload["characterId"],
                payload["coins"],
                transfer_overflow=payload.get("transferOverflow", False),
                expected_coins=payload.get("expectedCoins"),
                expected_shared_coins=payload.get("expectedSharedCoins"),
            )
            character = result.character
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = (
                f"{result.transferred} monete trasferite alle risorse condivise."
                if result.transferred
                else "Monete trasportate aggiornate."
            )
        elif action == "campaign.updateSharedCoins":
            character = update_shared_coins(
                payload["characterId"],
                payload["coins"],
                expected_coins=payload.get("expectedCoins"),
            )
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Monete condivise aggiornate."
        elif action == "effects.apply":
            character = apply_effect(payload["characterId"], payload["effectId"])
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Effetto applicato."
        elif action == "effects.remove":
            character = remove_custom_or_legacy_effect(
                payload["characterId"],
                effect_id=payload.get("effectId"),
                legacy_slot=payload.get("slot"),
            )
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Effetto rimosso."
        elif action == "effects.create":
            character = create_custom_effect(payload["characterId"], payload["values"])
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Effetto creato e applicato."
        elif action == "effects.update":
            character = update_custom_effect(
                payload["characterId"],
                payload["values"],
                effect_id=payload.get("effectId"),
                legacy_slot=payload.get("legacySlot"),
            )
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Effetto aggiornato."
        elif action == "effects.move":
            character = move_custom_effect(
                payload["characterId"],
                payload["effectId"],
                payload["direction"],
            )
            data = {"character": _character_sheet_payload(character, user, giocatore)}
            message = "Ordine degli effetti aggiornato."
        elif action == "items.create":
            item = create_item(user, giocatore, payload["values"])
            data = {"item": serialize_item(item, detailed=True), "catalog": item_catalog_payload(include_archived=True)}
            message = "Oggetto creato."
        elif action == "items.update":
            item_id = payload.get("itemId")
            if not item_id:
                raise ApiError("items.id_required", "Scegli l'oggetto da modificare.", "itemId")
            item = update_item(user, giocatore, item_id, payload["values"])
            data = {"item": serialize_item(item, detailed=True), "catalog": item_catalog_payload(include_archived=True)}
            message = "Oggetto aggiornato."
        elif action == "items.archive":
            item = archive_item(user, giocatore, payload["itemId"])
            data = {"item": serialize_item(item, detailed=True), "catalog": item_catalog_payload(include_archived=True)}
            message = "Oggetto archiviato."
        elif action == "items.setSpecial":
            updated = set_items_special(user, giocatore, payload.get("itemIds", []), bool(payload.get("special")))
            data = {"management": {"updated": updated}}
            message = f"{updated} oggetti aggiornati."
        elif action == "items.recheckSpecial":
            result = recheck_items_special(user, giocatore, payload.get("itemIds", []))
            data = {"management": result}
            message = f"{result['cleared']} oggetti non sono più Speciali, {result['stillSpecial']} hanno ancora un motivo aperto."
        elif action == "items.bulkPreview":
            preview = preview_bulk_items(
                user,
                giocatore,
                payload.get("filters", []),
                payload.get("actions", []),
                limit=payload.get("limit", 25),
            )
            data = {"management": {"bulkPreview": preview}}
            message = (
                f"{preview['changed']} oggetti su {preview['total']} cambierebbero."
                if preview["changed"]
                else "Nessun oggetto cambierebbe con questi filtri."
            )
        elif action == "items.bulkApply":
            result = apply_bulk_items(
                user,
                giocatore,
                payload.get("filters", []),
                payload.get("actions", []),
                payload.get("token", ""),
            )
            data = {"management": {"bulkApply": result}, "catalog": item_catalog_payload(include_archived=True)}
            message = f"{result['updated']} oggetti aggiornati su {result['matched']} selezionati."
        elif action == "items.compareSave":
            item, created = save_compared_item(
                user,
                giocatore,
                payload.get("itemId"),
                payload.get("identityName", ""),
                payload["values"],
            )
            data = {
                "item": serialize_item(item, detailed=True),
                "catalog": item_catalog_payload(include_archived=True, limit=1000),
                "management": {"created": created},
            }
            message = "Nuovo oggetto creato dal confronto." if created else "Oggetto aggiornato dal confronto."
        elif action == "management.characters.update":
            detail = update_managed_character(
                user,
                giocatore,
                payload["characterId"],
                payload.get("profile", {}),
                payload.get("relations", {}),
            )
            data = {"management": detail}
            message = "Personaggio e record collegati aggiornati."
        elif action == "management.characters.attach":
            detail = attach_orphan_record(
                user,
                giocatore,
                payload["characterId"],
                payload["kind"],
                payload["recordId"],
            )
            data = {"management": detail}
            message = "Record orfano collegato al personaggio."
        elif action == "management.characters.deleteOrphan":
            removed = delete_orphan_record(user, giocatore, payload["kind"], payload["recordId"])
            data = {"management": character_management_overview()}
            message = f"{removed['label']} «{removed['name']}» eliminato."
        elif action == "management.characters.delete":
            character_name = delete_managed_character(
                user,
                giocatore,
                payload["characterId"],
                payload["previewToken"],
            )
            data = {"management": character_management_overview()}
            message = f"{character_name} e i record evidenziati sono stati eliminati."
        elif action == "management.players.create":
            result = create_player(user, giocatore, payload.get("values", {}))
            data = {"management": result["overview"]}
            message = f"Giocatore {result['playerName']} creato."
        elif action == "management.players.update":
            result = update_player(user, giocatore, payload["playerId"], payload.get("values", {}))
            data = {"management": result["overview"]}
            message = f"Giocatore {result['playerName']} aggiornato."
        elif action == "management.players.setPassword":
            result = set_player_password(user, giocatore, payload["playerId"], payload.get("password"))
            data = {"management": result["overview"]}
            message = f"Password di {result['playerName']} aggiornata."
        elif action == "management.players.assignCharacters":
            result = assign_player_characters(user, giocatore, payload["playerId"], payload.get("characterIds") or [])
            data = {"management": result["overview"]}
            message = (
                f"{result['assignedCount']} personaggi assegnati a {result['playerName']}."
                if result["assignedCount"]
                else f"{result['playerName']} non ha più personaggi assegnati."
            )
        elif action == "management.skills.group.save":
            group = save_skill_group(user, giocatore, payload.get("values", {}), payload.get("groupId"))
            data = {"management": {"group": serialize_managed_group(group)}}
            message = f"Gruppo {group.nome} salvato."
        elif action == "management.skills.group.state":
            group = set_skill_group_archived(user, giocatore, payload["groupId"], payload["archived"])
            data = {"management": {"group": serialize_managed_group(group)}}
            message = f"Gruppo {group.nome} {'archiviato' if payload['archived'] else 'ripristinato'}."
        elif action == "management.skills.family.save":
            family = save_skill_family(user, giocatore, payload.get("values", {}), payload.get("familyId"))
            data = {"management": {"family": serialize_managed_family(family)}}
            message = f"Famiglia {family.nome} salvata."
        elif action == "management.skills.family.state":
            family = set_skill_family_archived(user, giocatore, payload["familyId"], payload["archived"])
            data = {"management": {"family": serialize_managed_family(family)}}
            message = f"Famiglia {family.nome} {'archiviata' if payload['archived'] else 'ripristinata'}."
        elif action == "management.skills.structure.reorder":
            touched = reorder_skill_structure(user, giocatore, payload.get("groups"), payload.get("families"))
            data = {"management": {"reordered": touched}}
            message = f"Ordine aggiornato: {touched['groups']} gruppi, {touched['families']} famiglie."
        elif action == "management.skills.skill.state":
            skill = set_managed_skill_archived(user, giocatore, payload["skillId"], payload["archived"])
            data = {"skill": serialize_skill(skill)}
            message = f"Abilità {skill.nome} {'archiviata' if payload['archived'] else 'ripristinata'}."
        elif action == "management.units.save":
            unit, created = save_managed_unit(
                user,
                giocatore,
                payload.get("values", {}),
                payload.get("unitId"),
            )
            data = {
                "management": {
                    "unit": serialize_managed_unit(unit),
                    "overview": unit_management_overview(),
                    "created": created,
                }
            }
            message = f"Unit {unit.nome} {'creata' if created else 'aggiornata'}."
        elif action == "management.units.state":
            unit = set_managed_unit_archived(
                user,
                giocatore,
                payload["unitId"],
                payload["archived"],
            )
            data = {
                "management": {
                    "unit": serialize_managed_unit(unit),
                    "overview": unit_management_overview(),
                }
            }
            message = f"Unit {unit.nome} {'archiviata' if payload['archived'] else 'ripristinata'}."
        elif action == "management.units.preview":
            data = {
                "management": {
                    "preview": preview_managed_unit(
                        user,
                        giocatore,
                        payload["unitId"],
                        payload.get("level", 1),
                        payload.get("variant", "standard"),
                    )
                }
            }
            message = "Anteprima Unit generata senza creare un personaggio."
        elif action == "management.themes.save":
            data = {"management": save_theme(user, giocatore, payload.get("themeId"), payload.get("theme", {}))}
            message = "Tema salvato."
        elif action == "management.themes.create":
            data = {"management": create_theme(user, giocatore, payload.get("theme", {}))}
            message = "Tema creato."
        elif action == "management.themes.setDefault":
            data = {"management": set_default_theme(user, giocatore, payload.get("themeId"))}
            message = "Tema predefinito aggiornato."
        elif action == "management.themes.archive":
            data = {"management": archive_theme(user, giocatore, payload.get("themeId"))}
            message = "Tema archiviato."
        elif action == "management.variables.validate":
            data = {
                "management": {
                    "validation": validate_game_variables(
                        user,
                        giocatore,
                        payload.get("values", {}),
                    )
                }
            }
            message = "Variabili validate senza modificare il database."
        elif action == "management.variables.save":
            data = {
                "management": {
                    "variables": save_game_variables(
                        user,
                        giocatore,
                        payload.get("values", {}),
                        payload.get("previewToken", ""),
                    )
                }
            }
            message = "Variabili di gioco salvate."
        elif action == "management.backups.saveSettings":
            data = {
                "management": save_backup_configuration(
                    user,
                    giocatore,
                    payload.get("configuration", {}),
                )
            }
            message = "Configurazione backup salvata."
        elif action == "management.backups.create":
            backup = create_manual_backup(user, giocatore, payload.get("label", ""))
            data = {"management": backup_management_overview(created_backup_id=backup["id"])}
            message = "Backup creato."
        elif action == "management.backups.delete":
            delete_backup(user, giocatore, payload["backupId"])
            data = {"management": backup_management_overview()}
            message = "Backup eliminato."
        elif action == "management.backups.inspect":
            require_backup_admin(user, giocatore)
            data = {
                "management": {
                    **backup_management_overview(),
                    "inspection": inspect_backup(payload["backupId"], payload.get("characterId")),
                }
            }
            message = "Backup aperto in sola lettura."
        elif action == "management.damageRules.validate":
            data = {
                "management": {
                    "validation": validate_damage_rules(
                        user,
                        giocatore,
                        payload.get("rules", {}),
                    )
                }
            }
            message = "Regole del danno validate senza modificare il database."
        elif action == "management.damageRules.save":
            data = {
                "management": {
                    "damageRules": save_damage_rules(
                        user,
                        giocatore,
                        payload.get("rules", {}),
                        payload.get("previewToken", ""),
                    )
                }
            }
            message = "Regole del danno salvate."
        elif action == "dice.roll":
            dice_roll = roll_dice(payload)
            character = (
                _allowed_character(user, giocatore, int(payload["characterId"]))
                if payload.get("characterId")
                else None
            )
            record_quick_dice_roll(giocatore, character, dice_roll)
            data = {"diceRoll": dice_roll}
            message = f"Tiro {dice_roll['notation']}: {dice_roll['total']}."
        elif action == "diceSets.create":
            dice_set = create_dice_set(user, giocatore, payload["values"])
            data = {"diceSets": dice_sets_payload(include_inactive=True)}
            message = f"Set {dice_set.name} creato."
        elif action == "diceSets.update":
            dice_set = update_dice_set(user, giocatore, payload["diceSetId"], payload["values"])
            data = {"diceSets": dice_sets_payload(include_inactive=True)}
            message = f"Set {dice_set.name} aggiornato."
        elif action == "diceSets.archive":
            dice_set = archive_dice_set(user, giocatore, payload["diceSetId"])
            data = {"diceSets": dice_sets_payload(include_inactive=True)}
            message = f"Set {dice_set.name} archiviato."
        elif action == "diceSets.duplicate":
            dice_set = duplicate_dice_set(user, giocatore, payload["diceSetId"])
            data = {"diceSets": dice_sets_payload(include_inactive=True)}
            message = f"Set {dice_set.name} creato come copia."
        elif action == "diceHistory.purge":
            archived = purge_dice_history(user, giocatore, older_than_days=payload.get("olderThanDays", 30))
            data = {"management": {"archived": archived}}
            message = f"{archived} tiri archiviati."
        elif action == "notes.updateSection":
            character = update_note_section(payload["characterId"], payload["section"], payload["content"])
            data = {"notes": character_notes_payload(character)}
            message = "Note salvate."
        elif action == "campaign.select":
            if not _can_control_all_characters(user, giocatore):
                raise ApiError(
                    "campaign.forbidden",
                    "Solo Master e Amministratori possono cambiare la campagna attiva.",
                    status=403,
                )
            data = {"campaigns": select_campaign(giocatore, payload["campaignId"])}
            message = "Campagna selezionata."
        elif action == "campaign.notes.update":
            data = {
                "campaigns": update_shared_campaign_notes(
                    giocatore,
                    payload["campaignId"],
                    payload["content"],
                )
            }
            message = "Note condivise salvate."
        elif action == "campaign.clock.update":
            campaigns, weather_reminder = update_campaign_clock(
                user,
                giocatore,
                payload["campaignId"],
                payload["field"],
                payload["direction"],
            )
            data = {"campaigns": campaigns, "weatherReminder": weather_reminder}
            message = "Ora della campagna aggiornata." if payload["field"] == "ora" else "Giorno della campagna aggiornato."
        elif action == "campaign.weather.reroll":
            campaigns, weather_entry, weather_prolonged = reroll_campaign_weather(
                user,
                giocatore,
                payload["campaignId"],
            )
            data = {"campaigns": campaigns}
            message = (
                f"Il meteo resta {weather_entry.label}."
                if weather_prolonged
                else f"Nuovo meteo: {weather_entry.label}."
            )
        elif action == "alchemy.brew":
            character, alchemy_result = brew_alchemy(
                payload["characterId"],
                payload.get("ingredients", []),
                payload["potionColor"],
                payload["effect"],
                payload.get("setItemId"),
            )
            data = {
                "creation": alchemy_creation_payload(character),
                "alchemyResult": alchemy_result,
            }
            message = f"{alchemy_result['effect']}: miscela distillata con potenza {alchemy_result['potency']}."
        elif action == "alchemy.extract":
            character, extracted_reagent = extract_alchemy_reagent(payload["characterId"])
            data = {
                "creation": alchemy_creation_payload(character),
                "extractedReagent": extracted_reagent,
            }
            message = f"Estratto {extracted_reagent['name']}."
        elif action == "competencies.upgrade":
            character = upgrade_competence(
                payload["characterId"],
                payload["competenceKey"],
                payload["track"],
                payload["targetRank"],
            )
            data = {"competencies": updated_competence_payload(character)}
            message = "Competenza e PE aggiornati."
        elif action == "competencies.updateExtra":
            character = update_competence_extra(
                payload["characterId"],
                payload["competenceKey"],
                payload["extra"],
            )
            data = {"competencies": updated_competence_payload(character)}
            message = "Extra permanente aggiornato."
        elif action == "competencies.roll":
            character, competence_roll = roll_competence(
                payload["characterId"],
                payload["competenceKey"],
                payload.get("technique", "standard"),
                payload.get("diceSetId"),
            )
            record_competence_dice_roll(giocatore, competence_roll)
            roll_data = serialized_roll(competence_roll)
            data = {
                "competencies": updated_competence_payload(character),
                "competenceRoll": roll_data,
            }
            message = f"{roll_data['competenceName']}: risultato {roll_data['total']}."
        elif action == "competencies.reroll":
            competence_roll = reroll_competence(payload["characterId"], payload["rollId"])
            record_competence_dice_roll(giocatore, competence_roll, reroll=True)
            roll_data = serialized_roll(competence_roll)
            data = {
                "competencies": updated_competence_payload(competence_roll.personaggio),
                "competenceRoll": roll_data,
            }
            message = f"Rilancio di {roll_data['competenceName']}: risultato {roll_data['total']}."
        elif action == "skills.previewUnlock":
            character = _allowed_character(user, giocatore, payload["characterId"])
            data = {
                "skillPreview": preview_skill_unlock(
                    character,
                    payload["skillId"],
                    bypass_prerequisites=_can_bypass_skill_prerequisites(user, giocatore),
                )
            }
            message = "Anteprima dello sblocco preparata."
        elif action == "skills.previewSpell":
            character = _allowed_character(user, giocatore, payload["characterId"])
            data = {
                "spellPreview": preview_spell_cast(
                    character,
                    payload["skillId"],
                    payload["effect"],
                    payload.get("power", 0),
                )
            }
            message = "Anteprima dell'incantesimo preparata senza spendere risorse."
        elif action == "skills.unlock":
            character = unlock_skill(
                payload["characterId"],
                payload["skillId"],
                payload["spend"],
                payload.get("acceptedPassiveIds", []),
                payload.get("note", ""),
                bypass_prerequisites=_can_bypass_skill_prerequisites(user, giocatore),
            )
            data = {
                "character": _character_sheet_payload(character, user, giocatore),
                "skills": skill_catalog_payload(
                    character,
                    can_manage=_can_manage_skills(user, giocatore),
                    can_delete=_can_delete_skills(user, giocatore),
                    bypass_prerequisites=_can_bypass_skill_prerequisites(user, giocatore),
                ),
            }
            message = "Sblocco, PE e note dell'abilità sono stati aggiornati."
        elif action == "skills.updateCharacterXp":
            character = update_character_xp(payload["characterId"], payload.get("xp", {}))
            data = {
                "character": _character_sheet_payload(character, user, giocatore),
                "skills": skill_catalog_payload(
                    character,
                    can_manage=_can_manage_skills(user, giocatore),
                    can_delete=_can_delete_skills(user, giocatore),
                    bypass_prerequisites=_can_bypass_skill_prerequisites(user, giocatore),
                ),
            }
            message = "Punti Esperienza disponibili aggiornati."
        elif action == "skills.configureCharacterActions":
            character = _allowed_character(user, giocatore, payload["characterId"])
            character = configure_character_actions(character.id, payload.get("actions", []))
            data = {
                "skills": skill_catalog_payload(
                    character,
                    can_manage=_can_manage_skills(user, giocatore),
                    can_delete=_can_delete_skills(user, giocatore),
                    bypass_prerequisites=_can_bypass_skill_prerequisites(user, giocatore),
                )
            }
            message = "Configurazione delle azioni del personaggio salvata."
        elif action == "combatButtons.create":
            character = _allowed_character(user, giocatore, payload["characterId"])
            button = create_combat_button(character.id, payload.get("values", {}))
            data = {
                "skills": skill_catalog_payload(
                    character,
                    can_manage=_can_manage_skills(user, giocatore),
                    can_delete=_can_delete_skills(user, giocatore),
                    bypass_prerequisites=_can_bypass_skill_prerequisites(user, giocatore),
                )
            }
            message = f"Bottone combat {button.nome} creato."
        elif action == "combatButtons.update":
            character = _allowed_character(user, giocatore, payload["characterId"])
            button_id = payload.get("buttonId")
            if not button_id:
                raise ApiError("combat_buttons.id_required", "Scegli il bottone combat da modificare.", "buttonId")
            button = update_combat_button(character.id, button_id, payload.get("values", {}))
            data = {
                "skills": skill_catalog_payload(
                    character,
                    can_manage=_can_manage_skills(user, giocatore),
                    can_delete=_can_delete_skills(user, giocatore),
                    bypass_prerequisites=_can_bypass_skill_prerequisites(user, giocatore),
                )
            }
            message = f"Bottone combat {button.nome} aggiornato."
        elif action == "combatButtons.delete":
            character = _allowed_character(user, giocatore, payload["characterId"])
            button_name = delete_combat_button(character.id, payload["buttonId"])
            data = {
                "skills": skill_catalog_payload(
                    character,
                    can_manage=_can_manage_skills(user, giocatore),
                    can_delete=_can_delete_skills(user, giocatore),
                    bypass_prerequisites=_can_bypass_skill_prerequisites(user, giocatore),
                )
            }
            message = f"Bottone combat {button_name} eliminato."
        elif action == "skills.create":
            skill = create_skill(user, giocatore, payload["values"])
            data = {"skill": serialize_skill(skill)}
            message = f"Abilità {skill.nome} creata."
        elif action == "skills.update":
            skill_id = payload.get("skillId")
            if not skill_id:
                raise ApiError("skills.id_required", "Scegli l'abilità da modificare.", "skillId")
            skill = update_skill(user, giocatore, skill_id, payload["values"])
            data = {"skill": serialize_skill(skill)}
            message = f"Abilità {skill.nome} aggiornata."
        elif action == "skills.archive":
            skill = archive_skill(user, giocatore, payload["skillId"])
            data = {"skill": serialize_skill(skill)}
            message = f"Abilità {skill.nome} archiviata."
        elif action == "skills.reorder":
            skill_order = reorder_skills(
                user,
                giocatore,
                payload["familyId"],
                payload.get("skillIds", []),
            )
            data = {"skillOrder": skill_order}
            message = "Ordine delle abilità aggiornato."
        elif action == "market.shop.preview":
            require_game_manager(user, giocatore)
            data = {"market": {"preview": preview_market_generation(payload.get("values", {}))}}
            message = "Anteprima dello stock pronta."
        elif action == "market.shop.save":
            shop, created = save_market_shop(user, giocatore, payload.get("values", {}))
            data = {"market": {**market_management_overview(giocatore), "savedShopId": shop.id, "created": created}}
            message = f"Negozio {shop.nome} {'creato' if created else 'aggiornato'}."
        elif action == "market.shop.regenerate":
            shop_id = payload.get("shopId") or payload.get("values", {}).get("shopId")
            if not shop_id:
                raise ApiError("market.shop_required", "Scegli un negozio.", "shopId")
            shop, diagnostics = regenerate_market_shop(user, giocatore, int(shop_id), payload.get("seed", ""))
            data = {"market": {**market_management_overview(giocatore), "savedShopId": shop.id, "diagnostics": diagnostics}}
            message = f"Stock di {shop.nome} rigenerato."
        elif action == "market.shop.batchCreate":
            values = payload.get("values", {})
            if payload.get("confirm"):
                shops = create_market_batch(user, giocatore, values)
                data = {"market": {**market_management_overview(giocatore), "createdShopIds": [shop.id for shop in shops]}}
                message = f"Creati {len(shops)} negozi."
            else:
                data = {"market": {"batchPreview": preview_market_batch(values)}}
                message = "Anteprima della creazione in serie pronta."
        elif action == "market.shop.state":
            shop = set_market_shop_state(user, giocatore, payload["shopId"], payload["archived"])
            data = {"market": {**market_management_overview(giocatore), "savedShopId": shop.id}}
            message = f"Negozio {shop.nome} {'archiviato' if payload['archived'] else 'ripristinato'}."
        elif action == "market.settings.save":
            save_market_settings(user, giocatore, payload.get("values", {}))
            data = {"market": market_management_overview(giocatore)}
            message = "Impostazioni Mercato salvate."
        elif action == "market.quote":
            data = {"marketQuote": quote_market_purchase(payload["shopId"], payload.get("lines", []), payload.get("negotiationPercent", 0))}
            message = "Preventivo aggiornato."
        elif action == "market.purchase":
            _allowed_character(user, giocatore, payload["characterId"])
            shop, character, quote = purchase_from_market(user, giocatore, payload)
            data = {"market": market_overview(giocatore, selected_shop_id=shop.id, character_id=character.id), "marketQuote": quote, "character": _character_sheet_payload(character, user, giocatore)}
            message = "Acquisto completato."
        elif action == "lore.faction.save":
            save_lore_faction(user, giocatore, payload["values"])
            data = {"lore": lore_payload(user, giocatore)}
            message = "Fazione salvata."
        elif action == "lore.faction.delete":
            delete_lore_faction(user, giocatore, payload["id"])
            data = {"lore": lore_payload(user, giocatore)}
            message = "Fazione archiviata. Gli eventi passati restano consultabili."
        elif action == "lore.relations.save":
            save_lore_relations(user, giocatore, payload["relations"])
            data = {"lore": lore_payload(user, giocatore)}
            message = "Matrice delle reazioni aggiornata."
        elif action == "lore.event.record":
            record_lore_event(user, giocatore, payload["values"])
            data = {"lore": lore_payload(user, giocatore)}
            message = "Evento registrato."
        elif action == "lore.event.update":
            update_lore_event(user, giocatore, payload["values"])
            data = {"lore": lore_payload(user, giocatore)}
            message = "Evento aggiornato."
        elif action == "lore.event.delete":
            delete_lore_event(user, giocatore, payload["id"])
            data = {"lore": lore_payload(user, giocatore)}
            message = "Evento rimosso e reputazioni ricalcolate."
        elif action == "lore.character.save":
            save_lore_npc(user, giocatore, payload["values"])
            data = {"lore": lore_payload(user, giocatore)}
            message = "Personaggio salvato."
        elif action == "names.generate":
            generated = generate_name(giocatore, payload)
            data = {"generatedName": generated}
            message = f"{generated['name']} ({generated['culture']})."
        elif action == "lore.character.delete":
            delete_lore_npc(user, giocatore, payload["id"])
            data = {"lore": lore_payload(user, giocatore)}
            message = "Personaggio archiviato."
        elif action == "lore.timeline.save":
            save_lore_timeline_event(user, giocatore, payload["values"])
            data = {"lore": lore_payload(user, giocatore)}
            message = "Evento della Timeline salvato."
        elif action == "lore.timeline.archive":
            archive_lore_timeline_event(user, giocatore, payload["id"])
            data = {"lore": lore_payload(user, giocatore)}
            message = "Evento della Timeline archiviato."
        elif action == "skills.delete":
            skill_name = delete_skill(
                user,
                giocatore,
                payload["skillId"],
                payload.get("confirmation", ""),
            )
            data = {}
            message = f"Abilità {skill_name} eliminata definitivamente."
        else:  # pragma: no cover
            raise ApiError("action.unknown", "Azione non riconosciuta.", "action", 404)
        return _envelope(
            request,
            data,
            request_id=request_id,
            events=[{"type": action, "message": message}],
            warnings=warnings,
        )
    except ApiError as error:
        return _error_envelope(request, error, request_id=request_id)
    except ObjectDoesNotExist:
        return _error_envelope(request, ApiError("resource.not_found", "La risorsa richiesta non esiste.", status=404), request_id=request_id)

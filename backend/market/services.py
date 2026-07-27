from __future__ import annotations

from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from backend.characters.models import Personaggio, Zaino
from backend.characters.services.inventory_rules import backpack_capacity
from backend.core.api import ApiError
from backend.core.management_services import require_game_manager
from backend.core.models import Giocatore, Negozio, Oggetto, SettingDefinition
from backend.core.security import effective_role

from .config import GENERATOR_RULES_KEY, LOCATION_KEY, SHOP_TYPES_KEY, get_generator_rules, get_shop_type_definitions, resolve_location, validate_generator_rules, validate_market_locations, validate_shop_types
from .generator import generate_stock
from .selectors import normalize_stock, shop_detail


def _category(key: str, *, selectable: bool = True) -> dict:
    category = next((item for item in get_shop_type_definitions()["types"] if item["key"] == key), None)
    if not category:
        raise ApiError("market.category_not_found", "Tipo di negozio non configurato.", "categoryKey")
    if selectable and not category["enabled"]:
        raise ApiError("market.category_disabled", "Questo tipo di negozio è disabilitato.", "categoryKey")
    return category


def _location(key: str) -> dict:
    try:
        return resolve_location(key, selectable=True)
    except ValidationError as exc:
        raise ApiError("market.location_invalid", str(exc.messages[0]), "locationKey") from exc


def _stock(seed: str, category: dict, level: int, location: dict, price_modifier_percent: int = 0) -> tuple[dict, dict]:
    rules = get_generator_rules()
    if not rules["minLevel"] <= level <= rules["maxLevel"]:
        raise ApiError("market.level_invalid", f"Il livello deve essere tra {rules['minLevel']} e {rules['maxLevel']}.", "level")
    generated = generate_stock(seed=seed, category=category, level=level, region_key=location["regionKey"], rules=rules, price_modifier_percent=price_modifier_percent)
    return {"version": 2, "seed": generated.seed, "generatedAt": timezone.now().isoformat(), "entries": generated.entries}, generated.diagnostics


def preview_generation(values: dict) -> dict:
    location = _location(str(values.get("locationKey", "")))
    category = _category(str(values.get("categoryKey", "")))
    level = int(values.get("level", 1))
    seed = str(values.get("seed") or f"{location['key']}-{category['key']}-{level}")[:120]
    stock, diagnostics = _stock(seed, category, level, location, int(values.get("priceModifierPercent", 0) or 0))
    probe = Negozio(nome="Anteprima", categoria=category["key"], livello=level, location_key=location["key"], lista_oggetti=stock)
    detail = shop_detail(probe)
    return {"shop": detail, "diagnostics": diagnostics}


@transaction.atomic
def save_shop(user, giocatore: Giocatore, values: dict) -> tuple[Negozio, bool]:
    require_game_manager(user, giocatore)
    shop_id = values.get("shopId")
    creating = not shop_id
    location = _location(str(values.get("locationKey", "")))
    category = _category(str(values.get("categoryKey", "")))
    level = int(values.get("level", 1))
    rules = get_generator_rules()
    if not rules["minLevel"] <= level <= rules["maxLevel"]:
        raise ApiError("market.level_invalid", f"Il livello deve essere tra {rules['minLevel']} e {rules['maxLevel']}.", "level")
    if creating:
        shop = Negozio()
    else:
        try: shop = Negozio.objects.select_for_update().get(pk=int(shop_id))
        except Negozio.DoesNotExist as exc: raise ApiError("market.shop_not_found", "Negozio non trovato.", "shopId", 404) from exc
    name = str(values.get("name") or f"{category['label']} di {location['placeLabel']}").strip()[:180]
    if not name: raise ApiError("market.name_required", "Inserisci un nome per il negozio.", "name")
    duplicate = Negozio.objects.filter(location_key=location["key"], nome__iexact=name).exclude(pk=shop.pk).filter(archived_at__isnull=True).exists()
    if duplicate: raise ApiError("market.duplicate", "Esiste già un negozio con questo nome nella località.", "name", 409)
    shop.nome, shop.proprietario, shop.categoria, shop.livello = name, str(values.get("owner", "")).strip()[:180], category["key"], level
    shop.location_key, shop.regione_nome, shop.citta_nome = location["key"], location["regionLabel"], location["placeLabel"]
    shop.descrizione = str(values.get("description", shop.descrizione or "")).strip()
    try:
        modifier = int(values.get("priceModifierPercent", shop.price_modifier_percent or 0) or 0)
    except (TypeError, ValueError) as exc:
        raise ApiError("market.price_modifier_invalid", "Il modificatore prezzo deve essere un numero intero.", "priceModifierPercent") from exc
    if abs(modifier) > rules["maximumNegotiationPercent"]:
        raise ApiError("market.price_modifier_limit", f"Il modificatore può essere al massimo ±{rules['maximumNegotiationPercent']}%.", "priceModifierPercent")
    shop.price_modifier_percent = modifier
    shop.in_evidenza = bool(values.get("featured", values.get("inEvidenza", shop.in_evidenza)))
    seed = str(values.get("seed") or shop.generation_seed or f"shop-{shop.pk or name}-{location['key']}")[:120]
    shop.generation_seed = seed
    if values.get("generateStock", creating):
        shop.lista_oggetti, _diagnostics = _stock(seed, category, level, location, modifier)
        shop.stock_revision = (shop.stock_revision or 0) + 1
        shop.last_restocked_at = timezone.now()
    shop.save()
    return shop, creating


@transaction.atomic
def regenerate_shop(user, giocatore: Giocatore, shop_id: int, seed: str = "") -> tuple[Negozio, dict]:
    require_game_manager(user, giocatore)
    try: shop = Negozio.objects.select_for_update().get(pk=shop_id)
    except Negozio.DoesNotExist as exc: raise ApiError("market.shop_not_found", "Negozio non trovato.", "shopId", 404) from exc
    location = _location(shop.location_key)
    category = _category(shop.categoria, selectable=False)
    actual_seed = str(seed or shop.generation_seed or f"shop-{shop.id}")[:120]
    shop.lista_oggetti, diagnostics = _stock(actual_seed, category, shop.livello, location, shop.price_modifier_percent)
    shop.generation_seed, shop.stock_revision, shop.last_restocked_at = actual_seed, F("stock_revision") + 1, timezone.now()
    shop.save(update_fields=["lista_oggetti", "generation_seed", "stock_revision", "last_restocked_at", "updated_at"])
    shop.refresh_from_db()
    return shop, diagnostics


@transaction.atomic
def set_shop_state(user, giocatore: Giocatore, shop_id: int, archived: bool) -> Negozio:
    require_game_manager(user, giocatore)
    if effective_role(user, giocatore) != Giocatore.ROLE_ADMIN:
        raise ApiError("market.archive_admin_only", "L'archiviazione dei negozi è riservata agli amministratori.", status=403)
    try: shop = Negozio.objects.select_for_update().get(pk=shop_id)
    except Negozio.DoesNotExist as exc: raise ApiError("market.shop_not_found", "Negozio non trovato.", "shopId", 404) from exc
    shop.archived_at = timezone.now() if archived else None
    shop.save(update_fields=["archived_at", "updated_at"])
    return shop


def preview_batch(values: dict) -> list[dict]:
    count = int(values.get("count", 1))
    if not 1 <= count <= 20: raise ApiError("market.batch_count", "Puoi creare da 1 a 20 negozi.", "count")
    return [preview_generation({**values, "seed": f"{values.get('seed') or 'batch'}-{index + 1}"}) for index in range(count)]


@transaction.atomic
def create_batch(user, giocatore: Giocatore, values: dict) -> list[Negozio]:
    require_game_manager(user, giocatore)
    if effective_role(user, giocatore) != Giocatore.ROLE_ADMIN:
        raise ApiError("market.batch_admin_only", "La creazione in serie è riservata agli amministratori.", status=403)
    count = int(values.get("count", 1))
    if not 1 <= count <= 20: raise ApiError("market.batch_count", "Puoi creare da 1 a 20 negozi.", "count")
    template = str(values.get("nameTemplate") or "{typeLabel} di {placeLabel} {number}")
    location = _location(str(values.get("locationKey", ""))); category = _category(str(values.get("categoryKey", "")))
    shops = []
    for index in range(count):
        name = template.format(typeLabel=category["label"], placeLabel=location["placeLabel"], number=index + 1)
        shop, _ = save_shop(user, giocatore, {**values, "name": name, "seed": f"{values.get('seed') or 'batch'}-{index + 1}", "shopId": None})
        shops.append(shop)
    return shops


@transaction.atomic
def save_market_settings(user, giocatore: Giocatore, values: dict) -> None:
    require_game_manager(user, giocatore)
    role = effective_role(user, giocatore)
    validators = {LOCATION_KEY: validate_market_locations, SHOP_TYPES_KEY: validate_shop_types, GENERATOR_RULES_KEY: validate_generator_rules}
    aliases = {"locations": LOCATION_KEY, "shopTypes": SHOP_TYPES_KEY, "generatorRules": GENERATOR_RULES_KEY}
    submitted = {aliases.get(key, key): value for key, value in values.items()}
    for key, validator in validators.items():
        if key not in submitted: continue
        if key == GENERATOR_RULES_KEY and role != Giocatore.ROLE_ADMIN:
            raise ApiError("market.generator_admin_only", "Le regole del generatore sono riservate agli amministratori.", key, 403)
        try: value = validator(submitted[key])
        except ValidationError as exc: raise ApiError("market.settings_invalid", exc.messages[0], key) from exc
        SettingDefinition.objects.filter(key=key).update(value=value)


def _lines(shop: Negozio, lines: object) -> tuple[list[dict], int]:
    if not isinstance(lines, list) or not lines: raise ApiError("market.cart_empty", "Il carrello è vuoto.", "lines")
    stock = normalize_stock(shop.lista_oggetti); available = {entry.get("itemId"): entry for entry in stock["entries"] if isinstance(entry, dict)}
    checked, total = [], 0
    for line in lines:
        item_id, quantity = int(line.get("itemId")), int(line.get("quantity"))
        entry = available.get(item_id)
        if not entry or quantity < 1 or quantity > int(entry.get("quantity", 0)):
            raise ApiError("market.stock_insufficient", "La disponibilità del negozio è cambiata.", "lines", 409)
        checked.append({"itemId": item_id, "quantity": quantity, "unitPrice": int(entry.get("unitPrice", 0))})
        total += quantity * int(entry.get("unitPrice", 0))
    return checked, total


def _negotiated_total(base_total: int, raw_percent: object) -> tuple[int, int]:
    try:
        percent = int(raw_percent or 0)
    except (TypeError, ValueError) as exc:
        raise ApiError("market.negotiation_invalid", "Il modificatore della contrattazione deve essere un numero intero.", "negotiationPercent") from exc
    if percent == 0:
        return base_total, 0
    maximum = int(get_generator_rules()["maximumNegotiationPercent"])
    if abs(percent) > maximum:
        raise ApiError("market.negotiation_limit", f"La contrattazione può modificare il prezzo al massimo di ±{maximum}%.", "negotiationPercent")
    return max(0, (base_total * (100 + percent) + 50) // 100), percent


def quote_purchase(shop_id: int, lines: object, negotiation_percent: object = 0) -> dict:
    try: shop = Negozio.objects.get(pk=shop_id, archived_at__isnull=True)
    except Negozio.DoesNotExist as exc: raise ApiError("market.shop_not_found", "Negozio non trovato.", "shopId", 404) from exc
    checked, base_total = _lines(shop, lines)
    total, percent = _negotiated_total(base_total, negotiation_percent)
    return {"shopId": shop.id, "stockRevision": shop.stock_revision, "lines": checked, "baseTotal": base_total, "negotiationPercent": percent, "total": total}


@transaction.atomic
def purchase(user, giocatore: Giocatore, values: dict) -> tuple[Negozio, Personaggio, dict]:
    character_id = int(values.get("characterId")); shop_id = int(values.get("shopId"))
    try: shop = Negozio.objects.select_for_update().get(pk=shop_id, archived_at__isnull=True)
    except Negozio.DoesNotExist as exc: raise ApiError("market.shop_not_found", "Negozio non trovato.", "shopId", 404) from exc
    character = Personaggio.objects.select_for_update().select_related("zaino").get(pk=character_id)
    if int(values.get("stockRevision", -1)) != shop.stock_revision: raise ApiError("market.stale_stock", "Lo stock è cambiato: aggiorna il carrello.", "stockRevision", 409)
    lines, base_total = _lines(shop, values.get("lines"))
    total, negotiation_percent = _negotiated_total(base_total, values.get("negotiationPercent", 0))
    if character.monete < total: raise ApiError("market.insufficient_coins", "Monete insufficienti.", "lines", 409)
    if character.zaino is None: raise ApiError("market.backpack_missing", "Il personaggio non ha uno zaino.", "characterId", 409)
    capacity = backpack_capacity(character.tot if isinstance(character.tot, dict) else {})
    free_slots = [index for index in range(1, capacity + 1) if getattr(character.zaino, f"slot_{index}_id") is None]
    needed = sum(line["quantity"] for line in lines)
    if len(free_slots) < needed: raise ApiError("market.backpack_full", "Non ci sono abbastanza spazi liberi nello zaino.", "lines", 409)
    items = Oggetto.objects.in_bulk([line["itemId"] for line in lines])
    if len(items) != len(lines): raise ApiError("market.item_missing", "Uno degli oggetti non è più disponibile.", "lines", 409)
    slot_index = 0
    for line in lines:
        for _ in range(line["quantity"]):
            setattr(character.zaino, f"slot_{free_slots[slot_index]}", items[line["itemId"]]); slot_index += 1
    character.zaino.save(update_fields=[f"slot_{index}" for index in free_slots[:needed]] + ["updated_at"])
    character.monete -= total; character.save(update_fields=["monete", "updated_at"])
    stock = normalize_stock(shop.lista_oggetti)
    purchased = {line["itemId"]: line["quantity"] for line in lines}
    for entry in stock["entries"]:
        if entry.get("itemId") in purchased: entry["quantity"] -= purchased[entry["itemId"]]
    shop.lista_oggetti, shop.stock_revision = stock, F("stock_revision") + 1
    shop.save(update_fields=["lista_oggetti", "stock_revision", "updated_at"]); shop.refresh_from_db()
    return shop, character, {"baseTotal": base_total, "negotiationPercent": negotiation_percent, "total": total, "lines": lines, "stockRevision": shop.stock_revision}

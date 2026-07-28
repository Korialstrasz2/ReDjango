from __future__ import annotations

from backend.characters.selectors import serialize_item
from backend.core.models import Giocatore, Negozio, Oggetto
from backend.core.security import effective_role, has_minimum_role

from .config import configuration_payload, get_market_locations, get_shop_type_definitions, market_settings_payload, resolve_location
from .generator import parse_loot_levels

# Mirrors the filters in generator.generate_stock. Kept as data so the reasons a
# template is skipped can be reported instead of failing silently.
STOCK_EXCLUSION_REASONS = (
    ("notTemplate", "Non è un modello (modello=False)"),
    ("archived", "Archiviato"),
    ("special", "Marcato speciale"),
    ("unique", "Rarità Unico"),
    ("noLootLevel", "lv_loot mancante o illeggibile"),
    ("unrankedType", "tipo_1 assente o non previsto da nessuna categoria di negozio"),
)


def normalize_stock(value: object) -> dict:
    if isinstance(value, dict) and value.get("version") == 2 and isinstance(value.get("entries"), list):
        return value
    # Old data is intentionally visible but cannot be purchased until imported/restocked.
    return {"version": 2, "seed": "", "generatedAt": None, "entries": []}


def _image_url(image) -> str:
    return image.file.url if image and image.file else ""


def _shop_summary(shop: Negozio) -> dict:
    stock = normalize_stock(shop.lista_oggetti)
    entries = [entry for entry in stock["entries"] if isinstance(entry, dict)]
    return {"id": shop.id, "name": shop.nome, "owner": shop.proprietario, "categoryKey": shop.categoria, "level": shop.livello, "locationKey": shop.location_key, "regionName": shop.regione_nome, "placeName": shop.citta_nome, "description": shop.descrizione, "backgroundUrl": _image_url(shop.immagine_sfondo), "stockCount": sum(max(0, int(entry.get("quantity", 0) or 0)) for entry in entries), "distinctStockCount": len(entries), "featured": shop.in_evidenza, "priceModifierPercent": shop.price_modifier_percent, "stockRevision": shop.stock_revision, "lastRestockedAt": shop.last_restocked_at.isoformat() if shop.last_restocked_at else None, "generationProfileKey": shop.generation_profile_key, "archived": bool(shop.archived_at)}


def shop_detail(shop: Negozio) -> dict:
    result = _shop_summary(shop)
    stock = normalize_stock(shop.lista_oggetti)
    item_ids = [entry.get("itemId") for entry in stock["entries"] if isinstance(entry, dict) and isinstance(entry.get("itemId"), int)]
    items = Oggetto.objects.in_bulk(item_ids)
    entries = []
    for entry in stock["entries"]:
        if not isinstance(entry, dict) or entry.get("itemId") not in items:
            continue
        entries.append({"item": serialize_item(items[entry["itemId"]], detailed=True), "quantity": max(0, int(entry.get("quantity", 0) or 0)), "unitPrice": max(0, int(entry.get("unitPrice", 0) or 0)), "source": entry.get("source", "generated")})
    result["stock"] = entries
    result["seed"] = stock.get("seed", "")
    return result


def _locations(shops: list[Negozio]) -> list[dict]:
    counts = {}
    for shop in shops:
        counts[shop.location_key] = counts.get(shop.location_key, 0) + 1
    regions = []
    for region in get_market_locations()["regions"]:
        places = [{"key": place["key"], "label": place["label"], "enabled": place["enabled"], "locationKey": f"{region['key']}/{place['key']}", "shopCount": counts.get(f"{region['key']}/{place['key']}", 0)} for place in region["places"]]
        regions.append({"key": region["key"], "label": region["label"], "enabled": region["enabled"], "places": places, "shopCount": sum(place["shopCount"] for place in places)})
    return regions


def market_overview(giocatore: Giocatore, *, selected_shop_id: int | None = None, character_id: int | None = None, include_archived: bool = False) -> dict:
    role = effective_role(None, giocatore)
    can_manage = has_minimum_role(role, Giocatore.ROLE_MASTER)
    query = Negozio.objects.all()
    if not include_archived or not can_manage:
        query = query.filter(archived_at__isnull=True)
    shops = list(query.order_by("regione_nome", "citta_nome", "nome"))
    selected = next((shop for shop in shops if shop.id == selected_shop_id), None)
    character = None
    from backend.characters.models import Personaggio
    if character_id:
        character_obj = Personaggio.objects.filter(pk=character_id, archived_at__isnull=True).first()
        if character_obj:
            character = {"id": character_obj.id, "name": character_obj.nome, "coins": character_obj.monete}
    if character is None and giocatore.active_character_id:
        character_obj = Personaggio.objects.filter(pk=giocatore.active_character_id, archived_at__isnull=True).first()
        if character_obj:
            character = {"id": character_obj.id, "name": character_obj.nome, "coins": character_obj.monete}
    is_admin = role == Giocatore.ROLE_ADMIN
    full_configuration = configuration_payload()
    configuration = {"locationsVersion": full_configuration["locationsVersion"], "shopTypesVersion": full_configuration["shopTypesVersion"], "hash": full_configuration["hash"], "limits": full_configuration["limits"]}
    if can_manage:
        configured_types = {
            item_type
            for shop_type in full_configuration["shopTypes"]["types"]
            for item_type in shop_type["itemTypeRanks"]
        }
        catalog_types = set(
            Oggetto.objects.filter(modello=True, archived_at__isnull=True)
            .exclude(tipo_1="")
            .values_list("tipo_1", flat=True)
            .distinct()
        )
        configuration.update({
            "locations": full_configuration["locations"],
            "shopTypes": full_configuration["shopTypes"],
            "generatorRules": full_configuration["generatorRules"] if is_admin else None,
            "generationProfiles": full_configuration["generationProfiles"],
            "itemTypes": sorted(configured_types | catalog_types, key=str.casefold),
        })
    return {"locations": _locations(shops), "shopTypes": [{key: item[key] for key in ("key", "label", "icon", "enabled", "defaultBackground", "inventoryMultiplier")} for item in get_shop_type_definitions()["types"]], "shops": [_shop_summary(shop) for shop in shops], "selectedShop": shop_detail(selected) if selected else None, "character": character, "permissions": {"canManage": can_manage, "canConfigure": can_manage, "canEditLocations": can_manage, "canEditShopTypes": can_manage, "canRegenerate": can_manage, "canTuneGenerator": is_admin, "canEditGenerationProfiles": is_admin, "canBatchCreate": is_admin, "canArchive": is_admin, "canPurchase": character is not None}, "configuration": configuration}


def _exclusion_reasons(item: Oggetto, ranked_types: set[str]) -> list[str]:
    reasons = []
    if not item.modello:
        reasons.append("notTemplate")
    if item.archiviato or item.archived_at:
        reasons.append("archived")
    if item.speciale:
        reasons.append("special")
    if item.rarita == Oggetto.Rarita.UNICO:
        reasons.append("unique")
    if not parse_loot_levels(item.lv_loot):
        reasons.append("noLootLevel")
    if item.tipo_1.strip() not in ranked_types:
        reasons.append("unrankedType")
    return reasons


def stock_eligibility_report(*, limit: int = 200) -> dict:
    """List catalogue items the stock generator can never pick, and why.

    Every filter is silent inside the generator, so an item with a missing
    lv_loot or an unranked tipo_1 simply never appears in any shop. Surfacing
    the count and the reasons is the only way to notice.
    """
    ranked_types = {
        item_type
        for definition in get_shop_type_definitions()["types"]
        for item_type, rank in definition["itemTypeRanks"].items()
        if rank < 5
    }
    items = Oggetto.objects.only(
        "id", "nome", "modello", "archiviato", "archived_at", "speciale",
        "rarita", "lv_loot", "tipo_1",
    )
    eligible = 0
    excluded = 0
    counts = {key: 0 for key, _label in STOCK_EXCLUSION_REASONS}
    samples: list[dict] = []
    for item in items.iterator(chunk_size=2000):
        reasons = _exclusion_reasons(item, ranked_types)
        if not reasons:
            eligible += 1
            continue
        excluded += 1
        for reason in reasons:
            counts[reason] += 1
        if len(samples) < limit:
            samples.append({"id": item.id, "name": item.nome, "itemType": item.tipo_1, "lootLevel": item.lv_loot, "reasons": reasons})
    return {
        "eligibleCount": eligible,
        "excludedCount": excluded,
        "rankedTypes": sorted(ranked_types),
        "reasons": [
            {"key": key, "label": label, "count": counts[key]}
            for key, label in STOCK_EXCLUSION_REASONS
        ],
        "samples": samples,
        "sampleLimit": limit,
    }


def management_overview(giocatore: Giocatore) -> dict:
    payload = market_overview(giocatore, include_archived=True)
    settings = market_settings_payload()
    if effective_role(None, giocatore) != Giocatore.ROLE_ADMIN:
        settings["generatorRules"] = None
    payload["settings"] = settings
    payload["stockEligibility"] = stock_eligibility_report()
    return payload


def location_for_shop(location_key: str) -> dict:
    return resolve_location(location_key, selectable=True)

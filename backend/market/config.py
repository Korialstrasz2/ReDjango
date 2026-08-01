from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy

from django.core.exceptions import ValidationError

from backend.core.models import Oggetto, SettingDefinition


LOCATION_KEY = "mercato.locations"
SHOP_TYPES_KEY = "mercato.shop_types"
GENERATOR_RULES_KEY = "mercato.generator_rules"
_KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def rollable_rarities() -> list[int]:
    """Every catalogue rarity a shop can roll, derived from the item model.

    Unico is deliberately excluded: those pieces are assigned by hand. Reading
    the list from ``Oggetto.Rarita`` instead of hard-coding it is what keeps a
    newly added rarity from silently becoming ungeneratable, which is exactly
    how rarity 5 stayed out of every shop.
    """
    return [value for value in Oggetto.Rarita.values if value != Oggetto.Rarita.UNICO]


def rarity_choices() -> list[dict]:
    labels = dict(Oggetto.Rarita.choices)
    return [{"value": str(value), "label": labels[value]} for value in rollable_rarities()]


def _normalized_rarity_probabilities(raw: object, field: str, context: str = "") -> dict[str, float]:
    prefix = f"{context}: " if context else ""
    if not isinstance(raw, dict):
        raise ValidationError({field: f"{prefix}rarityProbabilities deve essere un oggetto."})
    try:
        normalized = {
            str(rarity): float(raw.get(str(rarity), raw.get(rarity, 0)) or 0)
            for rarity in rollable_rarities()
        }
    except (TypeError, ValueError) as exc:
        raise ValidationError({field: f"{prefix}probabilità di rarità non valide."}) from exc
    if any(probability < 0 for probability in normalized.values()):
        raise ValidationError({field: f"{prefix}le probabilità non possono essere negative."})
    if abs(sum(normalized.values()) - 1) > .001:
        raise ValidationError({field: f"{prefix}le probabilità di rarità devono sommare a 1."})
    return normalized


def _value(key: str) -> object:
    setting = SettingDefinition.objects.filter(key=key, active=True, archived_at__isnull=True).first()
    if setting is None:
        raise ValidationError(f"Manca la configurazione Mercato: {key}.")
    return setting.default_value if setting.value is None else setting.value


def _key(raw: object, field: str) -> str:
    value = str(raw or "").strip()
    if not _KEY_RE.fullmatch(value):
        raise ValidationError({field: "Usa una chiave minuscola, stabile e separata da trattini."})
    return value


def _label(raw: object, field: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValidationError({field: "L'etichetta è obbligatoria."})
    return value[:180]


def validate_market_locations(value: object) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("regions"), list):
        raise ValidationError("mercato.locations deve contenere una lista regions.")
    region_keys: set[str] = set()
    place_keys: set[str] = set()
    regions = []
    for index, raw_region in enumerate(value["regions"]):
        if not isinstance(raw_region, dict):
            raise ValidationError({"regions": f"La regione #{index + 1} non è un oggetto."})
        key = _key(raw_region.get("key"), f"regions[{index}].key")
        if key in region_keys:
            raise ValidationError({"regions": f"Chiave regione duplicata: {key}."})
        region_keys.add(key)
        places = raw_region.get("places")
        if not isinstance(places, list):
            raise ValidationError({"regions": f"{key}: places deve essere una lista."})
        normalized_places = []
        for place_index, raw_place in enumerate(places):
            if not isinstance(raw_place, dict):
                raise ValidationError({"regions": f"{key}: località #{place_index + 1} non valida."})
            place_key = _key(raw_place.get("key"), f"regions[{index}].places[{place_index}].key")
            location_key = f"{key}/{place_key}"
            if location_key in place_keys:
                raise ValidationError({"regions": f"Località duplicata: {location_key}."})
            place_keys.add(location_key)
            aliases = raw_place.get("aliases", [])
            if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
                raise ValidationError({"regions": f"{location_key}: aliases deve essere una lista di testi."})
            normalized_places.append({
                "key": place_key, "label": _label(raw_place.get("label"), "place.label"),
                "enabled": bool(raw_place.get("enabled", True)), "aliases": [alias.strip() for alias in aliases if alias.strip()],
            })
        regions.append({"key": key, "label": _label(raw_region.get("label"), "region.label"), "enabled": bool(raw_region.get("enabled", True)), "places": normalized_places})
    return {"version": int(value.get("version", 1)), "regions": regions}


def validate_shop_types(value: object) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("types"), list):
        raise ValidationError("mercato.shop_types deve contenere una lista types.")
    keys: set[str] = set()
    types = []
    for index, raw in enumerate(value["types"]):
        if not isinstance(raw, dict):
            raise ValidationError({"types": f"Tipo #{index + 1} non valido."})
        key = _key(raw.get("key"), f"types[{index}].key")
        if key in keys:
            raise ValidationError({"types": f"Chiave tipo duplicata: {key}."})
        keys.add(key)
        ranks = raw.get("itemTypeRanks", {})
        # Earlier ReDjango prototypes persisted relative itemWeights.  Accepting
        # them here keeps an administrator's edited setting valid while the
        # service consumes one normalized rank contract.
        if not ranks and isinstance(raw.get("itemWeights"), dict):
            weights = raw["itemWeights"]
            maximum = max((float(weight) for weight in weights.values()), default=0)
            ranks = {
                item_type: 0 if float(weight) >= maximum * .8 else 1 if float(weight) >= maximum * .6 else 2 if float(weight) >= maximum * .4 else 3
                for item_type, weight in weights.items()
            }
        if not isinstance(ranks, dict) or not ranks:
            raise ValidationError({"types": f"{key}: itemTypeRanks è obbligatorio."})
        normalized_ranks = {}
        for item_type, rank in ranks.items():
            try:
                rank = int(rank)
            except (TypeError, ValueError) as exc:
                raise ValidationError({"types": f"{key}: grado non valido per {item_type}."}) from exc
            if rank < 0 or rank > 5:
                raise ValidationError({"types": f"{key}: i gradi sono compresi tra 0 e 5."})
            normalized_ranks[str(item_type).strip()] = rank
        try:
            multiplier = float(raw.get("inventoryMultiplier", 1))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"types": f"{key}: inventoryMultiplier non valido."}) from exc
        if multiplier <= 0 or multiplier > 10:
            raise ValidationError({"types": f"{key}: inventoryMultiplier deve essere tra 0 e 10."})
        types.append({"key": key, "label": _label(raw.get("label"), "type.label"), "icon": str(raw.get("icon", "store")).strip()[:80], "enabled": bool(raw.get("enabled", True)), "defaultBackground": str(raw.get("defaultBackground", "")).strip()[:160], "inventoryMultiplier": multiplier, "itemTypeRanks": normalized_ranks})
    return {"version": int(value.get("version", 1)), "types": types}


def validate_generator_rules(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValidationError("mercato.generator_rules deve essere un oggetto.")
    # quantityScale is the global size dial Elder applied as a hard-coded 1.55
    # on top of the per-shop multiplier. It lives here so shop size is tunable
    # without editing every shop type. varietyBias, levelSpread and
    # levelSpreadWeight are the assortment dials: how much a template is
    # discounted once it is already on the shelf, and how far off the shop's
    # grade the generator may shop for merchandise.
    defaults = {"minLevel": 1, "maxLevel": 10, "baseCount": 25, "countPerLevel": 5.5, "countVariance": .25, "quantityScale": 1.4, "varietyBias": .35, "levelSpread": 1, "levelSpreadWeight": .5, "rarityProbabilities": {"1": .68, "2": .15, "3": .1, "4": .05, "5": .02}, "fallbackLevelDeltas": [0, -1, 1, -2, 2, -3, 3], "maximumCopies": 5, "priceBasePercent": 75, "priceLevelPercent": 5, "maximumNegotiationPercent": 25}
    result = {**defaults, **value}
    for key in ("minLevel", "maxLevel", "baseCount", "countPerLevel", "countVariance", "quantityScale", "varietyBias", "levelSpread", "levelSpreadWeight", "maximumCopies", "priceBasePercent", "priceLevelPercent", "maximumNegotiationPercent"):
        try:
            result[key] = float(result[key]) if key in {"baseCount", "countPerLevel", "countVariance", "quantityScale", "varietyBias", "levelSpreadWeight"} else int(result[key])
        except (ValueError, TypeError) as exc:
            raise ValidationError({key: "Deve essere un numero."}) from exc
    if result["minLevel"] < 1 or result["maxLevel"] < result["minLevel"] or result["maximumCopies"] < 1:
        raise ValidationError("Limiti del generatore non validi.")
    if not 0 < result["quantityScale"] <= 10:
        raise ValidationError({"quantityScale": "Deve essere maggiore di 0 e al massimo 10."})
    # 1 keeps a template as likely on its second copy as on its first, which is
    # the behaviour that made shops repeat themselves; 0 forbids a second copy.
    if not 0 <= result["varietyBias"] <= 1:
        raise ValidationError({"varietyBias": "Deve essere compreso tra 0 e 1."})
    if not 0 <= result["levelSpread"] <= 10:
        raise ValidationError({"levelSpread": "Deve essere compreso tra 0 e 10."})
    if not 0 < result["levelSpreadWeight"] <= 1:
        raise ValidationError({"levelSpreadWeight": "Deve essere maggiore di 0 e al massimo 1."})
    result["rarityProbabilities"] = _normalized_rarity_probabilities(
        result["rarityProbabilities"], "rarityProbabilities",
    )
    if not isinstance(result["fallbackLevelDeltas"], list) or not all(isinstance(delta, int) for delta in result["fallbackLevelDeltas"]):
        raise ValidationError({"fallbackLevelDeltas": "Deve essere una lista di interi."})
    return result


def get_market_locations() -> dict: return validate_market_locations(_value(LOCATION_KEY))
def get_shop_type_definitions() -> dict: return validate_shop_types(_value(SHOP_TYPES_KEY))
def get_generator_rules() -> dict: return validate_generator_rules(_value(GENERATOR_RULES_KEY))


def resolve_location(location_key: str, *, selectable: bool = False) -> dict:
    for region in get_market_locations()["regions"]:
        for place in region["places"]:
            if location_key == f"{region['key']}/{place['key']}":
                if selectable and (not region["enabled"] or not place["enabled"]):
                    raise ValidationError("La località è disabilitata e non può ricevere nuovi negozi.")
                return {"key": location_key, "regionKey": region["key"], "regionLabel": region["label"], "placeKey": place["key"], "placeLabel": place["label"], "enabled": bool(region["enabled"] and place["enabled"])}
    raise ValidationError("Località Mercato non configurata.")


def configuration_payload() -> dict:
    locations, types, rules = get_market_locations(), get_shop_type_definitions(), get_generator_rules()
    canonical = json.dumps({"locations": locations, "shopTypes": types, "rules": rules}, sort_keys=True, separators=(",", ":"))
    return {"locationsVersion": locations["version"], "shopTypesVersion": types["version"], "hash": hashlib.sha256(canonical.encode()).hexdigest()[:16], "locations": locations, "shopTypes": types, "generatorRules": rules, "rarityChoices": rarity_choices(), "limits": {"minLevel": rules["minLevel"], "maxLevel": rules["maxLevel"], "maximumNegotiationPercent": rules["maximumNegotiationPercent"], "batchMaximum": 20}}


def market_settings_payload() -> dict:
    return {"locations": get_market_locations(), "shopTypes": get_shop_type_definitions(), "generatorRules": get_generator_rules()}

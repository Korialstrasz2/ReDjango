from __future__ import annotations

from django.db import transaction

from backend.core.api import ApiError
from backend.core.models import Giocatore

from .models import DatiMappa
from .services import create_uploaded_image
from .travel_selectors import can_manage_travel_maps


def _require_manager(user, giocatore: Giocatore) -> None:
    if not can_manage_travel_maps(user, giocatore):
        raise ApiError(
            "travel.master_required",
            "Questa operazione è riservata a Master e Amministratori.",
            status=403,
        )


def _campaign(giocatore: Giocatore):
    if not giocatore.active_campaign_id:
        raise ApiError("travel.campaign_required", "Seleziona una campagna attiva prima di usare Viaggio.", status=409)
    return giocatore.active_campaign


def get_travel_map(giocatore: Giocatore, map_id: int) -> DatiMappa:
    try:
        return DatiMappa.objects.select_related("image").get(
            pk=map_id,
            campagna=_campaign(giocatore),
            tipo="globale",
            archived_at__isnull=True,
        )
    except DatiMappa.DoesNotExist as exc:
        raise ApiError("travel.map_not_found", "Mappa globale non trovata.", status=404) from exc


def _number(value, fallback: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(parsed, maximum))


def _integer(value, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(parsed, maximum))


def sanitize_grid(raw: object) -> dict:
    grid = raw if isinstance(raw, dict) else {}
    return {
        "orientation": "flat" if grid.get("orientation") == "flat" else "pointy",
        "cols": _integer(grid.get("cols"), 20, 1, 1000),
        "rows": _integer(grid.get("rows"), 20, 1, 1000),
        "scale": _number(grid.get("scale"), 1, 0.1, 12),
        "offsetX": _number(grid.get("offsetX"), 80, -100000, 100000),
        "offsetY": _number(grid.get("offsetY"), 80, -100000, 100000),
        "hexSize": _number(grid.get("hexSize"), 35, 3, 750),
        "gridOffsetX": _number(grid.get("gridOffsetX"), 0, -100000, 100000),
        "gridOffsetY": _number(grid.get("gridOffsetY"), 0, -100000, 100000),
    }


def sanitize_effects(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ApiError("travel.effects_invalid", "Gli effetti degli esagoni non sono validi.", "hexEffects")
    result = {}
    for key, value in list(raw.items())[:1000000]:
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        effect = {
            "black": bool(value.get("black")),
            "bw": bool(value.get("bw")),
            "blur": _number(value.get("blur"), 0, 0, 20),
        }
        if effect["black"] or effect["bw"] or effect["blur"] > 0:
            result[key[:40]] = effect
    return result


def sanitize_markers(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        raise ApiError("travel.markers_invalid", "Le icone della mappa non sono valide.", "markers")
    result = []
    for marker in raw[:500]:
        if not isinstance(marker, dict):
            continue
        raw_hex = str(marker.get("hex") or "").strip()
        parts = raw_hex.split("-")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            continue
        result.append(
            {
                "id": str(marker.get("id") or "")[:80],
                "hex": raw_hex[:40],
                "markerType": str(marker.get("markerType") or "circle-green")[:60],
                "tag": str(marker.get("tag") or "").strip()[:120],
                "author": str(marker.get("author") or "Sconosciuto").strip()[:120] or "Sconosciuto",
                "createdAt": str(marker.get("createdAt") or "")[:60],
            }
        )
    return result


@transaction.atomic
def create_travel_map(user, giocatore: Giocatore, uploaded_file, payload: dict) -> DatiMappa:
    _require_manager(user, giocatore)
    campaign = _campaign(giocatore)
    name = str(payload.get("name") or payload.get("title") or "").strip()[:180]
    if not name:
        raise ApiError("travel.name_required", "Inserisci un nome per la mappa.", "name")
    asset = create_uploaded_image(
        user,
        uploaded_file,
        {
            "title": name,
            "usageType": "travel_map",
            "categoryId": payload.get("categoryId"),
            "group": payload.get("group") or "Mappe globali",
            "notes": payload.get("notes") or "",
        },
    )
    is_first_map = not DatiMappa.objects.filter(
        campagna=campaign,
        tipo="globale",
        archived_at__isnull=True,
    ).exists()
    travel_map = DatiMappa.objects.create(
        nome=name,
        campagna=campaign,
        image=asset,
        tipo="globale",
        grid_data=sanitize_grid({}),
        default_for_campaign=is_first_map,
    )
    return travel_map


@transaction.atomic
def update_travel_map(user, giocatore: Giocatore, travel_map: DatiMappa, payload: dict) -> DatiMappa:
    action = str(payload.get("operation") or "")
    if action == "saveMarkers":
        travel_map.markers = sanitize_markers(payload.get("markers"))
        travel_map.save(update_fields=["markers", "updated_at"])
        return travel_map

    _require_manager(user, giocatore)
    if action == "saveAll":
        travel_map.grid_data = sanitize_grid(payload.get("grid"))
        travel_map.hex_effects = sanitize_effects(payload.get("hexEffects"))
        travel_map.markers = sanitize_markers(payload.get("markers"))
        fields = ["grid_data", "hex_effects", "markers", "updated_at"]
    elif action == "saveGrid":
        travel_map.grid_data = sanitize_grid(payload.get("grid"))
        fields = ["grid_data", "updated_at"]
    elif action == "saveEffects":
        travel_map.hex_effects = sanitize_effects(payload.get("hexEffects"))
        fields = ["hex_effects", "updated_at"]
    elif action == "setDefault":
        DatiMappa.objects.filter(
            campagna=travel_map.campagna,
            tipo="globale",
            archived_at__isnull=True,
        ).exclude(pk=travel_map.pk).update(default_for_campaign=False)
        travel_map.default_for_campaign = True
        fields = ["default_for_campaign", "updated_at"]
    else:
        raise ApiError("travel.operation_invalid", "Operazione Viaggio non riconosciuta.", "operation")
    travel_map.save(update_fields=fields)
    return travel_map

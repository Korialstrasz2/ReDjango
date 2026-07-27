from backend.core.models import Giocatore
from backend.core.security import effective_role, get_or_create_giocatore_for_user, has_minimum_role

from .models import DatiMappa


def can_manage_travel_maps(user, giocatore: Giocatore | None = None) -> bool:
    if not user:
        return False
    giocatore = giocatore or get_or_create_giocatore_for_user(user)
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)


def serialize_travel_map(travel_map: DatiMappa) -> dict:
    grid = travel_map.grid_data if isinstance(travel_map.grid_data, dict) else {}
    return {
        "id": travel_map.id,
        "name": travel_map.nome,
        "imageUrl": travel_map.image.file.url if travel_map.image_id and travel_map.image.file else "",
        "grid": {
            "orientation": grid.get("orientation", "pointy"),
            "cols": grid.get("cols", 20),
            "rows": grid.get("rows", 20),
            "scale": grid.get("scale", 1),
            "offsetX": grid.get("offsetX", 80),
            "offsetY": grid.get("offsetY", 80),
            "hexSize": grid.get("hexSize", 35),
            "gridOffsetX": grid.get("gridOffsetX", 0),
            "gridOffsetY": grid.get("gridOffsetY", 0),
        },
        "hexEffects": travel_map.hex_effects if isinstance(travel_map.hex_effects, dict) else {},
        "markers": travel_map.markers if isinstance(travel_map.markers, list) else [],
        "isDefault": travel_map.default_for_campaign,
        "updatedAt": travel_map.updated_at.isoformat() if travel_map.updated_at else None,
    }


def travel_maps_payload(user, giocatore: Giocatore) -> dict:
    campaign = giocatore.active_campaign
    maps = []
    if campaign:
        maps = [
            serialize_travel_map(travel_map)
            for travel_map in DatiMappa.objects.select_related("image").filter(
                campagna=campaign,
                tipo="globale",
                archived_at__isnull=True,
            ).order_by("-default_for_campaign", "nome", "id")
        ]
    return {
        "campaign": (
            {"id": campaign.id, "name": campaign.nome}
            if campaign
            else None
        ),
        "maps": maps,
        "canManage": can_manage_travel_maps(user, giocatore),
        "playerName": giocatore.display_name or giocatore.nome,
    }

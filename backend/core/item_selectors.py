from __future__ import annotations

from itertools import islice

from django.db.models import Q

from backend.characters.selectors import serialize_item
from backend.characters.services.custom_effects import effect_configuration_payload
from backend.characters.services.inventory_rules import item_fits_container
from backend.core.weapon_rules import weapon_configuration_payload

from .models import Oggetto, OpzioneTipoOggetto, TipoArma


CATALOG_FILTER_POSITIONS = ("tipo_1", "tipo_2", "tipo_3")


def _catalog_queryset(
    query: str,
    *,
    include_archived: bool,
    types: tuple[str, str, str],
    rarity: int | None,
    weapon_type_id: int | None,
):
    queryset = Oggetto.objects.select_related("tipo_arma", "media")
    if not include_archived:
        queryset = queryset.filter(archiviato=False, archived_at__isnull=True)
    if query:
        queryset = queryset.filter(
            Q(nome__icontains=query)
            | Q(descrizione__icontains=query)
            | Q(tipo_1__icontains=query)
            | Q(tipo_2__icontains=query)
            | Q(tipo_3__icontains=query)
        )
    for field, value in zip(CATALOG_FILTER_POSITIONS, types):
        if value:
            queryset = queryset.filter(**{f"{field}__iexact": value})
    if rarity is not None:
        queryset = queryset.filter(rarita=rarity)
    if weapon_type_id is not None:
        queryset = queryset.filter(tipo_arma_id=weapon_type_id)
    return queryset.order_by("numero_ordine", "nome")


def _catalog_rows(queryset, *, limit: int, group: str, slot: str) -> list[Oggetto]:
    """Read the catalogue lazily so a slot-scoped search stops at the first `limit` matches.

    Compatibility depends on type aliases stored in `metadata`, so it cannot become a
    database filter without losing items. Streaming the queryset keeps the rule exact
    while still serializing only the rows the caller asked for.
    """
    if not group:
        return list(queryset[:limit])
    matching = (item for item in queryset.iterator(chunk_size=500) if item_fits_container(item, group, slot))
    return list(islice(matching, limit))


def item_catalog_payload(
    query: str = "",
    *,
    include_archived: bool = False,
    limit: int = 100,
    type_1: str = "",
    type_2: str = "",
    type_3: str = "",
    rarity: int | None = None,
    weapon_type_id: int | None = None,
    group: str = "",
    slot: str = "",
) -> dict:
    queryset = _catalog_queryset(
        query,
        include_archived=include_archived,
        types=(type_1, type_2, type_3),
        rarity=rarity,
        weapon_type_id=weapon_type_id,
    )
    rows = _catalog_rows(queryset, limit=min(limit, 10000), group=group, slot=slot)
    return {
        "items": [serialize_item(item, detailed=True) for item in rows],
        "typeOptions": [
            {
                "position": option.posizione,
                "value": option.valore,
                "label": option.label,
            }
            for option in OpzioneTipoOggetto.objects.filter(
                attiva=True,
                archived_at__isnull=True,
            ).order_by("posizione", "ordine", "etichetta", "valore")
        ],
        "rarityChoices": [
            {"value": value, "label": label}
            for value, label in Oggetto.Rarita.choices
        ],
        "effectConfiguration": effect_configuration_payload(),
        "weaponConfiguration": weapon_configuration_payload(),
        "weaponTypes": [
            {
                "id": weapon_type.id,
                "name": weapon_type.nome,
                "length": weapon_type.lunghezza,
                "power": weapon_type.potenza,
                "bonus1": weapon_type.bonus_1,
                "bonus2": weapon_type.bonus_2,
                "rules": weapon_type.rules if isinstance(weapon_type.rules, dict) else {},
            }
            for weapon_type in TipoArma.objects.order_by("nome")
        ],
    }

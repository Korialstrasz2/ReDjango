from __future__ import annotations

from itertools import islice

from django.db.models import Q

from backend.characters.selectors import serialize_item
from backend.characters.services.custom_effects import effect_configuration_payload
from backend.characters.services.inventory_rules import item_fits_container
from backend.core.weapon_rules import weapon_configuration_payload

from .models import Oggetto, OpzioneTipoOggetto, TipoArma
from .weapon_presets import WEAPON_TYPE_PRESETS


CATALOG_FILTER_POSITIONS = ("tipo_1", "tipo_2", "tipo_3")

# Sentinel a filter value can carry to mean "explicitly empty" (no region / no type
# at that position), as opposed to "" which means the filter is not applied at all.
NONE_SENTINEL = "__none__"

CATALOG_SORT_OPTIONS: dict[str, tuple[str, ...]] = {
    "": ("numero_ordine", "nome"),
    "name": ("nome",),
    "name_desc": ("-nome", "nome"),
    "rarity": ("rarita", "nome"),
    "rarity_desc": ("-rarita", "nome"),
    "weight": ("peso", "nome"),
    "weight_desc": ("-peso", "nome"),
    "value": ("valore", "nome"),
    "value_desc": ("-valore", "nome"),
}


def weapon_type_profiles() -> list[dict]:
    """Read the weapon catalogue from TipoArma, falling back to the shipped presets.

    Seeded rows keep the whole profile under ``rules["profile"]``; anything saved
    later by hand may only have the plain columns, so both are merged. Every
    reader of the catalogue — the weapon guide and the player compendium — must
    resolve a type the same way, otherwise the same weapon would describe itself
    differently on two pages.
    """
    presets = {entry["name"]: entry["profile"] for entry in WEAPON_TYPE_PRESETS}
    entries = []
    for weapon_type in TipoArma.objects.filter(archived_at__isnull=True):
        rules = weapon_type.rules if isinstance(weapon_type.rules, dict) else {}
        profile = rules.get("profile") if isinstance(rules.get("profile"), dict) else {}
        merged = {**presets.get(weapon_type.nome, {}), **profile}
        notes = merged.get("bonusNotes") or [
            note for note in (weapon_type.bonus_1, weapon_type.bonus_2) if note
        ]
        entries.append(
            {
                **merged,
                "id": weapon_type.id,
                "name": weapon_type.nome,
                "bonusNotes": notes,
                # Without a profile the creator cannot suggest modifiers, so the
                # guide lists the type as incomplete instead of inventing one.
                "incomplete": not merged.get("combatMode"),
            }
        )
    if not entries:
        entries = [
            {**entry["profile"], "id": None, "name": entry["name"]}
            for entry in WEAPON_TYPE_PRESETS
        ]
    return entries


def _catalog_queryset(
    query: str,
    *,
    include_archived: bool,
    types: tuple[str, str, str],
    rarity: int | None,
    weapon_type_id: int | None,
    special: bool | None = None,
    region: str = "",
    state: str = "",
    weight_min: float | None = None,
    weight_max: float | None = None,
    value_min: int | None = None,
    value_max: int | None = None,
    sort: str = "",
):
    queryset = Oggetto.objects.select_related("tipo_arma", "media")
    if not include_archived:
        queryset = queryset.filter(archiviato=False, archived_at__isnull=True)
    elif state == "archived":
        queryset = queryset.filter(Q(archiviato=True) | Q(archived_at__isnull=False))
    elif state == "active":
        queryset = queryset.filter(archiviato=False, archived_at__isnull=True)
    if special is not None:
        queryset = queryset.filter(speciale=special)
    if region == NONE_SENTINEL:
        queryset = queryset.filter(regione_loot="")
    elif region:
        queryset = queryset.filter(regione_loot__iexact=region)
    if query:
        queryset = queryset.filter(
            Q(nome__icontains=query)
            | Q(descrizione__icontains=query)
            | Q(tipo_1__icontains=query)
            | Q(tipo_2__icontains=query)
            | Q(tipo_3__icontains=query)
        )
    for field, value in zip(CATALOG_FILTER_POSITIONS, types):
        if value == NONE_SENTINEL:
            queryset = queryset.filter(**{field: ""})
        elif value:
            queryset = queryset.filter(**{f"{field}__iexact": value})
    if rarity is not None:
        queryset = queryset.filter(rarita=rarity)
    if weapon_type_id is not None:
        queryset = queryset.filter(tipo_arma_id=weapon_type_id)
    if weight_min is not None:
        queryset = queryset.filter(peso__gte=weight_min)
    if weight_max is not None:
        queryset = queryset.filter(peso__lte=weight_max)
    if value_min is not None:
        queryset = queryset.filter(valore__gte=value_min)
    if value_max is not None:
        queryset = queryset.filter(valore__lte=value_max)
    return queryset.order_by(*CATALOG_SORT_OPTIONS.get(sort, CATALOG_SORT_OPTIONS[""]))


def _catalog_rows(queryset, *, limit: int, offset: int, group: str, slot: str) -> list[Oggetto]:
    """Read the catalogue lazily so a slot-scoped search stops at the first `limit` matches.

    Compatibility depends on type aliases stored in `metadata`, so it cannot become a
    database filter without losing items. Streaming the queryset keeps the rule exact
    while still serializing only the rows the caller asked for.
    """
    if not group:
        return list(queryset[offset:offset + limit])
    matching = (item for item in queryset.iterator(chunk_size=500) if item_fits_container(item, group, slot))
    return list(islice(matching, offset, offset + limit))


def item_catalog_payload(
    query: str = "",
    *,
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
    type_1: str = "",
    type_2: str = "",
    type_3: str = "",
    rarity: int | None = None,
    weapon_type_id: int | None = None,
    special: bool | None = None,
    region: str = "",
    state: str = "",
    weight_min: float | None = None,
    weight_max: float | None = None,
    value_min: int | None = None,
    value_max: int | None = None,
    sort: str = "",
    group: str = "",
    slot: str = "",
) -> dict:
    queryset = _catalog_queryset(
        query,
        include_archived=include_archived,
        types=(type_1, type_2, type_3),
        rarity=rarity,
        weapon_type_id=weapon_type_id,
        special=special,
        region=region,
        state=state,
        weight_min=weight_min,
        weight_max=weight_max,
        value_min=value_min,
        value_max=value_max,
        sort=sort,
    )
    page_size = min(limit, 10000)
    offset = max(0, offset)
    rows = _catalog_rows(queryset, limit=page_size, offset=offset, group=group, slot=slot)
    # A slot-scoped search is decided in Python, so only the unscoped catalogue
    # can report a trustworthy total; the picker does not use one anyway.
    total = queryset.count() if not group else offset + len(rows)
    return {
        "items": [serialize_item(item, detailed=True) for item in rows],
        "total": total,
        "offset": offset,
        "limit": page_size,
        "hasMore": offset + len(rows) < total,
        # The default model ordering would otherwise join the DISTINCT: Django
        # adds `numero_ordine`/`nome` to the SELECT and every region comes back
        # once per item.
        "regions": sorted(
            value
            for value in Oggetto.objects.exclude(regione_loot="")
            .order_by()
            .values_list("regione_loot", flat=True)
            .distinct()
        ),
        "specialCount": Oggetto.objects.filter(speciale=True).count(),
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

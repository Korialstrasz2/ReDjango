from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from backend.core.api import ApiError
from backend.core.models import Giocatore, Oggetto, OpzioneTipoOggetto, TipoArma
from backend.core.security import effective_role, has_minimum_role
from backend.core.weapon_rules import normalize_weapon_profile
from backend.media_library.models import UploadedImage


ITEM_TYPE_FIELDS = ("tipo_1", "tipo_2", "tipo_3", "tipo_4")
ELDER_EFFECT_FIELDS = tuple(f"effetto_{index}" for index in range(1, 9))

ITEM_FIELDS = (
    "nome",
    "modello",
    "temporaneo",
    "archiviato",
    "speciale",
    "numero_ordine",
    "icona",
    "tipo_1",
    "tipo_2",
    "tipo_3",
    "tipo_4",
    "descrizione",
    "valore",
    "peso",
    "rarita",
    "lv_loot",
    "regione_loot",
    "peso_regione",
    "pa_per_attacco",
    *ELDER_EFFECT_FIELDS,
    "effects",
    "weapon_profile",
    "alchemy_profile",
    "crafting_profile",
    "notes",
)


def require_item_author(user, giocatore: Giocatore) -> None:
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER):
        raise ApiError("items.forbidden", "Solo master e amministratori possono modificare il catalogo oggetti.", status=403)


def _clean_item_payload(payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in ITEM_FIELDS:
        if field not in payload:
            continue
        value = payload[field]
        if field in {"nome", "icona", *ITEM_TYPE_FIELDS, *ELDER_EFFECT_FIELDS, "descrizione", "lv_loot", "regione_loot", "notes"}:
            value = str(value or "").strip()
            if value.casefold() == "vuoto":
                value = ""
            if field in ITEM_TYPE_FIELDS and value:
                posizione = int(field.rsplit("_", 1)[1])
                option = OpzioneTipoOggetto.objects.filter(
                    posizione=posizione,
                    valore__iexact=value,
                    attiva=True,
                    archived_at__isnull=True,
                ).first()
                if option is None:
                    raise ApiError(
                        "items.type_not_configured",
                        f"{field} deve usare un'opzione attiva configurata nell'Amministrazione Django.",
                        field,
                    )
                value = option.valore
            if field in ELDER_EFFECT_FIELDS and len(value) > 255:
                raise ApiError(
                    "items.elder_effect_too_long",
                    f"{field} non può superare 255 caratteri.",
                    field,
                )
        elif field in {"modello", "temporaneo", "archiviato", "speciale"}:
            if not isinstance(value, bool):
                raise ApiError("items.boolean_required", f"{field} deve essere Sì oppure No.", field)
        elif field in {"numero_ordine", "valore", "rarita", "pa_per_attacco"}:
            try:
                value = None if value in (None, "") else int(value)
            except (TypeError, ValueError) as exc:
                raise ApiError("items.integer_required", f"{field} deve essere un numero intero.", field) from exc
            if field == "rarita" and value is not None and value not in Oggetto.Rarita.values:
                raise ApiError(
                    "items.rarity_invalid",
                    "La rarità deve essere Unico oppure un valore da 1 a 5.",
                    field,
                )
        elif field in {"peso", "peso_regione"}:
            try:
                value = None if value in (None, "") else float(value)
            except (TypeError, ValueError) as exc:
                raise ApiError("items.number_required", f"{field} deve essere un numero.", field) from exc
            if value is not None and value < 0:
                raise ApiError("items.negative_value", f"{field} non può essere negativo.", field)
        elif field == "effects":
            if not isinstance(value, list):
                raise ApiError("items.effects_invalid", "Gli effetti devono essere una lista strutturata.", field)
            value = [entry for entry in value if isinstance(entry, dict)]
        elif field in {"weapon_profile", "alchemy_profile", "crafting_profile"}:
            if not isinstance(value, dict):
                raise ApiError("items.profile_invalid", f"{field} deve essere un oggetto strutturato.", field)
            if field == "weapon_profile":
                value = normalize_weapon_profile(value)
        values[field] = value

    if not partial or "nome" in payload:
        if not values.get("nome"):
            raise ApiError("items.name_required", "Il nome dell'oggetto è obbligatorio.", "nome")
    return values


def _relations(payload: dict[str, Any], values: dict[str, Any]) -> None:
    if "tipo_arma_id" in payload or "tipoArmaId" in payload:
        raw_id = payload.get("tipo_arma_id", payload.get("tipoArmaId"))
        weapon_type = None if raw_id in (None, "") else TipoArma.objects.get(pk=int(raw_id))
        values["tipo_arma"] = weapon_type
        # `weapon_profile` is a per-item override and is currently unused: no
        # catalogue row stores one, and `item_weapon_profile()` resolves every
        # weapon through `TipoArma.rules`, which is the effective source of
        # truth. Seeding it from the weapon type keeps the override consistent
        # with the type it was derived from whenever a caller does write one.
        if weapon_type is not None and "weapon_profile" not in values:
            rules = weapon_type.rules if isinstance(weapon_type.rules, dict) else {}
            values["weapon_profile"] = normalize_weapon_profile(rules.get("profile"))
    if "media_id" in payload or "mediaId" in payload:
        raw_id = payload.get("media_id", payload.get("mediaId"))
        values["media"] = None if raw_id in (None, "") else UploadedImage.objects.get(pk=int(raw_id))


def _refresh_characters_using(item: Oggetto) -> None:
    from backend.characters.models import Equip, Personaggio
    from backend.characters.services.inventory_rules import EQUIPMENT_SLOT_ORDER
    from backend.characters.services.refresh_personaggio import refresh_personaggio

    query = Q()
    for slot in EQUIPMENT_SLOT_ORDER:
        query |= Q(**{f"{slot}_id": item.id})
    equip_ids = Equip.objects.filter(query).values_list("id", flat=True)
    for character_id in Personaggio.objects.filter(equip_id__in=equip_ids).values_list("id", flat=True):
        refresh_personaggio(character_id)


@transaction.atomic
def create_item(user, giocatore: Giocatore, payload: dict[str, Any]) -> Oggetto:
    require_item_author(user, giocatore)
    values = _clean_item_payload(payload, partial=False)
    _relations(payload, values)
    if Oggetto.objects.filter(nome__iexact=values["nome"]).exists():
        raise ApiError("items.duplicate_name", "Esiste già un oggetto con questo nome.", "nome", 409)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    values["metadata"] = {**metadata, "sourceProject": "redjango", "source": "item_authoring"}
    return Oggetto.objects.create(**values)


@transaction.atomic
def update_item(user, giocatore: Giocatore, item_id: int, payload: dict[str, Any]) -> Oggetto:
    require_item_author(user, giocatore)
    item = Oggetto.objects.select_for_update().get(pk=item_id)
    values = _clean_item_payload(payload, partial=True)
    _relations(payload, values)
    if "nome" in values and Oggetto.objects.exclude(pk=item.pk).filter(nome__iexact=values["nome"]).exists():
        raise ApiError("items.duplicate_name", "Esiste già un oggetto con questo nome.", "nome", 409)
    for field, value in values.items():
        setattr(item, field, value)
    # The editor exposes `archiviato` as a checkbox; keep the soft-delete
    # timestamp in step with it, or unticking the box would leave the item
    # hidden from every query that filters on `archived_at`.
    if "archiviato" in values:
        item.archived_at = (item.archived_at or timezone.now()) if values["archiviato"] else None
    item.save()
    _refresh_characters_using(item)
    return item


@transaction.atomic
def save_compared_item(
    user,
    giocatore: Giocatore,
    item_id: int | None,
    identity_name: str,
    payload: dict[str, Any],
) -> tuple[Oggetto, bool]:
    """Save the editable right side of the comparer.

    The selected id and its original name form the identity lock. Keeping both
    updates that catalog row; changing either turns the right side into a new
    item. This makes cloning explicit and prevents accidental overwrites.
    """

    require_item_author(user, giocatore)
    proposed_name = str(payload.get("nome") or "").strip()
    if item_id:
        try:
            selected = Oggetto.objects.select_for_update().get(pk=item_id)
        except Oggetto.DoesNotExist as exc:
            raise ApiError("items.not_found", "L'oggetto selezionato non esiste più.", status=404) from exc
        identity_matches = (
            selected.nome.casefold() == str(identity_name or "").strip().casefold()
            and proposed_name.casefold() == selected.nome.casefold()
        )
        if identity_matches:
            return update_item(user, giocatore, selected.id, payload), False
    return create_item(user, giocatore, payload), True


@transaction.atomic
def archive_item(user, giocatore: Giocatore, item_id: int) -> Oggetto:
    require_item_author(user, giocatore)
    item = Oggetto.objects.select_for_update().get(pk=item_id)
    item.archiviato = True
    # `archiviato` is the catalogue flag and `archived_at` the V2Model soft
    # delete. Half the queries in the project filter on one and half on the
    # other, so archiving has to set both or the item stays visible somewhere.
    item.archived_at = item.archived_at or timezone.now()
    item.save(update_fields=["archiviato", "archived_at", "updated_at"])
    return item


@transaction.atomic
def restore_item(user, giocatore: Giocatore, item_id: int) -> Oggetto:
    require_item_author(user, giocatore)
    item = Oggetto.objects.select_for_update().get(pk=item_id)
    item.archiviato = False
    item.archived_at = None
    item.save(update_fields=["archiviato", "archived_at", "updated_at"])
    return item


@transaction.atomic
def set_items_special(user, giocatore: Giocatore, item_ids: list[int], special: bool) -> int:
    """Flag or clear `speciale` on several items at once.

    The flag excludes an item from every shop, and it is by far the commonest
    reason a template never appears anywhere. Reviewing thousands of legacy rows
    one modal at a time is not a workflow, so the triage list clears them in
    batches.
    """
    require_item_author(user, giocatore)
    identifiers = []
    for raw in item_ids or []:
        try:
            identifiers.append(int(raw))
        except (TypeError, ValueError) as exc:
            raise ApiError("items.id_invalid", "Identificativo oggetto non valido.", "itemIds") from exc
    if not identifiers:
        raise ApiError("items.selection_required", "Seleziona almeno un oggetto.", "itemIds")
    return Oggetto.objects.filter(id__in=identifiers).update(speciale=special, updated_at=timezone.now())

from __future__ import annotations

from django.db.models import Q

from backend.characters.selectors import serialize_item
from backend.characters.services.custom_effects import effect_configuration_payload
from backend.core.weapon_rules import weapon_configuration_payload

from .models import Oggetto, OpzioneTipoOggetto, TipoArma


def item_catalog_payload(query: str = "", *, include_archived: bool = False, limit: int = 100) -> dict:
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
    items = [serialize_item(item, detailed=True) for item in queryset.order_by("numero_ordine", "nome")[: min(limit, 10000)]]
    return {
        "items": items,
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

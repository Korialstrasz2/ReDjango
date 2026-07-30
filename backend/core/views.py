import json
import re

from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from backend.characters.services.refresh_personaggio import (
    extract_characteristic_adjustments,
    extract_formula_map,
    extract_quick_stat_adjustment,
)
from backend.combat.damage_rules import configured_damage_rules

from .api import api_response
from .defaults import CHARACTERISTIC_ADJUSTMENT_DEFAULTS, FORMULE_BASE_FORMULAS, FORMULE_BASE_VALUE_FLOAT
from .guides_it import (
    V2_GUIDE_DEFAULTS,
    race_guide_html,
    character_variable_guide_blocks,
    weapon_catalogue_guide_blocks,
)
from .item_selectors import weapon_type_profiles
from .models import GlobalModifiers, Guida
from .security import get_or_create_giocatore_for_user, security_payload


def get_authenticated_user(request):
    if not request.user.is_authenticated:
        raise PermissionDenied("Accedi per utilizzare ReDjango.")
    return request.user


@ensure_csrf_cookie
def index(request):
    return render(request, "index.html")


@require_GET
def health(request):
    return api_response(request, {"service": "ReDjango", "status": "pronto"})


def _dynamic_character_variable_blocks():
    profile = GlobalModifiers.objects.filter(name="Formule_base").first()
    if profile is None:
        base_values = FORMULE_BASE_VALUE_FLOAT
        formulas = FORMULE_BASE_FORMULAS
        value_string = {}
    else:
        base_values = dict(FORMULE_BASE_VALUE_FLOAT)
        if isinstance(profile.value_float, dict):
            base_values.update(profile.value_float)
        value_string = profile.value_string if isinstance(profile.value_string, dict) else {}
        formulas = extract_formula_map(value_string)
    characteristic_adjustments = {
        **CHARACTERISTIC_ADJUSTMENT_DEFAULTS,
        **extract_characteristic_adjustments(value_string),
    }
    return character_variable_guide_blocks(
        base_values,
        formulas,
        extract_quick_stat_adjustment(value_string),
        characteristic_adjustments,
        configured_damage_rules(),
    )


def _dynamic_weapon_catalogue_blocks():
    return weapon_catalogue_guide_blocks(weapon_type_profiles())


def _guide_blocks(raw_content):
    if not raw_content:
        return []
    try:
        blocks = json.loads(raw_content)
    except json.JSONDecodeError:
        if re.search(r"<\s*(?:h[1-6]|p|ul|ol|table|div|section)\b", raw_content, flags=re.IGNORECASE):
            return [{"type": "legacy_html", "html": race_guide_html(raw_content)}]
        return [{"type": "paragraph", "text": raw_content}]
    if not isinstance(blocks, list):
        return [{"type": "paragraph", "text": raw_content}]
    expanded = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "dynamic_character_variables":
            expanded.extend(_dynamic_character_variable_blocks())
        elif block.get("type") == "dynamic_weapon_catalogue":
            expanded.extend(_dynamic_weapon_catalogue_blocks())
        else:
            expanded.append(block)
    return expanded


def _default_guides_payload():
    return [
        {
            "id": None,
            "name": guide["nome"],
            "category": guide.get("categoria", ""),
            "order": guide.get("ordine", 0),
            "content": _guide_blocks(guide["contenuto"]),
        }
        for guide in sorted(V2_GUIDE_DEFAULTS, key=lambda item: (item.get("ordine", 0), item["nome"]))
    ]


def _guides_payload():
    guides = list(Guida.objects.order_by("ordine", "nome"))
    if not guides:
        return _default_guides_payload()
    return [
        {
            "id": guide.id,
            "name": guide.nome,
            "category": guide.categoria,
            "order": guide.ordine,
            "content": _guide_blocks(guide.contenuto),
        }
        for guide in guides
    ]


@ensure_csrf_cookie
@require_GET
def bootstrap(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    security = security_payload(user, giocatore)
    menus = [
        {"id": "dashboard", "label": "Menu principale"},
        {"id": "characters", "label": "Personaggi"},
        {"id": "media", "label": "Archivio immagini"},
        {"id": "guide", "label": "Guide"},
        {"id": "settings", "label": "Impostazioni"},
    ]
    if security["canManageGameData"]:
        menus.append(
            {
                "id": "management",
                "label": "Gestione",
                "items": [
                    {"id": "management-characters", "label": "Gestione Personaggi", "path": "/tools/characters"},
                    {"id": "management-items", "label": "Gestione Oggetti", "path": "/tools/items"},
                ],
            }
        )
    from .campaigns import campaigns_payload

    return api_response(
        request,
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "isAuthenticated": request.user.is_authenticated,
                "role": security["role"],
            },
            "security": security,
            "menus": menus,
            "guides": _guides_payload(),
            **campaigns_payload(giocatore),
        }
    )

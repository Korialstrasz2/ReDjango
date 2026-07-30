"""Strumenti di sola lettura esposti all'agente.

Ogni strumento chiama i selettori esistenti **come l'utente che ha posto la domanda**.
È la regola che tiene insieme tutto il resto: i permessi (`visibilita_limitata`,
`visibile_ai_giocatori`, i personaggi assegnati) sono già applicati là dentro, quindi
un giocatore non può estrarre dalla chat quello che la sua pagina gli nasconde.
Nessuno strumento scrive: la versione 1 dell'agente risponde e basta.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from html import unescape
from typing import Any, Callable

from django.db.models import Q
from django.utils.html import strip_tags

from backend.characters.alchemy_selectors import alchemy_creation_payload
from backend.characters.competence_selectors import competence_catalog_payload
from backend.characters.models import Personaggio
from backend.characters.note_selectors import character_notes_payload
from backend.characters.selectors import ordered_personaggi_for, personaggio_detail
from backend.characters.services.inventory_rules import calculate_weight_breakdown
from backend.combat.models import CombatModifier, CombatModifierState, MapMetadata, MapParticipant
from backend.core.game_variable_selectors import game_variables_payload
from backend.core.item_selectors import item_catalog_payload
from backend.core.models import (
    CampaignLoreEntry,
    Curiosita,
    DatiCampagna,
    Giocatore,
    Guida,
    HallOfFameCharacter,
    Negozio,
    OpzioneTipoOggetto,
    ReagenteAlchemico,
    SettingDefinition,
    Skill,
    TipoArma,
)
from backend.core.security import effective_role, has_minimum_role
from backend.core.settings_selectors import ADMIN_MANAGED_SETTING_KEYS
from backend.core.skill_pricing import skill_price
from backend.core.skill_selectors import character_skill_summaries, serialize_skill, skill_catalog_payload, skill_character_analysis
from backend.core.spell_services import serialize_spell
from backend.dice_tools.selectors import dice_history_payload
from backend.lore.selectors import lore_payload, resolve_campaign
from backend.market.selectors import market_overview, shop_detail
from backend.media_library.travel_selectors import travel_maps_payload


MAXIMUM_TOOL_RESULT_CHARACTERS = 24000


@dataclass(frozen=True)
class AITool:
    name: str
    description: str
    schema: dict[str, Any]
    run: Callable[..., Any]
    scope: str = "cataloghi"
    minimum_role: str = Giocatore.ROLE_USER
    read_only: bool = True

    def definition(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "input_schema": self.schema}


def _object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _is_master(user, giocatore: Giocatore) -> bool:
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)


def _accessible_character(user, giocatore: Giocatore, name: str) -> Personaggio | None:
    """Risolve un personaggio per nome, ma solo fra quelli che l'utente può già vedere."""

    allowed = ordered_personaggi_for(giocatore, include_all=_is_master(user, giocatore))
    needle = str(name or "").strip().casefold()
    if not needle:
        return next(iter(allowed), None)
    exact = next((entry for entry in allowed if entry.nome.casefold() == needle), None)
    return exact or next((entry for entry in allowed if needle in entry.nome.casefold()), None)


def _search_items(user, giocatore: Giocatore, query: str = "", limit: int = 12) -> dict[str, Any]:
    catalog = item_catalog_payload(str(query or ""), limit=max(1, min(int(limit or 12), 40)))
    return {
        "oggetti": [
            {
                "id": item.get("id"),
                "nome": item.get("name"),
                "tipi": item.get("types") or [],
                "rarita": item.get("rarityLabel") or item.get("rarity"),
                "peso": item.get("weight"),
                "valore": item.get("value"),
                "descrizione": item.get("description"),
                "tipoArma": item.get("weaponType"),
                "effetti": item.get("effects"),
            }
            for item in catalog.get("items", [])
        ]
    }


CHARACTER_SHEET_BASE_KEYS = ("id", "name")
CHARACTER_SHEET_SECTIONS: dict[str, tuple[str, ...]] = {
    "riepilogo": ("type", "races", "level", "coins", "resources", "encumbrance", "details"),
    "economia": ("coins", "coinStorage", "encumbrance"),
    "caratteristiche": ("characteristics", "primaryTotals", "diceModifiers", "criticalThresholds"),
    "combattimento": ("combat", "resistances", "modifiedStats"),
    "inventario": ("inventory", "quiver", "utilityContainer", "campaignContainer", "encumbrance"),
    "equipaggiamento": ("equipment", "appearance"),
    "esperienza": ("xp", "level"),
    "effetti": ("effects",),
    "competenze": ("competencies",),
    "note": ("notes",),
    "reagenti": ("reagents",),
}
DEFAULT_CHARACTER_SHEET_SECTION = "riepilogo"


def _character_sheet(user, giocatore: Giocatore, nome: str = "", sezione: str = "") -> dict[str, Any]:
    character = _accessible_character(user, giocatore, nome)
    if character is None:
        return {"errore": "Nessun personaggio accessibile con questo nome."}
    requested = str(sezione or "").strip().casefold()
    resolved = requested if requested in CHARACTER_SHEET_SECTIONS else DEFAULT_CHARACTER_SHEET_SECTION
    keys = CHARACTER_SHEET_BASE_KEYS + CHARACTER_SHEET_SECTIONS[resolved]
    sheet = personaggio_detail(character, can_manage_items=_is_master(user, giocatore), include_skills=False) or {}
    return {
        "sezione": resolved,
        "sezioniDisponibili": sorted(CHARACTER_SHEET_SECTIONS),
        "personaggio": {key: sheet.get(key) for key in keys if key in sheet},
    }


def _search_skills(user, giocatore: Giocatore, query: str = "") -> dict[str, Any]:
    catalog = skill_catalog_payload(None, query=str(query or ""))
    return {
        "abilita": [
            {
                "nome": skill.get("name"),
                "famiglia": skill.get("familyName"),
                "gruppo": skill.get("familyGroup"),
                "costoPe": skill.get("baseXpCost"),
                "magia": skill.get("magic"),
                "descrizione": skill.get("description"),
            }
            for skill in (catalog.get("skills") or [])[:25]
        ]
    }


def _competences(user, giocatore: Giocatore, nome: str = "") -> dict[str, Any]:
    character = _accessible_character(user, giocatore, nome)
    if character is None:
        return {"errore": "Nessun personaggio accessibile con questo nome."}
    catalog = competence_catalog_payload(character)
    return {
        "personaggio": character.nome,
        "competenze": [
            {
                "nome": entry.get("name"),
                "attributo": entry.get("attribute"),
                "rangoBase": entry.get("baseRank"),
                "maestria": entry.get("masteryRank"),
                "extraEfficace": entry.get("effectiveExtra"),
                "modificatoreTiro": entry.get("rollModifier"),
            }
            for entry in catalog.get("competencies") or []
        ],
    }


def _lore(user, giocatore: Giocatore, argomento: str = "") -> dict[str, Any]:
    payload = lore_payload(user, giocatore)
    requested = str(argomento or "").strip()

    def normalize(value: object) -> str:
        text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()

    needle = normalize(requested)
    requested_tokens = set(needle.split())
    generic_words = {
        "che", "quale", "quali", "abbiamo", "con", "le", "la", "i", "rapporti",
        "rapporto", "reputazione", "reputazioni", "fazione", "fazioni", "standing",
    }
    if needle and set(needle.split()).issubset(generic_words):
        needle = ""

    def matches(entry: dict[str, Any], aliases: str = "") -> bool:
        if not needle:
            return True
        searchable = normalize(f"{aliases} {json.dumps(entry, ensure_ascii=False)}")
        return all(token in searchable for token in needle.split())

    factions = [
        {
            "nome": item.get("name"),
            "reputazione": item.get("reputation"),
            "livello": (item.get("tier") or {}).get("label") if isinstance(item.get("tier"), dict) else item.get("tier"),
            "descrizione": item.get("description"),
        }
        for item in payload.get("factions", [])
        if matches(item, "fazione fazioni reputazione reputazioni rapporti standing")
    ][:20]
    npcs = [
        {
            "nome": item.get("name"),
            "ruolo": item.get("role"),
            "fazione": item.get("factionName"),
            "descrizione": item.get("description"),
        }
        for item in payload.get("npcs", [])
        if matches(item, "personaggio personaggi npc fazione")
    ][:20]
    events = [
        {"titolo": item.get("title"), "motivo": item.get("reason"), "giorno": item.get("campaignDay")}
        for item in payload.get("events", [])
        if matches(item, "evento eventi reputazione reputazioni")
    ][:20]
    if requested_tokens & {"reputazione", "reputazioni", "fazione", "fazioni", "standing", "rapporti", "rapporto"}:
        npcs = []
        if not requested_tokens & {"evento", "eventi", "motivo", "motivi", "storia"}:
            events = []
    total_factions = len(payload.get("factions", []))
    status = "ok"
    if not total_factions:
        status = "nessun_dato"
    elif needle and not factions and not npcs and not events:
        status = "filtro_senza_risultati"

    return {
        "campagna": (payload.get("campaign") or {}).get("name"),
        "stato": status,
        "filtroRichiesto": requested,
        "fazioniTotali": total_factions,
        "fazioni": factions,
        "personaggi": npcs,
        "eventi": events,
    }


def _market(user, giocatore: Giocatore, negozio: str = "") -> dict[str, Any]:
    overview = market_overview(giocatore)
    shops = overview.get("shops", [])
    needle = str(negozio or "").strip().casefold()
    if needle:
        shops = [shop for shop in shops if needle in str(shop.get("name") or "").casefold()]
    return {
        "negozi": [
            {
                "nome": shop.get("name"),
                "tipo": shop.get("categoryKey"),
                "livello": shop.get("level"),
                "localita": shop.get("placeName"),
                "regione": shop.get("regionName"),
                "oggettiInVendita": shop.get("distinctStockCount"),
            }
            for shop in shops[:25]
        ]
    }


GUIDE_EXCERPT_RADIUS = 900
MAXIMUM_GUIDE_EXCERPTS = 3
MAXIMUM_GUIDES_RETURNED = 4


def _guide_plain_text(contenuto: str) -> str:
    """Appiattisce i blocchi di una guida in testo semplice cercabile.

    `Guida.contenuto` è un TextField che *contiene* JSON: una lista di blocchi
    tipizzati (`legacy_html`, `paragraph`, `callout`, `heading`, `warning`, `code`,
    `list`). Va letto e appiattito, non ri-serializzato: `json.dumps` su questa
    stringa la incapsulerebbe una seconda volta, trasformando ogni `"` in `\\"` e
    ogni interruzione di riga in `\\r\\n`, così il budget di caratteri finisce in
    escape invece che in regole.
    """

    try:
        blocks = json.loads(contenuto or "[]")
    except (TypeError, ValueError):
        return str(contenuto or "")
    if not isinstance(blocks, list):
        return str(contenuto or "")

    parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "legacy_html":
            parts.append(unescape(strip_tags(str(block.get("html") or ""))))
            continue
        for key in ("title", "text"):
            value = block.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value)
        items = block.get("items")
        if isinstance(items, list):
            parts.extend(str(item) for item in items if isinstance(item, (str, int, float)))
    # Lo stripping dell'HTML lascia lunghe scie di righe vuote: comprimerle qui
    # significa che il raggio dell'estratto porta regole e non spazi.
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", "\n".join(parts))).strip()


def _guide_excerpts(text: str, needle: str) -> list[str]:
    """Le finestre di testo più dense di occorrenze, non l'inizio del documento.

    Due correzioni, entrambe necessarie su una guida da 58.000 caratteri con
    indice interno:

    - restituire i primi N caratteri consegnava l'indice e mai la risposta,
      perché le regole cercate stanno a metà documento;
    - scandire le occorrenze in ordine consumava tutti gli estratti sulle voci
      dell'indice, che citano il termine prima della sezione che lo spiega.

    Si scelgono quindi le finestre che contengono più occorrenze: una voce
    d'indice nomina il termine una volta, la sezione che lo definisce lo ripete.
    """

    if not needle:
        return [text[: GUIDE_EXCERPT_RADIUS * 2]] if text else []

    low = text.casefold()
    offsets: list[int] = []
    start = 0
    while True:
        found = low.find(needle, start)
        if found < 0:
            break
        offsets.append(found)
        start = found + len(needle)
    if not offsets:
        return []

    remaining = set(offsets)
    excerpts: list[str] = []
    while remaining and len(excerpts) < MAXIMUM_GUIDE_EXCERPTS:
        # A parità di densità vince l'occorrenza più avanti nel documento: l'indice
        # sta sempre in testa, il corpo delle regole dopo.
        centre = max(
            remaining,
            key=lambda offset: (
                sum(1 for other in remaining if abs(other - offset) <= GUIDE_EXCERPT_RADIUS),
                offset,
            ),
        )
        left = max(0, centre - GUIDE_EXCERPT_RADIUS)
        right = min(len(text), centre + len(needle) + GUIDE_EXCERPT_RADIUS)
        prefix = "…" if left > 0 else ""
        suffix = "…" if right < len(text) else ""
        excerpts.append(f"{prefix}{text[left:right].strip()}{suffix}")
        remaining = {offset for offset in remaining if not left <= offset < right}
    return excerpts


def _rules_guide(user, giocatore: Giocatore, argomento: str = "") -> dict[str, Any]:
    requested = str(argomento or "").strip()
    needle = requested.casefold()
    guides = list(Guida.objects.filter(archived_at__isnull=True).order_by("categoria", "ordine", "nome"))
    found: list[dict[str, Any]] = []
    matched = 0
    for guide in guides:
        text = _guide_plain_text(guide.contenuto)
        if needle and needle not in f"{guide.nome} {text}".casefold():
            continue
        matched += 1
        if len(found) >= MAXIMUM_GUIDES_RETURNED:
            continue
        found.append(
            {
                "nome": guide.nome,
                "categoria": guide.categoria,
                "estratti": _guide_excerpts(text, needle),
            }
        )
    status = "ok"
    if not guides:
        status = "nessun_dato"
    elif not matched:
        status = "filtro_senza_risultati"
    return {
        "stato": status,
        "filtroRichiesto": requested,
        "guideTotali": len(guides),
        "guideCorrispondenti": matched,
        "guide": found,
    }


def _game_variables(user, giocatore: Giocatore) -> dict[str, Any]:
    if not _is_master(user, giocatore):
        return {"errore": "Le variabili di gioco sono riservate a Master e Amministratori."}
    payload = game_variables_payload()
    return {
        "profilo": payload.get("profile"),
        "gruppi": [
            {
                "nome": group.get("label"),
                "campi": [{"nome": field.get("label"), "valore": field.get("value")} for field in group.get("fields", [])],
            }
            for group in payload.get("groups", [])
        ][:12],
    }


# --- Scope "personaggi": dati del personaggio oltre alla scheda base -------------


def _character_skills(user, giocatore: Giocatore, nome: str = "") -> dict[str, Any]:
    character = _accessible_character(user, giocatore, nome)
    if character is None:
        return {"errore": "Nessun personaggio accessibile con questo nome."}
    summaries = character_skill_summaries(character)
    progression = skill_character_analysis(character).get("progression", {})
    return {
        "personaggio": character.nome,
        "progressione": progression,
        "abilitaSbloccate": [
            {
                "nome": entry.get("name"),
                "famiglia": entry.get("familyName"),
                "gruppo": entry.get("familyGroup"),
                "magia": entry.get("magic"),
                "costoPe": entry.get("xpCost"),
                "descrizione": entry.get("description"),
            }
            for entry in summaries
        ],
    }


def _character_notes(user, giocatore: Giocatore, nome: str = "") -> dict[str, Any]:
    character = _accessible_character(user, giocatore, nome)
    if character is None:
        return {"errore": "Nessun personaggio accessibile con questo nome."}
    payload = character_notes_payload(character)
    return {"personaggio": character.nome, "note": payload.get("sections", {})}


def _character_alchemy(user, giocatore: Giocatore, nome: str = "") -> dict[str, Any]:
    character = _accessible_character(user, giocatore, nome)
    if character is None:
        return {"errore": "Nessun personaggio accessibile con questo nome."}
    payload = alchemy_creation_payload(character)
    bag = payload.get("bag", {})
    return {
        "personaggio": character.nome,
        "sacca": {
            "capacita": bag.get("capacity"),
            "occupata": bag.get("occupied"),
            "residua": bag.get("remaining"),
            "scorte": [row for row in bag.get("stock", []) if row.get("quantity")],
        },
        "set": payload.get("sets"),
        "famiglieDiPozioni": payload.get("potionFamilies"),
        "regole": payload.get("rules"),
    }


# --- Scope "cataloghi": consultazioni indipendenti dal personaggio --------------


def _search_spells(user, giocatore: Giocatore, query: str = "") -> dict[str, Any]:
    needle = str(query or "").strip()
    skills = Skill.objects.filter(archived_at__isnull=True, spell_definition__isnull=False).select_related(
        "famiglia", "famiglia__gruppo", "spell_definition"
    )
    if needle:
        skills = skills.filter(Q(nome__icontains=needle) | Q(descrizione__icontains=needle))
    results = []
    for skill in skills.order_by("famiglia__ordine", "spell_definition__tier", "nome")[:20]:
        spell = serialize_spell(skill)
        pricing = skill_price(skill, None)
        results.append(
            {
                "nome": skill.nome,
                "famiglia": skill.famiglia.nome,
                "livello": spell.get("tierLabel") if spell else None,
                "gittata": spell.get("range") if spell else "",
                "formula": spell.get("formula") if spell else "",
                "costoBase": pricing.get("baseCost"),
                "descrizione": skill.descrizione,
            }
        )
    return {"incantesimi": results}


def _weapon_types(user, giocatore: Giocatore, query: str = "") -> dict[str, Any]:
    needle = str(query or "").strip()
    weapons = TipoArma.objects.filter(archived_at__isnull=True).order_by("nome")
    if needle:
        weapons = weapons.filter(nome__icontains=needle)
    return {
        "tipiArma": [
            {
                "nome": weapon.nome,
                "lunghezza": weapon.lunghezza,
                "potenza": weapon.potenza,
                "bonus1": weapon.bonus_1,
                "bonus2": weapon.bonus_2,
            }
            for weapon in weapons[:30]
        ],
        "categorieOggetto": [
            {"posizione": option.posizione, "valore": option.label}
            for option in OpzioneTipoOggetto.objects.filter(attiva=True, archived_at__isnull=True).order_by(
                "posizione", "ordine"
            )
        ],
    }


def _reagents(user, giocatore: Giocatore, colore: str = "") -> dict[str, Any]:
    reagents = ReagenteAlchemico.objects.filter(attivo=True, archived_at__isnull=True).order_by("ordine", "livello", "nome")
    needle = str(colore or "").strip().casefold()
    if needle:
        reagents = reagents.filter(colore=needle)
    return {
        "reagenti": [
            {"nome": reagent.nome, "colore": reagent.get_colore_display(), "livello": reagent.livello}
            for reagent in reagents
        ]
    }


# --- Scope "mercato": negozi oltre all'elenco base ------------------------------


def _shop_stock(user, giocatore: Giocatore, negozio: str = "", oggetto: str = "") -> dict[str, Any]:
    overview = market_overview(giocatore)
    shops = overview.get("shops", [])
    needle_shop = str(negozio or "").strip().casefold()
    if needle_shop:
        shops = [shop for shop in shops if needle_shop in str(shop.get("name") or "").casefold()]
    if not shops:
        return {"errore": "Nessun negozio trovato con questo nome."}
    needle_item = str(oggetto or "").strip().casefold()
    result = []
    for summary in shops[:5]:
        shop = Negozio.objects.filter(pk=summary["id"]).first()
        if shop is None:
            continue
        entries = shop_detail(shop).get("stock", [])
        if needle_item:
            entries = [entry for entry in entries if needle_item in str((entry.get("item") or {}).get("name") or "").casefold()]
        result.append(
            {
                "negozio": summary.get("name"),
                "oggettiInVendita": [
                    {
                        "nome": (entry.get("item") or {}).get("name"),
                        "quantita": entry.get("quantity"),
                        "prezzoUnitario": entry.get("unitPrice"),
                    }
                    for entry in entries[:30]
                ],
            }
        )
    return {"negozi": result}


# --- Scope "campagna": lore, timeline, viaggio oltre alla panoramica base -------


def _faction_relations(user, giocatore: Giocatore) -> dict[str, Any]:
    if not _is_master(user, giocatore):
        return {"errore": "La rete di relazioni fra fazioni è riservata a Master e Amministratori."}
    payload = lore_payload(user, giocatore)
    names = {faction["id"]: faction["name"] for faction in payload.get("factions", [])}
    relations = [
        {"da": faction.get("name"), "a": names.get(relation.get("targetId"), "?"), "coefficiente": relation.get("coefficient")}
        for faction in payload.get("factions", [])
        for relation in faction.get("relations", [])
    ]
    return {"campagna": (payload.get("campaign") or {}).get("name"), "relazioni": relations}


def _reputation_events(user, giocatore: Giocatore, fazione: str = "") -> dict[str, Any]:
    payload = lore_payload(user, giocatore)
    needle = str(fazione or "").strip().casefold()
    events = payload.get("events", [])
    if needle:
        events = [
            event for event in events
            if any(needle in str(effect.get("factionName") or "").casefold() for effect in event.get("effects", []))
        ]
    return {
        "campagna": (payload.get("campaign") or {}).get("name"),
        "eventi": [
            {
                "titolo": event.get("title"),
                "motivo": event.get("reason"),
                "giorno": event.get("campaignDay"),
                "effetti": [
                    {
                        "fazione": effect.get("factionName"),
                        "delta": effect.get("delta"),
                        "precedente": effect.get("previous"),
                        "risultante": effect.get("resulting"),
                        "propagato": effect.get("propagated"),
                    }
                    for effect in event.get("effects", [])
                ],
            }
            for event in events[:20]
        ],
    }


def _lore_entries(user, giocatore: Giocatore, argomento: str = "") -> dict[str, Any]:
    campaign = resolve_campaign(giocatore)
    if campaign is None:
        return {"errore": "Nessuna campagna attiva."}
    entries = CampaignLoreEntry.objects.filter(campagna=campaign, archived_at__isnull=True)
    if not _is_master(user, giocatore):
        # "dm" è testo privato del Master: mai attraversare questo confine, indipendentemente dal filtro.
        entries = entries.exclude(visibilita="dm")
    needle = str(argomento or "").strip()
    if needle:
        entries = entries.filter(Q(nome__icontains=needle) | Q(sommario__icontains=needle))
    return {
        "voci": [
            {"nome": entry.nome, "tipo": entry.tipo, "sommario": entry.sommario, "stato": entry.stato}
            for entry in entries.order_by("tipo", "nome")[:20]
        ]
    }


def _timeline(user, giocatore: Giocatore, argomento: str = "") -> dict[str, Any]:
    payload = lore_payload(user, giocatore)
    events = payload.get("timelineEvents", [])
    needle = str(argomento or "").strip().casefold()
    if needle:
        events = [event for event in events if needle in f"{event.get('title')} {event.get('description')}".casefold()]
    return {
        "campagna": (payload.get("campaign") or {}).get("name"),
        "eventi": [
            {"titolo": event.get("title"), "data": event.get("dateLabel"), "descrizione": event.get("description")}
            for event in events[:20]
        ],
    }


def _curiosities(user, giocatore: Giocatore, argomento: str = "") -> dict[str, Any]:
    curiosities = Curiosita.objects.filter(archived_at__isnull=True)
    if not _is_master(user, giocatore):
        curiosities = curiosities.filter(visibile=True)
    needle = str(argomento or "").strip()
    if needle:
        curiosities = curiosities.filter(Q(nome__icontains=needle) | Q(descrizione__icontains=needle))
    return {
        "curiosita": [
            {"nome": item.nome, "categoria": item.categoria, "descrizione": item.descrizione}
            for item in curiosities.order_by("categoria", "nome")[:20]
        ]
    }


def _hall_of_fame(user, giocatore: Giocatore) -> dict[str, Any]:
    entries = HallOfFameCharacter.objects.filter(archived_at__isnull=True).order_by("ordine", "nome")
    return {
        "personaggi": [{"nome": entry.nome, "campagna": entry.campaign, "descrizione": entry.descrizione} for entry in entries[:30]]
    }


def _campaign_state(user, giocatore: Giocatore) -> dict[str, Any]:
    campaign = giocatore.active_campaign or DatiCampagna.objects.filter(attiva=True, archived_at__isnull=True).first()
    if campaign is None:
        return {"errore": "Nessuna campagna attiva."}
    payload = {
        "nome": campaign.nome,
        "giorno": campaign.giorni_da_inizio,
        "ora": campaign.ora_corrente,
        "meteo": campaign.meteo,
        "moneteCondivise": campaign.monete_condivise,
    }
    if _is_master(user, giocatore):
        payload["noteCondivise"] = campaign.note_condivise
        payload["risorseSpeciali"] = campaign.risorse_speciali
    return payload


def _travel_maps(user, giocatore: Giocatore) -> dict[str, Any]:
    payload = travel_maps_payload(user, giocatore)
    campaign = payload.get("campaign")
    return {
        "campagna": campaign.get("name") if campaign else None,
        "mappe": [{"nome": entry.get("name"), "predefinita": entry.get("isDefault")} for entry in payload.get("maps", [])],
    }


# --- Scope "dadi": storico e statistiche dei tiri, riservati al Master ---------


def _dice_history(user, giocatore: Giocatore, giocatore_nome: str = "", limite: int = 20) -> dict[str, Any]:
    if not _is_master(user, giocatore):
        return {"errore": "Lo storico dei tiri del gruppo è riservato a Master e Amministratori."}
    payload = dice_history_payload(user, giocatore, player=str(giocatore_nome or ""), limit=max(1, min(int(limite or 20), 100)))
    return {
        "totale": payload.get("total"),
        "tiri": [
            {
                "giocatore": roll.get("playerName"),
                "personaggio": roll.get("characterName"),
                "notazione": roll.get("notation"),
                "risultati": roll.get("rolls"),
                "totale": roll.get("total"),
            }
            for roll in payload.get("rolls", [])
        ],
    }


def _dice_statistics(user, giocatore: Giocatore) -> dict[str, Any]:
    if not _is_master(user, giocatore):
        return {"errore": "Le statistiche dei tiri del gruppo sono riservate a Master e Amministratori."}
    payload = dice_history_payload(user, giocatore, limit=500, include_statistics=True)
    return payload.get("statistics", {})


# --- Scope "combattimento": stato leggero, non il payload completo della mappa -


def _combat_state(user, giocatore: Giocatore, mappa: str = "") -> dict[str, Any]:
    maps = MapMetadata.objects.filter(archived_at__isnull=True)
    needle = str(mappa or "").strip()
    selected = maps.filter(name__icontains=needle).first() if needle else None
    if selected is None:
        selected = maps.filter(is_default=True).first() or maps.first()
    if selected is None:
        return {"errore": "Nessuna mappa di combattimento configurata."}
    participants = (
        MapParticipant.objects.filter(map=selected, active=True).select_related("character").order_by("order", "id")
    )
    rows = []
    for participant in participants:
        character = participant.character
        totals = character.tot if isinstance(character.tot, dict) else {}
        maximum_pf = max(0, int(float(totals.get("pf", 0) or 0)))
        rows.append(
            {
                "nome": character.nome,
                "livello": character.livello,
                "pf": {"attuali": max(0, maximum_pf - character.danno), "massimi": maximum_pf},
            }
        )
    return {"mappa": selected.name, "partecipanti": rows}


def _combat_modifiers(user, giocatore: Giocatore, mappa: str = "") -> dict[str, Any]:
    modifiers = CombatModifier.objects.filter(active=True, archived_at__isnull=True).order_by("order", "name")
    maps = MapMetadata.objects.filter(archived_at__isnull=True)
    needle = str(mappa or "").strip()
    selected = maps.filter(name__icontains=needle).first() if needle else None
    if selected is None:
        selected = maps.filter(is_default=True).first() or maps.first()
    active_ids: set[int] = set()
    if selected is not None:
        active_ids = set(CombatModifierState.objects.filter(map=selected, enabled=True).values_list("modifier_id", flat=True))
    return {
        "mappa": selected.name if selected else None,
        "modificatori": [
            {
                "nome": modifier.name,
                "ambito": modifier.scope,
                "bonusAttacco": modifier.attack_bonus,
                "bonusDanno": modifier.damage_bonus,
                "penetrazioneFissa": modifier.penetration_flat,
                "penetrazionePercentuale": modifier.penetration_percent,
                "attivoOra": modifier.id in active_ids,
                "descrizione": modifier.description,
            }
            for modifier in modifiers
        ],
    }


# --- Scope "gestione": riservato a Master e Amministratori ----------------------


def _players(user, giocatore: Giocatore) -> dict[str, Any]:
    if not _is_master(user, giocatore):
        return {"errore": "L'elenco dei giocatori è riservato a Master e Amministratori."}
    role_labels = dict(Giocatore.ROLE_CHOICES)
    players = (
        Giocatore.objects.select_related("active_character", "active_campaign")
        .filter(archived_at__isnull=True)
        .order_by("nome")
    )
    return {
        "giocatori": [
            {
                "nome": player.display_name or player.nome,
                "ruolo": role_labels.get(player.role, player.role),
                "personaggioAttivo": player.active_character.nome if player.active_character_id else None,
                "campagnaAttiva": player.active_campaign.nome if player.active_campaign_id else None,
            }
            for player in players
        ]
    }


def _settings_overview(user, giocatore: Giocatore) -> dict[str, Any]:
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_ADMIN):
        return {"errore": "Le impostazioni globali sono riservate agli Amministratori."}
    # `ADMIN_MANAGED_SETTING_KEYS` include i codici di accesso Master/Admin: restano
    # esclusi anche per un Amministratore, perché sono credenziali e non dati di gioco.
    definitions = (
        SettingDefinition.objects.filter(active=True, archived_at__isnull=True)
        .exclude(key__in=ADMIN_MANAGED_SETTING_KEYS)
        .order_by("category", "order", "key")
    )
    return {
        "impostazioni": [
            {
                "chiave": setting.key,
                "etichetta": setting.label,
                "categoria": setting.category,
                "valore": setting.value if setting.value is not None else setting.default_value,
            }
            for setting in definitions
        ]
    }


# --- Strumenti compositi: una giunzione deterministica invece di più chiamate --


def _can_afford(user, giocatore: Giocatore, oggetto: str = "", negozio: str = "") -> dict[str, Any]:
    character = _accessible_character(user, giocatore, "")
    if character is None:
        return {"errore": "Nessun personaggio attivo per questo giocatore."}
    needle_item = str(oggetto or "").strip().casefold()
    if not needle_item:
        return {"errore": "Indica il nome dell'oggetto da cercare."}
    overview = market_overview(giocatore)
    shops = overview.get("shops", [])
    needle_shop = str(negozio or "").strip().casefold()
    if needle_shop:
        shops = [shop for shop in shops if needle_shop in str(shop.get("name") or "").casefold()]

    matches = []
    for summary in shops[:10]:
        shop = Negozio.objects.filter(pk=summary["id"]).first()
        if shop is None:
            continue
        for entry in shop_detail(shop).get("stock", []):
            name = str((entry.get("item") or {}).get("name") or "")
            if needle_item in name.casefold():
                price = int(entry.get("unitPrice") or 0)
                matches.append(
                    {
                        "negozio": summary.get("name"),
                        "oggetto": name,
                        "prezzoUnitario": price,
                        "quantitaDisponibile": entry.get("quantity"),
                        "permesso": character.monete >= price,
                    }
                )
    if not matches:
        return {"errore": "Nessuna corrispondenza in questi negozi.", "monete": character.monete}
    return {"personaggio": character.nome, "monete": character.monete, "risultati": matches[:10]}


def _skill_analysis(user, giocatore: Giocatore, nome: str = "") -> dict[str, Any]:
    character = _accessible_character(user, giocatore, "")
    if character is None:
        return {"errore": "Nessun personaggio attivo per questo giocatore."}
    needle = str(nome or "").strip()
    if not needle:
        return {"errore": "Indica il nome dell'abilità da analizzare."}
    skill = (
        Skill.objects.filter(archived_at__isnull=True, nome__icontains=needle)
        .select_related("famiglia", "famiglia__gruppo")
        .first()
    )
    if skill is None:
        return {"errore": "Nessuna abilità trovata con questo nome."}
    xp_labels = {"general": "Generali", "red": "Rossi", "green": "Verdi", "blue": "Blu"}
    serialized = serialize_skill(skill, character=character)
    unlock = serialized["unlock"]
    return {
        "personaggio": character.nome,
        "abilita": skill.nome,
        "famiglia": skill.famiglia.nome,
        "costoPe": serialized["pricing"]["calculatedCost"],
        "peConsentiti": [xp_labels.get(pool, pool) for pool in unlock["allowedXpPools"]],
        "giaSbloccata": unlock["owned"],
        "puoSbloccarla": unlock["canUnlock"],
        "motiviBlocco": unlock["blockedReasons"],
    }


def _faction_history(user, giocatore: Giocatore, fazione: str = "") -> dict[str, Any]:
    needle = str(fazione or "").strip()
    if not needle:
        return {"errore": "Indica il nome della fazione."}
    payload = lore_payload(user, giocatore)
    needle_cf = needle.casefold()
    faction = next((item for item in payload.get("factions", []) if needle_cf in str(item.get("name") or "").casefold()), None)
    if faction is None:
        return {"errore": "Nessuna fazione trovata con questo nome."}
    timeline = []
    for event in payload.get("events", []):
        effect = next((item for item in event.get("effects", []) if item.get("factionName") == faction.get("name")), None)
        if effect is None:
            continue
        timeline.append(
            {
                "giorno": event.get("campaignDay"),
                "motivo": event.get("reason"),
                "delta": effect.get("delta"),
                "precedente": effect.get("previous"),
                "risultante": effect.get("resulting"),
            }
        )
    return {
        "fazione": faction.get("name"),
        "reputazioneAttuale": faction.get("reputation"),
        "livello": (faction.get("tier") or {}).get("label"),
        "storiaEventi": sorted(timeline, key=lambda row: row.get("giorno") or 0),
    }


def _group_summary(user, giocatore: Giocatore) -> dict[str, Any]:
    if not _is_master(user, giocatore):
        return {"errore": "Il riepilogo del gruppo è riservato a Master e Amministratori."}
    characters = ordered_personaggi_for(giocatore, include_all=True)
    rows = []
    for character in characters:
        totals = character.tot if isinstance(character.tot, dict) else {}
        maximum_pf = max(0, int(float(totals.get("pf", 0) or 0)))
        rows.append(
            {
                "nome": character.nome,
                "livello": character.livello,
                "monete": character.monete,
                "pf": {"attuali": max(0, maximum_pf - character.danno), "massimi": maximum_pf},
                "peGenerali": character.pe_generali,
            }
        )
    return {"personaggi": rows[:30]}


def _carrying_capacity(user, giocatore: Giocatore, nome: str = "") -> dict[str, Any]:
    character = _accessible_character(user, giocatore, nome)
    if character is None:
        return {"errore": "Nessun personaggio accessibile con questo nome."}
    totals = character.tot if isinstance(character.tot, dict) else {}
    breakdown = calculate_weight_breakdown(character, totals)
    load_step = breakdown["loadStep"]
    margin = (load_step - (breakdown["total"] % load_step)) if load_step else 0
    sheet = personaggio_detail(character, can_manage_items=_is_master(user, giocatore), include_skills=False) or {}
    inventory = sheet.get("inventory", {})
    quiver = sheet.get("quiver", {})
    return {
        "personaggio": character.nome,
        "zaino": {"capacita": inventory.get("capacity"), "occupati": inventory.get("occupied")},
        "faretra": {"capacita": quiver.get("capacity"), "occupati": quiver.get("occupied")},
        "peso": breakdown,
        "pesoResiduoPrimaDelProssimoMalus": round(margin, 2),
    }


AI_TOOLS: list[AITool] = [
    AITool(
        name="cerca_oggetti",
        description="Cerca oggetti nel catalogo per nome, tipo o descrizione. Usalo per domande su armi, armature, pozioni, prezzi, pesi ed effetti.",
        schema=_object_schema(
            {
                "query": {"type": "string", "description": "Testo da cercare, per esempio «spada lunga» o «pozione»."},
                "limit": {"type": "integer", "description": "Numero massimo di oggetti, da 1 a 40."},
            }
        ),
        run=_search_items,
    ),
    AITool(
        name="scheda_personaggio",
        description=(
            "Legge la scheda di un personaggio accessibile a chi sta chiedendo. Usa `sezione` per scegliere cosa leggere: "
            "riepilogo (predefinita: monete, livello, razze, risorse, ingombro), economia (monete e ingombro monete), "
            "caratteristiche, combattimento, inventario, equipaggiamento, esperienza (PE), effetti, competenze, note, reagenti. "
            "Per «quante monete ho» usa la sezione economia o riepilogo."
        ),
        schema=_object_schema(
            {
                "nome": {"type": "string", "description": "Nome del personaggio. Vuoto per quello attivo."},
                "sezione": {
                    "type": "string",
                    "description": (
                        "Una fra: riepilogo, economia, caratteristiche, combattimento, inventario, "
                        "equipaggiamento, esperienza, effetti, competenze, note, reagenti. Vuoto per riepilogo."
                    ),
                },
            }
        ),
        run=_character_sheet,
        scope="personaggi",
    ),
    AITool(
        name="cerca_abilita",
        description="Cerca abilità nel catalogo per nome o descrizione, con famiglia e costo in punti esperienza.",
        schema=_object_schema({"query": {"type": "string", "description": "Testo da cercare fra le abilità."}}),
        run=_search_skills,
    ),
    AITool(
        name="competenze_personaggio",
        description="Legge le 21 competenze di un personaggio con i due ranghi e il valore extra efficace.",
        schema=_object_schema({"nome": {"type": "string", "description": "Nome del personaggio."}}),
        run=_competences,
        scope="personaggi",
    ),
    AITool(
        name="lore_campagna",
        description="Consulta fazioni, reputazioni correnti, personaggi non giocanti ed eventi della campagna. Per domande generali su fazioni o reputazione usa un argomento vuoto. `stato` distingue dati assenti da un filtro senza corrispondenze.",
        schema=_object_schema({"argomento": {"type": "string", "description": "Solo una fazione, persona o evento specifico; vuoto per reputazioni e panoramiche generali."}}),
        run=_lore,
        scope="campagna",
    ),
    AITool(
        name="mercato",
        description="Elenca i negozi del mercato con tipo, località e regione.",
        schema=_object_schema({"negozio": {"type": "string", "description": "Filtra per nome del negozio."}}),
        run=_market,
        scope="mercato",
    ),
    AITool(
        name="guide_regole",
        description=(
            "Cerca nelle guide di gioco il testo delle regole su un argomento e restituisce gli estratti attorno "
            "a ogni occorrenza del termine. È lo strumento giusto per ogni domanda «come funziona X». "
            "`stato` distingue `nessun_dato` (nessuna guida esiste) da `filtro_senza_risultati` (nessuna guida cita il termine): "
            "se è `filtro_senza_risultati`, riprova con un sinonimo più ampio invece di ripetere lo stesso termine."
        ),
        schema=_object_schema({"argomento": {"type": "string", "description": "Argomento della regola, per esempio «fatica», «viaggio» o «alchimia». Vuoto per l'elenco delle guide."}}),
        run=_rules_guide,
        scope="regole",
    ),
    AITool(
        name="variabili_gioco",
        description="Legge le variabili e le formule di base del sistema. Riservato a Master e Amministratori.",
        schema=_object_schema({}),
        run=_game_variables,
        scope="regole",
        minimum_role=Giocatore.ROLE_MASTER,
    ),
    AITool(
        name="abilita_personaggio",
        description="Legge le abilità sbloccate di un personaggio e la sua progressione di livello (PE spesi, PE mancanti al prossimo livello).",
        schema=_object_schema({"nome": {"type": "string", "description": "Nome del personaggio. Vuoto per quello attivo."}}),
        run=_character_skills,
        scope="personaggi",
    ),
    AITool(
        name="note_personaggio",
        description="Legge le sezioni di note libere di un personaggio.",
        schema=_object_schema({"nome": {"type": "string", "description": "Nome del personaggio. Vuoto per quello attivo."}}),
        run=_character_notes,
        scope="personaggi",
    ),
    AITool(
        name="alchimia_personaggio",
        description="Legge la sacca reagenti di un personaggio, i set alchemici disponibili e le famiglie di pozioni che può creare.",
        schema=_object_schema({"nome": {"type": "string", "description": "Nome del personaggio. Vuoto per quello attivo."}}),
        run=_character_alchemy,
        scope="personaggi",
    ),
    AITool(
        name="cerca_incantesimi",
        description="Cerca incantesimi nel catalogo per nome o descrizione, con livello, gittata, formula di costo e costo base in Mana.",
        schema=_object_schema({"query": {"type": "string", "description": "Testo da cercare fra gli incantesimi."}}),
        run=_search_spells,
    ),
    AITool(
        name="tipi_arma",
        description="Elenca i tipi d'arma del regolamento (lunghezza, potenza, bonus) e le categorie di tipo oggetto.",
        schema=_object_schema({"query": {"type": "string", "description": "Filtra per nome del tipo d'arma."}}),
        run=_weapon_types,
    ),
    AITool(
        name="reagenti",
        description="Elenca i reagenti alchemici del catalogo con colore e livello.",
        schema=_object_schema({"colore": {"type": "string", "description": "Filtra per colore: rosso, verde o blu."}}),
        run=_reagents,
    ),
    AITool(
        name="inventario_negozio",
        description="Legge lo stock in vendita di uno o più negozi: oggetti, quantità e prezzo unitario.",
        schema=_object_schema(
            {
                "negozio": {"type": "string", "description": "Filtra per nome del negozio."},
                "oggetto": {"type": "string", "description": "Filtra lo stock per nome dell'oggetto."},
            }
        ),
        run=_shop_stock,
        scope="mercato",
    ),
    AITool(
        name="relazioni_fazioni",
        description="Legge la rete di relazioni fra fazioni (quanto la reputazione di una influenza le altre). Riservato a Master e Amministratori.",
        schema=_object_schema({}),
        run=_faction_relations,
        scope="campagna",
        minimum_role=Giocatore.ROLE_MASTER,
    ),
    AITool(
        name="eventi_reputazione",
        description="Legge gli eventi che hanno cambiato la reputazione con le fazioni, con il motivo e i valori prima/dopo. Usalo per «perché»/«come mai» la reputazione è cambiata.",
        schema=_object_schema({"fazione": {"type": "string", "description": "Filtra per nome della fazione. Vuoto per tutti gli eventi."}}),
        run=_reputation_events,
        scope="campagna",
    ),
    AITool(
        name="voci_lore",
        description="Cerca nelle voci di lore della campagna (luoghi, oggetti, concetti narrativi) per nome o sommario.",
        schema=_object_schema({"argomento": {"type": "string", "description": "Testo da cercare fra le voci di lore."}}),
        run=_lore_entries,
        scope="campagna",
    ),
    AITool(
        name="timeline",
        description="Legge la timeline storica della campagna (eventi cronologici, distinti dagli eventi di reputazione).",
        schema=_object_schema({"argomento": {"type": "string", "description": "Testo da cercare fra gli eventi della timeline."}}),
        run=_timeline,
        scope="campagna",
    ),
    AITool(
        name="curiosita",
        description="Cerca curiosità di ambientazione per nome o descrizione.",
        schema=_object_schema({"argomento": {"type": "string", "description": "Testo da cercare fra le curiosità."}}),
        run=_curiosities,
        scope="campagna",
    ),
    AITool(
        name="hall_of_fame",
        description="Legge la Hall of Fame dei personaggi storici della campagna.",
        schema=_object_schema({}),
        run=_hall_of_fame,
        scope="campagna",
    ),
    AITool(
        name="stato_campagna",
        description="Legge lo stato corrente della campagna attiva: giorno, ora, meteo e monete condivise del gruppo.",
        schema=_object_schema({}),
        run=_campaign_state,
        scope="campagna",
    ),
    AITool(
        name="mappe_viaggio",
        description="Elenca le mappe di viaggio della campagna attiva.",
        schema=_object_schema({}),
        run=_travel_maps,
        scope="campagna",
    ),
    AITool(
        name="storico_tiri",
        description="Legge lo storico dei tiri di dado del gruppo. Riservato a Master e Amministratori.",
        schema=_object_schema(
            {
                "giocatore_nome": {"type": "string", "description": "Filtra per nome del giocatore che ha tirato."},
                "limite": {"type": "integer", "description": "Numero massimo di tiri, da 1 a 100."},
            }
        ),
        run=_dice_history,
        scope="dadi",
        minimum_role=Giocatore.ROLE_MASTER,
    ),
    AITool(
        name="statistiche_tiri",
        description="Legge le statistiche aggregate dei tiri di dado del gruppo (medie per giocatore e per set di dadi). Riservato a Master e Amministratori.",
        schema=_object_schema({}),
        run=_dice_statistics,
        scope="dadi",
        minimum_role=Giocatore.ROLE_MASTER,
    ),
    AITool(
        name="stato_combattimento",
        description="Legge lo stato sintetico di una mappa di combattimento: partecipanti attivi e punti ferita attuali/massimi.",
        schema=_object_schema({"mappa": {"type": "string", "description": "Nome della mappa. Vuoto per quella predefinita."}}),
        run=_combat_state,
        scope="combattimento",
    ),
    AITool(
        name="modificatori_combattimento",
        description="Legge il catalogo dei modificatori di combattimento e quali sono attivi sulla mappa corrente.",
        schema=_object_schema({"mappa": {"type": "string", "description": "Nome della mappa. Vuoto per quella predefinita."}}),
        run=_combat_modifiers,
        scope="combattimento",
    ),
    AITool(
        name="giocatori",
        description="Elenca i giocatori della campagna con ruolo, personaggio attivo e campagna attiva. Riservato a Master e Amministratori.",
        schema=_object_schema({}),
        run=_players,
        scope="gestione",
        minimum_role=Giocatore.ROLE_MASTER,
    ),
    AITool(
        name="impostazioni",
        description="Legge le impostazioni globali di gioco non riservate. Riservato agli Amministratori.",
        schema=_object_schema({}),
        run=_settings_overview,
        scope="gestione",
        minimum_role=Giocatore.ROLE_ADMIN,
    ),
    AITool(
        name="posso_permettermi",
        description=(
            "Cerca un oggetto nei negozi e confronta il prezzo con le monete del personaggio attivo. "
            "Usalo per «posso comprare X?» o «quanto costa X e quante monete ho?»."
        ),
        schema=_object_schema(
            {
                "oggetto": {"type": "string", "description": "Nome dell'oggetto da cercare."},
                "negozio": {"type": "string", "description": "Filtra per nome del negozio. Vuoto per cercare in tutti."},
            },
            required=["oggetto"],
        ),
        run=_can_afford,
        scope="mercato",
    ),
    AITool(
        name="analisi_abilita",
        description=(
            "Analizza se il personaggio attivo può sbloccare un'abilità: costo in PE, pool di PE consentiti, "
            "se è già sbloccata e i motivi per cui non può essere sbloccata ora. Usalo per «quanti PE mi servono per X?»."
        ),
        schema=_object_schema({"nome": {"type": "string", "description": "Nome dell'abilità."}}, required=["nome"]),
        run=_skill_analysis,
        scope="personaggi",
    ),
    AITool(
        name="perche_reputazione",
        description="Ricostruisce la storia della reputazione con una fazione: valore attuale e ogni evento che l'ha cambiata, in ordine. Usalo per «perché/come mai» la reputazione con una fazione è quella che è.",
        schema=_object_schema({"fazione": {"type": "string", "description": "Nome della fazione."}}, required=["fazione"]),
        run=_faction_history,
        scope="campagna",
    ),
    AITool(
        name="riepilogo_gruppo",
        description="Riepiloga livello, monete, punti ferita e PE generali di ogni personaggio del gruppo. Riservato a Master e Amministratori.",
        schema=_object_schema({}),
        run=_group_summary,
        scope="personaggi",
        minimum_role=Giocatore.ROLE_MASTER,
    ),
    AITool(
        name="capacita_trasporto",
        description="Calcola quanti spazi di zaino/faretra restano liberi e quanto peso il personaggio può ancora portare prima del prossimo malus da ingombro.",
        schema=_object_schema({"nome": {"type": "string", "description": "Nome del personaggio. Vuoto per quello attivo."}}),
        run=_carrying_capacity,
        scope="personaggi",
    ),
]

AI_TOOLS_BY_NAME = {tool.name: tool for tool in AI_TOOLS}
ALL_SCOPES: frozenset[str] = frozenset(tool.scope for tool in AI_TOOLS)


def tool_is_available(tool: AITool, user, giocatore: Giocatore) -> bool:
    return has_minimum_role(effective_role(user, giocatore), tool.minimum_role)


def reachable_tools(user, giocatore: Giocatore, allowed_names: list[str] | None = None) -> list[AITool]:
    """Gli strumenti che questo utente può davvero chiamare in questo turno, prima del filtro per scope."""

    allowed = set(allowed_names) if allowed_names is not None else None
    return [
        tool
        for tool in AI_TOOLS
        if (allowed is None or tool.name in allowed) and tool_is_available(tool, user, giocatore)
    ]


def tool_definitions(
    user=None,
    giocatore: Giocatore | None = None,
    allowed_names: list[str] | None = None,
    scopes: set[str] | None = None,
) -> list[dict[str, Any]]:
    allowed = set(allowed_names) if allowed_names is not None else None
    return [
        tool.definition()
        for tool in AI_TOOLS
        if (allowed is None or tool.name in allowed)
        and (scopes is None or tool.scope in scopes)
        and (user is None or giocatore is None or tool_is_available(tool, user, giocatore))
    ]


def _iter_list_fields(node: Any, path: tuple[Any, ...] = ()) -> list[tuple[tuple[Any, ...], list]]:
    """Trova ogni lista non vuota annidata in `node`, con il percorso per raggiungerla."""

    found: list[tuple[tuple[Any, ...], list]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.extend(_iter_list_fields(value, path + (key,)))
    elif isinstance(node, list):
        if node:
            found.append((path, node))
        for index, item in enumerate(node):
            found.extend(_iter_list_fields(item, path + (index,)))
    return found


def _set_at_path(root: dict[str, Any], path: tuple[Any, ...], new_list: list, total: int) -> None:
    node: Any = root
    for step in path[:-1]:
        node = node[step]
    key = path[-1]
    node[key] = new_list
    if isinstance(node, dict) and isinstance(key, str):
        # `setdefault`: se questa lista è già stata dimezzata in un giro precedente,
        # `total` qui sarebbe la dimensione già ridotta, non quella originale.
        node.setdefault(f"{key}Totale", total)


def _truncate_result(result: dict[str, Any]) -> dict[str, Any]:
    """Dimezza ripetutamente la lista annidata più pesante finché il JSON rientra nel limite.

    Non taglia mai una stringa a metà: o il risultato resta JSON valido con un marcatore
    `troncato`, oppure degrada a un errore esplicito che l'agente può leggere e su cui
    può correggersi (per esempio restringendo la ricerca o cambiando sezione).
    """

    for _ in range(24):
        if len(json.dumps(result, ensure_ascii=False, default=str)) <= MAXIMUM_TOOL_RESULT_CHARACTERS:
            result["troncato"] = True
            return result
        candidates = [entry for entry in _iter_list_fields(result) if len(entry[1]) > 1]
        if not candidates:
            break
        path, items = max(candidates, key=lambda entry: len(json.dumps(entry[1], ensure_ascii=False, default=str)))
        half = max(1, len(items) // 2)
        _set_at_path(result, path, items[:half], len(items))

    return {
        "errore": "risultato_troppo_grande",
        "suggerimento": "Restringi la ricerca o richiedi una sezione più piccola.",
    }


def _serialize_tool_result(result: Any) -> str:
    encoded = json.dumps(result, ensure_ascii=False, default=str)
    if len(encoded) <= MAXIMUM_TOOL_RESULT_CHARACTERS:
        return encoded
    if not isinstance(result, dict):
        return json.dumps(
            {"errore": "risultato_troppo_grande", "suggerimento": "Restringi la ricerca o richiedi una sezione più piccola."},
            ensure_ascii=False,
        )
    return json.dumps(_truncate_result(result), ensure_ascii=False, default=str)


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    user,
    giocatore: Giocatore,
    *,
    allowed_names: list[str] | None = None,
) -> tuple[str, bool]:
    """Esegue uno strumento e restituisce `(testo, is_error)`.

    Un errore non solleva: torna all'agente come risultato, così può correggersi.
    """

    tool = AI_TOOLS_BY_NAME.get(name)
    if tool is None:
        return json.dumps({"errore": f"Strumento sconosciuto: {name}"}, ensure_ascii=False), True
    if allowed_names is not None and name not in allowed_names:
        return json.dumps({"errore": f"Strumento non autorizzato per questo agente: {name}"}, ensure_ascii=False), True
    if not tool_is_available(tool, user, giocatore):
        return json.dumps({"errore": f"Permessi insufficienti per lo strumento: {name}"}, ensure_ascii=False), True
    safe_arguments = {key: value for key, value in (arguments or {}).items() if key in tool.schema["properties"]}
    try:
        result = tool.run(user, giocatore, **safe_arguments)
    except Exception as error:  # noqa: BLE001 - l'agente deve poter leggere il guasto
        return json.dumps({"errore": f"{type(error).__name__}: {error}"}, ensure_ascii=False), True
    return _serialize_tool_result(result), False

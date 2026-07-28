"""Strumenti di sola lettura esposti all'agente.

Ogni strumento chiama i selettori esistenti **come l'utente che ha posto la domanda**.
È la regola che tiene insieme tutto il resto: i permessi (`visibilita_limitata`,
`visibile_ai_giocatori`, i personaggi assegnati) sono già applicati là dentro, quindi
un giocatore non può estrarre dalla chat quello che la sua pagina gli nasconde.
Nessuno strumento scrive: la versione 1 dell'agente risponde e basta.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from backend.characters.competence_selectors import competence_catalog_payload
from backend.characters.models import Personaggio
from backend.characters.selectors import ordered_personaggi_for, personaggio_detail
from backend.core.game_variable_selectors import game_variables_payload
from backend.core.item_selectors import item_catalog_payload
from backend.core.models import Giocatore, Guida
from backend.core.security import effective_role, has_minimum_role
from backend.core.skill_selectors import skill_catalog_payload
from backend.lore.selectors import lore_payload
from backend.market.selectors import market_overview


MAXIMUM_TOOL_RESULT_CHARACTERS = 24000


@dataclass(frozen=True)
class AITool:
    name: str
    description: str
    schema: dict[str, Any]
    run: Callable[..., Any]

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


def _character_sheet(user, giocatore: Giocatore, nome: str = "") -> dict[str, Any]:
    character = _accessible_character(user, giocatore, nome)
    if character is None:
        return {"errore": "Nessun personaggio accessibile con questo nome."}
    sheet = personaggio_detail(character, can_manage_items=_is_master(user, giocatore), include_skills=False) or {}
    return {
        "personaggio": {
            key: sheet.get(key)
            for key in ("id", "name", "type", "races", "level", "details", "primaryTotals", "resources", "stats", "encumbrance")
            if key in sheet
        }
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
    # lore_payload filtra già gli eventi e i personaggi nascosti ai giocatori.
    payload = lore_payload(user, giocatore)
    needle = str(argomento or "").strip().casefold()

    def matches(entry: dict[str, Any]) -> bool:
        if not needle:
            return True
        return needle in json.dumps(entry, ensure_ascii=False).casefold()

    return {
        "campagna": (payload.get("campaign") or {}).get("name"),
        "fazioni": [
            {
                "nome": item.get("name"),
                "reputazione": item.get("reputation"),
                "livello": item.get("tier"),
                "descrizione": item.get("description"),
            }
            for item in payload.get("factions", [])
            if matches(item)
        ][:20],
        "personaggi": [
            {
                "nome": item.get("name"),
                "ruolo": item.get("role"),
                "fazione": item.get("factionName"),
                "descrizione": item.get("description"),
            }
            for item in payload.get("npcs", [])
            if matches(item)
        ][:20],
        "eventi": [
            {"titolo": item.get("title"), "motivo": item.get("reason"), "giorno": item.get("campaignDay")}
            for item in payload.get("events", [])
            if matches(item)
        ][:20],
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


def _rules_guide(user, giocatore: Giocatore, argomento: str = "") -> dict[str, Any]:
    needle = str(argomento or "").strip().casefold()
    guides = Guida.objects.filter(archived_at__isnull=True).order_by("categoria", "ordine", "nome")
    found = []
    for guide in guides:
        blob = json.dumps(guide.contenuto, ensure_ascii=False) if guide.contenuto else ""
        if needle and needle not in f"{guide.nome} {blob}".casefold():
            continue
        found.append({"nome": guide.nome, "categoria": guide.categoria, "contenuto": blob[:4000]})
        if len(found) >= 4:
            break
    return {"guide": found}


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
        description="Legge la scheda di un personaggio accessibile a chi sta chiedendo: caratteristiche, risorse, livello e totali.",
        schema=_object_schema(
            {"nome": {"type": "string", "description": "Nome del personaggio. Vuoto per quello attivo."}}
        ),
        run=_character_sheet,
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
    ),
    AITool(
        name="lore_campagna",
        description="Consulta fazioni, reputazioni, personaggi non giocanti ed eventi della campagna. Mostra soltanto ciò che chi chiede può già vedere.",
        schema=_object_schema({"argomento": {"type": "string", "description": "Parola chiave. Vuoto per un quadro generale."}}),
        run=_lore,
    ),
    AITool(
        name="mercato",
        description="Elenca i negozi del mercato con tipo, località e regione.",
        schema=_object_schema({"negozio": {"type": "string", "description": "Filtra per nome del negozio."}}),
        run=_market,
    ),
    AITool(
        name="guide_regole",
        description="Cerca nelle guide di gioco il testo delle regole su un argomento.",
        schema=_object_schema({"argomento": {"type": "string", "description": "Argomento della regola, per esempio «fatica» o «alchimia»."}}),
        run=_rules_guide,
    ),
    AITool(
        name="variabili_gioco",
        description="Legge le variabili e le formule di base del sistema. Riservato a Master e Amministratori.",
        schema=_object_schema({}),
        run=_game_variables,
    ),
]

AI_TOOLS_BY_NAME = {tool.name: tool for tool in AI_TOOLS}


def tool_definitions() -> list[dict[str, Any]]:
    return [tool.definition() for tool in AI_TOOLS]


def execute_tool(name: str, arguments: dict[str, Any], user, giocatore: Giocatore) -> tuple[str, bool]:
    """Esegue uno strumento e restituisce `(testo, is_error)`.

    Un errore non solleva: torna all'agente come risultato, così può correggersi.
    """

    tool = AI_TOOLS_BY_NAME.get(name)
    if tool is None:
        return json.dumps({"errore": f"Strumento sconosciuto: {name}"}, ensure_ascii=False), True
    safe_arguments = {key: value for key, value in (arguments or {}).items() if key in tool.schema["properties"]}
    try:
        result = tool.run(user, giocatore, **safe_arguments)
    except Exception as error:  # noqa: BLE001 - l'agente deve poter leggere il guasto
        return json.dumps({"errore": f"{type(error).__name__}: {error}"}, ensure_ascii=False), True
    return json.dumps(result, ensure_ascii=False, default=str)[:MAXIMUM_TOOL_RESULT_CHARACTERS], False

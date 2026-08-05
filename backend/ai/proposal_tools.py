from __future__ import annotations

from typing import Any

from backend.combat.unit_management_selectors import unit_management_overview
from backend.core.api import ApiError
from backend.core.models import AccessoryProfile

from .changes.registry import get_change_handler
from .changes.serializers import serialize_change_set
from .changes.services import (
    add_change_operation,
    delete_change_operation,
    entity_catalog,
    get_change_set_for_user,
    search_change_entities,
)
from .models import AIChangeSet
from .tool_context import AIToolExecutionContext


UNIT_DISCOVERY_SECTIONS = (
    "contratto",
    "progressione",
    "razze_competenze",
    "equipaggiamento",
    "statistiche_creature",
)


def _change_set(user, context: AIToolExecutionContext | None) -> AIChangeSet:
    if context is None or context.change_set is None:
        raise ApiError(
            "ai.change_context_required",
            "Questo strumento richiede una proposta modificabile collegata all'esecuzione.",
            status=409,
        )
    change_set = get_change_set_for_user(user, context.change_set.id)
    if change_set.status not in AIChangeSet.EDITABLE_STATUSES:
        raise ApiError("ai.change_set_immutable", "La proposta non è più modificabile.", status=409)
    return change_set


def list_editable_entities(user, giocatore, context: AIToolExecutionContext | None) -> dict[str, Any]:
    _change_set(user, context)
    return {"entita": entity_catalog(user, giocatore)}


def read_unit_authoring_configuration(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    sezione: str = "contratto",
) -> dict[str, Any]:
    """Return one bounded, authoritative Unit-authoring section.

    The generic entity catalogue can be large enough to require tool-result
    truncation. Unit authoring must not depend on a truncated dropdown schema,
    so this tool exposes the live contract in small deterministic sections.
    """

    _change_set(user, context)
    handler = get_change_handler("unit")
    handler.require_access(user, giocatore, "create")
    section = str(sezione or "contratto").strip().lower()
    if section not in UNIT_DISCOVERY_SECTIONS:
        raise ApiError(
            "ai.unit_discovery_section_invalid",
            f"Sezione Unit non valida. Usa: {', '.join(UNIT_DISCOVERY_SECTIONS)}.",
            "sezione",
        )
    configuration = unit_management_overview()["configuration"]
    common = {
        "sezione": section,
        "sezioniDisponibili": list(UNIT_DISCOVERY_SECTIONS),
        "fonte": "configurazione Unit live e servizi correnti",
        "dto": [
            "name",
            "category",
            "loreImageId",
            "archetypeDescription",
            "loreDescription",
            "notes",
            "generation",
            "archetypeTags",
            "competenceProfile",
            "skillUnlocks",
            "equipmentSlots",
            "equipmentGroups",
            "accessoryCountByLevel",
            "accessoryProfileKey",
            "innateActions",
            "statProfile",
            "levels",
        ],
    }
    if section == "contratto":
        return {
            **common,
            "regoleObbligatorie": [
                "Usa esclusivamente il DTO di gestione e i servizi Unit; mai campi ORM o metadata arbitrari.",
                "Scegli creature o humanoid per meccaniche, non per aspetto o lore.",
                "Prima della proposta leggi questa configurazione, almeno cinque Unit comparabili e ogni Skill/Item selezionato.",
                "Crea un payload completo in una sola operazione; non salvare scheletri da completare con ID inventati.",
                "Le azioni innate delle creature sono promemoria e non esecutori di combattimento.",
                "L'audit del backend usa il generatore reale e blocca errori, instabilità e progressioni umanoidi incomplete.",
                "L'applicazione resta una conferma umana atomica; la proposta non è una modifica di dominio.",
            ],
            "contratti": configuration["kinds"],
            "decisione": {
                "humanoid": "Usalo solo se servono Skill a PE, Perk, Competenze, razza/sottorazza ed equipaggiamento.",
                "creature": "Usalo per chassis a curve/modificatori e azioni innate senza sistemi umanoidi.",
            },
            "verifica": {
                "livelliNominati": list(handler.AUDIT_LEVELS),
                "livelliRipetibilita": list(handler.AUDIT_REPEAT_LEVELS),
                "livelliVariantiAutomatiche": list(handler.AUDIT_AUTO_LEVELS),
                "variantiAutomatichePerLivello": handler.AUDIT_AUTO_PER_LEVEL,
                "nessunRecordPreviewPersistito": True,
            },
        }
    if section == "progressione":
        return {
            **common,
            "cores": configuration["cores"],
            "tags": configuration["tags"],
            "magicPolicies": configuration["magicPolicies"],
            "classFamilies": configuration["classFamilies"],
            "religionFamilies": configuration["religionFamilies"],
            "regole": [
                "Ogni umanoide deve avere almeno una Skill ordinaria Core e una Archetipo realmente acquistabili.",
                "I tag pesano candidati ma non creano pool Skill.",
                "Leggi ogni Skill scelta con leggi_record_gestibile: prerequisiti, prezzo, requisiti, famiglia, magia ed effetti.",
                "Le Skill Classe e Religione richiedono le rispettive famiglie consentite esatte.",
                "L'audit di livello 20 richiede una progressione completa di 20 Perk minori e 10 maggiori.",
            ],
        }
    if section == "razze_competenze":
        return {
            **common,
            "races": configuration["races"],
            "competences": configuration["competences"],
            "regole": [
                "Una lista razze vuota significa tutte le razze correnti, non nessuna razza.",
                "Le sottorazze devono appartenere alle razze selezionate.",
                "I valori Competenza sono pesi da -5 a +5, non barre fisse.",
                "Dopo la proposta verifica nel risultato serializzato che razze e sottorazze non siano state ampliate da valori sconosciuti.",
            ],
        }
    if section == "equipaggiamento":
        profiles = [
            {
                "key": profile.key,
                "name": profile.nome,
                "description": profile.descrizione,
                "rules": profile.rules if isinstance(profile.rules, dict) else {},
            }
            for profile in AccessoryProfile.objects.filter(
                archived_at__isnull=True,
            ).order_by("nome", "key")
        ]
        return {
            **common,
            "slots": configuration["equipmentSlots"],
            "accessoryProfiles": profiles,
            "regole": [
                "Leggi ogni Item scelto con leggi_record_gestibile e verifica tipi, effetti, regole speciali e compatibilità slot.",
                "Non combinare arma a due mani con scudo/offhand occupato.",
                "Un Item di gruppo deve essere compatibile con ogni slot del gruppo, non soltanto con uno.",
                "Le fasce accessori esplicite devono coprire 1-20 senza vuoti o sovrapposizioni e rispettare minimi/capacità.",
                "Il profilo accessori condiviso usa il catalogo live e può produrre fallback: controllare sempre trace e avvisi.",
                "Materiale e tier sono politiche curate dall'autore, non vincoli automatici del server.",
            ],
        }
    return {
        **common,
        "curveProfiles": configuration["statCurveProfiles"],
        "curveVariables": configuration["statCurveVariables"],
        "regole": [
            "Le curve sono endpoint esatti livello 1/livello 20 con interpolazione lineare arrotondata.",
            "Ogni chiave curva può apparire una sola volta e deve provenire dalla configurazione live.",
            "Le curve applicano strong_set e possono sovrascrivere totali calcolati.",
            "baseModifiers, perLevelModifiers, milestones e levels accettano target più ampi: usarli solo dopo verifica del codice.",
            "Le azioni innate devono specificare regola completa e costi ammessi, ma restano promemoria manuali.",
            "Una creatura non può contenere Skill, equipaggiamento, profilo accessori, Competenze, razze o famiglie.",
        ],
    }


def search_manageable_records(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    tipo: str,
    query: str = "",
    limite: int = 10,
) -> dict[str, Any]:
    _change_set(user, context)
    return {
        "tipo": str(tipo or "").strip().lower(),
        "risultati": search_change_entities(user, giocatore, tipo, query, limite),
    }


def read_manageable_record(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    tipo: str,
    id: int,
) -> dict[str, Any]:
    _change_set(user, context)
    handler = get_change_handler(tipo)
    handler.require_access(user, giocatore, "update")
    return {
        "record": handler.snapshot(user, giocatore, id),
        "fields": handler.field_schema(user, giocatore, action="update"),
    }


def propose_create(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    tipo: str,
    valori: dict[str, Any],
    sorgenteId: int | None = None,
) -> dict[str, Any]:
    change_set = _change_set(user, context)
    operation = add_change_operation(
        user,
        giocatore,
        change_set.id,
        entity_type=tipo,
        action="create",
        values=valori,
        source_id=sorgenteId,
    )
    return {
        "propostaId": str(change_set.id),
        "operazioneId": operation.id,
        "tipo": operation.entity_type,
        "azione": operation.action,
        "etichetta": operation.display_label,
        "stato": operation.status,
    }


def propose_update(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    tipo: str,
    id: int,
    valori: dict[str, Any],
) -> dict[str, Any]:
    change_set = _change_set(user, context)
    operation = add_change_operation(
        user,
        giocatore,
        change_set.id,
        entity_type=tipo,
        action="update",
        values=valori,
        target_id=id,
    )
    return {
        "propostaId": str(change_set.id),
        "operazioneId": operation.id,
        "tipo": operation.entity_type,
        "azione": operation.action,
        "etichetta": operation.display_label,
        "stato": operation.status,
    }


def propose_archive(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    tipo: str,
    id: int,
) -> dict[str, Any]:
    change_set = _change_set(user, context)
    operation = add_change_operation(
        user,
        giocatore,
        change_set.id,
        entity_type=tipo,
        action="archive",
        target_id=id,
    )
    return {
        "propostaId": str(change_set.id),
        "operazioneId": operation.id,
        "tipo": operation.entity_type,
        "azione": operation.action,
        "etichetta": operation.display_label,
        "stato": operation.status,
    }


def remove_proposed_operation(
    user,
    giocatore,
    context: AIToolExecutionContext | None,
    operazioneId: int,
) -> dict[str, Any]:
    change_set = _change_set(user, context)
    delete_change_operation(user, change_set.id, operazioneId)
    return {
        "propostaId": str(change_set.id),
        "operazioneRimossa": operazioneId,
        "proposta": serialize_change_set(get_change_set_for_user(user, change_set.id)),
    }


def summarize_proposal(user, giocatore, context: AIToolExecutionContext | None) -> dict[str, Any]:
    change_set = _change_set(user, context)
    return {"proposta": serialize_change_set(change_set)}

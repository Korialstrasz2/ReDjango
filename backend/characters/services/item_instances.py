"""Esemplari: le righe oggetto che appartengono a un personaggio, non al catalogo.

Ogni slot di inventario ed equipaggiamento è una ForeignKey a ``Oggetto``, e
5.881 righe su 5.895 sono modelli condivisi. Se due personaggi portano
``Martello (ferro)`` puntano alla stessa riga: scrivere lì un miglioramento lo
regalerebbe anche all'altro. Per questo forgiare e incantare clonano il
modello in una riga nuova.

Il guadagno è che non serve altro motore. ``collect_personaggio_effect_payloads``
già legge ``Oggetto.effects`` di ogni oggetto equipaggiato e lo somma ai totali,
quindi un ``+1 Attacco`` scritto qui compare sulla scheda e in combattimento
senza una riga di calcolo in più.

Il registro in ``metadata["instance"]`` è la verità: ``effects`` ne è la
proiezione, ricostruita da zero a ogni modifica. Non si legge mai il registro
dagli effetti.
"""

from __future__ import annotations

import re
from typing import Any

from django.db import transaction

from backend.core.api import ApiError
from backend.core.forge_defaults import IMPROVEMENT_BY_KEY, improvement_cost
from backend.core.item_special import INSTANCE_KEY
from backend.core.models import Oggetto

from ..models import Personaggio, Zaino


# Origine scritta sulle operazioni prodotte al banco, per distinguerle dagli
# effetti che l'oggetto aveva già come modello.
FORGE_SOURCE = "forge_improvement"
ENCHANT_SOURCE = "enchant"
CRAFT_SOURCES = (FORGE_SOURCE, ENCHANT_SOURCE)

_SUFFIX = re.compile(r" #(\d+)$")


def instance_block(item: Oggetto) -> dict[str, Any]:
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    block = metadata.get(INSTANCE_KEY)
    return dict(block) if isinstance(block, dict) else {}


def is_instance(item: Oggetto) -> bool:
    return bool(instance_block(item))


def _unique_name(base_name: str) -> str:
    """``Ascia (acciaio)`` → ``Ascia (acciaio) #2``, poi #3, e così via.

    ``Oggetto.nome`` è unique: senza suffisso la seconda ascia forgiata dallo
    stesso stampo esploderebbe con un IntegrityError.
    """
    stem = _SUFFIX.sub("", base_name).strip()
    existing = set(
        Oggetto.objects.filter(nome__startswith=stem).values_list("nome", flat=True)
    )
    if stem not in existing:
        return stem[:180]
    for index in range(2, 500):
        candidate = f"{stem} #{index}"
        if candidate not in existing:
            return candidate[:180]
    raise ApiError(
        "crafting.name_unavailable",
        "Troppi esemplari con questo nome: rinominane qualcuno prima di continuare.",
        status=409,
    )


def _base_effects(item: Oggetto) -> list[dict[str, Any]]:
    """Effetti del modello, ripuliti da quelli prodotti al banco."""
    effects = item.effects if isinstance(item.effects, list) else []
    return [
        dict(effect)
        for effect in effects
        if not (isinstance(effect, dict) and effect.get("source") in CRAFT_SOURCES)
    ]


def rebuild_effects(item: Oggetto) -> None:
    """Riscrive ``effects`` dal registro. Il registro comanda, sempre."""
    block = instance_block(item)
    effects = _base_effects(item)

    for entry in block.get("improvements", []):
        definition = IMPROVEMENT_BY_KEY.get(entry.get("key", ""))
        if not definition or definition["apply"]["mode"] != "effect":
            continue
        apply = definition["apply"]
        stack = max(1, int(entry.get("stack", 1)))
        effects.append(
            {
                "target": apply["target"],
                "operation": "add",
                "value": apply["value"] * stack,
                "source": FORGE_SOURCE,
            }
        )

    for entry in block.get("enchantments", []):
        for effect in entry.get("effects", []):
            if isinstance(effect, dict) and effect.get("target"):
                effects.append({**effect, "source": ENCHANT_SOURCE})

    item.effects = effects


def append_table_rule(item: Oggetto, text: str) -> None:
    """Aggiunge una regola da tavolo senza dichiarare rivisti i testi Elder.

    ``item_services.sync_special_rules_review`` interpreta un ``regole_speciali``
    non vuoto come «le regole curate coprono gli effetti descrittivi» e marca
    ``descriptiveEffectsReviewed``. Passando di lì, una regola di forgiatura
    farebbe sparire dalla coda di revisione testi che nessuno ha letto: qui il
    campo si scrive a mano e il marcatore di revisione resta com'era.
    """
    line = str(text or "").strip()
    if not line:
        return
    existing = [row for row in (item.regole_speciali or "").splitlines() if row.strip()]
    if line in existing:
        return
    existing.append(line)
    item.regole_speciali = "\n".join(existing)


@transaction.atomic
def create_instance(
    template: Oggetto,
    character: Personaggio,
    *,
    kind: str,
    extra: dict[str, Any] | None = None,
) -> Oggetto:
    """Clona un modello in un esemplare del personaggio.

    ``archiviato=True`` lo tiene fuori da catalogo, compendio e generazione dei
    negozi; ``modello=False`` dice che non è riutilizzabile. La coppia è ciò che
    ``item_special.is_crafted_instance`` riconosce per non segnalarlo.
    """
    instance = Oggetto.objects.create(
        nome=_unique_name(template.nome),
        modello=False,
        temporaneo=False,
        archiviato=True,
        speciale=False,
        icona=template.icona,
        tipo_1=template.tipo_1,
        tipo_2=template.tipo_2,
        tipo_3=template.tipo_3,
        tipo_4=template.tipo_4,
        descrizione=template.descrizione,
        valore=template.valore,
        peso=template.peso,
        rarita=template.rarita,
        lv_loot=template.lv_loot,
        regione_loot=template.regione_loot,
        tipo_arma=template.tipo_arma,
        pa_per_attacco=template.pa_per_attacco,
        effetto_1=template.effetto_1, effetto_2=template.effetto_2,
        effetto_3=template.effetto_3, effetto_4=template.effetto_4,
        effetto_5=template.effetto_5, effetto_6=template.effetto_6,
        effetto_7=template.effetto_7, effetto_8=template.effetto_8,
        regole_speciali=template.regole_speciali,
        effects=_base_effects(template),
        media=template.media,
        metadata={
            # Il marcatore di revisione del modello viaggia con l'esemplare:
            # senza, i testi Elder già curati tornerebbero in coda da soli.
            **{
                key: value
                for key, value in (template.metadata or {}).items()
                if key == "descriptiveEffectsReviewed"
            },
            INSTANCE_KEY: {
                "kind": kind,
                "baseItemId": template.id,
                "baseItemName": template.nome,
                "ownerId": character.id,
                "ownerName": character.nome,
                "improvements": [],
                "enchantments": [],
                "pointsSpent": 0,
                **(extra or {}),
            },
        },
    )
    return instance


def write_instance_block(item: Oggetto, block: dict[str, Any]) -> None:
    metadata = dict(item.metadata) if isinstance(item.metadata, dict) else {}
    metadata[INSTANCE_KEY] = block
    item.metadata = metadata


def apply_improvement(item: Oggetto, improvement_key: str) -> dict[str, Any]:
    """Applica un miglioramento e restituisce il costo pagato.

    Il raddoppio Elder vive nel registro: la pila dice quante volte lo stesso
    miglioramento è già stato messo, e il prezzo del prossimo è ``base * 2^pila``.
    """
    definition = IMPROVEMENT_BY_KEY.get(improvement_key)
    if definition is None:
        raise ApiError("forge.improvement_unknown", "Miglioramento non riconosciuto.", "improvementKey")

    block = instance_block(item)
    improvements = [dict(entry) for entry in block.get("improvements", [])]
    current = next((entry for entry in improvements if entry.get("key") == improvement_key), None)
    stack = int(current.get("stack", 0)) if current else 0
    cost = improvement_cost(definition["cost"], stack)

    if current is None:
        improvements.append({"key": improvement_key, "stack": 1, "pointsPaid": cost})
    else:
        current["stack"] = stack + 1
        current["pointsPaid"] = int(current.get("pointsPaid", 0)) + cost
        improvements = [current if entry.get("key") == improvement_key else entry for entry in improvements]

    block["improvements"] = improvements
    block["pointsSpent"] = int(block.get("pointsSpent", 0)) + cost
    write_instance_block(item, block)

    apply = definition["apply"]
    if apply["mode"] == "column":
        column = apply["column"]
        current_value = getattr(item, column, None) or 0
        floor = apply.get("minimum", 0)
        setattr(item, column, max(floor, current_value + apply["delta"]))
    elif apply["mode"] == "rule":
        append_table_rule(item, apply["text"])

    rebuild_effects(item)
    return {"key": improvement_key, "label": definition["label"], "cost": cost, "stack": stack + 1}


def next_improvement_cost(item: Oggetto, improvement_key: str) -> int:
    definition = IMPROVEMENT_BY_KEY.get(improvement_key)
    if definition is None:
        return 0
    block = instance_block(item)
    entry = next(
        (row for row in block.get("improvements", []) if row.get("key") == improvement_key),
        None,
    )
    return improvement_cost(definition["cost"], int(entry.get("stack", 0)) if entry else 0)


def store_in_backpack(character: Personaggio, item: Oggetto) -> int:
    """Mette l'esemplare nel primo slot libero dello zaino.

    Torna il numero di slot usato, 0 se lo zaino è pieno: in quel caso
    l'oggetto esiste comunque e il chiamante avvisa, invece di perdere il
    lavoro appena fatto.
    """
    zaino: Zaino | None = character.zaino
    if zaino is None:
        return 0
    for slot in range(1, 51):
        if getattr(zaino, f"slot_{slot}_id", None) is None:
            setattr(zaino, f"slot_{slot}", item)
            zaino.save(update_fields=[f"slot_{slot}", "updated_at"])
            return slot
    return 0


def owned_instances(character: Personaggio, kinds: tuple[str, ...] = ()) -> list[Oggetto]:
    """Esemplari del personaggio, presi da zaino ed equipaggiamento."""
    seen: dict[int, Oggetto] = {}
    for container in (character.zaino, character.equip):
        if container is None:
            continue
        for field in container._meta.get_fields():
            if not getattr(field, "many_to_one", False) or field.related_model is not Oggetto:
                continue
            item = getattr(container, field.name, None)
            if item is None or item.id in seen or not is_instance(item):
                continue
            if kinds and instance_block(item).get("kind") not in kinds:
                continue
            seen[item.id] = item
    return sorted(seen.values(), key=lambda entry: entry.nome)


def release_instance(item: Oggetto) -> None:
    """Stacca l'esemplare da ogni slot e lo elimina.

    Le FK degli slot sono ``SET_NULL``, quindi la cancellazione basterebbe; lo
    sganciamento esplicito evita però che un ``prefetch`` già in memoria continui
    a mostrarlo dopo la fusione.
    """
    item.delete()

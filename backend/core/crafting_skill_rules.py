"""Traduce in dati le abilità Fabbro e Incantatore.

Le 79 abilità dei due rami esistevano solo come prosa italiana in
``Skill.descrizione``: leggibili al tavolo, invisibili al motore. Qui la stessa
regola viene scritta una seconda volta in una forma che un servizio può
interrogare, esattamente come ``Alchimista 1`` porta già le sue operazioni su
``moltiplicatore_reagenti_*``.

Due meccanismi, scelti per natura della regola:

``effetti_passivi``
    Per le **grandezze**. Diventano ``EffettoPersonalizzato`` allo sblocco e
    ``refresh_personaggio`` le somma in ``Personaggio.tot``. Il vantaggio è che
    il totale non appartiene all'abilità: domani un oggetto o un effetto scritto
    a mano possono contribuire alla stessa chiave e il servizio legge un numero
    solo, senza sapere da dove venga.

``Skill.metadata``
    Per i **permessi**. Quali materiali sa lavorare un fabbro non è un numero:
    le fasce 4-7 si sbloccano a rami separati, e "fascia 2" più "fascia 3" non
    fa "fascia 5". Un float mentirebbe. Il precedente è ``pricingModifier``, che
    ``skill_pricing`` legge già da questo stesso campo.
"""

from __future__ import annotations

from typing import Any

from .forge_defaults import MATERIAL_BY_KEY


FORGE_RULE_KEY = "forgeRule"
ENCHANT_RULE_KEY = "enchantRule"
PASSIVE_SOURCE = "crafting_skill_rules"


def _passive(name: str, description: str, icon: str, operations: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "id": f"passivo-crafting-{name.lower().replace(' ', '-').replace(chr(39), '')}",
        "name": name,
        "description": description,
        "icon": icon,
        "operations": [{**operation, "condition": ""} for operation in operations],
    }


def _add(target: str, value: str) -> dict[str, str]:
    return {"target": target, "operation": "add", "value": value}


def _set(target: str, value: str) -> dict[str, str]:
    return {"target": target, "operation": "set", "value": value}


# --- Forgiatura -------------------------------------------------------------

# Sbloccano materiali. Fabbro 2/3/4 aprono entrambi i rami di una fascia; le
# specializzazioni oltre Fabbro 3 aprono un materiale alla volta.
MATERIAL_UNLOCKS: dict[str, tuple[str, ...]] = {
    "Fabbro 2": ("ferro", "pelle", "legno"),
    "Fabbro 3": ("chitina", "acciaio"),
    "Fabbro 4": ("elfico", "nordico"),
    "Lingotto di Ossa": ("ossa",),
    "Fucina Orchesca": ("orchesco",),
    "Materiale Dreugh": ("dreugh",),
    "Segreti Dwemer": ("dwemer",),
    "Lavorazione del Vetro": ("vetro",),
    "Maestria dell'Ebano": ("ebano",),
    "Lavorazione dell'Adamantio": ("adamantio",),
    "Fattura daedrica": ("daedrico",),
}

# Potenziato N alza il tetto dei miglioramenti a N+1; il tetto reale sottrae poi
# la fascia del materiale, quindi resta una grandezza e non un permesso.
POTENZIATO_LEVELS = {f"Potenziato {level}": level + 1 for level in range(1, 8)}
SPECIALISTA_LEVELS = {f"Specialista {level}": level for level in range(1, 4)}

FORGE_CAPABILITY_TOTALS: dict[str, str] = {
    "Scioglitore": "forgia_puo_fondere",
    "Riplasmare": "forgia_puo_riplasmare",
    "Fucina improvvisata": "forgia_puo_ovunque",
    "Il meglio che posso": "forgia_miglioramenti_stanchezza",
    "Fabbricante di frecce": "forgia_bonus_frecce",
}

USO_PRATICO_LEVELS = {"Uso pratico 1": 1, "Uso pratico 2": 2}

# Regole che il motore non rappresenta: restano al tavolo, ma vengono dichiarate
# così la scheda può dirlo invece di tacere.
FORGE_TABLE_RULES: dict[str, str] = {
    "Fabbro 1": "Forgi e ripari oggetti semplici: è il requisito d'ingresso della fucina, senza materiali propri.",
    "Specialista armaiolo": "Sblocca le specializzazioni di materiale; ognuna già presa sconta le altre di 1 PE.",
    "Design di freccia": "Frecce leggere +10% AP, frecce pesanti +1 tier di danno.",
    "Esperto in martelli": "+1 tier di danno con armi contundenti.",
    "Converti oggetto": "Converte anello, spilla, orecchino, amuleto fra loro; fascia e cintura; il mantello in qualunque cosa.",
    "Uso pratico magico": "Versioni magiche degli oggetti di Uso pratico, se collabori con un incantatore.",
}


# --- Incantamento -----------------------------------------------------------

# Incantatore 1-3 vale su entrambi i fronti; Scriba solo pergamene, Gioielliere
# solo oggetti. Il livello è un tetto, quindi `set` e non `add`: prendere
# Gioielliere 5 dopo Gioielliere 4 non deve sommare 9.
ENCHANT_LEVEL_CAPS: dict[str, tuple[int, tuple[str, ...]]] = {
    **{
        f"Incantatore {level}": (level, ("incanta_livello_max_oggetti", "incanta_livello_max_pergamene"))
        for level in range(1, 4)
    },
    **{f"Scriba {level}": (level + 3, ("incanta_livello_max_pergamene",)) for level in range(1, 8)},
    **{f"Gioielliere {level}": (level + 3, ("incanta_livello_max_oggetti",)) for level in range(1, 8)},
}

# Infusore N: "ogni livello è come se castassi con N+5 mana".
INFUSORE_LEVELS = {f"Infusore {level}": level + 5 for level in range(1, 6)}
ANIMA_COMPRESSA_LEVELS = {"Anima compressa 1": 25, "Anima compressa 2": 25}
MULTI_ENCHANT_LEVELS = {"Multi Incantamento 1": 2, "Multi Incantamento 2": 3}

ENCHANT_CAPABILITY_TOTALS: dict[str, str] = {
    "Incantatore Esperto": "incanta_puo_reincantare",
    "Artigiano di anime": "incanta_puo_sommare_gemme",
    "Riciclo di anime": "incanta_puo_disincantare",
    "Mana e anima": "incanta_bonus_livello_stanchezza",
}

ENCHANT_TABLE_RULES: dict[str, str] = {
    # Queste due portano già i loro passivi legacy su anelli_max/orecchini_max e
    # funzionano: qui ricevono solo l'etichetta, e il piano resta senza passivi
    # proprio perché la migrazione non deve sovrascriverli.
    "Moda delle anime": "Uno slot anello in più, già applicato automaticamente alla scheda.",
    "Arte delle anime": "Uno slot orecchino in più, già applicato automaticamente alla scheda.",
    "Danno da impatto": "L'arma incantata infligge danno magico a ogni colpo.",
    "Paralisi da impatto": "L'arma incantata riduce i PA del bersaglio a ogni colpo.",
    "Assorbi danno": "Le nuove armi con Danno da impatto rubano PF.",
    "Assorbi PA": "Le nuove armi con Paralisi da impatto rubano PA.",
    "Assorbi Anima": "L'arma incantata infligge Assorbi Anima a ogni colpo.",
    "Infondi counterspell": "Puoi infondere Counterspell, se lo conosci.",
    "Infondi risorse": "Puoi infondere PF, Mana, Potere ed Energia nell'oggetto.",
    "Scriba Avanzato": "Il Potere speso aumenta il mana finale della pergamena.",
    "Scriba Energico": "I punti Stanchezza spesi aumentano il mana finale della pergamena.",
    "Rilegatore": "Crea Grimori del Mago con carta e inchiostro.",
    "Rilegatore Avanzato": "Crea Grimori avanzati con carta e inchiostro.",
    "Scrittore Esperto": "Scrivi incantesimi sul grimorio per conto di altri.",
    "Scrittore Eccezionale": "Trascrivi senza costo fra grimori; converti il costo in 8 punti Stanchezza.",
}


def forge_plan(skill_name: str) -> dict[str, Any] | None:
    """Passivi e metadata da scrivere su un'abilità Fabbro, o None."""
    name = skill_name.strip()
    passives: list[dict[str, Any]] = []
    rule: dict[str, Any] = {}

    if name in MATERIAL_UNLOCKS:
        materials = MATERIAL_UNLOCKS[name]
        tiers = sorted({MATERIAL_BY_KEY[key]["tier"] for key in materials})
        rule = {"type": "material_unlock", "materials": list(materials), "tiers": tiers}
    elif name in POTENZIATO_LEVELS:
        cap = POTENZIATO_LEVELS[name]
        passives.append(_passive(
            name,
            f"Tetto dei miglioramenti pari a {cap} meno la fascia del materiale.",
            "lama",
            [_set("forgia_tetto_miglioramenti", str(cap))],
        ))
        rule = {"type": "improvement_cap", "cap": cap}
    elif name in SPECIALISTA_LEVELS:
        passives.append(_passive(
            name,
            "Un miglioramento in più sul materiale scelto.",
            "lama",
            [_add("forgia_miglioramenti_specialista", "1")],
        ))
        rule = {"type": "specialist_bonus", "amount": 1, "rebindFatigue": 3}
    elif name in FORGE_CAPABILITY_TOTALS:
        total = FORGE_CAPABILITY_TOTALS[name]
        passives.append(_passive(name, "Sblocca una capacità di forgiatura.", "lama", [_add(total, "1")]))
        rule = {"type": "capability", "total": total}
    elif name in USO_PRATICO_LEVELS:
        level = USO_PRATICO_LEVELS[name]
        passives.append(_passive(
            name,
            f"Oggetti di uso pratico fino al livello {level}.",
            "lama",
            [_set("forgia_uso_pratico", str(level))],
        ))
        rule = {"type": "practical_level", "level": level}
    elif name in FORGE_TABLE_RULES:
        rule = {"type": "table_rule", "text": FORGE_TABLE_RULES[name]}
    else:
        return None

    return {"passives": passives, "rule": rule, "key": FORGE_RULE_KEY}


def enchant_plan(skill_name: str) -> dict[str, Any] | None:
    """Passivi e metadata da scrivere su un'abilità Incantatore, o None."""
    name = skill_name.strip()
    passives: list[dict[str, Any]] = []
    rule: dict[str, Any] = {}

    if name in ENCHANT_LEVEL_CAPS:
        level, targets = ENCHANT_LEVEL_CAPS[name]
        passives.append(_passive(
            name,
            f"Incantamenti fino al livello {level}.",
            "runa",
            [_set(target, str(level)) for target in targets],
        ))
        rule = {"type": "enchant_level_cap", "level": level, "targets": list(targets)}
    elif name in INFUSORE_LEVELS:
        mana = INFUSORE_LEVELS[name]
        passives.append(_passive(
            name,
            f"Ogni livello di incantamento vale {mana} mana.",
            "runa",
            [_set("incanta_mana_per_livello", str(mana))],
        ))
        rule = {"type": "mana_per_level", "mana": mana}
    elif name in ANIMA_COMPRESSA_LEVELS:
        passives.append(_passive(
            name,
            "Cariche per oggetto +25%.",
            "runa",
            [_add("incanta_cariche_percento", str(ANIMA_COMPRESSA_LEVELS[name]))],
        ))
        rule = {"type": "charge_bonus", "percent": ANIMA_COMPRESSA_LEVELS[name]}
    elif name in MULTI_ENCHANT_LEVELS:
        maximum = MULTI_ENCHANT_LEVELS[name]
        passives.append(_passive(
            name,
            f"Fino a {maximum} effetti sullo stesso oggetto.",
            "runa",
            [_set("incanta_max_effetti", str(maximum))],
        ))
        rule = {"type": "multi_enchant", "max": maximum}
    elif name in ENCHANT_CAPABILITY_TOTALS:
        total = ENCHANT_CAPABILITY_TOTALS[name]
        passives.append(_passive(name, "Sblocca una capacità di incantamento.", "runa", [_add(total, "1")]))
        rule = {"type": "capability", "total": total}
    elif name in ENCHANT_TABLE_RULES:
        rule = {"type": "table_rule", "text": ENCHANT_TABLE_RULES[name]}
    else:
        return None

    return {"passives": passives, "rule": rule, "key": ENCHANT_RULE_KEY}


def plan_for(family_name: str, skill_name: str) -> dict[str, Any] | None:
    if family_name == "Fabbro":
        return forge_plan(skill_name)
    if family_name == "Incantatore":
        return enchant_plan(skill_name)
    return None

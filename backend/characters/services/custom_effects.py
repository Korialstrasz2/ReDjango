from __future__ import annotations

import re
from typing import Any, Mapping

from django.contrib.staticfiles import finders
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.templatetags.static import static

from backend.core.api import ApiError

from ..models import (
    PERSONAGGIO_TOT_KEYS,
    EffettoPersonalizzato,
    OperazioneEffettoPersonalizzato,
    Personaggio,
)
from .refresh_personaggio import (
    CalculationExpressionError,
    evaluate_expression,
    evaluate_number,
    normalize_stat_key,
    refresh_personaggio,
)


TEMPORARY_MARKER_RE = re.compile(r"\s*\(t\)\s*", re.IGNORECASE)
MAX_OPERATIONS = 24
EFFECT_ICON_DIRECTORY = "frontend/images/effects/icons"
ELDER_EFFECT_ICON_DIRECTORY = f"{EFFECT_ICON_DIRECTORY}/elder"

EFFECT_TARGET_LABELS = {
    "stanchezza": "Stanchezza",
    "modificatore_generale": "Modificatore generale",
    "fortuna": "Fortuna",
    "forza": "Forza",
    "resistenza": "Resistenza",
    "velocita": "Velocità",
    "agilita": "Agilità",
    "intelligenza": "Intelligenza",
    "concentrazione": "Concentrazione",
    "personalita": "Personalità",
    "saggezza": "Saggezza",
    "pf": "Punti ferita",
    "mana": "Mana",
    "energia": "Energia",
    "potere": "Potere",
    "pa": "Punti azione",
    "attacco": "Attacco",
    "difesa": "Difesa",
    "rd_fis": "Riduzione fisica",
    "res_contundente": "Resistenza contundente",
    "res_taglio": "Resistenza al taglio",
    "res_perforante": "Resistenza perforante",
    "res_fuoco": "Resistenza al fuoco",
    "res_gelo": "Resistenza al gelo",
    "res_elettro": "Resistenza elettrica",
    "rd_fuoco": "Riduzione fuoco",
    "rd_gelo": "Riduzione gelo",
    "rd_elettro": "Riduzione elettrica",
    "ap": "Perforazione armatura",
    "ap_percento": "Perforazione armatura (%)",
    "slot_magici": "Spazi magici",
    "slot_non_magici": "Spazi normali",
    "monete_per_slot": "Monete per spazio",
    "tier": "Tier",
    "sifone_di_mana": "Sifone di mana",
    "en_per_mana": "Energia per mana",
    "pa_per_mana": "PA per mana",
    "ogni_en_x_mana": "Mana ogni N energia",
    "ogni_pa_x_mana": "Mana ogni N PA",
    "sconto_mana_per_potere": "Sconto mana per potere",
    "sconto_pa_per_potere": "Sconto PA per potere",
    "mod_carico": "Passo di carico",
    "mod_peso_equip": "Sconto peso equipaggiamento (%)",
    "orecchini_max": "Orecchini massimi",
    "anelli_max": "Anelli massimi",
    "sacchi_max": "Sacchi massimi",
    "moltiplicatore_reagenti_rossi": "Moltiplicatore reagenti rossi",
    "moltiplicatore_reagenti_verdi": "Moltiplicatore reagenti verdi",
    "moltiplicatore_reagenti_blu": "Moltiplicatore reagenti blu",
    "moltiplicatore_reagenti_livello_1": "Effetto reagenti di livello 1",
    "moltiplicatore_reagenti_livello_2": "Effetto reagenti di livello 2",
    "moltiplicatore_reagenti_livello_3": "Effetto reagenti di livello 3",
    "moltiplicatore_reagenti_livello_4": "Effetto reagenti di livello 4",
    "atk_skill_taglio": "Attacco taglio",
    "atk_skill_contundente": "Attacco contundente",
    "atk_skill_perforante": "Attacco perforante",
    "atk_skill_corte": "Attacco con armi corte",
    "atk_skill_medie1": "Attacco con armi medie",
    "atk_skill_lunghe": "Attacco con armi lunghe",
    "atk_skill_precise": "Attacco con armi precise",
    "atk_skill_medie2": "Attacco con armi bilanciate",
    "atk_skill_potenti": "Attacco con armi potenti",
    "atk_skill_maninude": "Attacco a mani nude",
    "tier_skill_maninude": "Tier danno a mani nude",
    "def_skill_leggera": "Difesa con armatura leggera",
    "def_skill_pesante": "Difesa con armatura pesante",
    "def_skill_noarmatura": "Difesa senza armatura",
    "def_skill_scudo": "Difesa con scudo",
}

EFFECT_TARGETS = tuple(
    key
    for key in PERSONAGGIO_TOT_KEYS
    if key in EFFECT_TARGET_LABELS and key != "malus_carico"
)


def competence_effect_target_options() -> list[dict[str, str]]:
    """Expose competence extras to every structured effect editor.

    Competence targets deliberately live outside ``PERSONAGGIO_TOT_KEYS``: they
    are evaluated by the competence selector so an equipped item disappears
    from the total as soon as it is unequipped, without mutating the manual
    ``extra`` value owned by the character.
    """
    from backend.core.competence_defaults import COMPETENCE_DEFINITIONS

    return [
        {
            "value": f"competenza.{definition['key']}",
            "label": f"Competenza · {definition['name']} (extra)",
        }
        for definition in COMPETENCE_DEFINITIONS
    ]


def effect_target_options() -> list[dict[str, str]]:
    return [
        *[{"value": key, "label": EFFECT_TARGET_LABELS[key]} for key in EFFECT_TARGETS],
        *competence_effect_target_options(),
    ]


def effect_target_values() -> set[str]:
    return {option["value"] for option in effect_target_options()}

LEGACY_EFFECT_OPERATIONS = {
    "add": ("Aggiungi", "Somma il valore al totale calcolato."),
    "subtract": ("Sottrai", "Sottrae il valore dal totale calcolato."),
    "multiply": ("Moltiplica", "Moltiplica il totale corrente per il valore."),
    "percent": ("Percentuale", "Modifica il totale della percentuale indicata; usa -25 per ridurlo del 25%."),
    "min": ("Valore minimo", "Il risultato non può scendere sotto questo valore."),
    "max": ("Valore massimo", "Il risultato non può superare questo valore."),
    "cap": ("Limite massimo", "Sinonimo esplicito di valore massimo."),
    "set": ("Imposta", "Sostituisce il risultato con il valore indicato."),
    "formula_override": ("Sostituisci formula", "Sostituisce la formula base della statistica finché l'effetto è attivo."),
}

LEGACY_EFFECT_ICONS = (
    ("runa", "Runa arcana"),
    ("fiamma", "Fiamma"),
    ("gelo", "Gelo"),
    ("fulmine", "Fulmine"),
    ("scudo", "Scudo"),
    ("lama", "Lama"),
    ("cuore", "Vita"),
    ("pozione", "Pozione"),
    ("occhio", "Percezione"),
    ("vento", "Velocità"),
    ("luna", "Luna"),
    ("teschio", "Malattia o maledizione"),
)

LEGACY_FORMULA_GUIDE = (
    {
        "title": "Valori disponibili",
        "text": "Usa base.<stat> per il valore di partenza, pre.<stat> per l'istantanea prima degli effetti e final.<stat> per un valore già calcolato.",
        "example": "final.mod_forza * 2",
    },
    {
        "title": "Dati del personaggio",
        "text": "I dati anagrafici consentiti sono sotto personaggio, per esempio livello, monete o risorse spese.",
        "example": "floor(personaggio.livello / 3) + 1",
    },
    {
        "title": "Funzioni sicure",
        "text": "Sono disponibili floor, ceil, min, max, abs e round, oltre a +, -, *, / e **.",
        "example": "max(1, ceil(final.mana / 10))",
    },
    {
        "title": "Condizione opzionale",
        "text": "La riga si applica solo quando la condizione è vera. Lasciala vuota per applicarla sempre.",
        "example": "personaggio.livello >= 5",
    },
)


EFFECT_OPERATIONS = {
    "add": {"label": "Aggiungi", "description": "Somma il valore al totale corrente.", "example": "5 aggiunge cinque punti.", "timing": "Prima di moltiplicazioni e percentuali."},
    "subtract": {"label": "Sottrai", "description": "Sottrae il valore dal totale corrente.", "example": "3 sottrae tre punti.", "timing": "Dopo Aggiungi, prima di Moltiplica."},
    "multiply": {"label": "Moltiplica", "description": "Moltiplica il totale corrente per il valore.", "example": "1.5 porta 20 a 30.", "timing": "Dopo somme e sottrazioni."},
    "percent": {"label": "Percentuale", "description": "Aumenta o riduce il totale della percentuale indicata.", "example": "25 aumenta del 25%; -25 riduce del 25%.", "timing": "Dopo Moltiplica, prima dei limiti."},
    "min": {"label": "Valore minimo", "description": "Il risultato non può scendere sotto il valore indicato.", "example": "10 trasforma 7 in 10, ma lascia 14 invariato.", "timing": "Dopo le percentuali."},
    "max": {"label": "Valore massimo", "description": "Il risultato non può superare il valore indicato.", "example": "30 trasforma 42 in 30.", "timing": "Dopo il valore minimo."},
    "cap": {"label": "Limite massimo", "description": "Sinonimo esplicito di Valore massimo.", "example": "100 impedisce al campo di superare 100.", "timing": "Nella stessa fase dei valori massimi."},
    "set": {"label": "Imposta", "description": "Sostituisce il risultato della fase effetti, ma resta soggetto a stanchezza e modificatore generale.", "example": "50 imposta il campo a 50 prima delle correzioni rapide.", "timing": "Ultima operazione normale; tra più Imposta vince l'ultima nell'ordine effetti."},
    "strong_set": {"label": "Imposta forte", "description": "Blocca il valore finale del solo campo, anche dopo stanchezza, modificatore generale, limiti e arrotondamenti.", "example": "50 lascia il campo esattamente a 50.", "timing": "Ultimo passaggio assoluto; tra più Imposta forte vince l'ultima."},
    "formula_override": {"label": "Sostituisci formula", "description": "Sostituisce la formula base della statistica finché l'effetto è attivo.", "example": "base.pf + final.mod_resistenza * 8", "timing": "La nuova formula viene valutata prima delle operazioni normali."},
}

OPERATION_ORDER_NOTE = (
    "Le operazioni normali sono raggruppate in questo ordine: Aggiungi, Sottrai, Moltiplica, "
    "Percentuale, Valore minimo, Valore massimo/Limite, Imposta. Sostituisci formula agisce prima; "
    "Imposta forte agisce per ultima, dopo stanchezza e modificatore generale."
)

EXTRA_EFFECT_ICONS = (
    ("runa", "Runa arcana", "Arcano", "magia simbolo incantesimo"),
    ("fiamma", "Fiamma", "Elementi", "fuoco caldo bruciatura"),
    ("gelo", "Cristallo di gelo", "Elementi", "freddo ghiaccio neve"),
    ("fulmine", "Fulmine", "Elementi", "elettricità tuono shock"),
    ("scudo", "Scudo", "Combattimento", "difesa protezione barriera"),
    ("lama", "Lama", "Combattimento", "spada taglio arma"),
    ("cuore", "Cuore", "Risorse", "vita salute guarigione pf"),
    ("pozione", "Pozione", "Oggetti", "elisir alchimia cura"),
    ("occhio", "Occhio", "Sensi", "vista percezione rivelazione"),
    ("vento", "Vento", "Elementi", "aria velocità movimento"),
    ("luna", "Luna", "Arcano", "notte sogno magia"),
    ("teschio", "Teschio", "Afflizioni", "morte malattia maledizione"),
    ("sole", "Sole", "Arcano", "luce giorno energia"),
    ("stella", "Stella", "Arcano", "destino fortuna astrale"),
    ("corona", "Corona", "Stato", "potere comando regalità"),
    ("libro", "Libro", "Conoscenza", "studio intelligenza formula"),
    ("pergamena", "Pergamena", "Conoscenza", "scrittura missione regola"),
    ("chiave", "Chiave", "Oggetti", "apertura segreto accesso"),
    ("catena", "Catena", "Afflizioni", "vincolo rallentamento prigionia"),
    ("goccia", "Goccia", "Elementi", "acqua sangue liquido"),
    ("foglia", "Foglia", "Natura", "verde natura crescita"),
    ("artiglio", "Artiglio", "Creature", "bestia ferita attacco"),
    ("drago", "Drago", "Creature", "draconico fuoco potere"),
    ("demone", "Demone", "Creature", "daedra corna oscurità"),
    ("spirito", "Spirito", "Creature", "fantasma anima etereo"),
    ("veleno", "Veleno", "Afflizioni", "tossina danno verde"),
    ("malattia", "Malattia", "Afflizioni", "febbre contagio debolezza"),
    ("benedizione", "Benedizione", "Stato", "bonus sacro favore"),
    ("maledizione", "Maledizione", "Afflizioni", "malus oscuro sfortuna"),
    ("sangue", "Sangue", "Risorse", "ferita sacrificio vampiro"),
    ("luce", "Luce", "Elementi", "sacro bagliore alba"),
    ("ombra", "Ombra", "Elementi", "buio furtività notte"),
    ("tempo", "Tempo", "Arcano", "clessidra durata lentezza"),
    ("portale", "Portale", "Arcano", "teletrasporto varco evocazione"),
    ("musica", "Musica", "Stato", "canto bardo suono"),
    ("silenzio", "Silenzio", "Afflizioni", "muto magia bloccata"),
    ("invisibilita", "Invisibilità", "Stato", "nascosto furtivo trasparente"),
    ("paura", "Paura", "Afflizioni", "terrore fuga morale"),
    ("sonno", "Sonno", "Afflizioni", "riposo sogno stordito"),
    ("rigenerazione", "Rigenerazione", "Risorse", "cura recupero rinnovo"),
    ("barriera", "Barriera", "Combattimento", "protezione ward scudo"),
)

ELDER_EFFECT_ICON_VALUES = (
    "213131", "agilita_extra", "anelli_max_extra", "anello_blu", "ap_extra",
    "ap_percento_extra", "argnoiano", "armatura", "atk_skill_perforante_extra",
    "attacco_extra", "bussola", "calderone", "chiave", "cibo", "clessidra",
    "concentrazione_extra", "cuore", "difesa_extra", "effetto", "en_per_mana_caos_extra",
    "en_per_mana_ordine_extra", "energia_extra", "extra_1", "extra_2", "extra_3",
    "extra_4", "extra_5", "extra_6", "extra_7", "extra_8", "extra_9", "fortuna_extra",
    "forza_extra", "fuoco_extra", "gemma", "golem", "intelligenza_extra", "libro",
    "luna", "malattia", "mana_extra", "mod_carico_extra", "mod_gen", "mod_peso_equip_extra",
    "modificatore_generale", "modificatore_generale_extra", "monete_per_slot_extra",
    "ogni_en_x_mana_caos_extra", "ogni_en_x_mana_ordine_extra", "ogni_pa_x_mana_caos_extra",
    "ogni_pa_x_mana_ordine_extra", "orecchini_max_extra", "pa_extra", "pa_per_mana_caos_extra",
    "pa_per_mana_ordine_extra", "personalita_extra", "pf_extra", "potere_extra", "razza",
    "rd_elettro_extra", "rd_fis_extra", "rd_fuoco_extra", "rd_gelo_extra", "res_contundente_extra",
    "res_elettro_extra", "res_fuoco_extra", "res_gelo_extra", "res_perforante_extra",
    "res_taglio_extra", "resistenza_extra", "sacca_bonus_extra", "saggezza_extra",
    "sconto_mana_per_potere_extra", "sconto_pa_per_potere_extra", "scudo_viola",
    "sifone_di_mana_extra", "slot_magici_extra", "slot_non_magici_extra", "sole",
    "stanchezza_extra", "stefano", "teschio", "teschio_rosso", "tier_danno_extra",
    "tier_extra", "velocita_extra",
)

# ReDjango field keys keep their stable API values, while their artwork uses
# the corresponding historical Elder Django icon wherever one exists.
EFFECT_ICON_ASSET_ALIASES = {
    "stanchezza": "stanchezza_extra", "modificatore_generale": "modificatore_generale_extra",
    "fortuna": "fortuna_extra", "forza": "forza_extra", "resistenza": "resistenza_extra",
    "velocita": "velocita_extra", "agilita": "agilita_extra", "intelligenza": "intelligenza_extra",
    "concentrazione": "concentrazione_extra", "personalita": "personalita_extra", "saggezza": "saggezza_extra",
    "pf": "pf_extra", "mana": "mana_extra", "energia": "energia_extra", "potere": "potere_extra",
    "pa": "pa_extra", "attacco": "attacco_extra", "difesa": "difesa_extra", "rd_fis": "rd_fis_extra",
    "res_contundente": "res_contundente_extra", "res_taglio": "res_taglio_extra",
    "res_perforante": "res_perforante_extra", "res_fuoco": "res_fuoco_extra",
    "res_gelo": "res_gelo_extra", "res_elettro": "res_elettro_extra", "rd_fuoco": "rd_fuoco_extra",
    "rd_gelo": "rd_gelo_extra", "rd_elettro": "rd_elettro_extra", "ap": "ap_extra",
    "ap_percento": "ap_percento_extra", "slot_magici": "slot_magici_extra",
    "slot_non_magici": "slot_non_magici_extra", "monete_per_slot": "monete_per_slot_extra",
    "tier": "tier_extra", "sifone_di_mana": "sifone_di_mana_extra", "en_per_mana": "en_per_mana_ordine_extra",
    "pa_per_mana": "pa_per_mana_ordine_extra", "ogni_en_x_mana": "ogni_en_x_mana_ordine_extra",
    "ogni_pa_x_mana": "ogni_pa_x_mana_ordine_extra", "sconto_mana_per_potere": "sconto_mana_per_potere_extra",
    "sconto_pa_per_potere": "sconto_pa_per_potere_extra", "mod_carico": "mod_carico_extra",
    "mod_peso_equip": "mod_peso_equip_extra", "orecchini_max": "orecchini_max_extra",
    "anelli_max": "anelli_max_extra", "sacchi_max": "sacca_bonus_extra",
    "atk_skill_perforante": "atk_skill_perforante_extra",
}

_BASE_EFFECT_ICONS = EXTRA_EFFECT_ICONS + tuple(
    (key, label, "Statistiche", f"{key.replace('_', ' ')} {label}")
    for key, label in EFFECT_TARGET_LABELS.items()
    if key in EFFECT_TARGETS
)
_BASE_EFFECT_ICON_VALUES = {value for value, _label, _category, _keywords in _BASE_EFFECT_ICONS}
EFFECT_ICONS = _BASE_EFFECT_ICONS + tuple(
    (value, value.replace("_", " ").title(), "Elder Django", value.replace("_", " "))
    for value in ELDER_EFFECT_ICON_VALUES
    if value not in _BASE_EFFECT_ICON_VALUES
)

FORMULA_PERSONAGGIO_VALUES = (
    "personaggio.id", "personaggio.pk", "personaggio.livello", "personaggio.eta",
    "personaggio.monete", "personaggio.danno", "personaggio.mana_speso",
    "personaggio.energia_spesa", "personaggio.potere_speso", "personaggio.mana_in_sifone",
    "personaggio.pe_generali", "personaggio.pe_rossi", "personaggio.pe_verdi",
    "personaggio.pe_blu", "personaggio.pe_abilita",
)

FORMULA_GUIDE = (
    {"title": "Cos'è una formula", "text": "Al posto di un numero fisso puoi scrivere un calcolo. Viene rivalutato quando cambia il personaggio; non usare il segno = all'inizio.", "example": "5 + floor(personaggio.livello / 2)", "values": []},
    {"title": "I tre contesti statistici", "text": "base contiene i valori di partenza; pre è l'istantanea prima degli effetti; final contiene i valori già calcolati fino a quel punto. Un final non ancora calcolato vale 0: evita dipendenze circolari.", "example": "base.pf + final.mod_resistenza * 3", "values": ["base.<campo>", "pre.<campo>", "final.<campo>"]},
    {"title": "Campi statistici accettati", "text": "Sostituisci <campo> con uno di questi identificatori. L'autocomplete Campo mostra la stessa lista con nomi leggibili.", "example": "final.mana + base.potere", "values": list(PERSONAGGIO_TOT_KEYS)},
    {"title": "Valori numerici del personaggio", "text": "Questi valori descrivono il personaggio e le risorse spese. Sono i campi personaggio garantiti nelle formule numeriche.", "example": "floor(personaggio.livello / 3) + personaggio.mana_speso", "values": list(FORMULA_PERSONAGGIO_VALUES)},
    {"title": "Operatori accettati", "text": "Puoi usare parentesi e operatori aritmetici. La potenza usa due asterischi. Nelle condizioni sono accettati anche i confronti.", "example": "(final.mana + 5) * 1.25", "values": ["+ somma", "- sottrazione", "* moltiplicazione", "/ divisione", "** potenza", "== != > >= < <= confronti"]},
    {"title": "Funzioni sicure", "text": "Sono disponibili solo queste funzioni. Puoi annidarle se tutti gli argomenti sono numerici.", "example": "max(1, ceil(final.mana / 10))", "values": ["floor(x)", "ceil(x)", "round(x)", "abs(x)", "min(a, b, ...)", "max(a, b, ...)"]},
    {"title": "Condizione opzionale", "text": "La modifica si applica solo quando l'espressione è vera. Lasciala vuota per applicarla sempre; non usare testo libero.", "example": "personaggio.livello >= 5", "values": ["final.pf < 10", "personaggio.mana_speso > 0", "base.res_fuoco >= 25"]},
    {"title": "Esempi completi", "text": "Se vuoi un risultato terminale usa Imposta forte; se vuoi cambiare la formula strutturale usa Sostituisci formula.", "example": "max(0, final.mod_intelligenza * 2 + floor(personaggio.livello / 4))", "values": ["Bonus fisso: 5", "Bonus per livello: floor(personaggio.livello / 2)", "Dieci percento del mana: final.mana * 0.10", "Minimo dinamico: max(10, base.pf)"]},
)


def _effect_icon_image_url(value: str, label: str) -> str:
    elder_asset = EFFECT_ICON_ASSET_ALIASES.get(value, value)
    elder_path = f"{ELDER_EFFECT_ICON_DIRECTORY}/{elder_asset}.png"
    if finders.find(elder_path):
        return static(elder_path)
    relative_path = f"{EFFECT_ICON_DIRECTORY}/{label}.webp"
    return static(relative_path) if finders.find(relative_path) else ""


def effect_configuration_payload() -> dict[str, Any]:
    return {
        "targets": effect_target_options(),
        "operations": [
            {"value": value, **details}
            for value, details in EFFECT_OPERATIONS.items()
        ],
        "operationOrderNote": OPERATION_ORDER_NOTE,
        "icons": [
            {
                "value": value,
                "label": label,
                "category": category,
                "keywords": keywords,
                "imageUrl": _effect_icon_image_url(value, label),
            }
            for value, label, category, keywords in EFFECT_ICONS
        ],
        "formulaGuide": list(FORMULA_GUIDE),
    }


def _formula_contexts() -> dict[str, Mapping[str, Any]]:
    values = {key: 7 for key in PERSONAGGIO_TOT_KEYS}
    return {
        "base": values,
        "pre": values,
        "final": values,
        "personaggio": {
            "id": 1,
            "pk": 1,
            "livello": 5,
            "eta": 30,
            "monete": 100,
            "danno": 0,
            "mana_speso": 0,
            "energia_spesa": 0,
            "potere_speso": 0,
            "mana_in_sifone": 0,
            "pe_generali": 0,
            "pe_rossi": 0,
            "pe_verdi": 0,
            "pe_blu": 0,
            "pe_abilita": 0,
        },
    }


def _normalize_description(description: Any, temporary: bool) -> str:
    cleaned = TEMPORARY_MARKER_RE.sub(" ", str(description or ""))
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    if temporary:
        return f"{cleaned} (t)" if cleaned else "(t)"
    return cleaned


def _validate_expression(value: str, *, condition: bool = False) -> None:
    try:
        if condition:
            evaluate_expression(value, _formula_contexts())
        else:
            evaluate_number(value, _formula_contexts())
    except ZeroDivisionError:
        # The expression is structurally valid; live character data may make the denominator non-zero.
        return
    except (CalculationExpressionError, SyntaxError, TypeError, ValueError) as exc:
        raise ApiError(
            "effects.formula_invalid",
            f"Formula non valida: {exc}",
            "operations",
        ) from exc


def validate_effect_values(values: Mapping[str, Any]) -> dict[str, Any]:
    name = str(values.get("name") or "").strip()
    if not name:
        raise ApiError("effects.name_required", "Il nome dell'effetto è obbligatorio.", "name")
    if len(name) > 180:
        raise ApiError("effects.name_too_long", "Il nome dell'effetto è troppo lungo.", "name")

    description_input = str(values.get("description") or "")
    if "temporary" in values:
        temporary = bool(values.get("temporary"))
    else:
        temporary = bool(TEMPORARY_MARKER_RE.search(description_input))

    icon = str(values.get("icon") or "runa").strip().lower()
    allowed_icons = {value for value, _label, _category, _keywords in EFFECT_ICONS}
    if icon not in allowed_icons:
        raise ApiError("effects.icon_invalid", "Scegli un'icona disponibile.", "icon")

    operations_input = values.get("operations")
    if not isinstance(operations_input, list) or not operations_input:
        raise ApiError("effects.operations_required", "Aggiungi almeno una modifica all'effetto.", "operations")
    if len(operations_input) > MAX_OPERATIONS:
        raise ApiError(
            "effects.operations_limit",
            f"Un effetto può contenere al massimo {MAX_OPERATIONS} modifiche.",
            "operations",
        )

    operations: list[dict[str, Any]] = []
    for index, raw_operation in enumerate(operations_input):
        if not isinstance(raw_operation, Mapping):
            raise ApiError("effects.operation_invalid", "Una modifica dell'effetto non è valida.", "operations")
        target = normalize_stat_key(raw_operation.get("target"))
        if target not in effect_target_values():
            raise ApiError(
                "effects.target_invalid",
                f"Il bersaglio della modifica {index + 1} non è disponibile.",
                "operations",
            )
        operation = str(raw_operation.get("operation") or "").strip().lower()
        if operation not in EFFECT_OPERATIONS:
            raise ApiError(
                "effects.operation_invalid",
                f"L'operazione della modifica {index + 1} non è disponibile.",
                "operations",
            )
        if target.startswith("competenza.") and operation == "formula_override":
            raise ApiError(
                "effects.competence_formula_unsupported",
                "Per le competenze usa un bonus, un limite o Imposta: la sostituzione della formula non è disponibile.",
                "operations",
            )
        value = str(raw_operation.get("value") if raw_operation.get("value") is not None else "").strip()
        if not value:
            raise ApiError(
                "effects.value_required",
                f"Inserisci il valore o la formula della modifica {index + 1}.",
                "operations",
            )
        _validate_expression(value)
        condition = str(raw_operation.get("condition") or "").strip()
        if condition:
            _validate_expression(condition, condition=True)
        operations.append(
            {
                "ordine": index,
                "bersaglio": target,
                "operazione": operation,
                "valore": value,
                "condizione": condition,
            }
        )

    return {
        "nome": name,
        "descrizione": _normalize_description(description_input, temporary),
        "origine": str(values.get("origin") or "").strip()[:180],
        "icona": icon,
        "temporaneo": temporary,
        "operazioni": operations,
    }


def _locked_character(personaggio_id: int) -> Personaggio:
    try:
        return Personaggio.objects.select_for_update().select_related("effetti").get(pk=personaggio_id)
    except Personaggio.DoesNotExist as exc:
        raise ApiError("character.not_found", "Personaggio non trovato.", status=404) from exc


def _assert_name_available(personaggio: Personaggio, name: str, *, exclude_id: int | None = None) -> None:
    queryset = EffettoPersonalizzato.objects.filter(personaggio=personaggio, nome=name)
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.exists():
        raise ApiError(
            "effects.name_duplicate",
            "Esiste già un effetto personalizzato con questo nome.",
            "name",
            status=409,
        )


def _replace_operations(effect: EffettoPersonalizzato, operations: list[dict[str, Any]]) -> None:
    effect.operazioni.all().delete()
    OperazioneEffettoPersonalizzato.objects.bulk_create(
        [OperazioneEffettoPersonalizzato(effetto=effect, **operation) for operation in operations]
    )


@transaction.atomic
def create_custom_effect(personaggio_id: int, values: Mapping[str, Any]) -> Personaggio:
    personaggio = _locked_character(personaggio_id)
    validated = validate_effect_values(values)
    _assert_name_available(personaggio, validated["nome"])
    next_order = (
        EffettoPersonalizzato.objects.filter(personaggio=personaggio).aggregate(value=Max("ordine"))["value"] or 0
    ) + 1
    operations = validated.pop("operazioni")
    try:
        effect = EffettoPersonalizzato.objects.create(
            personaggio=personaggio,
            ordine=next_order,
            **validated,
        )
    except IntegrityError as exc:
        raise ApiError(
            "effects.name_duplicate",
            "Esiste già un effetto con questo nome.",
            "name",
            status=409,
        ) from exc
    _replace_operations(effect, operations)
    refresh_personaggio(personaggio)
    personaggio.refresh_from_db()
    return personaggio


@transaction.atomic
def update_custom_effect(
    personaggio_id: int,
    values: Mapping[str, Any],
    *,
    effect_id: int | None = None,
    legacy_slot: int | None = None,
) -> Personaggio:
    personaggio = _locked_character(personaggio_id)
    validated = validate_effect_values(values)

    if effect_id is not None:
        try:
            effect = EffettoPersonalizzato.objects.select_for_update().get(
                pk=effect_id,
                personaggio=personaggio,
            )
        except EffettoPersonalizzato.DoesNotExist as exc:
            raise ApiError("effects.not_found", "Effetto personalizzato non trovato.", status=404) from exc
        _assert_name_available(personaggio, validated["nome"], exclude_id=effect.id)
    elif legacy_slot is not None:
        if personaggio.effetti is None or not 1 <= int(legacy_slot) <= 50:
            raise ApiError(
                "effects.slot_not_found",
                "Lo spazio effetto non esiste.",
                "legacySlot",
                status=404,
            )
        field_name = f"effetto_{int(legacy_slot)}"
        if getattr(personaggio.effetti, field_name) is None:
            raise ApiError(
                "effects.slot_empty",
                "Lo spazio effetto è già vuoto.",
                "legacySlot",
                status=404,
            )
        _assert_name_available(personaggio, validated["nome"])
        next_order = (
            EffettoPersonalizzato.objects.filter(personaggio=personaggio).aggregate(value=Max("ordine"))["value"] or 0
        ) + 1
        effect = EffettoPersonalizzato(personaggio=personaggio, ordine=next_order)
        setattr(personaggio.effetti, field_name, None)
        personaggio.effetti.save(update_fields=[field_name, "updated_at"])
    else:
        raise ApiError("effects.id_required", "Scegli l'effetto da modificare.", "effectId")

    operations = validated.pop("operazioni")
    for field, value in validated.items():
        setattr(effect, field, value)
    effect.save()
    _replace_operations(effect, operations)
    refresh_personaggio(personaggio)
    personaggio.refresh_from_db()
    return personaggio


@transaction.atomic
def remove_custom_or_legacy_effect(
    personaggio_id: int,
    *,
    effect_id: int | None = None,
    legacy_slot: int | None = None,
) -> Personaggio:
    personaggio = _locked_character(personaggio_id)
    if effect_id is not None:
        deleted, _details = EffettoPersonalizzato.objects.filter(
            pk=effect_id,
            personaggio=personaggio,
        ).delete()
        if not deleted:
            raise ApiError("effects.not_found", "Effetto personalizzato non trovato.", status=404)
    elif legacy_slot is not None:
        if personaggio.effetti is None or not 1 <= int(legacy_slot) <= 50:
            raise ApiError(
                "effects.slot_not_found",
                "Lo spazio effetto non esiste.",
                "slot",
                status=404,
            )
        field_name = f"effetto_{int(legacy_slot)}"
        if getattr(personaggio.effetti, field_name) is None:
            raise ApiError(
                "effects.slot_empty",
                "Lo spazio effetto è già vuoto.",
                "slot",
                status=404,
            )
        setattr(personaggio.effetti, field_name, None)
        personaggio.effetti.save(update_fields=[field_name, "updated_at"])
    else:
        raise ApiError("effects.id_required", "Scegli l'effetto da rimuovere.", "effectId")

    refresh_personaggio(personaggio)
    personaggio.refresh_from_db()
    return personaggio


@transaction.atomic
def move_custom_effect(personaggio_id: int, effect_id: int, direction: str) -> Personaggio:
    personaggio = _locked_character(personaggio_id)
    effects = list(
        EffettoPersonalizzato.objects.select_for_update()
        .filter(personaggio=personaggio)
        .order_by("ordine", "nome", "id")
    )
    current_index = next((index for index, effect in enumerate(effects) if effect.id == effect_id), None)
    if current_index is None:
        raise ApiError("effects.not_found", "Effetto personalizzato non trovato.", status=404)
    offset = -1 if direction == "up" else 1 if direction == "down" else 0
    if not offset:
        raise ApiError("effects.direction_invalid", "Direzione di spostamento non valida.", "direction")
    target_index = current_index + offset
    if 0 <= target_index < len(effects):
        effects[current_index], effects[target_index] = effects[target_index], effects[current_index]
        for index, effect in enumerate(effects, start=1):
            if effect.ordine != index:
                effect.ordine = index
                effect.save(update_fields=["ordine"])
    personaggio.refresh_from_db()
    return personaggio

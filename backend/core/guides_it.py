import json
import re
import unicodedata
from collections.abc import Mapping
from html import unescape
from pathlib import Path
from typing import Any


V2_GUIDE_DEFAULT_VERSION = "2026-07-28-guide-system-review-v4"

CHARACTER_VARIABLE_GUIDE_NAME = "Variabili del personaggio e alchimia"
WEAPON_CATALOGUE_GUIDE_NAME = "Guida Armi"

RACE_GUIDE_RACES = (
    "Bosmer", "Dunmer", "Orsimer", "Altmer", "Imperiale", "Bretone",
    "Redguard", "Argoniano", "Khajiit", "Nord", "Falmer",
)


CHARACTER_VARIABLE_GROUPS = (
    (
        "Regole globali e caratteristiche",
        (
            ("stanchezza", "Stanchezza", "Ogni punto applica una penalità percentuale ai valori rapidi configurati dall'amministratore."),
            ("modificatore_generale", "Modificatore generale", "Ogni punto applica un bonus percentuale ai valori rapidi configurati dall'amministratore; può compensare la Stanchezza."),
            ("forza", "Forza", "Misura la potenza fisica. Le formule amministrative possono usarla per PF, Attacco o altri valori."),
            ("resistenza", "Resistenza", "Misura robustezza e tenuta. Le formule amministrative possono usarla per PF, Energia o altri valori."),
            ("velocita", "Velocità", "Misura rapidità e movimento. Le formule amministrative possono usarla per Energia, PA o altri valori."),
            ("agilita", "Agilità", "Misura coordinazione e destrezza. Le formule amministrative possono usarla per Attacco, Difesa o altri valori."),
            ("intelligenza", "Intelligenza", "Misura ragionamento e studio. Le formule amministrative possono usarla per Mana, Potere o altri valori."),
            ("concentrazione", "Concentrazione", "Misura attenzione e controllo. Le formule amministrative possono usarla per Mana, Difesa o altri valori."),
            ("personalita", "Personalità", "Misura presenza e influenza sociale; alimenta anche il relativo modificatore di dado."),
            ("saggezza", "Saggezza", "Misura intuito e giudizio. Le formule amministrative possono usarla per Potere, PA o altri valori."),
            ("fortuna", "Fortuna", "Misura la sorte del personaggio, alimenta il relativo modificatore di dado e interviene due volte in combattimento: nella differenza d'attacco (per l'attaccante conta come minimo 12) e nella potenza dei critici."),
        ),
    ),
    (
        "Risorse e combattimento",
        (
            ("pf", "Punti ferita", "Sono i PF massimi del personaggio; i PF correnti non possono superarli."),
            ("mana", "Mana", "È il Mana massimo disponibile per magie e capacità; il Mana corrente non può superarlo."),
            ("energia", "Energia", "È l'Energia massima usata dalle azioni che richiedono sforzo."),
            ("potere", "Potere", "È il Potere massimo, usato anche dagli sconti delle magie quando la relativa regola è attiva."),
            ("pa", "Punti azione", "Sono i PA disponibili nelle azioni di combattimento. Il carico li riduce, senza scendere sotto 4."),
            ("attacco", "Attacco", "È il valore sommato al d20 nella risoluzione d'attacco, prima delle specializzazioni d'arma e dei modificatori situazionali."),
            ("difesa", "Difesa", "È il valore sottratto al totale d'attacco per ottenere la differenza d'attacco, e il riferimento delle prove che richiedono una difesa."),
            ("tier", "Tier", "Indica la fascia di potenza del personaggio e sceglie la formula dei dadi di danno usata dalla risoluzione d'attacco (tabella configurabile da −5 a 30). È il bersaglio su cui il creator armi salva i bonus chiamati DMG."),
        ),
    ),
    (
        "Modificatori di dado",
        (
            ("mod_forza", "Modificatore di Forza", "Bonus o malus alle prove di Forza."),
            ("mod_resistenza", "Modificatore di Resistenza", "Bonus o malus alle prove di Resistenza."),
            ("mod_velocita", "Modificatore di Velocità", "Bonus o malus alle prove di Velocità."),
            ("mod_agilita", "Modificatore di Agilità", "Bonus o malus alle prove di Agilità."),
            ("mod_intelligenza", "Modificatore di Intelligenza", "Bonus o malus alle prove di Intelligenza."),
            ("mod_concentrazione", "Modificatore di Concentrazione", "Bonus o malus alle prove di Concentrazione."),
            ("mod_personalita", "Modificatore di Personalità", "Bonus o malus alle prove di Personalità."),
            ("mod_saggezza", "Modificatore di Saggezza", "Bonus o malus alle prove di Saggezza."),
            ("mod_fortuna", "Modificatore di Fortuna", "Bonus o malus alle prove di Fortuna."),
        ),
    ),
    (
        "Resistenze, riduzioni e perforazione",
        (
            ("rd_fis", "Riduzione danni fisici", "Sottrae una quantità fissa al danno fisico secondo le regole di combattimento."),
            ("res_contundente", "Resistenza contundente", "Livello di resistenza percentuale contro i danni contundenti."),
            ("res_taglio", "Resistenza al taglio", "Livello di resistenza percentuale contro i danni da taglio."),
            ("res_perforante", "Resistenza perforante", "Livello di resistenza percentuale contro i danni perforanti."),
            ("res_fuoco", "Resistenza al fuoco", "Livello di resistenza percentuale contro i danni da fuoco."),
            ("res_gelo", "Resistenza al gelo", "Livello di resistenza percentuale contro i danni da gelo."),
            ("res_elettro", "Resistenza elettrica", "Livello di resistenza percentuale contro i danni elettrici."),
            ("rd_fuoco", "Riduzione danni da fuoco", "Sottrae una quantità fissa ai danni da fuoco secondo le regole di combattimento."),
            ("rd_gelo", "Riduzione danni da gelo", "Sottrae una quantità fissa ai danni da gelo secondo le regole di combattimento."),
            ("rd_elettro", "Riduzione danni elettrici", "Sottrae una quantità fissa ai danni elettrici secondo le regole di combattimento."),
            ("ap", "Perforazione armatura", "Ignora una quantità fissa della protezione fisica e restituisce danno solo fino a quanto era stato assorbito. Vale sui danni Contundente, Perforante e Taglio."),
            ("ap_percento", "Perforazione armatura percentuale", "Ignora una percentuale della protezione assorbita e si somma ad AP senza mai superarla. Vale sui danni Contundente, Perforante e Taglio."),
        ),
    ),
    (
        "Carico, inventario ed equipaggiamento",
        (
            ("malus_carico", "Malus carico", "È calcolato dividendo il peso trasportato per Modificatore carico e arrotondando per difetto; riduce i PA."),
            ("mod_carico", "Modificatore carico", "Indica quanti punti di peso servono per generare un punto di Malus carico."),
            ("mod_peso_equip", "Riduzione peso equipaggiato", "Percentuale di peso ignorata per gli oggetti indossati prima di calcolare il carico."),
            ("slot_magici", "Spazi magici", "Numero di spazi iniziali dello zaino che ignorano il peso degli oggetti contenuti."),
            ("slot_non_magici", "Spazi non magici", "Numero di normali spazi aggiunti alla capacità dello zaino."),
            ("monete_per_slot", "Monete per spazio", "Numero di monete trasportate che occupa uno spazio dello zaino. Gli spazi Monete sono creati e rimossi automaticamente quando cambia il saldo personale."),
            ("orecchini_max", "Orecchini massimi", "Numero di slot Orecchino utilizzabili; gli slot successivi sono bloccati e non accettano oggetti."),
            ("anelli_max", "Anelli massimi", "Numero di slot Anello utilizzabili; gli slot successivi sono bloccati e non accettano oggetti."),
            ("sacchi_max", "Sacchi massimi", "Numero di slot Sacco utilizzabili; gli slot successivi sono bloccati e non accettano oggetti."),
        ),
    ),
    (
        "Mana e conversioni magiche",
        (
            ("sifone_di_mana", "Sifone di Mana", "Percentuale del Mana speso che il regolamento originario accumula nel sifone, arrotondata per difetto, per un successivo recupero."),
            ("en_per_mana", "Energia per Mana", "Rapporto diretto Energia/Mana conservato per le conversioni del regolamento originario; l'anteprima magie v2 usa invece Ogni EN per X Mana."),
            ("pa_per_mana", "PA per Mana", "Rapporto diretto PA/Mana conservato per le conversioni del regolamento originario; l'anteprima magie v2 usa invece Ogni PA per X Mana."),
            ("ogni_en_x_mana", "Ogni EN per X Mana", "Quantità di Mana proiettato che costa 1 Energia nell'anteprima magie; il costo viene arrotondato per eccesso."),
            ("ogni_pa_x_mana", "Ogni PA per X Mana", "Quantità di Mana proiettato che costa 1 PA nell'anteprima magie; il costo viene arrotondato per eccesso."),
            ("sconto_mana_per_potere", "Sconto Mana per Potere", "Mana sottratto al requisito della magia per ogni punto di Potere."),
            ("sconto_pa_per_potere", "Sconto PA per Potere", "PA sottratti al costo della magia per ogni punto di Potere."),
        ),
    ),
    (
        "Moltiplicatori alchimia",
        (
            ("moltiplicatore_reagenti_rossi", "Moltiplicatore reagenti rossi", "Bonus di colore applicato ai reagenti rossi; parte dal valore base amministrativo e riceve bonus da abilità, oggetti ed effetti."),
            ("moltiplicatore_reagenti_verdi", "Moltiplicatore reagenti verdi", "Bonus di colore applicato ai reagenti verdi; parte dal valore base amministrativo e riceve bonus da abilità, oggetti ed effetti."),
            ("moltiplicatore_reagenti_blu", "Moltiplicatore reagenti blu", "Bonus di colore applicato ai reagenti blu; parte dal valore base amministrativo e riceve bonus da abilità, oggetti ed effetti."),
            ("moltiplicatore_reagenti_livello_1", "Effetto reagenti livello 1", "Valore base dell'effetto di un reagente di livello 1, modificabile da abilità, oggetti ed effetti."),
            ("moltiplicatore_reagenti_livello_2", "Effetto reagenti livello 2", "Valore base dell'effetto di un reagente di livello 2, modificabile da abilità, oggetti ed effetti."),
            ("moltiplicatore_reagenti_livello_3", "Effetto reagenti livello 3", "Valore base dell'effetto di un reagente di livello 3, modificabile da abilità, oggetti ed effetti."),
            ("moltiplicatore_reagenti_livello_4", "Effetto reagenti livello 4", "Valore base dell'effetto di un reagente di livello 4, modificabile da abilità, oggetti ed effetti."),
        ),
    ),
    (
        "Specializzazioni d'attacco",
        (
            ("atk_skill_taglio", "Competenza d'attacco: taglio", "Bonus di specializzazione agli attacchi con armi da taglio secondo il regolamento originario."),
            ("atk_skill_contundente", "Competenza d'attacco: contundente", "Bonus di specializzazione agli attacchi con armi contundenti secondo il regolamento originario."),
            ("atk_skill_perforante", "Competenza d'attacco: perforante", "Bonus di specializzazione agli attacchi con armi perforanti secondo il regolamento originario."),
            ("atk_skill_corte", "Competenza d'attacco: armi corte", "Il sistema aggiunge questo bonus all'Attacco quando l'arma principale equipaggiata è corta."),
            ("atk_skill_medie1", "Competenza d'attacco: armi medie I", "Il sistema aggiunge questo bonus all'Attacco quando l'arma principale equipaggiata è media di tipo I."),
            ("atk_skill_lunghe", "Competenza d'attacco: armi lunghe", "Il sistema aggiunge questo bonus all'Attacco quando l'arma principale equipaggiata è lunga."),
            ("atk_skill_precise", "Competenza d'attacco: armi precise", "Il sistema aggiunge questo bonus all'Attacco quando l'arma principale equipaggiata è precisa."),
            ("atk_skill_medie2", "Competenza d'attacco: armi medie II", "Il sistema aggiunge questo bonus all'Attacco quando l'arma principale equipaggiata è media di tipo II."),
            ("atk_skill_potenti", "Competenza d'attacco: armi potenti", "Il sistema aggiunge questo bonus all'Attacco quando l'arma principale equipaggiata è potente."),
            ("atk_skill_maninude", "Competenza d'attacco: mani nude", "Il sistema aggiunge questo bonus all'Attacco quando non è equipaggiata un'arma principale."),
            ("tier_skill_maninude", "Tier: mani nude", "Il sistema aggiunge questo valore al Tier quando non è equipaggiata un'arma principale."),
        ),
    ),
    (
        "Specializzazioni di difesa",
        (
            ("def_skill_leggera", "Competenza di difesa: armatura leggera", "Il sistema aggiunge questo bonus alla Difesa quando è equipaggiata un'armatura leggera."),
            ("def_skill_pesante", "Competenza di difesa: armatura pesante", "Il sistema aggiunge questo bonus alla Difesa quando è equipaggiata un'armatura pesante."),
            ("def_skill_noarmatura", "Competenza di difesa: senza armatura", "Il sistema aggiunge questo bonus alla Difesa quando non è equipaggiata un'armatura."),
            ("def_skill_scudo", "Competenza di difesa: scudo", "Il sistema aggiunge questo bonus alla Difesa quando è equipaggiato uno scudo."),
        ),
    ),
)


def _display_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def character_variable_guide_blocks(
    base_values: Mapping[str, Any],
    formulas: Mapping[str, str],
    quick_stat_adjustment: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build the guide from the active administrator-controlled formula profile."""
    labels = {
        key: label
        for _group_label, entries in CHARACTER_VARIABLE_GROUPS
        for key, label, _description in entries
    }
    targets = {
        str(target)
        for target in quick_stat_adjustment.get("targets", set())
        if str(target) in labels
    }
    target_names = ", ".join(labels[target] for target in sorted(targets)) or "nessun valore"
    fatigue_rate = _display_number(quick_stat_adjustment.get("fatigue_percent_per_point", 0))
    fatigue_fixed_rate = _display_number(
        quick_stat_adjustment.get("fatigue_fixed_per_point", 0)
    )
    general_rate = _display_number(quick_stat_adjustment.get("general_modifier_percent_per_point", 0))
    general_fixed_rate = _display_number(
        quick_stat_adjustment.get("general_modifier_fixed_per_point", 0)
    )

    dependencies: dict[str, list[str]] = {key: [] for key in labels}
    for result_key, formula in formulas.items():
        for source_key in labels:
            if re.search(rf"\b(?:final|pre)\.{re.escape(source_key)}\b", str(formula)):
                dependencies[source_key].append(str(result_key))

    blocks: list[dict[str, Any]] = [
        {
            "type": "paragraph",
            "text": (
                "Questa guida elenca tutte le variabili tecniche del personaggio. Valori base, formule, "
                "percentuali e bersagli riportati qui provengono dal profilo Formule_base attivo: "
                "se un amministratore li cambia, questa pagina cambia con loro."
            ),
        },
        {
            "type": "callout",
            "title": "Ordine di calcolo",
            "text": (
                "Il sistema parte dai valori base, applica formule ed effetti, calcola il carico e infine "
                f"applica Stanchezza (-{fatigue_rate}% e -{fatigue_fixed_rate} fisso per punto) "
                f"e Modificatore generale (+{general_rate}% e +{general_fixed_rate} fisso per punto) "
                f"a: {target_names}. Percentuali e valori fissi precedono l'arrotondamento per difetto."
            ),
        },
    ]

    for group_label, entries in CHARACTER_VARIABLE_GROUPS:
        items: list[str] = []
        for key, label, description in entries:
            details = [description]
            if key == "stanchezza":
                details.append(
                    f"Configurazione attuale: -{fatigue_rate}% e "
                    f"-{fatigue_fixed_rate} fisso per punto su {target_names}."
                )
            elif key == "modificatore_generale":
                details.append(
                    f"Configurazione attuale: +{general_rate}% e "
                    f"+{general_fixed_rate} fisso per punto su {target_names}."
                )

            if key.startswith("mod_") and key not in {"mod_carico", "mod_peso_equip"}:
                characteristic = key.removeprefix("mod_")
                details.append(f"Calcolo attuale: ⌊({labels.get(characteristic, characteristic)} - 10) / 2⌋.")
            else:
                if key in base_values:
                    details.append(f"Valore base attuale: {_display_number(base_values[key])}.")
                if key in formulas:
                    details.append(f"Formula attuale: {formulas[key]}.")

            if dependencies[key]:
                dependent_labels = ", ".join(labels.get(item, item) for item in dependencies[key])
                details.append(f"È richiamata dalle formule attuali di: {dependent_labels}.")
            items.append(f"{label} ({key}) — {' '.join(details)}")
        blocks.extend(({"type": "heading", "text": group_label}, {"type": "list", "items": items}))
        if group_label == "Resistenze, riduzioni e perforazione":
            blocks.append(
                {
                    "type": "callout",
                    "title": "Scala delle resistenze",
                    "text": (
                        "Conversione livello → percentuale: -4 → -45%, -3 → -35%, -2 → -25%, -1 → -15%, "
                        "0 → 0%, 1 → 15%, 2 → 23%, 3 → 30%, 4 → 35%, 5 → 40%, 6 → 45%, "
                        "7 → 50%, 8 → 55%, 9 → 60%. La scala è modificabile dall'amministratore e i livelli "
                        "sono comunque limitati fra -4 e 9. L'attacco applica prima questa percentuale, "
                        "poi la RD fissa, infine il recupero da perforazione."
                    ),
                }
            )

    blocks.extend(
        (
            {"type": "heading", "text": "Borsa dei reagenti e alchimia"},
            {
                "type": "paragraph",
                "text": (
                    "La borsa conserva quantità di ingredienti e capacità massima. I moltiplicatori alchemici "
                    "sono invece variabili calcolate del personaggio, con valore base amministrativo e contributi "
                    "automatici di abilità, equipaggiamento ed effetti. "
                    "Nella scheda, Spazi occupati è la somma delle quantità positive e Spazi liberi è la capacità "
                    "meno tale somma. I nomi possono essere quelli classici per colore/livello oppure reagenti personalizzati."
                ),
            },
            {
                "type": "list",
                "items": [
                    "Regolamento originario: i reagenti sono Rossi, Verdi o Blu e hanno livello da 1 a 4.",
                    "Per creare una pozione si consumano fino a quattro reagenti; ciascuno contribuisce con il moltiplicatore del proprio livello.",
                    "Potenza finale originaria: (somma dei quattro moltiplicatori di livello) × (bonus del set alchemico + abilità).",
                    "Soglie originarie delle pozioni: livello 1 da potenza 3, poi un livello ogni 3 punti, fino al livello 10 da potenza 30.",
                    "Rosso: cura, difesa, attacco, riduzione PA, danno alla vita, vita temporanea, energia spesa.",
                    "Verde: aumento PA, visione, cura effetti, esplosione, stanchezza spesa, fumogeno.",
                    "Blu: mana, danno al mana, potere speso, resistenza magica, volo, invisibilità, intangibilità.",
                ],
            },
            {
                "type": "callout",
                "title": "Moltiplicatori colore",
                "text": (
                    "Rosso, Verde, Blu e i quattro livelli sono bersagli del normale sistema effetti. La scheda "
                    "mostra sempre il totale finale; rimuovere una skill o un oggetto rimuove automaticamente "
                    "anche il relativo contributo."
                ),
            },
        )
    )
    return blocks


WEAPON_TYPE_LABELS = {
    "accetta": "Accetta", "accettadalancio": "Accetta da lancio", "arcocomposito": "Arco composito",
    "arcocorto": "Arco corto", "arcolungo": "Arco lungo", "armblade": "Armblade", "ascia": "Ascia",
    "asciaaduemani": "Ascia a due mani", "balestra": "Balestra",
    "balestraaripetizione": "Balestra a ripetizione", "bastone": "Bastone",
    "bastoneconpesi": "Bastone con pesi", "bastonemagico": "Bastone magico",
    "beccodicorvo": "Becco di corvo", "chukonu": "Chu Ko Nu", "coltello": "Coltello",
    "coltellodalancio": "Coltello da lancio", "daga": "Daga", "estoc": "Estoc",
    "fioretto": "Fioretto", "grimorio": "Grimorio", "katana": "Katana", "kriss": "Kriss",
    "kusarigama": "Kusarigama", "lancia": "Lancia", "maninude": "Mani nude",
    "martello": "Martello", "martellodaguerra": "Martello da guerra", "mazza": "Mazza",
    "mazzafrusta": "Mazzafrusta", "natura1": "Forma naturale corta",
    "natura2": "Forma naturale media", "natura3": "Forma naturale lunga",
    "nunchaku": "Nunchaku", "picca": "Picca", "rapier": "Rapier", "sciabola": "Sciabola",
    "shiv": "Shiv", "shuriken": "Shuriken", "spadalunga": "Spada lunga", "spadone": "Spadone",
    "stiletto": "Stiletto", "tirapugni": "Tirapugni", "tonfa": "Tonfa", "tridente": "Tridente",
    "zweihander": "Zweihander",
}

_WEAPON_MODE_SECTIONS = (
    ("melee", "Armi da mischia", "Colpiscono in contatto. La lunghezza decide i PA per attacco e se servono due mani."),
    ("throwable", "Armi da lancio", "Gittata base 4 m, poi -2 ATK per cella; gittata massima pari alla Forza in metri; in mischia -4 ATK."),
    ("ranged", "Armi a distanza", "Gittata base 9 m, poi -2 ATK per cella; in mischia -7 ATK salvo eccezioni. Consumano munizioni dalla faretra."),
    ("unarmed", "Mani nude", "Profilo usato quando nessuna arma principale è equipaggiata."),
    ("magic", "Armi magiche", "Focalizzatori arcani con regole proprie."),
    ("nature", "Forme naturali", "Preset per artigli, zanne e attacchi naturali delle Unit."),
)

_WEAPON_LENGTH_SUMMARY = {
    "corta": "corta, 3 PA/attacco, una mano",
    "media": "media, 4 PA/attacco, una mano",
    "lunga": "lunga, 6 PA/attacco, due mani",
    "maninude": "mani nude, 2 PA/attacco",
}


def _weapon_label(name: str) -> str:
    return WEAPON_TYPE_LABELS.get(name, str(name or "").replace("_", " ").title())


def weapon_catalogue_guide_blocks(weapon_types: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build the weapon guide from the TipoArma catalogue actually loaded in the game.

    Every number shown here is read from the same presets the weapon creator uses,
    so the guide cannot drift away from the rules the server applies.
    """
    blocks: list[dict[str, Any]] = [
        {
            "type": "paragraph",
            "text": (
                "Ogni arma combina quattro assi indipendenti: pesantezza, lunghezza, precisione/potenza "
                "e tipo di danno. Questa pagina è generata dal catalogo Tipi arma caricato nel gioco: "
                "i valori qui sotto sono gli stessi che il creator armi propone e che il combattimento applica."
            ),
        },
        {
            "type": "callout",
            "title": "Come leggere una voce",
            "text": (
                "Nome — lunghezza e PA per attacco · pesantezza · precisione/potenza · tipo di danno · "
                "banda di prezzo. Il bonus in corsivo è la regola speciale del tipo: è un promemoria per il "
                "Master, non un'automazione."
            ),
        },
        {"type": "heading", "text": "Cosa modifica ogni asse"},
        {
            "type": "list",
            "items": [
                "Pesantezza — Leggera: +4 Attacco, +1 PA, -3 Tier. Media: nessun bonus. Pesante: -4 Attacco, +3 Tier, +1 Energia.",
                "Lunghezza — Corta: 3 PA/attacco, -2 Tier, +3 AP. Media: 4 PA/attacco, +1 Tier. Lunga: 6 PA/attacco, +5 Tier, +10% AP. Mani nude: 2 PA/attacco.",
                "Tipo di danno — Perforante: +1 Tier. Taglio: +1 PA. Contundente: +1 Energia. Magico e Natura non aggiungono modificatori.",
                "Precisione/potenza — non modifica le statistiche: sceglie soltanto quale competenza d'attacco si applica (Precisa, Media o Potente).",
                "Materiale — famiglia leggera: +2 PA e +1 Attacco. Famiglia pesante: +2 Energia e +1 Tier. Il tier del materiale (1-7) guida solo il prezzo suggerito.",
            ],
        },
        {
            "type": "callout",
            "title": "I bonus DMG sono Tier",
            "text": (
                "Tutto ciò che il regolamento chiama bonus al danno è salvato sul bersaglio tier, che sceglie "
                "la formula dei dadi di danno. Non esiste un bonus di danno fisso separato."
            ),
        },
    ]

    by_mode: dict[str, list[Mapping[str, Any]]] = {}
    incomplete: list[Mapping[str, Any]] = []
    for entry in weapon_types:
        if entry.get("incomplete"):
            incomplete.append(entry)
        else:
            by_mode.setdefault(str(entry.get("combatMode") or "melee"), []).append(entry)

    for mode, title, description in _WEAPON_MODE_SECTIONS:
        entries = by_mode.get(mode)
        if not entries:
            continue
        blocks.extend(({"type": "heading", "text": title}, {"type": "paragraph", "text": description}))
        items: list[dict[str, str]] = []
        for entry in sorted(entries, key=lambda item: _weapon_label(str(item.get("name") or ""))):
            length = str(entry.get("length") or "")
            details = [_WEAPON_LENGTH_SUMMARY.get(length, length)]
            for key in ("heaviness", "power", "damageType"):
                value = str(entry.get(key) or "")
                if value and value != "maninude":
                    details.append(value)
            band = str(entry.get("costBand") or "")
            if band:
                details.append(f"banda {band}")
            items.append(
                {
                    "title": _weapon_label(str(entry.get("name") or "")),
                    "meta": " · ".join(detail for detail in details if detail),
                    "note": " ".join(str(note) for note in entry.get("bonusNotes") or []),
                }
            )
        blocks.append({"type": "entries", "items": items})

    if incomplete:
        blocks.extend(
            (
                {"type": "heading", "text": "Tipi arma da completare"},
                {
                    "type": "warning",
                    "title": "Profilo mancante",
                    "text": (
                        "Questi Tipi arma non hanno un profilo completo, quindi il creator non può proporne i "
                        "modificatori: "
                        + ", ".join(
                            _weapon_label(str(entry.get("name") or ""))
                            for entry in sorted(incomplete, key=lambda item: str(item.get("name") or ""))
                        )
                        + ". Completali dall'Amministrazione oppure archiviali."
                    ),
                },
            )
        )

    blocks.extend(
        (
            {"type": "heading", "text": "Una mano, due mani e doppia impugnatura"},
            {
                "type": "list",
                "items": [
                    "La lunghezza determina le mani: Corta e Media sono a una mano, Lunga richiede due mani e lo slot Scudo libero.",
                    "Per la doppia impugnatura inserisci una seconda arma Corta o Media nello slot Scudo.",
                    "Una sola arma è primaria: soltanto i suoi effetti e le sue categorie modificano la scheda.",
                    "Cambiare arma primaria dalla scheda o dal combattimento non costa Punti Azione.",
                ],
            },
            {"type": "heading", "text": "Munizioni e ricarica"},
            {
                "type": "list",
                "items": [
                    "Un'arma consuma munizioni solo se ha modalità a distanza e un tipo di munizione configurato (freccia, dardo o proiettile).",
                    "Capacità del caricatore, costo fisso di ricarica e costo per proiettile sono salvati nel profilo dell'arma e usati dalla postazione Combattimento.",
                    "Le frecce e i dardi vengono prelevati dalla faretra del personaggio.",
                ],
            },
            {
                "type": "callout",
                "title": "I modificatori sono incorporati una sola volta",
                "text": (
                    "Il creator mostra un'anteprima e il comando Applica modificatori suggeriti. Solo quel comando "
                    "copia i bonus negli effetti dell'oggetto e il costo PA nel record. Dopo il salvataggio non vengono "
                    "ricalcolati: puoi cambiare categoria, togliere bonus o creare un'arma con le stesse categorie e "
                    "nessun modificatore. Prezzo e peso delle bande sono suggerimenti, non vincoli."
                ),
            },
        )
    )
    return blocks


def _guide_content(*blocks: dict) -> str:
    return json.dumps(list(blocks), ensure_ascii=False, indent=2)


def _difference_warning(text: str) -> dict[str, str]:
    return {
        "type": "warning",
        "title": "Differenze rispetto al sistema attuale",
        "text": text,
    }


_ELDER_RULES_PATH = Path(__file__).with_name("regole_varie_elder.html")

_RULE_STATUS_NOTES: dict[str | tuple[str, str], tuple[str, str]] = {
    "INDICE": ("implemented", "INDICE ORIGINALE — I collegamenti restano interni a questa guida e portano alle sezioni Elder sottostanti."),
    "BASE": ("partial", "PARZIALMENTE IMPLEMENTATO — In ReDjango si possono usare tutti i dadi: il d20 risolve gli attacchi, le competenze salgono da d6 a d12 e gli strumenti rapidi tirano qualsiasi set configurato. Le risorse sono conservate, ma non tutte le eccezioni Elder sono applicate automaticamente."),
    "Risorse del Personaggio": ("partial", "PARZIALMENTE IMPLEMENTATO — PF, Mana, Energia, Potere, PA e Stanchezza sono presenti. NON ANCORA IMPLEMENTATI: morte a −Resistenza PF, raddoppio automatico dei PA a 0 PF, ciclo Energia −1/Stanchezza e recuperi completi del riposo."),
    "Competenze e Barre": ("implemented", "IMPLEMENTATO — Due barre 0–7, costo progressivo, tecniche in Energia, dadi superiori e reroll giornalieri sono gestiti nella pagina Competenze."),
    "Lista Competenze": ("implemented", "IMPLEMENTATO — Le 21 competenze Elder sono presenti nell’atlante ReDjango."),
    "Check di Competenza": ("implemented", "IMPLEMENTATO — Il tiro è server-side e somma i bonus; soglia e interpretazione restano al Master, come previsto dalla guida."),
    "Equipaggiamento e Slot": ("partial", "PARZIALMENTE IMPLEMENTATO — Slot, zaino, faretre, limiti di anelli/orecchini/sacchi, compatibilità e peso sono gestiti. Alcune incompatibilità narrative Elder fra strati di vestiario non sono ancora automatizzate."),
    "COMBAT": ("implemented", "IMPLEMENTATO — La postazione Combattimento risolve l’attacco lato server: d20, differenza d’attacco, moltiplicatore di danno, Tier, critici, resistenze, RD e perforazione. Restano manuali soltanto iniziativa e ordine dei turni."),
    "Turni, Iniziativa e Punti Azione": ("partial", "PARZIALMENTE IMPLEMENTATO — Movimento su griglia e costo in PA sono calcolati (percorso più rapido, moltiplicatori di terreno, celle bloccate o invalicabili, PA arrotondati per eccesso). NON ANCORA IMPLEMENTATI iniziativa e ordine dei turni: il Master li gestisce a mano."),
    "Attacco, Difesa e Risoluzione": ("implemented", "IMPLEMENTATO — Catena completa: differenza = −4 + Attacco + d20 − Difesa + mod. Fortuna attaccante (calcolato su una Fortuna minima di 12) − mod. Fortuna difensore, limitata da −25 a +45; la tabella d20 × differenza dà la percentuale di danno; il Tier sceglie la formula dei dadi; poi resistenza percentuale, RD fissa e recupero da perforazione. Il tiro di 1 è sempre fallimento critico."),
    "Critici": ("partial", "PARZIALMENTE IMPLEMENTATO — I critici sono risolti: le soglie crit_min/crit_nor/crit_mag danno +40%/+60%/+80% di danno, corretti dalla Fortuna e dalla differenza d’attacco. NON ANCORA IMPLEMENTATI gittata, malus in mischia e attacchi di opportunità, che restano regole manuali; la ricarica delle armi a distanza è invece gestita dalla postazione."),
    "MALATTIE E STATUS": ("partial", "PARZIALMENTE IMPLEMENTATO — Gli effetti strutturati possono rappresentare stati e malattie; NON ANCORA IMPLEMENTATI guarigione giornaliera, Cura Effetti e scadenza completa legata alla causa."),
    "Status": ("partial", "PARZIALMENTE IMPLEMENTATO — I singoli status possono essere creati come effetti, ma questo catalogo Elder non è ancora applicato e risolto automaticamente."),
    "Malattie": ("partial", "PARZIALMENTE IMPLEMENTATO — Le malattie possono essere registrate come effetti persistenti, ma tiri, progressione, Astinenza e guarigione non sono automatizzati."),
    "SCASSINARE e BORSEGGIARE": ("missing", "NON ANCORA IMPLEMENTATO — Mancano workflow dedicati per serrature, usura degli attrezzi, soglie, furtività e borseggio."),
    "LIVELLI": ("missing", "NON ANCORA IMPLEMENTATO — La tabella XP, le quattro categorie di PE e l’assegnazione automatica dei perk per livello non sono attive in ReDjango."),
    "Caratteristiche e Influenza sulle Statistiche": ("partial", "PARZIALMENTE IMPLEMENTATO — Le caratteristiche e le dipendenze esistono, ma le formule ReDjango sono amministrabili. Verificare sempre la guida dinamica “Variabili del personaggio e alchimia”."),
    "Calcolo delle Statistiche di Base": ("incorrect", "NON CORRETTO COME FORMULA FISSA PER REDJANGO — Queste sono le formule Elder originali; ReDjango usa il profilo Formule_base attivo, che può essere modificato dall’amministratore."),
    "CREA PG": ("partial", "PARZIALMENTE IMPLEMENTATO — Personaggi, razze, caratteristiche ed effetti sono gestibili; NON ANCORA IMPLEMENTATO un wizard giocatore che esegua l’intera procedura Elder."),
    "RESURREZIONE": ("missing", "NON ANCORA IMPLEMENTATO — Finestra di 48 ore, integrità del corpo, sacrificio e malus post-resurrezione sono regole manuali."),
    "EVOCAZIONE": ("missing", "NON ANCORA IMPLEMENTATO — Creature evocate, limiti, cattura anima, durata e costi non hanno un sistema dedicato."),
    "INSEGNAMENTO": ("missing", "NON ANCORA IMPLEMENTATO — Gli sconti alle skill esistono, ma lezioni, tempo, pagamento e trasferimento fra PG non sono un workflow automatico."),
    "GRIMORI": ("missing", "NON ANCORA IMPLEMENTATO — Scrittura, cancellazione, mani libere, voce, magie contenute e cariche del grimorio non sono automatizzati."),
    "CAVALCARE": ("missing", "NON ANCORA IMPLEMENTATO — Selle, andature, movimento, malus e prove in combattimento non hanno un sistema dedicato."),
    "ALCHIMIA, INCANTAMENTO E FORGIATURA": ("partial", "PARZIALMENTE IMPLEMENTATO — Alchimia è operativa; Incantamento e Forgiatura sono visibili nella Creazione ma non ancora implementati."),
    "Alchimia": ("implemented", "IMPLEMENTATO CON DIFFERENZE REDJANGO — Borsa, 42 ingredienti Elder, estrazione, anteprima e distillazione transazionale sono attive."),
    ("Alchimia", "Introduzione"): ("partial", "PARZIALMENTE IMPLEMENTATO — La creazione è attiva; tempi narrativi di 15/10 minuti e percentuale del set non fanno avanzare automaticamente un orologio di campagna."),
    "Reagenti e Ingredienti": ("implemented", "IMPLEMENTATO — Colori Rosso/Verde/Blu, livelli 1–4 e moltiplicatori calcolati sono presenti."),
    "Meccaniche di Creazione delle Pozioni": ("incorrect", "DIFFERENZA REDJANGO — La miscela ReDjango accetta fino a quattro reagenti e usa la formula/anteprima del backend; non applicare come limite automatico la frase Elder dei tre slot base."),
    "Regole Speciali di Alchimia": ("partial", "PARZIALMENTE IMPLEMENTATO — Estrazione e distillazione sono attive; fusione 3→1 e tutte le abilità speciali di produzione multipla non sono ancora complete."),
    "Incantamento": ("missing", "NON ANCORA IMPLEMENTATO — La scheda Creazione mostra la sede futura, ma non esegue incantamenti."),
    ("Incantamento", "Introduzione"): ("missing", "NON ANCORA IMPLEMENTATO — Tempi, anime per PF e gemme nere restano regole manuali."),
    "Incantare Oggetti": ("missing", "NON ANCORA IMPLEMENTATO — Altare, gemme, cariche, pergamene e consumo degli incantesimi non sono gestiti."),
    "Forgiatura": ("missing", "NON ANCORA IMPLEMENTATO — La sede è presente nella Creazione, ma non esegue fusione, creazione o miglioramento."),
    "Materiali e Livelli": ("partial", "SOLO DATI PARZIALI — Materiali e fasce Elder possono apparire nel catalogo oggetti; requisiti di lavorazione e progressione non sono automatizzati."),
    "Creazione degli Oggetti": ("missing", "NON ANCORA IMPLEMENTATO — Lingotti, tempi e rese delle munizioni non vengono consumati o prodotti automaticamente."),
    "Miglioramento degli Oggetti": ("missing", "NON ANCORA IMPLEMENTATO — I miglioramenti elencati non hanno ancora un servizio transazionale di forgiatura."),
    "Cumulare Miglioramenti": ("missing", "NON ANCORA IMPLEMENTATO — Il raddoppio cumulativo dei costi non è calcolato dal sistema."),
    "MODIFICATORI DI GIOCO": ("partial", "PARZIALMENTE IMPLEMENTATO — Le variabili esistono e possono ricevere effetti. Quelle di combattimento (Tier, resistenze, RD, perforazione, Attacco, Difesa, Fortuna) sono calcolate e applicate; altre sono conservate in attesa delle regole che le useranno."),
    "stanchezza": ("implemented", "IMPLEMENTATO CON CONFIGURAZIONE REDJANGO — Il valore entra nei totali secondo il profilo amministrativo attivo; la percentuale Elder −8% non è necessariamente fissa."),
    "modificatore_generale": ("implemented", "IMPLEMENTATO CON CONFIGURAZIONE REDJANGO — Il valore modifica i bersagli configurati; il +12% Elder non è necessariamente fisso."),
    "fortuna": ("partial", "PARZIALMENTE IMPLEMENTATO — Fortuna e relativo modificatore sono disponibili ai dadi e alle formule; non tutti gli effetti indiretti Elder sono automatizzati."),
    "rd_fis": ("implemented", "IMPLEMENTATO — RD fisica è sottratta dopo la resistenza a ogni danno Contundente, Perforante e Taglio. La perforazione dell’attaccante può recuperare quanto è stato assorbito, mai di più."),
    "res_contundente": ("implemented", "IMPLEMENTATO — Il livello è convertito in percentuale dalla scala configurata e sottratto al danno contundente. L'ordine è: resistenza percentuale, poi RD fissa, poi recupero da perforazione."),
    "res_taglio": ("implemented", "IMPLEMENTATO — Il livello è convertito in percentuale dalla scala configurata e sottratto al danno da taglio. L'ordine è: resistenza percentuale, poi RD fissa, poi recupero da perforazione."),
    "res_perforante": ("implemented", "IMPLEMENTATO — Il livello è convertito in percentuale dalla scala configurata e sottratto al danno perforante. L'ordine è: resistenza percentuale, poi RD fissa, poi recupero da perforazione."),
    "res_fuoco": ("implemented", "IMPLEMENTATO — Il livello è convertito in percentuale e sottratto al danno da fuoco; la riduzione fissa usata è rd_fuoco, non rd_fis."),
    "res_gelo": ("implemented", "IMPLEMENTATO — Il livello è convertito in percentuale e sottratto al danno da gelo; la riduzione fissa usata è rd_gelo, non rd_fis."),
    "res_elettro": ("implemented", "IMPLEMENTATO — Il livello è convertito in percentuale e sottratto al danno elettrico; la riduzione fissa usata è rd_elettro, non rd_fis."),
    "rd_fuoco": ("implemented", "IMPLEMENTATO — Sottratta al danno da fuoco dopo la resistenza. La perforazione non la recupera: agisce solo sui danni fisici."),
    "rd_gelo": ("implemented", "IMPLEMENTATO — Sottratta al danno da gelo dopo la resistenza. La perforazione non la recupera: agisce solo sui danni fisici."),
    "rd_elettro": ("implemented", "IMPLEMENTATO — Sottratta al danno elettrico dopo la resistenza. La perforazione non la recupera: agisce solo sui danni fisici."),
    "slot_magici": ("incorrect", "NON CORRETTO PER REDJANGO — Qui la descrizione Elder parla di equipaggiamento magico; in ReDjango slot_magici indica gli spazi iniziali dello zaino che ignorano il peso."),
    "slot_non_magici": ("implemented", "IMPLEMENTATO — Aggiunge spazi normali allo zaino ReDjango."),
    "monete_per_slot": ("implemented", "IMPLEMENTATO — Le monete personali occupano automaticamente spazi protetti nello zaino; l'eccedenza può essere trasferita esplicitamente alle monete condivise della campagna."),
    "tier": ("implemented", "IMPLEMENTATO — Il Tier totale dell’attaccante sceglie la formula dei dadi di danno nella tabella configurata (da −5 a 30, per esempio 0 → 1d8, 4 → 2d6, 10 → 3d10). È il bersaglio su cui il creator armi salva i bonus chiamati DMG."),
    "sifone_di_mana": ("missing", "NON ANCORA IMPLEMENTATO — La variabile è disponibile, ma accumulo e recupero del sifone non hanno un flusso completo."),
    "ogni_en_x_mana_ordine": ("incorrect", "NOME LEGACY NON CORRETTO PER REDJANGO — ReDjango usa il rapporto unificato ogni_en_x_mana nell’anteprima magie, senza rami Ordine/Caos separati."),
    "ogni_pa_x_mana_ordine": ("incorrect", "NOME LEGACY NON CORRETTO PER REDJANGO — ReDjango usa il rapporto unificato ogni_pa_x_mana nell’anteprima magie, senza rami Ordine/Caos separati."),
    "ogni_en_x_mana_caos": ("incorrect", "NON PRESENTE COME VARIABILE SEPARATA IN REDJANGO — Usare ogni_en_x_mana."),
    "ogni_pa_x_mana_caos": ("incorrect", "NON PRESENTE COME VARIABILE SEPARATA IN REDJANGO — Usare ogni_pa_x_mana."),
    "sconto_mana_per_potere": ("partial", "PARZIALMENTE IMPLEMENTATO — Lo sconto entra nell’anteprima magia; esecuzione e spesa completa della magia non sono ancora implementate."),
    "sconto_pa_per_potere": ("partial", "PARZIALMENTE IMPLEMENTATO — Lo sconto entra nell’anteprima magia; esecuzione e spesa completa della magia non sono ancora implementate."),
    "mod_carico": ("implemented", "IMPLEMENTATO — Il malus usa floor(peso / mod_carico) e riduce i PA senza scendere sotto 4."),
    "mod_peso_equip": ("implemented", "IMPLEMENTATO — Riduce percentualmente il peso equipaggiato prima del calcolo del carico."),
    "orecchini_max": ("implemented", "IMPLEMENTATO — Gli slot oltre il limite sono bloccati."),
    "anelli_max": ("implemented", "IMPLEMENTATO — Gli slot oltre il limite sono bloccati."),
    "sacchi_max": ("implemented", "IMPLEMENTATO — Gli slot oltre il limite sono bloccati."),
}


def _heading_text(raw_heading: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", "", raw_heading)).split())


def race_guide_html(source: str) -> str:
    """Add stable race anchors and a compact table of contents to Elder's HTML guide."""
    races: list[tuple[str, str]] = []

    def add_anchor(match: re.Match[str]) -> str:
        attributes, inner_html = match.group(1), match.group(2)
        heading = _heading_text(inner_html)
        race = next((name for name in RACE_GUIDE_RACES if re.search(rf"\b{re.escape(name)}\b", heading)), None)
        if not race:
            return match.group(0)
        anchor = "race-" + unicodedata.normalize("NFKD", race).encode("ascii", "ignore").decode().lower()
        races.append((race, anchor))
        if re.search(r'\bid\s*=', attributes, flags=re.IGNORECASE):
            return match.group(0)
        return f'<h3{attributes} id="{anchor}">{inner_html}</h3>'

    content = re.sub(r"<h3([^>]*)>(.*?)</h3>", add_anchor, source, flags=re.IGNORECASE | re.DOTALL)
    if not races:
        return content
    index = "".join(f'<li><a href="#{anchor}">{race}</a></li>' for race, anchor in races)
    return f'<nav class="race-guide-index" aria-label="Indice delle razze"><strong>Razze</strong><ul>{index}</ul></nav>{content}'


def _annotated_elder_rules_html() -> str:
    source = _ELDER_RULES_PATH.read_text(encoding="utf-8")
    current_h2 = ""

    def add_note(match: re.Match[str]) -> str:
        nonlocal current_h2
        level = match.group(1)
        heading = match.group(0)
        title = _heading_text(match.group(2))
        if level == "2":
            current_h2 = title
        note = _RULE_STATUS_NOTES.get((current_h2, title)) or _RULE_STATUS_NOTES.get(title)
        if not note:
            return heading
        status, text = note
        return (
            f'{heading}<aside class="guide-implementation-note guide-status-{status}" '
            f'role="note"><strong>Nota ReDjango</strong><p>{text}</p></aside>'
        )

    return re.sub(r"<h([1-3])\b[^>]*>(.*?)</h\1>", add_note, source, flags=re.IGNORECASE | re.DOTALL)


def _redjango_rules_guide_content() -> str:
    return _guide_content({"type": "legacy_html", "html": _annotated_elder_rules_html()})


CODE_ITEM_EFFECTS = """[
  {"target": "attacco", "operation": "add", "value": 3},
  {"target": "pf", "operation": "add", "value": "floor(personaggio.livello / 2)"}
]"""

CODE_SKILL = """{
  "nome": "Svelto 2",
  "slug": "svelto-2",
  "numero": 100000002,
  "famiglia": "Combattimento",
  "ordine_famiglia": 20,
  "costo_pe": 5,
  "tipo_pe": "general",
  "prerequisiti": ["Svelto 1"],
  "requisiti": "Richiede Svelto 1.",
  "metadata": {
    "unlockRequirements": [
      {"type": "caratteristica", "stat": "velocita", "minimum": 12}
    ]
  }
}"""

CODE_EFFECT = """{
  "nome": "Guardia salda",
  "tipo": "passivo",
  "origine_tipo": "skill",
  "origine_nome": "Difensore",
  "effect_payload": {
    "operations": [
      {"target": "difesa", "operation": "add", "value": 2},
      {"target": "pf", "operation": "add", "value": "floor(personaggio.livello / 3)",
       "condition": "personaggio.livello >= 5"}
    ]
  }
}"""

CODE_DISEASE = """{
  "tipo": "malattia",
  "nome": "Febbre delle paludi",
  "descrizione": "Indebolisce il viaggiatore finche non viene curato.",
  "default_duration_turns": 6,
  "stacking_rule": "refresh",
  "icon": "veleno",
  "effect_payload": {
    "operations": [
      {"target": "energia", "operation": "subtract", "value": 2}
    ]
  }
}"""


V2_GUIDE_DEFAULTS = [
    {
        "seed_key": "regole-varie",
        "nome": "Regole Varie — ReDjango",
        "categoria": "Regolamento",
        "ordine": 5,
        "contenuto": _redjango_rules_guide_content(),
    },
    {
        "seed_key": "oggetti",
        "nome": "Creare oggetti correttamente",
        "categoria": "Contenuti",
        "ordine": 10,
        "contenuto": _guide_content(
            {
                "type": "paragraph",
                "text": (
                    "Usa Oggetto per modelli riutilizzabili: armi, armature, ingredienti, accessori, "
                    "strumenti e bottino. Il record descrive l'oggetto; i modificatori automatici vanno "
                    "in effects, non nascosti soltanto nella descrizione."
                ),
            },
            {
                "type": "list",
                "items": [
                    "Mantieni nome univoco e leggibile: è il campo su cui il resto del sistema ritrova l'oggetto.",
                    "Usa tipo_1 fino a tipo_4 scegliendo opzioni configurate nell'Amministrazione Django. tipo_1 è quello che conta per negozi e bottino.",
                    "Imposta modello=True per il catalogo; le copie assegnate a un personaggio hanno modello=False.",
                    "Compila valore, peso e rarita (Unico oppure 1-5).",
                    "Per negozi e bottino servono lv_loot (livello singolo o fascia, per esempio 3 oppure 4-6), regione_loot e, se vuoi pesare la regione, peso_regione.",
                    "Conserva i testi Elder in effetto_1 fino a effetto_8 finché non vengono convertiti consapevolmente in effects.",
                ],
            },
            {"type": "heading", "text": "Profili specializzati"},
            {
                "type": "list",
                "items": [
                    "weapon_profile — assi dell'arma, modalità di combattimento, munizioni e ricarica. Vedi la Guida Armi.",
                    "alchemy_profile — dati del banco alchemico.",
                    "crafting_profile — dati di forgiatura, ancora in ricostruzione.",
                    "tipo_arma collega l'oggetto a un Tipo arma del catalogo; pa_per_attacco salva il costo in PA.",
                    "speciale=True marca gli oggetti anomali o da rivedere; archiviato=True li toglie dall'autoring normale.",
                ],
            },
            {"type": "heading", "text": "Effetti dell'oggetto"},
            {"type": "code", "language": "json", "text": CODE_ITEM_EFFECTS},
            {
                "type": "callout",
                "title": "Perché un oggetto non compare mai in negozio",
                "text": (
                    "Il generatore delle scorte considera soltanto oggetti con modello=True, archiviato=False, "
                    "speciale=False, rarita diversa da Unico, un lv_loot leggibile e un tipo_1 fra quelli previsti "
                    "dalla categoria del negozio. Se manca anche una sola condizione l'oggetto viene ignorato in "
                    "silenzio. La pagina Gestione Negozi elenca gli oggetti esclusi."
                ),
            },
            {
                "type": "callout",
                "title": "Regola pratica",
                "text": "Le chiavi tecniche restano stabili; nomi, descrizioni e testi mostrati al giocatore devono essere in italiano.",
            },
            _difference_warning(
                "Gli ingredienti dell'alchimia non sono normali record Oggetto: il banco usa il catalogo "
                "ReagenteAlchemico e Alchimia&Contenitori. Inoltre temporaneo è soltanto un indicatore salvato; "
                "non rende da solo una copia irripetibile. Le copie assegnate o generate sono distinte soprattutto "
                "da modello=False e dai metadati della clonazione."
            ),
        ),
    },
    {
        "seed_key": "armi-uso",
        "nome": "Creare e usare le armi",
        "categoria": "Combattimento",
        "ordine": 15,
        "contenuto": _guide_content(
            {
                "type": "paragraph",
                "text": (
                    "Ogni arma può descrivere quattro assi indipendenti: pesantezza, lunghezza, "
                    "precisione/potenza e tipo di danno. Le due opzioni chiamate Media appartengono "
                    "a griglie diverse: la lunghezza Media usa atk_skill_medie1; la potenza Media usa atk_skill_medie2."
                ),
            },
            {
                "type": "callout",
                "title": "Modificatori incorporati nell'oggetto",
                "text": (
                    "Il creator mostra una previsione e il comando Applica modificatori suggeriti. Solo quel comando "
                    "copia i bonus negli effetti e il costo PA nell'oggetto. Dopo il salvataggio non vengono ricalcolati: "
                    "puoi cambiare categoria, rimuovere bonus o creare un'arma con le stesse categorie e nessun modificatore."
                ),
            },
            {
                "type": "list",
                "items": [
                    "Pesantezza: Leggera (+4 ATK, +1 PA, -3 DMG), Media (nessun bonus), Pesante (-4 ATK, +3 DMG, +1 EN).",
                    "Lunghezza: Corta (3 PA/attacco, -2 DMG, +3 AP), Media (4 PA/attacco, +1 DMG), Lunga (6 PA/attacco, +5 DMG, +10% AP), Mani nude (2 PA/attacco).",
                    "Danno: Perforante (+1 DMG), Taglio (+1 PA), Contundente (+1 EN). Magico e Natura non aggiungono modificatori.",
                    "Precisione/potenza non cambia le statistiche: decide soltanto quale competenza d'attacco si applica.",
                    "Materiali leggeri: +2 PA e +1 ATK; materiali pesanti: +2 EN e +1 DMG. Il tier del materiale guida soltanto il prezzo suggerito.",
                    "Le bande A-D propongono prezzo e peso copiati da Elder; sono linee guida e non vincoli.",
                ],
            },
            {"type": "heading", "text": "Una mano, due mani e doppia impugnatura"},
            {
                "type": "list",
                "items": [
                    "La lunghezza determina le mani: Corta e Media sono a una mano; Lunga richiede due mani e lo slot Scudo libero.",
                    "Per la doppia impugnatura inserisci una seconda arma Corta o Media nello slot Scudo.",
                    "Una sola arma è primaria: soltanto i suoi effetti e le sue categorie modificano la scheda.",
                    "Cambia primaria dalla scheda o dal combattimento senza spendere Punti Azione.",
                    "Se attacchi con un'arma, cambi primaria e attacchi subito con l'altra, il secondo attacco costa 1 PA in meno.",
                ],
            },
            {"type": "heading", "text": "Armi da lancio e a distanza"},
            {
                "type": "list",
                "items": [
                    "Lancio: gittata base 4 m, poi -2 ATK per cella; massimo pari alla Forza in metri; in mischia -4 ATK.",
                    "Distanza: gittata base 9 m, poi -2 ATK per cella; in mischia -7 ATK salvo bonus specifico.",
                    "Estrarre o ricaricare un'arma a distanza in mischia espone a un attacco di opportunità.",
                    "Gli attacchi a distanza consumano frecce o dardi dalla faretra; caricatori e ricariche usano i costi salvati nell'arma.",
                    "Bonus speciali, capacità del caricatore e ricariche importati da Elder restano note visibili e preset modificabili.",
                ],
            },
            _difference_warning(
                "I bonus indicati qui come DMG vengono salvati dal creator sul bersaglio tecnico tier, che determina "
                "i dadi di danno, non come bonus di danno fisso. Inoltre una munizione viene consumata soltanto per "
                "un'arma con modalità ranged e ammunitionType configurato; un profilo a distanza senza quel campo "
                "non preleva frecce, dardi o proiettili dalla faretra. Gittate, malus in mischia e attacchi di "
                "opportunità restano regole applicate dal Master."
            ),
        ),
    },
    {
        "seed_key": "guida-armi",
        "nome": WEAPON_CATALOGUE_GUIDE_NAME,
        "categoria": "Combattimento",
        "ordine": 18,
        "contenuto": _guide_content({"type": "dynamic_weapon_catalogue"}),
    },
    {
        "seed_key": "abilita",
        "nome": "Creare abilità correttamente",
        "categoria": "Contenuti",
        "ordine": 20,
        "contenuto": _guide_content(
            {
                "type": "paragraph",
                "text": (
                    "Usa Skill per nodi di progressione, magie, vantaggi, tecniche, classi e religioni. "
                    "La Skill spiega cosa viene appreso; gli esiti meccanici attivi o passivi vanno collegati agli effetti."
                ),
            },
            {
                "type": "list",
                "items": [
                    "nome, slug e numero devono restare univoci e stabili.",
                    "famiglia è un riferimento a FamigliaSkill: usa una famiglia esistente, non una stringa libera. ordine_famiglia decide la posizione nell'albero.",
                    "costo_pe e tipo_pe definiscono il costo strutturato; tipo_pe accetta all, general, red, green o blue.",
                    "prerequisiti è la relazione fra Skill che il sistema verifica davvero; requisiti è soltanto testo descrittivo e non blocca lo sblocco.",
                    "Le condizioni automatiche sul personaggio si scrivono in metadata.unlockRequirements.",
                    "effetti_passivi e azioni_attive sono salvati sulla Skill; le azioni attive sono promemoria e non spendono risorse da sole.",
                    "Un grado successivo aggiunge soltanto il nuovo incremento, non l'intero totale cumulativo.",
                ],
            },
            {"type": "heading", "text": "Esempio essenziale"},
            {"type": "code", "language": "json", "text": CODE_SKILL},
            {
                "type": "callout",
                "title": "famiglia e prerequisiti sono relazioni",
                "text": (
                    "Nell'esempio i nomi servono a indicare quale FamigliaSkill e quali Skill collegare: "
                    "vanno risolti in riferimenti reali. Una famiglia inesistente fa fallire il salvataggio."
                ),
            },
        ),
    },
    {
        "seed_key": "effetti",
        "nome": "Creare effetti correttamente",
        "categoria": "Contenuti",
        "ordine": 30,
        "contenuto": _guide_content(
            {
                "type": "paragraph",
                "text": (
                    "Usa Effetto per una modifica strutturata e riutilizzabile. Definisci sempre un'origine, "
                    "un bersaglio, un'operazione e un valore; aggiungi condizioni soltanto quando sono necessarie."
                ),
            },
            {"type": "code", "language": "json", "text": CODE_EFFECT},
            {"type": "heading", "text": "Operazioni e ordine di applicazione"},
            {
                "type": "list",
                "items": [
                    "Nell'ordine: add, subtract, multiply, percent, min, max oppure cap, set.",
                    "formula_override agisce prima di tutte: sostituisce la formula base della statistica.",
                    "strong_set agisce per ultima e blocca il valore finale anche dopo Stanchezza e Modificatore generale; set invece resta soggetto a quelle correzioni.",
                    "Un effetto può contenere al massimo 24 operazioni.",
                ],
            },
            {"type": "heading", "text": "Formule"},
            {
                "type": "list",
                "items": [
                    "Al posto di un numero puoi scrivere un calcolo, senza il segno = iniziale.",
                    "Sono disponibili base.<variabile>, final.<variabile> e i campi anagrafici sotto personaggio: livello, eta, monete, danno, mana_speso, energia_spesa, potere_speso, mana_in_sifone, pe_generali, pe_rossi, pe_verdi, pe_blu, pe_abilita.",
                    "condition applica la modifica soltanto quando l'espressione è vera, per esempio final.pf < 10.",
                ],
            },
            {
                "type": "callout",
                "title": "Effetto ed EffettoPersonalizzato",
                "text": (
                    "Effetto è il catalogo riutilizzabile con origine_tipo e origine_nome. L'editor della scheda "
                    "crea invece EffettoPersonalizzato, con le stesse operazioni scritte su righe separate. "
                    "Descrizione e messaggi devono spiegare l'effetto in italiano."
                ),
            },
        ),
    },
    {
        "seed_key": "malattie-stati",
        "nome": "Creare malattie e stati correttamente",
        "categoria": "Contenuti",
        "ordine": 40,
        "contenuto": _guide_content(
            {
                "type": "paragraph",
                "text": (
                    "Usa EffettiEMalattie per malattie, ferite persistenti, benedizioni e condizioni ambientali. "
                    "Il record definisce durata, regola di cumulo e operazioni applicate al personaggio."
                ),
            },
            {"type": "code", "language": "json", "text": CODE_DISEASE},
            {
                "type": "callout",
                "title": "Durata e cumulo",
                "text": "Dichiara sempre se una nuova applicazione rinnova, somma o sostituisce l'effetto precedente.",
            },
            _difference_warning(
                "EffettiEMalattie è oggi un catalogo dati e non è collegato al flusso che applica gli effetti ai "
                "personaggi. default_duration_turns e stacking_rule vengono conservati, ma il sistema non decrementa "
                "la durata e non interpreta automaticamente refresh, somma o sostituzione; per ottenere modifiche "
                "calcolate bisogna creare o applicare un Effetto/EffettoPersonalizzato supportato."
            ),
        ),
    },
    {
        "seed_key": "variabili-personaggio",
        "nome": CHARACTER_VARIABLE_GUIDE_NAME,
        "categoria": "Personaggio",
        "ordine": 60,
        "contenuto": _guide_content(
            {"type": "dynamic_character_variables"},
            _difference_warning(
                "Alcune variabili sono calcolate e mostrate ma non ancora spese automaticamente: i PA non hanno uno "
                "storico di spesa persistente lato server, l'anteprima degli incantesimi non consuma risorse, e "
                "Sifone di Mana, en_per_mana e pa_per_mana restano valori compatibili con Elder senza automazione attiva."
            ),
        ),
    },
]

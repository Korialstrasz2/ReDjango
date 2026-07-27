import json
import re
import unicodedata
from collections.abc import Mapping
from html import unescape
from pathlib import Path
from typing import Any


V2_GUIDE_DEFAULT_VERSION = "2026-07-26-guide-system-review-v3"

CHARACTER_VARIABLE_GUIDE_NAME = "Variabili del personaggio e alchimia"

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
            ("fortuna", "Fortuna", "Misura la sorte del personaggio e alimenta il relativo modificatore di dado e le regole che la richiamano."),
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
            ("attacco", "Attacco", "È il valore generale usato per risolvere gli attacchi, prima di eventuali specializzazioni e modificatori situazionali."),
            ("difesa", "Difesa", "È il valore generale opposto agli attacchi e alle prove che richiedono una difesa."),
            ("tier", "Tier", "Indica la fascia di potenza del personaggio. Nel regolamento originario seleziona la progressione dei dadi di danno; l'automazione di combattimento v2 non è ancora completa."),
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
            ("ap", "Perforazione armatura", "Ignora una quantità fissa della protezione fisica. Nel calcolo originario restituisce danno solo fino a quanto era stato assorbito."),
            ("ap_percento", "Perforazione armatura percentuale", "Ignora una percentuale della protezione fisica. Nel calcolo originario si combina con AP senza superare il danno assorbito."),
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
            ("monete_per_slot", "Monete per spazio", "Numero di monete che occuperebbe uno spazio d'inventario. Il valore è conservato per il regolamento, ma la conversione automatica monete/spazi non è ancora implementata."),
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
                    "title": "Scala delle resistenze originaria",
                    "text": (
                        "Conversione livello → percentuale: -4 → -45%, -3 → -35%, -2 → -25%, -1 → -15%, "
                        "0 → 0%, 1 → 15%, 2 → 23%, 3 → 30%, 4 → 35%, 5 → 40%, 6 → 45%, "
                        "7 → 50%, 8 → 55%, 9 → 60%. L'automazione di combattimento v2 è ancora in completamento."
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


def _guide_content(*blocks: dict) -> str:
    return json.dumps(list(blocks), ensure_ascii=False, indent=2)


def _difference_warning(text: str) -> dict[str, str]:
    return {
        "type": "warning",
        "title": "Differenze rispetto al sistema attuale",
        "text": text,
    }


def _deprecated_short_redjango_rules_guide_content() -> str:
    """Rebuild-facing companion to Elder's ``Regole Varie``.

    It deliberately documents the rule intent while distinguishing gameplay rules
    that are stored/calculated by ReDjango from workflows still run by the Master.
    """
    implemented = "Implementato in ReDjango"
    pending = "NON ANCORA IMPLEMENTATO"
    incorrect = "NON CORRETTO PER REDJANGO"
    return _guide_content(
        {"type": "paragraph", "text": "Versione ReDjango della guida Elder “Regole Varie”. Le regole qui sotto sono divise per stato: usa i collegamenti per aprire gli strumenti che le applicano davvero."},
        {"type": "callout", "title": "Come leggere questa guida", "text": f"{implemented}: la regola ha supporto dati o calcolo nel gioco. {pending}: il Master la gestisce manualmente. {incorrect}: il testo Elder non descrive il comportamento attuale e non va applicato automaticamente."},
        {"type": "heading", "text": "Indice"},
        {"type": "list", "items": ["[Personaggio e risorse](/characters)", "[Competenze](/competencies) e [Abilità](/skills)", "[Combattimento](/combat)", "[Creazione e alchimia](/creation)", "[Scheda ed equipaggiamento](/characters)", "[Variabili del personaggio](/guides)"]},
        {"type": "heading", "text": "Base e risorse del personaggio"},
        {"type": "paragraph", "text": "Il dado base Elder è d6; prove e soglie rimangono una decisione del Master. PF, Mana, Energia, Potere e PA sono mostrati e calcolati nella scheda; i valori correnti possono essere aggiornati con salvataggio esplicito."},
        {"type": "warning", "title": pending, "text": "La penalità Elder a 0 PF, il recupero automatico dell'Energia a −1 e il riposo completo non sono un motore di risoluzione automatica. Applicali manualmente finché non saranno introdotti come azioni di gioco."},
        {"type": "heading", "text": "Competenze e check"},
        {"type": "paragraph", "text": "Le 21 competenze hanno due barre da 0 a 7. La prima aggiunge il bonus al tiro; la seconda abilita d8, d10, d12, bonus Energia, riduzioni e due rilanci giornalieri al grado 7. Il costo è progressivo/triangolare e i tiri sono eseguiti lato server."},
        {"type": "callout", "title": implemented, "text": "Apri [Competenze](/competencies): lì trovi avanzamento atomico, extra manuale, bonus da equipaggiamento/effetti/abilità e i tiri. Il Master definisce ancora la soglia e interpreta il risultato."},
        {"type": "heading", "text": "Equipaggiamento, inventario e carico"},
        {"type": "paragraph", "text": "La scheda gestisce slot equipaggiati, zaino, spazi magici e normali, faretre e peso. Gli oggetti si spostano con trascinamento o clic; lo scambio è valido solo se entrambe le destinazioni sono compatibili. Il carico riduce i PA senza scendere sotto 4."},
        {"type": "warning", "title": incorrect, "text": "In Elder slot_magici indicava talvolta slot di equipaggiamento magico. In ReDjango è la quantità iniziale di spazi magici dello zaino che ignorano il peso: non usare la definizione Elder per gli accessori."},
        {"type": "warning", "title": pending, "text": "La conversione automatica monete/spazi, le regole complete di vestiti/chainmail incompatibili e la logica di rifornimento non sono ancora implementate."},
        {"type": "heading", "text": "Negozi e viaggio"},
        {"type": "paragraph", "text": "Elder definisce scorte, produzione su ordinazione, velocità su strada/terreno, stanchezza di viaggio e cavalcature. Usa queste regole come riferimento narrativo del Master."},
        {"type": "warning", "title": pending, "text": "Non esistono ancora una pagina negozi, stock, acquisti, mappa di viaggio, avanzamento orario o automazione della stanchezza di viaggio."},
        {"type": "heading", "text": "Combattimento"},
        {"type": "paragraph", "text": "La postazione [Combattimento](/combat) genera e gestisce Unit, livelli e schede complete. Attacco, Difesa, resistenze, RD, perforazione, tier e costi delle armi restano valori disponibili nella scheda e nei dati degli oggetti."},
        {"type": "warning", "title": pending, "text": "Iniziativa 1d10 + Mod Agilità + Mod Velocità, griglia esagonale, consumo PA per movimento, attacco-vs-difesa, danno, critici, gittate, opportunità e resistenze/RD NON sono ancora risolti automaticamente dal combattimento ReDjango."},
        {"type": "heading", "text": "Malattie, status, scassinare e borseggiare"},
        {"type": "paragraph", "text": "La scheda dispone di effetti persistenti/temporanei strutturati: possono modificare più variabili, avere formule, durata e origine. È la base corretta per stati e malattie personalizzati."},
        {"type": "warning", "title": pending, "text": "Le tabelle Elder di status/malattie, il tiro giornaliero di guarigione, Cura effetti, scasso con attrezzi fragili e borseggio con soglie non hanno ancora workflow o risoluzione dedicata."},
        {"type": "heading", "text": "Livelli, PE e creazione del personaggio"},
        {"type": "paragraph", "text": "Le [Abilità](/skills) applicano prerequisiti, costo PE e sconti atomici; la scheda conserva livello, caratteristiche, razze e bonus tramite effetti. Il calcolo delle statistiche usa il profilo formule amministrativo attivo."},
        {"type": "warning", "title": incorrect, "text": "La tabella Elder XP 20 + livello, le quattro categorie di PE, perk per livello e la caratteristica preferita automatica non sono un sistema ReDjango attivo. Non assegnarli come automazione senza una regola di campagna esplicita."},
        {"type": "heading", "text": "Resurrezione, evocazione, insegnamento, grimori e cavalcare"},
        {"type": "paragraph", "text": "Queste sezioni Elder rimangono materiale di riferimento per il Master: costi, limiti e conseguenze vanno annotati nella sessione e, quando producono un bonus/malus persistente, rappresentati con un effetto strutturato."},
        {"type": "warning", "title": pending, "text": "Non esistono ancora workflow dedicati per resurrezione, evocazioni, apprendimento con insegnante, grimori, cattura anime o cavalcature."},
        {"type": "heading", "text": "Alchimia, incantamento e forgiatura"},
        {"type": "paragraph", "text": "[Creazione](/creation) implementa l'alchimia: borsa canonica, 42 reagenti Elder rosso/verde/blu di livello 1–4, estrazione, miscela fino a quattro reagenti, anteprima della formula e distillazione transazionale. Potenza e soglie 3–30 usano le variabili calcolate del personaggio."},
        {"type": "warning", "title": pending, "text": "Incantamento (gemme, anime, cariche) e forgiatura (lingotti, miglioramenti, cumulo dei costi) hanno una sede nella Creazione ma non sono ancora implementati. Non applicare automaticamente le tabelle Elder di materiali o miglioramenti."},
        {"type": "heading", "text": "Modificatori di gioco"},
        {"type": "paragraph", "text": "Consulta “Variabili del personaggio e alchimia” in questa sezione Guide per valori base, formule attive e dipendenze. Stanchezza, modificatore generale, Fortuna, resistenze, RD, carico, limiti accessori, tier, conversioni magiche e moltiplicatori alchemici sono variabili disponibili agli effetti."},
        {"type": "warning", "title": pending, "text": "Le conversioni Mana/EN/PA e il sifone sono descritti e configurabili, ma il loro impiego completo nelle azioni di combattimento/magia non è ancora automatizzato."},
    )

_ELDER_RULES_PATH = Path(__file__).with_name("regole_varie_elder.html")

_RULE_STATUS_NOTES: dict[str | tuple[str, str], tuple[str, str]] = {
    "INDICE": ("implemented", "INDICE ORIGINALE — I collegamenti restano interni a questa guida e portano alle sezioni Elder sottostanti."),
    "BASE": ("partial", "PARZIALMENTE IMPLEMENTATO — ReDjango offre i dadi e conserva le risorse, ma non applica automaticamente tutte le eccezioni Elder."),
    "Risorse del Personaggio": ("partial", "PARZIALMENTE IMPLEMENTATO — PF, Mana, Energia, Potere, PA e Stanchezza sono presenti. NON ANCORA IMPLEMENTATI: morte a −Resistenza PF, raddoppio automatico dei PA a 0 PF, ciclo Energia −1/Stanchezza e recuperi completi del riposo."),
    "Competenze e Barre": ("implemented", "IMPLEMENTATO — Due barre 0–7, costo progressivo, tecniche in Energia, dadi superiori e reroll giornalieri sono gestiti nella pagina Competenze."),
    "Lista Competenze": ("implemented", "IMPLEMENTATO — Le 21 competenze Elder sono presenti nell’atlante ReDjango."),
    "Check di Competenza": ("implemented", "IMPLEMENTATO — Il tiro è server-side e somma i bonus; soglia e interpretazione restano al Master, come previsto dalla guida."),
    "Equipaggiamento e Slot": ("partial", "PARZIALMENTE IMPLEMENTATO — Slot, zaino, faretre, limiti di anelli/orecchini/sacchi, compatibilità e peso sono gestiti. Alcune incompatibilità narrative Elder fra strati di vestiario non sono ancora automatizzate."),
    "NEGOZI": ("missing", "NON ANCORA IMPLEMENTATO — ReDjango non dispone ancora di pagina negozi, stock, ordini, acquisti o rifornimenti automatici. Questa sezione resta regola manuale del Master."),
    "VIAGGIO": ("missing", "NON ANCORA IMPLEMENTATO — Velocità, terreno, ore di marcia, Stanchezza di viaggio, sonno e cavalcature non hanno ancora un flusso automatico."),
    "COMBAT": ("partial", "PARZIALMENTE IMPLEMENTATO — Esistono postazione Combattimento, Unit e schede controllabili; NON ANCORA IMPLEMENTATO il motore completo di risoluzione descritto qui."),
    "Turni, Iniziativa e Punti Azione": ("missing", "NON ANCORA IMPLEMENTATO — Iniziativa, turni, ricarica PA e movimento su griglia non sono risolti automaticamente."),
    "Attacco, Difesa e Risoluzione": ("missing", "NON ANCORA IMPLEMENTATO — Attacco contro Difesa, danno, moltiplicatori, resistenze, RD e perforazione sono dati disponibili ma non una pipeline automatica di combattimento."),
    "Critici": ("missing", "NON ANCORA IMPLEMENTATO — Critici, gittata, malus in mischia, ricarica e attacchi di opportunità rimangono regole manuali."),
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
    "MODIFICATORI DI GIOCO": ("partial", "PARZIALMENTE IMPLEMENTATO — Le variabili esistono e possono ricevere effetti; alcune hanno calcolo completo, altre sono solo disponibili per regole future."),
    "stanchezza": ("implemented", "IMPLEMENTATO CON CONFIGURAZIONE REDJANGO — Il valore entra nei totali secondo il profilo amministrativo attivo; la percentuale Elder −8% non è necessariamente fissa."),
    "modificatore_generale": ("implemented", "IMPLEMENTATO CON CONFIGURAZIONE REDJANGO — Il valore modifica i bersagli configurati; il +12% Elder non è necessariamente fisso."),
    "fortuna": ("partial", "PARZIALMENTE IMPLEMENTATO — Fortuna e relativo modificatore sono disponibili ai dadi e alle formule; non tutti gli effetti indiretti Elder sono automatizzati."),
    "rd_fis": ("partial", "DATO IMPLEMENTATO; RISOLUZIONE NON ANCORA IMPLEMENTATA — RD fisica è calcolabile e visibile, ma non viene sottratta automaticamente in un motore danni completo."),
    "res_contundente": ("partial", "DATO IMPLEMENTATO; RISOLUZIONE NON ANCORA IMPLEMENTATA — La resistenza è disponibile, ma il danno contundente non è risolto automaticamente."),
    "res_taglio": ("partial", "DATO IMPLEMENTATO; RISOLUZIONE NON ANCORA IMPLEMENTATA — La resistenza è disponibile, ma il danno da taglio non è risolto automaticamente."),
    "res_perforante": ("partial", "DATO IMPLEMENTATO; RISOLUZIONE NON ANCORA IMPLEMENTATA — La resistenza è disponibile, ma il danno perforante non è risolto automaticamente."),
    "res_fuoco": ("partial", "DATO IMPLEMENTATO; RISOLUZIONE NON ANCORA IMPLEMENTATA — La resistenza è disponibile, ma il danno da fuoco non è risolto automaticamente."),
    "res_gelo": ("partial", "DATO IMPLEMENTATO; RISOLUZIONE NON ANCORA IMPLEMENTATA — La resistenza è disponibile, ma il danno da gelo non è risolto automaticamente."),
    "res_elettro": ("partial", "DATO IMPLEMENTATO; RISOLUZIONE NON ANCORA IMPLEMENTATA — La resistenza è disponibile, ma il danno elettrico non è risolto automaticamente."),
    "rd_fuoco": ("partial", "DATO IMPLEMENTATO; RISOLUZIONE NON ANCORA IMPLEMENTATA — RD fuoco è disponibile, ma non applicata da un motore danni completo."),
    "rd_gelo": ("partial", "DATO IMPLEMENTATO; RISOLUZIONE NON ANCORA IMPLEMENTATA — RD gelo è disponibile, ma non applicata da un motore danni completo."),
    "rd_elettro": ("partial", "DATO IMPLEMENTATO; RISOLUZIONE NON ANCORA IMPLEMENTATA — RD elettrica è disponibile, ma non applicata da un motore danni completo."),
    "slot_magici": ("incorrect", "NON CORRETTO PER REDJANGO — Qui la descrizione Elder parla di equipaggiamento magico; in ReDjango slot_magici indica gli spazi iniziali dello zaino che ignorano il peso."),
    "slot_non_magici": ("implemented", "IMPLEMENTATO — Aggiunge spazi normali allo zaino ReDjango."),
    "monete_per_slot": ("missing", "NON ANCORA IMPLEMENTATO — Il valore è conservato, ma monete e occupazione degli spazi non vengono convertite automaticamente."),
    "tier": ("partial", "PARZIALMENTE IMPLEMENTATO — Tier è disponibile in schede, oggetti e Unit; la progressione automatica dei dadi di danno non è completa."),
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


V2_GUIDE_DEFAULTS = [
    {
        "nome": "Regole Varie — ReDjango",
        "categoria": "Regolamento",
        "ordine": 5,
        "contenuto": _redjango_rules_guide_content(),
    },
    {
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
                    "Mantieni nome univoco e leggibile.",
                    "Usa tipo_1 fino a tipo_4 scegliendo opzioni configurate nell'Amministrazione Django.",
                    "Imposta modello=True per il catalogo e temporaneo=True per copie irripetibili.",
                    "Compila valore, peso, rarità (Unico oppure 1-5), livello e regione per negozi e generazione del bottino.",
                    "Conserva i testi Elder in effetto_1 fino a effetto_8 finché non vengono convertiti consapevolmente in effects.",
                ],
            },
            {"type": "heading", "text": "Effetti dell'oggetto"},
            {
                "type": "code",
                "language": "json",
                "text": """[
  {"target": "attacco", "operation": "add", "value": 3},
  {"target": "pf", "operation": "add", "value": "personaggio.livello * 2"}
]""",
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
                    "Lunghezza: Corta (3 PA/attacco, -2 DMG, +3 AP), Media (4 PA/attacco, +1 DMG), Lunga (6 PA/attacco, +5 DMG, +10% AP).",
                    "Danno: Perforante (+1 DMG), Taglio (+1 PA), Contundente (+1 EN).",
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
                "non preleva frecce, dardi o proiettili dalla faretra."
            ),
        ),
    },
    {
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
                    "numero deve rimanere univoco e stabile.",
                    "famiglia raggruppa l'albero e ordine_famiglia decide la posizione.",
                    "Usa costo_pe e tipo_pe per il costo strutturato, requisiti per i vincoli di accesso.",
                    "Un grado successivo aggiunge soltanto il nuovo incremento, non l'intero totale cumulativo.",
                ],
            },
            {"type": "heading", "text": "Esempio essenziale"},
            {
                "type": "code",
                "language": "json",
                "text": """{
  "nome": "Svelto 2",
  "numero": 100000002,
  "famiglia": "Combattimento",
  "ordine_famiglia": 20,
  "costo_pe": 5,
  "requisiti": "Svelto 1"
}""",
            },
            _difference_warning(
                "Nel sistema attuale famiglia è un riferimento a FamigliaSkill, non una stringa libera. requisiti è "
                "testo descrittivo e non blocca lo sblocco: i prerequisiti verificati sono la relazione prerequisiti "
                "e le regole strutturate in metadata.unlockRequirements. Passivi e azioni sono salvati direttamente "
                "in effetti_passivi e azioni_attive della Skill; le azioni attive sono promemoria e non eseguono né "
                "spendono risorse automaticamente."
            ),
        ),
    },
    {
        "nome": "Creare effetti correttamente",
        "categoria": "Contenuti",
        "ordine": 30,
        "contenuto": _guide_content(
            {
                "type": "paragraph",
                "text": (
                    "Usa Effetto per una modifica strutturata e riutilizzabile. Definisci sempre una fonte, "
                    "un bersaglio, un'operazione e un valore; aggiungi condizioni soltanto quando sono necessarie."
                ),
            },
            {
                "type": "code",
                "language": "json",
                "text": """{
  "nome": "Guardia salda",
  "fonte_tipo": "skill",
  "fonte_nome": "Difensore",
  "tipo": "passivo",
  "effect_payload": {
    "operations": [
      {"target": "difesa", "operation": "add", "value": 2}
    ]
  }
}""",
            },
            {
                "type": "list",
                "items": [
                    "Preferisci add, subtract, multiply, percent, min, max, cap e set.",
                    "Usa formule leggibili e limitate alle chiavi consentite.",
                    "Descrizione e messaggi devono spiegare chiaramente l'effetto in italiano.",
                ],
            },
            _difference_warning(
                "L'esempio usa i nomi fonte_tipo e fonte_nome, ma il modello Effetto corrente espone origine_tipo e "
                "origine_nome. L'editor della scheda crea invece EffettoPersonalizzato con righe di operazione "
                "separate. Oltre alle operazioni elencate sono supportate strong_set (Imposta forte) e "
                "formula_override; quest'ultima sostituisce la formula prima delle altre operazioni."
            ),
        ),
    },
    {
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
            {
                "type": "code",
                "language": "json",
                "text": """{
  "tipo": "malattia",
  "nome": "Febbre delle paludi",
  "descrizione": "Indebolisce il viaggiatore finché non viene curato.",
  "default_duration_turns": 6,
  "stacking_rule": "refresh",
  "effect_payload": {
    "operations": [
      {"target": "energia", "operation": "subtract", "value": 2}
    ]
  }
}""",
            },
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
        "nome": "Creare negozi correttamente",
        "categoria": "Contenuti",
        "ordine": 50,
        "contenuto": _guide_content(
            {
                "type": "paragraph",
                "text": (
                    "Usa Negozio per descrivere esercizio, proprietario, regione, città e inventario. "
                    "Le immagini di regione, città e sfondo sono record dell'Archivio immagini e possono essere riutilizzate."
                ),
            },
            {
                "type": "list",
                "items": [
                    "Mantieni regione e città in campi separati.",
                    "lista_oggetti può contenere riferimenti diretti oppure filtri per la generazione.",
                    "Usa generation_seed per rigenerazioni ripetibili.",
                    "Aggiorna le scorte invece di duplicare il negozio a ogni rifornimento.",
                ],
            },
            {"type": "heading", "text": "Scorte miste"},
            {
                "type": "code",
                "language": "json",
                "text": """[
  {"oggetto_nome": "Martello elfico", "quantita": 1, "prezzo_mod": 1.15},
  {"tipo_1": "arma", "rarita_min": 2, "rarita_max": 4, "quantita": "2d3"}
]""",
            },
            _difference_warning(
                "Negozio, lista_oggetti e generation_seed esistono nel database, ma non c'è ancora una pagina negozi, "
                "un generatore di scorte o un comando di rifornimento che interpreti questi esempi. Riferimenti, filtri, "
                "quantità a dadi e seed restano quindi dati descrittivi finché il relativo servizio non viene implementato."
            ),
        ),
    },
    {
        "nome": CHARACTER_VARIABLE_GUIDE_NAME,
        "categoria": "Personaggio",
        "ordine": 60,
        "contenuto": _guide_content(
            {"type": "dynamic_character_variables"},
            _difference_warning(
                "Il combattimento attuale usa già Tier, dadi di danno, resistenze, riduzioni e perforazione, quindi le "
                "note che li descrivono come automazione ancora incompleta sono superate. Al contrario, i PA non hanno "
                "uno storico di spesa persistente lato server e l'anteprima degli incantesimi non spende risorse; anche "
                "Sifone di Mana ed en_per_mana/pa_per_mana restano valori compatibili con Elder, non automazioni attive."
            ),
        ),
    },
]

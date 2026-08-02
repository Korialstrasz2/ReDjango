import json
import re
import unicodedata
from collections.abc import Mapping
from html import escape, unescape
from pathlib import Path
from typing import Any

from backend.characters.race_rules import RACE_CATALOG

from .defaults import (
    CHARACTERISTIC_DESCRIPTIONS,
    CHARACTERISTIC_LABELS,
    MAX_CHARACTER_AGE,
    MIN_CHARACTER_AGE,
    PREFERRED_CHARACTERISTIC_EFFECT_NAME,
    PREFERRED_CHARACTERISTIC_FORMULA,
)


V2_GUIDE_DEFAULT_VERSION = "2026-08-02-tailscale-private-access-v6-media-cache-lifecycle"

CHARACTER_VARIABLE_GUIDE_NAME = "Variabili del personaggio e alchimia"
WEAPON_CATALOGUE_GUIDE_NAME = "Guida Armi"
ITEM_COMPENDIUM_GUIDE_NAME = "Oggetti"
NEW_CHARACTER_GUIDE_NAME = "Creare un nuovo PG"

RACE_GUIDE_RACES = (
    "Bosmer", "Dunmer", "Orsimer", "Altmer", "Imperiale", "Bretone",
    "Redguard", "Argoniano", "Khajiit", "Nord", "Falmer", "Dremora", "Xivilai",
    "Non morto",
)

_DREMORA_GUIDE_HTML = """
<section class="redjango-race-supplement">
<h3>Dremora</h3>
<p><strong>Tipo:</strong> Daedra umanoide. I Dremora sono guerrieri immortali organizzati
in clan e caste militari; considerano rango, disciplina e forza di volontà prove di valore.</p>
<h4>Modificatori</h4>
<p>Forza +2, Resistenza +2, Concentrazione +1; Personalità −2, Fortuna −2, Saggezza −1.</p>
<h4>Tratto razziale — Sangue dell'Oblivion</h4>
<p>Resistenza al fuoco +1 e RD fuoco +2. Una volta al giorno il Dremora può ripetere
una prova di Intimidire contro una creatura mortale.</p>
<h4>Sottorazze e ranghi</h4>
<ul>
<li><strong>Churl:</strong> Energia +1.</li>
<li><strong>Caitiff:</strong> Velocità +1.</li>
<li><strong>Kynval:</strong> Attacco +1.</li>
<li><strong>Kynreeve:</strong> Difesa +1.</li>
<li><strong>Kynmarcher:</strong> Concentrazione +1.</li>
<li><strong>Markynaz:</strong> Potere +1.</li>
<li><strong>Valkynaz:</strong> Resistenza +1.</li>
</ul>
<p class="guide-implementation-note guide-status-implemented"><strong>Nota ReDjango:</strong>
razza, tratto e sottorazze sono applicati automaticamente e sono disponibili anche
nel generatore delle Unit umanoidi.</p>
</section>
"""

_XIVILAI_GUIDE_HTML = """
<section class="redjango-race-supplement">
<h3>Xivilai</h3>
<p><strong>Tipo:</strong> Daedra maggiore umanoide. Gli Xivilai sono esseri potenti,
intelligenti e indipendenti, distinti dalle caste militari dei Dremora.</p>
<h4>Modificatori</h4>
<p>Forza +2, Resistenza +2, Intelligenza +1; Personalità −2, Fortuna −2, Saggezza −1.</p>
<h4>Tratto razziale — Sangue dell'Oblivion</h4>
<p>Resistenza al fuoco +1 e RD fuoco +2. La loro natura daedrica e la loro forza
arcana sono rappresentate direttamente dai modificatori e dal tratto automatico.</p>
<h4>Sottorazze</h4>
<p>Nessuna. Xivilai è una specie daedrica autonoma e non usa i ranghi dei Dremora.</p>
<p class="guide-implementation-note guide-status-implemented"><strong>Nota ReDjango:</strong>
la razza e il tratto sono applicati automaticamente e sono disponibili nel generatore
delle Unit umanoidi.</p>
</section>
"""

_UNDEAD_GUIDE_HTML = """
<section class="redjango-race-supplement">
<h3>Non morto</h3>
<p><strong>Tipo:</strong> creatura animata dopo la morte da magia, volontà, maledizione o legame spirituale.
La razza copre non morti coscienti e utilizzabili come personaggi; un'Unit puramente bestiale può restare
una Creatura senza razza primaria.</p>
<h4>Modificatori</h4>
<p>Forza +1, Resistenza +2, Concentrazione +1; Personalità −2, Fortuna −1, Saggezza −1.</p>
<h4>Tratto razziale — Corpo senza vita</h4>
<p>RD fisica +1. Il non morto non necessita di respirare, mangiare o dormire ed è immune a veleni e
malattie; una volta al giorno può ignorare un effetto di paura.</p>
<h4>Sottorazze</h4>
<ul>
<li><strong>Scheletro:</strong> Agilità +1.</li>
<li><strong>Draugr:</strong> Resistenza al gelo +1.</li>
<li><strong>Revenant:</strong> Forza +1.</li>
<li><strong>Mummia:</strong> RD fisica +1.</li>
<li><strong>Vampiro:</strong> Velocità +1.</li>
<li><strong>Lich:</strong> Potere +1.</li>
<li><strong>Spettro:</strong> Difesa +1.</li>
</ul>
<p class="guide-implementation-note guide-status-implemented"><strong>Nota ReDjango:</strong>
la RD e le sottorazze sono applicate automaticamente. Immunità, fame, sonno e paura restano regole
narrative finché non esiste un motore completo per quelle condizioni.</p>
</section>
"""


CHARACTER_VARIABLE_GROUPS = (
    (
        "Regole globali e caratteristiche",
        (
            ("stanchezza", "Stanchezza", "Ogni punto applica una penalità (percentuale e fissa) ai valori rapidi configurati dall'amministratore."),
            ("modificatore_generale", "Modificatore generale", "Ogni punto applica un bonus (percentuale e fisso) ai valori rapidi configurati dall'amministratore; può compensare la Stanchezza."),
            # Le nove caratteristiche condividono la descrizione con il pannello
            # della caratteristica preferita nella creazione del PG.
            *(
                (key, CHARACTERISTIC_LABELS[key], CHARACTERISTIC_DESCRIPTIONS[key])
                for key in CHARACTERISTIC_DESCRIPTIONS
            ),
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
            ("attacco", "Attacco", "È il valore sommato al d20 nella risoluzione d'attacco. Include già le specializzazioni d'arma (atk_skill_*) dell'arma attualmente equipaggiata: il sistema le ricalcola e le somma qui automaticamente a ogni aggiornamento della scheda, prima di Stanchezza e Modificatore generale."),
            ("difesa", "Difesa", "È il valore sottratto al totale d'attacco per ottenere la differenza d'attacco, e il riferimento delle prove che richiedono una difesa. Include già le specializzazioni di difesa (def_skill_*) di armatura e scudo attualmente equipaggiati, sommate qui automaticamente."),
            ("tier", "Tier", "Indica la fascia di potenza del personaggio e sceglie la formula dei dadi di danno usata dalla risoluzione d'attacco, in una tabella configurabile dall'amministratore. Include già tier_skill_maninude quando non è equipaggiata un'arma. È il bersaglio su cui il creator armi salva i bonus chiamati DMG."),
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
            ("sifone_di_mana", "Sifone di Mana", "Percentuale del Mana lanciato che finisce nel sifone del personaggio, arrotondata per difetto. Il sifone raccoglie una quota del Mana speso dal personaggio stesso e da chi lancia nel suo raggio d'azione, e la conserva in una riserva separata (campo «Mana nel sifone») da cui il Mana torna disponibile. Il raggio dipende dalla fonte del sifone. Vedi il glossario delle meccaniche nella guida «Regole Varie»."),
            ("ogni_en_x_mana", "Mana ogni N energia", "Quantità di Mana richiesto che costa 1 Energia quando lanci una magia; il costo viene arrotondato per eccesso."),
            ("ogni_pa_x_mana", "Mana ogni N PA", "Quantità di Mana richiesto che costa 1 PA quando lanci una magia; il costo viene arrotondato per eccesso."),
            ("sconto_mana_per_potere", "Sconto Mana per Potere", "Nell'anteprima costi di una magia, Mana sottratto al requisito per ogni punto di Potere investito nel lancio (speso o messo a disposizione liberamente, la somma dei due conta)."),
            ("sconto_pa_per_potere", "Sconto PA per Potere", "Nell'anteprima costi di una magia, PA sottratti alla conversione in PA per ogni punto di Potere investito nel lancio (speso o messo a disposizione liberamente, la somma dei due conta)."),
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
        "Forgiatura",
        (
            ("forgia_tetto_miglioramenti", "Tetto dei miglioramenti", "Massimo dei punti miglioramento prima di sottrarre la fascia del materiale: lo alza Potenziato 1-7. I punti disponibili su un oggetto sono questo valore meno la fascia del materiale."),
            ("forgia_miglioramenti_specialista", "Miglioramenti da Specialista", "Punti miglioramento aggiuntivi che valgono solo sul materiale scelto con Specialista. Il materiale scelto è una stringa e vive in extra.forgia, non fra i totali."),
            ("forgia_miglioramenti_stanchezza", "Punto extra per Stanchezza", "Con «Il meglio che posso» si può spendere 1 punto Stanchezza per ottenere un punto miglioramento in più su una singola lavorazione."),
            ("forgia_bonus_frecce", "Bonus base delle frecce", "Bonus che «Fabbricante di frecce» aggiunge alle frecce forgiate dal personaggio."),
            ("forgia_uso_pratico", "Livello di Uso pratico", "Livello massimo di faretre, porta pozioni, porta pergamene e mantelli creabili in pelle. Uso pratico 1 e 2 lo portano a 1 e 2."),
            ("forgia_puo_fondere", "Può fondere", "Maggiore di zero con «Scioglitore»: permette di fondere un oggetto forgiato per recuperarne il materiale."),
            ("forgia_puo_riplasmare", "Può riplasmare", "Maggiore di zero con «Riplasmare»: permette di cambiare il metallo di un oggetto già migliorato conservandone i punti."),
            ("forgia_puo_ovunque", "Fucina improvvisata", "Maggiore di zero con «Fucina improvvisata»: permette di forgiare ovunque, se si portano gli strumenti da fabbro."),
        ),
    ),
    (
        "Incantamento",
        (
            ("incanta_livello_max_oggetti", "Livello massimo sugli oggetti", "Tetto del livello di incantamento applicabile a gioielli e accessori. Incantatore 1-3 arriva a 3, Gioielliere 1-7 porta il tetto fino a 10."),
            ("incanta_livello_max_pergamene", "Livello massimo delle pergamene", "Tetto del livello di pergamena scrivibile. Incantatore 1-3 arriva a 3, Scriba 1-7 porta il tetto fino a 10."),
            ("incanta_mana_per_livello", "Mana per livello di incantamento", "Quanto mana vale ogni livello di incantamento: base 5, portato a 6-10 da Infusore 1-5. L'altare aggiunge poi la sua percentuale al risultato."),
            ("incanta_cariche_percento", "Cariche aggiuntive (%)", "Percentuale di cariche in più per oggetto incantato, +25 per ciascuna Anima compressa. Le cariche di base sono pari al livello della gemma."),
            ("incanta_max_effetti", "Incantamenti per oggetto", "Quanti effetti distinti può portare un solo oggetto: 1 di base, 2 e 3 con Multi Incantamento 1 e 2. Le cariche restano indipendenti per ciascun effetto."),
            ("incanta_puo_reincantare", "Può reincantare", "Maggiore di zero con «Incantatore Esperto»: permette di incantare più volte un oggetto, anche acquistato o trovato."),
            ("incanta_puo_sommare_gemme", "Può sommare le gemme", "Maggiore di zero con «Artigiano di anime»: la prima gemma vale intera, la seconda a metà, la terza a un terzo."),
            ("incanta_puo_disincantare", "Può disincantare", "Maggiore di zero con «Riciclo di anime»: permette di svuotare un oggetto incantato al costo di 1 punto Stanchezza."),
            ("incanta_bonus_livello_stanchezza", "Livello extra per Stanchezza", "Con «Mana e anima» si può spendere 1 punto Stanchezza per alzare di 1 il livello dell'incantamento, senza mai superare il livello 10."),
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


_CHARACTERISTIC_KEYS = {
    "forza", "resistenza", "velocita", "agilita", "intelligenza",
    "concentrazione", "personalita", "saggezza", "fortuna",
}


def character_variable_guide_blocks(
    base_values: Mapping[str, Any],
    formulas: Mapping[str, str],
    quick_stat_adjustment: Mapping[str, Any],
    characteristic_adjustments: Mapping[str, str],
    damage_rules: Mapping[str, Any],
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
    level_formula = str(characteristic_adjustments.get("livello") or "").strip()
    fortuna_formula = str(characteristic_adjustments.get("fortuna") or "").strip()

    bounds = damage_rules.get("bounds") if isinstance(damage_rules.get("bounds"), Mapping) else {}
    resistance_percentages = (
        damage_rules.get("resistancePercentages")
        if isinstance(damage_rules.get("resistancePercentages"), Mapping)
        else {}
    )
    resistance_min = int(bounds.get("resistanceLevelMinimum", -4))
    resistance_max = int(bounds.get("resistanceLevelMaximum", 9))
    resistance_scale_text = ", ".join(
        f"{level} → {_display_number(resistance_percentages.get(str(level), 0))}%"
        for level in range(resistance_min, resistance_max + 1)
    )
    tier_min = int(bounds.get("tierMinimum", -5))
    tier_max = int(bounds.get("tierMaximum", 30))

    dependencies: dict[str, list[str]] = {key: [] for key in labels}
    for result_key, formula in formulas.items():
        for source_key in labels:
            if re.search(rf"\b(?:final|pre)\.{re.escape(source_key)}\b", str(formula)):
                dependencies[source_key].append(str(result_key))

    intro_blocks: list[dict[str, Any]] = [
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
                "Il sistema parte dai valori base, applica le caratteristiche (comprese le variazioni di Livello "
                "e Fortuna) e le loro formule derivate, aggiunge le specializzazioni di equipaggiamento ad "
                "Attacco, Difesa e Tier, calcola il carico e infine applica Stanchezza "
                f"(-{fatigue_rate}% e -{fatigue_fixed_rate} fisso per punto) "
                f"e Modificatore generale (+{general_rate}% e +{general_fixed_rate} fisso per punto) "
                f"a: {target_names}. Percentuali e valori fissi precedono l'arrotondamento per difetto."
            ),
        },
    ]

    groups: list[dict[str, Any]] = []
    for group_label, entries in CHARACTER_VARIABLE_GROUPS:
        variables: list[dict[str, Any]] = []
        for key, label, description in entries:
            facts: list[str] = []
            if key == "stanchezza":
                facts.append(
                    f"Configurazione attuale: -{fatigue_rate}% e "
                    f"-{fatigue_fixed_rate} fisso per punto su {target_names}."
                )
            elif key == "modificatore_generale":
                facts.append(
                    f"Configurazione attuale: +{general_rate}% e "
                    f"+{general_fixed_rate} fisso per punto su {target_names}."
                )
            elif key == "tier":
                facts.append(f"Intervallo attuale della tabella dadi: da {tier_min} a {tier_max}.")

            if key in _CHARACTERISTIC_KEYS:
                if level_formula:
                    facts.append(f"Bonus automatico attuale da Livello: {level_formula}.")
                if key != "fortuna" and fortuna_formula:
                    facts.append(f"Bonus automatico attuale da Fortuna: {fortuna_formula}.")

            if key.startswith("mod_") and key not in {"mod_carico", "mod_peso_equip"}:
                characteristic = key.removeprefix("mod_")
                facts.append(
                    f"Calcolo attuale: ⌊({labels.get(characteristic, characteristic)} finale − 10) / 2⌋."
                )
            else:
                if key in base_values:
                    facts.append(f"Valore base attuale: {_display_number(base_values[key])}.")
                if key in formulas:
                    facts.append(f"Formula attuale: {formulas[key]}.")

            if dependencies[key]:
                dependent_labels = ", ".join(labels.get(item, item) for item in dependencies[key])
                facts.append(f"È richiamata dalle formule attuali di: {dependent_labels}.")

            variables.append({"key": key, "label": label, "description": description, "facts": facts})

        group: dict[str, Any] = {"label": group_label, "variables": variables}
        if group_label == "Regole globali e caratteristiche" and (level_formula or fortuna_formula):
            group["note"] = {
                "title": "Livello e Fortuna influenzano tutte le caratteristiche",
                "text": (
                    "A ogni ricalcolo della scheda, il sistema aggiunge a ciascuna delle nove caratteristiche "
                    f"il valore della formula amministrativa di Livello ({level_formula or '—'}), e a ciascuna "
                    f"caratteristica diversa da Fortuna aggiunge anche il valore della formula di Fortuna "
                    f"({fortuna_formula or '—'}), prima dell'arrotondamento per difetto finale. Questo è "
                    "automatico e indipendente da qualunque effetto personalizzato che il giocatore crei per "
                    "una caratteristica preferita."
                ),
            }
        elif group_label == "Resistenze, riduzioni e perforazione":
            group["note"] = {
                "title": "Scala delle resistenze",
                "text": (
                    f"Conversione livello → percentuale: {resistance_scale_text}. La scala è modificabile "
                    f"dall'amministratore e i livelli sono comunque limitati fra {resistance_min} e "
                    f"{resistance_max}. L'attacco applica prima questa percentuale, poi la RD fissa, infine "
                    "il recupero da perforazione."
                ),
            }
        groups.append(group)

    reference_block: dict[str, Any] = {"type": "variable_reference", "groups": groups}

    alchemy_blocks: list[dict[str, Any]] = [
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
                "Per creare una pozione si selezionano da uno a quattro reagenti; ciascuno contribuisce con il moltiplicatore del proprio livello.",
                "Potenza della miscela: (somma dei moltiplicatori di livello dei reagenti scelti) × (bonus del set alchemico + moltiplicatore del colore scelto).",
                "Soglie delle pozioni: livello 1 da potenza 3, poi un livello ogni 3 punti, fino al livello 10 da potenza 30 (il livello non supera mai 10).",
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
                "anche il relativo contributo. Solo il moltiplicatore del colore scelto per la pozione entra "
                "nel calcolo della potenza, non tutti e tre insieme."
            ),
        },
    ]

    warning_block = _difference_warning(
        "Alcune variabili sono calcolate e mostrate ma non ancora spese automaticamente: i PA non hanno uno "
        "storico di spesa persistente lato server, l'anteprima degli incantesimi non consuma risorse, e "
        "il Sifone di Mana resta un valore compatibile con Elder senza automazione attiva."
    )

    return [*intro_blocks, reference_block, *alchemy_blocks, warning_block]


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


def _race_modifier_text(modifiers: Mapping[str, Any]) -> str:
    """Rende leggibili i modificatori di razza: prima i bonus, poi i malus."""
    bonuses, penalties = [], []
    for key, value in modifiers.items():
        label = CHARACTERISTIC_LABELS.get(key, key.replace("_", " ").capitalize())
        if isinstance(value, (int, float)) and value < 0:
            penalties.append(f"{label} {value}")
        else:
            bonuses.append(f"{label} +{value}")
    return "; ".join(filter(None, ("; ".join(bonuses), "; ".join(penalties)))) or "Nessun modificatore"


def _race_entries() -> list[dict[str, str]]:
    entries = []
    for race, definition in RACE_CATALOG.items():
        trait = definition.get("trait")
        trait_note = str((trait if isinstance(trait, dict) else {"note": trait or ""}).get("note") or "")
        subraces = ", ".join(definition.get("subraces") or {}) or "nessuna sottorazza"
        entries.append(
            {
                "title": race,
                "meta": _race_modifier_text(definition.get("modifiers") or {}),
                "note": f"Tratto razziale: {trait_note} Sottorazze: {subraces}.",
            }
        )
    return entries


def nuovo_pg_guide_blocks() -> list[dict[str, Any]]:
    """Procedura di creazione di un personaggio giocabile.

    Le razze sono generate da RACE_CATALOG: la guida non può descrivere
    modificatori diversi da quelli che il sistema applica davvero.
    """
    preferred_example = json.dumps(
        {
            "nome": PREFERRED_CHARACTERISTIC_EFFECT_NAME,
            "origine": "Creazione personaggio",
            "operazioni": [
                {
                    "bersaglio": "agilita",
                    "operazione": "add",
                    "valore": PREFERRED_CHARACTERISTIC_FORMULA,
                }
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
    return [
        {
            "type": "paragraph",
            "text": (
                "Un personaggio nuovo nasce al livello 1, con tutte e nove le caratteristiche al valore "
                "base 10, zero Punti Esperienza in ogni riserva, nessuna competenza, nessuna abilità e "
                "nessuna moneta. La scheda è volutamente vuota: tutto il resto si guadagna giocando. "
                "Alla creazione si decidono soltanto identità, razza, sottorazza e caratteristica preferita."
            ),
        },
        {"type": "heading", "text": "Identità"},
        {
            "type": "list",
            "items": [
                "Nome: il nome con cui il personaggio compare in tutta l'applicazione. Si può cambiare dopo.",
                "Nome interno: identificativo tecnico univoco, generato dal sistema e mai mostrato al tavolo. Non va scelto a mano.",
                "Tipologia: sempre «giocabile» per un PG. Le altre tipologie appartengono a NPC, nemici, evocazioni e unità generate.",
                f"Età: obbligatoria, fra {MIN_CHARACTER_AGE} e {MAX_CHARACTER_AGE}. Non ha effetti meccanici.",
                "Sesso: obbligatorio, Maschio o Femmina. Non ha effetti meccanici.",
                "Campagna: il personaggio entra nella campagna attiva del giocatore che lo crea.",
                "Ritratto: facoltativo alla creazione, si assegna in seguito dalla libreria immagini.",
                "Dettagli personaggio: descrizione breve. Il background lungo va nella sezione Background del diario.",
            ],
        },
        {
            "type": "callout",
            "title": "Il PG appena creato diventa quello attivo",
            "text": (
                "Chiusa la procedura si arriva sulla scheda del nuovo personaggio, che prende anche il posto di "
                "quello attivo precedente: barra laterale, Sala principale e voce «Scheda personaggio» lo seguono. "
                "Il personaggio di prima resta assegnato al giocatore e si riprende dalla Sala principale."
            ),
        },
        {
            "type": "callout",
            "title": "La terza razza non si usa alla creazione",
            "text": (
                "La scheda espone razza_1, razza_2 e razza_3. Alla creazione si compilano solo le prime due: "
                "razza_1 è la razza, razza_2 è la sottorazza. Il terzo campo resta libero per casi particolari "
                "decisi dal Master e non viene letto dal calcolo automatico dei bonus razziali."
            ),
        },
        {"type": "heading", "text": "Razza e sottorazza"},
        {
            "type": "paragraph",
            "text": (
                "La razza determina i modificatori alle caratteristiche e un tratto razziale; la sottorazza "
                "aggiunge una specializzazione, a volte puramente narrativa e a volte con un effetto numerico. "
                "Ogni razza ha le proprie sottorazze: una sottorazza non appartenente alla razza scelta viene "
                "rifiutata dalla creazione."
            ),
        },
        {"type": "entries", "items": _race_entries()},
        {
            "type": "callout",
            "title": "I bonus razziali sono automatici: non ricrearli a mano",
            "text": (
                "Questa è la differenza più importante rispetto a Elder Django. Là il regolamento chiedeva di "
                "annotare i bonus razziali e di costruirli a mano come effetti. In ReDjango il sistema li applica "
                "da solo non appena razza e sottorazza sono impostate: modificatori della razza, tratto razziale "
                "ed effetto della sottorazza compaiono nella scheda senza che nessuno li scriva. Creare a mano gli "
                "stessi effetti raddoppia ogni bonus. Si creano a mano solo gli effetti che il sistema non conosce."
            ),
        },
        {"type": "heading", "text": "Caratteristica preferita"},
        {
            "type": "paragraph",
            "text": (
                "È l'unica scelta meccanica della creazione, e va fatta subito. Si sceglie una fra Forza, "
                "Resistenza, Velocità, Agilità, Intelligenza, Concentrazione, Personalità, Saggezza e Fortuna: "
                "la creazione genera un effetto permanente che aggiunge "
                f"«{PREFERRED_CHARACTERISTIC_FORMULA}» a quella caratteristica, cioè +1 ogni cinque livelli."
            ),
        },
        {"type": "code", "language": "json", "text": preferred_example},
        {
            "type": "callout",
            "title": "In ReDjango il bonus di livello lo ricevono tutte le caratteristiche",
            "text": (
                "Il profilo Formule_base applica già automaticamente la formula di Livello a tutte e nove le "
                "caratteristiche, più un bonus derivato dalla Fortuna alle altre otto. La caratteristica preferita "
                "si somma a questo: la caratteristica scelta cresce quindi al doppio della velocità delle altre. "
                "In Elder Django il bonus di livello esisteva solo sulla preferita. Chi converte una scheda Elder "
                "deve saperlo: i numeri non coincideranno."
            ),
        },
        {
            "type": "warning",
            "title": "Differenze rispetto a Elder Django",
            "text": (
                "La creazione ReDjango non chiede una classe o un archetipo, che in Elder esistevano nel wizard "
                "AI. Non assegna un budget iniziale di Punti Esperienza: si parte da zero e non da un livello "
                "concordato. I bonus razziali sono automatici invece che manuali. La caratteristica preferita "
                "resta una scelta, ma si somma al bonus di livello globale invece di sostituirlo."
            ),
        },
        {"type": "heading", "text": "Dopo la creazione"},
        {
            "type": "list",
            "items": [
                "Perk: uno minore a ogni livello, uno maggiore ai livelli pari. Si annotano come effetti personalizzati.",
                "Punti Esperienza: quattro riserve (generali, rossi, verdi, blu) per sbloccare le abilità dalla pagina Abilità.",
                "Competenze: due barre da 0 a 7 per competenza, pagate con i PE competenze dalla pagina Competenze.",
                "Diario: nove sezioni (zaino, furto, combat, competenze, crafting, viaggio, appunti, missioni, background) dalla scheda del personaggio.",
                "Equipaggiamento e monete: si assegnano dalla scheda e dal Mercato; un PG nuovo parte senza nulla.",
                "Soglie di critico (crit_min, crit_nor, crit_mag) e bottoni combat: si configurano dalla scheda prima del primo combattimento.",
                "Borsa alchemica: si riempie giocando; i moltiplicatori dipendono da abilità ed equipaggiamento.",
            ],
        },
        {
            "type": "callout",
            "title": "Convenzione degli effetti manuali",
            "text": (
                "Gli effetti creati a mano vanno raggruppati per bersaglio (un effetto «+ attacco», un effetto "
                "«+ pf») e devono dichiarare la provenienza nel campo origine: «Perk minore», «Manuale Elder», "
                "«Abilità: Vitale 3», «Creazione personaggio». È la convenzione che seguono tutte le schede "
                "importate da Elder Django ed è l'unico modo per capire, mesi dopo, da dove arrivi un +1."
            ),
        },
    ]


def _difference_warning(text: str) -> dict[str, str]:
    return {
        "type": "warning",
        "title": "Differenze rispetto al sistema attuale",
        "text": text,
    }


_ELDER_RULES_PATH = Path(__file__).with_name("regole_varie_elder.html")

_RULE_STATUS_NOTES: dict[str | tuple[str, str], tuple[str, str]] = {
    "INDICE": ("implemented", "INDICE ORIGINALE — I collegamenti restano interni a questa guida e portano alle sezioni Elder sottostanti."),
    "Critici": ("partial", "PARZIALMENTE IMPLEMENTATO — I critici sono risolti: le soglie crit_min/crit_nor/crit_mag danno +40%/+60%/+80% di danno, corretti dalla Fortuna e dalla differenza d’attacco. NON ANCORA IMPLEMENTATI gittata, malus in mischia e attacchi di opportunità, che restano regole manuali; la ricarica delle armi a distanza è invece gestita dalla postazione."),
    "SCASSINARE e BORSEGGIARE": ("partial", "PARZIALMENTE IMPLEMENTATO — Lo strumento rapido Furto calcola soglie, modificatori di manutenzione e compagnia, diversivi e bonus del set. Restano manuali il tiro di competenza, l'usura dei set (annotata nella sezione Furto del diario) e il tiro di Percezione dell'altra persona."),
    "ALCHIMIA, INCANTAMENTO E FORGIATURA": ("implemented", "IMPLEMENTATO — I tre banchi della Creazione sono operativi: Alchimia distilla, Forgiatura crea e migliora, Incantamento infonde oggetti e scrive pergamene."),
    "Alchimia": ("implemented", "IMPLEMENTATO CON DIFFERENZE REDJANGO — Borsa, 42 ingredienti Elder, estrazione, anteprima e distillazione transazionale sono attive."),
    ("Alchimia", "Introduzione"): ("partial", "PARZIALMENTE IMPLEMENTATO — La creazione è attiva; tempi narrativi di 15/10 minuti e percentuale del set non fanno avanzare automaticamente un orologio di campagna."),
    "Reagenti e Ingredienti": ("implemented", "IMPLEMENTATO — Colori Rosso/Verde/Blu, livelli 1–4 e moltiplicatori calcolati sono presenti."),
    "Meccaniche di Creazione delle Pozioni": ("incorrect", "DIFFERENZA REDJANGO — La miscela ReDjango accetta fino a quattro reagenti e usa la formula/anteprima del backend; non applicare come limite automatico la frase Elder dei tre slot base."),
    "Regole Speciali di Alchimia": ("partial", "PARZIALMENTE IMPLEMENTATO — Estrazione e distillazione sono attive; fusione 3→1 e tutte le abilità speciali di produzione multipla non sono ancora complete."),
    "Incantamento": ("partial", "IMPLEMENTATO CON DIFFERENZE REDJANGO — Gemme, altari, livelli, cariche e pergamene sono calcolati dal banco Incantamento. Restano manuali il consumo delle cariche e la ricarica giornaliera, annotati nelle Regole speciali dell'oggetto."),
    ("Incantamento", "Introduzione"): ("partial", "PARZIALMENTE IMPLEMENTATO — Il livello della gemma guida il calcolo; tempi di lavorazione, anime per PF e gemme nere restano regole da tavolo."),
    "Incantare Oggetti": ("partial", "IMPLEMENTATO CON DIFFERENZE REDJANGO — Altare, gemme, cariche e pergamene sono gestiti dal banco. Le armi restano fuori: le tre abilità che le incantano sono dichiarate come regole da tavolo."),
    "Forgiatura": ("partial", "PARZIALMENTE IMPLEMENTATO — Il banco consuma i lingotti, crea l'esemplare, applica i miglioramenti con il raddoppio dei costi e fonde per recuperare il materiale. NON ANCORA IMPLEMENTATO il resto del ramo Fabbro: Riplasmare, Converti oggetto e gli oggetti di Uso pratico restano regole da tavolo."),
    "Materiali e Livelli": ("implemented", "IMPLEMENTATO — Le sette fasce e i due rami sono nel banco; ogni materiale si sblocca dall'abilità corrispondente e richiede strumenti da fabbro di livello pari alla fascia."),
    "Creazione degli Oggetti": ("implemented", "IMPLEMENTATO — Lingotti per categoria, ore di lavorazione e resa delle frecce sono applicati dal banco Forgiatura."),
    "Miglioramento degli Oggetti": ("partial", "IMPLEMENTATO CON DIFFERENZE REDJANGO — Undici miglioramenti su quattordici sono calcolati sulla scheda; Sanguinamento e Reroll consumano punti ma restano regole da tavolo, scritte nelle Regole speciali dell'oggetto."),
    "Cumulare Miglioramenti": ("implemented", "IMPLEMENTATO — Il raddoppio è calcolato e mostrato in anteprima: 1, 2, 4, 8. Resistenze diverse non raddoppiano fra loro, la stessa ripetuta sì."),
}


_RULE_GUIDE_LINKS: dict[str, tuple[str, str]] = {
    "Risorse del Personaggio": (
        CHARACTER_VARIABLE_GUIDE_NAME,
        "Valori base, formule attive e dipendenze di PF, Mana, Energia, Potere e PA sono elencati nella guida",
    ),
}


def _heading_text(raw_heading: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", "", raw_heading)).split())


# Correzioni al testo importato da Elder, applicate sia in import sia sulla
# guida già salvata. Elder parlava di "+1 danno": ReDjango non ha un bersaglio
# danno, la potenza di un colpo la decide il Tier, e il passivo Orsimer è
# applicato automaticamente su quello.
RACE_GUIDE_CORRECTIONS = (
    (
        "+1 danno ad attacchi fisici ogni 3 livelli",
        "+1 Tier agli attacchi fisici ogni 3 livelli",
    ),
    # La frase d'apertura di Elder diceva di sommare tutto a mano. In ReDjango i
    # bonus numerici di razza e sottorazza sono effetti automatici, raddoppi
    # compresi: lasciarla com'era farebbe contare due volte gli stessi punti.
    (
        "Tutti i bonus, esclusi i bonus caratteristica razziali di base che sono "
        "calcolati automaticamente ma modificabili(li trovi tra gli effetti), vanno "
        "aggiunti a mano. I bonus attivi e passivi non aumentano, ma quelli di "
        "sottorazza di raddoppiano, se possibile, a lv 5,10,15,20.",
        "In ReDjango i bonus numerici di razza e sottorazza sono applicati "
        "automaticamente alla scheda, raddoppi compresi: non vanno sommati a mano. "
        "Restano da segnare al tavolo soltanto i poteri che il motore non sa "
        "rappresentare, e la creazione del PG li elenca uno per uno. I bonus attivi "
        "e passivi di razza non aumentano, mentre quelli di sottorazza guadagnano "
        "un'altra volta il valore di partenza a livello 5, 10, 15 e 20.",
    ),
)


def apply_race_guide_corrections(html: str) -> str:
    for original, replacement in RACE_GUIDE_CORRECTIONS:
        html = html.replace(original, replacement)
    return html


def race_guide_html(source: str) -> str:
    """Add stable race anchors and a compact table of contents to Elder's HTML guide."""
    source = apply_race_guide_corrections(source)
    if not re.search(r"<h3[^>]*>\s*Dremora\s*</h3>", source, flags=re.IGNORECASE):
        source = f"{source}\n{_DREMORA_GUIDE_HTML}"
    if not re.search(r"<h3[^>]*>\s*Xivilai\s*</h3>", source, flags=re.IGNORECASE):
        source = f"{source}\n{_XIVILAI_GUIDE_HTML}"
    if not re.search(r"<h3[^>]*>\s*Non morto\s*</h3>", source, flags=re.IGNORECASE):
        source = f"{source}\n{_UNDEAD_GUIDE_HTML}"
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


# La Lista Competenze di Elder contiene tutte e 21 le competenze, ma tre le
# chiama in modo diverso da come si chiamano nella scheda: chi cercava
# "Conoscenze Religioni" nella guida non trovava nulla. Qui i nomi vengono
# riportati a quelli canonici di COMPETENCE_DEFINITIONS.
RULES_GUIDE_COMPETENCE_RENAMES = (
    ("<strong>Conoscenze natura/geografia</strong>", "<strong>Conoscenze Natura e Geografia</strong>"),
    ("<strong>Religioni</strong>", "<strong>Conoscenze Religioni</strong>"),
    ("<strong>Storia/Nobilt&agrave;</strong>", "<strong>Conoscenze Storia e Nobilt&agrave;</strong>"),
)


def apply_rules_guide_corrections(html: str) -> str:
    for original, replacement in RULES_GUIDE_COMPETENCE_RENAMES:
        html = html.replace(original, replacement)
    return html


def _annotated_elder_rules_html() -> str:
    source = apply_rules_guide_corrections(_ELDER_RULES_PATH.read_text(encoding="utf-8"))
    current_h2 = ""

    def add_note(match: re.Match[str]) -> str:
        nonlocal current_h2
        level = match.group(1)
        heading = match.group(0)
        title = _heading_text(match.group(2))
        if level == "2":
            current_h2 = title
        link = _RULE_GUIDE_LINKS.get(title)
        if link:
            guide_name, lead = link
            heading += (
                f'<p class="guide-cross-link"><a href="#" data-guide="{escape(guide_name, quote=True)}">'
                f'{lead} “{guide_name}”.</a></p>'
            )
        note = _RULE_STATUS_NOTES.get((current_h2, title)) or _RULE_STATUS_NOTES.get(title)
        if not note:
            return heading
        status, text = note
        return (
            f'{heading}<aside class="guide-implementation-note guide-status-{status}" '
            f'role="note"><strong>Nota ReDjango</strong><p>{text}</p></aside>'
        )

    return re.sub(r"<h([1-3])\b[^>]*>(.*?)</h\1>", add_note, source, flags=re.IGNORECASE | re.DOTALL)


def mechanics_glossary_blocks() -> list[dict[str, Any]]:
    """Glossario dei termini che oggetti e abilità danno per scontati.

    Le voci descrivono la meccanica, non i valori: numeri, costi e durate
    restano scritti sul singolo oggetto o sulla singola abilità, perché
    cambiano a ogni livello del pezzo.
    """
    return [
        {"type": "heading", "text": "Glossario delle meccaniche"},
        {
            "type": "paragraph",
            "text": (
                "Anelli, mantelli, pergamene e abilità usano un vocabolario comune che il resto "
                "del regolamento dava per noto. Qui c'è il significato di ogni termine: i valori "
                "concreti (metri, durate, costi, numero di usi) restano scritti sul singolo pezzo, "
                "perché cambiano a ogni livello."
            ),
        },
        {"type": "heading", "text": "Danno e difese magiche"},
        {
            "type": "entries",
            "items": [
                {
                    "title": "Danno puro",
                    "meta": "Tipo di danno",
                    "note": (
                        "Danno che annulla qualsiasi resistenza e qualsiasi riduzione danni: arriva "
                        "sempre per intero. Non è una proprietà che si possa aggiungere a un colpo "
                        "qualunque: armi normali e incantesimi normali non sono in grado di infliggere "
                        "danno puro. Lo infliggono soltanto le fonti che lo dichiarano esplicitamente, "
                        "come il Raggio arcano."
                    ),
                },
                {
                    "title": "Scudo arcano",
                    "meta": "Difesa attivabile",
                    "note": (
                        "Assorbe per intero un numero prefissato di attacchi: l'attacco assorbito non "
                        "infligge nulla, indipendentemente da quanto avrebbe fatto. L'oggetto indica "
                        "quanti attacchi copre."
                    ),
                },
                {
                    "title": "Immagini speculari",
                    "meta": "Difesa attivabile",
                    "note": (
                        "Crea copie illusorie del personaggio che possono assorbire al posto suo gli "
                        "attacchi indirizzati contro di lui. L'oggetto indica quante immagini crea e "
                        "quanta Energia e quanti PA costano."
                    ),
                },
                {
                    "title": "Raggio arcano",
                    "meta": "Attacco a distanza",
                    "note": (
                        "Un raggio che colpisce a distanza e infligge danno puro. L'oggetto indica "
                        "gittata, danno, costo e quante volte è utilizzabile."
                    ),
                },
            ],
        },
        {"type": "heading", "text": "Scuole di magia"},
        {
            "type": "paragraph",
            "text": (
                "Ogni incantesimo appartiene a una scuola. La scuola è volutamente un'etichetta ampia: "
                "serve a raggruppare abilità, vesti, pergamene e anelli, non a imporre limiti rigidi su "
                "che cosa un incantesimo possa fare."
            ),
        },
        {
            "type": "entries",
            "items": [
                {"title": "Alterazione", "meta": "", "note": "Modifica le proprietà fisiche di ciò che esiste: peso, forma, solidità, serrature, oggetti nascosti."},
                {"title": "Distruzione", "meta": "", "note": "Magia offensiva diretta: elementi, raggi, esplosioni, danno inflitto sul posto."},
                {"title": "Evocazione", "meta": "", "note": "Chiama qui armi, armature, risorse e creature. Ha regole proprie nella sezione Evocazione di questa guida."},
                {"title": "Illusione", "meta": "", "note": "Agisce sui sensi e sulla mente: apparenze, suoni, paura, frenesia, controllo del comportamento."},
                {"title": "Maledizioni", "meta": "", "note": "Indebolisce e affligge il bersaglio nel tempo: malus, aure sfavorevoli, sottrazione di risorse vitali."},
                {"title": "Misticismo", "meta": "", "note": "Magia che agisce sulla magia stessa e sui piani: riflettere, copiare, nascondere, percepire, cambiare stato."},
                {"title": "Negromanzia", "meta": "", "note": "Opera su morte e cadaveri: rianimare, parlare con i morti, oscurità, decomposizione."},
                {"title": "Recupero", "meta": "", "note": "Ripristina e sostiene: cura, stabilizza, rimuove stati negativi, restituisce risorse."},
            ],
        },
        {
            "type": "callout",
            "title": "Progressione degli incantesimi",
            "text": (
                "Per gli incantesimi la scala è base → apprendista → maestro, e indica quanto è avanzato "
                "l'incantesimo, non il personaggio. Pergamene e vesti che riportano ranghi diversi seguono "
                "la propria scala e non vanno confusi con questa."
            ),
        },
        {"type": "heading", "text": "Lanciare gli incantesimi"},
        {
            "type": "entries",
            "items": [
                {
                    "title": "Cast silenzioso",
                    "meta": "Modo di lancio",
                    "note": "Permette di lanciare incantesimi senza pronunciare la formula: funziona anche da Muto o quando parlare tradirebbe la posizione.",
                },
                {
                    "title": "Cast immobile",
                    "meta": "Modo di lancio",
                    "note": "Permette di lanciare incantesimi senza compiere gesti: funziona anche legati, immobilizzati o con le mani occupate.",
                },
                {
                    "title": "Concast",
                    "meta": "Lancio condiviso",
                    "note": (
                        "Toccando un alleato, uno dei due lancia usando le risorse dell'altro: l'alleato "
                        "può usare nel proprio turno Mana, Energia, Potere e PA del caster, oppure il "
                        "caster lancia subito usando quelli dell'alleato."
                    ),
                },
                {
                    "title": "Recast",
                    "meta": "Ripetizione",
                    "note": (
                        "Permette di rilanciare gratuitamente un incantesimo identico a uno già lanciato, "
                        "pagando un costo ridotto e diverso da quello originale. L'oggetto indica il tetto "
                        "di Mana dell'incantesimo ripetibile e la cadenza d'uso."
                    ),
                },
                {
                    "title": "Counterspell",
                    "meta": "Reazione",
                    "note": "Annulla un incantesimo mentre viene lanciato, al costo indicato dalla fonte. L'incantesimo annullato non ha alcun effetto.",
                },
                {
                    "title": "Contingenza",
                    "meta": "Lancio differito",
                    "note": (
                        "Si lancia adesso un incantesimo che resta pronto e scatta da solo quando si "
                        "verifica una condizione stabilita al momento del lancio, entro 24 ore. Il Mana "
                        "si paga al momento della preparazione. La fonte indica quanti incantesimi si "
                        "possono tenere pronti."
                    ),
                },
                {
                    "title": "Range spell",
                    "meta": "Gittata",
                    "note": (
                        "Moltiplica la gittata degli incantesimi. Esiste in due varianti: «singola», che "
                        "vale per il solo incantesimo collegato all'oggetto, e per scuola, che vale per "
                        "tutti gli incantesimi di quella scuola."
                    ),
                },
                {
                    "title": "Sigilli e Rune",
                    "meta": "Magia preparata",
                    "note": (
                        "Un sigillo si prepara in 24 ore pagando un sovrapprezzo di Mana e si lancia a "
                        "parte, senza sommarsi al Mana del momento. Una runa si lascia sul pavimento ed "
                        "esplode quando viene calpestata: è visibile e non si può applicare su un nemico."
                    ),
                },
            ],
        },
        {"type": "heading", "text": "Mana condiviso e recuperato"},
        {
            "type": "entries",
            "items": [
                {
                    "title": "Ponte di mana",
                    "meta": "Trasferimento",
                    "note": (
                        "Due personaggi consenzienti si scambiano Mana liberamente, in entrambe le "
                        "direzioni. Costa di norma 3 PA ogni 10 Mana trasferiti e richiede il contatto "
                        "(portata: tocco)."
                    ),
                },
                {
                    "title": "Sifone di mana",
                    "meta": "Riserva",
                    "note": (
                        "Raccoglie in una riserva separata una piccola percentuale del Mana lanciato dal "
                        "personaggio e da chi lancia nel suo raggio d'azione; il raggio dipende dalla fonte "
                        "del sifone. Il Mana accumulato torna poi disponibile. La percentuale è la variabile "
                        "«Sifone di Mana» e la riserva è il campo «Mana nel sifone» della scheda."
                    ),
                },
            ],
        },
        {
            "type": "callout",
            "title": "Come si riempie e si svuota il sifone",
            "text": (
                "Il motore accredita da solo la quota nella riserva ogni volta che il personaggio spende Mana, "
                "sia abbassando la barra sulla scheda o in combattimento, sia pagando i costi di un'azione dal "
                "piano del turno. Per riprenderlo apri la barra del Mana sulla scheda e usa il bottone «Sifone»: "
                "svuota tutta la riserva in un colpo solo, quindi l'eccedenza oltre il Mana speso va persa. "
                "Il Mana sifonato da chi lancia nel raggio d'azione non è automatico: lo aggiunge il Master "
                "modificando «Mana nel sifone» dalla gestione personaggio."
            ),
        },
        {"type": "heading", "text": "Portata, distanze e spostamento"},
        {
            "type": "entries",
            "items": [
                {
                    "title": "Touch",
                    "meta": "Portata",
                    "note": (
                        "La portata dell'abilità o dell'incantesimo è il contatto: il bersaglio dev'essere "
                        "adiacente e va toccato. Alcune abilità estendono esplicitamente la portata di un "
                        "effetto che nasce a tocco."
                    ),
                },
                {
                    "title": "Casella, esagono, metro",
                    "meta": "Distanze",
                    "note": (
                        "Casella ed esagono sono la stessa cosa: la cella della mappa di combattimento. Dal "
                        "centro di un esagono al centro di quello adiacente c'è 1 metro, quindi una casella "
                        "vale un metro e le tre parole sono intercambiabili."
                    ),
                },
                {
                    "title": "Blink",
                    "meta": "Spostamento",
                    "note": "Teletrasporto istantaneo a corto raggio. L'oggetto indica la distanza coperta e il costo in PA, Mana ed Energia.",
                },
                {
                    "title": "Mark e Recall",
                    "meta": "Spostamento",
                    "note": (
                        "Mark fissa un punto di richiamo nel luogo in cui ci si trova; Recall riporta il "
                        "personaggio al punto marcato. Sono due usi distinti e vanno pagati entrambi."
                    ),
                },
                {
                    "title": "Slowfall",
                    "meta": "Movimento",
                    "note": "Rallenta la caduta del bersaglio fino a circa 10 km/h, evitando i normali danni da caduta.",
                },
                {
                    "title": "Telecinesi",
                    "meta": "Manipolazione a distanza",
                    "note": (
                        "Muove oggetti a distanza senza toccarli. Il costo base è 1 Mana per metro percorso, "
                        "moltiplicato per la categoria di peso dell'oggetto: leggero ×1, medio ×2, pesante ×3. "
                        "Gli oggetti che superano il limite di peso della fonte non si muovono."
                    ),
                },
                {
                    "title": "Materializzazione",
                    "meta": "Richiamo di oggetti",
                    "note": (
                        "Fa comparire in mano un oggetto collegato alla fonte, ovunque si trovi. Il collegamento "
                        "si può cambiare gratuitamente. La fonte indica la dimensione massima dell'oggetto "
                        "richiamabile."
                    ),
                },
                {
                    "title": "Estrazione",
                    "meta": "Richiamo di oggetti",
                    "note": (
                        "Materializza in mano un oggetto già presente nello zaino, senza doverlo cercare. "
                        "Da non confondere con l'estrazione dei reagenti alchemici, che è tutt'altra regola. "
                        "L'oggetto indica il costo in Energia."
                    ),
                },
            ],
        },
        {"type": "heading", "text": "Effetti continuativi e di utilità"},
        {
            "type": "entries",
            "items": [
                {"title": "Darkvision", "meta": "Senso", "note": "Permette di vedere al buio, in assenza di altra luce, fino alla distanza indicata dalla fonte."},
                {"title": "Waterbreathing", "meta": "Sopravvivenza", "note": "Permette di respirare sott'acqua per la durata indicata dalla fonte."},
                {"title": "Sostentamento", "meta": "Sopravvivenza", "note": "Chi ne beneficia non ha bisogno di mangiare né di bere."},
                {"title": "Shapeshifting (Mutaforma)", "meta": "Trasformazione", "note": "Cambia la forma del personaggio per la durata indicata dalla fonte; mantenere o rinnovare la trasformazione costa di nuovo."},
                {"title": "Illusione minore", "meta": "Illusione", "note": "Crea l'illusione di un suono o di un piccolo oggetto, per la durata indicata dalla fonte. Non può ferire né sostenere peso."},
                {"title": "Rigenerazione PF e Mana", "meta": "Recupero passivo", "note": "Restituisce 1 PF o 1 Mana ogni intervallo di tempo di gioco indicato dalla fonte, senza bisogno di attivarla."},
            ],
        },
        {"type": "heading", "text": "Come si usano gli oggetti"},
        {
            "type": "entries",
            "items": [
                {
                    "title": "Effetto passivo",
                    "meta": "Sempre attivo",
                    "note": (
                        "Vale per il solo fatto di indossare o portare l'oggetto: non costa un'azione, non si "
                        "attiva e non si esaurisce. I bonus numerici della scheda sono quasi sempre passivi."
                    ),
                },
                {
                    "title": "Effetto attivabile",
                    "meta": "Va acceso",
                    "note": (
                        "Va dichiarato e pagato quando lo si usa, ha una durata e spesso un contraccolpo. Un "
                        "oggetto attivabile non fornisce nulla finché non lo si attiva, anche se lo si indossa."
                    ),
                },
                {
                    "title": "Cadenza d'uso",
                    "meta": "Quante volte",
                    "note": (
                        "«Una volta per combattimento» significa una volta per scontro: il contatore si azzera "
                        "quando il combattimento finisce. Fuori dal combattimento vale invece la cadenza a tempo "
                        "indicata dall'oggetto (una volta all'ora, al giorno). Le due cadenze sono separate e non "
                        "si sommano."
                    ),
                },
            ],
        },
    ]


def _redjango_rules_guide_content() -> str:
    return _guide_content(
        {"type": "legacy_html", "html": _annotated_elder_rules_html()},
        *mechanics_glossary_blocks(),
    )


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
        "seed_key": "nuovo-pg",
        "nome": NEW_CHARACTER_GUIDE_NAME,
        "categoria": "Personaggio",
        "ordine": 3,
        "contenuto": _guide_content(*nuovo_pg_guide_blocks()),
    },
    {
        "seed_key": "regole-varie",
        "nome": "Regole Varie",
        "categoria": "Regolamento",
        "ordine": 5,
        "contenuto": _redjango_rules_guide_content(),
    },
    {
        "seed_key": "compendio-oggetti",
        "nome": ITEM_COMPENDIUM_GUIDE_NAME,
        "categoria": "Compendio",
        "ordine": 8,
        "contenuto": _guide_content(
            {
                "type": "paragraph",
                "text": (
                    "Il catalogo completo degli oggetti del gioco: armi, armature, monili, pozioni, "
                    "pergamene, reagenti, strumenti e bottino. Filtra per categoria, rarità, regione o "
                    "livello, poi apri una scheda per leggere ogni dato del pezzo."
                ),
            },
            {
                "type": "callout",
                "title": "Le voci sottolineate si aprono",
                "text": (
                    "Nella scheda di un oggetto, categoria d'arma, effetti, rarità e livello di bottino "
                    "hanno una nota consultabile: la categoria di un'arma mostra il suo potere unico, "
                    "gli assi che la definiscono e i PA per attacco."
                ),
            },
            {"type": "item_compendium"},
        ),
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
                    "weapon_profile — override per singolo oggetto di assi, modalità di combattimento, munizioni e ricarica. Oggi nessun oggetto ne salva uno: il profilo effettivo arriva dalle regole del Tipo arma. Compilalo solo per un'arma che deve discostarsi dal suo tipo.",
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
        "contenuto": _guide_content({"type": "dynamic_character_variables"}),
    },
    {
        "seed_key": "accesso-remoto-tailscale",
        "nome": "Accesso remoto privato · Tailscale",
        "categoria": "Amministrazione",
        "ordine": 90,
        "minimum_role": "admin",
        "contenuto": _guide_content(
            {
                "type": "paragraph",
                "text": (
                    "Questa guida è visibile soltanto agli Amministratori di gioco. Tailscale non è una quarta "
                    "modalità di ReDjango: è un adattatore di rete isolato che pubblica la modalità online tramite "
                    "un indirizzo HTTPS privato. Database, media e login restano interamente gestiti da ReDjango."
                ),
            },
            {"type": "heading", "text": "Spiegazione semplice (ELI5)"},
            {
                "type": "list",
                "items": [
                    "Il computer che ospita ReDjango è la casa del gioco: deve rimanere acceso, connesso e senza sospensione.",
                    "Tailscale crea una strada privata e cifrata fra quella casa e i computer degli amici.",
                    "Tailscale Serve mette una porta HTTPS sulla strada privata e accompagna le richieste fino a ReDjango su 127.0.0.1:8003.",
                    "Ogni amico deve essere invitato in Tailscale e deve comunque accedere con il proprio account ReDjango.",
                    "Spegnere Tailscale non modifica il gioco: interrompe soltanto la strada privata. In futuro si potrà sostituire con Cloudflare, un VPS o Vercel senza creare una nuova modalità applicativa.",
                    "La Mappa Globale viene divisa in tasselli: il giocatore scarica soltanto la zona e il dettaglio che sta guardando, ma ingrandendo ritrova sempre le scritte alla risoluzione originale.",
                    "Impostazioni → Media locali è come uno zaino sul computer del giocatore: conserva in anticipo i media condivisi della campagna e li riusa senza riscaricarli.",
                ],
            },
            {"type": "heading", "text": "Avvio rapido per l'Amministratore"},
            {
                "type": "list",
                "items": [
                    "Installa Tailscale sul computer server, accedi e attendi che lo stato sia Running.",
                    "Se il server deve restare raggiungibile dopo un logout o riavvio, dall'icona Tailscale scegli Preferences → Run unattended. Questa opzione mantiene Tailscale attivo, ma non avvia automaticamente ReDjango.",
                    "Dalla radice del progetto esegui lo script indicato sotto. Il launcher rileva il nome .ts.net, prepara una chiave privata persistente e avvia ReDjango in modalità online.",
                    "Apri l'indirizzo HTTPS stampato dal launcher e verifica il login prima di invitare altre persone.",
                    "Dalla pagina Machines di Tailscale condividi soltanto questo computer con gli indirizzi dei giocatori.",
                    "Crea un account ReDjango distinto per ogni giocatore e non condividere mai l'account amministratore.",
                    "Prima della prima sessione esegui prepare_travel_tiles per preparare una volta sola i tasselli delle mappe; altrimenti ReDjango li preparerà al primo accesso a Viaggio.",
                    "Prima di partire copia fuori dal computer sia db.sqlite3 sia l'intera cartella media: i backup integrati non comprendono i file multimediali.",
                ],
            },
            {
                "type": "code",
                "language": "powershell",
                "text": (
                    ".\\run_tailscale_plus_server.bat\n"
                    "# Il launcher richiede automaticamente l'autorizzazione Windows per Tailscale Serve.\n"
                    "# Avvio PowerShell avanzato, se necessario:\n"
                    "powershell -ExecutionPolicy Bypass -File .\\redjango\\deployment\\tailscale\\start.ps1\n"
                    "# Per controllare configurazione e connettività:\n"
                    "powershell -ExecutionPolicy Bypass -File .\\redjango\\deployment\\tailscale\\diagnose.ps1\n"
                    "# Prepara in anticipo tutte le mappe globali senza modificare gli originali:\n"
                    ".\\venv\\Scripts\\python.exe manage.py prepare_travel_tiles\n"
                    "# Per rimuovere soltanto la pubblicazione HTTPS di ReDjango:\n"
                    "powershell -ExecutionPolicy Bypass -File .\\redjango\\deployment\\tailscale\\stop.ps1"
                ),
            },
            {"type": "heading", "text": "Guida per i giocatori"},
            {
                "type": "list",
                "items": [
                    "Installa Tailscale dal sito ufficiale e accedi con il tuo account personale.",
                    "Apri l'invito ricevuto dall'Amministratore e accetta la condivisione del computer ReDjango.",
                    "Apri nel browser l'indirizzo https://nome-computer.nome-rete.ts.net comunicato dall'Amministratore.",
                    "Accedi con il tuo nome utente e la tua password ReDjango; l'invito Tailscale non sostituisce il login del gioco.",
                    "Apri Impostazioni → Media locali. Premi Mantieni su questo dispositivo, poi Scarica media campagna e lascia aperta la pagina fino al completamento.",
                    "In seguito usa Aggiorna media locali: vengono scaricati soltanto i file nuovi o cambiati. Svuota cache media locale cancella esclusivamente il pacchetto ReDjango di quell'account e campagna.",
                    "Se la pagina non si apre, verifica che Tailscale dica Connected, poi prova di nuovo senza VPN aziendali o filtri concorrenti.",
                    "Non inoltrare l'invito o le credenziali. Se perdi un dispositivo, avvisa l'Amministratore perché possa revocare subito la condivisione.",
                ],
            },
            {"type": "heading", "text": "Full Tech Debug"},
            {
                "type": "callout",
                "title": "Confine architetturale",
                "text": (
                    "ReDjango usa sempre REDJANGO_ACCESS_MODE=online. Lo script Tailscale valorizza soltanto il "
                    "contratto generico REDJANGO_PUBLIC_ORIGIN e inoltra HTTPS a http://127.0.0.1:8003. Nessun "
                    "pacchetto Tailscale viene importato da Django o React e gli header di identità Tailscale non "
                    "vengono usati per autorizzare un giocatore."
                ),
            },
            {
                "type": "list",
                "items": [
                    "REDJANGO_PUBLIC_ORIGIN viene validata come origine HTTPS senza percorso, query, frammento o credenziali; da essa Django deriva ALLOWED_HOSTS e CSRF_TRUSTED_ORIGINS.",
                    "REDJANGO_SECRET_KEY viene letta da .redjango/django-secret-key, che è ignorato da Git e deve restare privato. Cambiarla invalida le sessioni e rende illeggibili eventuali segreti AI cifrati con la chiave precedente.",
                    "REDJANGO_TRUSTED_PROXIES resta limitato ai loopback. Tailscale Serve è configurato verso 127.0.0.1, quindi non è necessario fidarsi della rete Tailscale intera.",
                    "Il proxy deve preservare X-Forwarded-Proto=https. Se il controllo remoto segnala troppi redirect, esegui diagnose.ps1 e controlla gli header prima di disattivare qualsiasi protezione HTTPS.",
                    "Il flusso Combattimento usa Server-Sent Events: verificare che la connessione /api/combat/.../events resti aperta e si riconnetta dopo cinque minuti.",
                    "Il controllo pubblico /api/auth/session/ deve rispondere senza richiedere un login. Un errore locale indica ReDjango; un locale verde e un remoto rosso indica Tailscale, DNS, condivisione o policy.",
                    "I media condivisi con URL versionati rispondono con Cache-Control private, max-age=31536000, immutable, ETag e Last-Modified. Un 304 indica che la convalida funziona; no-store è intenzionale per i media a visibilità limitata.",
                    "Le tile native sono artefatti rigenerabili sotto media/.derived/travel_tiles. Ogni URL contiene la revisione della sorgente; l'originale non viene ridimensionato né sovrascritto.",
                    "Il Service Worker vive a /service-worker.js, controlla soltanto richieste /media/ e salva una risposta soltanto quando X-ReDjango-Cacheability vale immutable. L'associazione client/utente/campagna è conservata anche se il browser riavvia il worker; le richieste Range di audio/video vengono ricostruite dalla copia completa locale.",
                    "La cache gestita è separata per utente e campagna e viene disattivata al logout. I media visibilita_limitata sono esclusi dal manifest e una risposta restricted-no-store viene rifiutata anche durante un download manuale.",
                    "Cache Storage e navigator.storage.persist richiedono HTTPS o localhost. Il browser può rifiutare la persistenza o essere svuotato manualmente; Media locali mostra uso, quota e stato effettivo.",
                    "Tailscale Serve resta configurato in background anche dopo il riavvio del servizio. ReDjango deve comunque essere avviato e Windows non deve sospendere il computer.",
                    "Su Windows, Run unattended mantiene Tailscale connesso senza un utente attivo. Dopo un riavvio bisogna comunque rilanciare run_tailscale_plus_server.bat, finché ReDjango non dispone di un servizio di avvio automatico dedicato.",
                ],
            },
            {
                "type": "code",
                "language": "powershell",
                "text": (
                    "tailscale status\n"
                    "tailscale serve status\n"
                    "Invoke-WebRequest http://127.0.0.1:8003/api/auth/session/ -UseBasicParsing\n"
                    "$dns = (tailscale status --json | ConvertFrom-Json).Self.DNSName.TrimEnd('.')\n"
                    "Invoke-WebRequest (\"https://{0}/api/auth/session/\" -f $dns) -UseBasicParsing\n"
                    "Get-NetTCPConnection -LocalPort 8003 -State Listen"
                ),
            },
            {
                "type": "warning",
                "title": "Non usare Funnel per questa configurazione",
                "text": (
                    "Serve limita l'accesso agli utenti Tailscale autorizzati. Funnel renderebbe il servizio pubblico "
                    "su Internet e richiederebbe una revisione separata di esposizione, rate limit e monitoraggio."
                ),
            },
        ),
    },
]

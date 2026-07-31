"""Batch-curate the Elder descriptive effects into `Oggetto.regole_speciali`.

Dry run by default: it reports what it *would* write, per rule and per item, and
lists every text no rule covers. `--apply` performs the write through
`sync_special_rules_review`, so the acknowledgement that releases an item from
the review queue is recorded exactly as the item editor records it.

The rule table below is the reviewable artefact. Each entry turns one Elder
shorthand into one Italian sentence a master can read at the table; entries
whose meaning cannot be derived from the data alone render `None`, which leaves
those items flagged on purpose. See
`Builder_docs/ITEM_SPECIAL_RULES_REVIEW_GUIDE.md`.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from backend.core.item_services import sync_special_rules_review
from backend.core.item_special import compute_special_reasons, descriptive_effects
from backend.core.models import Oggetto


# Stamped on every item this command writes, so `--recurate` can tell its own
# output from a rule a master typed by hand.
SOURCE = "curate_item_special_rules"


def _number(raw: str) -> str:
    """Render an Elder number the way Italian prose expects it."""
    text = str(raw).strip().replace(",", ".")
    value = float(text)
    return str(int(value)) if value.is_integer() else f"{value:g}".replace(".", ",")


def _plural(count: str, singular: str, plural: str) -> str:
    return singular if _number(count) == "1" else plural


_TIME_UNITS = {
    "sec": ("secondo", "secondi"),
    "min": ("minuto", "minuti"),
    "ora": ("ora", "ore"),
    "ore": ("ora", "ore"),
    "h": ("ora", "ore"),
}


def _duration(count: str, unit: str) -> str:
    singular, plural = _TIME_UNITS[unit.lower()]
    return f"{_number(count)} {_plural(count, singular, plural)}"


def _every(count: str, unit: str) -> str:
    """"ogni ora", not "ogni 1 ora": Italian drops the numeral at one."""
    singular, plural = _TIME_UNITS[unit.lower()]
    return f"ogni {singular}" if _number(count) == "1" else f"ogni {_number(count)} {plural}"


def _render_esplosione(raw_rings) -> str:
    """"Un Classico A['B]['C]": blunt damage at ground zero, then successive hex rings."""
    rings = list(raw_rings)
    if len(rings) == 1:
        return f"Esplode nella cella bersaglio infliggendo {_number(rings[0])} danni contundenti."
    parts = [f"{_number(rings[0])} danni contundenti nella cella bersaglio"]
    for distance, value in enumerate(rings[1:], start=1):
        parts.append(
            f"{_number(value)} danni contundenti nelle celle a {distance} "
            f"{_plural(str(distance), 'esagono', 'esagoni')} di distanza"
        )
    return "Esplode infliggendo " + ", ".join(parts) + "."


@dataclass(frozen=True)
class Rule:
    key: str
    pattern: re.Pattern[str]
    render: Callable[[re.Match[str]], str | None]


RULES: tuple[Rule, ...] = (
    # --- Boolean capabilities -------------------------------------------------
    Rule("cast_silenzioso", re.compile(r"^cast\s+silenzioso\s*:?\s*si$", re.I),
         lambda m: "Cast silenzioso: gli incantesimi possono essere lanciati senza pronunciare la formula."),
    Rule("cast_immobile", re.compile(r"^cast\s+immobile\s*:?\s*si$", re.I),
         lambda m: "Cast immobile: gli incantesimi possono essere lanciati senza compiere gesti."),
    Rule("waterbreathing", re.compile(r"^respiro\s+sott.?acqua\s*:?\s*si$", re.I),
         lambda m: "Respiro sott'acqua: chi lo indossa può respirare sott'acqua senza limiti di tempo."),
    Rule("sostentamento", re.compile(r"^sostentamento\s*:?\s*si$", re.I),
         lambda m: "Sostentamento: chi lo indossa non ha bisogno di mangiare né di bere."),
    Rule("ponte_di_mana", re.compile(r"^ponte\s+di\s+mana\s*:?\s*si$", re.I),
         lambda m: "Permette di scambiare mana tra persone che vogliono. Tocco."),

    # --- Regeneration over real time -----------------------------------------
    Rule("rigenerazione", re.compile(r"^rigenera\s+(\d+)\s*(pf|mana)\s+ogni\s+(\d+)\s*(sec|min|ora|ore|h)\.?$", re.I),
         lambda m: (
             f"Rigenera {_number(m.group(1))} {'PF' if m.group(2).lower() == 'pf' else 'mana'} "
             f"{_every(m.group(3), m.group(4))} di tempo di gioco."
         )),

    # --- Spell range multipliers ---------------------------------------------
    Rule("range_spell", re.compile(r"^range\s+spell\s*\*\s*([\d.,]+)$", re.I),
         lambda m: f"Moltiplica per {_number(m.group(1))} la gittata dell'incantesimo collegato all'oggetto."),
    Rule("range_scuola", re.compile(r"^range\s+scuola\s*\*\s*([\d.,]+)$", re.I),
         lambda m: f"Moltiplica per {_number(m.group(1))} la gittata degli incantesimi della scuola collegata."),
    Rule("range_tutte", re.compile(r"^range\s+tutte\s*\*\s*([\d.,]+)$", re.I),
         lambda m: f"Moltiplica per {_number(m.group(1))} la gittata degli incantesimi di tutte le scuole."),

    # --- Free spell power by school ------------------------------------------
    Rule("potere_free", re.compile(r"^\+\s*(\d+)\s+potere\s+free\s+(.+)$", re.I),
         lambda m: (
             f"Concede {_number(m.group(1))} "
             f"{_plural(m.group(1), 'potere gratuito', 'poteri gratuiti')} "
             f"per gli incantesimi di {m.group(2).strip().capitalize()}."
         )),

    # --- Costs and counters ---------------------------------------------------
    # "reroll" is the table's own term: never paraphrase it as "ripetere il tiro".
    Rule("reroll", re.compile(r"^(\d+)\s+reroll,\s*costo\s+en\s*:\s*(\d+)$", re.I),
         lambda m: (
             f"Concede {_number(m.group(1))} reroll al costo di {_number(m.group(2))} Energia"
             f"{'' if _number(m.group(1)) == '1' else ' ciascuno'}."
         )),
    Rule("estrazione_costo", re.compile(r"^costo\s+estrazione\s*:\s*(\d+)\s*en$", re.I),
         lambda m: f"Estrarre l'oggetto costa {_number(m.group(1))} Energia."),
    Rule("estrazione_gratis", re.compile(r"^costo\s+estrazione\s*:\s*gratis$", re.I),
         lambda m: "Estrarre l'oggetto è gratuito."),
    Rule("counterspell", re.compile(r"^costo\s+(\d+)\s*en\s+(\d+)\s*pa\s+(\d+)\s*magi[ae]$", re.I),
         lambda m: (
             f"Annulla fino a {_number(m.group(3))} {_plural(m.group(3), 'magia', 'magie')}, "
             f"al costo di {_number(m.group(1))} Energia e {_number(m.group(2))} PA."
         )),
    Rule("scudo_arcano", re.compile(r"^numero\s+attacchi\s*:\s*(\d+)$", re.I),
         lambda m: f"Assorbe {_number(m.group(1))} {_plural(m.group(1), 'attacco', 'attacchi')}."),
    Rule("contingenza", re.compile(r"^contingenza\s+spell\s+(\d+)$", re.I),
         lambda m: (
             f"Permette di tenere pronti in contingenza {_number(m.group(1))} "
             f"{_plural(m.group(1), 'incantesimo', 'incantesimi')}."
         )),
    Rule("immagini", re.compile(r"^immagini\s*:\s*(\d+)\s*imm\s*\(\s*(\d+)\s*en\s*(\d+)\s*pa\s*\)$", re.I),
         lambda m: (
             f"Crea {_number(m.group(1))} {_plural(m.group(1), 'immagine speculare', 'immagini speculari')}, "
             f"al costo di {_number(m.group(2))} Energia e {_number(m.group(3))} PA."
         )),
    Rule("illusione_durata", re.compile(r"^durata\s+illusione\s*:\s*(\d+)\s*turn[oi]$", re.I),
         lambda m: f"L'illusione dura {_number(m.group(1))} {_plural(m.group(1), 'turno', 'turni')}."),
    Rule("materializzazione", re.compile(r"^grandezza\s+oggetto\s*:\s*fino\s+a\s+(.+)$", re.I),
         lambda m: f"Materializza oggetti fino alla dimensione di: {m.group(1).strip()}."),
    Rule("telecinesi", re.compile(r"^numero\s+kg\s*:\s*([\d.,]+)\s*kg$", re.I),
         lambda m: f"Sposta con la telecinesi oggetti fino a {_number(m.group(1))} kg."),
    Rule("luce", re.compile(r"^tempo\s+luce\s*:\s*(\d+)\s*(sec|min|ore?|h)$", re.I),
         lambda m: f"Produce luce per {_duration(m.group(1), m.group(2))}."),
    Rule("darkvision", re.compile(r"^raggio\s+darkvision\s*:\s*(\d+)\s*mt$", re.I),
         lambda m: f"Concede visione nel buio entro {_number(m.group(1))} metri."),
    Rule("shapeshift", re.compile(r"^tempo\s+shapeshift\s*:\s*(\d+)\s*(sec|min|ore?|h)$", re.I),
         lambda m: f"La trasformazione dura {_duration(m.group(1), m.group(2))}."),

    # "danno raggio: <base>[+ ]lvpg[*/mult]": arcane-ray damage scaled by the
    # wielder's character level ("lvpg"). Confirmed against the item's own
    # `descrizione` field ("casti un raggio arcano fino a 20 metri. infligge
    # danno puro. + 1pa/lv oggetto + 1 en/lv oggetto. Una volta a combat.").
    Rule("danno_raggio", re.compile(
            r"^danno\s+raggio\s*:\s*(\d+)\s*\+\s*lvpg\s*(?:([*/])\s*([\d.,]+))?$", re.I),
         lambda m: (
             "Casti un raggio arcano fino a 20 metri, che infligge "
             f"{_number(m.group(1))} {_plural(m.group(1), 'danno puro', 'danni puri')}, "
             "più il livello del personaggio"
             + (f" diviso {_number(m.group(3))}" if m.group(2) == "/"
                else f" moltiplicato per {_number(m.group(3))}" if m.group(2) == "*"
                else "")
             + ". Costa 1 PA e 1 Energia per livello dell'oggetto. "
             "Utilizzabile una volta per combattimento."
         )),

    # Duration-tiered potions: the trailing "-M" on the effect text equals the
    # M in the item name and scales with potion level. Meaning confirmed per
    # family against the item's own `descrizione` and the table master.
    Rule("pozione_invisibilita", re.compile(r"^invisibile\s+per\s+x\s+turni\s*-\s*(\d+)$", re.I),
         lambda m: (
             f"Diventi invisibile per {_number(m.group(1))} "
             f"{_plural(m.group(1), 'turno', 'turni')}. Puoi comunque fare rumore."
         )),
    Rule("pozione_volo", re.compile(r"^voli\s+per\s+x\s+turni\s*-\s*(\d+)$", re.I),
         lambda m: f"Puoi volare per {_number(m.group(1))} {_plural(m.group(1), 'turno', 'turni')}."),
    Rule("pozione_cura_effetti", re.compile(r"^curati\s+da\s+effetti\s+nocivi\s*-\s*(\d+)$", re.I),
         lambda m: (
             f"Curati casualmente da {_number(m.group(1))} "
             f"{_plural(m.group(1), 'effetto nocivo o malattia', 'effetti nocivi o malattie')}."
         )),
    # 1 hex = 1 metro in questo sistema, quindi "raggio" si esprime in metri.
    Rule("pozione_fumogeno", re.compile(r"^crei\s+fumo\s+per\s+2\s+turni\s*-\s*(\d+)$", re.I),
         lambda m: (
             f"Crei una nuvola di fumo per 2 turni, con un raggio di {_number(m.group(1))} "
             f"{_plural(m.group(1), 'metro', 'metri')}."
         )),
    # M conta gli attacchi subiti che avevano una possibilità di colpire, non
    # gli attacchi effettivamente evitati: l'effetto scala anche se il 50% non
    # è mai scattato, e un attacco mancato per conto del nemico non conta.
    Rule("pozione_intangibilita", re.compile(r"^50%\s+di\s+evitare\s+danno\s+fisico\s*-\s*(\d+)$", re.I),
         lambda m: (
             f"Per i prossimi {_number(m.group(1))} "
             f"{_plural(m.group(1), 'attacco fisico subito', 'attacchi fisici subiti')} che "
             f"{_plural(m.group(1), 'aveva', 'avevano')} la possibilità di colpirti, hai il 50% "
             "di possibilità di evitare il danno. "
             f"L'effetto svanisce dopo {_number(m.group(1))} "
             f"{_plural(m.group(1), 'attacco così conteggiato', 'attacchi così conteggiati')}, "
             "anche se il 50% non è mai scattato a tuo favore; un attacco che il nemico manca per "
             "conto proprio non viene conteggiato."
         )),
    Rule("pozione_attacco", re.compile(r"^attacco\s+5\s+turni\s*-\s*(\d+)$", re.I),
         lambda m: f"Per 5 turni, aggiunge +{_number(m.group(1))} ad Attacco."),
    # Exact sibling of pozione_attacco (same "Aggiungi a Effetti" descrizione,
    # same "5 Turni -N" shape, paired item naming: Pozione attacco - 5t /
    # Pozione difesa - 5t). Applying the same reading by analogy.
    Rule("pozione_difesa", re.compile(r"^difesa\s+5\s+turni\s*-\s*(\d+)$", re.I),
         lambda m: f"Per 5 turni, aggiunge +{_number(m.group(1))} a Difesa."),

    # Alcoholic drinks: no formula to derive, just "you get drunk". 15 items,
    # all beverages (Cognac Bretone, Vino Pregiato, ...).
    Rule("sbornia", re.compile(r"^dopo\s+10\s+turni,\s*-50%\s*energia\s*\(sul\s+massimale\)$", re.I),
         lambda m: "Dopo 10 turni dall'attivazione, l'Energia massima viene dimezzata (-50%)."),

    # Ring/accessory light and darkvision utility (distinct from the timed
    # "tempo luce: N sec" / "raggio darkvision: N mt" families above).
    Rule("anello_luce", re.compile(r"^tempo\s+luce\s*:\s*a\s+volonta(?:,\s*intensita\s*\*\s*([\d.,]+))?$", re.I),
         lambda m: (
             "Crei luce attorno a te a volontà, con intensità regolabile dal caster da luce di "
             "candela a luce di falò"
             + (f", moltiplicata per {_number(m.group(1))}" if m.group(1) else "")
             + ", al costo di 2 Energia."
         )),
    Rule("anello_darkvision", re.compile(r"^raggio\s+darkvision\s*:\s*(1\s*km|infinito)$", re.I),
         lambda m: (
             "Vedi al buio senza limiti di distanza (in assenza di altra luce)."
             if m.group(1).strip().lower() == "infinito"
             else "Vedi al buio fino a 1 km di distanza (in assenza di altra luce)."
         )),

    # "Calcola sul danno da infliggere": the % is a magic-damage reduction
    # applied for the duration.
    Rule("pozione_res_magica", re.compile(r"^resistenza\s+magica\s+1\s+turno\s+(\d+)%$", re.I),
         lambda m: f"Per 1 turno, riduci del {_number(m.group(1))}% il danno magico subito."),

    # "Pozione vita temp. -24h": temporary HP is an established mechanic
    # elsewhere in this data ("+25% pf temporanei per 10 turni").
    Rule("pozione_vita_temp", re.compile(r"^vita\s+temporanea\s*-\s*(\d+)$", re.I),
         lambda m: f"Concede {_number(m.group(1))} punti ferita temporanei, validi per 24 ore."),

    # "Su nemici vivi": bonus damage specifically against living enemies.
    Rule("pozione_danneggia_vita", re.compile(r"^\+\s*danno\s+a\s+nemico\s*-\s*(\d+)$", re.I),
         lambda m: f"Infligge {_number(m.group(1))} danni aggiuntivi contro nemici viventi."),

    # Poisons: the debuff applies to the *target* only once the poisoned
    # attack actually connects, per the table master.
    Rule("veleno_pa", re.compile(r"^-\s*pa\s+nemico\s*-\s*(\d+)$", re.I),
         lambda m: (
             "Veleno: applicalo a un'arma o a un attacco. Se l'attacco colpisce il bersaglio, il "
             f"nemico colpito perde {_number(m.group(1))} PA."
         )),
    Rule("veleno_mana", re.compile(r"^\+\s*mana\s+speso\s+nemico\s*-\s*(\d+)$", re.I),
         lambda m: (
             "Veleno: applicalo a un'arma o a un attacco. Se l'attacco colpisce il bersaglio, il "
             f"nemico colpito perde {_number(m.group(1))} mana."
         )),

    # "Oltre a PA per bere -N": refunds whatever PA the drinker actually spent
    # to drink (not a flat 3), plus N — so a reduced drinking cost from another
    # power doesn't inflate the net PA gain, per the table master.
    Rule("pozione_piu_pa", re.compile(r"^oltre\s+a\s+pa\s+per\s+bere\s*-\s*(\d+)$", re.I),
         lambda m: (
             "Recupera tutti i PA spesi per bere questa pozione, più "
             f"{_number(m.group(1))} PA aggiuntivi: il guadagno netto è quindi di "
             f"{_number(m.group(1))} PA, anche se il costo per bere è ridotto da altri poteri."
         )),

    # "Un Classico A['B]['C]": blunt damage at the target hex, then successive
    # rings of adjacent hexes, per the table master.
    Rule("pozione_esplosione", re.compile(r"^un\s+classico\s+(\d+)(?:'(\d+))?(?:'(\d+))?$", re.I),
         lambda m: _render_esplosione(g for g in m.groups() if g is not None)),

    # --- Consumables that restore a resource ---------------------------------
    # Elder wrote these as a negative on the "spent" counter; at the table they
    # are simply "restores N".
    Rule("pozione_pf", re.compile(r"^personaggio\.danno\s*-\s*(\d+)$", re.I),
         lambda m: f"Ripristina {_number(m.group(1))} punti ferita."),
    Rule("pozione_mana", re.compile(r"^personaggio\.mana_speso\s*-\s*(\d+)$", re.I),
         lambda m: f"Ripristina {_number(m.group(1))} mana."),
    Rule("pozione_energia", re.compile(r"^personaggio\.energia_spesa\s*-\s*(\d+)$", re.I),
         lambda m: f"Ripristina {_number(m.group(1))} Energia."),
    Rule("pozione_potere", re.compile(r"^personaggio\.potere_speso\s*-\s*(\d+)$", re.I),
         lambda m: f"Ripristina {_number(m.group(1))} Potere."),

    # `mod gen A (B)`: A tracks ceil(livello/2); B is the stanchezza cost. Both
    # are read directly off the item, no formula needed at the table.
    Rule("mod_gen", re.compile(r"^\+?\s*mod\s+gen\s*(\d+)\s*\(\s*(\d+)\s*\)$", re.I),
         lambda m: (
             f"Per 2 turni concede +{_number(m.group(1))} al modificatore generale, poi si paga "
             f"{_number(m.group(2))} {_plural(m.group(2), 'punto stanchezza', 'punti stanchezza')}. "
             "Attivabile (non un effetto passivo): utilizzabile al massimo una volta per combattimento."
         )),
    Rule("recast", re.compile(r"^fino\s+a\s+x\s+mana\s*:\s*(\d+)\s*mana$", re.I),
         lambda m: (
             "Permette di ricastare gratuitamente (0 mana) un incantesimo identico già lanciato, "
             f"purché il suo costo originale non superi {_number(m.group(1))} mana, pagando invece "
             "1 PA e 3 Energia. Utilizzabile al massimo 2 volte per combattimento; fuori dal "
             "combattimento, al massimo 1 volta all'ora."
         )),
    # "teletrasporto A (B)": teleport A metres, costing B PA, B mana and a flat
    # 1 Energia. Confirmed with the table master 2026-08-01; not derivable from
    # the data alone (no per-use frequency limit was given, unlike mod_gen).
    Rule("teletrasporto", re.compile(r"^teletrasporto\s+(\d+)\s*\(\s*(\d+)\s*\)$", re.I),
         lambda m: (
             f"Permette di teletrasportarsi di {_number(m.group(1))} "
             f"{_plural(m.group(1), 'metro', 'metri')}, al costo di "
             f"{_number(m.group(2))} PA, {_number(m.group(2))} mana e 1 Energia."
         )),
)


def curate(text: str) -> tuple[str | None, str | None]:
    """Return (rule key, rendered sentence). A `None` sentence means "keep flagged"."""
    for rule in RULES:
        if rule.pattern.fullmatch(text.strip()):
            return rule.key, rule.render(rule.pattern.fullmatch(text.strip()))
    return None, None


class Command(BaseCommand):
    help = "Scrive le regole curate in regole_speciali per gli oggetti marcati speciali (dry run di default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Scrive le modifiche invece di simularle.")
        parser.add_argument("--rule", action="append", default=[], help="Applica solo le regole indicate (ripetibile).")
        parser.add_argument("--limit", type=int, default=0, help="Ferma la scrittura dopo N oggetti.")
        parser.add_argument("--samples", type=int, default=2, help="Righe di esempio per regola nel report.")
        parser.add_argument(
            "--recurate",
            action="store_true",
            help="Ripassa anche gli oggetti già curati da questo comando, per riscriverli con la tabella aggiornata.",
        )

    def handle(self, *args, **options):
        only = set(options["rule"])
        per_rule = Counter()
        samples: dict[str, list[str]] = {}
        uncovered = Counter()
        blocked_by = Counter()
        curable: list[tuple[Oggetto, str, list[str]]] = []

        # Curated items are no longer `speciale`, so a changed rule table would
        # never reach them again. `--recurate` reopens exactly the ones this
        # command wrote — a rule the master typed by hand carries no marker and
        # is never overwritten.
        scope = Q(speciale=True) | Q(metadata__specialRulesSource=SOURCE) if options["recurate"] else Q(speciale=True)
        items = Oggetto.objects.filter(scope, modello=True, archiviato=False).order_by("id")
        for item in items:
            texts = descriptive_effects(item)
            if not texts:
                continue
            lines, blockers, keys = [], [], []
            for text in texts:
                key, sentence = curate(text)
                if key is None:
                    uncovered[text] += 1
                    blockers.append("(nessuna regola)")
                    continue
                if sentence is None or (only and key not in only):
                    blockers.append(key)
                    continue
                per_rule[key] += 1
                samples.setdefault(key, []).append(f"{text}  ->  {sentence}")
                lines.append(sentence)
                keys.append(key)
            if blockers:
                for blocker in set(blockers):
                    blocked_by[blocker] += 1
                continue
            if lines:
                curable.append((item, "\n".join(lines), keys))

        self.stdout.write(f"Oggetti speciali attivi esaminati: {items.count()}")
        self.stdout.write(f"Oggetti completamente curabili:     {len(curable)}")
        self.stdout.write("")
        self.stdout.write("--- regole applicate (occorrenze) ---")
        for key, count in per_rule.most_common():
            self.stdout.write(f"{count:5d}  {key}")
            for line in samples.get(key, [])[: options["samples"]]:
                self.stdout.write(f"         {line}")
        if blocked_by:
            self.stdout.write("")
            self.stdout.write("--- oggetti che restano in coda, per causa ---")
            for key, count in blocked_by.most_common():
                self.stdout.write(f"{count:5d}  {key}")
        if uncovered:
            self.stdout.write("")
            self.stdout.write(f"--- testi senza regola: {len(uncovered)} distinti, {sum(uncovered.values())} occorrenze ---")
            for text, count in uncovered.most_common(30):
                self.stdout.write(f"{count:5d}  {text}")

        if not options["apply"]:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Simulazione: nessuna modifica scritta. Usa --apply per confermare."))
            return

        limit = options["limit"] or len(curable)
        written = 0
        with transaction.atomic():
            for item, body, _ in curable[:limit]:
                item.regole_speciali = body
                sync_special_rules_review(item)
                item.metadata = {**item.metadata, "specialRulesSource": SOURCE}
                item.speciale = bool(compute_special_reasons(item))
                item.save(update_fields=["regole_speciali", "metadata", "speciale", "updated_at"])
                written += 1
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Scritti {written} oggetti; flag speciale ricalcolato su ciascuno."))

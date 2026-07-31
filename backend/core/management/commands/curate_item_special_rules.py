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
    # "Ponte di Mana" has no definition anywhere in the data: only the master can
    # say what the bridge actually does, so these items stay in the queue.
    Rule("ponte_di_mana", re.compile(r"^ponte\s+di\s+mana\s*:?\s*si$", re.I), lambda m: None),

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

    # --- Deliberately left in the queue --------------------------------------
    # `mod gen A (B)`: A tracks ceil(livello/2) but B matches neither rarity nor
    # level nor value, so converting would be a guess repeated 60 times.
    Rule("mod_gen", re.compile(r"^\+?\s*mod\s+gen\s*\d+\s*\(\s*\d+\s*\)$", re.I), lambda m: None),
    Rule("teletrasporto", re.compile(r"^teletrasporto\s+\d+\s*\(\s*\d+\s*\)$", re.I), lambda m: None),
    Rule("recast", re.compile(r"^fino\s+a\s+x\s+mana\s*:\s*\d+\s*mana$", re.I), lambda m: None),
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

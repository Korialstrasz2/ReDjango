"""One-off curation of the 15 "Vestiti" special items.

Unlike every other family in `curate_item_special_rules`, these items' Elder
text ("Aggiungi a effetti ...") is a compound, per-item stat combination, not
a regex-shaped family — and their `descrizione` already states the full rule
in prose (e.g. "Abbigliamento povero. -1 Personalità e Fortuna +1 Saggezza").
Most of those stats are existing structured `effects` targets, so this writes
real `effects` instead of curated prose. Two items keep a genuine text
remainder because no matching target exists in this system (see
`Builder_docs/ITEM_SPECIAL_RULES_REVIEW_GUIDE.md`).

Dry run by default; `--apply` writes. Mirrors `curate_item_special_rules`'s
own dry-run-then-apply shape.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from backend.core.item_services import sync_special_rules_review
from backend.core.item_special import compute_special_reasons
from backend.core.models import Oggetto

NO_RESIDUE_NOTE = "Nessuna regola aggiuntiva: gli effetti sono applicati automaticamente alla scheda."

# item_id -> (structured effects, leftover regole_speciali text or "" for none)
PLAN: dict[int, tuple[list[tuple[str, str, int]], str]] = {
    5269: ([("personalita", "subtract", 1), ("fortuna", "subtract", 1), ("saggezza", "add", 1)], ""),
    5270: ([("competenza.diplomazia", "subtract", 1), ("fortuna", "add", 1)], ""),
    5272: ([("competenza.furtivita", "subtract", 1), ("attacco", "subtract", 2), ("difesa", "subtract", 2),
             ("personalita", "add", 1)], ""),
    5273: ([("competenza.furtivita", "subtract", 2), ("attacco", "subtract", 4), ("difesa", "subtract", 4),
             ("competenza.diplomazia", "add", 1)], ""),
    # "fisiche e magiche" decomposed into the six damage-type resistances: no
    # generic aggregate stat exists, but several armors already combine these
    # same six targets to mean "resists everything" (e.g. Armatura Manto della
    # Tempesta, Armatura Indoril), so this is the faithful reading, not a guess.
    5274: ([("pa", "subtract", 1), ("attacco", "subtract", 3), ("difesa", "subtract", 3),
             ("res_contundente", "add", 1), ("res_taglio", "add", 1), ("res_perforante", "add", 1),
             ("res_fuoco", "add", 1), ("res_gelo", "add", 1), ("res_elettro", "add", 1)], ""),
    5275: ([("competenza.furtivita", "subtract", 4), ("attacco", "subtract", 8), ("difesa", "subtract", 8),
             ("competenza.diplomazia", "add", 1), ("personalita", "add", 2)], ""),
    5276: ([("pa", "subtract", 1), ("competenza.scalare", "add", 1), ("competenza.sopravvivenza", "add", 1),
             ("competenza.cavalcare", "add", 1), ("competenza.nuotare", "add", 1)], ""),
    5277: ([("pa", "add", 1), ("velocita", "add", 1), ("resistenza", "subtract", 1)], ""),
    5278: ([("competenza.furtivita", "add", 1), ("competenza.intimidire", "add", 1),
             ("personalita", "subtract", 1), ("competenza.diplomazia", "subtract", 1)], ""),
    5279: ([("slot_magici", "add", 1), ("slot_non_magici", "add", 1), ("competenza.furtivita", "add", 2),
             ("competenza.intimidire", "add", 2), ("competenza.diplomazia", "subtract", 4)], ""),
    # "skill fisiche (rosse)" resolved to the table master's own list: scalare,
    # manovrare veicoli, nuotare.
    5280: ([("competenza.camuffare", "add", 1), ("competenza.intimidire", "add", 1),
             ("competenza.scalare", "subtract", 1), ("competenza.manovrare_veicoli", "subtract", 1),
             ("competenza.nuotare", "subtract", 1)], ""),
    5281: ([("slot_non_magici", "add", 1), ("difesa", "add", 2), ("velocita", "subtract", 1),
             ("pa", "subtract", 1)], ""),
    5282: ([("res_gelo", "add", 1), ("res_fuoco", "subtract", 1), ("res_elettro", "subtract", 1)], ""),
    5283: ([("res_fuoco", "add", 1), ("res_gelo", "subtract", 1), ("res_elettro", "subtract", 1)], ""),
    5284: ([("res_elettro", "add", 1), ("res_gelo", "subtract", 1), ("res_fuoco", "subtract", 1)], ""),
}


class Command(BaseCommand):
    help = "Scrive gli effetti strutturati per i 15 oggetti Vestiti (dry run di default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Scrive le modifiche invece di simularle.")

    def handle(self, *args, **options):
        written = 0
        with transaction.atomic():
            for item_id, (effects, residue) in PLAN.items():
                item = Oggetto.objects.select_for_update().get(pk=item_id)
                item.effects = [
                    {"target": target, "operation": op, "value": value, "source": "manual_curation"}
                    for target, op, value in effects
                ]
                item.regole_speciali = residue or NO_RESIDUE_NOTE
                sync_special_rules_review(item)
                item.speciale = bool(compute_special_reasons(item))
                self.stdout.write(
                    f"#{item.id} {item.nome} -> speciale={item.speciale}, "
                    f"effetti strutturati={len(item.effects)}"
                )
                if options["apply"]:
                    item.save(update_fields=["effects", "regole_speciali", "metadata", "speciale", "updated_at"])
                    written += 1
            if not options["apply"]:
                transaction.set_rollback(True)
        self.stdout.write("")
        if options["apply"]:
            self.stdout.write(self.style.SUCCESS(f"Scritti {written} oggetti."))
        else:
            self.stdout.write(self.style.WARNING("Simulazione: nessuna modifica scritta. Usa --apply per confermare."))

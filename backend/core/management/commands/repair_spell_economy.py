from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.db import transaction

from backend.core.spell_economy_repair import repair_spell_economy


class Command(BaseCommand):
    help = (
        "Rimuove il doppio conteggio dei bonus magici importati da Elder: le coppie "
        "Ordine/Caos collassate sullo stesso bersaglio e gli effetti manuali che "
        "ripetono un totale già fornito dalle abilità del personaggio."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Applica la riparazione. Senza questo flag esegue solo il dry-run.")

    def handle(self, *args, **options):
        apply = options["apply"]
        with transaction.atomic():
            summary = repair_spell_economy(apply=apply)
            if not apply:
                transaction.set_rollback(True)
        summary["mode"] = "apply" if apply else "dry-run"
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))

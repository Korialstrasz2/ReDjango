from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.db import transaction

from backend.core.legacy_item_import import repair_imported_item_effects


class Command(BaseCommand):
    help = "Backfill safely convertible Elder item effects without replacing the catalog."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the missing structured effects.")

    def handle(self, *args, **options):
        apply = options["apply"]
        with transaction.atomic():
            summary = repair_imported_item_effects(apply=apply)
            if not apply:
                transaction.set_rollback(True)
        summary["mode"] = "apply" if apply else "dry-run"
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))

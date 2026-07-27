from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from backend.core.legacy_item_import import ASSIGNMENT_REPLACEMENTS, apply_plan, read_plan


class Command(BaseCommand):
    help = "Dry-run or replace the ReDjango item catalog with The Elder Django objects."

    def add_arguments(self, parser):
        default = Path(settings.BASE_DIR).parent / "firstDjango" / "the_elder_django" / "db.sqlite3"
        parser.add_argument("--source-db", type=Path, default=default)
        parser.add_argument("--apply", action="store_true", help="Apply the atomic catalog replacement.")

    def handle(self, *args, **options):
        try:
            plan = read_plan(options["source_db"])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        summary = {
            "mode": "apply" if options["apply"] else "dry-run",
            "source": str(options["source_db"]),
            "imported": len(plan.rows),
            "skippedPlaceholders": len(plan.skipped),
            "typeOptions": {str(key): len(value) for key, value in plan.type_options.items()},
            "convertedEffects": plan.converted_effects,
            "retainedEffects": plan.retained_effects,
            "specialItems": plan.special_items,
            "remappedAssignments": len(plan.assignments),
            "assignmentReplacements": sorted({
                f"{entry['oldName']} -> {plan.source_names[entry.get('sourceId') or ASSIGNMENT_REPLACEMENTS[entry['oldName']]]}"
                for entry in plan.assignments
            }),
        }
        if options["apply"]:
            summary.update(apply_plan(plan))
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))

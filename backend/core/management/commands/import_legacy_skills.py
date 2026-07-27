from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from backend.core.legacy_skill_import import (
    apply_import_run,
    build_import_run,
    validate_import_write_path,
    write_import_artifacts,
)


class Command(BaseCommand):
    help = (
        "Prepara o applica l'importazione massiva delle Skill da the_elder_django. "
        "Senza --apply non scrive Skill, incantesimi, prerequisiti o ownership."
    )

    def add_arguments(self, parser):
        default_source = (
            Path(settings.BASE_DIR).parent
            / "firstDjango"
            / "the_elder_django"
            / "db.sqlite3"
        )
        parser.add_argument("--source", default=str(default_source), help="Percorso del DB SQLite legacy.")
        parser.add_argument(
            "--output-dir",
            default=str(Path(settings.BASE_DIR) / "Builder_docs" / "skill_migration_output"),
            help="Cartella dei report JSON di staging.",
        )
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", help="Genera e valida soltanto i report (default).")
        mode.add_argument("--apply", action="store_true", help="Importa soltanto la coda auto_import.")
        parser.add_argument(
            "--no-artifacts",
            action="store_true",
            help="Non scrive i report JSON; utile nei test automatici.",
        )
        parser.add_argument(
            "--validate-write-path",
            action="store_true",
            help="Esegue l'intero auto-import in una transazione destinata al rollback.",
        )

    def handle(self, *args, **options):
        source_path = Path(options["source"])
        if not source_path.is_file():
            raise CommandError(f"Database legacy non trovato: {source_path}")
        run = build_import_run(source_path)
        if not options["no_artifacts"]:
            paths = write_import_artifacts(run, Path(options["output_dir"]))
            self.stdout.write(f"Report scritti in {paths[0].parent}")
        counts = run.summary["decisionCounts"]
        self.stdout.write(
            " | ".join(
                (
                    f"Sorgente: {run.summary['sourceSkillCount']}",
                    f"Auto-import: {counts.get('auto_import', 0)}",
                    f"Da rivedere: {counts.get('needs_review', 0)}",
                    f"Intervento admin: {counts.get('admin_required', 0)}",
                    f"Incantesimi strutturati: {run.summary['spellCount']}",
                )
            )
        )
        if not options["apply"]:
            if options["validate_write_path"]:
                validated = validate_import_write_path(run)
                self.stdout.write(
                    f"Percorso di scrittura validato e annullato: {validated['imported']} Skill; "
                    f"seconda esecuzione idempotente: {validated['idempotentUnchanged']} invariate."
                )
            self.stdout.write(
                self.style.WARNING(
                    "DRY-RUN: nessuna Skill, ownership o risorsa del personaggio è stata modificata."
                )
            )
            return
        result = apply_import_run(run)
        from backend.core.skill_management_services import reconcile_legacy_skill_reviews

        review_result = reconcile_legacy_skill_reviews(run)
        self.stdout.write(
            self.style.SUCCESS(
                f"Importate {result['imported']} Skill; "
                f"escluse {result['skippedForReview']} Skill da rivedere; "
                f"coda persistente aggiornata a {review_result['queued']} revisioni; "
                f"sospese {result['reviewSkillsSuspended']} vecchie copie non più importabili; "
                f"archiviate {result['pocSkillsArchived']} POC. Ownership importate: 0."
            )
        )

from pathlib import Path
from tempfile import mkdtemp

from django.core.management.base import BaseCommand, CommandError

from backend.media_library.legacy_unit_portraits import (
    PortraitImportError,
    apply_staged_portraits,
    discover_portrait_candidates,
    stage_portrait_candidates,
)


DEFAULT_LEGACY_ROOT = Path(r"C:\Users\alexo\PycharmProjects\firstDjango\the_elder_django")
DEFAULT_SOURCE_DIRECTORY = (
    DEFAULT_LEGACY_ROOT / "django_slim" / "static" / "media" / "images" / "pgs"
)


class Command(BaseCommand):
    help = (
        "Prepara, converte in WebP e collega alle Unit i ritratti NPC di The Elder Django. "
        "Senza --apply crea soltanto staging e manifest."
    )

    def add_arguments(self, parser):
        parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIRECTORY)
        parser.add_argument(
            "--legacy-database",
            type=Path,
            default=DEFAULT_LEGACY_ROOT / "db.sqlite3",
        )
        parser.add_argument("--staging-dir", type=Path)
        parser.add_argument("--expected-count", type=int, default=131)
        parser.add_argument("--quality", type=int, default=70)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument(
            "--allow-partial",
            action="store_true",
            help="Con --apply importa i ritratti validi e lascia scollegate le Unit bloccate.",
        )

    def handle(self, *args, **options):
        quality = int(options["quality"])
        if not 1 <= quality <= 100:
            raise CommandError("--quality deve essere compreso tra 1 e 100.")
        staging_directory = options["staging_dir"]
        if staging_directory is None:
            staging_directory = Path(mkdtemp(prefix="redjango-elder-unit-portraits-"))
        else:
            staging_directory = staging_directory.resolve()
            staging_directory.mkdir(parents=True, exist_ok=True)

        try:
            candidates = discover_portrait_candidates(
                options["source_dir"].resolve(),
                options["legacy_database"].resolve(),
                expected_count=int(options["expected_count"]),
            )
            manifest = stage_portrait_candidates(
                candidates,
                staging_directory,
                quality=quality,
            )
            summary = manifest["summary"]
            self.stdout.write(
                "Unit: {units}; corrispondenze: {matched}; WebP validati: {validated}; "
                "bloccati: {blocked}; gruppi contenuto duplicato: {duplicateContentGroups}.".format(
                    **summary
                )
            )
            self.stdout.write(f"Manifest: {manifest['manifestPath']}")
            if summary["blocked"]:
                blocked = [
                    f"{entry['unitName']} ({', '.join(entry['blockers'])})"
                    for entry in manifest["entries"]
                    if entry["blockers"]
                ]
                self.stdout.write(self.style.ERROR("Bloccanti: " + "; ".join(blocked)))
                if options["apply"] and not options["allow_partial"]:
                    raise CommandError(
                        "Applicazione annullata: risolvere tutti i ritratti bloccati e rieseguire."
                    )
            if not options["apply"]:
                self.stdout.write(
                    self.style.WARNING(
                        "Dry run completato: nessun record o file media ReDjango è stato modificato."
                    )
                )
                return
            counts = apply_staged_portraits(
                manifest,
                allow_partial=bool(options["allow_partial"]),
            )
        except PortraitImportError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            self.style.SUCCESS(
                "Importazione completata: "
                f"{counts['created']} creati, {counts['updated']} aggiornati, "
                f"{counts['reused']} riutilizzati, {counts['linked']} Unit collegate, "
                f"{counts['skipped']} bloccati lasciati invariati."
            )
        )

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from backend.lore.legacy_import import DEFAULT_SOURCE_ROOT, LoreImporter, SOURCE_CAMPAIGN_NAME


class Command(BaseCommand):
    help = f"Importa fazioni, reputazione ed eventi Elder della campagna '{SOURCE_CAMPAIGN_NAME}' in backend.lore."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=str, default=str(DEFAULT_SOURCE_ROOT))
        parser.add_argument("--apply", action="store_true", help="Applica l'importazione. Senza questo flag esegue solo il dry-run.")

    def handle(self, *args, **options):
        source_root = Path(options["source"]).resolve()
        if not (source_root / "db.sqlite3").is_file():
            raise CommandError(f"Database Elder non trovato in {source_root}")

        importer = LoreImporter(source_root)
        try:
            report = importer.preview() if not options["apply"] else importer.apply()
        finally:
            importer.close()

        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        if options["apply"]:
            self.stdout.write(self.style.SUCCESS("Importazione lore completata."))
        else:
            self.stdout.write(self.style.WARNING("DRY-RUN: usa --apply per importare fazioni, relazioni, eventi e personaggi."))

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from backend.core.legacy_names_import import import_legacy_names, read_legacy_name_rows


class Command(BaseCommand):
    help = "Importa i bacini di nomi Elder (GroupNames) in NomiRazzeInfo."

    def add_arguments(self, parser):
        default_source = Path(settings.BASE_DIR).parent / "firstDjango" / "the_elder_django" / "db.sqlite3"
        parser.add_argument("--source", default=str(default_source), help="Percorso del database SQLite Elder.")
        parser.add_argument("--apply", action="store_true", help="Applica l'importazione; senza questo flag esegue solo il controllo.")

    def handle(self, *args, **options):
        source = Path(options["source"])
        if not source.is_file():
            raise CommandError(f"Database Elder non trovato: {source}")
        rows = read_legacy_name_rows(source)
        races = sorted({row["race"] for row in rows if row["race"]})
        self.stdout.write(f"Culture leggibili: {len(rows)} | razze: {len(races)}")
        self.stdout.write(", ".join(races))
        empty = [row["name"] for row in rows if not row["names_male"] and not row["names_female"]]
        if empty:
            self.stdout.write(self.style.WARNING(f"Culture senza nomi: {', '.join(empty)}"))
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("DRY-RUN: usa --apply per importare i bacini."))
            return
        result = import_legacy_names(source)
        self.stdout.write(
            self.style.SUCCESS(
                f"Import completato: {result['cultures']} culture "
                f"({result['created']} create, {result['updated']} aggiornate, "
                f"{result['renamed']} rinominate) su {result['races']} razze."
            )
        )

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from backend.core.legacy_race_import import import_legacy_races, read_legacy_race_rows


class Command(BaseCommand):
    help = "Importa la guida Razze e converte EffettiSbloccabili/Attivabile in abilità razziali ReDjango."

    def add_arguments(self, parser):
        default_source = Path(settings.BASE_DIR).parent / "firstDjango" / "the_elder_django" / "db.sqlite3"
        parser.add_argument("--source", default=str(default_source), help="Percorso del database SQLite Elder.")
        parser.add_argument("--apply", action="store_true", help="Applica l'importazione; senza questo flag esegue solo il controllo.")

    def handle(self, *args, **options):
        source = Path(options["source"])
        if not source.is_file():
            raise CommandError(f"Database Elder non trovato: {source}")
        guide, rows = read_legacy_race_rows(source)
        self.stdout.write(f"Guida Razze: {len(guide)} caratteri | mapping razza/sottorazza: {len(rows)} righe")
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("DRY-RUN: usa --apply per importare guida, famiglie e abilità."))
            return
        result = import_legacy_races(source)
        self.stdout.write(
            self.style.SUCCESS(
                f"Import completato: {result['guide']} guida, {result['families']} famiglie, "
                f"{result['skills']} abilità, {result['skipped']} righe escluse, "
                f"{result['synchronized']} personaggi sincronizzati."
            )
        )

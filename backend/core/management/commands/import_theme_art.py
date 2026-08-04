from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from backend.core.theme_art_import import ThemeArtImportError, import_theme_art


class Command(BaseCommand):
    help = "Importa gli sfondi dei temi da una cartella di PNG «{slug}-{superficie}.png»."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=str(Path.home() / "Downloads"),
            help="Cartella dei PNG sorgente (default: Downloads).",
        )
        parser.add_argument(
            "--theme",
            action="append",
            dest="themes",
            help="Slug del tema da importare (ripetibile; default: midnight e arcane).",
        )

    def handle(self, *args, **options):
        source = Path(options["source"])
        themes = tuple(options["themes"] or ["midnight", "arcane"])

        try:
            report = import_theme_art(source, themes)
        except ThemeArtImportError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Temi: {', '.join(themes)} | sfondi nuovi: {report.imported} | "
                f"aggiornati: {report.updated} | mancanti: {len(report.missing)}"
            )
        )
        if report.missing:
            self.stdout.write(self.style.WARNING("Non trovati: " + ", ".join(report.missing)))

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from backend.core.legacy_race_media_import import import_race_media, plan_race_media


class Command(BaseCommand):
    help = "Importa ritratti (in WebP) e clip del generatore nomi dal progetto Elder."

    def add_arguments(self, parser):
        default_source = Path(settings.BASE_DIR).parent / "firstDjango" / "the_elder_django"
        parser.add_argument("--source", default=str(default_source), help="Cartella radice del progetto Elder.")
        parser.add_argument("--apply", action="store_true", help="Applica l'importazione; senza questo flag esegue solo il controllo.")

    def handle(self, *args, **options):
        source = Path(options["source"])
        if not source.is_dir():
            raise CommandError(f"Progetto Elder non trovato: {source}")

        plan = plan_race_media(source)
        if not plan:
            raise CommandError("Nessuna cultura in NomiRazzeInfo: esegui prima import_legacy_names --apply.")
        races = {entry["race"] for entry in plan.values() if entry["racePortrait"] is not None}
        images = sum(1 for entry in plan.values() for key in ("image_m", "image_f") if entry[key] is not None)
        clips = sum(1 for entry in plan.values() for key in ("clip_m", "clip_f") if entry[key] is not None)
        self.stdout.write(f"Culture: {len(plan)} | ritratti di razza: {len(races)} | ritratti cultura: {images} | clip: {clips}")

        gaps = [
            f"{name} ({', '.join(key for key in ('image_m', 'image_f') if entry[key] is None)})"
            for name, entry in plan.items()
            if entry["image_m"] is None or entry["image_f"] is None
        ]
        if gaps:
            self.stdout.write(self.style.WARNING(f"Senza ritratto: {'; '.join(gaps)}"))

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("DRY-RUN: usa --apply per convertire e importare."))
            return

        report = import_race_media(source)
        self.stdout.write(
            self.style.SUCCESS(
                f"Import completato: {report.races} ritratti di razza, {report.culture_images} ritratti cultura, "
                f"{report.clips} clip, {report.linked} culture collegate."
            )
        )
        if report.missing:
            self.stdout.write(self.style.WARNING(f"Mancanti: {'; '.join(report.missing)}"))

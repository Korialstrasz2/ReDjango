import mimetypes
import sqlite3
from collections import Counter
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from backend.media_library.models import ImageCategory, UploadedImage


DEFAULT_LEGACY_ROOT = Path(r"C:\Users\alexo\PycharmProjects\firstDjango\the_elder_django")
SOURCE = "elder_django"

FOLDER_MAPPING = {
    "Città": ("ambientazioni", "Città"),
    "Dungeon": ("mappe", "Dungeon"),
    "Globali": ("mappe", "Globali"),
    "Lore": ("personaggi", "Lore"),
    "Momenti Epici": ("scene-di-gioco", "Momenti Epici"),
    "Personaggi": ("personaggi", "Personaggi"),
    "Regioni": ("mappe", "Regioni"),
    "extra": ("scene-di-gioco", "extra"),
    "": ("ambientazioni", "Città"),
}


class Command(BaseCommand):
    help = "Importa le immagini UploadedImage di The Elder Django in ReDjango."

    def add_arguments(self, parser):
        parser.add_argument("--legacy-root", type=Path, default=DEFAULT_LEGACY_ROOT)
        parser.add_argument("--apply", action="store_true", help="Esegue la copia; senza questo flag produce solo il report.")

    def handle(self, *args, **options):
        legacy_root = options["legacy_root"].resolve()
        database = legacy_root / "db.sqlite3"
        media_root = legacy_root / "media"
        if not database.is_file() or not media_root.is_dir():
            raise CommandError("Archivio Elder non trovato: sono necessari db.sqlite3 e media/.")

        categories = {category.slug: category for category in ImageCategory.objects.filter(archived_at__isnull=True)}
        missing_categories = sorted({slug for slug, _ in FOLDER_MAPPING.values()} - categories.keys())
        if missing_categories:
            raise CommandError(f"Categorie ReDjango mancanti: {', '.join(missing_categories)}")

        connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                "SELECT id, title, folder, image, thumbnail, parent_id "
                "FROM django_slim_uploadedimage ORDER BY id"
            ).fetchall()
        finally:
            connection.close()

        source_files = {}
        for row in rows:
            image_path = media_root / row["image"]
            thumbnail_path = media_root / row["thumbnail"]
            if not row["image"] or not image_path.is_file():
                raise CommandError(f"File originale Elder mancante per immagine #{row['id']}: {row['image']}")
            if row["thumbnail"] and not thumbnail_path.is_file():
                raise CommandError(f"Miniatura Elder mancante per immagine #{row['id']}: {row['thumbnail']}")
            source_files[row["id"]] = (image_path, thumbnail_path if row["thumbnail"] else None)

        legacy_ids = [row["id"] for row in rows]
        existing_ids = set(
            UploadedImage.objects.filter(source=SOURCE, metadata__legacyId__in=legacy_ids)
            .values_list("metadata__legacyId", flat=True)
        )
        pending = [row for row in rows if row["id"] not in existing_ids]
        mapping_counts = Counter(FOLDER_MAPPING.get(row["folder"], ("altro", row["folder"] or "Archivio"))[0] for row in pending)
        self.stdout.write(f"Elder records: {len(rows)}; già importati: {len(existing_ids)}; da importare: {len(pending)}")
        self.stdout.write("Categorie previste: " + ", ".join(f"{slug}={count}" for slug, count in sorted(mapping_counts.items())))
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Dry run: nessun file o record è stato creato. Rieseguire con --apply."))
            return

        imported = {}
        for row in pending:
            category_slug, group = FOLDER_MAPPING.get(row["folder"], ("altro", row["folder"] or "Archivio"))
            image_path, thumbnail_path = source_files[row["id"]]
            title = row["title"].strip() if row["title"] else image_path.stem
            asset = UploadedImage(
                title=title,
                folder=category_slug,
                usage_type="scene" if category_slug == "scene-di-gioco" else "generic",
                category=categories[category_slug],
                group=group,
                source=SOURCE,
                metadata={
                    "legacyId": row["id"],
                    "legacyFolder": row["folder"],
                    "legacyImagePath": row["image"],
                    "legacyThumbnailPath": row["thumbnail"],
                    "originalName": image_path.name,
                    "sizeBytes": image_path.stat().st_size,
                    "mimeType": mimetypes.guess_type(image_path.name)[0] or "image/*",
                },
            )
            with image_path.open("rb") as image_file:
                asset.file.save(image_path.name, File(image_file), save=False)
            if thumbnail_path:
                with thumbnail_path.open("rb") as thumbnail_file:
                    asset.thumbnail.save(thumbnail_path.name, File(thumbnail_file), save=False)
            asset.save()
            imported[row["id"]] = asset

        all_imported = {
            asset.metadata.get("legacyId"): asset
            for asset in UploadedImage.objects.filter(source=SOURCE)
            if isinstance(asset.metadata, dict) and asset.metadata.get("legacyId")
        }
        linked_versions = 0
        for row in rows:
            if row["parent_id"] and row["id"] in imported:
                parent = all_imported.get(row["parent_id"])
                if not parent:
                    raise CommandError(f"Versione Elder #{row['id']} senza padre importato #{row['parent_id']}.")
                asset = imported[row["id"]]
                asset.parent = parent
                asset.save(update_fields=["parent", "updated_at"])
                linked_versions += 1

        self.stdout.write(self.style.SUCCESS(f"Importate {len(imported)} immagini e {linked_versions} relazioni di versione."))

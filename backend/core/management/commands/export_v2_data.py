from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from backend.core.v2_registry import V2_MODEL_LABELS, get_v2_models


class Command(BaseCommand):
    help = "Export v2 database records as a Django JSON fixture."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            "-o",
            default="",
            help="Output JSON path. Defaults to Builder_docs/exports/v2_export_<timestamp>.json.",
        )
        parser.add_argument(
            "--model",
            action="append",
            choices=V2_MODEL_LABELS,
            help="Restrict export to one v2 model label. Can be repeated.",
        )
        parser.add_argument("--indent", type=int, default=2, help="JSON indentation level.")

    def handle(self, *args, **options):
        selected_labels = options.get("model") or None
        models = get_v2_models(selected_labels)
        objects = []
        counts = {}

        for model in models:
            label = model._meta.label
            queryset = model.objects.all().order_by("pk")
            count = queryset.count()
            counts[label] = count
            objects.extend(queryset)

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        output = Path(options["output"]) if options["output"] else settings.BASE_DIR / "Builder_docs" / "exports" / f"v2_export_{timestamp}.json"
        if output.suffix.lower() != ".json":
            raise CommandError("Export output must be a .json file.")
        output.parent.mkdir(parents=True, exist_ok=True)

        data = serializers.serialize("json", objects, indent=options["indent"])
        output.write_text(data, encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(f"Exported {len(objects)} records to {output}"))
        for label, count in counts.items():
            self.stdout.write(f"{label}: {count}")

import json

from django.conf import settings
from django.core.management.base import BaseCommand

from backend.api_v1 import api


class Command(BaseCommand):
    help = "Esporta lo schema OpenAPI v1 usato per generare i tipi TypeScript della SPA."

    def handle(self, *args, **options):
        output = settings.BASE_DIR / "Builder_docs" / "openapi-v1.json"
        output.write_text(json.dumps(api.get_openapi_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Schema OpenAPI esportato: {output}"))

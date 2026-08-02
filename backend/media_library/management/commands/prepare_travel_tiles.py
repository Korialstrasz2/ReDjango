from django.core.management.base import BaseCommand, CommandError

from backend.media_library.models import DatiMappa
from backend.media_library.travel_tiles import ensure_travel_tiles


class Command(BaseCommand):
    help = "Prepara le tile versionate delle mappe globali senza modificare gli originali."

    def add_arguments(self, parser):
        parser.add_argument("--map-id", type=int, help="Prepara soltanto la mappa indicata.")

    def handle(self, *args, **options):
        maps = DatiMappa.objects.select_related("image").filter(
            tipo="globale",
            archived_at__isnull=True,
        ).order_by("id")
        if options.get("map_id"):
            maps = maps.filter(pk=options["map_id"])
            if not maps.exists():
                raise CommandError("Mappa globale non trovata.")
        for travel_map in maps:
            self.stdout.write(f"Preparo {travel_map.pk} · {travel_map.nome}...")
            manifest = ensure_travel_tiles(travel_map)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {manifest['width']}x{manifest['height']} · livello {manifest['maxLevel']} · "
                    f"{manifest['byteSize']} byte"
                )
            )

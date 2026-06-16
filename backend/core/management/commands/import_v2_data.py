from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class DryRunRollback(Exception):
    pass


class Command(BaseCommand):
    help = "Import v2 database records from a Django JSON fixture."

    def add_arguments(self, parser):
        parser.add_argument("fixture", help="Path to a JSON fixture created by export_v2_data.")
        parser.add_argument("--dry-run", action="store_true", help="Validate the import and roll it back.")
        parser.add_argument("--database", default="default", help="Database alias to import into.")

    def handle(self, *args, **options):
        fixture = Path(options["fixture"])
        if not fixture.exists():
            raise CommandError(f"Fixture does not exist: {fixture}")
        if fixture.suffix.lower() != ".json":
            raise CommandError("Only .json fixtures are supported.")

        try:
            with transaction.atomic(using=options["database"]):
                call_command("loaddata", str(fixture), database=options["database"], verbosity=options["verbosity"])
                if options["dry_run"]:
                    raise DryRunRollback
        except DryRunRollback:
            self.stdout.write(self.style.WARNING(f"Dry run succeeded and was rolled back: {fixture}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Imported v2 fixture: {fixture}"))

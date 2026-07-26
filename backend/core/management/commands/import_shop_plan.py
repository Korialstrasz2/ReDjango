from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from backend.core.models import Giocatore
from backend.market.shop_plan import apply_batch, load_plan, validate_plan


class Command(BaseCommand):
    help = "Dry-run or atomically import a reviewed Mercato shop plan."

    def add_arguments(self, parser):
        parser.add_argument("--plan", type=Path, required=True)
        parser.add_argument("--apply", action="store_true", help="Write shops after a clean dry-run.")
        parser.add_argument("--giocatore-id", type=int, required=True)
        parser.add_argument("--batch-size", type=int, default=25)
        parser.add_argument("--receipt-dir", type=Path, default=Path(settings.BASE_DIR) / "shop-import-receipts")
        parser.add_argument("--no-backup", action="store_true", help="Skip the SQLite backup (not recommended).")

    def handle(self, *args, **options):
        if not 1 <= options["batch_size"] <= 25:
            raise CommandError("--batch-size deve essere compreso tra 1 e 25.")
        try:
            records = load_plan(options["plan"])
            giocatore = Giocatore.objects.get(pk=options["giocatore_id"])
        except (ValueError, Giocatore.DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
        report = validate_plan(records)
        result = {"mode": "apply" if options["apply"] else "dry-run", "records": len(records), **report.payload()}
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        if report.errors:
            raise CommandError("Il dry-run contiene conflitti o record non validi.")
        if not options["apply"]:
            return
        if not options["no_backup"]:
            database = Path(settings.DATABASES["default"]["NAME"])
            backup_dir = Path(settings.BASE_DIR) / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / f"shop-import-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite3"
            shutil.copy2(database, backup)
            self.stdout.write(f"Backup: {backup}")
        created = report.created
        receipt_dir = options["receipt_dir"]
        receipt_dir.mkdir(parents=True, exist_ok=True)
        for index in range(0, len(created), options["batch_size"]):
            batch = created[index:index + options["batch_size"]]
            try:
                entries = apply_batch(None, giocatore, batch)
            except RuntimeError as exc:
                raise CommandError(f"Batch {index // options['batch_size'] + 1} annullato: {exc}") from exc
            receipt = {"batch": index // options["batch_size"] + 1, "created": entries, "createdAt": datetime.now().astimezone().isoformat()}
            (receipt_dir / f"batch-{receipt['batch']:03d}.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(json.dumps(receipt, ensure_ascii=False))

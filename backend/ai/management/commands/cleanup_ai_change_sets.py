from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from backend.ai.changes.cleanup import cleanup_abandoned_change_sets


class Command(BaseCommand):
    help = "Scade le proposte Master AI abbandonate e rimuove soltanto le vecchie bozze vuote."

    def add_arguments(self, parser):
        parser.add_argument("--review-days", type=int, default=14, help="Giorni prima di marcare draft/ready come expired.")
        parser.add_argument("--empty-days", type=int, default=2, help="Giorni prima di eliminare una bozza vuota.")
        parser.add_argument("--dry-run", action="store_true", help="Mostra i conteggi senza modificare il database.")

    def handle(self, *args, **options):
        review_days = options["review_days"]
        empty_days = options["empty_days"]
        if review_days < 1 or empty_days < 1:
            raise CommandError("Le finestre di conservazione devono essere almeno di un giorno.")
        result = cleanup_abandoned_change_sets(
            review_days=review_days,
            empty_days=empty_days,
            dry_run=options["dry_run"],
        )
        prefix = "DRY RUN · " if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}bozze vuote eliminate: {result['deletedEmptyDrafts']}; "
                f"proposte scadute: {result['expiredProposals']}."
            )
        )

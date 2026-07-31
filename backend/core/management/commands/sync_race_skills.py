"""Riallinea le abilità razziali in banca dati con RACE_CATALOG."""

from django.core.management.base import BaseCommand

from backend.characters.models import Personaggio
from backend.characters.services.refresh_personaggio import refresh_personaggio
from backend.core.race_skill_sync import (
    plan_race_skill_sync,
    sync_race_guide_text,
    sync_race_skills,
)
from backend.core.skill_services import sync_automatic_racial_skills


class Command(BaseCommand):
    help = (
        "Proietta i bonus di RACE_CATALOG sulle abilità razziali e, con --apply, "
        "ricalcola le schede dei personaggi che le possiedono."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Scrive le modifiche; senza questo flag mostra soltanto cosa cambierebbe.",
        )

    def handle(self, *args, **options):
        planned = plan_race_skill_sync()
        pending = [entry for entry in planned if entry["status"] == "da aggiornare"]
        unmatched = [entry for entry in planned if entry["status"] == "senza voce di catalogo"]

        self.stdout.write(
            f"Abilità razziali: {len(planned)} | da aggiornare {len(pending)} | "
            f"invariate {len(planned) - len(pending) - len(unmatched)} | senza catalogo {len(unmatched)}"
        )
        for entry in unmatched:
            self.stdout.write(self.style.WARNING(f"  senza voce di catalogo: {entry['skill'].nome}"))

        if not options["apply"]:
            for entry in pending[:20]:
                passives = len(entry["passives"] or [])
                actions = len(entry["actions"] or [])
                self.stdout.write(f"  {entry['skill'].nome}: {passives} passivo/i, {actions} nota/e")
            if len(pending) > 20:
                self.stdout.write(f"  … e altre {len(pending) - 20}")
            self.stdout.write(self.style.WARNING("DRY-RUN: usa --apply per scrivere."))
            return

        result = sync_race_skills()
        guides = sync_race_guide_text()
        if guides:
            self.stdout.write(f"Guida Razze corretta: {guides}")
        characters = list(
            Personaggio.objects.filter(skill_sbloccate__metadata__source="race.auto").distinct()
        )
        for character in characters:
            sync_automatic_racial_skills(character)
            refresh_personaggio(character)
        self.stdout.write(
            self.style.SUCCESS(
                f"Abilità aggiornate: {result['updated']} | invariate: {result['unchanged']} | "
                f"senza catalogo: {result['unmatched']} | schede ricalcolate: {len(characters)}"
            )
        )

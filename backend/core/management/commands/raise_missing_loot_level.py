"""One-off: give the 20 no-lv_loot catalog items a high floor instead of none.

These items were blocked from every shop by `noLootLevel` (blank/unparseable
`lv_loot`), a data-entry gap rather than a deliberate exclusion. Per the table
master, the fix is to make them technically shop-eligible but rare: rarita=5
(the highest non-Unico tier) and lv_loot="10" (only rollable at the top loot
level), so they can appear without flooding low-level shops.

Excludes 7 items that share the same `noLootLevel` reason but are rarita=Unico
placeholder combat-mode entries, not real gear (Mani Nude, Natura 1/2/3 and
their "(cont)" duplicates) — raising their rarity would strip their Unico
status, a separate decision flagged to the table master rather than assumed.

Dry run by default; `--apply` writes. Mirrors the other one-off commands in
this app.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from backend.core.models import Oggetto

ITEM_IDS = (
    5927, 5924, 5926, 5922, 5928, 5923,  # Sanguine "Extra" flavour items
    5828, 5829,  # Gunblade Vetro con Pistola Ebano, Moschetto...(Touka)
    5789,  # Scudo Imperiale
    5674, 5675,  # Anello del desiderio, Orecchino della connessione
    5844, 5845,  # Vino Sangue di Sanguine, Liquore Lacrime di Sanguine
    5115, 5116,  # Sacca magica 4, Borsa magica
    5872,  # Lingotto massiccio di oro
    5676,  # Gemma della bestia
    5282,  # Vestiti caldi
    5827,  # Pergamena di disatomizzazione
    5869,  # Dado Fortunato di Sanguine
)


class Command(BaseCommand):
    help = "Imposta rarita=5, lv_loot='10' sui 20 oggetti senza lv_loot (dry run di default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Scrive le modifiche invece di simularle.")

    def handle(self, *args, **options):
        written = 0
        with transaction.atomic():
            for item_id in ITEM_IDS:
                item = Oggetto.objects.select_for_update().get(pk=item_id)
                before = f"rarita={item.rarita}, lv_loot={item.lv_loot!r}"
                item.rarita = 5
                item.lv_loot = "10"
                self.stdout.write(f"#{item.id} {item.nome} -> {before} => rarita=5, lv_loot='10'")
                if options["apply"]:
                    item.save(update_fields=["rarita", "lv_loot", "updated_at"])
                    written += 1
            if not options["apply"]:
                transaction.set_rollback(True)
        self.stdout.write("")
        if options["apply"]:
            self.stdout.write(self.style.SUCCESS(f"Scritti {written} oggetti."))
        else:
            self.stdout.write(self.style.WARNING("Simulazione: nessuna modifica scritta. Usa --apply per confermare."))

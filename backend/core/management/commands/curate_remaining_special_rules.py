"""One-off curation of the last 30 true one-off "speciale" items (2026-08-01).

Unlike the regex families in `curate_item_special_rules`, none of these share
a repeatable Elder shorthand across items — each needed its own field-by-field
read (`effetto_N`, `descrizione`) and, for the drink/drug family, a matching
`EffettoPreset` (see `backend/characters/effect_preset_defaults.py`, category
"Bevande") created alongside this pass. Presets carry the mechanics; this
command only writes the short `regole_speciali` pointer that lets a human (or
`sync_special_rules_review`) find them, since there is no FK from `Oggetto` to
`EffettoPreset`. See `Builder_docs/ITEM_SPECIAL_RULES_REVIEW_GUIDE.md`.

Dry run by default; `--apply` writes. Mirrors `curate_vestiti_effects`'s own
dry-run-then-apply shape.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from backend.core.item_services import sync_special_rules_review
from backend.core.item_special import compute_special_reasons
from backend.core.models import Oggetto

# item_id -> regole_speciali text
PLAN: dict[int, str] = {
    # --- Trivial one-offs -----------------------------------------------------
    5271: "Puro abbigliamento, senza alcun effetto meccanico.",
    5059: (  # Veste da Bardo (1)
        "Iconica: capo d'abbigliamento riconoscibile e distintivo, un vezzo "
        "scenico senza effetto meccanico oltre a quelli già strutturati."
    ),

    # --- Narrated one-offs, already near-complete Italian prose ---------------
    5674: (  # Anello del desiderio
        "Concede un piccolo desiderio per sessione (potenza a discrezione del "
        "master): costa 5 PA e 1 punto stanchezza."
    ),
    5675: (  # Orecchino della connessione
        "Si sintonizza con un altro Orecchino della connessione: chi lo indossa "
        "può evocare per un minuto, come semi-fantasma, la persona che indossa "
        "l'altro orecchino. L'evocato può interagire col mondo (castare, "
        "parlare, vedere) ma non può portare né raccogliere oggetti. Costa 10 "
        "PA e 10 Energia."
    ),
    5676: (  # Gemma della bestia
        "Per 1 ora ti trasformi in una bestia di livello pari al tuo, a tua "
        "scelta; la durata non è modificabile. Costa 3 PA. Il danno "
        "inflitto/subito resta invariato rispetto alla forma normale."
    ),
    5863: (  # Polvere di Sanguine
        "Per 5 turni, dimezza il costo in mana e raddoppia l'attacco.\n"
        "Ogni turno, tira 1d10: con un risultato da 1 a 6, invece dell'azione "
        "desiderata perdi il turno compiendo un'azione legata al piano di "
        "Sanguine corrispondente al tiro.\n"
        "Alla fine dell'effetto, paga 1 punto stanchezza."
    ),

    # --- Trappole: shape shared, numbers/wording come from `descrizione` ------
    5285: "Si posiziona a terra e infligge 2d6 danni perforanti a chi la attiva. Riutilizzabile.",
    5286: "Si posiziona a terra e infligge 4d6 danni perforanti a chi la attiva. Riutilizzabile.",
    5287: "Si posiziona a terra e infligge 10d4 danni perforanti a chi la attiva. Riutilizzabile.",
    5288: (
        "Si posiziona a terra, invisibile. Infligge 4d6 danni fisici a chi la "
        "attiva. Non riutilizzabile (si consuma dopo l'attivazione)."
    ),
    5289: (
        "Si posiziona a terra, invisibile. Infligge 10d4 danni fisici a chi la "
        "attiva. Non riutilizzabile (si consuma dopo l'attivazione)."
    ),

    # --- Drink/drug family: pointer to the matching "Bevande" preset(s) -------
    5209: (  # Flin
        "Applica il preset effetto 'Flin' dal catalogo effetti.\n"
        "Dopo 3 turni, applica invece il preset 'Flin (contraccolpo)'.\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5210: (  # Idromele Nordico
        "Applica il preset effetto 'Idromele Nordico' dal catalogo effetti.\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5211: (  # Vino Surilie
        "Applica il preset effetto 'Vino Surilie' dal catalogo effetti.\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5212: (  # Skooma
        "Applica il preset effetto 'Skooma' dal catalogo effetti.\n"
        "Dopo 5 turni, applica il preset 'Skooma (contraccolpo)'."
    ),
    5213: (  # Shein
        "Applica il preset effetto 'Shein' dal catalogo effetti.\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5214: (  # Birra Rovo Nero
        "Applica il preset effetto 'Birra Rovo Nero' dal catalogo effetti.\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5215: (  # Mazte
        "Applica il preset effetto 'Mazte' dal catalogo effetti (arbitrato al "
        "tavolo: 2 Energia e 2 Potere gratuiti ogni turno).\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5216: (  # Brandy Coloviano
        "Applica il preset effetto 'Brandy Coloviano' dal catalogo effetti.\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5217: (  # Vino delle Summerset
        "Applica il preset effetto 'Vino delle Summerset' dal catalogo effetti.\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5231: "Applica il preset effetto 'Sweet Roll' dal catalogo effetti.",
    5844: (  # Vino Sangue di Sanguine
        "Applica il preset effetto 'Vino Sangue di Sanguine' dal catalogo "
        "effetti.\n"
        "Applica inoltre il preset 'Vino Sangue di Sanguine (conversione)' "
        "(arbitrato al tavolo: ogni 4 PA spesi, 1 Energia in più)."
    ),
    5845: (  # Liquore Lacrime di Sanguine
        "Applica il preset effetto 'Liquore Lacrime di Sanguine' dal catalogo "
        "effetti.\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'.\n"
        "Tira 1d6: chi lo beve è colto da un irrefrenabile desiderio legato a "
        "Sanguine — 1 Bere, 2 Mangiare, 3 Sesso, 4 Droga, 5 Musica, 6 Gioco "
        "d'azzardo — e per la scena è spinto a indulgervi."
    ),
    5846: (  # Vino Economico
        "Applica il preset effetto 'Vino Economico' dal catalogo effetti.\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5847: (  # Vino Pregiato
        "Applica il preset effetto 'Vino Pregiato' dal catalogo effetti.\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5848: (  # Distillato di Marshmarrow
        "Applica il preset effetto 'Distillato di Marshmarrow' dal catalogo "
        "effetti.\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5849: (  # Zucchero Lunare
        "Applica il preset effetto 'Zucchero Lunare' dal catalogo effetti.\n"
        "Dopo 5 turni, applica il preset 'Zucchero Lunare (contraccolpo)'.\n"
        "Se il personaggio è khajiit, applica inoltre il preset 'Zucchero "
        "Lunare (khajiit)'."
    ),
    5852: (  # Distillato Nord
        "Applica il preset effetto 'Distillato Nord' dal catalogo effetti.\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5853: (  # Cognac Bretone
        "Applica il preset effetto 'Cognac Bretone' dal catalogo effetti "
        "(arbitrato al tavolo: 1 Potere gratuito ogni turno).\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
    5917: (  # Distillato Del Tempio di Sanguine
        "Applica il preset effetto 'Distillato Del Tempio di Sanguine' dal "
        "catalogo effetti (arbitrato al tavolo: +1 a tutti i tiri, nessun "
        "bersaglio esprime 'tutti i tiri').\n"
        "Dopo 10 turni dall'assunzione, applica il preset 'Sbornia'."
    ),
}


class Command(BaseCommand):
    help = "Scrive regole_speciali per gli ultimi 30 oggetti one-off (dry run di default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Scrive le modifiche invece di simularle.")

    def handle(self, *args, **options):
        written = 0
        with transaction.atomic():
            for item_id, text in PLAN.items():
                item = Oggetto.objects.select_for_update().get(pk=item_id)
                item.regole_speciali = text
                sync_special_rules_review(item)
                item.speciale = bool(compute_special_reasons(item))
                self.stdout.write(f"#{item.id} {item.nome} -> speciale={item.speciale}")
                if options["apply"]:
                    item.save(update_fields=["regole_speciali", "metadata", "speciale", "updated_at"])
                    written += 1
            if not options["apply"]:
                transaction.set_rollback(True)
        self.stdout.write("")
        if options["apply"]:
            self.stdout.write(self.style.SUCCESS(f"Scritti {written} oggetti."))
        else:
            self.stdout.write(self.style.WARNING("Simulazione: nessuna modifica scritta. Usa --apply per confermare."))

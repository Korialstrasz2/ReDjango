from django.db import migrations

# Il set di 8 strumenti che esisteva prima dell'espansione della Fase 2. Un profilo
# creato da `seed_ai_providers` prima di questa migrazione ha esattamente questo
# `allowed_tools` salvo che un Master l'abbia ristretto a mano.
HISTORICAL_TOOL_NAMES = frozenset(
    {
        "cerca_oggetti",
        "scheda_personaggio",
        "cerca_abilita",
        "competenze_personaggio",
        "lore_campagna",
        "mercato",
        "guide_regole",
        "variabili_gioco",
    }
)

NEW_TOOL_NAMES = [
    "abilita_personaggio",
    "note_personaggio",
    "alchimia_personaggio",
    "cerca_incantesimi",
    "tipi_arma",
    "reagenti",
    "inventario_negozio",
    "relazioni_fazioni",
    "eventi_reputazione",
    "voci_lore",
    "timeline",
    "curiosita",
    "hall_of_fame",
    "stato_campagna",
    "mappe_viaggio",
    "storico_tiri",
    "statistiche_tiri",
    "stato_combattimento",
    "modificatori_combattimento",
    "giocatori",
    "impostazioni",
    "posso_permettermi",
    "analisi_abilita",
    "perche_reputazione",
    "riepilogo_gruppo",
    "capacita_trasporto",
]


def expand_full_access_profiles(apps, schema_editor):
    """Un profilo con tutti gli strumenti storici riceve anche i nuovi.

    Un profilo ristretto a mano da un Master resta esattamente com'è: il confronto
    è con l'insieme storico completo, non con un sottoinsieme, quindi una selezione
    volutamente più stretta non viene mai riallargata da qui.
    """

    AIAgentProfile = apps.get_model("ai", "AIAgentProfile")
    for profile in AIAgentProfile.objects.all():
        current = set(profile.allowed_tools or [])
        if current == HISTORICAL_TOOL_NAMES:
            profile.allowed_tools = sorted(current | set(NEW_TOOL_NAMES))
            profile.save(update_fields=["allowed_tools"])


class Migration(migrations.Migration):
    dependencies = [("ai", "0005_configure_gpt_image_2")]

    operations = [migrations.RunPython(expand_full_access_profiles, migrations.RunPython.noop)]

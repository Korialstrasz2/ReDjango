from django.db import migrations
from django.utils import timezone


ELDER_RESOURCES = [
    {
        "id": "elder-sanguine-anime-umane",
        "character": "Rhyss",
        "name": "Anime Umane",
        "value": "6 umane · 3 animali",
        "notes": "Conteggio importato dal pannello Risorse Speciali di The Elder Django.",
        "highlighted": False,
    },
    {
        "id": "elder-sanguine-reroll-dado",
        "character": "Ra Zirr",
        "name": "Reroll Dado Sanguine",
        "value": "Disponibile al giorno 35",
        "notes": "Storico Elder: giorno 30 NO; 31 SÌ; 32 SÌ; 33 SÌ; 34 SÌ; 35 SÌ.",
        "highlighted": True,
    },
    {
        "id": "elder-sanguine-dono",
        "character": "Illaoi",
        "name": "Dono di Sanguine",
        "value": "2 disponibili",
        "notes": "Storico Elder: dal giorno 30 al giorno 35 risultavano 2 utilizzi disponibili ogni giorno.",
        "highlighted": True,
    },
    {
        "id": "elder-sanguine-ladro-funambolo",
        "character": "Ra Zirr",
        "name": "Ladro funambolo",
        "value": "Disponibile al giorno 34",
        "notes": "Storico Elder: disponibile nei giorni 30, 31, 32, 33 e 34.",
        "highlighted": False,
    },
    {
        "id": "elder-sanguine-rhyss",
        "character": "Rhyss",
        "name": "Sanguine",
        "value": "Disponibile al giorno 34",
        "notes": "Storico Elder: disponibile nei giorni 30, 31, 32, 33 e 34.",
        "highlighted": False,
    },
    {
        "id": "elder-sanguine-bonus-razza",
        "character": "Ra Zirr",
        "name": "Bonus razza",
        "value": "Disponibile al giorno 34",
        "notes": "Storico Elder: disponibile nei giorni 30, 31, 32, 33 e 34.",
        "highlighted": False,
    },
    {
        "id": "elder-sanguine-sigillo-vita-temp",
        "character": "Rhyss",
        "name": "Sigillo vita temp",
        "value": "Promemoria serale",
        "notes": "Ogni sera Rhyss deve castarsi Sigillo + Vita temporanea. Se il gruppo non se ne ricorda, viene applicato automaticamente.",
        "highlighted": True,
    },
]


def import_elder_special_resources(apps, schema_editor):
    DatiCampagna = apps.get_model("core", "DatiCampagna")
    campaign = DatiCampagna.objects.filter(nome__iexact="Sanguine").first()
    if not campaign or campaign.risorse_speciali:
        return
    now = timezone.now().isoformat()
    actor = {"id": 0, "name": "Importazione The Elder Django"}
    campaign.risorse_speciali = {
        "version": 1,
        "resources": [
            {
                **resource,
                "order": order,
                "archivedAt": None,
                "createdAt": now,
                "updatedAt": now,
                "updatedBy": actor,
            }
            for order, resource in enumerate(ELDER_RESOURCES)
        ],
        "proposals": [],
    }
    campaign.save(update_fields=["risorse_speciali", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("core", "0054_crafting_skill_rules")]

    operations = [migrations.RunPython(import_elder_special_resources, migrations.RunPython.noop)]

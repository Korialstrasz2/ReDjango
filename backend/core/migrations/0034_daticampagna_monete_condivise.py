from django.db import migrations, models


COIN_SYSTEM_KEY = "currency.coins"


def ensure_coin_item(apps, schema_editor):
    Oggetto = apps.get_model("core", "Oggetto")
    item = Oggetto.objects.filter(metadata__systemKey=COIN_SYSTEM_KEY).first()
    if item is None:
        item = Oggetto.objects.filter(nome__iexact="Monete").first()
    if item is None:
        item = Oggetto(nome="Monete")

    metadata = dict(item.metadata or {})
    metadata.update({"systemKey": COIN_SYSTEM_KEY, "systemManaged": True})
    item.nome = "Monete"
    item.modello = True
    item.archiviato = False
    item.archived_at = None
    item.tipo_1 = "Valuta"
    item.descrizione = "Monete trasportate dal personaggio. Gli spazi occupati sono gestiti automaticamente."
    item.peso = 1
    item.metadata = metadata
    item.save()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0033_loginthrottle"),
    ]

    operations = [
        migrations.AddField(
            model_name="daticampagna",
            name="monete_condivise",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(ensure_coin_item, migrations.RunPython.noop),
    ]

from django.db import migrations


# The initial rarity-5 review marked the existing group as Unico.  These are
# the deliberate exceptions: they are rare merchandise and must remain
# available to the stock generator at the requested tier.
RARITY_BY_ITEM_ID = {
    5058: 2,  # Mandolino
    5115: 3,  # Sacca magica 4
    5116: 4,  # Borsa magica
    5282: 1,  # Vestiti caldi
    5634: 4,  # Set Imperiale
    5682: 1,  # Set da Cucina
    5789: 4,  # Scudo Imperiale
    5825: 5,  # Pergamena dell'onnipotenza
    5827: 5,  # Pergamena di disatomizzazione
    5839: 3,  # Mantello di WhiteNight (500 g)
    5844: 2,  # Vino Sangue di Sanguine
    5845: 4,  # Liquore Lacrime di Sanguine
    5854: 3,  # Siero della Celibatezza
    5871: 5,  # Libro Esperienza +3
    5877: 2,  # Mantello dell'invisibilita' (400 g)
    5882: 2,  # Mantello Ignifugo Maggiore (400 g)
    5884: 2,  # Mantello Caldo Maggiore (400 g)
    5886: 2,  # Mantello Isolante Maggiore (400 g)
    5922: 4,  # Libro Della Visione
}


def assign_rarities(apps, _schema_editor):
    Oggetto = apps.get_model("core", "Oggetto")
    for item_id, rarity in RARITY_BY_ITEM_ID.items():
        Oggetto.objects.filter(id=item_id, rarita=0).update(rarita=rarity)


def restore_uniques(apps, _schema_editor):
    Oggetto = apps.get_model("core", "Oggetto")
    for item_id, rarity in RARITY_BY_ITEM_ID.items():
        Oggetto.objects.filter(id=item_id, rarita=rarity).update(rarita=0)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0051_move_current_rarity_five_to_unique"),
    ]

    operations = [
        migrations.RunPython(assign_rarities, restore_uniques),
    ]

from django.db import migrations


# The existing rarity-5 catalogue was reviewed as hand-assigned content, not
# merchandise. Keep the IDs explicit so this migration does not silently alter
# future items deliberately authored at rarity 5.
CURRENT_RARITY_FIVE_IDS = (
    5058, 5059, 5115, 5116, 5282, 5633, 5634, 5635, 5636, 5637, 5674, 5675,
    5676, 5677, 5678, 5679, 5680, 5681, 5682, 5683, 5684, 5685, 5686, 5687,
    5688, 5689, 5690, 5691, 5692, 5693, 5694, 5695, 5696, 5697, 5698, 5789,
    5824, 5825, 5826, 5827, 5828, 5829, 5832, 5833, 5836, 5837, 5839, 5844,
    5845, 5854, 5869, 5871, 5872, 5877, 5882, 5884, 5886, 5917, 5919, 5920,
    5921, 5922, 5923, 5924, 5925, 5926, 5927, 5928,
)


def mark_as_unique(apps, _schema_editor):
    Oggetto = apps.get_model("core", "Oggetto")
    Oggetto.objects.filter(id__in=CURRENT_RARITY_FIVE_IDS, rarita=5).update(rarita=0)


def restore_rarity_five(apps, _schema_editor):
    Oggetto = apps.get_model("core", "Oggetto")
    Oggetto.objects.filter(id__in=CURRENT_RARITY_FIVE_IDS, rarita=0).update(rarita=5)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0050_seed_leather_crafting_material"),
    ]

    operations = [
        migrations.RunPython(mark_as_unique, restore_rarity_five),
    ]

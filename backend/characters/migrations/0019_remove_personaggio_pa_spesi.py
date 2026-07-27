from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("characters", "0018_equip_arma_primaria_slot"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="personaggio",
            name="pa_spesi",
        ),
    ]

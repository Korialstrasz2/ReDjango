from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("characters", "0017_personaggio_pa_spesi_and_more"),
        ("core", "0015_oggetto_weapon_profile_and_elder_weapon_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="equip",
            name="arma_primaria_slot",
            field=models.CharField(default="arma", max_length=12),
        ),
    ]

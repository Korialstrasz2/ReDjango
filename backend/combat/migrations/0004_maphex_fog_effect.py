from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("combat", "0003_repair_combat_catalog_clones"),
    ]

    operations = [
        migrations.AddField(
            model_name="maphex",
            name="fog_effect",
            field=models.BooleanField(
                default=False,
                help_text="Applica all'esagono un trattamento scuro, desaturato e sfocato senza nasconderlo.",
                verbose_name="effetto nebbia locale",
            ),
        ),
    ]

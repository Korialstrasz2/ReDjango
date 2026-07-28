from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("characters", "0023_remove_reagent_bag"),
    ]

    operations = [
        migrations.AddField(
            model_name="personaggio",
            name="impostazioni_combat",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

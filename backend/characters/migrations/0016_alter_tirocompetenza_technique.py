from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("characters", "0015_note_competenze_tirocompetenza"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tirocompetenza",
            name="technique",
            field=models.CharField(
                choices=[
                    ("standard", "Standard"),
                    ("focus", "Impulso +1"),
                    ("amplify", "Impulso maggiore +2"),
                ],
                default="standard",
                max_length=24,
            ),
        ),
    ]

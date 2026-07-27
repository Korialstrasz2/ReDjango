from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("characters", "0011_effettopersonalizzato_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="effettopersonalizzato",
            name="tipo",
        ),
        migrations.AlterField(
            model_name="operazioneeffettopersonalizzato",
            name="operazione",
            field=models.CharField(
                choices=[
                    ("add", "Aggiungi"),
                    ("subtract", "Sottrai"),
                    ("multiply", "Moltiplica"),
                    ("percent", "Percentuale"),
                    ("min", "Valore minimo"),
                    ("max", "Valore massimo"),
                    ("cap", "Limite massimo"),
                    ("set", "Imposta"),
                    ("strong_set", "Imposta forte"),
                    ("formula_override", "Sostituisci formula"),
                ],
                default="add",
                max_length=32,
            ),
        ),
    ]

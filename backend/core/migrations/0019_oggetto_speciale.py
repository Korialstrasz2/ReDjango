from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0018_opzionetipooggetto_remove_oggetto_tipo_5_and_more")]

    operations = [
        migrations.AddField(
            model_name="oggetto",
            name="speciale",
            field=models.BooleanField(
                default=False,
                help_text="Contrassegna oggetti legacy anomali o che richiedono regole/revisione speciali.",
            ),
        ),
        migrations.AddIndex(
            model_name="oggetto",
            index=models.Index(fields=["speciale", "archiviato"], name="core_oggett_special_b95562_idx"),
        ),
    ]

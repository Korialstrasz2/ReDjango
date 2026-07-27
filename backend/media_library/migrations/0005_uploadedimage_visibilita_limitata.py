from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("media_library", "0004_uploadedimage_group_imagecategory_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="uploadedimage",
            name="visibilita_limitata",
            field=models.BooleanField(
                default=False,
                help_text="Nell'Archivio immagini è visibile soltanto a Master e Amministratori.",
                verbose_name="Visibilità limitata",
            ),
        ),
        migrations.AddIndex(
            model_name="uploadedimage",
            index=models.Index(
                fields=["visibilita_limitata", "archived_at"],
                name="media_img_limited_idx",
            ),
        ),
    ]

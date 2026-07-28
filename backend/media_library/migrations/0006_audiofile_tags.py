import backend.media_library.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("media_library", "0005_uploadedimage_visibilita_limitata"),
    ]

    operations = [
        migrations.AddField(
            model_name="audiofile",
            name="tags",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="audiofile",
            name="file",
            field=models.FileField(upload_to=backend.media_library.models.v2_audio_upload_path),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("characters", "0008_journalentry")]

    operations = [
        migrations.DeleteModel(name="JournalEntry"),
        migrations.RemoveField(model_name="note", name="personaggio_ref"),
        migrations.RemoveField(model_name="note", name="personaggio"),
        migrations.RemoveField(model_name="note", name="note_skill"),
        migrations.RemoveField(model_name="note", name="alchimia"),
        migrations.RemoveField(model_name="note", name="tracker_config"),
        migrations.RemoveField(model_name="note", name="tracker_state"),
        migrations.RenameField(model_name="note", old_name="note_combat", new_name="combat"),
        migrations.AlterField(model_name="note", name="appunti", field=models.TextField(blank=True, default="")),
        migrations.AlterField(model_name="note", name="combat", field=models.TextField(blank=True, default="")),
        migrations.AlterField(model_name="note", name="crafting", field=models.TextField(blank=True, default="")),
        migrations.AlterField(model_name="note", name="background", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="note", name="zaino", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="note", name="viaggio", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="note", name="missioni", field=models.TextField(blank=True, default="")),
    ]

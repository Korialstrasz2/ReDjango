import django.db.models.deletion

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0009_master_ai_change_proposals"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiexecutionrun",
            name="change_set",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="runs",
                to="ai.aichangeset",
            ),
        ),
    ]

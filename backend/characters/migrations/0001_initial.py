# Generated for the ReDjango minimum usable project.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("media_library", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Character",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("ancestry", models.CharField(blank=True, max_length=80)),
                ("archetype", models.CharField(blank=True, max_length=80)),
                ("level", models.PositiveIntegerField(default=1)),
                ("stats", models.JSONField(blank=True, default=dict)),
                ("resources", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="redjango_characters", to=settings.AUTH_USER_MODEL)),
                ("portrait", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="portrait_characters", to="media_library.usermediaasset")),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddIndex(
            model_name="character",
            index=models.Index(fields=["owner", "name"], name="characters__owner_i_c5d1ab_idx"),
        ),
    ]

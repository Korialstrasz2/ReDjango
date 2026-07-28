from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0032_authenticated_access_modes"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginThrottle",
            fields=[
                (
                    "key",
                    models.CharField(max_length=64, primary_key=True, serialize=False),
                ),
                ("failures", models.PositiveSmallIntegerField(default=0)),
                ("window_started_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "limite tentativi di accesso",
                "verbose_name_plural": "limiti tentativi di accesso",
                "indexes": [
                    models.Index(
                        fields=["updated_at"],
                        name="core_logint_updated_744393_idx",
                    ),
                ],
            },
        ),
    ]

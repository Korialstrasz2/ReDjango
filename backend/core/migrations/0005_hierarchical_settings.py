from django.db import migrations, models
import django.db.models.deletion


def migrate_roles_forward(apps, schema_editor):
    Giocatore = apps.get_model("core", "Giocatore")
    Giocatore.objects.filter(role__in=["guest", "player"]).update(role="user")
    Giocatore.objects.filter(role="dm").update(role="master")


def migrate_roles_backward(apps, schema_editor):
    Giocatore = apps.get_model("core", "Giocatore")
    Giocatore.objects.filter(role="user").update(role="player")
    Giocatore.objects.filter(role__in=["master", "admin"]).update(role="dm")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_effetto"),
    ]

    operations = [
        migrations.AlterField(
            model_name="giocatore",
            name="role",
            field=models.CharField(
                choices=[("user", "User"), ("master", "Master"), ("admin", "Admin")],
                default="user",
                max_length=20,
            ),
        ),
        migrations.RunPython(migrate_roles_forward, migrate_roles_backward),
        migrations.CreateModel(
            name="SettingDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("key", models.CharField(max_length=160, unique=True)),
                ("label", models.CharField(max_length=180)),
                ("category", models.CharField(max_length=80)),
                ("description", models.TextField(blank=True)),
                (
                    "minimum_role",
                    models.CharField(
                        choices=[("user", "User"), ("master", "Master"), ("admin", "Admin")],
                        default="user",
                        max_length=20,
                    ),
                ),
                (
                    "value_type",
                    models.CharField(
                        choices=[
                            ("bool", "Boolean"),
                            ("int", "Integer"),
                            ("string", "String"),
                            ("color", "Color"),
                            ("select", "Select"),
                            ("json", "JSON"),
                        ],
                        default="string",
                        max_length=20,
                    ),
                ),
                ("default_value", models.JSONField(blank=True, default=dict)),
                ("value", models.JSONField(blank=True, null=True)),
                ("choices", models.JSONField(blank=True, default=list)),
                ("user_customizable", models.BooleanField(default=False)),
                ("master_customizable", models.BooleanField(default=False)),
                ("ui_token", models.CharField(blank=True, max_length=80)),
                ("active", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "ordering": ["category", "order", "key"],
                "indexes": [
                    models.Index(
                        fields=["category", "minimum_role", "order"],
                        name="core_settin_categor_f4cfd9_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="SettingOverride",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("value", models.JSONField()),
                (
                    "giocatore",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="setting_overrides",
                        to="core.giocatore",
                    ),
                ),
                (
                    "setting",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="overrides",
                        to="core.settingdefinition",
                    ),
                ),
            ],
            options={
                "ordering": ["giocatore__nome", "setting__category", "setting__order"],
                "indexes": [
                    models.Index(fields=["giocatore", "setting"], name="core_settin_giocato_38af41_idx")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("setting", "giocatore"),
                        name="unique_setting_override_per_giocatore",
                    )
                ],
            },
        ),
    ]

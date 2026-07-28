from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


ACCESS_MODE_CHOICES = [
    {"value": "locked", "label": "Bloccata · solo questo computer"},
    {"value": "lan", "label": "Rete locale LAN"},
    {"value": "online", "label": "Server online"},
]


def migrate_access_mode_and_accounts(apps, schema_editor):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    SettingOverride = apps.get_model("core", "SettingOverride")
    Giocatore = apps.get_model("core", "Giocatore")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    old = SettingDefinition.objects.filter(key="security.require_login_for_remote").first()
    access_mode = SettingDefinition.objects.filter(key="security.access_mode").first()
    if old is not None and access_mode is None:
        old.key = "security.access_mode"
        access_mode = old
    elif old is not None:
        SettingOverride.objects.filter(setting=old).delete()
        old.delete()

    if access_mode is not None:
        SettingOverride.objects.filter(setting=access_mode).delete()
        access_mode.label = "Modalità di accesso"
        access_mode.category = "sicurezza"
        access_mode.description = (
            "Scegli se il server è limitato a questo computer, disponibile sulla LAN "
            "o configurato per una pubblicazione online protetta."
        )
        access_mode.minimum_role = "admin"
        access_mode.value_type = "select"
        access_mode.default_value = "locked"
        access_mode.value = "locked"
        access_mode.choices = ACCESS_MODE_CHOICES
        access_mode.user_customizable = False
        access_mode.master_customizable = False
        access_mode.active = True
        access_mode.archived_at = None
        access_mode.save()

    for giocatore in Giocatore.objects.filter(user__isnull=True).iterator():
        user = User.objects.filter(username__iexact=giocatore.nome).order_by("id").first()
        if user is not None and not Giocatore.objects.filter(user=user).exclude(pk=giocatore.pk).exists():
            giocatore.user = user
            giocatore.save(update_fields=["user", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0031_text_color_aware_outline"),
    ]

    operations = [
        migrations.AddField(
            model_name="giocatore",
            name="user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="redjango_giocatore",
                to=settings.AUTH_USER_MODEL,
                verbose_name="account Django",
            ),
        ),
        migrations.RunPython(migrate_access_mode_and_accounts, migrations.RunPython.noop),
    ]

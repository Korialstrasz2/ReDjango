from django.db import migrations
from django.utils import timezone


OBSOLETE_GROUPS = {
    "generale",
    "combattimento",
    "magia",
    "crafting",
    "sociale",
    "esplorazione",
    "classe",
    "religione",
    "perk",
}


def archive_empty_obsolete_groups(apps, schema_editor):
    Group = apps.get_model("core", "GruppoFamiglieSkill")
    for group in Group.objects.filter(nome__in=OBSOLETE_GROUPS, archived_at__isnull=True):
        if not group.famiglie.filter(archived_at__isnull=True).exists():
            group.archived_at = timezone.now()
            group.save(update_fields=["archived_at", "updated_at"])


def restore_obsolete_groups(apps, schema_editor):
    Group = apps.get_model("core", "GruppoFamiglieSkill")
    Group.objects.filter(nome__in=OBSOLETE_GROUPS).update(archived_at=None)


class Migration(migrations.Migration):
    dependencies = [("core", "0013_skill_management_workspace")]

    operations = [migrations.RunPython(archive_empty_obsolete_groups, restore_obsolete_groups)]

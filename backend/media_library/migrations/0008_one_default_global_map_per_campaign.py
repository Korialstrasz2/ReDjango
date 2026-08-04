from django.db import migrations, models


def keep_one_default_global_map(apps, schema_editor):
    DatiMappa = apps.get_model("media_library", "DatiMappa")
    campaign_ids = (
        DatiMappa.objects.filter(
            tipo="globale",
            default_for_campaign=True,
            archived_at__isnull=True,
            campagna__isnull=False,
        )
        .values_list("campagna_id", flat=True)
        .distinct()
    )
    for campaign_id in campaign_ids:
        defaults = DatiMappa.objects.filter(
            campagna_id=campaign_id,
            tipo="globale",
            default_for_campaign=True,
            archived_at__isnull=True,
        ).order_by("id")
        keep_id = defaults.values_list("id", flat=True).first()
        defaults.exclude(id=keep_id).update(default_for_campaign=False)


class Migration(migrations.Migration):

    dependencies = [
        ("media_library", "0007_videoclip"),
    ]

    operations = [
        migrations.RunPython(keep_one_default_global_map, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="datimappa",
            constraint=models.UniqueConstraint(
                fields=("campagna",),
                condition=models.Q(
                    tipo="globale",
                    default_for_campaign=True,
                    archived_at__isnull=True,
                    campagna__isnull=False,
                ),
                name="one_default_global_map_per_campaign",
            ),
        ),
    ]

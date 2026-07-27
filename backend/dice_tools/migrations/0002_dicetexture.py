from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("dice_tools", "0001_initial"),
        ("media_library", "0003_delete_usermediaasset"),
    ]

    operations = [
        migrations.CreateModel(
            name="DiceTexture",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("sides", models.PositiveSmallIntegerField(verbose_name="facce del dado")),
                ("offset_x", models.SmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(-100), django.core.validators.MaxValueValidator(100)], verbose_name="spostamento orizzontale")),
                ("offset_y", models.SmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(-100), django.core.validators.MaxValueValidator(100)], verbose_name="spostamento verticale")),
                ("scale", models.PositiveSmallIntegerField(default=100, validators=[django.core.validators.MinValueValidator(50), django.core.validators.MaxValueValidator(300)], verbose_name="scala percentuale")),
                ("rotation", models.SmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(-180), django.core.validators.MaxValueValidator(180)], verbose_name="rotazione")),
                ("dice_set", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="textures", to="dice_tools.diceset", verbose_name="set di dadi")),
                ("image", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dice_textures", to="media_library.uploadedimage", verbose_name="immagine texture")),
            ],
            options={"verbose_name": "texture dado", "verbose_name_plural": "texture dadi", "ordering": ["sides"]},
        ),
        migrations.AddConstraint(
            model_name="dicetexture",
            constraint=models.UniqueConstraint(fields=("dice_set", "sides"), name="unique_texture_per_die_in_set"),
        ),
    ]

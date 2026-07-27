from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("characters", "0019_remove_personaggio_pa_spesi"),
    ]

    operations = [
        migrations.CreateModel(
            name="BottoneCombat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("nome", models.CharField(max_length=80)),
                ("testo_da_mostrare", models.TextField(blank=True, max_length=1000)),
                ("bonus_attacco", models.SmallIntegerField(default=0)),
                ("bonus_danno", models.SmallIntegerField(default=0)),
                ("bonus_tier", models.SmallIntegerField(default=0)),
                ("perforazione", models.SmallIntegerField(default=0)),
                ("perforazione_percentuale", models.SmallIntegerField(default=0)),
                ("pubblico", models.BooleanField(default=False)),
                ("attivo", models.BooleanField(default=True)),
                ("tieni_attivo_in_combat", models.BooleanField(default=False)),
                ("ordine", models.PositiveSmallIntegerField(default=0)),
                ("personaggio", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bottoni_combat", to="characters.personaggio")),
            ],
            options={"ordering": ["ordine", "id"]},
        ),
        migrations.AddIndex(
            model_name="bottonecombat",
            index=models.Index(fields=["personaggio", "attivo", "ordine"], name="characters__persona_73647a_idx"),
        ),
        migrations.AddIndex(
            model_name="bottonecombat",
            index=models.Index(fields=["pubblico", "ordine"], name="characters__pubblic_e32bbc_idx"),
        ),
    ]

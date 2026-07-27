import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("characters", "0019_remove_personaggio_pa_spesi"),
        ("core", "0015_oggetto_weapon_profile_and_elder_weapon_types"),
    ]

    operations = [
        migrations.CreateModel(
            name="CharacterAssignmentRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("pending", "In attesa"), ("approved", "Approvata"), ("rejected", "Rifiutata")], default="pending", max_length=20, verbose_name="stato")),
                ("message", models.TextField(blank=True, verbose_name="messaggio del giocatore")),
                ("admin_note", models.TextField(blank=True, verbose_name="nota amministrativa")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True, verbose_name="esaminata il")),
                ("giocatore", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="character_assignment_requests", to="core.giocatore", verbose_name="giocatore")),
                ("personaggio", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignment_requests", to="characters.personaggio", verbose_name="personaggio richiesto")),
            ],
            options={
                "verbose_name": "richiesta di assegnazione personaggio",
                "verbose_name_plural": "richieste di assegnazione personaggi",
                "ordering": ["status", "-created_at"],
                "indexes": [models.Index(fields=["status", "created_at"], name="core_charac_status_202b98_idx")],
                "constraints": [models.UniqueConstraint(fields=("giocatore", "personaggio"), name="unique_character_request_per_player")],
            },
        ),
    ]

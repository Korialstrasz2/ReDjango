import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from backend.characters.models import Personaggio
from backend.combat.models import MapMetadata, MapParticipant, MapType
from backend.core.models import DatiCampagna, Giocatore


MAP_NAME = "E2E · Matrice ruoli combattimento"
MASTER_USERNAME = "combat_e2e_master"
PLAYER_USERNAME = "combat_e2e_player"
DEFAULT_PASSWORD = "ReDjango-Combat-E2E-2026!"


class Command(BaseCommand):
    help = "Crea identità, personaggi e mappa deterministici per i test E2E dei ruoli Combat."

    def _account(self, username: str, role: str, display_name: str, password: str) -> Giocatore:
        User = get_user_model()
        user, _created = User.objects.get_or_create(username=username)
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(password)
        user.save(update_fields=["is_active", "is_staff", "is_superuser", "password"])

        giocatore, _created = Giocatore.objects.get_or_create(
            nome=username,
            defaults={"user": user, "display_name": display_name, "role": role},
        )
        giocatore.user = user
        giocatore.display_name = display_name
        giocatore.role = role
        giocatore.save(update_fields=["user", "display_name", "role", "updated_at"])
        return giocatore

    def handle(self, *args, **options):
        password = os.environ.get("REDJANGO_COMBAT_E2E_PASSWORD", DEFAULT_PASSWORD)
        if not password:
            raise CommandError("REDJANGO_COMBAT_E2E_PASSWORD non può essere vuota.")

        campaign = DatiCampagna.objects.filter(attiva=True, archived_at__isnull=True).first()
        map_type = MapType.objects.filter(active=True, archived_at__isnull=True).order_by("id").first()
        characters = list(
            Personaggio.objects.filter(
                archived_at__isnull=True,
                metadata__seed_kind="poc_personaggio",
            ).order_by("id")[:2]
        )
        if len(characters) < 2:
            characters = list(Personaggio.objects.filter(archived_at__isnull=True).order_by("id")[:2])
        if campaign is None or map_type is None or len(characters) < 2:
            raise CommandError("Esegui seed_minimum_data prima di ensure_combat_e2e_roles.")

        master = self._account(MASTER_USERNAME, Giocatore.ROLE_MASTER, "Master E2E Combat", password)
        player = self._account(PLAYER_USERNAME, Giocatore.ROLE_USER, "Giocatore E2E Combat", password)
        master_character, player_character = characters

        for giocatore, active_character, character_ids in (
            (master, master_character, [character.id for character in characters]),
            (player, player_character, [player_character.id]),
        ):
            giocatore.active_campaign = campaign
            giocatore.active_character = active_character
            giocatore.character_ids = character_ids
            giocatore.save(update_fields=["active_campaign", "active_character", "character_ids", "updated_at"])

        combat_map = MapMetadata.objects.filter(metadata__seed_key="combat_e2e_roles").first()
        if combat_map is None:
            combat_map = MapMetadata.objects.create(
                name=MAP_NAME,
                map_type=map_type,
                created_by=master,
                rows=8,
                columns=10,
                is_default=True,
                metadata={"seed_kind": "e2e_fixture", "seed_key": "combat_e2e_roles"},
            )
        else:
            combat_map.name = MAP_NAME
            combat_map.map_type = map_type
            combat_map.created_by = master
            combat_map.rows = 8
            combat_map.columns = 10
            combat_map.is_default = True
            combat_map.archived_at = None
            combat_map.metadata = {"seed_kind": "e2e_fixture", "seed_key": "combat_e2e_roles"}
            combat_map.save(update_fields=[
                "name", "map_type", "created_by", "rows", "columns", "is_default",
                "archived_at", "metadata", "updated_at",
            ])
        MapMetadata.objects.exclude(pk=combat_map.pk).filter(is_default=True).update(is_default=False)

        participants = (
            (master_character, 2, 2, "#b97842", 0),
            (player_character, 5, 3, "#477ab5", 1),
        )
        for character, q, r, color, order in participants:
            participant, _created = MapParticipant.objects.update_or_create(
                map=combat_map,
                character=character,
                defaults={
                    "active": True,
                    "anchor_q": q,
                    "anchor_r": r,
                    "token_color": color,
                    "order": order,
                    "archived_at": None,
                    "metadata": {"seed_kind": "e2e_fixture", "seed_key": "combat_e2e_roles"},
                },
            )
            participant.footprint.all().delete()

        combat_map.active_character = master_character
        combat_map.save(update_fields=["active_character", "updated_at"])
        self.stdout.write(self.style.SUCCESS(
            f"Fixture Combat E2E pronta: {MASTER_USERNAME}, {PLAYER_USERNAME}, mappa {combat_map.id}."
        ))

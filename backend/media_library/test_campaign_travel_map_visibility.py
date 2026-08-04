from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from PIL import Image

from backend.core.models import DatiCampagna, Giocatore

from .models import DatiMappa, ImageCategory, UploadedImage


def image_upload(name: str, color: str = "#31506f") -> SimpleUploadedFile:
    source = BytesIO()
    Image.new("RGB", (96, 64), color).save(source, format="WEBP")
    return SimpleUploadedFile(name, source.getvalue(), content_type="image/webp")


class CampaignTravelMapVisibilityTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = TemporaryDirectory()
        cls.override = override_settings(MEDIA_ROOT=cls.media_root.name)
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        cls.media_root.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.category = ImageCategory.objects.create(
            name="Mappe campagna test",
            slug="mappe-campagna-visibility-test",
            usage_types=["travel_map"],
        )
        self.campaign = DatiCampagna.objects.create(nome="Campagna condivisa", attiva=True)
        self.player_user = get_user_model().objects.create_user(username="campaign-map-player")
        self.player = Giocatore.objects.create(
            user=self.player_user,
            nome=self.player_user.username,
            role=Giocatore.ROLE_USER,
            active_campaign=self.campaign,
        )
        self.map_image = UploadedImage.objects.create(
            title="Sorgente mappa riservata",
            folder="mappe",
            file=image_upload("campaign-map.webp"),
            category=self.category,
            visibilita_limitata=True,
        )
        self.travel_map = DatiMappa.objects.create(
            nome="Mappa globale condivisa",
            campagna=self.campaign,
            image=self.map_image,
            tipo="globale",
            default_for_campaign=True,
        )
        self.client.force_login(self.player_user)

    def test_player_receives_and_can_render_limited_campaign_map(self):
        response = self.client.get("/api/travel/maps/")

        self.assertEqual(response.status_code, 200)
        maps = response.json()["data"]["maps"]
        self.assertEqual([entry["id"] for entry in maps], [self.travel_map.id])
        self.assertTrue(maps[0]["isDefault"])

        raw_image = self.client.get(self.map_image.file.url)
        self.assertEqual(raw_image.status_code, 200)
        self.assertEqual(raw_image["Cache-Control"], "private, max-age=31536000, immutable")
        raw_image.close()

        tiles = maps[0]["tiles"]
        tile_url = f"{tiles['baseUrl']}/{tiles['maxLevel']}/0/0.webp"
        tile = self.client.get(tile_url)
        self.assertEqual(tile.status_code, 200)
        self.assertEqual(tile["Cache-Control"], "private, max-age=31536000, immutable")
        tile.close()

    def test_campaign_map_source_is_hidden_from_image_archive_for_every_role(self):
        ordinary = UploadedImage.objects.create(
            title="Immagine normale",
            folder="general",
            file=image_upload("ordinary.webp", "#704530"),
            category=self.category,
        )

        player_assets = self.client.get("/api/media/").json()["data"]["assets"]
        self.assertEqual([asset["id"] for asset in player_assets], [ordinary.id])

        admin_user = get_user_model().objects.create_user(username="campaign-map-admin")
        Giocatore.objects.create(
            user=admin_user,
            nome=admin_user.username,
            role=Giocatore.ROLE_ADMIN,
            active_campaign=self.campaign,
        )
        self.client.force_login(admin_user)
        admin_assets = self.client.get("/api/media/").json()["data"]["assets"]
        self.assertEqual([asset["id"] for asset in admin_assets], [ordinary.id])
        self.assertEqual(self.client.get(f"/api/media/{self.map_image.id}/").status_code, 404)

    def test_cache_includes_campaign_map_but_not_unrelated_limited_images(self):
        unrelated = UploadedImage.objects.create(
            title="Segreto non mappa",
            folder="general",
            file=image_upload("unrelated-secret.webp", "#522f61"),
            category=self.category,
            visibilita_limitata=True,
        )

        response = self.client.get("/api/media/cache-manifest/")

        self.assertEqual(response.status_code, 200)
        urls = {entry["url"] for entry in response.json()["data"]["entries"]}
        self.assertIn(self.map_image.file.url, urls)
        self.assertNotIn(unrelated.file.url, urls)

    def test_limited_map_from_another_campaign_remains_hidden(self):
        other_campaign = DatiCampagna.objects.create(nome="Altra campagna", attiva=True)
        other_image = UploadedImage.objects.create(
            title="Mappa altra campagna",
            folder="mappe",
            file=image_upload("other-campaign.webp", "#62562e"),
            category=self.category,
            visibilita_limitata=True,
        )
        DatiMappa.objects.create(
            nome="Mappa globale altra campagna",
            campagna=other_campaign,
            image=other_image,
            tipo="globale",
            default_for_campaign=True,
        )

        self.assertEqual(self.client.get(other_image.file.url).status_code, 404)

    def test_only_one_active_default_global_map_is_allowed_per_campaign(self):
        second_image = UploadedImage.objects.create(
            title="Seconda mappa",
            folder="mappe",
            file=image_upload("second-map.webp", "#40673f"),
            category=self.category,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            DatiMappa.objects.create(
                nome="Seconda predefinita",
                campagna=self.campaign,
                image=second_image,
                tipo="globale",
                default_for_campaign=True,
            )

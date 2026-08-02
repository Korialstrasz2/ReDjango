import json
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from backend.core.models import DatiCampagna, Giocatore, Oggetto
from backend.dice_tools.models import DiceSet, DiceTexture

from .models import DatiMappa, ImageCategory, UploadedImage


def media_envelope(request_id: str, payload: dict | None = None) -> str:
    return json.dumps(
        {
            "action": "media.upload",
            "requestId": request_id,
            "context": {"screen": "media"},
            "payload": payload or {},
            "meta": {"clientVersion": "test"},
        }
    )


class MediaApiContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.generic_category = ImageCategory.objects.create(
            name="Altro",
            slug="altro-test",
            usage_types=["generic"],
            order=100,
        )
        cls.icon_category = ImageCategory.objects.create(
            name="Icone",
            slug="icone-test",
            usage_types=["item_icon", "dice_texture"],
            order=10,
        )

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
        user = get_user_model().objects.create_user(username="media_master")
        Giocatore.objects.create(
            user=user,
            nome=user.username,
            display_name="Media Master",
            role=Giocatore.ROLE_MASTER,
        )
        self.client.force_login(user)

    def login_admin(self):
        user = get_user_model().objects.create_user(username="media_admin")
        Giocatore.objects.create(
            user=user,
            nome=user.username,
            display_name="Media Admin",
            role=Giocatore.ROLE_ADMIN,
        )
        self.client.force_login(user)
        return user

    def test_upload_list_and_delete_v2_image(self):
        uploaded = SimpleUploadedFile("map.png", b"not-a-rendered-image", content_type="image/png")
        response = self.client.post(
            "/api/media/",
            data={
                "envelope": media_envelope("media-upload-1", {"title": "Gate Map", "notes": "Starter note", "categoryId": self.generic_category.id, "group": "Cancelli"}),
                "file": uploaded,
            },
            HTTP_X_REDJANGO_ACTION="media.upload",
            HTTP_X_REDJANGO_REQUEST_ID="media-upload-1",
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["requestId"], "media-upload-1")
        asset = body["data"]["asset"]
        self.assertEqual(asset["title"], "Gate Map")
        self.assertEqual(asset["notes"], "Starter note")
        self.assertEqual(asset["mimeType"], "image/png")
        self.assertEqual(asset["category"], "Altro")
        self.assertEqual(asset["group"], "Cancelli")
        self.assertFalse(asset["canMove"])
        self.assertFalse(asset["canDelete"])
        self.assertEqual(UploadedImage.objects.count(), 1)

        list_response = self.client.get("/api/media/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["data"]["assets"]), 1)
        self.assertIn("Altro", [entry["name"] for entry in list_response.json()["data"]["categories"]])

        denied_delete = self.client.delete(f"/api/media/{asset['id']}/")
        self.assertEqual(denied_delete.status_code, 403)
        self.assertEqual(denied_delete.json()["errors"][0]["code"], "media.admin_required")
        self.assertEqual(UploadedImage.objects.count(), 1)

        self.login_admin()
        admin_list = self.client.get("/api/media/").json()["data"]["assets"]
        self.assertTrue(admin_list[0]["canMove"])
        self.assertTrue(admin_list[0]["canDelete"])
        delete_response = self.client.delete(f"/api/media/{asset['id']}/")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(UploadedImage.objects.count(), 0)

    def test_detail_reports_usages_and_admin_can_move_then_delete_shared_image(self):
        asset = UploadedImage.objects.create(
            title="Icona condivisa",
            folder="seed_assets",
            file=SimpleUploadedFile("shared.png", b"shared-image", content_type="image/png"),
            category=self.icon_category,
            group="Oggetti",
        )
        item = Oggetto.objects.create(nome="Spada illustrata", media=asset)
        dice_set = DiceSet.objects.create(slug="set-condiviso", name="Set condiviso", dice=[6])
        texture = DiceTexture.objects.create(dice_set=dice_set, sides=6, image=asset)

        denied_detail = self.client.get(f"/api/media/{asset.id}/")
        self.assertEqual(denied_detail.status_code, 403)
        self.login_admin()
        detail_response = self.client.get(f"/api/media/{asset.id}/")
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.json()["data"]
        self.assertEqual(detail["usageCount"], 2)
        self.assertIn("Oggetto: Spada illustrata", [usage["label"] for usage in detail["usages"]])
        self.assertIn("Texture dado: Set condiviso · d6", [usage["label"] for usage in detail["usages"]])
        self.assertIn("clear", [usage["deletionBehavior"] for usage in detail["usages"]])
        self.assertIn("cascade", [usage["deletionBehavior"] for usage in detail["usages"]])

        move_response = self.client.patch(
            f"/api/media/{asset.id}/",
            data=json.dumps(
                {
                    "action": "media.move",
                    "requestId": "media-move-1",
                    "context": {"screen": "media"},
                    "payload": {"categoryId": self.generic_category.id, "group": "Condivise"},
                    "meta": {"clientVersion": "test"},
                }
            ),
            content_type="application/json",
            HTTP_X_REDJANGO_ACTION="media.move",
            HTTP_X_REDJANGO_REQUEST_ID="media-move-1",
        )
        self.assertEqual(move_response.status_code, 200)
        asset.refresh_from_db()
        self.assertEqual(asset.category, self.generic_category)
        self.assertEqual(asset.group, "Condivise")
        self.assertEqual(move_response.json()["data"]["usageCount"], 2)

        delete_response = self.client.delete(f"/api/media/{asset.id}/")
        self.assertEqual(delete_response.status_code, 200)
        item.refresh_from_db()
        self.assertIsNone(item.media_id)
        self.assertFalse(DiceTexture.objects.filter(pk=texture.pk).exists())
        self.assertFalse(UploadedImage.objects.filter(pk=asset.pk).exists())

    def test_missing_upload_returns_structured_error(self):
        response = self.client.post(
            "/api/media/",
            data={"envelope": media_envelope("media-missing-1", {"title": "No File"})},
            HTTP_X_REDJANGO_REQUEST_ID="media-missing-1",
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["errors"][0]["code"], "media.file_required")

    def test_non_image_upload_is_rejected(self):
        uploaded = SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")
        response = self.client.post(
            "/api/media/",
            data={"envelope": media_envelope("media-type-1"), "file": uploaded},
            HTTP_X_REDJANGO_REQUEST_ID="media-type-1",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["code"], "media.image_required")

    def test_image_mime_with_an_unsafe_extension_is_rejected(self):
        uploaded = SimpleUploadedFile("page.html", b"<script>alert(1)</script>", content_type="image/png")
        response = self.client.post(
            "/api/media/",
            data={"envelope": media_envelope("media-extension-1"), "file": uploaded},
            HTTP_X_REDJANGO_REQUEST_ID="media-extension-1",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["code"], "media.image_required")

    def test_media_files_require_login_and_enforce_limited_visibility(self):
        public = UploadedImage.objects.create(
            title="Pubblica diretta",
            folder="seed_assets",
            file=SimpleUploadedFile("direct-public.png", b"public-direct", content_type="image/png"),
            category=self.generic_category,
        )
        limited = UploadedImage.objects.create(
            title="Segreta diretta",
            folder="seed_assets",
            file=SimpleUploadedFile("direct-secret.png", b"secret-direct", content_type="image/png"),
            category=self.generic_category,
            visibilita_limitata=True,
        )

        self.client.logout()
        anonymous = self.client.get(public.file.url)
        self.assertEqual(anonymous.status_code, 302)
        self.assertTrue(anonymous.headers["Location"].startswith("/login/"))

        player = get_user_model().objects.create_user(username="direct-player")
        Giocatore.objects.create(user=player, nome=player.username, role=Giocatore.ROLE_USER)
        self.client.force_login(player)
        self.assertEqual(self.client.get(limited.file.url).status_code, 404)

        self.client.force_login(get_user_model().objects.get(username="media_master"))
        visible = self.client.get(limited.file.url)
        self.assertEqual(visible.status_code, 200)
        self.assertEqual(visible.headers["Cache-Control"], "private, no-store")
        cached = self.client.get(public.file.url)
        self.assertEqual(cached.status_code, 200)
        self.assertEqual(cached.headers["Cache-Control"], "private, max-age=31536000, immutable")
        self.assertTrue(cached.headers["ETag"].startswith('"'))
        not_modified = self.client.get(public.file.url, HTTP_IF_NONE_MATCH=cached.headers["ETag"])
        self.assertEqual(not_modified.status_code, 304)
        self.assertEqual(visible.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(visible.headers["Cross-Origin-Resource-Policy"], "same-origin")
        visible.close()
        cached.close()
        not_modified.close()

    def test_large_global_travel_map_exposes_and_serves_native_resolution_tiles(self):
        source = BytesIO()
        Image.new("RGB", (1100, 700), "#4c7898").save(source, format="WEBP")
        image = UploadedImage.objects.create(
            title="Mappa enorme",
            folder="mappe",
            file=SimpleUploadedFile("huge-map.webp", source.getvalue(), content_type="image/webp"),
            category=self.generic_category,
        )
        campaign = DatiCampagna.objects.create(nome="Tile viaggio", attiva=True)
        travel_map = DatiMappa.objects.create(nome="Mappa enorme", campagna=campaign, tipo="globale", image=image)
        giocatore = Giocatore.objects.get(user__username="media_master")
        giocatore.active_campaign = campaign
        giocatore.save(update_fields=["active_campaign", "updated_at"])

        response = self.client.get("/api/travel/maps/")

        self.assertEqual(response.status_code, 200)
        serialized = response.json()["data"]["maps"][0]
        self.assertEqual(serialized["id"], travel_map.id)
        self.assertEqual(serialized["imageUrl"], image.file.url)
        self.assertEqual(serialized["tiles"]["width"], 1100)
        self.assertEqual(serialized["tiles"]["height"], 700)
        self.assertGreaterEqual(serialized["tiles"]["maxLevel"], 1)
        tile_url = f"{serialized['tiles']['baseUrl']}/{serialized['tiles']['maxLevel']}/0/0.webp"
        tile = self.client.get(tile_url)
        self.assertEqual(tile.status_code, 200)
        self.assertEqual(tile["Content-Type"], "image/webp")
        self.assertEqual(tile["Cache-Control"], "private, max-age=31536000, immutable")
        tile.close()

        manifest_response = self.client.get("/api/media/cache-manifest/")
        self.assertEqual(manifest_response.status_code, 200)
        manifest = manifest_response.json()["data"]
        self.assertEqual(manifest["scope"], f"user-{giocatore.user_id}-campaign-{campaign.id}")
        self.assertEqual(manifest["campaign"]["id"], campaign.id)
        urls = {entry["url"] for entry in manifest["entries"]}
        self.assertIn(image.file.url, urls)
        self.assertTrue(any(url.startswith(serialized["tiles"]["baseUrl"]) for url in urls))
        self.assertEqual(manifest["totalBytes"], sum(entry["size"] for entry in manifest["entries"]))

    def test_media_cache_manifest_never_contains_limited_images(self):
        public = UploadedImage.objects.create(
            title="Condivisa cache",
            folder="cache",
            file=SimpleUploadedFile("cache-public.png", b"public", content_type="image/png"),
            category=self.generic_category,
        )
        limited = UploadedImage.objects.create(
            title="Riservata cache",
            folder="cache",
            file=SimpleUploadedFile("cache-secret.png", b"secret", content_type="image/png"),
            category=self.generic_category,
            visibilita_limitata=True,
        )

        response = self.client.get("/api/media/cache-manifest/")

        self.assertEqual(response.status_code, 200)
        urls = {entry["url"] for entry in response.json()["data"]["entries"]}
        self.assertIn(public.file.url, urls)
        self.assertNotIn(limited.file.url, urls)

    def test_service_worker_is_public_and_controls_the_origin(self):
        self.client.logout()

        response = self.client.get("/service-worker.js")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_context_upload_uses_admin_configured_category_and_default_group(self):
        uploaded = SimpleUploadedFile("die.png", b"not-a-rendered-image", content_type="image/png")
        response = self.client.post(
            "/api/media/",
            data={
                "envelope": media_envelope(
                    "media-context-1",
                    {"title": "Dado verde", "usageType": "dice_texture"},
                ),
                "file": uploaded,
            },
            HTTP_X_REDJANGO_ACTION="media.upload",
            HTTP_X_REDJANGO_REQUEST_ID="media-context-1",
        )
        self.assertEqual(response.status_code, 201)
        asset = response.json()["data"]["asset"]
        self.assertEqual(asset["categoryId"], self.icon_category.id)
        self.assertEqual(asset["category"], "Icone")
        self.assertEqual(asset["group"], "Dadi")

    def test_limited_images_are_hidden_from_players_but_visible_to_master_and_admin(self):
        public = UploadedImage.objects.create(
            title="Pubblica",
            folder="seed_assets",
            file=SimpleUploadedFile("public.png", b"public", content_type="image/png"),
            category=self.generic_category,
        )
        limited = UploadedImage.objects.create(
            title="Segreta",
            folder="seed_assets",
            file=SimpleUploadedFile("secret.png", b"secret", content_type="image/png"),
            category=self.generic_category,
            visibilita_limitata=True,
        )
        User = get_user_model()
        staff_player = User.objects.create_user(username="staff_player", is_staff=True)
        staff_profile = Giocatore.objects.create(
            nome=staff_player.username,
            display_name="Staff Player",
            role=Giocatore.ROLE_USER,
        )
        self.client.force_login(staff_player)

        player_assets = self.client.get("/api/media/").json()["data"]["assets"]
        self.assertEqual([asset["id"] for asset in player_assets], [public.id])
        self.assertFalse(player_assets[0]["canMove"])
        self.assertFalse(player_assets[0]["canDelete"])
        self.assertTrue(staff_player.is_staff)

        staff_profile.role = Giocatore.ROLE_MASTER
        staff_profile.save(update_fields=["role"])
        master_assets = self.client.get("/api/media/").json()["data"]["assets"]
        self.assertEqual({asset["id"] for asset in master_assets}, {public.id, limited.id})
        self.assertFalse(any(asset["canMove"] for asset in master_assets))

        staff_profile.role = Giocatore.ROLE_ADMIN
        staff_profile.save(update_fields=["role"])
        admin_assets = self.client.get("/api/media/").json()["data"]["assets"]
        self.assertTrue(all(asset["canMove"] and asset["canSetLimitedVisibility"] for asset in admin_assets))

    def test_admin_can_toggle_limited_visibility_and_player_cannot(self):
        asset = UploadedImage.objects.create(
            title="Riservabile",
            folder="seed_assets",
            file=SimpleUploadedFile("toggle.png", b"toggle", content_type="image/png"),
            category=self.generic_category,
        )
        User = get_user_model()
        staff_player = User.objects.create_user(username="limited_staff", is_staff=True)
        Giocatore.objects.create(nome=staff_player.username, role=Giocatore.ROLE_USER)
        self.client.force_login(staff_player)
        denied = self.client.patch(
            f"/api/media/{asset.id}/",
            data=json.dumps({"payload": {"limitedVisibility": True}}),
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

        self.login_admin()
        updated = self.client.patch(
            f"/api/media/{asset.id}/",
            data=json.dumps({"payload": {"limitedVisibility": True}}),
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200)
        asset.refresh_from_db()
        self.assertTrue(asset.visibilita_limitata)
        self.assertTrue(updated.json()["data"]["asset"]["limitedVisibility"])


class TravelMapApiTests(TestCase):
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
            name="Mappe",
            slug="mappe-travel-test",
            usage_types=["travel_map", "generic"],
        )
        self.campaign = DatiCampagna.objects.create(nome="Viaggio Test", attiva=True)
        self.user = get_user_model().objects.create_user(username="travel_staff", is_staff=True)
        self.profile = Giocatore.objects.create(
            nome=self.user.username,
            display_name="Esploratore",
            role=Giocatore.ROLE_USER,
            active_campaign=self.campaign,
        )
        self.client.force_login(self.user)

    def upload_map(self):
        return self.client.post(
            "/api/travel/maps/",
            data={
                "envelope": json.dumps(
                    {
                        "action": "travel.createMap",
                        "requestId": "travel-upload",
                        "payload": {"name": "Tamriel", "categoryId": self.category.id},
                    }
                ),
                "file": SimpleUploadedFile("tamriel.png", b"map-image", content_type="image/png"),
            },
            HTTP_X_REDJANGO_REQUEST_ID="travel-upload",
        )

    def test_staff_player_cannot_use_master_map_controls_but_can_place_markers(self):
        denied = self.upload_map()
        self.assertEqual(denied.status_code, 403)

        self.profile.role = Giocatore.ROLE_MASTER
        self.profile.save(update_fields=["role"])
        created = self.upload_map()
        self.assertEqual(created.status_code, 201)
        travel_map = created.json()["data"]["map"]
        self.assertTrue(travel_map["isDefault"])

        self.profile.role = Giocatore.ROLE_USER
        self.profile.save(update_fields=["role"])
        denied_grid = self.client.patch(
            f"/api/travel/maps/{travel_map['id']}/",
            data=json.dumps({"payload": {"operation": "saveGrid", "grid": {"cols": 8, "rows": 9}}}),
            content_type="application/json",
        )
        self.assertEqual(denied_grid.status_code, 403)
        denied_save_all = self.client.patch(
            f"/api/travel/maps/{travel_map['id']}/",
            data=json.dumps({"payload": {"operation": "saveAll", "grid": {}, "hexEffects": {}, "markers": []}}),
            content_type="application/json",
        )
        self.assertEqual(denied_save_all.status_code, 403)

        markers = [{"id": "m1", "hex": "2-3", "markerType": "flag-blue", "tag": "Campo", "author": "Esploratore"}]
        saved_marker = self.client.patch(
            f"/api/travel/maps/{travel_map['id']}/",
            data=json.dumps({"payload": {"operation": "saveMarkers", "markers": markers}}),
            content_type="application/json",
        )
        self.assertEqual(saved_marker.status_code, 200)
        self.assertEqual(saved_marker.json()["data"]["map"]["markers"][0]["tag"], "Campo")

    def test_master_can_save_grid_and_hex_effects(self):
        self.profile.role = Giocatore.ROLE_MASTER
        self.profile.save(update_fields=["role"])
        travel_map = self.upload_map().json()["data"]["map"]

        grid_response = self.client.patch(
            f"/api/travel/maps/{travel_map['id']}/",
            data=json.dumps({"payload": {"operation": "saveGrid", "grid": {"orientation": "flat", "cols": 12, "rows": 10, "hexSize": 42}}}),
            content_type="application/json",
        )
        self.assertEqual(grid_response.status_code, 200)
        self.assertEqual(grid_response.json()["data"]["map"]["grid"]["orientation"], "flat")
        self.assertEqual(grid_response.json()["data"]["map"]["grid"]["cols"], 12)

        effects_response = self.client.patch(
            f"/api/travel/maps/{travel_map['id']}/",
            data=json.dumps({"payload": {"operation": "saveEffects", "hexEffects": {
                "1-2": {"black": True, "bw": True, "blur": 99},
                "2-3": {"black": False, "bw": False, "blur": 0},
            }}}),
            content_type="application/json",
        )
        self.assertEqual(effects_response.status_code, 200)
        self.assertEqual(effects_response.json()["data"]["map"]["hexEffects"]["1-2"]["blur"], 20)
        self.assertNotIn("2-3", effects_response.json()["data"]["map"]["hexEffects"])

        save_all_response = self.client.patch(
            f"/api/travel/maps/{travel_map['id']}/",
            data=json.dumps({"payload": {
                "operation": "saveAll",
                "grid": {"orientation": "flat", "cols": 12, "rows": 10, "hexSize": 42, "scale": 2, "offsetX": -321, "offsetY": 654},
                "hexEffects": {"3-4": {"black": True, "bw": False, "blur": 0}},
                "markers": [{"id": "party", "hex": "3-4", "markerType": "flag-green", "tag": "Gruppo", "author": "Master"}],
            }}),
            content_type="application/json",
        )
        self.assertEqual(save_all_response.status_code, 200)
        saved_map = save_all_response.json()["data"]["map"]
        self.assertEqual(saved_map["grid"]["offsetX"], -321)
        self.assertEqual(saved_map["grid"]["offsetY"], 654)
        self.assertIn("3-4", saved_map["hexEffects"])
        self.assertEqual(saved_map["markers"][0]["id"], "party")

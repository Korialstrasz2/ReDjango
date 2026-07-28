import json
from pathlib import Path
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.test import TestCase

from backend.characters.models import PERSONAGGIO_TOT_KEYS, Personaggio
from backend.core.legacy_race_import import import_legacy_races
from backend.core.defaults import V2_SETTING_DEFAULTS

from .admin import GlobalModifiersAdminForm, OggettoAdminForm
from .models import CharacterAssignmentRequest, FamigliaSkill, Giocatore, GlobalModifiers, GruppoFamiglieSkill, Guida, Oggetto, OpzioneTipoOggetto, SettingDefinition, SettingOverride, Theme
from .settings_selectors import global_setting_value
from .settings_services import approve_character_assignment


ENVELOPE_KEYS = {"ok", "requestId", "data", "events", "warnings", "errors"}


class LegacyRaceImportTests(TestCase):
    def row(self, **overrides):
        values = {
            "id": 193,
            "nome": "Dunmer - resistenza al fuoco",
            "fonte_tipo": "razza",
            "fonte_nome": "Dunmer",
            "note_proposte": "Bonus passivo.",
            "effetto_proposto": json.dumps(
                {
                    "tipo": "effetto_extra",
                    "effetto_extra": {
                        "nome": "Resistenza al fuoco",
                        "descrizione": "+1 Resistenza al fuoco, +2 RD fuoco.",
                        "origine": "Dunmer",
                        "effetti": [
                            {"name": "res_fuoco", "operation": "+", "value": "1"},
                            {"name": "rd_fuoco", "operation": "+", "value": "2"},
                        ],
                    },
                }
            ),
            "attivabile_nome": "",
            "attivabile_descrizione": "",
            "costo_en": None,
            "costo_man": None,
            "costo_pa": None,
            "costo_pf": None,
            "costo_pow": None,
            "costo_st": None,
            "durata_turni": None,
        }
        values.update(overrides)
        return values

    @patch("backend.core.legacy_race_import.read_legacy_race_rows")
    def test_import_creates_guide_race_families_passives_and_action_notes(self, read_rows):
        read_rows.return_value = (
            "<h3>Dunmer</h3><p>Guida Elder completa.</p>",
            [
                self.row(),
                self.row(
                    id=194,
                    nome="Dunmer - evoca fantasma",
                    effetto_proposto='{"tipo":"nessuno","effetto_extra":null}',
                    attivabile_nome="Dunmer - evoca fantasma",
                    attivabile_descrizione="Evoca un fantasma di livello -4 una volta al giorno.",
                    costo_pa=0,
                ),
                self.row(
                    id=195,
                    nome="Dunmer - Retaggio Mago",
                    fonte_tipo="subrazza",
                    effetto_proposto=json.dumps(
                        {
                            "tipo": "effetto_extra",
                            "effetto_extra": {
                                "nome": "Mana razziale",
                                "descrizione": "+8 Mana.",
                                "origine": "Retaggio Mago",
                                "effetti": [{"name": "mana", "operation": "+", "value": "8"}],
                            },
                        }
                    ),
                ),
            ],
        )
        character = Personaggio.objects.create(
            nome="Ordinatore",
            nome_interno="legacy-race-import-test",
            razza_1="Dunmer",
            razza_2="Retaggio Mago",
        )

        result = import_legacy_races(Path("unused.sqlite3"))
        character.refresh_from_db()

        self.assertEqual(result["families"], 11)
        self.assertTrue(Guida.objects.filter(nome="Razze", contenuto__contains="Guida Elder").exists())
        self.assertTrue(GruppoFamiglieSkill.objects.filter(slug="razze-sottorazze").exists())
        self.assertEqual(GruppoFamiglieSkill.objects.get(slug="razze-sottorazze").ordine, 41)
        family = FamigliaSkill.objects.get(nome="Dunmer")
        self.assertEqual(family.skills.count(), 4)
        self.assertEqual(character.skill_sbloccate.count(), 4)
        self.assertEqual(character.tot["intelligenza"], 12)
        self.assertGreaterEqual(character.tot["mana"], 8)
        actions = [
            action
            for ownership in character.skill_sbloccate.select_related("skill")
            for action in ownership.skill.azioni_attive
        ]
        self.assertEqual(actions[0]["description"], "Evoca un fantasma di livello -4 una volta al giorno.")


class CoreContractTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="local_master",
            is_staff=True,
        )
        Giocatore.objects.create(
            user=user,
            nome="local_master",
            display_name="Master locale",
            role=Giocatore.ROLE_MASTER,
        )
        self.client.force_login(user)

    def test_item_type_options_drive_admin_picklists_and_reject_case_duplicates(self):
        OpzioneTipoOggetto.objects.create(
            posizione=1,
            valore="arma",
            etichetta="Arma",
        )
        form = OggettoAdminForm(instance=Oggetto(nome="Bozza"))
        self.assertIn(("arma", "Arma"), list(form.fields["tipo_1"].choices))
        self.assertEqual(
            [value for value, _label in form.fields["rarita"].choices],
            ["", 0, 1, 2, 3, 4, 5],
        )

        duplicate = OpzioneTipoOggetto(posizione=1, valore="ARMA")
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_health_uses_response_envelope(self):
        response = self.client.get("/api/health/", HTTP_X_REDJANGO_REQUEST_ID="health-1")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(ENVELOPE_KEYS.issubset(body))
        self.assertTrue(body["ok"])
        self.assertEqual(body["requestId"], "health-1")
        self.assertEqual(body["data"]["service"], "ReDjango")
        self.assertEqual(body["data"]["status"], "pronto")

    def test_shell_mounts_versioned_react_spa_assets(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        for marker in ['id="app"', '/static/frontend/dist/app.css', '/static/frontend/dist/app.js']:
            with self.subTest(marker=marker):
                self.assertIn(marker, html)

        nested_response = self.client.get("/character/123")
        self.assertEqual(nested_response.status_code, 200)
        self.assertIn('id="app"', nested_response.content.decode("utf-8"))

    def test_global_modifier_admin_exposes_and_saves_quick_stat_rules(self):
        profile = GlobalModifiers.objects.create(name="Regole test", value_float={}, value_string={})
        form = GlobalModifiersAdminForm(
            data={
                "name": profile.name,
                "value_float": "{}",
                "value_string": "{}",
                "rule_notes": "",
                "fatigue_percent_per_point": "6.5",
                "fatigue_fixed_per_point": "1.25",
                "general_modifier_percent_per_point": "9",
                "general_modifier_fixed_per_point": "2.5",
                "quick_stat_targets": ["pf", "attacco"],
                "skill_price_modifier_base": "3",
                "skill_price_modifier_max": "9",
                "skill_price_scaling_factor": "0.7",
                "skill_price_scaling_divisor": "1.5",
                "skill_price_spent_xp_discount_cap": "100",
            },
            instance=profile,
        )

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(
            saved.value_string["quick_stat_adjustments"],
            {
                "fatigue_percent_per_point": 6.5,
                "fatigue_fixed_per_point": 1.25,
                "general_modifier_percent_per_point": 9.0,
                "general_modifier_fixed_per_point": 2.5,
                "targets": ["pf", "attacco"],
            },
        )
        self.assertEqual(
            saved.value_string["skill_pricing"],
            {
                "modifier_base": 3.0,
                "modifier_max": 9.0,
                "scaling_factor": 0.7,
                "scaling_divisor": 1.5,
                "spent_xp_discount_cap": 100.0,
            },
        )
        self.assertIsInstance(admin.site._registry[GlobalModifiers].form, type)

    def test_bootstrap_includes_default_guides(self):
        response = self.client.get("/api/bootstrap/", HTTP_X_REDJANGO_REQUEST_ID="bootstrap-guides")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["requestId"], "bootstrap-guides")
        self.assertIn({"id": "guide", "label": "Guide"}, body["data"]["menus"])
        self.assertIn({"id": "settings", "label": "Impostazioni"}, body["data"]["menus"])
        self.assertEqual(body["data"]["security"]["role"], "master")
        self.assertTrue(body["data"]["security"]["showAdminLink"])
        self.assertFalse(body["data"]["security"]["showRoleLabels"])
        self.assertEqual(body["data"]["security"]["hierarchy"], [])
        guides = body["data"]["guides"]
        self.assertEqual(len(guides), 8)
        self.assertEqual(guides[0]["name"], "Regole Varie — ReDjango")
        self.assertTrue(guides[0]["content"])
        rules_guide = guides[0]
        self.assertEqual(rules_guide["content"][0]["type"], "legacy_html")
        rules_html = rules_guide["content"][0]["html"]
        self.assertGreater(len(rules_html), 75_000)
        self.assertIn('href="#combat"', rules_html)
        self.assertIn('id="combat"', rules_html)
        self.assertIn("NON ANCORA IMPLEMENTATO", rules_html)
        self.assertTrue(any(guide["name"] == "Creare e usare le armi" for guide in guides))
        character_guide = next(guide for guide in guides if guide["name"] == "Variabili del personaggio e alchimia")
        guide_text = json.dumps(character_guide["content"], ensure_ascii=False)
        for key in PERSONAGGIO_TOT_KEYS:
            with self.subTest(character_variable=key):
                self.assertIn(f"({key})", guide_text)
        self.assertIn("Borsa dei reagenti e alchimia", guide_text)
        # A guide only carries a divergence warning when it actually diverges;
        # guides that match the system must not invent one.
        for guide in guides[1:]:
            with self.subTest(reviewed_guide=guide["name"]):
                warnings = [
                    block for block in guide["content"]
                    if block.get("title") == "Differenze rispetto al sistema attuale"
                ]
                for warning in warnings:
                    self.assertEqual(warning["type"], "warning")
                    self.assertTrue(warning["text"])
        diverging = {
            guide["name"] for guide in guides
            if any(
                block.get("title") == "Differenze rispetto al sistema attuale"
                for block in guide["content"]
            )
        }
        self.assertEqual(
            diverging,
            {
                "Creare oggetti correttamente",
                "Creare e usare le armi",
                "Creare malattie e stati correttamente",
                "Variabili del personaggio e alchimia",
            },
        )
        self.assertNotEqual(rules_guide["content"][-1].get("type"), "warning")

    def test_guides_do_not_contradict_implemented_market_and_combat(self):
        response = self.client.get("/api/bootstrap/", HTTP_X_REDJANGO_REQUEST_ID="guide-contradictions")
        self.assertEqual(response.status_code, 200)
        guides = response.json()["data"]["guides"]
        names = {guide["name"] for guide in guides}
        self.assertNotIn("Creare negozi correttamente", names)
        self.assertIn("Guida Armi", names)

        weapons = next(guide for guide in guides if guide["name"] == "Guida Armi")
        entries = [block for block in weapons["content"] if block["type"] == "entries"]
        self.assertTrue(entries)
        titles = {item["title"] for block in entries for item in block["items"]}
        self.assertIn("Katana", titles)
        self.assertIn("Mani nude", titles)

        rules_html = guides[0]["content"][0]["html"]
        self.assertNotIn("NEGOZI</h1>\n<aside", rules_html)
        self.assertNotIn("RISOLUZIONE NON ANCORA IMPLEMENTATA", rules_html)

    def test_character_variable_guide_uses_current_admin_formula_profile(self):
        GlobalModifiers.objects.create(
            name="Formule_base",
            value_float={"pf": 31},
            value_string={
                "formulas": {"pf": "floor(base.pf + 99)"},
                "quick_stat_adjustments": {
                    "fatigue_percent_per_point": 6.5,
                    "fatigue_fixed_per_point": 1.25,
                    "general_modifier_percent_per_point": 9,
                    "general_modifier_fixed_per_point": 2.5,
                    "targets": ["pf", "attacco"],
                },
            },
        )

        response = self.client.get("/api/bootstrap/")

        self.assertEqual(response.status_code, 200)
        guide = next(
            guide
            for guide in response.json()["data"]["guides"]
            if guide["name"] == "Variabili del personaggio e alchimia"
        )
        guide_text = json.dumps(guide["content"], ensure_ascii=False)
        self.assertIn("-{fatigue}% e".format(fatigue=6.5), guide_text)
        self.assertIn("-1.25 fisso", guide_text)
        self.assertIn("+9% e", guide_text)
        self.assertIn("+2.5 fisso", guide_text)
        self.assertIn("Attacco, Punti ferita", guide_text)
        self.assertIn("Valore base attuale: 31", guide_text)
        self.assertIn("Formula attuale: floor(base.pf + 99)", guide_text)


class HierarchicalSettingsTests(TestCase):
    def setUp(self):
        call_command("seed_minimum_data", verbosity=0)
        self.client.force_login(get_user_model().objects.get(username="local_master"))

    def post_settings(self, settings: dict, request_id: str = "settings-save"):
        return self.client.post(
            "/api/settings/",
            data=json.dumps(
                {
                    "action": "settings.save",
                    "requestId": request_id,
                    "context": {"screen": "settings"},
                    "payload": {"settings": settings},
                }
            ),
            content_type="application/json",
        )

    def test_seed_creates_admin_editable_setting_table_without_overwriting_admin_value(self):
        self.assertGreaterEqual(SettingDefinition.objects.count(), len(V2_SETTING_DEFAULTS))
        self.assertFalse(
            SettingDefinition.objects.filter(key="features.experimental_tools").exists()
        )
        movement = SettingDefinition.objects.get(key="combat.base_movement_ap")
        self.assertEqual(movement.base_value, 1)
        self.assertEqual(Theme.objects.count(), 6)
        self.assertSetEqual(
            set(Theme.objects.values_list("slug", flat=True)),
            {"parchment", "midnight", "arcane", "skyrim", "morrowind", "oblivion"},
        )
        accent = SettingDefinition.objects.get(key="appearance.accent_color")
        accent.value = "#123456"
        accent.save(update_fields=["value", "updated_at"])
        SettingDefinition.objects.create(
            key="features.experimental_tools",
            label="Strumenti sperimentali",
            category="funzioni",
            value_type=SettingDefinition.TYPE_BOOL,
            default_value=False,
            value=False,
        )

        call_command("seed_minimum_data", verbosity=0)
        accent.refresh_from_db()

        self.assertEqual(accent.value, "#123456")
        self.assertFalse(
            SettingDefinition.objects.filter(key="features.experimental_tools").exists()
        )
        self.assertIn(SettingDefinition, admin.site._registry)
        self.assertIn(SettingOverride, admin.site._registry)
        self.assertIn(Theme, admin.site._registry)
        self.assertIn(CharacterAssignmentRequest, admin.site._registry)

    def test_combat_movement_cost_is_only_managed_as_a_global_admin_definition(self):
        movement = SettingDefinition.objects.get(key="combat.base_movement_ap")
        self.assertFalse(movement.master_customizable)
        self.assertTrue(movement.metadata["admin_managed"])

        master_response = self.client.get("/api/settings/")
        master_keys = {
            setting["key"] for setting in master_response.json()["data"]["settings"]
        }
        self.assertNotIn(movement.key, master_keys)

        rejected = self.post_settings({movement.key: 7})
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected.json()["errors"][0]["code"], "settings.admin_managed")
        self.assertFalse(SettingOverride.objects.filter(setting=movement).exists())

        User = get_user_model()
        superuser = User.objects.create_superuser(
            username="movement_admin",
            password="test-pass",
        )
        self.client.force_login(superuser)
        admin_response = self.client.get("/api/settings/")
        admin_keys = {
            setting["key"] for setting in admin_response.json()["data"]["settings"]
        }
        self.assertNotIn(movement.key, admin_keys)

        movement.value = 4
        movement.save(update_fields=["value", "updated_at"])
        self.assertEqual(global_setting_value(movement.key), 4)

    def test_access_codes_are_global_admin_definitions_and_never_enter_settings_payload(self):
        keys = {"security.game_master_access_code", "security.game_admin_access_code"}
        definitions = SettingDefinition.objects.filter(key__in=keys)
        self.assertEqual(definitions.count(), 2)
        self.assertTrue(all(definition.metadata["admin_managed"] for definition in definitions))
        response = self.client.get("/api/settings/")
        visible_keys = {setting["key"] for setting in response.json()["data"]["settings"]}
        self.assertTrue(keys.isdisjoint(visible_keys))

    def test_player_can_update_alias_and_request_character_assignment(self):
        User = get_user_model()
        user = User.objects.create_user(username="player_profile")
        self.client.force_login(user)
        character = Personaggio.objects.create(nome="Neria", nome_interno="test-neria")

        alias_response = self.client.post(
            "/api/settings/",
            data=json.dumps({"action": "player.updateAlias", "payload": {"profile": {"alias": "Luna"}}}),
            content_type="application/json",
        )
        self.assertEqual(alias_response.status_code, 200)
        self.assertEqual(alias_response.json()["data"]["player"]["alias"], "Luna")

        request_response = self.client.post(
            "/api/settings/",
            data=json.dumps({"action": "player.requestCharacters", "payload": {"assignmentRequest": {"characterIds": [character.id], "message": "Il mio PG"}}}),
            content_type="application/json",
        )
        self.assertEqual(request_response.status_code, 200)
        assignment = CharacterAssignmentRequest.objects.get(personaggio=character)
        self.assertEqual(assignment.status, CharacterAssignmentRequest.STATUS_PENDING)
        self.assertEqual(assignment.message, "Il mio PG")

        approve_character_assignment(assignment)
        assignment.giocatore.refresh_from_db()
        self.assertIn(character.id, assignment.giocatore.character_ids)
        self.assertEqual(assignment.giocatore.active_character_id, character.id)

    def test_player_can_redeem_django_admin_managed_role_codes(self):
        SettingDefinition.objects.filter(key="security.game_master_access_code").update(value="MASTER-42")
        SettingDefinition.objects.filter(key="security.game_admin_access_code").update(value="ADMIN-84")
        User = get_user_model()
        user = User.objects.create_user(username="role_player")
        self.client.force_login(user)

        invalid = self.client.post(
            "/api/settings/",
            data=json.dumps({"action": "player.redeemMasterCode", "payload": {"roleCode": {"targetRole": "master", "code": "wrong"}}}),
            content_type="application/json",
        )
        self.assertEqual(invalid.status_code, 403)

        promoted = self.client.post(
            "/api/settings/",
            data=json.dumps({"action": "player.redeemMasterCode", "payload": {"roleCode": {"targetRole": "master", "code": "MASTER-42"}}}),
            content_type="application/json",
        )
        self.assertEqual(promoted.status_code, 200)
        self.assertEqual(promoted.json()["data"]["security"]["role"], "master")

        promoted_again = self.client.post(
            "/api/settings/",
            data=json.dumps({"action": "player.redeemAdminCode", "payload": {"roleCode": {"targetRole": "admin", "code": "ADMIN-84"}}}),
            content_type="application/json",
        )
        self.assertEqual(promoted_again.status_code, 200)
        self.assertEqual(promoted_again.json()["data"]["security"]["role"], "admin")

    def test_django_superuser_can_switch_game_roles_without_losing_django_admin_access(self):
        User = get_user_model()
        user = User.objects.create_superuser(username="django_admin", password="test-pass")
        self.client.force_login(user)

        player = self.client.post(
            "/api/settings/",
            data=json.dumps({"action": "player.selectRole", "payload": {"roleSelection": {"targetRole": "user"}}}),
            content_type="application/json",
        )
        self.assertEqual(player.status_code, 200)
        self.assertEqual(player.json()["data"]["security"]["role"], "user")
        self.assertTrue(player.json()["data"]["security"]["canUseDjangoAdmin"])

        master = self.client.post(
            "/api/settings/",
            data=json.dumps({"action": "player.selectRole", "payload": {"roleSelection": {"targetRole": "master"}}}),
            content_type="application/json",
        )
        self.assertEqual(master.status_code, 200)
        self.assertEqual(master.json()["data"]["security"]["role"], "master")

        admin = self.client.post(
            "/api/settings/",
            data=json.dumps({"action": "player.selectRole", "payload": {"roleSelection": {"targetRole": "admin"}}}),
            content_type="application/json",
        )
        self.assertEqual(admin.status_code, 200)
        self.assertEqual(admin.json()["data"]["security"]["role"], "admin")

    def test_bundled_themes_have_distinct_readable_palettes_and_matching_art(self):
        expected_art = {
            "midnight": "notte.webp",
            "arcane": "arcano.webp",
            "skyrim": "skyrim.webp",
            "morrowind": "morrowind.webp",
            "oblivion": "oblivion.webp",
        }

        def luminance(color: str) -> float:
            channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def contrast(first: str, second: str) -> float:
            light, dark = sorted((luminance(first), luminance(second)), reverse=True)
            return (light + 0.05) / (dark + 0.05)

        for theme in Theme.objects.all():
            with self.subTest(theme=theme.slug):
                self.assertGreaterEqual(contrast(theme.text_color, theme.panel_color), 7)
                self.assertGreaterEqual(contrast(theme.muted_text_color, theme.panel_color), 4.5)
                if theme.slug in expected_art:
                    expected = expected_art[theme.slug]
                    for field_name in (
                        "dashboard_background",
                        "characters_background",
                        "personaggio_background",
                        "media_background",
                        "guide_background",
                        "settings_background",
                        "dice_background",
                        "journal_background",
                        "lore_background",
                        "market_background",
                    ):
                        self.assertTrue(getattr(theme, field_name).file.name.endswith(expected))

    def test_typography_settings_expose_five_fonts_and_the_expanded_scale(self):
        response = self.client.get("/api/settings/")
        settings = {setting["key"]: setting for setting in response.json()["data"]["settings"]}

        self.assertEqual(
            [choice["value"] for choice in settings["appearance.font_family"]["choices"]],
            ["system", "serif", "book", "humanist", "accessible"],
        )
        self.assertEqual(
            settings["appearance.font_scale"]["constraints"],
            {"minimum": 75, "maximum": 175, "step": 5},
        )
        self.assertEqual(settings["appearance.font_scale"]["valueType"], "integer")
        self.assertEqual(settings["accessibility.reduced_motion"]["valueType"], "boolean")
        self.assertEqual(settings["accessibility.contrast_outline"]["valueType"], "select")
        self.assertEqual(settings["accessibility.text_color_aware_outline"]["valueType"], "boolean")
        self.assertFalse(settings["accessibility.text_color_aware_outline"]["value"])
        self.assertEqual(
            [choice["value"] for choice in settings["accessibility.contrast_outline"]["choices"]],
            ["off", "soft", "strong"],
        )
        self.assertEqual(settings["accessibility.contrast_outline"]["value"], "off")
        self.assertEqual(
            [choice["value"] for choice in settings["appearance.density"]["choices"]],
            ["spacious", "comfortable", "compact", "condensed"],
        )

        for scale in (75, 175):
            with self.subTest(scale=scale):
                saved = self.post_settings({"appearance.font_scale": scale}, request_id=f"font-{scale}")
                self.assertEqual(saved.status_code, 200)
                self.assertEqual(saved.json()["data"]["ui"]["appearance.font_scale"], scale)

        for scale in (74, 176):
            with self.subTest(scale=scale):
                rejected = self.post_settings({"appearance.font_scale": scale}, request_id=f"font-{scale}")
                self.assertEqual(rejected.status_code, 400)

        for level in ("soft", "strong", "off"):
            with self.subTest(level=level):
                outlined = self.post_settings(
                    {"accessibility.contrast_outline": level},
                    request_id=f"contrast-outline-{level}",
                )
                self.assertEqual(outlined.status_code, 200)
                self.assertEqual(outlined.json()["data"]["ui"]["accessibility.contrast_outline"], level)

        rejected_outline = self.post_settings(
            {"accessibility.contrast_outline": True},
            request_id="contrast-outline-legacy",
        )
        self.assertEqual(rejected_outline.status_code, 400)

        aware_outline = self.post_settings(
            {"accessibility.text_color_aware_outline": True},
            request_id="text-color-aware-outline",
        )
        self.assertEqual(aware_outline.status_code, 200)
        self.assertTrue(aware_outline.json()["data"]["ui"]["accessibility.text_color_aware_outline"])

    def test_keyboard_shortcuts_have_safe_unique_defaults_and_can_be_changed(self):
        response = self.client.get("/api/settings/")
        shortcuts = {
            setting["key"]: setting
            for setting in response.json()["data"]["settings"]
            if setting["key"].startswith("shortcuts.")
        }

        self.assertEqual(
            {key: setting["value"] for key, setting in shortcuts.items()},
            {
                "shortcuts.dashboard": "Alt+S",
                "shortcuts.characters": "Alt+P",
                "shortcuts.character": "Alt+C",
                "shortcuts.skills": "Alt+A",
                "shortcuts.competencies": "Alt+N",
                "shortcuts.creation": "Alt+K",
                "shortcuts.combat": "Alt+B",
                "shortcuts.travel": "Alt+V",
                "shortcuts.market": "Alt+Q",
                "shortcuts.lore": "Alt+L",
                "shortcuts.media": "Alt+M",
                "shortcuts.guides": "Alt+G",
                "shortcuts.settings": "Alt+I",
                "shortcuts.journal": "Alt+J",
                "shortcuts.dice": "Alt+R",
                "shortcuts.tools": "Alt+T",
            },
        )
        self.assertNotIn("Alt+D", {choice["value"] for choice in shortcuts["shortcuts.journal"]["choices"]})

        saved = self.post_settings({"shortcuts.journal": "Alt+H"})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["data"]["ui"]["shortcuts.journal"], "Alt+H")

    def test_keyboard_shortcuts_reject_duplicate_assignments(self):
        response = self.post_settings({"shortcuts.journal": "Alt+R"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["code"], "settings.shortcut_conflict")
        self.assertEqual(SettingOverride.objects.count(), 0)

    def test_master_sees_user_and_master_settings_but_not_admin_definitions(self):
        response = self.client.get("/api/settings/", HTTP_X_REDJANGO_REQUEST_ID="settings-list")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        keys = {setting["key"] for setting in data["settings"]}
        self.assertEqual(data["security"]["role"], Giocatore.ROLE_MASTER)
        self.assertIn("appearance.theme", keys)
        self.assertIn("master.show_hidden_rolls", keys)
        self.assertNotIn("master.confirm_dangerous_actions", keys)
        self.assertNotIn("master.show_master_tools", keys)
        self.assertNotIn("branding.app_name", keys)
        self.assertNotIn("branding.subtitle", keys)
        self.assertTrue(data["ui"]["master.show_hidden_rolls"])
        self.assertNotIn("security.require_login_for_remote", keys)
        self.assertEqual(data["ui"]["appearance.accent_color"], "#2f6f62")
        self.assertFalse(data["security"]["showRoleLabels"])
        self.assertEqual(data["security"]["hierarchy"], [])
        self.assertEqual(data["theme"]["name"], "Pergamena")
        self.assertTrue(data["theme"]["backgrounds"]["dashboard"].endswith("pergamena-menu.webp"))
        theme_setting = next(setting for setting in data["settings"] if setting["key"] == "appearance.theme")
        self.assertEqual(theme_setting["label"], "Tema dell'interfaccia")
        self.assertIn({"value": "arcane", "label": "Arcano"}, theme_setting["choices"])

    def test_master_can_save_personal_and_master_overrides(self):
        response = self.post_settings(
            {
                "appearance.theme": "arcane",
                "appearance.font_scale": 115,
                "master.show_hidden_rolls": False,
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["ui"]["appearance.theme"], "arcane")
        self.assertEqual(data["ui"]["appearance.font_scale"], 115)
        self.assertEqual(data["theme"]["name"], "Arcano")
        self.assertTrue(data["theme"]["backgrounds"]["dashboard"].endswith("arcano.webp"))
        self.assertEqual(SettingOverride.objects.count(), 3)

    def test_master_cannot_edit_admin_setting(self):
        response = self.post_settings({"appearance.accent_color": "#123456"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["errors"][0]["code"], "settings.forbidden")
        self.assertEqual(SettingOverride.objects.count(), 0)

    def test_user_cannot_see_admin_link_or_edit_master_setting(self):
        giocatore = Giocatore.objects.get(nome="local_master")
        giocatore.role = Giocatore.ROLE_USER
        giocatore.save(update_fields=["role", "updated_at"])

        list_response = self.client.get("/api/settings/")
        keys = {setting["key"] for setting in list_response.json()["data"]["settings"]}
        self.assertTrue(list_response.json()["data"]["security"]["showAdminLink"])
        self.assertTrue(list_response.json()["data"]["security"]["canUseDjangoAdmin"])
        self.assertFalse(list_response.json()["data"]["security"]["canManageGameData"])
        self.assertNotIn("master.show_hidden_rolls", keys)
        self.assertNotIn("shortcuts.tools", keys)
        self.assertNotIn("master.show_hidden_rolls", list_response.json()["data"]["ui"])
        self.assertNotIn("shortcuts.tools", list_response.json()["data"]["ui"])

        save_response = self.post_settings({"master.show_hidden_rolls": False})
        self.assertEqual(save_response.status_code, 403)
        self.assertEqual(save_response.json()["errors"][0]["code"], "settings.forbidden")

        visible_shortcut = self.post_settings({"shortcuts.dashboard": "Alt+T"})
        self.assertEqual(visible_shortcut.status_code, 200)

    def test_superuser_uses_selected_game_role_for_game_settings(self):
        User = get_user_model()
        superuser = User.objects.create_superuser(username="settings_admin", password="test-pass")
        self.client.force_login(superuser)

        response = self.client.get("/api/settings/")
        data = response.json()["data"]
        keys = {setting["key"] for setting in data["settings"]}

        self.assertEqual(data["security"]["role"], Giocatore.ROLE_USER)
        self.assertTrue(data["security"]["showAdminLink"])
        self.assertFalse(data["security"]["showRoleLabels"])
        self.assertEqual(data["security"]["hierarchy"], [])
        self.assertNotIn("security.require_login_for_remote", keys)
        self.assertNotIn("branding.app_name", keys)
        self.assertNotIn("branding.subtitle", keys)

        switched = self.client.post(
            "/api/settings/",
            data=json.dumps({"action": "player.selectRole", "payload": {"roleSelection": {"targetRole": "admin"}}}),
            content_type="application/json",
        )
        admin_data = switched.json()["data"]
        admin_keys = {setting["key"] for setting in admin_data["settings"]}
        self.assertEqual(admin_data["security"]["role"], Giocatore.ROLE_ADMIN)
        self.assertTrue(admin_data["security"]["showRoleLabels"])
        self.assertEqual(len(admin_data["security"]["hierarchy"]), 3)
        self.assertIn("security.access_mode", admin_keys)
        self.assertNotIn("branding.app_name", admin_keys)
        self.assertNotIn("branding.subtitle", admin_keys)

    def test_active_admin_theme_is_selectable_without_frontend_code_changes(self):
        Theme.objects.create(
            slug="rovine",
            name="Rovine",
            description="Tema aggiunto dall'amministratore.",
            is_active=True,
            background_color="#202020",
        )

        list_response = self.client.get("/api/settings/")
        theme_setting = next(
            setting
            for setting in list_response.json()["data"]["settings"]
            if setting["key"] == "appearance.theme"
        )
        self.assertIn({"value": "rovine", "label": "Rovine"}, theme_setting["choices"])

        save_response = self.post_settings({"appearance.theme": "rovine"})
        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(save_response.json()["data"]["theme"]["slug"], "rovine")

    def test_theme_rejects_invalid_admin_visual_values(self):
        theme = Theme(
            slug="non-valido",
            name="Non valido",
            accent_color="verde",
            background_blur=21,
        )

        with self.assertRaises(ValidationError):
            theme.full_clean()


class ThemeManagementTests(TestCase):
    def setUp(self):
        call_command("seed_minimum_data", verbosity=0)
        self.user = get_user_model().objects.create_superuser(username="theme-admin", password="x")
        self.client.force_login(self.user)
        self.become("admin")

    def become(self, role: str):
        return self.client.post(
            "/api/settings/",
            data=json.dumps({"action": "player.selectRole", "payload": {"roleSelection": {"targetRole": role}}}),
            content_type="application/json",
        )

    def action(self, action: str, payload: dict, request_id: str = "theme-action"):
        return self.client.post(
            "/api/v1/actions",
            data=json.dumps(
                {
                    "action": action,
                    "requestId": request_id,
                    "context": {"screen": "settings"},
                    "payload": payload,
                }
            ),
            content_type="application/json",
        )

    def test_payload_exposes_every_screen_including_lore_and_market(self):
        response = self.client.get("/api/v1/management/themes")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        background_keys = [entry["key"] for entry in data["backgroundFields"]]
        self.assertIn("lore", background_keys)
        self.assertIn("market", background_keys)
        self.assertEqual(len(data["themes"]), 6)

        parchment = next(theme for theme in data["themes"] if theme["slug"] == "parchment")
        self.assertTrue(parchment["backgrounds"]["lore_background"]["url"])
        self.assertTrue(parchment["backgrounds"]["market_background"]["url"])
        self.assertTrue(parchment["preview"]["backgrounds"]["lore"])
        self.assertTrue(parchment["preview"]["backgrounds"]["market"])

    def test_accent_gold_and_sidebar_can_fall_back_to_the_global_settings(self):
        theme = Theme.objects.get(slug="midnight")
        response = self.action(
            "management.themes.save",
            {"themeId": theme.id, "theme": {"colors": {"accent_color": "", "gold_color": ""}}},
        )
        self.assertEqual(response.status_code, 200)

        theme.refresh_from_db()
        self.assertEqual(theme.accent_color, "")
        self.assertEqual(theme.gold_color, "")

        saved = response.json()["data"]["management"]["theme"]
        self.assertEqual(saved["colors"]["accent_color"], "")
        self.assertEqual(response.json()["data"]["management"]["fallbacks"]["appearance.accent_color"], "#2f6f62")

    def test_mandatory_colours_cannot_be_cleared(self):
        theme = Theme.objects.get(slug="midnight")
        response = self.action(
            "management.themes.save",
            {"themeId": theme.id, "theme": {"colors": {"text_color": ""}}},
        )
        self.assertEqual(response.status_code, 400)
        theme.refresh_from_db()
        self.assertTrue(theme.text_color)

    def test_duplicate_creates_an_independent_inactive_copy(self):
        source = Theme.objects.get(slug="arcane")
        response = self.action(
            "management.themes.create",
            {"theme": {"name": "Arcano notturno", "duplicateOfId": source.id, "isActive": False}},
        )
        self.assertEqual(response.status_code, 200)

        created = Theme.objects.get(slug="arcano-notturno")
        self.assertFalse(created.is_default)
        self.assertFalse(created.is_active)
        self.assertEqual(created.background_color, source.background_color)
        self.assertEqual(created.metadata["duplicated_from"], "arcane")

    def test_default_theme_moves_and_stays_unique(self):
        target = Theme.objects.get(slug="oblivion")
        response = self.action("management.themes.setDefault", {"themeId": target.id})
        self.assertEqual(response.status_code, 200)

        target.refresh_from_db()
        self.assertTrue(target.is_default)
        self.assertEqual(Theme.objects.filter(is_default=True).count(), 1)

        blocked = self.action(
            "management.themes.save",
            {"themeId": target.id, "theme": {"isActive": False}},
        )
        self.assertEqual(blocked.status_code, 400)

    def test_seeded_themes_are_not_archivable_but_custom_ones_are(self):
        seeded = Theme.objects.get(slug="skyrim")
        self.assertEqual(self.action("management.themes.archive", {"themeId": seeded.id}).status_code, 400)

        self.action("management.themes.create", {"theme": {"name": "Tema di prova"}})
        custom = Theme.objects.get(slug="tema-di-prova")
        self.assertEqual(self.action("management.themes.archive", {"themeId": custom.id}).status_code, 200)

        custom.refresh_from_db()
        self.assertIsNotNone(custom.archived_at)
        self.assertFalse(custom.is_active)

    def test_non_admins_cannot_reach_the_theme_tools(self):
        self.become("user")

        self.assertEqual(self.client.get("/api/v1/management/themes").status_code, 403)
        theme = Theme.objects.get(slug="midnight")
        self.assertEqual(
            self.action("management.themes.save", {"themeId": theme.id, "theme": {"name": "Nope"}}).status_code,
            403,
        )

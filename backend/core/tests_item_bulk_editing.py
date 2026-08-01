from django.test import TestCase

from backend.core.api import ApiError
from backend.core.item_bulk_services import apply_bulk_items, bulk_field_catalog, preview_bulk_items
from backend.core.models import Giocatore, Oggetto, OpzioneTipoOggetto, TipoArma


def _filter(field: str, operator: str, value: str = "") -> dict:
    return {"field": field, "operator": operator, "value": value}


def _action(field: str, operator: str, value: str = "", **extra) -> dict:
    return {"field": field, "operator": operator, "value": value, "replacement": "", "rounding": "keep", "decimals": 0, **extra}


class ItemBulkEditingTests(TestCase):
    """Scoped by a name prefix so a seeded catalogue row cannot join a batch."""

    PREFIX = "Massa"

    @classmethod
    def setUpTestData(cls):
        cls.master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER)
        cls.player = Giocatore.objects.create(nome="player", role=Giocatore.ROLE_USER)
        for posizione, valore in ((1, "pozione"), (1, "armatura"), (2, "bevanda"), (2, "cuoio")):
            OpzioneTipoOggetto.objects.get_or_create(posizione=posizione, valore=valore, defaults={"etichetta": valore, "attiva": True})
        cls.ascia = TipoArma.objects.create(nome="Ascia da massa")
        cls.tonic = Oggetto.objects.create(nome=f"{cls.PREFIX} tonico", tipo_1="pozione", valore=25, peso=1.234)
        cls.beer = Oggetto.objects.create(nome=f"{cls.PREFIX} birra", tipo_1="pozione", tipo_2="bevanda", valore=10, peso=2.5)
        cls.mail = Oggetto.objects.create(nome=f"{cls.PREFIX} maglia", tipo_1="armatura", valore=200, peso=8.0)

    def preview(self, filters, actions, **kwargs):
        return preview_bulk_items(None, self.master, filters, actions, **kwargs)

    def apply(self, filters, actions, token):
        return apply_bulk_items(None, self.master, filters, actions, token)

    def run_batch(self, filters, actions):
        """Preview then apply, the way the tab does, so the token is always the matching one."""
        preview = self.preview(filters, actions)
        return preview, self.apply(filters, actions, preview["token"])

    # ------------------------------------------------------------ filtering --

    def test_filters_combine_with_and(self):
        preview = self.preview(
            [_filter("nome", "istartswith", self.PREFIX), _filter("tipo_1", "eq", "pozione"), _filter("tipo_2", "ne", "bevanda")],
            [_action("valore", "mul", "0.5")],
        )
        self.assertEqual(preview["total"], 1)
        self.assertEqual([row["id"] for row in preview["sample"]], [self.tonic.id])

    def test_empty_matches_a_blank_text_column_and_a_null_number(self):
        blank = Oggetto.objects.create(nome=f"{self.PREFIX} anonimo")
        by_type = self.preview([_filter("nome", "istartswith", self.PREFIX), _filter("tipo_1", "empty")], [_action("speciale", "set", "true")])
        by_value = self.preview([_filter("nome", "istartswith", self.PREFIX), _filter("valore", "empty")], [_action("speciale", "set", "true")])
        self.assertEqual([row["id"] for row in by_type["sample"]], [blank.id])
        self.assertEqual([row["id"] for row in by_value["sample"]], [blank.id])

    def test_in_accepts_a_comma_separated_list(self):
        preview = self.preview(
            [_filter("nome", "istartswith", self.PREFIX), _filter("valore", "in", "10, 200")],
            [_action("speciale", "set", "true")],
        )
        self.assertEqual({row["id"] for row in preview["sample"]}, {self.beer.id, self.mail.id})

    def test_an_unknown_field_is_refused(self):
        with self.assertRaises(ApiError) as caught:
            self.preview([_filter("effects", "eq", "[]")], [_action("valore", "set", "1")])
        self.assertEqual(caught.exception.code, "items.bulk_field_unknown")

    def test_an_operator_the_field_does_not_offer_is_refused(self):
        with self.assertRaises(ApiError) as caught:
            self.preview([_filter("modello", "icontains", "s")], [_action("valore", "set", "1")])
        self.assertEqual(caught.exception.code, "items.bulk_operator_unknown")

    # ------------------------------------------------------------- actions --

    def test_multiplying_an_integer_column_rounds_half_away_from_zero(self):
        _, result = self.run_batch(
            [_filter("nome", "eq", self.tonic.nome)],
            [_action("valore", "mul", "0.5")],
        )
        self.tonic.refresh_from_db()
        self.assertEqual(result["updated"], 1)
        self.assertEqual(self.tonic.valore, 13)

    def test_rounding_a_float_column_to_two_decimals(self):
        self.run_batch(
            [_filter("nome", "eq", self.tonic.nome)],
            [_action("peso", "mul", "1", rounding="round", decimals=2)],
        )
        self.tonic.refresh_from_db()
        self.assertEqual(self.tonic.peso, 1.23)

    def test_text_actions_transform_the_current_value(self):
        self.run_batch(
            [_filter("nome", "eq", self.beer.nome)],
            [_action("lv_loot", "set", "basso"), _action("descrizione", "prepend", "Bevanda. ")],
        )
        self.beer.refresh_from_db()
        self.assertEqual(self.beer.lv_loot, "basso")
        self.assertEqual(self.beer.descrizione, "Bevanda.")

    def test_regex_replace_rewrites_matching_text(self):
        item = Oggetto.objects.create(nome=f"{self.PREFIX} runa", regole_speciali="Infligge 3d6 danni da fuoco.")
        self.run_batch(
            [_filter("nome", "eq", item.nome)],
            [_action("regole_speciali", "regexReplace", r"\d+d\d+", replacement="2d8")],
        )
        item.refresh_from_db()
        self.assertEqual(item.regole_speciali, "Infligge 2d8 danni da fuoco.")

    def test_toggle_flips_a_boolean_per_row(self):
        self.beer.speciale = True
        self.beer.save(update_fields=["speciale"])
        self.run_batch(
            [_filter("nome", "istartswith", self.PREFIX), _filter("tipo_1", "eq", "pozione")],
            [_action("speciale", "toggle")],
        )
        self.tonic.refresh_from_db()
        self.beer.refresh_from_db()
        self.assertTrue(self.tonic.speciale)
        self.assertFalse(self.beer.speciale)

    def test_clearing_a_nullable_column_writes_null_and_a_text_one_writes_blank(self):
        self.run_batch(
            [_filter("nome", "eq", self.mail.nome)],
            [_action("valore", "clear"), _action("lv_loot", "set", "alto")],
        )
        self.run_batch([_filter("nome", "eq", self.mail.nome)], [_action("lv_loot", "clear")])
        self.mail.refresh_from_db()
        self.assertIsNone(self.mail.valore)
        self.assertEqual(self.mail.lv_loot, "")

    def test_the_same_field_cannot_carry_two_actions(self):
        with self.assertRaises(ApiError) as caught:
            self.preview([], [_action("valore", "inc", "5"), _action("valore", "mul", "2")])
        self.assertEqual(caught.exception.code, "items.bulk_action_duplicated")

    def test_a_recipe_without_actions_is_refused(self):
        with self.assertRaises(ApiError) as caught:
            self.preview([_filter("nome", "istartswith", self.PREFIX)], [])
        self.assertEqual(caught.exception.code, "items.bulk_actions_required")

    def test_dividing_by_zero_is_refused_before_anything_is_written(self):
        with self.assertRaises(ApiError) as caught:
            self.preview([_filter("nome", "istartswith", self.PREFIX)], [_action("valore", "div", "0")])
        self.assertEqual(caught.exception.code, "items.bulk_division_by_zero")

    def test_an_invalid_regex_is_refused_at_normalisation(self):
        with self.assertRaises(ApiError) as caught:
            self.preview([], [_action("descrizione", "regexReplace", "([")])
        self.assertEqual(caught.exception.code, "items.bulk_regex_invalid")

    # ---------------------------------------------------------- validation --

    def test_a_type_that_is_not_configured_is_refused(self):
        with self.assertRaises(ApiError) as caught:
            self.preview([_filter("nome", "istartswith", self.PREFIX)], [_action("tipo_1", "set", "inventato")])
        self.assertEqual(caught.exception.code, "items.type_not_configured")

    def test_a_rarity_outside_the_allowed_range_is_refused(self):
        with self.assertRaises(ApiError) as caught:
            self.preview([_filter("nome", "istartswith", self.PREFIX)], [_action("rarita", "set", "9")])
        self.assertEqual(caught.exception.code, "items.rarity_invalid")

    def test_a_negative_weight_is_refused(self):
        with self.assertRaises(ApiError) as caught:
            self.preview([_filter("nome", "istartswith", self.PREFIX)], [_action("peso", "set", "-3")])
        self.assertEqual(caught.exception.code, "items.negative_value")

    def test_an_elder_effect_over_the_column_length_is_reported_per_row(self):
        long_text = "x" * 250
        item = Oggetto.objects.create(nome=f"{self.PREFIX} verboso", effetto_1=long_text)
        preview = self.preview([_filter("nome", "eq", item.nome)], [_action("effetto_1", "append", "y" * 20)])
        self.assertEqual(preview["changed"], 0)
        self.assertEqual(preview["issues"][0]["id"], item.id)
        self.assertEqual(preview["token"], "")

    def test_an_unknown_weapon_type_is_refused(self):
        with self.assertRaises(ApiError) as caught:
            self.preview([_filter("nome", "istartswith", self.PREFIX)], [_action("tipo_arma", "set", "999999")])
        self.assertEqual(caught.exception.code, "items.bulk_weapon_type_unknown")

    def test_a_batch_that_would_duplicate_a_name_never_writes(self):
        preview = self.preview(
            [_filter("nome", "istartswith", self.PREFIX), _filter("tipo_1", "eq", "pozione")],
            [_action("nome", "set", f"{self.PREFIX} unico")],
        )
        self.assertEqual(preview["token"], "")
        self.assertTrue(any(issue["field"] == "nome" for issue in preview["issues"]))
        with self.assertRaises(ApiError) as caught:
            self.apply(preview["filters"], preview["actions"], "any-token")
        self.assertEqual(caught.exception.code, "items.bulk_token_stale")
        self.tonic.refresh_from_db()
        self.assertEqual(self.tonic.nome, f"{self.PREFIX} tonico")

    def test_a_rename_that_collides_only_after_the_preview_is_still_refused(self):
        """The token covers the match set, so a clash created outside it slips past it."""
        filters = [_filter("nome", "eq", self.mail.nome)]
        actions = [_action("nome", "set", f"{self.PREFIX} occupato")]
        token = self.preview(filters, actions)["token"]
        self.assertTrue(token)
        Oggetto.objects.create(nome=f"{self.PREFIX} occupato")
        with self.assertRaises(ApiError) as caught:
            self.apply(filters, actions, token)
        self.assertEqual(caught.exception.code, "items.duplicate_name")
        self.mail.refresh_from_db()
        self.assertEqual(self.mail.nome, f"{self.PREFIX} maglia")

    def test_the_preview_already_reports_a_rename_onto_an_existing_item(self):
        Oggetto.objects.create(nome=f"{self.PREFIX} preso")
        preview = self.preview([_filter("nome", "eq", self.mail.nome)], [_action("nome", "set", f"{self.PREFIX} preso")])
        self.assertEqual(preview["token"], "")
        self.assertEqual(preview["issues"][0]["field"], "nome")

    # --------------------------------------------------------------- token --

    def test_apply_without_a_token_is_refused(self):
        filters = [_filter("nome", "eq", self.tonic.nome)]
        actions = [_action("valore", "inc", "5")]
        with self.assertRaises(ApiError) as caught:
            self.apply(filters, actions, "")
        self.assertEqual(caught.exception.code, "items.bulk_token_stale")
        self.tonic.refresh_from_db()
        self.assertEqual(self.tonic.valore, 25)

    def test_a_token_from_a_different_recipe_is_refused(self):
        filters = [_filter("nome", "eq", self.tonic.nome)]
        stale = self.preview(filters, [_action("valore", "inc", "5")])["token"]
        with self.assertRaises(ApiError) as caught:
            self.apply(filters, [_action("valore", "inc", "500")], stale)
        self.assertEqual(caught.exception.code, "items.bulk_token_stale")

    def test_a_token_goes_stale_when_the_match_set_grows(self):
        filters = [_filter("nome", "istartswith", self.PREFIX), _filter("tipo_1", "eq", "pozione")]
        actions = [_action("valore", "inc", "5")]
        token = self.preview(filters, actions)["token"]
        Oggetto.objects.create(nome=f"{self.PREFIX} elisir", tipo_1="pozione", valore=1)
        with self.assertRaises(ApiError) as caught:
            self.apply(filters, actions, token)
        self.assertEqual(caught.exception.code, "items.bulk_token_stale")

    def test_a_recipe_that_changes_nothing_gets_no_token(self):
        preview = self.preview([_filter("nome", "eq", self.tonic.nome)], [_action("valore", "set", "25")])
        self.assertEqual(preview["changed"], 0)
        self.assertEqual(preview["token"], "")

    # ------------------------------------------------------------- outcomes --

    def test_only_rows_that_actually_change_are_counted_and_saved(self):
        self.beer.valore = 99
        self.beer.save(update_fields=["valore"])
        _, result = self.run_batch(
            [_filter("nome", "istartswith", self.PREFIX), _filter("tipo_1", "eq", "pozione")],
            [_action("valore", "set", "99")],
        )
        self.assertEqual(result["matched"], 2)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["unchanged"], 1)

    def test_archiving_in_batch_moves_the_soft_delete_timestamp_too(self):
        self.run_batch([_filter("nome", "eq", self.mail.nome)], [_action("archiviato", "set", "true")])
        self.mail.refresh_from_db()
        self.assertTrue(self.mail.archiviato)
        self.assertIsNotNone(self.mail.archived_at)
        self.run_batch([_filter("nome", "eq", self.mail.nome)], [_action("archiviato", "set", "false")])
        self.mail.refresh_from_db()
        self.assertFalse(self.mail.archiviato)
        self.assertIsNone(self.mail.archived_at)

    def test_writing_the_rules_in_batch_clears_the_descriptive_review(self):
        item = Oggetto.objects.create(nome=f"{self.PREFIX} anello", tipo_1="anello", effetto_1="+1 potere free Alterazione")
        self.run_batch([_filter("nome", "eq", item.nome)], [_action("regole_speciali", "set", "Regola riscritta.")])
        item.refresh_from_db()
        self.assertEqual(item.metadata["descriptiveEffectsReviewed"], ["+1 potere free Alterazione"])

    def test_the_preview_reports_the_before_and_after_of_each_field(self):
        preview = self.preview([_filter("nome", "eq", self.tonic.nome)], [_action("valore", "inc", "5")])
        self.assertEqual(preview["sample"][0]["changes"], [{"field": "valore", "label": "Valore", "before": "25", "after": "30"}])

    # --------------------------------------------------------- permissions --

    def test_players_cannot_preview(self):
        with self.assertRaises(ApiError) as caught:
            preview_bulk_items(None, self.player, [], [_action("valore", "inc", "1")])
        self.assertEqual(caught.exception.status, 403)

    def test_players_cannot_apply(self):
        with self.assertRaises(ApiError) as caught:
            apply_bulk_items(None, self.player, [], [_action("valore", "inc", "1")], "whatever")
        self.assertEqual(caught.exception.status, 403)

    # ---------------------------------------------------------- field list --

    def test_the_field_catalogue_never_exposes_a_structured_column(self):
        names = {field["name"] for field in bulk_field_catalog()["fields"]}
        self.assertFalse(names & {"effects", "weapon_profile", "media", "metadata"})

    def test_the_field_catalogue_offers_the_configured_item_types(self):
        fields = {field["name"]: field for field in bulk_field_catalog()["fields"]}
        self.assertIn("pozione", {choice["value"] for choice in fields["tipo_1"]["choices"]})
        self.assertIn(str(self.ascia.id), {choice["value"] for choice in fields["tipo_arma"]["choices"]})

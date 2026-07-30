from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.characters.models import Personaggio
from backend.core.api import ApiError
from backend.core.models import DatiCampagna, Giocatore, NomiRazzeInfo
from backend.core.naming_rules import (
    GENDER_FEMALE,
    GENDER_MALE,
    join_name,
    normalize_display,
    normalize_gender,
    pick,
    pool_for_gender,
    resolve_gender,
)
from backend.core.naming_selectors import name_catalog_payload
from backend.core.naming_services import generate_name
from backend.lore.models import PersonaggioLore


class NamingRulesTests(TestCase):
    """Le regole pure: nessun database, nessun provider."""

    def test_orsimer_patronymic_never_separates_the_particle(self):
        # Elder produceva «Mog gro- Burz», con lo spazio di troppo.
        self.assertEqual(join_name("Mog", "Burz", race="Orsimer", gender=GENDER_MALE), "Mog gro-Burz")
        self.assertEqual(join_name("Bagrak", "Burz", race="Orsimer", gender=GENDER_FEMALE), "Bagrak gra-Burz")

    def test_other_races_join_with_a_plain_space(self):
        self.assertEqual(join_name("Rathas", "Dren", race="Dunmer", gender=GENDER_MALE), "Rathas Dren")

    def test_missing_surname_returns_the_first_name_alone(self):
        self.assertEqual(join_name("Teeus", "", race="Argoniano", gender=GENDER_MALE), "Teeus")
        self.assertEqual(join_name("Teeus", "   ", race="Orsimer", gender=GENDER_MALE), "Teeus")

    def test_khajiit_prefix_keeps_its_canonical_lowercase(self):
        self.assertEqual(normalize_display("Do'zirr"), "Do'zirr")
        self.assertEqual(normalize_display("j'zargo"), "J'zargo")
        self.assertEqual(normalize_display("  ra'savi   Custode-Del-Cielo "), "Ra'savi Custode-Del-Cielo")

    def test_gender_aliases_and_random(self):
        self.assertEqual(normalize_gender("Maschio"), GENDER_MALE)
        self.assertEqual(normalize_gender("female"), GENDER_FEMALE)
        self.assertEqual(normalize_gender("indifferente"), "casuale")
        self.assertEqual(normalize_gender("pesce"), "")
        self.assertIn(resolve_gender("casuale"), (GENDER_MALE, GENDER_FEMALE))
        self.assertEqual(resolve_gender(GENDER_MALE), GENDER_MALE)

    def test_pick_is_uniform_and_has_no_head_bias(self):
        """Elder pesava 1.5 il primo elemento di ogni lista: un vantaggio deciso
        dall'ordine del file. Con 4000 estrazioni su due voci lo squilibrio
        sarebbe evidente."""
        pool = ["primo", "secondo"]
        counts = {"primo": 0, "secondo": 0}
        for _ in range(4000):
            counts[pick(pool)] += 1
        self.assertLess(abs(counts["primo"] - counts["secondo"]), 400)

    def test_pick_avoids_excluded_names_but_never_returns_empty(self):
        self.assertEqual(pick(["solo"], exclude=["altro"]), "solo")
        # Bacino esaurito dalle esclusioni: meglio un doppione che nessun nome.
        self.assertEqual(pick(["solo"], exclude=["solo"]), "solo")
        self.assertEqual(pick([]), "")

    def test_unisex_pool_falls_back_to_the_other_gender(self):
        self.assertEqual(pool_for_gender(["A", "B"], [], GENDER_FEMALE), ["A", "B"])
        self.assertEqual(pool_for_gender([], ["C"], GENDER_MALE), ["C"])


class NamingServiceTests(TestCase):
    def setUp(self):
        self.campaign = DatiCampagna.objects.create(nome="Sanguine", attiva=True)
        self.user = get_user_model().objects.create_user(username="dm", password="Fortissima-1")
        self.giocatore = Giocatore.objects.create(
            user=self.user, nome="dm", display_name="Il DM",
            role=Giocatore.ROLE_MASTER, active_campaign=self.campaign,
        )
        self.dunmer = NomiRazzeInfo.objects.create(
            name="Dunmer", race="Dunmer",
            names_male=["Rathas"], names_female=["Velyn"], surnames=["Dren"],
            description="Popolo delle ceneri.",
        )
        self.telvanni = NomiRazzeInfo.objects.create(
            name="Telvanni", race="Dunmer",
            names_male=["Neloth"], names_female=["Drilas"], surnames=["Telvanni"],
        )

    def test_race_alone_resolves_the_culture_named_after_it(self):
        result = generate_name(self.giocatore, {"race": "Dunmer", "gender": "maschile"})
        self.assertEqual(result["name"], "Rathas Dren")
        self.assertEqual(result["culture"], "Dunmer")

    def test_culture_id_wins_over_the_race_default(self):
        result = generate_name(self.giocatore, {"cultureId": self.telvanni.id, "gender": "maschile"})
        self.assertEqual(result["name"], "Neloth Telvanni")

    def test_random_gender_reports_the_one_it_rolled(self):
        result = generate_name(self.giocatore, {"race": "Dunmer", "gender": "casuale"})
        self.assertEqual(result["requestedGender"], "casuale")
        self.assertIn(result["gender"], ("maschile", "femminile"))

    def test_unknown_race_explains_that_no_pool_is_configured(self):
        with self.assertRaises(ApiError) as caught:
            generate_name(self.giocatore, {"race": "Sciamano di Vetro", "gender": "maschile"})
        self.assertEqual(caught.exception.code, "names.pool_missing")

    def test_empty_pool_is_an_error_not_a_silent_fallback(self):
        """Elder ricadeva su 485 righe di liste hardcoded: un bacino svuotato dal
        Master produceva comunque un nome, preso da un'altra parte."""
        empty = NomiRazzeInfo.objects.create(name="Nedic", race="Nedic", names_male=[], names_female=[])
        with self.assertRaises(ApiError) as caught:
            generate_name(self.giocatore, {"cultureId": empty.id, "gender": "maschile"})
        self.assertEqual(caught.exception.code, "names.pool_empty")

    def test_invalid_gender_is_rejected(self):
        with self.assertRaises(ApiError) as caught:
            generate_name(self.giocatore, {"race": "Dunmer", "gender": "pesce"})
        self.assertEqual(caught.exception.code, "names.gender_invalid")

    def test_a_name_already_used_in_the_campaign_is_flagged(self):
        PersonaggioLore.objects.create(campagna=self.campaign, nome="Rathas Dren")
        result = generate_name(self.giocatore, {"race": "Dunmer", "gender": "maschile"})
        self.assertTrue(result["alreadyUsed"])

    def test_existing_characters_also_count_as_taken(self):
        Personaggio.objects.create(
            nome="Rathas Dren", nome_interno="rathas-dren", tipologia="npc", campagna=self.campaign,
        )
        self.assertTrue(generate_name(self.giocatore, {"race": "Dunmer", "gender": "maschile"})["alreadyUsed"])

    def test_a_free_name_is_not_flagged(self):
        self.assertFalse(generate_name(self.giocatore, {"race": "Dunmer", "gender": "femminile"})["alreadyUsed"])


class NameCatalogTests(TestCase):
    def setUp(self):
        NomiRazzeInfo.objects.create(name="Dunmer", race="Dunmer", names_male=["Rathas"])
        NomiRazzeInfo.objects.create(name="Ashlander", race="Dunmer", names_male=["Sul"])
        # Razza solo narrativa: non è in RACE_CATALOG ma serve per i PNG.
        NomiRazzeInfo.objects.create(name="Dwemer", race="Dwemer", names_male=["Kagrenac"])
        NomiRazzeInfo.objects.create(name="Vuoto", race="Vuoto", names_male=[], names_female=[])

    def test_playable_races_come_first_and_are_marked(self):
        payload = name_catalog_payload()
        races = payload["races"]
        self.assertEqual(races[0]["race"], "Dunmer")
        self.assertTrue(races[0]["playable"])
        self.assertFalse(next(entry for entry in races if entry["race"] == "Dwemer")["playable"])

    def test_the_default_culture_is_the_one_named_after_the_race(self):
        dunmer = next(entry for entry in name_catalog_payload()["races"] if entry["race"] == "Dunmer")
        self.assertEqual(dunmer["defaultCulture"], "Dunmer")
        self.assertEqual(len(dunmer["cultures"]), 2)

    def test_cultures_without_names_are_hidden(self):
        payload = name_catalog_payload()
        self.assertNotIn("Vuoto", [entry["race"] for entry in payload["races"]])
        self.assertEqual(payload["cultureCount"], 3)

from django.test import TestCase

from backend.characters.models import Personaggio, SkillPersonaggio
from backend.core.api import ApiError
from backend.core.models import FamigliaSkill, Giocatore, GruppoFamiglieSkill, Skill
from backend.core.skill_management_selectors import managed_skill_detail, skill_management_overview
from backend.core.skill_management_services import reorder_skill_structure


class SkillManagementBaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.master = Giocatore.objects.create(nome="master", role=Giocatore.ROLE_MASTER)
        cls.player = Giocatore.objects.create(nome="player", role=Giocatore.ROLE_USER)
        cls.group = GruppoFamiglieSkill.objects.create(nome="Gruppo A", slug="gruppo-a", ordine=5)
        cls.other_group = GruppoFamiglieSkill.objects.create(nome="Gruppo B", slug="gruppo-b", ordine=9)
        cls.family = FamigliaSkill.objects.create(nome="Famiglia A", gruppo=cls.group, ordine=3)
        cls.other_family = FamigliaSkill.objects.create(nome="Famiglia B", gruppo=cls.group, ordine=7)

    def make_skill(self, number: int, name: str, **kwargs) -> Skill:
        return Skill.objects.create(
            nome=name, slug=f"skill-{number}", numero=number,
            famiglia=kwargs.pop("famiglia", self.family), **kwargs,
        )


class SkillOwnershipTests(SkillManagementBaseTests):
    def test_a_skill_reports_how_many_characters_bought_it(self):
        skill = self.make_skill(1, "Colpo preciso")
        for index in range(2):
            character = Personaggio.objects.create(nome=f"Eroe {index}", nome_interno=f"eroe-{index}")
            SkillPersonaggio.objects.create(personaggio=character, skill=skill)
        row = next(entry for entry in skill_management_overview()["skills"] if entry["id"] == skill.id)
        self.assertEqual(row["ownerCount"], 2)

    def test_an_unbought_skill_reports_zero_owners(self):
        skill = self.make_skill(2, "Mai comprata")
        row = next(entry for entry in skill_management_overview()["skills"] if entry["id"] == skill.id)
        self.assertEqual(row["ownerCount"], 0)

    def test_the_detail_names_the_owning_characters(self):
        skill = self.make_skill(3, "Posseduta")
        character = Personaggio.objects.create(nome="Zelda", nome_interno="zelda")
        SkillPersonaggio.objects.create(personaggio=character, skill=skill)
        self.assertEqual(managed_skill_detail(skill.id)["owners"], ["Zelda"])


class SkillCataloguePaginationTests(SkillManagementBaseTests):
    def test_a_page_reports_the_total_and_whether_more_remain(self):
        for index in range(12):
            self.make_skill(100 + index, f"Skill {index:02d}")
        first = skill_management_overview(limit=5, offset=0)
        self.assertEqual(first["total"], 12)
        self.assertEqual(len(first["skills"]), 5)
        self.assertTrue(first["hasMore"])
        last = skill_management_overview(limit=5, offset=10)
        self.assertEqual(len(last["skills"]), 2)
        self.assertFalse(last["hasMore"])

    def test_metrics_count_the_whole_catalogue_not_the_page(self):
        for index in range(8):
            self.make_skill(200 + index, f"Metrica {index}")
        payload = skill_management_overview(limit=3)
        self.assertEqual(len(payload["skills"]), 3)
        self.assertEqual(payload["metrics"]["activeSkills"], 8)

    def test_filters_apply_in_the_database(self):
        self.make_skill(300, "Cercabile", famiglia=self.family)
        self.make_skill(301, "Altra", famiglia=self.other_family)
        self.assertEqual(skill_management_overview("Cercabile")["total"], 1)
        self.assertEqual(skill_management_overview(family_id=self.other_family.id)["total"], 1)
        self.assertEqual(skill_management_overview(group_id=self.group.id)["total"], 2)

    def test_archived_skills_are_separable(self):
        active = self.make_skill(400, "Attiva")
        archived = self.make_skill(401, "Archiviata")
        Skill.objects.filter(pk=archived.pk).update(archived_at="2026-01-01T00:00:00Z")
        self.assertEqual([s["id"] for s in skill_management_overview(state="active")["skills"]], [active.id])
        self.assertEqual([s["id"] for s in skill_management_overview(state="archived")["skills"]], [archived.id])


class SkillStructureReorderTests(SkillManagementBaseTests):
    def test_groups_are_renumbered_from_one_in_the_given_order(self):
        reorder_skill_structure(None, self.master, groups=[self.other_group.id, self.group.id])
        self.other_group.refresh_from_db()
        self.group.refresh_from_db()
        self.assertEqual(self.other_group.ordine, 1)
        self.assertEqual(self.group.ordine, 2)

    def test_families_are_renumbered_too(self):
        result = reorder_skill_structure(None, self.master, families=[self.other_family.id, self.family.id])
        self.other_family.refresh_from_db()
        self.family.refresh_from_db()
        self.assertEqual((self.other_family.ordine, self.family.ordine), (1, 2))
        self.assertEqual(result["families"], 2)

    def test_an_unknown_identifier_is_refused_without_partial_writes(self):
        with self.assertRaises(ApiError):
            reorder_skill_structure(None, self.master, groups=[self.group.id, 999999])
        self.group.refresh_from_db()
        self.assertEqual(self.group.ordine, 5)

    def test_players_cannot_reorder(self):
        with self.assertRaises(ApiError):
            reorder_skill_structure(None, self.player, groups=[self.group.id])


class RetiredElderReviewTests(TestCase):
    def test_the_review_model_and_workflow_are_gone(self):
        import backend.core.models as models
        import backend.core.skill_management_services as services
        self.assertFalse(hasattr(models, "SkillMigrationReview"))
        for name in (
            "sync_legacy_skill_reviews",
            "save_legacy_skill_review",
            "import_legacy_skill_review",
            "set_legacy_skill_review_status",
            "default_legacy_skill_source",
        ):
            self.assertFalse(hasattr(services, name), f"{name} should have been removed")

    def test_the_command_line_importer_still_exists(self):
        # The review queue is retired; the CLI import path it was built on is not.
        from backend.core import legacy_skill_import
        self.assertTrue(hasattr(legacy_skill_import, "build_import_run"))

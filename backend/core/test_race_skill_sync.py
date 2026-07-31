"""La sincronizzazione fra RACE_CATALOG e le abilità razziali in banca dati.

Il catalogo da solo non basta: un personaggio che possiede abilità razziali non
legge ``automatic_race_effects``, quindi finché le abilità non vengono
riallineate correggere il catalogo non cambia nulla in gioco.
"""

from django.test import TestCase

from backend.characters.race_rules import RACE_CATALOG
from backend.core.models import FamigliaSkill, GruppoFamiglieSkill, Guida, Skill
from backend.core.race_skill_sync import (
    MANUAL_NOTE_PREFIX,
    RACE_SKILL_GROUP_SLUG,
    plan_race_skill_sync,
    sync_race_guide_text,
    sync_race_skills,
)


class RaceSkillSyncTests(TestCase):
    def setUp(self):
        gruppo = GruppoFamiglieSkill.objects.create(nome="Razze", slug=RACE_SKILL_GROUP_SLUG)
        self.famiglia = FamigliaSkill.objects.create(nome="Sottorazze", gruppo=gruppo)

    def _skill(self, nome, slug, *, race, subrace="", kind="subrazza", **extra):
        self.counter = getattr(self, "counter", 0) + 1
        return Skill.objects.create(
            nome=nome,
            slug=slug,
            numero=self.counter,
            famiglia=self.famiglia,
            metadata={
                "automaticRaceUnlock": True,
                "race": race,
                "subrace": subrace,
                "raceUnlockKind": kind,
            },
            **extra,
        )

    def test_a_subrace_receives_the_catalog_bonus_as_a_passive(self):
        skill = self._skill("Dunmer - Retaggio Mago", "sub-mago", race="Dunmer", subrace="Retaggio Mago")

        sync_race_skills()
        skill.refresh_from_db()

        operation = skill.effetti_passivi[0]["operations"][0]
        self.assertEqual(operation["target"], "mana")
        self.assertEqual(operation["operation"], "add")
        self.assertIn("personaggio.livello", operation["value"])

    def test_a_purely_manual_subrace_gets_a_reminder_and_no_passive(self):
        skill = self._skill(
            "Orsimer - Forgiatore D'Armi", "sub-forgiatore", race="Orsimer", subrace="Forgiatore d'Armi"
        )

        sync_race_skills()
        skill.refresh_from_db()

        self.assertEqual(skill.effetti_passivi, [])
        self.assertTrue(skill.azioni_attive[0]["usageNotes"].startswith(MANUAL_NOTE_PREFIX))

    def test_a_legacy_misspelling_still_finds_its_catalog_entry(self):
        """L'import Elder ha portato «Apprensista»; il catalogo dice «Apprendista»."""
        skill = self._skill(
            "Imperiale - Apprensista", "sub-apprensista", race="Imperiale", subrace="Apprensista"
        )

        planned = next(entry for entry in plan_race_skill_sync() if entry["skill"].id == skill.id)

        self.assertNotEqual(planned["status"], "senza voce di catalogo")

    def test_race_and_base_skills_are_left_alone_unless_the_catalog_claims_them(self):
        """Sono già granulari e corrette: riscriverle dal tratto le romperebbe."""
        base = self._skill(
            "Dunmer - Caratteristiche razziali",
            "base-dunmer",
            race="Dunmer",
            kind="base",
            effetti_passivi=[{"id": "x", "name": "y", "operations": []}],
        )
        power = self._skill(
            "Dunmer - resistenza al fuoco", "elder-racial-trait-193", race="Dunmer", kind="razza"
        )
        claimed = self._skill(
            "Orsimer - danno fisico incrementale", "elder-racial-trait-200", race="Orsimer", kind="razza"
        )

        sync_race_skills()
        base.refresh_from_db()
        power.refresh_from_db()
        claimed.refresh_from_db()

        self.assertEqual(base.effetti_passivi, [{"id": "x", "name": "y", "operations": []}])
        self.assertEqual(power.effetti_passivi, [])
        self.assertEqual(claimed.effetti_passivi[0]["operations"][0]["target"], "tier")
        self.assertEqual(claimed.nome, "Orsimer - Tier fisico incrementale")

    def test_running_twice_changes_nothing_the_second_time(self):
        self._skill("Dunmer - Retaggio Mago", "sub-mago", race="Dunmer", subrace="Retaggio Mago")

        first = sync_race_skills()
        second = sync_race_skills()

        self.assertEqual(first["updated"], 1)
        self.assertEqual(second["updated"], 0)
        self.assertEqual(second["unchanged"], 1)

    def test_every_catalog_subrace_is_reachable_by_the_sync(self):
        """Una sottorazza che il sync non sa abbinare resterebbe muta per sempre."""
        for race, definition in RACE_CATALOG.items():
            for subrace in definition.get("subraces") or {}:
                self._skill(
                    f"{race} - {subrace}",
                    f"sub-{race}-{subrace}".replace(" ", "-").lower(),
                    race=race,
                    subrace=subrace,
                )

        unmatched = [
            entry["skill"].nome
            for entry in plan_race_skill_sync()
            if entry["status"] == "senza voce di catalogo"
        ]

        self.assertEqual(unmatched, [])

    def test_the_stored_race_guide_stops_promising_flat_damage(self):
        guide = Guida.objects.create(
            nome="Razze",
            contenuto="<li>Passivo: +1 danno ad attacchi fisici ogni 3 livelli</li>",
        )

        changed = sync_race_guide_text()
        guide.refresh_from_db()

        self.assertEqual(changed, 1)
        self.assertIn("+1 Tier agli attacchi fisici ogni 3 livelli", guide.contenuto)
        self.assertNotIn("danno ad attacchi fisici", guide.contenuto)

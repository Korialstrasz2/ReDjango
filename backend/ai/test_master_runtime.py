import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.core.api import ApiError
from backend.core.models import (
    FamigliaSkill,
    Giocatore,
    GruppoFamiglieSkill,
    Oggetto,
    Skill,
    SpellDefinition,
    Theme,
)

from . import execution, tools
from .changes.services import (
    add_change_operation,
    apply_change_set,
    create_change_set,
    entity_catalog,
    validate_change_set,
)
from .models import AIAgentProfile, AIChangeOperation, AIExecutionRun, AIProvider
from .services import save_agent
from .tool_context import AIToolExecutionContext


class MasterAIProposalRuntimeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.master_user = user_model.objects.create_user(username="master_ai_runtime_master")
        cls.master = Giocatore.objects.create(
            user=cls.master_user,
            nome="master_ai_runtime_master",
            role=Giocatore.ROLE_MASTER,
        )
        cls.admin_user = user_model.objects.create_user(username="master_ai_runtime_admin")
        cls.admin = Giocatore.objects.create(
            user=cls.admin_user,
            nome="master_ai_runtime_admin",
            role=Giocatore.ROLE_ADMIN,
        )
        cls.player_user = user_model.objects.create_user(username="master_ai_runtime_player")
        cls.player = Giocatore.objects.create(
            user=cls.player_user,
            nome="master_ai_runtime_player",
            role=Giocatore.ROLE_USER,
        )
        group = GruppoFamiglieSkill.objects.create(nome="Runtime", slug="runtime")
        cls.family = FamigliaSkill.objects.create(nome="Runtime", gruppo=group)
        cls.provider = AIProvider.objects.create(
            name="Runtime provider",
            slug="runtime-provider",
            purpose=AIProvider.PURPOSE_CHAT,
            kind=AIProvider.KIND_ANTHROPIC,
            auth_strategy=AIProvider.AUTH_NONE,
            model="runtime-test",
            is_enabled=True,
        )

    def skill_values(self, name: str, number: int, *, magic: bool = False) -> dict:
        values = {
            "name": name,
            "slug": "",
            "number": number,
            "familyId": self.family.id,
            "familyOrder": 0,
            "prerequisiteIds": [],
            "baseXpCost": 0,
            "xpType": "general",
            "rulesCost": "",
            "requirementsText": "",
            "description": "Descrizione di prova",
            "profileTags": {},
            "profileNotes": "",
            "passiveEffects": [],
            "activeReminders": [],
            "magic": magic,
            "spell": None,
            "icon": "runa",
            "notes": "",
        }
        if magic:
            values["spell"] = {
                "tier": "base",
                "range": "Contatto",
                "effectUnit": "Danno",
                "baseMana": 5,
                "effectPerMana": 1,
                "minimumMana": 5,
                "fixedCosts": {},
                "rounding": "none",
                "legacyFormula": "",
                "costNotes": "",
                "combatConfiguration": {},
            }
        return values

    def test_proposer_agent_requires_master_role_and_proposal_tool(self):
        with self.assertRaises(ApiError) as captured:
            save_agent(
                self.master_user,
                self.master,
                {
                    "name": "Invalid proposer",
                    "mode": "proposer",
                    "minimumRole": "user",
                    "providerId": self.provider.id,
                    "toolNames": ["proponi_creazione"],
                    "maxIterations": 4,
                    "routingMode": "off",
                    "isEnabled": True,
                },
            )
        self.assertEqual(captured.exception.code, "ai.proposer_role_invalid")

        with self.assertRaises(ApiError) as captured:
            save_agent(
                self.master_user,
                self.master,
                {
                    "name": "Missing proposal tools",
                    "mode": "proposer",
                    "minimumRole": "master",
                    "providerId": self.provider.id,
                    "toolNames": ["cerca_oggetti"],
                    "maxIterations": 4,
                    "routingMode": "off",
                    "isEnabled": True,
                },
            )
        self.assertEqual(captured.exception.code, "ai.proposer_tools_required")

    def test_read_only_agent_cannot_expose_proposal_tools_even_if_corrupted(self):
        agent = AIAgentProfile.objects.create(
            name="Corrupted read only",
            slug="corrupted-read-only",
            mode=AIAgentProfile.MODE_READ_ONLY,
            minimum_role=Giocatore.ROLE_MASTER,
            provider=self.provider,
            allowed_tools=["cerca_oggetti", "proponi_creazione"],
        )
        reachable = tools.reachable_tools(
            self.master_user,
            self.master,
            agent.allowed_tools,
            agent_mode=agent.mode,
        )
        self.assertEqual([tool.name for tool in reachable], ["cerca_oggetti"])
        result, is_error = tools.execute_tool(
            "proponi_creazione",
            {"tipo": "item", "valori": {"nome": "Non autorizzato"}},
            self.master_user,
            self.master,
            allowed_names=agent.allowed_tools,
            agent_mode=agent.mode,
        )
        self.assertTrue(is_error)
        self.assertIn("non autorizzato", result.lower())
        self.assertFalse(Oggetto.objects.filter(nome="Non autorizzato").exists())

    def test_proposal_tool_requires_context_and_never_writes_domain_records(self):
        result, is_error = tools.execute_tool(
            "proponi_creazione",
            {"tipo": "item", "valori": {"nome": "Senza contesto"}},
            self.master_user,
            self.master,
            agent_mode=AIAgentProfile.MODE_PROPOSER,
        )
        self.assertTrue(is_error)
        self.assertIn("ai.change_context_required", result)

        change_set = create_change_set(self.master_user, self.master, title="Runtime")
        result, is_error = tools.execute_tool(
            "proponi_creazione",
            {"tipo": "item", "valori": {"nome": "Solo proposta"}},
            self.master_user,
            self.master,
            agent_mode=AIAgentProfile.MODE_PROPOSER,
            context=AIToolExecutionContext(change_set=change_set),
        )
        self.assertFalse(is_error, result)
        payload = json.loads(result)
        self.assertEqual(payload["tipo"], "item")
        self.assertEqual(change_set.operations.count(), 1)
        self.assertFalse(Oggetto.objects.filter(nome="Solo proposta").exists())

    def test_proposer_run_creates_and_attaches_change_set(self):
        agent = AIAgentProfile.objects.create(
            name="Runtime proposer",
            slug="runtime-proposer",
            mode=AIAgentProfile.MODE_PROPOSER,
            minimum_role=Giocatore.ROLE_MASTER,
            provider=self.provider,
            allowed_tools=["proponi_creazione"],
        )
        with patch("backend.ai.execution._submit"):
            run = execution.start_chat_run(
                self.master_user,
                self.master,
                {"message": "Crea un oggetto", "agentId": agent.id},
            )
        self.assertEqual(run.status, AIExecutionRun.STATUS_QUEUED)
        self.assertIsNotNone(run.change_set_id)
        self.assertEqual(run.change_set.user_id, self.master_user.id)
        self.assertEqual(run.change_set.agent_id, agent.id)
        self.assertEqual(run.change_set.conversation_id, run.conversation_id)
        self.assertEqual(run.request_payload["changeSetId"], str(run.change_set_id))

    def test_foreign_change_set_cannot_be_reused_by_proposer_run(self):
        agent = AIAgentProfile.objects.create(
            name="Runtime proposer foreign",
            slug="runtime-proposer-foreign",
            mode=AIAgentProfile.MODE_PROPOSER,
            minimum_role=Giocatore.ROLE_MASTER,
            provider=self.provider,
            allowed_tools=["proponi_creazione"],
        )
        foreign = create_change_set(self.admin_user, self.admin, title="Foreign")
        with patch("backend.ai.execution._submit"):
            with self.assertRaises(ApiError) as captured:
                execution.start_chat_run(
                    self.master_user,
                    self.master,
                    {
                        "message": "Continua",
                        "agentId": agent.id,
                        "changeSetId": str(foreign.id),
                    },
                )
        self.assertEqual(captured.exception.code, "ai.change_set_not_found")

    def test_skill_proposal_applies_through_skill_service(self):
        change_set = create_change_set(self.master_user, self.master, title="Skill")
        add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="skill",
            action="create",
            values=self.skill_values("Runtime Skill", 910001),
        )
        ready = validate_change_set(self.master_user, self.master, change_set.id)
        apply_change_set(self.master_user, self.master, change_set.id, ready.validation_token)
        skill = Skill.objects.get(nome="Runtime Skill")
        self.assertEqual(skill.famiglia_id, self.family.id)
        self.assertFalse(hasattr(skill, "spell_definition"))

    def test_spell_facade_creates_magic_skill_and_definition(self):
        change_set = create_change_set(self.master_user, self.master, title="Spell")
        add_change_operation(
            self.master_user,
            self.master,
            change_set.id,
            entity_type="spell",
            action="create",
            values=self.skill_values("Runtime Spell", 910002, magic=True),
        )
        ready = validate_change_set(self.master_user, self.master, change_set.id)
        apply_change_set(self.master_user, self.master, change_set.id, ready.validation_token)
        skill = Skill.objects.get(nome="Runtime Spell")
        definition = SpellDefinition.objects.get(skill=skill)
        self.assertEqual(float(definition.base_mana), 5.0)

    def test_theme_is_admin_only_in_catalog_and_operations(self):
        master_types = {entry["type"] for entry in entity_catalog(self.master_user, self.master)}
        admin_types = {entry["type"] for entry in entity_catalog(self.admin_user, self.admin)}
        self.assertNotIn("theme", master_types)
        self.assertIn("theme", admin_types)

        master_set = create_change_set(self.master_user, self.master, title="Denied theme")
        with self.assertRaises(ApiError) as captured:
            add_change_operation(
                self.master_user,
                self.master,
                master_set.id,
                entity_type="theme",
                action="create",
                values={"name": "Tema negato"},
            )
        self.assertEqual(captured.exception.code, "management.themes.forbidden")
        self.assertFalse(Theme.objects.filter(name="Tema negato").exists())

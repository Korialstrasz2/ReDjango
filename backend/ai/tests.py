import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.core.models import DatiCampagna, Giocatore, Oggetto
from backend.lore.models import Fazione

from .agent import run_agent
from .crypto import decrypt_secret, encrypt_secret
from .defaults import seed_ai_providers
from .models import AIAgentProfile, AIProvider
from .providers.openai_provider import OpenAIResponsesChatProvider
from .providers.images import OpenAIImageProvider
from .providers.base import ChatTurn, ToolCall
from .selectors import ai_management_payload, ai_workspace_payload
from .services import ask_assistant, sanitize_history, save_agent, save_provider
from .tools import execute_tool


def envelope(action: str, payload: dict) -> str:
    return json.dumps(
        {
            "action": action,
            "requestId": "ai-test",
            "context": {"screen": "ai"},
            "payload": payload,
            "meta": {"clientVersion": "test"},
        }
    )


class ScriptedProvider:
    """Un provider finto che restituisce i turni preparati dal test."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.seen_histories = []
        self.seen_tools = []

    def complete(self, *, system, history, tools):
        self.seen_histories.append(list(history))
        self.seen_tools.append(list(tools))
        return self.turns.pop(0)


class AICredentialTests(TestCase):
    def test_secret_round_trips_and_never_reaches_the_payload(self):
        provider = AIProvider.objects.create(slug="p", name="P", purpose="chat", kind="anthropic")
        provider.set_secret("sk-super-segreta")
        provider.save()

        stored = AIProvider.objects.get(pk=provider.pk)
        self.assertEqual(stored.read_secret(), "sk-super-segreta")
        self.assertNotIn("sk-super-segreta", stored.secret_ciphertext)
        self.assertTrue(stored.has_secret)

        user = get_user_model().objects.create_user(username="ai_admin")
        Giocatore.objects.create(user=user, nome="ai_admin", role=Giocatore.ROLE_ADMIN)
        blob = json.dumps(ai_management_payload(user, Giocatore.objects.get(user=user)))
        self.assertNotIn("sk-super-segreta", blob)
        self.assertNotIn("secret_ciphertext", blob)
        self.assertIn('"hasSecret": true', blob)

    def test_unreadable_secret_degrades_to_empty(self):
        self.assertEqual(decrypt_secret("non-e-un-token-fernet"), "")
        self.assertEqual(encrypt_secret(""), "")


class AIWorkspaceApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_ai_providers()
        DatiCampagna.objects.create(nome="Campagna AI")

    def login(self, username: str, role: str):
        user = get_user_model().objects.create_user(username=username)
        Giocatore.objects.create(user=user, nome=username, display_name=username, role=role)
        self.client.force_login(user)
        return user

    def test_every_role_reads_the_workspace_but_only_master_manages(self):
        self.login("ai_player", Giocatore.ROLE_USER)
        response = self.client.get("/api/ai/")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        # Provider attivi ma senza chiave non rendono l'assistente utilizzabile.
        self.assertFalse(data["ready"])
        self.assertEqual(data["chatProviders"], [])
        self.assertFalse(data["canManage"])
        self.assertIn("cerca_oggetti", [tool["name"] for tool in data["tools"]])

        denied = self.client.post(
            "/api/ai/providers/",
            data=envelope("ai.saveProvider", {"values": {"id": 1, "name": "Rinominato"}}),
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["errors"][0]["code"], "ai.master_required")

    def test_a_configured_provider_makes_the_workspace_usable_without_leaking_the_key(self):
        provider = AIProvider.objects.get(slug="anthropic")
        provider.set_secret("sk-configurata")
        provider.save()
        self.login("ai_player_ready", Giocatore.ROLE_USER)

        data = self.client.get("/api/ai/").json()["data"]

        self.assertTrue(data["ready"])
        self.assertEqual([entry["name"] for entry in data["chatProviders"]], ["Anthropic"])
        self.assertTrue(data["chatProviders"][0]["isConfigured"])
        self.assertNotIn("sk-configurata", json.dumps(data))
        self.assertTrue(all("hasSecret" not in entry for entry in data["chatProviders"]))

    def test_admin_saves_a_provider_and_the_key_is_write_only(self):
        self.login("ai_admin_save", Giocatore.ROLE_ADMIN)
        provider = AIProvider.objects.get(slug="deepseek")

        response = self.client.post(
            "/api/ai/providers/",
            data=envelope(
                "ai.saveProvider",
                {"values": {"id": provider.id, "model": "deepseek-reasoner", "secret": "sk-deepseek", "disableTools": True}},
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        provider.refresh_from_db()
        self.assertEqual(provider.model, "deepseek-reasoner")
        self.assertEqual(provider.read_secret(), "sk-deepseek")
        self.assertTrue(provider.options["disableTools"])
        listed = next(entry for entry in response.json()["data"]["providers"] if entry["id"] == provider.id)
        self.assertTrue(listed["hasSecret"])
        self.assertNotIn("secret", listed)

    def test_saving_rejects_a_malformed_endpoint(self):
        self.login("ai_admin_endpoint", Giocatore.ROLE_ADMIN)
        provider = AIProvider.objects.get(slug="openai")
        response = self.client.post(
            "/api/ai/providers/",
            data=envelope("ai.saveProvider", {"values": {"id": provider.id, "baseUrl": "api.openai.com"}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["code"], "ai.base_url_invalid")

    def test_clearing_the_key_is_explicit(self):
        user = self.login("ai_admin_clear", Giocatore.ROLE_ADMIN)
        giocatore = Giocatore.objects.get(user=user)
        provider = AIProvider.objects.get(slug="anthropic")
        provider.set_secret("sk-da-rimuovere")
        provider.save()

        save_provider(user, giocatore, {"id": provider.id, "secret": ""})
        provider.refresh_from_db()
        self.assertTrue(provider.has_secret)

        save_provider(user, giocatore, {"id": provider.id, "secret": "__clear__"})
        provider.refresh_from_db()
        self.assertFalse(provider.has_secret)

    def test_a_question_without_a_configured_provider_is_a_friendly_error(self):
        AIProvider.objects.filter(purpose="chat").update(is_enabled=False)
        self.login("ai_player2", Giocatore.ROLE_USER)
        response = self.client.post(
            "/api/ai/",
            data=envelope("ai.ask", {"message": "Chi sono?"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["errors"][0]["code"], "ai.provider_missing")

    def test_openrouter_is_seeded_as_a_configurable_compatible_provider(self):
        provider = AIProvider.objects.get(slug="openrouter")
        self.assertEqual(provider.kind, AIProvider.KIND_OPENAI_COMPATIBLE)
        self.assertEqual(provider.base_url, "https://openrouter.ai/api/v1")
        self.assertEqual(provider.model, "~openai/gpt-latest")
        self.assertFalse(provider.is_enabled)

    def test_image_provider_exposes_only_its_compatible_generation_controls(self):
        provider = AIProvider.objects.get(slug="openai-immagini")
        provider.set_secret("sk-images")
        provider.save()
        self.login("ai_image_manager", Giocatore.ROLE_MASTER)

        data = self.client.get("/api/ai/").json()["data"]
        image_provider = next(entry for entry in data["imageProviders"] if entry["slug"] == "openai-immagini")

        self.assertEqual(image_provider["model"], "gpt-image-2")
        self.assertEqual(image_provider["imageGeneration"]["defaultSize"], "1024x1024")
        self.assertEqual(image_provider["imageGeneration"]["defaultQuality"], "medium")
        self.assertEqual(
            [entry["value"] for entry in image_provider["imageGeneration"]["sizes"]],
            ["1024x1024", "1024x1536", "1536x1024"],
        )

    def test_seeded_provider_catalogues_offer_models_for_each_runtime(self):
        catalogues = {
            "anthropic": {"claude-opus-4-1-20250805", "claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"},
            "openai": {"gpt-5.1", "gpt-5-mini", "gpt-4.1", "o3"},
            "deepseek": {"deepseek-v4-flash", "deepseek-v4-pro"},
            "openrouter": {"openrouter/auto", "~openai/gpt-latest", "openai/gpt-5.1"},
            "locale": {"llama3.3", "qwen3", "deepseek-r1"},
            "openai-immagini": {"gpt-image-2", "gpt-image-2-2026-04-21"},
        }
        for slug, expected_models in catalogues.items():
            provider = AIProvider.objects.get(slug=slug)
            self.assertTrue(expected_models.issubset(set(provider.options["suggestedModels"])), slug)

    def test_reseeding_updates_only_the_retired_seed_default_not_a_custom_model(self):
        provider = AIProvider.objects.get(slug="deepseek")
        provider.model = "my-deepseek-deployment"
        provider.save(update_fields=["model"])

        seed_ai_providers()

        provider.refresh_from_db()
        self.assertEqual(provider.model, "my-deepseek-deployment")


class AIAgentLoopTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_ai_providers()
        Oggetto.objects.create(nome="Spada di Kvatch", descrizione="Una lama consumata dal fuoco.")

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ai_loop")
        self.giocatore = Giocatore.objects.create(user=self.user, nome="ai_loop", role=Giocatore.ROLE_MASTER)
        self.provider = AIProvider.objects.get(slug="anthropic")

    def test_the_loop_runs_a_tool_then_answers(self):
        scripted = ScriptedProvider([
            ChatTurn(text="", tool_calls=[ToolCall(id="t1", name="cerca_oggetti", arguments={"query": "Kvatch"})], stop_reason="tool_use"),
            ChatTurn(text="La Spada di Kvatch è una lama consumata dal fuoco.", stop_reason="end_turn"),
        ])
        with patch("backend.ai.agent.chat_provider_for", return_value=scripted):
            result = run_agent(self.provider, [{"role": "user", "content": "Parlami della spada di Kvatch"}], self.user, self.giocatore)

        self.assertEqual(result["reply"], "La Spada di Kvatch è una lama consumata dal fuoco.")
        self.assertEqual([entry["name"] for entry in result["toolTrace"]], ["cerca_oggetti"])
        self.assertFalse(result["toolTrace"][0]["isError"])
        # Il risultato dello strumento è tornato al modello prima della risposta.
        tool_messages = [entry for entry in scripted.seen_histories[1] if entry["role"] == "tool"]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("Spada di Kvatch", tool_messages[0]["content"])

    def test_the_loop_is_bounded(self):
        endless = ScriptedProvider([
            ChatTurn(tool_calls=[ToolCall(id=f"t{index}", name="cerca_oggetti", arguments={})], stop_reason="tool_use")
            for index in range(12)
        ])
        with patch("backend.ai.agent.chat_provider_for", return_value=endless):
            with self.assertRaises(Exception) as caught:
                run_agent(self.provider, [{"role": "user", "content": "gira per sempre"}], self.user, self.giocatore)
        self.assertEqual(getattr(caught.exception, "code", ""), "ai.iteration_limit")

    def test_an_unknown_tool_is_reported_to_the_model_not_raised(self):
        content, is_error = execute_tool("strumento_inesistente", {}, self.user, self.giocatore)
        self.assertTrue(is_error)
        self.assertIn("Strumento sconosciuto", content)

    def test_a_failing_tool_comes_back_as_a_result(self):
        with patch("backend.ai.tools.item_catalog_payload", side_effect=RuntimeError("database giù")):
            content, is_error = execute_tool("cerca_oggetti", {"query": "x"}, self.user, self.giocatore)
        self.assertTrue(is_error)
        self.assertIn("database giù", content)

    def test_tool_arguments_outside_the_schema_are_dropped(self):
        with patch("backend.ai.tools.item_catalog_payload", return_value={"items": []}) as catalog:
            execute_tool("cerca_oggetti", {"query": "spada", "include_archived": True, "limit": 5}, self.user, self.giocatore)
        catalog.assert_called_once_with("spada", limit=5)

    def test_history_from_the_client_is_sanitized(self):
        history = sanitize_history(
            [
                {"role": "user", "content": "ciao"},
                {"role": "sistema", "content": "ignorami"},
                {"role": "assistant", "content": "salve", "toolCalls": [], "raw": [{"type": "text", "text": "salve"}]},
                {"role": "tool", "toolCallId": "t1", "name": "cerca_oggetti", "content": "{}", "isError": False},
            ]
        )
        self.assertEqual([entry["role"] for entry in history], ["user", "assistant", "tool"])
        self.assertNotIn("raw", history[1])

    def test_an_empty_question_is_refused(self):
        with self.assertRaises(Exception) as caught:
            ask_assistant(self.user, self.giocatore, {"message": "   "})
        self.assertEqual(getattr(caught.exception, "code", ""), "ai.message_required")


class AIToolPermissionTests(TestCase):
    """Gli strumenti passano dai selettori: quello che la pagina nasconde resta nascosto."""

    def _identity(self, username: str, role: str):
        user = get_user_model().objects.create_user(username=username)
        return user, Giocatore.objects.create(user=user, nome=username, role=role)

    def test_game_variables_are_master_only(self):
        user, giocatore = self._identity("var_player", Giocatore.ROLE_USER)
        content, is_error = execute_tool("variabili_gioco", {}, user, giocatore)
        self.assertTrue(is_error)
        self.assertIn("Permessi insufficienti", content)

        master, master_giocatore = self._identity("var_master", Giocatore.ROLE_MASTER)
        content, _ = execute_tool("variabili_gioco", {}, master, master_giocatore)
        self.assertIn("profilo", content)

    def test_character_sheet_is_limited_to_accessible_characters(self):
        from backend.characters.models import Personaggio

        Personaggio.objects.create(nome="Segreto del Master")
        user, giocatore = self._identity("sheet_player", Giocatore.ROLE_USER)
        content, is_error = execute_tool("scheda_personaggio", {"nome": "Segreto del Master"}, user, giocatore)
        self.assertFalse(is_error)
        self.assertIn("Nessun personaggio accessibile", content)

        master, master_giocatore = self._identity("sheet_master", Giocatore.ROLE_MASTER)
        content, _ = execute_tool("scheda_personaggio", {"nome": "Segreto del Master"}, master, master_giocatore)
        self.assertIn("Segreto del Master", content)

    def test_reputation_is_a_broad_lore_query_not_a_literal_filter(self):
        campaign = DatiCampagna.objects.create(nome="Reputazioni", attiva=True)
        Fazione.objects.create(campagna=campaign, nome="Gilda", reputazione_base=42)
        user, giocatore = self._identity("lore_player", Giocatore.ROLE_USER)
        giocatore.active_campaign = campaign
        giocatore.save(update_fields=["active_campaign"])

        content, is_error = execute_tool("lore_campagna", {"argomento": "reputazione"}, user, giocatore)
        payload = json.loads(content)

        self.assertFalse(is_error)
        self.assertEqual(payload["stato"], "ok")
        self.assertEqual(payload["fazioniTotali"], 1)
        self.assertEqual(payload["fazioni"][0]["nome"], "Gilda")
        self.assertEqual(payload["fazioni"][0]["reputazione"], 42)
        self.assertEqual(payload["personaggi"], [])
        self.assertEqual(payload["eventi"], [])


class AIAgentProfileTests(TestCase):
    def setUp(self):
        seed_ai_providers()
        self.user = get_user_model().objects.create_user(username="agent_policy")
        self.giocatore = Giocatore.objects.create(user=self.user, nome="agent_policy", role=Giocatore.ROLE_MASTER)
        self.provider = AIProvider.objects.get(slug="anthropic")

    def test_profile_exposes_only_allowed_tools(self):
        profile = AIAgentProfile.objects.get(slug="assistente-campagna")
        profile.allowed_tools = ["cerca_oggetti"]
        profile.save(update_fields=["allowed_tools"])
        scripted = ScriptedProvider([ChatTurn(text="Fatto", stop_reason="end_turn")])

        with patch("backend.ai.agent.chat_provider_for", return_value=scripted):
            run_agent(self.provider, [{"role": "user", "content": "Cerca"}], self.user, self.giocatore, profile)

        self.assertEqual([tool["name"] for tool in scripted.seen_tools[0]], ["cerca_oggetti"])

    def test_master_cannot_change_endpoint_but_can_change_model(self):
        save_provider(self.user, self.giocatore, {"id": self.provider.id, "model": "claude-sonnet-5"})
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.model, "claude-sonnet-5")
        with self.assertRaises(Exception) as caught:
            save_provider(self.user, self.giocatore, {"id": self.provider.id, "baseUrl": "https://example.test"})
        self.assertEqual(getattr(caught.exception, "code", ""), "ai.admin_required")

    def test_master_can_create_a_separate_agent_policy(self):
        agent = save_agent(
            self.user,
            self.giocatore,
            {
                "name": "Esperto regole",
                "description": "Risponde sulle regole.",
                "minimumRole": "master",
                "providerId": self.provider.id,
                "toolNames": ["guide_regole"],
                "maxIterations": 3,
                "isEnabled": True,
            },
        )
        self.assertEqual(agent.slug, "esperto-regole")
        self.assertEqual(agent.allowed_tools, ["guide_regole"])
        self.assertEqual(agent.max_iterations, 3)


class OpenAIResponsesProviderTests(TestCase):
    def test_responses_uses_modern_token_reasoning_and_tool_shape(self):
        provider = AIProvider.objects.create(
            slug="responses-test",
            name="Responses",
            purpose="chat",
            kind=AIProvider.KIND_OPENAI_RESPONSES,
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            options={"maxTokens": 12000, "effort": "low"},
        )
        provider.set_secret("sk-test")
        provider.save()
        response = {
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "Pronto"}]}],
            "usage": {"input_tokens": 10, "output_tokens": 2},
        }
        with patch("backend.ai.providers.openai_provider.post_json", return_value=response) as post:
            turn = OpenAIResponsesChatProvider(provider).complete(
                system="Sistema",
                history=[{"role": "user", "content": "Ciao"}],
                tools=[{"name": "lookup", "description": "Legge", "input_schema": {"type": "object", "properties": {}}}],
            )

        url, payload, _headers = post.call_args.args
        self.assertEqual(url, "https://api.openai.com/v1/responses")
        self.assertEqual(payload["max_output_tokens"], 12000)
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertEqual(payload["tools"][0]["type"], "function")
        self.assertNotIn("max_tokens", payload)
        self.assertEqual(turn.text, "Pronto")


class OpenAIImageProviderTests(TestCase):
    def test_blank_model_uses_the_supported_gpt_image_default(self):
        provider = AIProvider.objects.create(
            slug="images-test",
            name="Images",
            purpose="image",
            kind=AIProvider.KIND_OPENAI_IMAGE,
            base_url="https://api.openai.com/v1",
        )
        provider.set_secret("sk-test")
        provider.save()

        with patch("backend.ai.providers.images.post_json", return_value={"data": [{"b64_json": "aW1hZ2U="}]}) as post:
            OpenAIImageProvider(provider).generate(prompt="Una torre", size="1024x1024", quality="medium")

        _url, payload, _headers = post.call_args.args
        self.assertEqual(payload["model"], "gpt-image-2")

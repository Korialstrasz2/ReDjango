import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.core.api import ApiError
from backend.core.models import DatiCampagna, Giocatore, Oggetto
from backend.lore.models import Fazione

from .agent import RunBudget, run_agent
from .crypto import decrypt_secret, encrypt_secret
from .defaults import seed_ai_providers
from .execution import start_chat_run
from .models import AIAgentProfile, AIConversation, AIExecutionRun, AIProvider
from .providers.openai_provider import OpenAIResponsesChatProvider
from .providers.images import OpenAIImageProvider
from .providers.base import ChatTurn, ToolCall
from .providers.catalog import fetch_provider_models
from .selectors import ai_management_payload, ai_workspace_payload
from .services import ask_assistant, sanitize_history, save_agent, save_provider
from .tools import AI_TOOLS, execute_tool


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
        self.seen_systems = []

    def complete(self, *, system, history, tools):
        self.seen_histories.append(list(history))
        self.seen_tools.append(list(tools))
        self.seen_systems.append(system)
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

        denied_read = self.client.get("/api/ai/providers/")
        self.assertEqual(denied_read.status_code, 403)
        self.assertEqual(denied_read.json()["errors"][0]["code"], "ai.master_required")

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

    def test_master_management_redacts_admin_only_endpoints(self):
        self.login("ai_master_redacted", Giocatore.ROLE_MASTER)

        response = self.client.get("/api/ai/providers/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["canManageCredentials"])
        self.assertTrue(all(entry["baseUrl"] == "" for entry in response.json()["data"]["providers"]))

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
            # 640x1024 è il minimo che gpt-image-2 accetta (655.360 pixel) e resta
            # in cima perché è il ritratto più economico.
            ["640x1024", "1024x1024", "1024x1536", "1536x1024"],
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

    def test_live_model_refresh_is_saved_without_exposing_the_key(self):
        self.login("ai_admin_models", Giocatore.ROLE_ADMIN)
        provider = AIProvider.objects.get(slug="openai")
        provider.set_secret("sk-catalogo")
        provider.save()
        catalog = [{
            "id": "gpt-live",
            "label": "GPT Live",
            "contextWindow": 32000,
            "capabilities": {
                "chat": True, "tools": True, "reasoning": True,
                "verbosity": True, "images": False, "imageEditing": False,
            },
        }]

        with patch("backend.ai.services.fetch_provider_models", return_value=catalog):
            response = self.client.post(
                f"/api/ai/providers/{provider.id}/models/",
                data=envelope("ai.refreshModels", {}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        provider.refresh_from_db()
        self.assertEqual(provider.model_catalog, catalog)
        self.assertIsNotNone(provider.model_catalog_refreshed_at)
        self.assertNotIn("sk-catalogo", json.dumps(response.json()))

    def test_model_catalog_capabilities_reject_unsupported_controls(self):
        user = self.login("ai_admin_validation", Giocatore.ROLE_ADMIN)
        giocatore = Giocatore.objects.get(user=user)
        provider = AIProvider.objects.get(slug="openai")
        provider.model_catalog = [{
            "id": "plain-model",
            "label": "Plain model",
            "contextWindow": 16000,
            "capabilities": {
                "chat": True, "tools": True, "reasoning": False,
                "verbosity": False, "images": False, "imageEditing": False,
            },
        }]
        provider.save(update_fields=["model_catalog"])

        with self.assertRaises(ApiError) as raised:
            save_provider(user, giocatore, {"id": provider.id, "model": "plain-model", "effort": "high"})

        self.assertEqual(raised.exception.code, "ai.effort_unsupported")
        with self.assertRaises(ApiError) as token_error:
            save_provider(user, giocatore, {"id": provider.id, "model": "plain-model", "maxTokens": 16001})
        self.assertEqual(token_error.exception.code, "ai.max_tokens_invalid")

    def test_setting_a_default_provider_clears_the_previous_default(self):
        user = self.login("ai_admin_default", Giocatore.ROLE_ADMIN)
        giocatore = Giocatore.objects.get(user=user)
        original = AIProvider.objects.get(slug="anthropic")
        replacement = AIProvider.objects.get(slug="deepseek")

        save_provider(user, giocatore, {"id": replacement.id, "isEnabled": True, "isDefault": True})

        original.refresh_from_db()
        replacement.refresh_from_db()
        self.assertFalse(original.is_default)
        self.assertTrue(replacement.is_default)

    def test_an_agent_pinned_to_a_broken_provider_does_not_silently_fall_back(self):
        ready = AIProvider.objects.get(slug="anthropic")
        ready.set_secret("sk-ready")
        ready.save()
        broken = AIProvider.objects.get(slug="deepseek")
        broken.is_enabled = True
        broken.save(update_fields=["is_enabled"])
        agent = AIAgentProfile.objects.get(slug="assistente-campagna")
        agent.provider = broken
        agent.save(update_fields=["provider"])
        user = self.login("ai_broken_agent", Giocatore.ROLE_USER)

        workspace = ai_workspace_payload(user, Giocatore.objects.get(user=user))

        self.assertEqual(workspace["agents"], [])
        self.assertFalse(workspace["readiness"]["chat"])


class AIExecutionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_ai_providers()
        DatiCampagna.objects.create(nome="Campagna esecuzioni")
        cls.user = get_user_model().objects.create_user(username="ai_runs")
        cls.giocatore = Giocatore.objects.create(
            user=cls.user,
            nome="ai_runs",
            display_name="AI Runs",
            role=Giocatore.ROLE_USER,
        )
        provider = AIProvider.objects.get(slug="anthropic")
        provider.set_secret("sk-runs")
        provider.save()

    def test_chat_requests_are_queued_and_owned_by_the_requesting_user(self):
        self.client.force_login(self.user)
        with patch("backend.ai.execution._submit"):
            response = self.client.post(
                "/api/ai/",
                data=envelope("ai.ask", {"message": "Cosa sappiamo?"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 202)
        run_id = response.json()["data"]["run"]["id"]
        self.assertEqual(response.json()["data"]["run"]["status"], "queued")
        restored = self.client.get("/api/ai/").json()["data"]["activeRun"]
        self.assertEqual(restored["id"], run_id)

        stranger = get_user_model().objects.create_user(username="ai_runs_stranger")
        Giocatore.objects.create(user=stranger, nome="stranger", role=Giocatore.ROLE_USER)
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(f"/api/ai/runs/{run_id}/").status_code, 404)

    def test_cancelling_a_queued_run_discards_its_empty_conversation(self):
        self.client.force_login(self.user)
        with patch("backend.ai.execution._submit"):
            started = self.client.post(
                "/api/ai/",
                data=envelope("ai.ask", {"message": "Domanda annullata"}),
                content_type="application/json",
            )
        run_id = started.json()["data"]["run"]["id"]

        cancelled = self.client.delete(f"/api/ai/runs/{run_id}/")

        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["data"]["run"]["status"], "cancelled")
        self.assertEqual(AIConversation.objects.filter(user=self.user).count(), 0)

    def test_only_the_three_most_recent_conversations_are_kept(self):
        for number in range(4):
            with patch("backend.ai.execution._submit"):
                run = start_chat_run(self.user, self.giocatore, {"message": f"Domanda {number}"})
            AIExecutionRun.objects.filter(pk=run.pk).update(status=AIExecutionRun.STATUS_COMPLETED)

        conversations = list(AIConversation.objects.filter(user=self.user).order_by("created_at"))
        self.assertEqual(len(conversations), 3)
        self.assertEqual([entry.title for entry in conversations], ["Domanda 1", "Domanda 2", "Domanda 3"])

    def test_runtime_budget_stops_token_overruns_and_cancellation(self):
        budget = RunBudget(maximum_tokens=10, cancel_check=lambda: False)
        with self.assertRaises(ApiError) as token_error:
            budget.add_usage(8, 3)
        self.assertEqual(token_error.exception.code, "ai.token_budget")

        cancelled = RunBudget(cancel_check=lambda: True)
        with self.assertRaises(ApiError) as cancel_error:
            cancelled.check()
        self.assertEqual(cancel_error.exception.code, "ai.run_cancelled")


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


class AICharacterSheetSectionTests(TestCase):
    """Fase 0: la scheda restituisce sezioni piccole invece di una whitelist morta."""

    def _identity_with_character(self, username: str, **character_fields):
        from backend.characters.models import Personaggio

        character = Personaggio.objects.create(
            nome="Illaoi", nome_interno=f"{username}-personaggio", **character_fields
        )
        user = get_user_model().objects.create_user(username=username)
        giocatore = Giocatore.objects.create(
            user=user,
            nome=username,
            role=Giocatore.ROLE_USER,
            character_ids=[character.id],
            active_character=character,
        )
        return user, giocatore

    def test_default_section_includes_coins(self):
        user, giocatore = self._identity_with_character("sheet_coins_default", monete=250, livello=4)
        content, is_error = execute_tool("scheda_personaggio", {"nome": "Illaoi"}, user, giocatore)

        payload = json.loads(content)
        self.assertFalse(is_error)
        self.assertEqual(payload["sezione"], "riepilogo")
        self.assertEqual(payload["personaggio"]["coins"], 250)

    def test_economia_section_returns_only_economic_fields(self):
        user, giocatore = self._identity_with_character("sheet_econ", monete=999)
        content, _ = execute_tool("scheda_personaggio", {"nome": "Illaoi", "sezione": "economia"}, user, giocatore)

        payload = json.loads(content)
        self.assertEqual(payload["sezione"], "economia")
        self.assertEqual(payload["personaggio"]["coins"], 999)
        self.assertNotIn("characteristics", payload["personaggio"])
        self.assertNotIn("combat", payload["personaggio"])

    def test_unknown_section_degrades_to_riepilogo(self):
        user, giocatore = self._identity_with_character("sheet_unknown_section", monete=10)
        content, is_error = execute_tool(
            "scheda_personaggio", {"nome": "Illaoi", "sezione": "non_esiste"}, user, giocatore
        )

        payload = json.loads(content)
        self.assertFalse(is_error)
        self.assertEqual(payload["sezione"], "riepilogo")
        self.assertIn("coins", payload["personaggio"])

    def test_no_dead_stats_key_remains(self):
        from .tools import CHARACTER_SHEET_SECTIONS

        for keys in CHARACTER_SHEET_SECTIONS.values():
            self.assertNotIn("stats", keys)


class AIToolResultTruncationTests(TestCase):
    """Fase 0.3: un risultato troppo grande resta JSON valido, mai una stringa spezzata."""

    def test_oversized_list_is_shrunk_with_a_valid_marker_not_a_cut_string(self):
        from .tools import _serialize_tool_result

        huge = {"oggetti": [{"nome": f"Oggetto {index}", "descrizione": "x" * 200} for index in range(500)]}
        encoded = _serialize_tool_result(huge)

        payload = json.loads(encoded)  # solleva se il JSON è stato tagliato a metà
        self.assertTrue(payload.get("troncato"))
        self.assertIn("oggettiTotale", payload)
        self.assertEqual(payload["oggettiTotale"], 500)
        self.assertLess(len(payload["oggetti"]), 500)

    def test_result_with_nothing_shrinkable_still_yields_valid_json(self):
        from .tools import _serialize_tool_result

        huge_string_only = {"descrizione": "x" * 30000}
        encoded = _serialize_tool_result(huge_string_only)

        payload = json.loads(encoded)
        self.assertEqual(payload["errore"], "risultato_troppo_grande")

    def test_small_result_is_untouched(self):
        from .tools import _serialize_tool_result

        small = {"oggetti": [{"nome": "Spada"}]}
        encoded = _serialize_tool_result(small)
        self.assertEqual(json.loads(encoded), small)


class AIAgentContextTests(TestCase):
    """Fase 1: il prompt di sistema dichiara chi sta chiedendo, invece di lasciarlo indovinare."""

    @classmethod
    def setUpTestData(cls):
        seed_ai_providers()

    def setUp(self):
        self.provider = AIProvider.objects.get(slug="anthropic")

    def test_system_prompt_names_the_active_character_and_role(self):
        from backend.characters.models import Personaggio

        character = Personaggio.objects.create(nome="Illaoi", nome_interno="illaoi-context-test", livello=7)
        user = get_user_model().objects.create_user(username="context_player")
        giocatore = Giocatore.objects.create(
            user=user,
            nome="context_player",
            role=Giocatore.ROLE_USER,
            character_ids=[character.id],
            active_character=character,
        )

        scripted = ScriptedProvider([ChatTurn(text="risposta", stop_reason="end_turn")])
        with patch("backend.ai.agent.chat_provider_for", return_value=scripted):
            run_agent(self.provider, [{"role": "user", "content": "quante monete ho?"}], user, giocatore)

        system_prompt = scripted.seen_systems[0]
        self.assertIn("Illaoi", system_prompt)
        self.assertIn("Giocatore", system_prompt)
        self.assertIn("personaggio attivo", system_prompt.lower())

    def test_context_block_does_not_crash_without_characters_or_campaign(self):
        user = get_user_model().objects.create_user(username="context_empty")
        giocatore = Giocatore.objects.create(user=user, nome="context_empty", role=Giocatore.ROLE_USER)

        scripted = ScriptedProvider([ChatTurn(text="risposta", stop_reason="end_turn")])
        with patch("backend.ai.agent.chat_provider_for", return_value=scripted):
            result = run_agent(self.provider, [{"role": "user", "content": "ciao"}], user, giocatore)

        self.assertEqual(result["reply"], "risposta")
        self.assertIn("nessuno", scripted.seen_systems[0])


class AIToolSmokeTests(TestCase):
    """Fase 2: ogni strumento deve poter essere eseguito senza sollevare eccezioni non gestite.

    Chiama `tool.run(...)` direttamente, non `execute_tool`: `execute_tool` incaraverebbe
    un vero bug di programmazione (AttributeError, KeyError) in un normale `{"errore": ...}`,
    rendendolo indistinguibile da un esito atteso.
    """

    @classmethod
    def setUpTestData(cls):
        from backend.characters.models import Personaggio, Zaino
        from backend.combat.models import CombatModifier, CombatModifierState, MapMetadata, MapParticipant, MapType
        from backend.core.defaults import V2_SETTING_DEFAULTS
        from backend.core.models import (
            CampaignLoreEntry,
            Curiosita,
            FamigliaSkill,
            GruppoFamiglieSkill,
            HallOfFameCharacter,
            Negozio,
            OpzioneTipoOggetto,
            ReagenteAlchemico,
            SettingDefinition,
            Skill,
            SpellDefinition,
            TimelineEvent,
            TipoArma,
        )
        from backend.dice_tools.models import DiceRollRecord
        from backend.lore.models import EffettoEventoReputazione, EventoReputazione, RelazioneFazione
        from backend.media_library.models import DatiMappa, UploadedImage

        # market_overview() legge la configurazione Mercato dalle SettingDefinition seed:
        # senza questo, ogni strumento che tocca il mercato solleva ValidationError.
        for definition in V2_SETTING_DEFAULTS:
            if definition["key"].startswith("mercato."):
                SettingDefinition.objects.create(**definition, value=definition["default_value"])

        cls.campaign = DatiCampagna.objects.create(
            nome="Smoke", attiva=True, giorni_da_inizio=12, ora_corrente="Mattino", meteo="Sereno"
        )
        zaino = Zaino.objects.create(nome="Zaino smoke")
        cls.character = Personaggio.objects.create(
            nome="Illaoi",
            nome_interno="illaoi-smoke",
            monete=500,
            livello=5,
            campagna=cls.campaign,
            zaino=zaino,
            tot={"slot_magici": 0, "slot_non_magici": 10, "pf": 40, "mod_carico": 5},
        )
        cls.user = get_user_model().objects.create_user(username="smoke_master")
        cls.giocatore = Giocatore.objects.create(
            user=cls.user,
            nome="smoke_master",
            role=Giocatore.ROLE_MASTER,
            character_ids=[cls.character.id],
            active_character=cls.character,
            active_campaign=cls.campaign,
        )

        item = Oggetto.objects.create(nome="Pozione smoke", tipo_1="pozione", valore=10, rarita=1, lv_loot="1")
        Negozio.objects.create(
            nome="Bottega smoke",
            location_key="skyrim/whiterun",
            categoria="generale",
            livello=1,
            lista_oggetti={"version": 2, "entries": [{"itemId": item.id, "quantity": 3, "unitPrice": 20, "source": "manual"}]},
        )

        group = GruppoFamiglieSkill.objects.create(nome="Smoke group", slug="smoke-group")
        family = FamigliaSkill.objects.create(nome="Smoke family", gruppo=group)
        skill = Skill.objects.create(
            nome="Smoke skill", slug="smoke-skill", numero=999001, famiglia=family, costo_pe=5, tipo_pe="all"
        )
        SpellDefinition.objects.create(
            skill=skill, tier="base", range_text="Vicino", effect_unit="Intensità",
            base_mana=1, effect_per_mana=1, minimum_mana=1,
        )

        TipoArma.objects.create(nome="Spada smoke")
        OpzioneTipoOggetto.objects.create(posizione=1, valore="arma", etichetta="Arma")
        ReagenteAlchemico.objects.create(nome="Radice smoke", colore="rosso", livello=1)

        fazione = Fazione.objects.create(campagna=cls.campaign, nome="Fazione smoke", reputazione_base=10)
        altra = Fazione.objects.create(campagna=cls.campaign, nome="Altra fazione", reputazione_base=0)
        RelazioneFazione.objects.create(origine=fazione, destinazione=altra, coefficiente=0.2)
        evento = EventoReputazione.objects.create(
            campagna=cls.campaign, titolo="Evento smoke", motivo="Un motivo", giorno_campagna=1,
            visibile_ai_giocatori=True,
        )
        EffettoEventoReputazione.objects.create(evento=evento, fazione=fazione, delta=5)

        CampaignLoreEntry.objects.create(
            campagna=cls.campaign, slug="voce-smoke", nome="Voce smoke", sommario="Un sommario", visibilita="player"
        )
        cls.dm_only_entry = CampaignLoreEntry.objects.create(
            campagna=cls.campaign, slug="voce-segreta", nome="Voce segreta del Master", sommario="Solo per il Master", visibilita="dm"
        )
        Curiosita.objects.create(nome="Curiosita smoke", descrizione="Una curiosità", visibile=True)
        HallOfFameCharacter.objects.create(nome="Eroe smoke")
        TimelineEvent.objects.create(nome="Evento timeline smoke", campagna=cls.campaign)

        map_type = MapType.objects.create(name="Tipo smoke", slug="tipo-smoke")
        cls.map = MapMetadata.objects.create(name="Mappa smoke", map_type=map_type, is_default=True)
        MapParticipant.objects.create(map=cls.map, character=cls.character)
        modifier = CombatModifier.objects.create(name="Modificatore smoke")
        CombatModifierState.objects.create(map=cls.map, modifier=modifier, enabled=True)

        cls.non_secret_setting = SettingDefinition.objects.create(
            key="smoke.setting", label="Impostazione smoke", category="Smoke", value_type="string", default_value="ok"
        )

        DiceRollRecord.objects.create(
            giocatore=cls.giocatore, player_name="smoke_master", personaggio=cls.character,
            notation="1d20", rolls=[15], modifier=0, total=15,
        )

        image = UploadedImage.objects.create(title="Mappa viaggio smoke")
        DatiMappa.objects.create(nome="Mappa viaggio smoke", campagna=cls.campaign, tipo="globale", image=image)

    def test_every_tool_runs_without_raising(self):
        required_arguments = {
            "posso_permettermi": {"oggetto": "Pozione"},
            "analisi_abilita": {"nome": "Smoke skill"},
            "perche_reputazione": {"fazione": "Fazione smoke"},
        }
        failures = []
        for tool in AI_TOOLS:
            if getattr(tool, "proposal_only", False):
                continue
            kwargs = required_arguments.get(tool.name, {})
            try:
                tool.run(self.user, self.giocatore, **kwargs)
            except Exception as error:  # noqa: BLE001 - il test deve poter riportare qualunque rottura
                failures.append(f"{tool.name}: {type(error).__name__}: {error}")
        self.assertEqual(failures, [])

    def test_master_only_tools_refuse_a_plain_player(self):
        player_user = get_user_model().objects.create_user(username="smoke_player")
        player = Giocatore.objects.create(user=player_user, nome="smoke_player", role=Giocatore.ROLE_USER)
        for name in ("giocatori", "storico_tiri", "statistiche_tiri", "relazioni_fazioni", "riepilogo_gruppo"):
            content, is_error = execute_tool(name, {}, player_user, player)
            self.assertTrue(is_error, f"{name} should refuse a plain player")

    def test_admin_only_tool_refuses_a_master(self):
        content, is_error = execute_tool("impostazioni", {}, self.user, self.giocatore)
        self.assertTrue(is_error)

    def test_settings_tool_never_exposes_admin_managed_keys(self):
        from backend.core.settings_selectors import ADMIN_MANAGED_SETTING_KEYS
        from backend.core.models import SettingDefinition

        SettingDefinition.objects.create(
            key="security.game_master_access_code", label="Codice Master", category="Sicurezza",
            value_type="string", default_value="segreto",
        )
        admin_user = get_user_model().objects.create_user(username="smoke_admin")
        admin = Giocatore.objects.create(user=admin_user, nome="smoke_admin", role=Giocatore.ROLE_ADMIN)
        content, is_error = execute_tool("impostazioni", {}, admin_user, admin)
        payload = json.loads(content)
        self.assertFalse(is_error)
        keys = {entry["chiave"] for entry in payload["impostazioni"]}
        self.assertFalse(keys & ADMIN_MANAGED_SETTING_KEYS)
        self.assertIn("smoke.setting", keys)

    def test_voci_lore_hides_dm_only_entries_from_a_player(self):
        player_user = get_user_model().objects.create_user(username="lore_player")
        player = Giocatore.objects.create(
            user=player_user, nome="lore_player", role=Giocatore.ROLE_USER, active_campaign=self.campaign,
        )
        content, _ = execute_tool("voci_lore", {}, player_user, player)
        payload = json.loads(content)
        names = {entry["nome"] for entry in payload["voci"]}
        self.assertNotIn("Voce segreta del Master", names)
        self.assertIn("Voce smoke", names)

        content, _ = execute_tool("voci_lore", {}, self.user, self.giocatore)
        payload = json.loads(content)
        names = {entry["nome"] for entry in payload["voci"]}
        self.assertIn("Voce segreta del Master", names)


class ExpandFullAccessProfilesMigrationTests(TestCase):
    """La migrazione 0006 allarga solo i profili che avevano l'insieme storico completo."""

    def test_full_access_profile_gains_new_tools_but_narrowed_profile_does_not(self):
        import importlib

        from django.apps import apps as django_apps

        migration_module = importlib.import_module("backend.ai.migrations.0006_expand_full_access_agent_profiles")

        full_access = AIAgentProfile.objects.create(
            name="Completo", slug="completo-migrazione-test",
            allowed_tools=sorted(migration_module.HISTORICAL_TOOL_NAMES),
        )
        narrowed = AIAgentProfile.objects.create(
            name="Ristretto", slug="ristretto-migrazione-test",
            allowed_tools=["cerca_oggetti", "scheda_personaggio"],
        )

        migration_module.expand_full_access_profiles(django_apps, None)

        full_access.refresh_from_db()
        narrowed.refresh_from_db()
        self.assertIn("posso_permettermi", full_access.allowed_tools)
        self.assertIn("capacita_trasporto", full_access.allowed_tools)
        self.assertEqual(set(narrowed.allowed_tools), {"cerca_oggetti", "scheda_personaggio"})


class AIGuideSearchTests(TestCase):
    """Regressione da «come funziona il viaggio?»: la guida grande deve restituire le regole, non l'indice."""

    LONG_GUIDE = json.dumps([
        {
            "type": "legacy_html",
            "html": (
                "<h1>INDICE</h1><ul><li>Base</li><li>Viaggio</li><li>Combat</li></ul>"
                + "<p>Testo di riempimento sul combattimento e sulle malattie. </p>" * 120
                + "<h2>VIAGGIO</h2><p>In viaggio i PG si muovono a 5 km orari su strada. "
                + "Dopo 5h 30m di viaggio si prende 1 Stanchezza. Il viaggio al buio dimezza la velocità.</p>"
                + "<p>Altro riempimento finale. </p>" * 40
            ),
        }
    ])

    def setUp(self):
        from backend.core.models import Guida

        self.guide = Guida.objects.create(nome="Regole Varie", contenuto=self.LONG_GUIDE, categoria="Regolamento")

    def test_excerpt_reaches_the_rules_section_not_the_table_of_contents(self):
        from .tools import _rules_guide

        payload = _rules_guide(None, None, argomento="viaggio")
        joined = " ".join(payload["guide"][0]["estratti"])

        self.assertEqual(payload["stato"], "ok")
        # Il dato che l'utente ha chiesto e che prima non arrivava mai al modello.
        self.assertIn("5 km orari", joined)
        self.assertIn("Stanchezza", joined)

    def test_content_is_not_double_encoded_json(self):
        from .tools import _rules_guide

        payload = _rules_guide(None, None, argomento="viaggio")
        joined = " ".join(payload["guide"][0]["estratti"])

        # `json.dumps` sul TextField produceva \" e \r\n letterali dentro il testo.
        self.assertNotIn('\\"', joined)
        self.assertNotIn("\\r\\n", joined)
        self.assertNotIn("legacy_html", joined)
        self.assertNotIn("<p>", joined)

    def test_status_distinguishes_no_data_from_no_match(self):
        from backend.core.models import Guida

        from .tools import _rules_guide

        self.assertEqual(_rules_guide(None, None, argomento="tema-inesistente")["stato"], "filtro_senza_risultati")
        Guida.objects.all().delete()
        self.assertEqual(_rules_guide(None, None, argomento="viaggio")["stato"], "nessun_dato")

    def test_result_stays_within_the_tool_character_budget(self):
        from .tools import MAXIMUM_TOOL_RESULT_CHARACTERS, _rules_guide

        encoded = json.dumps(_rules_guide(None, None, argomento="viaggio"), ensure_ascii=False)
        self.assertLess(len(encoded), MAXIMUM_TOOL_RESULT_CHARACTERS)


class AIAgentLoopResilienceTests(TestCase):
    """Un modello che gira a vuoto deve essere fermato e comunque produrre una risposta."""

    @classmethod
    def setUpTestData(cls):
        seed_ai_providers()

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="loop_resilience")
        self.giocatore = Giocatore.objects.create(user=self.user, nome="loop_resilience", role=Giocatore.ROLE_MASTER)
        self.provider = AIProvider.objects.get(slug="anthropic")

    def test_identical_repeated_calls_are_reported_instead_of_re_executed(self):
        repeated = ScriptedProvider([
            ChatTurn(tool_calls=[ToolCall(id="t1", name="guide_regole", arguments={"argomento": "viaggio"})], stop_reason="tool_use"),
            ChatTurn(tool_calls=[ToolCall(id="t2", name="guide_regole", arguments={"argomento": "viaggio"})], stop_reason="tool_use"),
            ChatTurn(text="Ecco quello che ho trovato.", stop_reason="end_turn"),
        ])
        with patch("backend.ai.agent.chat_provider_for", return_value=repeated):
            result = run_agent(self.provider, [{"role": "user", "content": "come funziona il viaggio?"}], self.user, self.giocatore)

        tool_messages = [entry for entry in result["history"] if entry["role"] == "tool"]
        self.assertEqual(len(tool_messages), 2)
        self.assertIn("chiamata_ripetuta", tool_messages[1]["content"])
        self.assertTrue(result["toolTrace"][1]["isError"])

    def test_exhausting_iterations_still_answers_from_what_was_gathered(self):
        turns = [
            ChatTurn(tool_calls=[ToolCall(id=f"t{index}", name="guide_regole", arguments={"argomento": f"tema{index}"})], stop_reason="tool_use")
            for index in range(6)
        ]
        turns.append(ChatTurn(text="Non ho trovato la regola, ma ecco cosa ho verificato.", stop_reason="end_turn"))
        scripted = ScriptedProvider(turns)

        with patch("backend.ai.agent.chat_provider_for", return_value=scripted):
            result = run_agent(self.provider, [{"role": "user", "content": "una domanda difficile"}], self.user, self.giocatore)

        self.assertEqual(result["stopReason"], "iteration_limit")
        self.assertIn("ecco cosa ho verificato", result["reply"])
        # L'ultima chiamata deve essere senza strumenti: è ciò che forza la conclusione.
        self.assertEqual(scripted.seen_tools[-1], [])

    def test_iteration_limit_still_raises_when_the_model_returns_nothing(self):
        turns = [
            ChatTurn(tool_calls=[ToolCall(id=f"t{index}", name="guide_regole", arguments={"argomento": f"tema{index}"})], stop_reason="tool_use")
            for index in range(6)
        ]
        turns.append(ChatTurn(text="   ", stop_reason="end_turn"))
        scripted = ScriptedProvider(turns)

        with patch("backend.ai.agent.chat_provider_for", return_value=scripted):
            with self.assertRaises(Exception) as caught:
                run_agent(self.provider, [{"role": "user", "content": "domanda"}], self.user, self.giocatore)
        self.assertEqual(getattr(caught.exception, "code", ""), "ai.iteration_limit")


class AIScopeRouterTests(TestCase):
    """Fase 3: il router riduce il menu di strumenti quando aiuta, mai a costo della risposta."""

    def setUp(self):
        seed_ai_providers()
        self.user = get_user_model().objects.create_user(username="router_user")
        self.giocatore = Giocatore.objects.create(user=self.user, nome="router_user", role=Giocatore.ROLE_MASTER)
        self.provider = AIProvider.objects.get(slug="anthropic")
        self.profile = AIAgentProfile.objects.get(slug="assistente-campagna")

    def test_router_narrows_the_tool_menu_to_the_chosen_scope(self):
        from .tools import reachable_tools

        scripted = ScriptedProvider(
            [
                ChatTurn(text='["personaggi"]', stop_reason="end_turn"),
                ChatTurn(text="Fatto", stop_reason="end_turn"),
            ]
        )
        with patch("backend.ai.agent.chat_provider_for", return_value=scripted):
            run_agent(
                self.provider, [{"role": "user", "content": "quante monete ho?"}], self.user, self.giocatore, self.profile
            )

        self.assertEqual(len(scripted.seen_systems), 2)
        main_call_tools = {tool["name"] for tool in scripted.seen_tools[1]}
        # `regole` è sempre incluso per progetto: vedi ROUTER_ALWAYS_INCLUDED_SCOPES.
        expected = {
            tool.name for tool in reachable_tools(self.user, self.giocatore, self.profile.allowed_tools)
            if tool.scope in {"personaggi", "regole"}
        }
        self.assertEqual(main_call_tools, expected)
        self.assertLess(len(expected), len(self.profile.allowed_tools))

    def test_router_failure_falls_back_to_every_reachable_tool(self):
        from .tools import reachable_tools

        scripted = ScriptedProvider(
            [
                ChatTurn(text="questo non è un array JSON", stop_reason="end_turn"),
                ChatTurn(text="Fatto comunque", stop_reason="end_turn"),
            ]
        )
        with patch("backend.ai.agent.chat_provider_for", return_value=scripted):
            result = run_agent(
                self.provider, [{"role": "user", "content": "una domanda qualsiasi"}], self.user, self.giocatore, self.profile
            )

        self.assertEqual(result["reply"], "Fatto comunque")
        main_call_tools = {tool["name"] for tool in scripted.seen_tools[1]}
        expected_all = {tool.name for tool in reachable_tools(self.user, self.giocatore, self.profile.allowed_tools)}
        self.assertEqual(main_call_tools, expected_all)

    def test_router_is_skipped_below_the_tool_threshold(self):
        self.profile.allowed_tools = ["cerca_oggetti", "scheda_personaggio"]
        self.profile.save(update_fields=["allowed_tools"])
        scripted = ScriptedProvider([ChatTurn(text="Fatto", stop_reason="end_turn")])
        with patch("backend.ai.agent.chat_provider_for", return_value=scripted):
            run_agent(self.provider, [{"role": "user", "content": "ciao"}], self.user, self.giocatore, self.profile)
        self.assertEqual(len(scripted.seen_systems), 1)

    def test_rules_scope_survives_a_router_that_omits_it(self):
        """«come funziona il viaggio?» veniva instradata su campagna e non raggiungeva le guide."""

        scripted = ScriptedProvider([
            ChatTurn(text='["campagna"]', stop_reason="end_turn"),
            ChatTurn(text="Fatto", stop_reason="end_turn"),
        ])
        with patch("backend.ai.agent.chat_provider_for", return_value=scripted):
            run_agent(
                self.provider, [{"role": "user", "content": "come funziona il viaggio?"}], self.user, self.giocatore, self.profile
            )

        offered = {tool["name"] for tool in scripted.seen_tools[1]}
        self.assertIn("guide_regole", offered)
        self.assertIn("mappe_viaggio", offered)

    def test_routing_mode_off_skips_the_router_even_with_many_tools(self):
        self.profile.routing_mode = AIAgentProfile.ROUTING_OFF
        self.profile.save(update_fields=["routing_mode"])
        scripted = ScriptedProvider([ChatTurn(text="Fatto", stop_reason="end_turn")])
        with patch("backend.ai.agent.chat_provider_for", return_value=scripted):
            run_agent(self.provider, [{"role": "user", "content": "ciao"}], self.user, self.giocatore, self.profile)
        self.assertEqual(len(scripted.seen_systems), 1)


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


class AIModelCatalogTests(TestCase):
    def test_live_catalog_normalizes_models_and_filters_non_chat_products(self):
        provider = AIProvider.objects.create(
            slug="catalog-test",
            name="Catalog",
            purpose=AIProvider.PURPOSE_CHAT,
            kind=AIProvider.KIND_OPENAI_COMPATIBLE,
            auth_strategy=AIProvider.AUTH_NONE,
            base_url="http://127.0.0.1:11434/v1",
            model="chat-pro",
        )
        response = {
            "data": [
                {"id": "chat-pro", "context_length": 32768, "supported_parameters": ["tools", "reasoning"]},
                {"id": "text-embedding-3-large"},
                {"id": "image-alpha"},
            ],
        }

        with patch("backend.ai.providers.catalog.get_json", return_value=response):
            catalog = fetch_provider_models(provider)

        self.assertEqual([entry["id"] for entry in catalog], ["chat-pro"])
        self.assertEqual(catalog[0]["contextWindow"], 32768)
        self.assertTrue(catalog[0]["capabilities"]["tools"])
        self.assertTrue(catalog[0]["capabilities"]["reasoning"])


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

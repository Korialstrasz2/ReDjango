from __future__ import annotations

from django.core.management.base import BaseCommand

from backend.core.models import Giocatore

from backend.ai.models import AIAgentProfile, AIProvider


PROPOSAL_TOOLS = [
    "elenca_entita_modificabili",
    "cerca_record_gestibili",
    "leggi_record_gestibile",
    "proponi_creazione",
    "proponi_modifica",
    "proponi_archiviazione",
    "rimuovi_operazione_proposta",
    "riassumi_proposta",
]


class Command(BaseCommand):
    help = "Crea un provider locale non contattabile e un agente proposer per i test Playwright."

    def handle(self, *args, **options):
        provider, _created = AIProvider.objects.update_or_create(
            slug="e2e-master-ai-no-call",
            defaults={
                "name": "E2E Master AI · nessuna chiamata",
                "purpose": AIProvider.PURPOSE_CHAT,
                "kind": AIProvider.KIND_OPENAI_COMPATIBLE,
                "auth_strategy": AIProvider.AUTH_NONE,
                "base_url": "http://127.0.0.1:9/v1",
                "model": "e2e-no-call",
                "options": {
                    "description": "Fixture Playwright: il test non invia richieste al provider.",
                    "capabilities": {"chat": True, "tools": True},
                },
                "is_enabled": True,
                "is_default": False,
                "order": 999,
                "archived_at": None,
            },
        )
        agent, _created = AIAgentProfile.objects.update_or_create(
            slug="e2e-master-ai-proposer",
            defaults={
                "name": "E2E Master AI",
                "description": "Agente fixture per verificare il workspace senza chiamate esterne.",
                "instructions": "Non viene invocato dai test E2E.",
                "mode": AIAgentProfile.MODE_PROPOSER,
                "minimum_role": Giocatore.ROLE_MASTER,
                "provider": provider,
                "allowed_tools": PROPOSAL_TOOLS,
                "max_iterations": 4,
                "routing_mode": AIAgentProfile.ROUTING_OFF,
                "is_enabled": True,
                "is_default": False,
                "order": 999,
                "archived_at": None,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Fixture Master AI pronta: provider={provider.id}, agent={agent.id}."))

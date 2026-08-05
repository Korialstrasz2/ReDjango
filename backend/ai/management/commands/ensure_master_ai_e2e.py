from __future__ import annotations

from django.core.management.base import BaseCommand

from backend.core.models import Giocatore, Unit

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

E2E_UNIT_NAME = "Bestia E2E Master AI"


class Command(BaseCommand):
    help = "Crea provider, agente proposer e Unit deterministici per i test Playwright Master AI."

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
        unit, _created = Unit.objects.update_or_create(
            nome=E2E_UNIT_NAME,
            defaults={
                "categoria": "Creature E2E",
                "archetipo_descrizione": (
                    "Creatura rapida con chassis deterministico, usata per verificare il launcher Unit di Master AI."
                ),
                "lore_description": "Fixture locale senza dipendenze da Skill, Item o accessori.",
                "notes": "Fixture E2E. L'azione innata è un promemoria manuale.",
                "generation_rules": {
                    "kind": "creature",
                    "coreKey": "",
                    "coreShare": 0.5,
                    "startingXp": 0,
                    "xpPerLevel": {"base": 20, "growth": 1},
                    "competenceXp": {"starting": 5, "base": 15, "growth": 0},
                    "finalSpendingPasses": 4,
                    "magicPolicy": "any",
                    "allowedClassFamilies": [],
                    "allowedReligionFamilies": [],
                    "allowedRaces": [],
                    "allowedSubraces": [],
                    "allowHumanoidStatGrowth": False,
                },
                "archetipo_tags": {},
                "profilo_competenze": {},
                "skill_unlocks": [],
                "equipment_profiles": {},
                "skill_actions": [
                    {
                        "key": "e2e-master-ai-artiglio",
                        "name": "Artiglio E2E",
                        "description": "Il Master risolve manualmente bersaglio, tiro e danno.",
                        "minLevel": 1,
                        "maxLevel": 20,
                        "costs": {"energia": 1, "pa": 2},
                        "trigger": "Azione",
                        "duration": "Istantanea",
                        "icon": "runa",
                    }
                ],
                "stat_profiles": {
                    "baseModifiers": {},
                    "perLevelModifiers": {},
                    "milestones": [],
                    "curves": [
                        {"key": "pf", "profile": "custom", "level1": 12, "level20": 60},
                        {"key": "pa", "profile": "custom", "level1": 7, "level20": 24},
                    ],
                },
                "levels": [],
                "metadata": {"sourceProject": "redjango", "authoring": "e2e-fixture"},
                "archived_at": None,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Fixture Master AI pronta: provider={provider.id}, agent={agent.id}, unit={unit.id}."
            )
        )

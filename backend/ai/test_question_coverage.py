"""Fase 6 del piano di potenziamento AI: copertura delle domande d'oro e invarianti di sicurezza.

Questo file non valuta la prosa del modello: verifica in modo deterministico che, per
ogni forma di domanda della sezione 3 del piano, lo strumento giusto sia raggiungibile
per il ruolo indicato e che il suo risultato contenga davvero il dato atteso. Vedi
Builder_docs/AI_AGENT_UPGRADE_PLAN.md.
"""

from __future__ import annotations

import copy

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.characters.models import Personaggio, Zaino
from backend.core.models import (
    CampaignLoreEntry,
    DatiCampagna,
    FamigliaSkill,
    Giocatore,
    Guida,
    GruppoFamiglieSkill,
    Negozio,
    Oggetto,
    SettingDefinition,
    Skill,
)
from backend.core.defaults import V2_SETTING_DEFAULTS
from backend.dice_tools.models import DiceRollRecord
from backend.lore.models import EffettoEventoReputazione, EventoReputazione, Fazione

from .tools import AI_TOOLS, AI_TOOLS_BY_NAME, tool_is_available


def _build_fixture():
    """Un piccolo mondo con un rappresentante di ogni dominio delle domande d'oro."""

    for definition in V2_SETTING_DEFAULTS:
        if definition["key"].startswith("mercato."):
            SettingDefinition.objects.create(**definition, value=definition["default_value"])

    campaign = DatiCampagna.objects.create(nome="Copertura", attiva=True, giorni_da_inizio=5)
    zaino = Zaino.objects.create(nome="Zaino copertura")
    character = Personaggio.objects.create(
        nome="Illaoi", nome_interno="illaoi-coverage", monete=300, livello=6, campagna=campaign, zaino=zaino,
        tot={"slot_magici": 0, "slot_non_magici": 10, "pf": 30, "mod_carico": 5},
    )
    master_user = get_user_model().objects.create_user(username="coverage_master")
    master = Giocatore.objects.create(
        user=master_user, nome="coverage_master", role=Giocatore.ROLE_MASTER,
        character_ids=[character.id], active_character=character, active_campaign=campaign,
    )
    player_user = get_user_model().objects.create_user(username="coverage_player")
    player = Giocatore.objects.create(
        user=player_user, nome="coverage_player", role=Giocatore.ROLE_USER,
        character_ids=[character.id], active_character=character, active_campaign=campaign,
    )

    item = Oggetto.objects.create(nome="Pozione copertura", tipo_1="pozione", valore=15, rarita=1, lv_loot="1")
    Negozio.objects.create(
        nome="Bottega copertura", location_key="skyrim/whiterun", categoria="generale", livello=1,
        lista_oggetti={"version": 2, "entries": [{"itemId": item.id, "quantity": 5, "unitPrice": 15, "source": "manual"}]},
    )

    group = GruppoFamiglieSkill.objects.create(nome="Copertura group", slug="copertura-group")
    family = FamigliaSkill.objects.create(nome="Copertura family", gruppo=group)
    Skill.objects.create(
        nome="Smoke skill", slug="coverage-skill", numero=998001, famiglia=family, costo_pe=5, tipo_pe="all"
    )

    fazione = Fazione.objects.create(campagna=campaign, nome="Fazione smoke", reputazione_base=10)
    evento = EventoReputazione.objects.create(
        campagna=campaign, titolo="Evento copertura", motivo="Un motivo di copertura", giorno_campagna=3,
        visibile_ai_giocatori=True,
    )
    EffettoEventoReputazione.objects.create(evento=evento, fazione=fazione, delta=4)

    Guida.objects.create(nome="Guida fatica", contenuto="La fatica si accumula per turno.", categoria="regole")
    CampaignLoreEntry.objects.create(
        campagna=campaign, slug="voce-player", nome="Voce pubblica", sommario="Visibile ai giocatori", visibilita="player"
    )
    CampaignLoreEntry.objects.create(
        campagna=campaign, slug="voce-dm", nome="Voce del Master", sommario="Solo per il Master", visibilita="dm"
    )
    DiceRollRecord.objects.create(
        giocatore=master, player_name="coverage_master", personaggio=character,
        notation="1d20", rolls=[20], modifier=0, total=20,
    )

    return {"master_user": master_user, "master": master, "player_user": player_user, "player": player, "character": character}


# (domanda rappresentativa, strumento atteso, ruolo minimo per porla, argomenti, verifica sul risultato)
GOLDEN_QUESTIONS = [
    ("quante monete ho?", "scheda_personaggio", Giocatore.ROLE_USER, {"sezione": "economia"},
     lambda payload: "coins" in payload["personaggio"]),
    ("che livello ho?", "scheda_personaggio", Giocatore.ROLE_USER, {},
     lambda payload: "level" in payload["personaggio"]),
    ("quanto pesa una pozione?", "cerca_oggetti", Giocatore.ROLE_USER, {"query": "Pozione"},
     lambda payload: len(payload["oggetti"]) >= 1),
    ("quanti PE mi servono per Smoke skill?", "analisi_abilita", Giocatore.ROLE_USER, {"nome": "Smoke skill"},
     lambda payload: "costoPe" in payload),
    ("quanto peso posso ancora portare?", "capacita_trasporto", Giocatore.ROLE_USER, {},
     lambda payload: "pesoResiduoPrimaDelProssimoMalus" in payload),
    ("posso comprare la pozione?", "posso_permettermi", Giocatore.ROLE_USER, {"oggetto": "Pozione"},
     lambda payload: "monete" in payload),
    ("quali pozioni posso creare?", "alchimia_personaggio", Giocatore.ROLE_USER, {},
     lambda payload: "sacca" in payload),
    ("perché la fazione smoke ci considera così?", "perche_reputazione", Giocatore.ROLE_USER, {"fazione": "Fazione smoke"},
     lambda payload: "storiaEventi" in payload and payload["storiaEventi"]),
    ("cosa è successo di recente in campagna?", "stato_campagna", Giocatore.ROLE_USER, {},
     lambda payload: "giorno" in payload),
    ("come funziona la fatica?", "guide_regole", Giocatore.ROLE_USER, {"argomento": "fatica"},
     lambda payload: payload["guide"]),
    ("quali competenze ha il personaggio?", "competenze_personaggio", Giocatore.ROLE_USER, {},
     lambda payload: "competenze" in payload),
    ("chi ha più monete nel gruppo?", "riepilogo_gruppo", Giocatore.ROLE_MASTER, {},
     lambda payload: payload["personaggi"] and "monete" in payload["personaggi"][0]),
    ("quante volte è uscito 20?", "statistiche_tiri", Giocatore.ROLE_MASTER, {},
     lambda payload: "faceDistribution" in payload),
    ("quali giocatori ci sono nella campagna?", "giocatori", Giocatore.ROLE_MASTER, {},
     lambda payload: payload["giocatori"]),
]


class GoldenQuestionCoverageTests(TestCase):
    """Ogni riga verifica che lo strumento giusto sia raggiungibile e produca il dato atteso."""

    @classmethod
    def setUpTestData(cls):
        cls.fixture = _build_fixture()

    def _identity_for(self, role: str):
        if role == Giocatore.ROLE_MASTER:
            return self.fixture["master_user"], self.fixture["master"]
        return self.fixture["player_user"], self.fixture["player"]

    def test_every_golden_question_resolves_to_a_reachable_tool_with_the_expected_data(self):
        failures = []
        for question, tool_name, role, kwargs, check in GOLDEN_QUESTIONS:
            tool = AI_TOOLS_BY_NAME.get(tool_name)
            if tool is None:
                failures.append(f"«{question}»: strumento sconosciuto {tool_name}")
                continue
            user, giocatore = self._identity_for(role)
            if not tool_is_available(tool, user, giocatore):
                failures.append(f"«{question}»: {tool_name} non raggiungibile per il ruolo {role}")
                continue
            payload = tool.run(user, giocatore, **kwargs)
            if "errore" in payload:
                failures.append(f"«{question}»: {tool_name} ha risposto errore: {payload['errore']}")
                continue
            if not check(payload):
                failures.append(f"«{question}»: {tool_name} non contiene il dato atteso ({payload})")
        self.assertEqual(failures, [])


class AISecurityInvariantTests(TestCase):
    """Invarianti che devono restare vere indipendentemente da quanti strumenti si aggiungono."""

    @classmethod
    def setUpTestData(cls):
        cls.fixture = _build_fixture()

    def test_tool_mutability_is_explicit(self):
        ordinary_non_read_only = [
            tool.name for tool in AI_TOOLS
            if not getattr(tool, "proposal_only", False) and not tool.read_only
        ]
        proposal_declared_read_only = [
            tool.name for tool in AI_TOOLS
            if getattr(tool, "proposal_only", False) and tool.read_only
        ]
        self.assertEqual(ordinary_non_read_only, [])
        self.assertEqual(proposal_declared_read_only, [])

    def test_running_every_tool_leaves_the_database_unchanged(self):
        """La prova comportamentale che nessuno strumento scrive: uno snapshot prima/dopo, non un'ispezione degli import."""

        required_arguments = {
            "posso_permettermi": {"oggetto": "Pozione"},
            "analisi_abilita": {"nome": "Smoke skill"},
            "perche_reputazione": {"fazione": "Fazione smoke"},
        }
        character = self.fixture["character"]
        master_user, master = self.fixture["master_user"], self.fixture["master"]

        def snapshot():
            character.refresh_from_db()
            return {
                "personaggi": list(Personaggio.objects.values_list("id", "monete", "danno", "pe_generali", "livello").order_by("id")),
                "negozi": list(Negozio.objects.values_list("id", "lista_oggetti").order_by("id")),
                "giocatori": list(Giocatore.objects.values_list("id", "character_ids", "active_character_id").order_by("id")),
                "campagne": list(DatiCampagna.objects.values_list("id", "monete_condivise", "giorni_da_inizio").order_by("id")),
                "counts": {
                    model.__name__: model.objects.count()
                    for model in (Personaggio, Negozio, Giocatore, DatiCampagna, EventoReputazione, DiceRollRecord)
                },
            }

        before = copy.deepcopy(snapshot())
        for tool in AI_TOOLS:
            kwargs = required_arguments.get(tool.name, {})
            try:
                tool.run(master_user, master, **kwargs)
            except Exception:  # noqa: BLE001 - solo la corruzione del DB interessa qui, non i fallimenti applicativi
                pass
        after = snapshot()
        self.assertEqual(before, after)

    def test_a_player_cannot_read_another_characters_sheet(self):
        from backend.ai.tools import execute_tool

        other_character = Personaggio.objects.create(nome="Personaggio altrui", nome_interno="altrui-coverage", monete=9999)
        content, is_error = execute_tool(
            "scheda_personaggio", {"nome": "Personaggio altrui"}, self.fixture["player_user"], self.fixture["player"]
        )
        self.assertNotIn(str(other_character.monete), content)

    def test_role_gated_tools_refuse_a_lower_role(self):
        from backend.ai.tools import execute_tool

        role_gated = [(tool.name, tool.minimum_role) for tool in AI_TOOLS if tool.minimum_role != Giocatore.ROLE_USER]
        self.assertTrue(role_gated, "nessuno strumento è protetto da ruolo: il test non verifica nulla")
        for name, _minimum in role_gated:
            content, is_error = execute_tool(name, {}, self.fixture["player_user"], self.fixture["player"])
            self.assertTrue(is_error, f"{name} avrebbe dovuto rifiutare un giocatore semplice")

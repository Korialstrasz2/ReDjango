# AI Agent Upgrade Plan

Date: 2026-07-30
Status: Proposal, not implemented.
Scope: `backend/ai/` (`tools.py`, `agent.py`, `models.py`, `defaults.py`, `selectors.py`, `services.py`), one migration, one frontend file.
Hard constraint: **read-only throughout**. No tool writes to the database or to code, in any phase.

---

## 1. Problem Description

### 1.1 The symptom

A player authenticated as Illaoi asks «quante monete ho?». The assistant answers that it does not know what monete are.

The model did not reason badly. **It had no path to that value at all.**

### 1.2 Immediate cause — the character sheet whitelist

`_character_sheet` at [tools.py:91-102](../backend/ai/tools.py#L91) filters the `personaggio_detail` payload through this whitelist:

```python
for key in ("id", "name", "type", "races", "level", "details",
            "primaryTotals", "resources", "stats", "encumbrance")
```

Two distinct defects:

1. **`coins` is discarded.** `personaggio_summary` produces it at [selectors.py:1078](../backend/characters/selectors.py#L1078) (`"coins": personaggio.monete`), but the whitelist does not list it. Lost alongside it: `xp`, `inventory`, `equipment`, `quiver`, `coinStorage`, `abilities`, `competencies`, `notes`, `reagents`, `effects`, `characteristics`, `combat`, `resistances`, `diceModifiers`, `valueGroups`, `criticalThresholds`, `modifiedStats`.
2. **`"stats"` does not exist.** The payload never has a `stats` key — those values live under `characteristics`, `combat`, and `resistances`. The entry is dead metadata that silently yields nothing.

Effective output of the tool: `id`, `name`, `type`, `races`, `level`, `details`, `primaryTotals`, `resources`, `encumbrance`. The one tool meant to answer "how much do I have" returns level, races, and hit-point bars.

### 1.3 Structural cause A — the agent does not know who is asking

`run_agent` receives `giocatore` ([agent.py:52](../backend/ai/agent.py#L52)) and uses it for permissions and logging, but `_system_prompt` ([agent.py:47](../backend/ai/agent.py#L47)) never mentions it. The system prompt never states:

- the asker's name and role;
- which character is active;
- which characters are accessible;
- the campaign, current day, time, or weather.

So «quante monete **ho**?» forces the model to infer on its own that "ho" means "call `scheda_personaggio` with an empty `nome`". Strong models get there; small ones do not. This is an entire failure class (`io`, `mio`, `ho`, `posso`, `mi serve`) produced by a four-line omission.

### 1.4 Structural cause B — no domain glossary

Tool descriptions are generic and carry none of the rulebook's Italian vocabulary. A small model does not know which tool covers *monete, PE, PF, mana, energia, potere, fatica, slot, rango, maestria, ingombro, reputazione*. The failure is **routing**, not reasoning: without a term → tool map the model calls nothing and improvises.

### 1.5 Structural cause C — 13% domain coverage

Eight tools against roughly sixty models. Domains with **zero** tools:

alchemy and reagents · spells and their costs · dice history and statistics · combat (maps, hexes, participants, modifiers, turn plans, events) · timeline · curiosities · hall of fame · campaign lore entries and their relations · faction relations · character notes · travel maps · equipment and containers · custom effects and presets · skill prerequisite analysis · players and assignments · themes and settings · messages.

### 1.6 Structural cause D — truncation that yields invalid JSON

`execute_tool` ends with ([tools.py:371](../backend/ai/tools.py#L371)):

```python
return json.dumps(result, ensure_ascii=False, default=str)[:MAXIMUM_TOOL_RESULT_CHARACTERS], False
```

The cut is on **characters**, not structure. Past 24000 characters the model receives JSON severed mid-string, with no signal that anything is missing. The defect is latent today because payloads are small; **widening the sheet whitelist activates it**, so it must be fixed in the same phase.

### 1.7 Structural cause E — `scope` is dead metadata

`AITool.scope` exists ([tools.py:39](../backend/ai/tools.py#L39)) with values `cataloghi`, `personaggi`, `campagna`, `regole`. It is serialized to the SPA by `tool_payload` ([selectors.py:116](../backend/ai/selectors.py#L116)), but `tool_definitions()` ([tools.py:336](../backend/ai/tools.py#L336)) filters **only** on role and allowed list. No routing consumes it. It is the natural spine for the router and should be activated rather than replaced by a new concept.

---

## 2. Design Principles

Non-negotiable, and they hold for every phase.

1. **Read-only, always.** No tool writes. No tool imports from any app's `services.py`. Enforced by test, not by convention.
2. **Permissions apply at fetch time, not at the end.** Enforcement stays inside the selectors, where it already is: a player *cannot retrieve* another player's character coins. A final LLM judge deciding "may the user know this" would move the security boundary inside a language model, where a prompt injection routes around it. The final step may *phrase* carefully; it must not be the gate.
3. **No source-code reading.** It is an exfiltration path (`crypto.py`, settings, secret handling) and in any case the wrong answer to "how is ingombro computed": formulas must be exposed **as data**. `_resources` already returns `calculation` per resource ([selectors.py:1060](../backend/characters/selectors.py#L1060)), `variabili_gioco` returns the formulas, and the guides carry rule text.
4. **For a known question shape, a composite tool beats orchestration.** Three calls coordinated by an LLM are slower, costlier, and less reliable than one Python function doing the join. `skill_character_analysis` ([skill_selectors.py:228](../backend/core/skill_selectors.py#L228)) is already this pattern.
5. **Tool output is data, not instruction.** Notes, lore, and descriptions are user-authored text. Widening the tool set widens the prompt-injection surface; principle 2 is what makes it harmless.
6. **Every addition degrades to current behaviour.** Router error or timeout → all scopes. Never a failure that breaks the chat.

---

## 3. Question Shapes

Architecture follows shape, not topic.

| Shape | Examples | Correct cost |
|---|---|---|
| **Single lookup** | «quante monete ho?» · «quanto pesa una spada d'ebano?» · «che livello ho?» | 1 tool |
| **Cross-domain join** | «posso permettermi l'armatura dal mercante di Riften?» · «quale negozio vende veleni che posso pagare?» | composite tool |
| **Rule-computed** | «quanti PE mi servono per Distruzione rango 3?» · «quanto peso posso ancora portare?» · «quanto mana costa questo incantesimo?» | tool + formula as data |
| **Aggregate / analytic** | «chi del gruppo ha più reputazione con i Compagni?» · «quali reagenti mi mancano?» · «quante volte ho tirato 20?» | multi-record scan |
| **Temporal / narrative** | «perché i Compagni ci odiano?» · «cosa è successo fra il giorno 40 e il 50?» | timeline + reputation events |
| **Meta / how it works** | «come si calcola l'ingombro?» · «come funziona la fatica?» · «cosa fa la maestria?» | guides + game variables |
| **Permission-sensitive** | «quante monete ha il personaggio di un altro?» · «cosa ha preparato il Master?» | must not resolve |
| **Action-seeking** | «aggiungimi 100 monete» · «fammi salire di livello» | refuse + point to the UI |

---

## 4. Phases

### Phase 0 — Fix the defect (half a day)

Goal: «quante monete ho?» works. No new architecture.

**0.1 — Replace the whitelist with sections.** Do not widen the whitelist to every key: the full sheet payload easily exceeds 24000 characters and floods a small model's context. Introduce a `sezione` enum parameter instead:

| `sezione` | Keys returned |
|---|---|
| `riepilogo` (default) | `name`, `type`, `races`, `level`, `coins`, `resources`, `encumbrance`, `details` |
| `economia` | `coins`, `coinStorage`, `encumbrance` |
| `caratteristiche` | `characteristics`, `primaryTotals`, `diceModifiers`, `criticalThresholds` |
| `combattimento` | `combat`, `resistances`, `modifiedStats` |
| `inventario` | `inventory`, `quiver`, `utilityContainer`, `campaignContainer`, `encumbrance` |
| `equipaggiamento` | `equipment`, `appearance` |
| `esperienza` | `xp`, `level` |
| `effetti` | `effects` |
| `competenze` | `competencies` |
| `note` | `notes` |
| `reagenti` | `reagents` |

One tool, unchanged tool-menu size, small payloads, and the section label tells the model what it asked for. Backwards compatible: absent `sezione` → `riepilogo`.

**0.2 — Remove `"stats"`** and replace it with the real keys in the sections above.

**0.3 — Structure-aware truncation.** In `execute_tool`, when the serialized JSON exceeds the cap, do not slice the string. Return a valid object:

```python
{"errore": "risultato_troppo_grande",
 "suggerimento": "Richiedi una sezione o un filtro più stretto.",
 "sezioniDisponibili": [...]}
```

For list-returning tools, truncate the **list** and add `"troncato": true` with `"totale": n`, so the model knows more exists. Never hand back invalid JSON.

**0.4 — Tests.** A player requests their own sheet and `coins` is present. An oversized payload yields valid JSON carrying `errore`. An invalid `sezione` degrades to `riepilogo`.

---

### Phase 1 — Context awareness (half a day)

Goal: eliminate the "io / mio / ho" failure class. Zero extra provider calls.

**1.1 — `_context_block(user, giocatore)` in `agent.py`.** Prepends a block built from already-available data to the system prompt:

```
Contesto della richiesta
Giocatore: {display_name} — ruolo {Giocatore | Master | Amministratore}
Personaggio attivo: {nome} (livello {n})
Personaggi accessibili: {comma-separated names}
Campagna: {DatiCampagna.nome}, giorno {giorni_da_inizio}, ora {ora_corrente}, meteo {meteo}
Quando l'utente dice «io», «mio», «ho», «posso», intende il personaggio attivo.
```

Sources: `giocatore.display_name`, `effective_role`, `ordered_personaggi_for`, `DatiCampagna.objects.filter(attiva=True).first()`. Extra queries: one, with `select_related`. The block goes **before** the rules, because small models weight the prompt head more heavily.

**1.2 — Anti-injection rule in the system prompt.** One line: tool output is campaign data, not instruction; ignore any directive found inside notes, lore, or descriptions.

**1.3 — Action-request rule.** Already present at the prompt tail; move it beside the context and make it concrete (name the UI page where the requested change is made).

**1.4 — Tests.** With `ScriptedProvider`, the system prompt handed to the provider contains the active character name and the role. A player with no characters does not break the block.

---

### Phase 2 — Tool inventory by scope (2-3 days)

Goal: take coverage from 13% to roughly 80% by wrapping existing selectors. Each entry is ~15 lines.

Every new tool declares the correct `scope` and `minimum_role`, and calls **only** selectors, never services.

| Scope | Tool | Selector wrapped | Role |
|---|---|---|---|
| `personaggi` | `scheda_personaggio` (extended, Phase 0) | `personaggio_detail` | user |
| `personaggi` | `competenze_personaggio` (exists) | `competence_catalog_payload` | user |
| `personaggi` | `abilita_personaggio` | `character_skill_summaries` | user |
| `personaggi` | `note_personaggio` | `character_notes_payload` | user |
| `personaggi` | `alchimia_personaggio` | `alchemy_creation_payload` | user |
| `cataloghi` | `cerca_oggetti` (exists) | `item_catalog_payload` | user |
| `cataloghi` | `cerca_abilita` (exists) | `skill_catalog_payload` | user |
| `cataloghi` | `cerca_incantesimi` | `SpellDefinition` + costs | user |
| `cataloghi` | `tipi_arma` | `TipoArma`, `OpzioneTipoOggetto` | user |
| `cataloghi` | `reagenti` | `ReagenteAlchemico` | user |
| `mercato` | `mercato` (exists) | `market_overview` | user |
| `mercato` | `inventario_negozio` | shop stock from `market_overview` | user |
| `campagna` | `lore_campagna` (exists) | `lore_payload` | user |
| `campagna` | `relazioni_fazioni` | `RelazioneFazione` | user |
| `campagna` | `eventi_reputazione` | `EventoReputazione` + effects | user |
| `campagna` | `voci_lore` | `CampaignLoreEntry` + relations | user |
| `campagna` | `timeline` | `TimelineEvent` | user |
| `campagna` | `curiosita` | `Curiosita` | user |
| `campagna` | `hall_of_fame` | `HallOfFameCharacter` | user |
| `campagna` | `stato_campagna` | `DatiCampagna` (day, time, weather, shared coins) | user |
| `campagna` | `mappe_viaggio` | `travel_maps_payload` | user |
| `dadi` | `storico_tiri` | `dice_history_payload` | user |
| `dadi` | `statistiche_tiri` | `dice_statistics` | user |
| `combattimento` | `stato_combattimento` | `combat_workspace_payload` | user |
| `combattimento` | `modificatori_combattimento` | `CombatModifier` + state | user |
| `regole` | `guide_regole` (exists) | `Guida` | user |
| `regole` | `variabili_gioco` (exists) | `game_variables_payload` | master |
| `gestione` | `giocatori` | `player_management_selectors` | master |
| `gestione` | `impostazioni` | `settings_selectors` | admin |

New scopes to introduce: `mercato`, `dadi`, `combattimento`, `gestione`.

**2.1 — Glossary in the system prompt.** A compact term → tool table, one line per term, in the shared prompt (not in a profile's `instructions`, so every agent benefits):

```
monete, oro, soldi → scheda_personaggio (sezione economia)
PE, punti esperienza → scheda_personaggio (sezione esperienza), cerca_abilita
PF, mana, energia, potere, fatica → scheda_personaggio (sezione riepilogo)
ingombro, peso, slot, zaino → scheda_personaggio (sezione inventario)
rango, maestria → competenze_personaggio
reputazione, fazione → lore_campagna, eventi_reputazione
prezzo, negozio, comprare → mercato, inventario_negozio
tiro, dado, d20 → storico_tiri, statistiche_tiri
```

**2.2 — Update the presets.** `seed_ai_providers` at [defaults.py:142](../backend/ai/defaults.py#L142) creates `assistente-campagna` with `allowed_tools = [tool.name for tool in AI_TOOLS]`, so new tools enter new profiles automatically. **Existing profiles do not**: a data migration must add the new names to profiles that already held the full set (compared against the historical set), leaving hand-narrowed selections untouched.

**2.3 — Tests.** Per tool: a player gets only their own data; a master gets more; `admin` tools refuse a master. Plus one parametric test that walks `AI_TOOLS` and executes every tool with empty arguments without raising.

---

### Phase 3 — Scope router (1 day)

Goal: keep the tool menu small. At ~30 tools a small model mis-routes; the router narrows the choice to 4-6 entries.

**3.1 — Activate `scope`.** Add `scopes: set[str] | None` to `tool_definitions()`, filtering in AND with role and allowed list.

**3.2 — `route_scopes(question, provider, available_scopes)`.** A single `complete()` with no tools, low `max_tokens`, prompting for a JSON array of scopes. Cost is one short call; saving is one or two iterations.

**3.3 — Activation rules.**
- Skip the router when available tools ≤ 8: no benefit.
- Skip the router after the first turn: reuse the union of scopes already chosen in the conversation.
- Any error, timeout, or unparsable output → **all** scopes. The router cannot break the chat.
- Empty scope set returned → all scopes.

**3.4 — Configuration, migration `0006`.** On `AIAgentProfile`:
- `routing_mode` — `CharField(choices=[("off","Disattivato"),("auto","Automatico")], default="auto")`.

Expose it in `serialize_agent` (management) and validate it in `save_agent`, consistently with `max_iterations`.

**3.5 — Observability.** Add `scopes=` and `router_ms=` to the structured log lines already present in `run_agent` ([agent.py:101](../backend/ai/agent.py#L101)).

**3.6 — Tests.** With `ScriptedProvider`: the router picks `personaggi` and `tool_definitions` returns only that scope. A router that raises yields all scopes and a valid answer.

---

### Phase 4 — Composite tools (1-2 days)

Goal: turn the "join" and "computed" shapes into one deterministic call instead of three LLM-coordinated ones. Best quality-per-latency ratio of any phase.

| Tool | Joins | Answers |
|---|---|---|
| `posso_permettermi(oggetto, negozio)` | coins + shop stock and price + remaining encumbrance | «posso comprare l'armatura d'ebano a Riften?» |
| `analisi_abilita(nome)` | `skill_character_analysis` + XP pools + prerequisites | «quanti PE mi servono per Distruzione 3?» |
| `cosa_posso_creare()` | reagent bag + recipes + alchemy set bonuses | «quali pozioni posso fare adesso?» |
| `capacita_trasporto()` | encumbrance + slots + `monete_per_slot` | «quanto peso posso ancora portare?» |
| `perche_reputazione(fazione)` | reputation events + effects + timeline | «perché i Compagni ci odiano?» |
| `riepilogo_gruppo()` — master | key stats for every character | «chi ha più reputazione con i Compagni?» |

Every composite returns **the operands too**, not just the verdict: the model must be able to cite the numbers, and the prompt already demands it ("riporta i valori e le etichette disponibili nel risultato").

`riepilogo_gruppo` is `minimum_role = master` and uses `ordered_personaggi_for(..., include_all=True)`.

---

### Phase 5 — Selective fan-out (deferred, only on evidence)

Sub-agent fan-out serves **only** the analytic shape, and only after Phases 0-4 are in production and the logs show which questions still go unanswered.

Reason for deferral: router + 2 sub-agents + judge is 4 sequential round-trips. For «quante monete ho?» — one call after Phase 1 — that is a fourfold regression on the very goal of being faster.

If and when it happens, two technical cautions: Django connections are not shared across threads (needs `close_old_connections` per worker in a `ThreadPoolExecutor`), and each sub-agent must receive the **same** `user`/`giocatore`, never an elevated context.

---

### Phase 6 — Coverage tests and observability (half a day, in parallel)

**6.1 — Golden question set.** `backend/ai/test_question_coverage.py`: the table in section 3 as a fixture. For each question, verify deterministically with `ScriptedProvider` that the expected tool is **reachable** for that role and that its payload carries the expected key. Model prose is not graded; data availability is.

**6.2 — Security invariant tests.**
- Every `AI_TOOLS` entry has `read_only=True`.
- No module under `backend/ai/` imports `services` from another app (static check over the source).
- A player requesting another player's character sheet gets an error, not the data.
- A player cannot reach `master`/`admin` tools.

**6.3 — Logs.** The `agent_run` lines already exist and are good. Add `scopes`, `router_ms`, `sections` to see which questions burn iterations.

---

## 4b. Phase 7 — Retrieval quality and loop resilience (implemented)

Added after Phases 0-4 shipped, from a real failure: «come funziona il viaggio?» returned
`ai.iteration_limit` — the model burned all six iterations and the user got nothing. The
question was simple; four compounding defects made it unanswerable.

**7.1 — `Guida.contenuto` was double-encoded.** The field is a `TextField` that *contains*
JSON (a list of typed blocks: `legacy_html`, `paragraph`, `callout`, `heading`, `warning`,
`code`, `list`). `_rules_guide` called `json.dumps()` on that string, wrapping it a second
time: every `"` became `\"`, every newline `\r\n`. The model received
`"[\r\n {\r\n \"type\": \"legacy_html\", \"html\": \"<h1 id=\\\\\\"indice\\\\\\">…` — escape
noise consuming the character budget instead of rules. Fixed by parsing the blocks and
flattening them to plain text (`strip_tags` + `html.unescape` for `legacy_html`).

**7.2 — Excerpts came from the head of the document, so the index was returned instead of
the rules.** `Regole Varie` is 58,780 characters with an internal table of contents. The
travel rules live at offset ~14,700; the tool returned `blob[:4000]`, i.e. the index. Fixed
by returning windows centred on matches.

**7.3 — Sequential match scanning still returned only the index.** "viaggio" appears at
offsets 454 and 472 (two consecutive table-of-contents entries), then 3276, 6295 — the
three excerpt slots were exhausted before reaching the section at 14,689. Fixed by
selecting the **densest** windows: an index entry names a term once, the section that
defines it repeats it (6 occurrences within ~1,400 characters). Ties break toward later
offsets, because the index is always at the top.

**7.4 — `guide_regole` had no `stato` field.** The system prompt instructs the model to
distinguish `nessun_dato` from `filtro_senza_risultati`, but only `lore_campagna` ever
returned it. The model could not tell "no guides exist" from "no guide mentions this", so
it retried blindly. `stato`, `guideTotali` and `guideCorrispondenti` are now returned.

**7.5 — The router could remove the rules scope.** "viaggio" maps to `mappe_viaggio`
(scope `campagna`) in the glossary, so a router choosing only `campagna` left
`guide_regole` unreachable — the tool holding the answer was not on the menu.
`ROUTER_ALWAYS_INCLUDED_SCOPES = {"regole"}` now guarantees the two rules tools survive any
routing decision; almost every "how does X work" question needs them and they cost two
slots.

**7.6 — Identical repeated tool calls were silently re-executed.** A call with the same
name and arguments cannot return anything new, yet the loop happily ran it again, which is
precisely how a small model spends its iteration budget. Repeats now return
`chiamata_ripetuta` with an instruction to change argument, change tool, or answer.

**7.7 — Hitting the iteration limit discarded all gathered work.** `run_agent` raised
`ApiError` after six iterations, throwing away a conversation that already contained six
tool results. It now makes one final call **with no tools** and the `FINAL_ANSWER_INSTRUCTION`
preamble, forcing an answer from the accumulated evidence and returning
`stopReason: "iteration_limit"`. The hard error remains only for the case where that final
call also produces nothing. A partial answer that declares its gaps beats "riformula la
domanda".

---

## 5. Alternatives Considered and Rejected

| Alternative | Why not |
|---|---|
| Final LLM judge deciding what the user may know | Moves the security boundary inside a model. Today enforcement lives in the selectors and an injection cannot route around it; with the judge it can. A regression, not an improvement. |
| A source-code reading tool | Exfiltration path (`crypto.py`, settings, secrets) and the wrong answer to the problem: formulas are already available as data via `calculation` and `variabili_gioco`. |
| Widen the whitelist to every sheet key | Payloads past 24000 characters, saturated context on small models, and it activates the truncation defect. Sections solve both. |
| Always-on fan-out | Quadruples round-trips on the common case, against the stated goal of speed. |
| Raising `max_iterations` to fix the travel-question failure | Treats the symptom. The tool was returning a table of contents instead of rules; more iterations would only have let the model fail more expensively. Fixed retrieval instead (7.1-7.3). |
| Splitting large guides into many small `Guida` rows | A data migration touching authored content, to work around a retrieval bug. Excerpt windows solve it without editing anything the Master wrote. |
| A separate agent profile per domain | Pushes tool selection onto the user. The router does it without asking. |
| Glossary in a profile's `instructions` | Duplicated across profiles and drifts over time. Belongs in the shared `SYSTEM_PROMPT`. |

---

## 6. Order and Dependencies

```
Phase 0 (defect) ─┬─> Phase 1 (context) ─┬─> Phase 2 (tools) ─┬─> Phase 3 (router)
                  │                      │                    └─> Phase 4 (composites)
                  └──────────────────────┴─> Phase 6 (tests, in parallel)
                                                                   └─> Phase 5 (deferred)
```

Phases 0 and 1 are independent and closeable in one day: alone they fix the coins question and the whole "io/mio/ho" family. Phase 3 only makes sense after Phase 2, because with eight tools a router is pointless.

## 7. Change Surface

| File | Phases | Nature |
|---|---|---|
| [backend/ai/tools.py](../backend/ai/tools.py) | 0, 2, 3, 4 | sections, truncation, ~20 tools, scope filter |
| [backend/ai/agent.py](../backend/ai/agent.py) | 1, 3 | context block, glossary, router, logs |
| [backend/ai/models.py](../backend/ai/models.py) | 3 | `routing_mode` |
| `backend/ai/migrations/0006_*.py` | 2, 3 | field + `allowed_tools` backfill |
| [backend/ai/selectors.py](../backend/ai/selectors.py) | 3 | serialize `routing_mode` |
| [backend/ai/services.py](../backend/ai/services.py) | 3 | validate `routing_mode` |
| [backend/ai/defaults.py](../backend/ai/defaults.py) | 2 | presets carrying the new tools |
| [frontend/src/features/ai/AITool.tsx](../frontend/src/features/ai/AITool.tsx) | 2, 3 | tools grouped by scope, `routing_mode` control |
| `backend/ai/tests.py` + `test_question_coverage.py` | all | tests per phase |

# Nuovo PG — Guida + procedura di creazione

Preparation document. Written 2026-07-30, before any code is touched.
Scope: an in-app Italian guide **and** a real player-facing character creation flow.

---

## 1. Decisions locked

| # | Question | Answer |
|---|---|---|
| 1 | What is the deliverable? | Guide **and** creation wizard (full vertical slice) |
| 2 | Caratteristica preferita vs. the automatic `livello/5` | Keep the global bonus, add the preferred characteristic **on top** |
| 3 | Where does a new PG start? | Level 1, all characteristics at base 10, nothing spent |
| 4 | Guide depth | Identity + race/subrace in full detail; everything else at pointer depth |
| 5 | Placement | Player-facing, its own route |

Assumption, stated rather than asked: the preferred characteristic grants
`personaggio.livello / 5` on the chosen stat, Elder's exact formula, as a named custom
effect. At level 20 a PG is therefore +4 from the choice **plus** the +4 everyone gets
automatically. Change the value in one place (`PREFERRED_CHARACTERISTIC_FORMULA`) if this
turns out too generous.

---

## 2. What exists today

### Elder Django

- `regole_varie_elder.html#crea-pg` is the whole written rule: name, age, sex, race,
  subrace, background; then note racial bonuses, hand-build effects for bonus/malus, and
  choose a **caratteristica preferita** as an effect `<stat> + personaggio.livello/5`.
- `django_slim/ai_pg_creation/` treats `caratteristica_preferita` as mandatory
  (`crea_pg_con_ai_step_identity.py` raises if missing) and materializes it via
  `_build_caratteristica_preferita_effect()` in `crea_pg_con_ai_workflow.py`.
- The wizard state also carries `classe`/archetipo, `profilo_competenze`, `indicazioni`,
  `livello` → `xp_totali_per_livello()`, the four PE pools, and a generated `nome_interno`.

### ReDjango

- **No character creation path exists.** `management.characters.*` offers only `update`,
  `attach`, `deleteOrphan`, `delete`. Existing PGs came from `import_elder_characters`;
  units are generated as `tipologia="nemico"`.
- **No caratteristica preferita**, and `CHARACTERISTIC_ADJUSTMENT_DEFAULTS`
  (`backend/core/defaults.py`) already grants `personaggio.livello / 5` to all nine
  characteristics plus a Fortuna-derived bonus to the other eight.
- **Race is already automatic**: `automatic_race_effects()` in
  `backend/characters/race_rules.py` applies race modifiers, racial trait and subrace from
  `razza_1`/`razza_2`. 14 races. `razza_3` exists and is unused.
- **No `classe`/archetipo field** on `Personaggio`.
- Base profile `Formule_base`: all nine characteristics 10; pf 15, mana 10, energia 6,
  potere 2, pa 8, attacco 5, difesa 15.
- Ownership is `Giocatore.character_ids` (JSON list). `RichiestaAssegnazionePersonaggio`
  already exists for *claiming an existing* PG — creation should not go through it.
- `seed_minimum_data` builds an `empty_personaggio_template` PG (Equip + Zaino + Note +
  Faretra + EffettiPersonaggio, `tipologia="altro"`, level 1) that is filtered out of every
  list. It is the exact skeleton the creation service must produce.
- Guides live in `V2_GUIDE_DEFAULTS` (`backend/core/guides_it.py`), JSON blocks rendered by
  `GuidesPage` in `frontend/src/App.tsx`. Existing `ordine`: 5, 8, 10, 15, 18, 20, 30, 40, 60.

---

## 3. Part A — the guide

New entry in `V2_GUIDE_DEFAULTS`:

```text
seed_key:  "nuovo-pg"
nome:      "Creare un nuovo PG"
categoria: "Personaggio"
ordine:    3          # first guide in the list, before "Regole Varie"
```

Bump `V2_GUIDE_DEFAULT_VERSION` in `backend/core/defaults.py`.

### Block outline

1. `paragraph` — what creating a PG means here: level 1, base 10 everywhere, nothing spent.
   The sheet is empty by design and fills up in play.
2. `heading` "Identità" + `list` — every identity field and who decides it:
   `nome`, `nome_interno` (unique, generated, never shown to players), `tipologia`
   (`giocabile`), `eta`, `sesso`, `campagna`, `portrait`, `dettagli_personaggio`.
   Explicit: `razza_3` is not used at creation.
3. `heading` "Razza e sottorazza" + `entries` — the 14 races with their modifiers, trait
   and subraces, generated from `RACE_CATALOG` so the guide never drifts from the code.
4. `callout` "I bonus razziali sono automatici" — the difference from Elder that matters
   most: you do **not** hand-build racial effects here. `automatic_race_effects()` applies
   race modifiers, trait and subrace as soon as `razza_1`/`razza_2` are set. Elder required
   these by hand; copying that habit produces doubled bonuses.
5. `heading` "Caratteristica preferita" + `paragraph` + `code` — the choice, the nine valid
   stats, the effect it creates, and the honest note that ReDjango also gives every
   characteristic `livello/5` automatically, so the preferred one advances twice as fast.
6. `warning` "Differenze rispetto a Elder Django" — condensed: no `classe`/archetipo, no
   starting PE budget, racial effects automatic, preferred characteristic stacks.
7. `heading` "Dopo la creazione" + `list` — pointer depth only, one line each with the
   destination page: perk minore/maggiore, the four PE pools and skills, competenze
   barra1/barra2 from `pe_abilita`, the 9 note sections, equipaggiamento and monete,
   `crit_min`/`crit_nor`/`crit_mag`, bottoni combat, borsa alchemica.
8. `callout` "Convenzione degli effetti manuali" — the `origine` naming convention visible
   on every imported PG (`Perk minore`, `Manuale Elder`, `Abilità: Vitale 3`), so new PGs
   stay consistent with Illaoi, Rhyss, Ra'Zirr and Mog.

Race blocks are built by a `nuovo_pg_guide_blocks()` function next to
`character_variable_guide_blocks()`, kept dynamic like the weapon catalogue.

---

## 4. Part B — the creation flow

### Data

`Personaggio` gains one field:

```python
caratteristica_preferita = models.CharField(max_length=32, blank=True)
```

Additive migration, blank default, no backfill — existing PGs simply have no choice
recorded. Valid values are the nine characteristic keys; validated in the service, not by
`choices`, so an admin renaming a stat does not break rows.

### Backend

`backend/characters/services/creation.py` — new module:

- `create_personaggio(giocatore, payload) -> Personaggio`, one transaction:
  1. validate nome, età, sesso, razza/sottorazza against `RACE_CATALOG`, preferred stat
     against the nine keys;
  2. generate a unique `nome_interno` (slug of nome + short uuid, mirroring
     `unit_generation.py`);
  3. create Equip / Zaino / Note / Faretra / EffettiPersonaggio, same shape as the
     `empty_personaggio_template` seed;
  4. create the `Personaggio` with `tipologia="giocabile"`, `livello=1`, PE pools 0,
     `monete=0`, `campagna` = the player's active campaign;
  5. create the preferred-characteristic `EffettoPersonalizzato` +
     `OperazioneEffettoPersonalizzato` (`bersaglio=<stat>`, `operazione="add"`,
     `valore="personaggio.livello / 5"`, `origine="Caratteristica preferita"`);
  6. append the id to `giocatore.character_ids` and set it as `active_character` if the
     player has none;
  7. call the existing refresh so `tot` is populated before the response.

Racial effects need no code here — `refresh_personaggio` already reads
`automatic_race_effects()` from `razza_1`/`razza_2`.

Action name, per `best_build_practices.md`: **`characters.create`**. Dispatch in
`backend/api_v1/api.py` alongside the other `characters.*` actions, not under
`management.characters.*` — this one is player-facing and must not sit behind the
Master guard.

A `characters.creationOptions` read endpoint returns `race_configuration_payload()` (already
exists) plus the nine characteristics with their labels, so the wizard has no hardcoded lists.

### Frontend

- New route `/new-character` in `App.tsx`, plain `<Route>` — no `GameManagerOnly`/`AdminOnly`.
- `frontend/src/features/creation-pg/NewCharacterPage.tsx`. Note the folder name: the
  existing `features/creation/` is the crafting workshop and must not be reused.
- Steps, one panel each: Identità → Razza e sottorazza → Caratteristica preferita →
  Riepilogo. Race step shows the modifiers that will be applied, read from the payload.
- Entry point: a "Nuovo PG" button on the character selection screen.
- On success: invalidate `["bootstrap"]`, set the new PG active, navigate to
  `/character/:id`, toast in Italian.

### Verification

- `backend/characters/tests.py`: creation produces all five related records; racial effects
  land in `tot` without being written by the creation service; the preferred-characteristic
  effect exists with the right operation; the character is assigned to the creating
  giocatore; an invalid subrace for a given race is rejected; `nome_interno` collisions
  resolve.
- Frontend: the wizard's step validation as a plain unit test next to `mechanics.test.ts`.
- Browser check on the real app with the test account before reporting done.

---

## 5. Status

Built and verified on 2026-07-30. What shipped matches the plan above, with one addition:
the quota open point was resolved in code rather than deferred —
`MAX_PLAYABLE_CHARACTERS_PER_PLAYER = 5` in
`backend/characters/services/creation.py`, with Master and admin exempt. The wizard reads
the remaining allowance from `characters.creationOptions` and refuses to start when it is
spent.

## 6. Open points

- **The quota is a module constant, not a game variable.** Five per player is a guess. If
  the table wants it configurable it belongs in the `Formule_base` profile like the other
  tunables.
- **`classe`/archetipo** exists in Elder's wizard and nowhere in ReDjango. Left out of this
  slice deliberately; if it should come back it is a second field plus a catalog.
- **Starting equipment and monete** are zero by decision 3. If the table expects a starting
  kit, that is a separate content decision, not a creation-flow one.
- **`razza_3`** is still written by nobody. The guide says so explicitly; the field remains
  for the Master's manual use.

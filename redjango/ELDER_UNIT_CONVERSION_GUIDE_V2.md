# Elder Django → ReDjango: Unit conversion guide, v2

**Audience: you, the converting agent.** This document is an operating manual, not
an essay. Read it fully before touching a Unit. Everything you need to convert a
Unit correctly is either stated here or reachable from a path stated here. When
this guide and the code disagree, **the code wins** — and it is your job to find
out, not to guess.

v1 of this guide optimised for *traceability*: hashes, receipts, stage isolation.
That machinery stops an agent from lying about its work. It does not stop an
agent from producing twenty structurally perfect Units that are secretly the same
Unit. v2 keeps every hard legality gate and moves the centre of gravity to
**per-unit authorship**: each Unit gets a Charter written against named
siblings, a signature-axis budget, expectations written *before* the payload, and
a human read of its five level checkpoints. Bookkeeping is reduced to what is
actually load-bearing.

---

## 0. Your standing orders

1. **Verify before you write.** Every constant, ID, enum, and behavior in §1–§2
   is quoted from the code as of the last verification pass. Re-verify anything
   you are about to depend on. Concrete commands are given throughout — run them.
2. **You may improve the Unit, not the rules.** You are an author, not a
   transcriber. Elder Django is evidence about *what this thing is*, not a
   specification of what it must become. But every mechanic you author must
   already be implementable by ReDjango's current handlers.
3. **A catalog hit is permission to consider, never evidence of belonging.**
4. **Ambiguity blocks one Unit, never the queue.** Mark it `blocked`, record the
   question, move to the next Unit.
5. **Never silently widen a pool, swap an item, change `kind`, or drop a
   warning.** Those are Charter amendments and need an explicit note.
6. **One Unit at a time for the calibration set.** Batch tooling is research
   support (§10), not an authoring shortcut.

---

## 1. Ground truth: where everything is

### 1.1 Databases

| What | Path |
|---|---|
| Current ReDjango DB | `C:\Users\alexo\PycharmProjects\ReDjango\db.sqlite3` |
| Legacy Elder DB (read-only) | `C:\Users\alexo\PycharmProjects\firstDjango\the_elder_django\db.sqlite3` |
| Backups | `backups/`, `redjango/backups/` |

The legacy DB holds **203** rows in `django_slim_unit`. Open it read-only:

```bash
python -c "import sqlite3;c=sqlite3.connect('file:C:/Users/alexo/PycharmProjects/firstDjango/the_elder_django/db.sqlite3?mode=ro',uri=True);print([r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")])"
```

### 1.2 Code you must read at least once

| Concern | File |
|---|---|
| Payload validation, every error code, the write path | `backend/combat/unit_management_services.py` |
| Generation semantics: curves, pools, perks, equipping, warnings | `backend/combat/unit_generation.py` |
| Catalog options served to the UI, archetype tag list | `backend/combat/unit_management_selectors.py` |
| Legal damage types, hex geometry, combat math | `backend/combat/rules.py` |
| Resistance %, tier damage formulas | `backend/combat/damage_rules.py` |
| Slot names and item→slot compatibility | `backend/characters/services/inventory_rules.py` |
| Race catalog and racial modifiers | `backend/characters/race_rules.py` |
| Competence keys, descriptions, tag vectors | `backend/core/competence_defaults.py` |
| `Unit`, `Skill`, `Oggetto` models | `backend/core/models.py` |
| Effect operation vocabulary | `backend/characters/models.py` (`OperazioneEffettoPersonalizzato`) |
| Bulk research pipeline (see §10 for its correct role) | `backend/combat/legacy_unit_import.py` |
| Existing Unit tests | `backend/combat/tests.py` (`UnitGenerationTests`), `backend/api_v1/tests.py` |

### 1.3 API surface

```
GET  /api/v1/management/units                       → overview + catalog metadata
GET  /api/v1/management/units/options?kind=item|skill&query=&limit=80
GET  /api/v1/management/units/{unit_id}
POST /api/v1/combat/actions  action=management.units.save     {unitId?, values}
POST /api/v1/combat/actions  action=management.units.preview  {unitId, level, variant}
POST /api/v1/combat/actions  action=management.units.state    {unitId, archived}
```

All require master/admin role (`require_unit_manager`).

`management.units.preview` calls `create_unit_character` and then
`transaction.set_rollback(True)` — it really generates a `Personaggio` and throws
it away. Previews are free and safe; use them constantly.

### 1.4 Provenance — v1's blocker is CLOSED

v1 told you to block `apply` because `save_managed_unit` could not persist
`metadata`. **That is no longer true.** It now takes a keyword-only
`source_metadata` mapping and merges it into `unit.metadata`
(`unit_management_services.py:812`). `Unit` inherits `metadata`, `archived_at`,
`created_at`, `updated_at` from `V2Model` (`backend/core/models.py:15`).

One catch: the HTTP action `management.units.save` does **not** forward
`source_metadata`. Provenance therefore has to be written by a Python-side
importer (`legacy_unit_import.apply_import_run` does this) or a shell call. If
you author through the API, plan a follow-up provenance write. Store:

```json
{
  "sourceProject": "the_elder_django",
  "sourceTable": "django_slim_unit",
  "sourceIds": [931],
  "normalizedName": "ordinatore",
  "converterVersion": "elder-unit-charter-v2",
  "charterHash": "sha256:…",
  "approvedBy": "<name>",
  "approvedAt": "<iso8601>"
}
```

`sourceIds` is the idempotency key. Notes are not a key.

---

## 2. The complete ReDjango vocabulary

Everything in this section is a hard constraint enforced by
`_clean_unit_values` and `_validate_unit`. Violating any of it produces an
`ApiError`, not a warning.

### 2.1 Top-level payload

```jsonc
{
  "name": "string, required, unique case-insensitively, ≤180",
  "category": "string ≤80",
  "archetypeDescription": "text",
  "loreDescription": "text",
  "notes": "text",
  "levels": [],                    // optional legacy level bands, see §2.8
  "archetypeTags": {},             // tag → -5..5
  "competenceProfile": {},         // competence key → -5..5 (humanoid only)
  "generation": {},                // §2.2
  "skillUnlocks": [],              // §2.3, humanoid only
  "equipmentSlots": [],            // §2.4, humanoid only
  "equipmentGroups": [],           // §2.4, humanoid only
  "accessoryCountByLevel": [],     // §2.4, humanoid only
  "innateActions": [],             // §2.5, creature only
  "statProfile": {                 // §2.6
    "baseModifiers": {}, "perLevelModifiers": {}, "milestones": [], "curves": []
  }
}
```

Field names are **camelCase on input**; they are mapped to the Italian model
fields (`nome`, `categoria`, `archetipo_tags`, `profilo_competenze`,
`equipment_profiles`, `stat_profiles`, `skill_actions`, `skill_unlocks`,
`generation_rules`) on save. Read `_clean_unit_values` before you invent a field.

### 2.2 `generation`

| Key | Type / range | Default | Notes |
|---|---|---|---|
| `kind` | `"creature"` \| `"humanoid"` | — | required; `"animal"` is silently coerced to `"creature"` |
| `coreKey` | `warrior` \| `mage` \| `stealth` \| `support` \| `specialist` | — | required for humanoids |
| `coreShare` | 0.1–0.9 | 0.5 | fraction of XP spent from the Core pool |
| `startingXp` | ≥0 | 0 | |
| `xpBase` | ≥0 | 20 | XP per level = `base + growth*(level-1)`, summed |
| `xpGrowth` | ≥0 | 1 | |
| `competenceStartingXp` | ≥0 | 5 | |
| `competenceXpBase` | ≥0 | 15 | |
| `competenceXpGrowth` | ≥0 | 0 | |
| `finalSpendingPasses` | 0–20 | 4 | extra passes to spend leftover XP |
| `magicPolicy` | `"none"` \| `"any"` | `"any"` | `none` rejects every magic Skill |
| `allowedClassFamilies` | `string[]` | `[]` | family name or id; empty = all classes allowed |
| `allowedReligionFamilies` | `string[]` | `[]` | **empty means no religion Skill is allowed at all** |
| `allowedRaces` | `string[]` | `[]` | silently filtered to `RACE_NAMES`; empty = all races |
| `allowHumanoidStatGrowth` | bool | false | required to use curves/milestones/perLevel on a humanoid |

Note the asymmetry: an empty `allowedClassFamilies` is permissive, an empty
`allowedReligionFamilies` is restrictive. That is deliberate in the code
(`unit_management_services.py:192-217`); confirm before you rely on it.

**Races (11):** Bosmer, Dunmer, Orsimer, Altmer, Imperiale, Bretone, Redguard,
Argoniano, Khajiit, Nord, Falmer. Subraces are drawn automatically from
`RACE_CATALOG[race]["subraces"]`. Racial modifiers are applied by the character
layer, so an all-Dunmer Unit inherits Dunmer stats — check `race_rules.py`
before you assume a stat gap is your curve's fault.

### 2.3 `skillUnlocks` (humanoid only — creatures must send `[]`)

```jsonc
{
  "skillId": 335,          // must exist, archived_at IS NULL
  "pool": "archetype",     // core | archetype | minor | major
  "weight": 10,            // 0.1–100, default 1
  "minLevel": 1,           // 1–20
  "maxLevel": 20,          // ≥ minLevel, ≤20
  "requiredAtLevel": 5     // optional; forces the pick at that level
}
```

Rules the validator enforces:

- A `skillId` may appear **once** in the whole list.
- `minor` / `major` pools accept **only** Skills whose family has `is_perk`;
  non-perk pools **reject** perk-family Skills. On save, `minor`/`major` are
  normalised to `pool: "archetype"` plus `perkTier: "minor"|"major"`.
- With `magicPolicy: "none"`, a Skill is magic — and rejected — if its family
  group slug is `scuole-di-magia`, or the group name contains `magia`, or
  `profile_tags.core_magico > 0`, or `profile_tags.natura_magica > 0`, or it has
  a `spell_definition`.
- Class-family Skills are rejected when `allowedClassFamilies` is non-empty and
  does not list the family.
- Religion-family Skills are rejected unless `allowedReligionFamilies` lists the
  family.

**Pool semantics.** `core` is the Core half of the XP budget — broadly reusable
durability, mobility, resource and utility tools. `archetype` is the
role-defining half — the attacks, stances, magic and tactics that make this Unit
*this* Unit. `coreShare` splits the budget between them. A humanoid needs
`archetypeTags` **or** at least one `skillUnlocks` entry, and needs a non-empty
resolved pool on **both** sides at generation time or `create_unit_character`
raises `combat.unit_core_pool_empty` / `combat.unit_archetype_pool_empty`.

**Prerequisites** are expanded automatically by `_expand_prerequisites`, but the
expansion has to be *affordable*. A 40-PE capstone with three prerequisites in a
level-1–5 window is a coverage failure, not a stretch goal. Query the closure:

```sql
SELECT p.from_skill_id AS skill_id, p.to_skill_id AS prerequisite_id
FROM core_skill_prerequisiti p
WHERE p.from_skill_id IN (:candidate_skill_ids);
```

**Archetype tags (13)** — the vector used to score Skills when you do not name
them explicitly: `core_fisico`, `core_magico`, `focus_combat`, `range_skill`,
`area_e_multi_target`, `natura_magica`, `difesa`, `attacco`, `sociale`,
`supporto_party`, `esplorazione_infiltrazione`, `tecnica_crafting`,
`controllo_situazionale`. Range −5..+5.

**Core profile vectors** (`DEFAULT_CORE_PROFILES`, overridable per Unit via
`generation_rules.coreProfile`):

| Core | Vector |
|---|---|
| `warrior` | core_fisico 4, focus_combat 3, attacco 2, difesa 2, range_skill 1 |
| `mage` | core_magico 4, natura_magica 3, area_e_multi_target 2, controllo_situazionale 2, supporto_party 1 |
| `stealth` | esplorazione_infiltrazione 4, range_skill 2, controllo_situazionale 2, core_fisico 1, tecnica_crafting 1 |
| `support` | supporto_party 4, sociale 3, controllo_situazionale 2, core_magico 1, difesa 1 |
| `specialist` | tecnica_crafting 4, esplorazione_infiltrazione 2, controllo_situazionale 2, sociale 1, supporto_party 1 |

Core also drives characteristic perks via `CORE_CHARACTERISTIC_WEIGHTS`, e.g.
`warrior` → forza 5, resistenza 4, agilita 3, velocita 2, fortuna 1. If your
Ordinator's Strength keeps arriving low, that table is why.

**Perks** are granted on the `PERK_MILESTONE_SCHEDULE` (levels 1–20, minor at
every level, major at 2/4/6/8/10/12/14/16/18). You do not schedule them; you only
supply candidates in the `minor`/`major` pools. Missing candidates emit the
warning `Nessun perk {tier} compatibile disponibile al livello {level}.`

### 2.4 Equipment (humanoid only — creatures must send `[]`)

A humanoid **must** have at least one `equipmentSlots` entry or one
`equipmentGroups` entry, or the save fails with
`management.units.equipment_required`.

`equipmentSlots[]`:

```jsonc
{"slot": "armatura", "itemId": 5785, "minLevel": 1, "maxLevel": 20, "weight": 1, "chance": 1}
```

- `slot` must be a key of `EQUIPMENT_SLOT_LABELS`: `arma`, `armatura`, `scudo`,
  `chainmail`, `veste`, `vestiti`, `fascia`, `spilla`, `amuleto`, `cintura`,
  `mantello`, `borsello`, `anello_1..8`, `orecchino_1..6`, `sacco_1..3`,
  `faretra_1..2`, `extra_slot_1..4`.
- The item must satisfy `item_compatible_with_equipment_slot` — real type
  checking, not a name convention. `arma` needs a weapon; `scudo` accepts a
  shield *or* a one-handed weapon; `extra_slot_*` accepts anything.
- The item must be live: `archived_at IS NULL AND archiviato = 0`.
- `(slot, itemId)` must be unique.
- `weight` 0.1–100 controls relative frequency; `chance` 0–1 is the probability
  the slot is filled at all.

`equipmentGroups[]` are for accessories that float across several slots:

```jsonc
{
  "name": "Gioielli Indoril",
  "slots": ["anello_1", "anello_2", "amuleto"],
  "minCount": 1, "maxCount": 2, "emptyChance": 0.2,
  "items": [{"itemId": 1234, "minLevel": 1, "maxLevel": 20, "weight": 3, "chance": 1}]
}
```

Every item must be compatible with at least one slot in the group; a group may
not be empty.

`accessoryCountByLevel[]` — **optional, but all-or-nothing**: if you provide any
band, the bands must be non-overlapping and cover levels 1–20 with no gap, and
every band's `minCount` ≥ Σ group `minCount` and `maxCount` ≤ Σ group `maxCount`.

### 2.5 `innateActions` (creature only — humanoids must send `[]`)

```jsonc
{
  "key": "balzo-predatorio",     // ≤120, stable, kebab-case
  "name": "Balzo Predatorio",    // required, ≤180
  "description": "…",            // where all targeting/range/effect text lives
  "minLevel": 1, "maxLevel": 20,
  "costs": {"pa": 7, "energia": 2},
  "trigger": "Azione",
  "duration": "Istantanea",
  "icon": "artiglio"
}
```

**Cost resources are a closed set of six:** `pf`, `mana`, `energia`, `potere`,
`pa`, `stanchezza`. Any other key is silently dropped — check your payload
round-trips. Values are non-negative integers.

The schema has no fields for range, target pattern, damage type, area, or
condition. Those go in `description`, written precisely enough that a master can
adjudicate it and a future schema migration can parse it. Be disciplined and
consistent: `"Bersaglio singolo entro 2 esagoni. 2d6 danni Taglio, poi Difesa −2
per 2 turni."` is good; `"Attacca ferocemente."` is not.

At generation, actions in-window land in `character.abilita["known"]` with
`unlockedAtLevel` and `sourceUnitId` attached.

### 2.6 `statProfile.curves` — the creature chassis

```jsonc
{"key": "pf", "profile": "medium", "level1": 18, "level20": 100}
```

**The generator interpolates linearly and nothing else.** Read
`_curve_progress` / `_stat_curve_values` (`unit_generation.py:986`):

```
value(level) = round(level1 + (level20 - level1) * (level - 1) / 19)
```

`profile` is a **label only** — it has zero effect on the math. It exists so the
UI can show which preset an endpoint pair matches. A constant is expressed as
`level1 == level20`. Legacy shape words (`quadratic`, `exponential`, `hi_hi`)
have no runtime meaning; if you preserve a shaped legacy curve you keep its
endpoints and record that the interior became linear.

Curves on a humanoid are **ignored entirely** unless
`allowHumanoidStatGrowth: true`, and the validator rejects them outright without
the flag.

**The 28 legal curve keys:**

| Group | Keys | Preset endpoints (very_low → very_high) |
|---|---|---|
| Vitality | `pf`, `mana` | (10,50) (14,75) (18,100) (25,150) (35,225) |
| Pools | `energia`, `potere` | (3,20) (4,25) (6,30) (8,35) (10,40) |
| Actions | `pa` | (5,15) (6,20) (7,25) (9,32) (12,40) |
| Combat | `attacco`, `difesa` | (6,25) (8,40) (10,55) (12,75) (15,100) |
| Primaries | `fortuna`, `forza`, `resistenza`, `velocita`, `agilita`, `intelligenza`, `concentrazione`, `personalita`, `saggezza` | (4,10) (6,16) (8,22) (11,30) (15,40) |
| Resistances | `res_contundente`, `res_taglio`, `res_perforante`, `res_fuoco`, `res_gelo`, `res_elettro` | (−4,0) (−2,1) (0,2) (1,4) (2,5) |
| Reductions | `rd_fis`, `rd_fuoco`, `rd_gelo`, `rd_elettro`, `ap` | (0,1) (0,2) (1,3) (1,5) (2,7) |
| Tier | `tier` | (2,6) (3,9) (4,12) (5,15) (6,18) |

Preset labels in order: `very_low`, `low`, `medium`, `high`, `very_high`, plus
`custom`. Regenerate this table yourself if you suspect drift:

```bash
python -c "
import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','redjango.settings');django.setup()
from backend.combat.unit_generation import UNIT_STAT_CURVE_VARIABLES
for e in UNIT_STAT_CURVE_VARIABLES: print(e['key'], e['presets']['very_low'], e['presets']['very_high'])
"
```

Omit variables ReDjango derives itself. Do not author a curve for a total the
engine already computes — check `refresh_personaggio` before adding an exotic key.

### 2.7 `competenceProfile` (humanoid only)

21 legal keys: `camuffare`, `cavalcare`, `conoscenze_naturaegeografia`,
`conoscenze_religioni`, `conoscenze_storiaenobilta`, `diplomazia`, `furtivita`,
`gestione_risorse`, `ingegneria`, `intimidire`, `intuizione`,
`manovrare_veicoli`, `nuotare`, `percezione`, `raggirare`, `rapidita_di_mano`,
`sapienza_magica`, `scalare`, `sopravvivenza`, `strategia_militare`, `suonare`.

Priorities are −5..+5 and feed `COMPETENCE_WEIGHT_TABLE`:

| −5 | −4 | −3 | −2 | −1 | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.02 | 0.05 | 0.1 | 0.25 | 0.75 | 2.0 | 4.0 | 8.0 | 14.0 | 22.0 |

**−5 is an absolute veto (weight 0.0), not a strong dislike.** Use it to state
identity exclusions ("this brute never has `sapienza_magica`"). The curve from
0 to 5 is steep — a `+5` competence is 29× a `0` — so spend +4/+5 on the one or
two competences that *are* the character, and let the rest sit at 0/±1.

### 2.8 `statProfile` extras and `levels`

`baseModifiers` (flat, always applied), `perLevelModifiers` (× `level-1`),
`milestones` (`[{level, modifiers}]`, applied cumulatively at/below level), and
the legacy `levels` band list (`[{minLevel, maxLevel, modifiers}]`). All except
`baseModifiers` are gated behind `allowHumanoidStatGrowth` for humanoids. These
are applied through a `EffettoPersonalizzato` named `"<Unit> · chassis"`, whose
operation vocabulary is: `add`, `subtract`, `multiply`, `percent`, `min`, `max`,
`cap`, `set`, `strong_set`, `formula_override`.

### 2.9 Hard contracts, restated

| Contract | Rule |
|---|---|
| Creature | no `skillUnlocks`, no equipment of any kind, no `competenceProfile`. Innate actions + curves only. |
| Humanoid | ≥1 equipment pool, no `innateActions`, a `coreKey` (or custom `coreProfile`), `archetypeTags` or `skillUnlocks`, no stat growth without the override. |
| Both | levels 1–20 only (`MAX_GENERATED_LEVEL = 20`), unique name. |

### 2.10 Rule legality: what actually exists

`DAMAGE_TYPES` (`backend/combat/rules.py:21`) is exactly:
**Contundente, Perforante, Taglio, Gelo, Fuoco, Elettro, Puro.**

There is no poison damage type. There is no Strength damage. There is no
"psychic", "holy", or "necrotic" damage. `Veleno` may exist as an effect or
status — verify it, do not assume it.

Before you write any mechanic, prove it is expressible. Run the searches:

```bash
grep -rn "DAMAGE_TYPES\|RESISTANCE_PERCENT\|TIER_DAMAGE_FORMULAS" backend/combat/
grep -rn "def apply_\|def resolve_" backend/combat/services.py | head -40
```

and find a **precedent**: an existing Skill or implemented action that already
does the thing you want.

```sql
SELECT id, nome, descrizione, azioni_attive, effetti_passivi
FROM core_skill
WHERE archived_at IS NULL
  AND (lower(descrizione) LIKE '%veleno%' OR lower(nome) LIKE '%veleno%')
LIMIT 20;
```

If no precedent exists, you have three legal moves: re-author the mechanic with
supported primitives; propose the mechanic as a separate engine change (out of
scope for a conversion); or block the Unit. You may **not** write it and hope.

A legacy action name such as `Sputo Velenoso` proves *identity* — this creature
spits something foul. It does not license poison damage. Re-author it: e.g.
`Perforante` damage plus a documented Difesa/Agilità debuff, or a supported
lingering effect, with a receipt pointing at the precedent you copied.

---

## 3. The legacy source: how to read it

### 3.1 `django_slim_unit`

Columns: `id`, `levels`, `preset`, `vestito`, `armatura`, `chainmail`, `veste`,
`scudo`, `arma`, `archetipo`, `categoria`, `nome`, `skill_1_id`…`skill_7_id`,
`profili_attributi_formule`, `razza`.

Reading notes, all of them load-bearing:

- **`nome` is the grouping key, `id` is not.** Several rows share a name and
  differ only by level band. Group by `lower(trim(nome))`, keep every `id` in
  `sourceIds`.
- **`levels`** is a JSON list of the levels that row covered, e.g. `[15,16,17,
  18,19,20]` for Ordinatore `#931`, `[20]` for most creatures. This is *the
  level range the original author actually designed for*. Extending to 1–20 is a
  deliberate authorial act that must be justified in the Charter, not a default.
- **`razza` is unreliable.** Soldato Dremora `#944` has `razza="Entità"` but is
  mechanically a disciplined heavy-infantry humanoid. Lupo `#986` also has
  `razza="Entità"`. Classify by **behavior**: does it wear gear and learn Skills
  (`humanoid`), or does it have innate biology (`creature`)? Note the text is
  latin-1 mangled in places (`Entit?`) — normalise before comparing.
- **`categoria`** (`Umano`, `Daedra`, `Natura`, `Extra`…) and **`archetipo`**
  (`tank`, `guerriero`, `Entità`…) are weak but real hints about the author's
  intent.
- **Equipment fields** are JSON lists of item names, mapped as
  `vestito→vestiti`, `armatura→armatura`, `chainmail→chainmail`, `veste→veste`,
  `scudo→scudo`, `arma→arma`. Empty markers to ignore: `""`, `vuoto`,
  `nessuno`, `nessuna`. Names must be resolved to **current** `core_oggetto` IDs
  by normalised name — never by "the number looks about right".
- **`skill_1_id`…`skill_7_id`** join to `django_slim_skillnpc`
  (`id, nome, descrizione, effetto, costo, boost`). **All ten humanoid families
  in the calibration set have these empty.** Their Skill pools are therefore
  authored from current catalog semantics, not copied — say so in the Charter
  rather than pretending fidelity you do not have.
- **`preset`** (`Heavy`, `Any`, …) hints at armor weight class.

### 3.2 `profili_attributi_formule`

A JSON map of `"<variable>_tot" → [score, mode]`:

```json
{"forza_tot": [7, "linear"], "pf_tot": [3, "linear"], "mana_tot": [0, "0"],
 "res_taglio_tot": [5, "-1"], "ap_tot": [6, "exponential"]}
```

- `score` is an **ordinal 1–10**, meaningful only *relative to other Elder
  Units*. It is not a ReDjango number.
- `mode` is either a shape word (`linear`, `quadratic`, `exponential`, `hi_hi`)
  or a **numeric literal**.
- A numeric literal means **constant at that value**: `"mana_tot": [0, "0"]` is
  "mana is always 0"; `"res_taglio_tot": [5, "-1"]` is "cut resistance is always
  −1". The leading score is noise in that case.
- Strip the `_tot` suffix to get the ReDjango curve key.

The conversion used by the research pipeline (`_curve_from_legacy`) is:

```
progress = clamp((score - 1) / 9, 0, 1)
level1  = very_low.level1  + (very_high.level1  - very_low.level1)  * progress
level20 = very_low.level20 + (very_high.level20 - very_low.level20) * progress
```

**Treat that as a first draft, not an answer.** It maps an ordinal onto a
straight line through the preset range and knows nothing about your creature
family. Always compare against siblings and adjust deliberately, then note the
adjustment.

### 3.3 `django_slim_unitlore`

`id, unit_id, nome, descrizione, immagine`. Match on `unit_id IN (:source_ids)`
**or** `nome = :name` — the link is inconsistent. The description is HTML; strip
tags. **Read it. Actually read it.** It is the single richest source of identity
signal in the whole legacy dataset and the pipeline reduces it to a string.

### 3.4 The canonical research queries

```sql
-- 1. all rows for one normalized name
SELECT * FROM django_slim_unit
WHERE lower(trim(nome)) = lower(trim(:unit_name)) ORDER BY id;

-- 2. their innate abilities
SELECT s.* FROM django_slim_unit u
JOIN django_slim_skillnpc s
  ON s.id IN (u.skill_1_id,u.skill_2_id,u.skill_3_id,u.skill_4_id,
              u.skill_5_id,u.skill_6_id,u.skill_7_id)
WHERE u.id IN (:source_ids) ORDER BY s.id;

-- 3. lore
SELECT * FROM django_slim_unitlore
WHERE unit_id IN (:source_ids) OR lower(trim(nome)) = lower(trim(:unit_name));

-- 4. siblings: same category/archetype, for the differential brief
SELECT id, nome, categoria, archetipo, razza, levels, preset
FROM django_slim_unit WHERE categoria = :categoria ORDER BY nome;
```

Against the **current** DB:

```sql
-- items
SELECT id, nome, tipo_1, tipo_2, tipo_3, tipo_4, lv_loot, rarita, valore, weapon_profile
FROM core_oggetto
WHERE archived_at IS NULL AND archiviato = 0
  AND (lower(nome) LIKE :token OR (tipo_1 = :slot_class AND tipo_2 = :material))
ORDER BY tipo_1, tipo_2, nome;

-- skills with family context
SELECT s.id, s.nome, f.nome AS famiglia, g.nome AS gruppo, g.slug AS gruppo_slug,
       f.is_classe, f.is_religione, f.is_perk,
       s.costo_pe, s.tipo_pe, s.descrizione, s.requisiti,
       s.azioni_attive, s.effetti_passivi, s.profile_tags
FROM core_skill s
JOIN core_famigliaskill f ON f.id = s.famiglia_id
JOIN core_gruppofamiglieskill g ON g.id = f.gruppo_id
WHERE s.archived_at IS NULL
  AND (lower(s.nome) LIKE :token OR lower(f.nome) LIKE :token
       OR lower(s.descrizione) LIKE :token)
ORDER BY f.ordine, s.ordine_famiglia;

-- an Elder-origin Skill, resolved by provenance not by numeric coincidence
SELECT id, nome FROM core_skill
WHERE json_extract(metadata,'$.sourceProject') = 'the_elder_django'
  AND json_extract(metadata,'$.sourceId') = :legacy_id;
```

Record, per Unit, the SQL you ran and the IDs it returned. That is the whole
receipt requirement in v2 — no hashes needed. It exists so a reviewer can
re-run your search, not so a machine can audit you.

---

## 4. The Unit Charter — the heart of v2

Before any payload, write the Charter. It is short prose plus a small amount of
structure, and **every later field must be traceable to a line in it.** If a
field cannot be justified from the Charter or a source record, delete the field
or amend the Charter.

### 4.1 Required sections

```jsonc
{
  "unit": "Ordinatore",
  "sourceIds": [931],
  "kind": "humanoid",                   // + one sentence justifying it if razza disagrees
  "authoredLevels": [1, 20],            // + justification if it differs from legacy `levels`

  "fantasy": "2–4 sentences. What is this thing, in the fiction? Who fears it? What does a player remember after meeting one? Written from the lore row and the source implementation, in your own words.",

  "combatStory": "2–4 sentences. What does a fight against it feel like at low level, and how does that change by level 20? What is the player supposed to *do* about it?",

  "siblings": [
    {"unit": "Cavaliere Redoran", "relation": "nearest",  "mustDifferBy": "Ordinator is a zealot enforcer with a fixed uniform; Redoran is a house knight with a varied bone-armor line and more weapon breadth."},
    {"unit": "Soldato Imperiale", "relation": "same-role", "mustDifferBy": "Imperial fights in formation and is replaceable; the Ordinator is an individual threat with better gear at the same level."},
    {"unit": "Soldato Dremora",   "relation": "contrast",  "mustDifferBy": "Both are iconic-locked heavy infantry; Dremora is supernatural, faster-escalating, and not bound by Tribunal discipline."}
  ],

  "signatureAxes": [
    {"axis": "identity-locked heavy armor at every level", "expressedBy": "equipmentSlots.armatura = [5785] for 1–20"},
    {"axis": "Tribunal discipline / shield-and-mace doctrine", "expressedBy": "competenceProfile + archetype Skill pool"}
  ],

  "must":    ["Armatura Indoril at every authored level", "shield present", "melee range"],
  "mustNot": ["generic armor of any tier", "ranged weapons", "arcane damage Skills", "creature innate actions"],

  "rigidity": "iconic-locked",
  "variationBudget": "weapon choice (mace ≫ ebony longsword), accessories, later Skill picks, competence spread",

  "levelCheckpoints": {
    "1":  "recognisably an Ordinator already: full Indoril, mace, low Skill count, no downgrade",
    "5":  "shield discipline online; first defensive archetype Skill",
    "10": "a real wall; competences read as a trained enforcer",
    "15": "matches the legacy design band; clearly above an Imperial soldier",
    "20": "elite Tribunal enforcer without leaving the armor identity"
  },

  "openQuestions": []
}
```

### 4.2 Rules for writing it

**Differential or nothing.** `siblings` is not decoration. Pick three real Units
— the nearest neighbour, one that shares the role, one deliberate contrast — and
for each one write what this Unit must do *that the sibling must not*. If you
cannot complete that sentence, you do not yet understand the Unit; go back to the
lore and the source implementation. This single field is the main defence
against twenty interchangeable Units.

**Signature-axis budget: one or two, no more.** An axis is a movement identity,
a resistance/vulnerability shape, a control tool, a summon, a regeneration
pattern, a phase behavior, an unusual resource profile, or an equipment lock.
Three or more axes means you are building a boss out of a mook. Zero means you
are building filler. Name them and then *spend* them — every axis must show up
in a concrete field, and every unusual field should trace to an axis.

**`mustNot` is as important as `must`.** It is what makes the critic pass useful
and what turns into `forbidden` in your expectations.

**Level range is a decision.** If the legacy row says `[15,16,17,18,19,20]` and
you author 1–20, say why and say what level 1 looks like. Iconic gear that is
too strong at level 1 is not a reason to hand out leather — either start the Unit
at a higher supported level, or accept and balance the front-loading. **Identity
is not a loot tier.**

**Write it in your own words.** Copy-pasting the lore description into `fantasy`
means you did not read it.

---

## 5. Expectations before payload

Immediately after the Charter, and *before* authoring `skillUnlocks` or
`equipmentSlots`, write the expectations. They are the test the payload must
pass, and writing them first is what stops you from rationalising whatever the
generator happened to produce.

```jsonc
{
  "unit": "Soldato Dremora",
  "levels": [1, 5, 10, 15, 20],
  "variantsPerLevel": 8,
  "allVariants": {
    "generationKind": "humanoid",
    "armorItemIds": [608],
    "shieldItemIds": [622],
    "weaponMaterial": "daedrico",
    "innateActionCount": 0,
    "warningCount": 0
  },
  "atLeastOneVariantHas": ["a defensive archetype Skill by level 5"],
  "allowedVariation": ["weapon type", "skills", "competences", "accessories"],
  "forbidden": ["generic armor", "non-daedric weapons", "creature innate actions", "magic Skills"],
  "differsFrom": {
    "Soldato Imperiale": "higher PF and better material at every shared level",
    "Ordinatore": "different armor family; faster escalation; no Tribunal competence signature"
  }
}
```

The inverse shape for a creature is just as important:

```jsonc
{
  "unit": "Centurione Nanico",
  "allVariants": {
    "generationKind": "creature",
    "equipmentSlotCount": 0,
    "skillUnlockCount": 0,
    "competenceCount": 0,
    "innateActionKeys": ["martello-a-vapore", "…"]
  },
  "forbidden": ["any equipped item", "any SkillPersonaggio record"],
  "curveAssertions": [{"key": "pf", "level": 10, "expected": 57}]
}
```

Compute `curveAssertions` by hand from §2.6 and check them against the preview.
For Lupo `pf` 18→100: `round(18 + 82 × 9/19) = 57`.

**Bad expectations are worse than none.** "Prefer Daedric equipment" is
untestable and permits a low-weight generic result. "`armorItemIds == [608]` in
all 40 previews" is a test.

---

## 6. Humanoid authoring

Work in this order. Do not jump to equipment first — a loot search is not a
character.

**1. Core and shares.** Pick `coreKey` from the fiction, then set `coreShare`.
0.5 is a generalist; 0.35 pushes budget into the archetype half (specialists,
elites with a narrow identity); 0.65 into the core half (durable generic troops).
Set `magicPolicy: "none"` for any Unit that must never cast — it is cheaper and
safer than curating around magic Skills.

**2. Competences.** Two or three at +3..+5 that *are* the character, a handful at
+1/+2, and — this is the part agents skip — **explicit negatives**. `-5` is a
veto; use it for the exclusions you already wrote in `mustNot`. A bandit archer
with `sapienza_magica: -5` and `percezione: 3` reads as a character. A bandit
archer with eight competences at +2 reads as nothing.

**3. Skill pools.** Two curated pools with real level windows and weights.
`core` = durability, mobility, resource, utility. `archetype` = the role. Use
`requiredAtLevel` sparingly — one or two anchors that guarantee the Unit is
itself at a checkpoint, not a scripted build order. Then explicitly **reject**
the plausible-but-wrong candidates and log why (§8). Verify affordability: sum
`costo_pe` across the prerequisite closure and compare against
`xpBase`/`xpGrowth` accumulated to the window's start level.

**4. Equipment as a constraint system.** Choose a rigidity class and honour it:

| Policy | Defining armor | Weapons | Example |
|---|---|---|---|
| `open` | several common families overlap | several compatible types and materials | Mercenario |
| `path-locked` | one authored light/heavy material route | type stays coherent, material advances | Arciere Bandito |
| `faction-locked` | the faction model never leaves the pool | several lore-valid faction weapons | Soldato Imperiale, Cavaliere Redoran |
| `iconic-locked` | one inseparable visual identity at all authored levels | variation moves almost entirely to weapons/accessories | Ordinatore, Soldato Dremora |

Locked identity ≠ identical clones. Move the variation to weapons, shields,
accessories, enchantments and Skill picks — never to the defining armor. Give
armor windows deliberate **overlap** so two copies at level 5 can differ without
either stopping being the archetype.

**5. Coverage proof.** Build a level × slot matrix, 1–20, and check:
every required slot has ≥1 eligible entry at every authored level; no forbidden
family appears anywhere; every possible weapon has a matching competence; every
possible armor has a matching competence; accessory counts respect group
capacity; nothing exceeds the Unit's narrative tier ceiling. A gap at levels
12–13 is a blocker, not a rounding error.

**6. Stat growth stays off.** Humanoids grow through Skills, perks, competences
and gear. `allowHumanoidStatGrowth: true` is an exception requiring a written
justification in the Charter — not a convenience.

### Worked humanoid payload (shape reference)

```json
{
  "name": "Arciere Bandito",
  "category": "Banditi",
  "archetypeDescription": "Predone a distanza che apre dall'imboscata e usa il terreno.",
  "generation": {
    "kind": "humanoid",
    "coreKey": "warrior",
    "coreShare": 0.45,
    "magicPolicy": "none",
    "allowedClassFamilies": ["Ranger"],
    "allowedReligionFamilies": [],
    "allowedRaces": [],
    "xpBase": 20,
    "xpGrowth": 1,
    "finalSpendingPasses": 4,
    "allowHumanoidStatGrowth": false
  },
  "competenceProfile": {
    "percezione": 4, "rapidita_di_mano": 2, "strategia_militare": 2,
    "furtivita": 3, "sopravvivenza": 2,
    "sapienza_magica": -5, "diplomazia": -3, "suonare": -3
  },
  "skillUnlocks": [
    {"skillId": 71,  "pool": "core",      "weight": 9,  "minLevel": 1, "maxLevel": 20},
    {"skillId": 64,  "pool": "core",      "weight": 8,  "minLevel": 1, "maxLevel": 20},
    {"skillId": 335, "pool": "archetype", "weight": 10, "minLevel": 1, "maxLevel": 20, "requiredAtLevel": 1},
    {"skillId": 336, "pool": "archetype", "weight": 10, "minLevel": 1, "maxLevel": 20},
    {"skillId": 601, "pool": "archetype", "weight": 8,  "minLevel": 5, "maxLevel": 20}
  ],
  "equipmentSlots": [
    {"slot": "armatura", "itemId": 595, "minLevel": 1, "maxLevel": 3,  "weight": 4, "chance": 1},
    {"slot": "armatura", "itemId": 596, "minLevel": 2, "maxLevel": 6,  "weight": 5, "chance": 1},
    {"slot": "armatura", "itemId": 597, "minLevel": 4, "maxLevel": 11, "weight": 5, "chance": 1},
    {"slot": "armatura", "itemId": 598, "minLevel": 9, "maxLevel": 20, "weight": 4, "chance": 1},
    {"slot": "arma", "itemId": 510, "minLevel": 1, "maxLevel": 3,  "weight": 4, "chance": 1},
    {"slot": "arma", "itemId": 511, "minLevel": 2, "maxLevel": 6,  "weight": 5, "chance": 1},
    {"slot": "arma", "itemId": 512, "minLevel": 4, "maxLevel": 11, "weight": 5, "chance": 1},
    {"slot": "arma", "itemId": 513, "minLevel": 9, "maxLevel": 20, "weight": 4, "chance": 1}
  ],
  "equipmentGroups": [],
  "accessoryCountByLevel": [],
  "innateActions": [],
  "statProfile": {"baseModifiers": {}, "perLevelModifiers": {}, "milestones": [], "curves": []}
}
```

The IDs above are illustrative — **re-verify every one against the current DB
before use.** A production pool needs more affordable alternatives and full
prerequisite closure across all four level bands.

### Worked identity lock (Ordinatore)

```json
[
  {"slot": "armatura", "itemId": 5785, "minLevel": 1, "maxLevel": 20, "weight": 1, "chance": 1},
  {"slot": "scudo",    "itemId": 621,  "minLevel": 1, "maxLevel": 20, "weight": 1, "chance": 1},
  {"slot": "arma",     "itemId": 5718, "minLevel": 1, "maxLevel": 20, "weight": 5, "chance": 1},
  {"slot": "arma",     "itemId": 228,  "minLevel": 1, "maxLevel": 20, "weight": 2, "chance": 1}
]
```

Every Ordinator wears Indoril. Variation is the weighted mace-vs-longsword split,
Skill picks, accessories and seed — never an occasional generic-armor spawn.

---

## 7. Creature authoring

Creatures get **no** Skills, perks, competences, inventory or equipment. Their
entire character is: curves + innate actions + the fiction in
`archetypeDescription` / `loreDescription`.

**1. Family first.** Before curves, place the creature in its family and fill in
the coherence matrix. This is where per-unit attention actually pays off:

| Axis | Lupo `#986` | Cliff Racer `#971` | Drago `#1020` |
|---|---|---|---|
| Movement identity | fast ground leap | aerial dive | strategic flight |
| Durability evidence | PF score 3 | PF score 4 | PF score 10 |
| Signature control | self-buff at a defence cost | push / stun | breath zones, tail sweep |
| Cognition evidence | intelligenza 2 | intelligenza 2 | intelligenza 8 |
| Must not inherit | elemental breath | pack fury | low-animal cognition |

Wolves share pack mobility but not dragon flight. Frost beings share cold
resistance but not identical attacks. Constructs share immunities without being
palette swaps. Fill a row for **your** creature against at least two relatives
before authoring numbers.

**2. Curves.** Convert `profili_attributi_formule` per §3.2, then *adjust
deliberately*:

- Compare each key within the family. A wolf's `pf` should sit below a bear's and
  above a rat's, whatever the ordinals say.
- Preserve literal constants exactly (`mana` 0→0, `res_taglio` −1→−1).
- A former shaped curve keeps its endpoints and becomes linear — note it.
- Omit keys ReDjango derives. Omit keys you cannot justify.
- Record every deviation from the mechanical conversion with one line of reason.

**3. Innate actions.** The legacy `SkillNpc` list is a **baseline, not a
ceiling.** You are explicitly authorised to add innate actions when they are
strongly supported by lore, biology, supernatural nature, expected combat
behavior, and family comparison. You are equally authorised to *drop* a legacy
action that is incoherent — say so.

Each action needs: stable `key`, evocative `name`, a `description` precise enough
to adjudicate (range, target pattern, damage type, effect, save/contest), a level
window, parsed `costs` from the six legal resources, `trigger`, `duration`, and
a **legality receipt** naming the current rule or implemented Skill that makes it
legal. Re-author unsupported legacy mechanics per §2.10.

Aim for a shape, not a pile: typically one reliable attack, one signature axis
expression, one situational tool. Level windows let a creature grow into its
scarier actions — use them.

### Worked creature payload (Lupo)

```json
{
  "name": "Lupo",
  "category": "Animali",
  "archetypeDescription": "Predatore naturale da branco, rapido e resistente.",
  "generation": {"kind": "creature"},
  "competenceProfile": {},
  "skillUnlocks": [],
  "equipmentSlots": [],
  "equipmentGroups": [],
  "accessoryCountByLevel": [],
  "statProfile": {
    "baseModifiers": {}, "perLevelModifiers": {}, "milestones": [],
    "curves": [
      {"key": "pf",           "profile": "medium", "level1": 18, "level20": 100},
      {"key": "forza",        "profile": "high",   "level1": 11, "level20": 30},
      {"key": "velocita",     "profile": "high",   "level1": 11, "level20": 30},
      {"key": "agilita",      "profile": "high",   "level1": 11, "level20": 30},
      {"key": "intelligenza", "profile": "low",    "level1": 6,  "level20": 16},
      {"key": "mana",         "profile": "custom", "level1": 0,  "level20": 0},
      {"key": "res_taglio",   "profile": "custom", "level1": -1, "level20": -1}
    ]
  },
  "innateActions": [
    {
      "key": "balzo-predatorio",
      "name": "Balzo Predatorio",
      "description": "Salta fino a 3 esagoni in linea e attacca il bersaglio all'arrivo con +3 Attacco e un reroll del dado di attacco.",
      "minLevel": 1, "maxLevel": 20,
      "costs": {"pa": 7, "energia": 2},
      "trigger": "Azione", "duration": "Istantanea", "icon": "artiglio"
    },
    {
      "key": "furia",
      "name": "Furia",
      "description": "Ottiene +4 Forza e +3 Attacco, ma -2 Difesa.",
      "minLevel": 1, "maxLevel": 20,
      "costs": {"pa": 4, "energia": 4},
      "trigger": "Azione", "duration": "3 turni", "icon": "artiglio"
    }
  ]
}
```

At level 10, `pf = round(18 + 82 × 9/19) = 57`. `mana` and `res_taglio` are 0 and
−1 at every level. Assert that arithmetic in a test; do not eyeball it.

---

## 8. The dossier

One file per Unit — the durable working memory. v2 trims v1's cryptographic
overhead to what a reviewer actually uses.

```jsonc
{
  "schemaVersion": 2,
  "conversionKey": "elder-unit:django_slim_unit:931",
  "status": "draft | needs-review | blocked | approved | applied",

  "sourceSnapshot": {
    "project": "the_elder_django",
    "table": "django_slim_unit",
    "ids": [931],
    "normalizedName": "ordinatore",
    "rows": [ /* verbatim legacy rows, frozen after discover */ ],
    "lore": [ /* stripped lore rows */ ],
    "legacyActions": [ /* SkillNpc rows */ ]
  },

  "charter": { /* §4 */ },
  "expectations": { /* §5 */ },

  "evidence": [
    {"claim": "Armatura Indoril", "source": "unit:931.armatura[0]"},
    {"claim": "soldato della fede", "source": "unitlore:90"}
  ],

  "catalogQueries": [
    {"purpose": "indoril armor", "sql": "…", "params": {"token": "%indoril%"}, "resultIds": [5785, 5718]}
  ],

  "proposal": { /* the Unit-management payload, §2.1 */ },

  "rejectedCandidates": [
    {
      "candidate": {"skillId": 348, "name": "Affondo"},
      "decision": "reject",
      "reasonCode": "weapon-role-mismatch",
      "reason": "Melee attack conflicts with an equipment pool containing only short bows.",
      "evidence": ["equipment-matrix:arma:1-20", "charter.mustNot"]
    }
  ],

  "deviations": [
    {"what": "ap curve", "from": "legacy exponential", "to": "linear 2→7", "why": "engine interpolates linearly; endpoints preserved"}
  ],

  "findings": [],
  "simulation": {"previews": [], "warnings": []},
  "approval": null
}
```

Prefer a documented rejection over a lowered weight. **Weight controls
frequency; it does not make an incoherent outcome acceptable.**

---

## 9. Workflow and gates

A resumable state machine per Unit. Stages `research`→`score` are yours;
`human-approve` is not.

| Stage | You do | You must not touch |
|---|---|---|
| `discover` | group legacy rows by normalized name, freeze `sourceSnapshot` | source rows |
| `research` | read rows, lore, legacy actions, source implementation; run catalog queries; pick and read 3 siblings | proposal |
| `charter` | write §4 in your own words | source snapshot |
| `expect` | write §5 **before** the payload | charter (amend explicitly if you must) |
| `design` | author the payload, field by field, each traceable to the charter | frozen snapshot, expectations |
| `critic` | attack your own proposal: identity drift, coverage gaps, prerequisite/affordability, magic policy, family clone risk, rule legality. Findings only. | proposal |
| `resolve` | change the proposal in response to findings, or mark `blocked` | findings history |
| `dry-run` | `_clean_unit_values(payload)` offline, then a rollback-only save | — |
| `simulate` | 5 levels × 8 variants of `management.units.preview` | expectations |
| `score` | run the scorecard in §11 | — |
| `human-approve` | present the checkpoints and wait | everything |
| `apply` | idempotent upsert keyed on `metadata.sourceIds` + provenance write | the approved proposal |

Offline schema check without touching the DB:

```python
from backend.combat.unit_management_services import _clean_unit_values
_clean_unit_values(payload)   # raises ApiError with the exact field path
```

**The critic stage is not optional and not self-congratulation.** Write findings
as if you were trying to get the Unit rejected. If your critic pass produces zero
findings on a first draft, it did not run.

---

## 10. The bulk pipeline: correct role

`backend/combat/legacy_unit_import.py` (`build_import_run`,
`write_import_artifacts`, `apply_import_run`, `load_approvals`,
`validate_import_write_path`) can mechanically derive a payload for all 203 rows:
grouping, curve conversion, equipment name→ID resolution, rigidity guessing,
unsupported-mechanic pattern flags
(`unsupported_poison_damage`, `unsupported_strength_damage`), provenance-keyed
idempotent apply.

**Use it for `discover` and `research`. Do not let it perform `charter`,
`expect`, or `design` for a calibration Unit.** Its identity briefs are derived
from column values; its rigidity comes from a faction-token list; its curves come
from the ordinal formula in §3.2. Run end-to-end, it produces exactly the
failure mode this guide exists to prevent: twenty legal, provenanced,
interchangeable Units.

The correct sequence: hand-author the 20 calibration Units one at a time with a
human in the loop; extract the patterns that survived review; **then** let the
pipeline handle the ~180-unit tail, with every tail Unit still passing the hard
gates and spot-checked in family batches.

---

## 11. Validation, simulation, rollout

### Deterministic gates (pass/fail — a qualitative score cannot compensate)

| Gate | Requirement |
|---|---|
| Schema | `_clean_unit_values` accepts the complete payload |
| Provenance | `metadata.sourceIds` present and unique across Units |
| Name | unique case-insensitively |
| Kind contract | creature: no Skills/equipment/competences. humanoid: equipment present, no innate actions, growth off unless justified |
| Levels | every window inside 1–20, `minLevel ≤ maxLevel` |
| Curves | exact endpoints incl. constants; only the 28 legal keys; hand-computed checkpoint values match |
| Catalog | every `skillId` / `itemId` live and non-archived |
| Slot compat | every item passes `item_compatible_with_equipment_slot` for its slot |
| Coverage | every required slot has ≥1 eligible item at **every** authored level |
| Competence match | every possible weapon and armor has a matching authored competence |
| Prerequisites | closure resolvable and affordable inside each level window |
| Policy | magic / class / religion / race policies hold for every pool entry |
| Accessories | bands non-overlapping, covering 1–20, within group capacity |
| Rule vocabulary | every damage type, status, resource, variable and effect resolves to a current implemented rule |
| Determinism | the same named variant produces the same signature twice |
| Warnings | zero unexplained generator warnings |

### Simulation

40 previews per Unit: levels **1, 5, 10, 15, 20** × **8 variants**. Use named
variants (`"calibration-<unit>-1"…`) for reproducibility plus `"auto"` for the
random path — `AUTO_VARIANT_VALUES = {"", "auto", "casuale", "random"}`, and the
seed is derived stably from Unit + variant.

For each preview, diff the report against the expectations: `skills`, `perks`,
`equipment`, `innateActions`, `competences`, `statCurves`, `race`, `xp`,
`warnings`. Then do the part no gate can do: **read three of the forty**. Ask out
loud whether it plays differently from its siblings.

Known generator warnings and what they mean:

| Warning | Meaning |
|---|---|
| `Nessun perk {tier} compatibile disponibile al livello {level}.` | your perk pools are too thin |
| `Slot equipaggiamento Unit non valido: {slot}.` | a slot key that is not in `EQUIPMENT_SLOT_LABELS` |
| `{n} PE generali restano disponibili: nessuna Skill configurata è acquistabile.` | pool too small, too expensive, or blocked by prerequisites |

### Scorecard

```json
{
  "unit": "Lupo",
  "hardGates": {"passed": 16, "failed": 0},
  "previews": {"levels": [1,5,10,15,20], "variantsPerLevel": 8, "completed": 40, "warnings": 0},
  "determinism": {"variant": "calibration-lupo", "match": true},
  "qualitative": {"identity": 5, "sourceFidelity": 5, "familyCoherence": 4, "meaningfulVariety": 4, "siblingDistinctness": 5},
  "decision": "ready-for-human-approval"
}
```

Threshold: ≥4/5 in every category, and the reviewer must explain each score in
one sentence. `siblingDistinctness` is the v2 addition and the one that most
often should fail.

### Rollout

Release in small faction/family batches. Before each batch: database backup
(`backups/`), dry-run receipts, idempotent apply keyed on `sourceIds`. After:
post-import counts and a family spot-check. Roll back **by import batch**, never
by destructive table replacement.

---

## 12. The 20 calibration Units

These are proposals, not approved imports. For each one, replace names with
verified current IDs, write the Charter with three real siblings, and write the
five checkpoint expectations. `#` refers to `django_slim_unit.id`.

### Humanoids

All ten have **empty** `skill_1_id…skill_7_id` — their equipment is preservation
evidence, their Skill and competence pools are authored. Say so in each Charter.

| Unit | IDs | Rigidity | Key notes |
|---|---|---|---|
| Soldato Imperiale | 838–840 | faction-locked | `#5782 Armatura di servizio Imperiale (acciaio)`, `#5789 Scudo Imperiale`; sword/maul/axe iron→steel→Nordic; formation, shield, medium weapons, endurance, `strategia_militare` |
| Mercenario | 848–851 | open | overlapping iron/leather → steel/chitin → Nordic/elven → Orcish/glass; **every generated weapon family needs a matching competence**; authored elite ceiling |
| Arciere Bandito | 951–952 | path-locked | short bow + knife evidence; light leather/chitin/elven overlap; ranged/Ranger, ambush, `percezione`, `furtivita`, `sopravvivenza`; **forbid generic melee in the Core pool**; document the bandit ceiling if extending to 1–20 |
| Mago da Battaglia | 884–886 | path-locked | staff-or-longsword choice, Evocation robe/armor path; test that every build affords both defensive Core and a coherent spell/weapon branch |
| Guaritore | 887–890 | path-locked | Restoration robes and staves novice→master; support Core; healing/cleanse/protection/resource; **no damage magic added merely to spend PE** |
| Agente Morag Tong | 924–925 | faction-locked | `#5769 Armatura Morag Tong (chitina)`; stilettos `#5711` glass / `#5713` ebony + verified kriss equivalents; stealth, poison, precision, composure, short weapons |
| Ordinatore | 931 | iconic-locked | `#5785 Armatura Indoril (ebano)` at every authored level; prefer `#5718 Mazza Indoril (ebano)` with a controlled ebony longsword alternative; shield/heavy defense, Tribunal discipline; legacy band is `[15..20]` — justify any extension; **never downgrade identity at low level** |
| Cavaliere Redoran | 940–941 | faction-locked | `#5773 Armatura rinforzata Redoran (ossa)`; shield/tank; vary the Redoran longsword line `#5723–#5728` + lore-valid axes by level |
| Mago Telvanni | 934–935 | path-locked | Illusion robes/staves; mage or specialist Core; control, summons, mobility, scholarship; **avoid generic healer or frontline pools** |
| Soldato Dremora | 944 | iconic-locked | classify `humanoid` despite `razza="Entità"`; `#608 Armatura (daedrico)`, `#622 Scudo (daedrico)` at every supported level; vary only vetted Daedric sword/maul/axe; disciplined heavy warfare, **not** creature actions |

### Creatures

| Unit | ID | Anchors and signature axes |
|---|---|---|
| Lupo | 986 | PF 3, velocità/agilità 7; `Balzo Predatorio`, `Furia`; pack mobility |
| Cliff Racer | 971 | PF 4 vs velocità 8; `Colpo d'Ala`, `Tuffo Aereo`, `Stridio Sonico`; aerial harasser |
| Regina Kwama | 982 | PF 8, difesa/riduzione fisica 7, constant velocità/agilità 1; `Evoca Minion`, `Nuvola di Spore`, `Sputo Velenoso` — **re-author the "poison" mechanically**; brood control |
| Dreugh | 978 | forza/resistenza 7, constant rd_fis 3, res_fuoco 1, res_elettro −1; `Pelle di Pietra`, `Rigenerazione`, `Colpo di Coda`, `Sottrai Vita` |
| Atronach del Gelo | 1007 | forza/resistenza 8, constant res_gelo 5 and res_fuoco −2; `Soffio Gelido`, `Armatura di Ghiaccio`, `Tormenta` |
| Lich | 1013 | intelligenza/mana/potere 9, constant res_gelo 5; `Sottrazione Spirituale`, `Rianima Morti`, `Barriera Mistica`, `Tocco Necrotico` — verify each against implemented rules |
| Spriggan | 1018 | PF/resistenza 7, res_fuoco low 2; `Radici Intrappolanti`, `Evoca Minion`, `Sottrai Vita` |
| Drago | 1020 | PF/forza/resistenza 10, bounded intelligenza 8, flight, three elemental breaths, stone skin, tail sweep — **prefer a variant policy over giving every breath to every dragon** |
| Centurione Nanico | 1031 | PF 9, forza/resistenza/attacco 8, velocità 4; the legacy Dwemer warhammer becomes an **innate hammer action** because creatures cannot equip items; steam/construct traits only if supported |
| Anomalia Magica | 1023 | low PF/forza 3, mana 8, former `hi_hi` elemental profiles → documented linear endpoints; `Distorsione Temporale`, `Bruciatura di Mana`, `Scudo di Mana` |

The Dremora/Centurione pair is a useful classification regression test: one is a
humanoid with zero innate actions and a locked loadout, the other is a creature
with zero equipment whose weapon lives inside an innate action.

---

## 13. Failure catalogue

Check yourself against these before requesting approval.

1. **The interchangeable twenty.** Every Unit legal, provenanced, and secretly
   the same. *Test:* cover the names in two dossiers — can you still tell them
   apart? *Fix:* the `siblings` field, honestly written.
2. **Loot-search authoring.** Equipment picked because it matched a name query,
   not because it constrains the character. *Fix:* choose rigidity first.
3. **Identity downgrade at low level.** Iconic gear replaced with leather at
   level 1 to "balance" it. *Fix:* start higher or balance the surroundings.
4. **Weight as an excuse.** A 0.5-weight incoherent option instead of a
   rejection. *Fix:* `rejectedCandidates`.
5. **Plausible-sounding mechanics.** Poison damage, Strength damage, a new
   resistance, a new status. *Fix:* §2.10 and a precedent query.
6. **Curve cargo-culting.** Copying legacy shape words, or trusting the ordinal
   conversion without a family comparison. *Fix:* §7 step 2.
7. **Competence mush.** Eight competences at +2 and no negatives. *Fix:* two or
   three at +4/+5, real `-5` vetoes.
8. **Unaffordable pools.** A prerequisite closure nobody can buy inside the
   window. *Fix:* sum `costo_pe` against accumulated XP.
9. **Coverage holes.** No legal item at levels 12–13. *Fix:* the level × slot
   matrix.
10. **Silent classification.** Trusting `razza` over behavior. *Fix:* justify
    `kind` in the Charter whenever the legacy string disagrees.
11. **Unread lore.** `fantasy` that paraphrases the column headers. *Fix:* read
    `django_slim_unitlore` and write in your own words.
12. **Warning blindness.** Shipping with generator warnings "that always
    appear". *Fix:* explain every warning or fix its cause.

---

## 14. Definition of done, per Unit

A Unit is done when **all** of the following are true:

- [ ] `sourceSnapshot` frozen with every legacy `id` for the normalized name
- [ ] lore and legacy actions actually read, and reflected in the Charter
- [ ] Charter complete, with three named siblings and a filled `mustDifferBy`
- [ ] one or two signature axes named, each expressed by a concrete field
- [ ] `kind` justified where the legacy `razza`/`categoria` disagrees
- [ ] authored level range justified against legacy `levels`
- [ ] expectations written **before** the payload
- [ ] every payload field traceable to the Charter or a source record
- [ ] every mechanic backed by a current rule or an implemented precedent
- [ ] rejected candidates logged with reason codes
- [ ] deviations from mechanical conversion logged with reasons
- [ ] all deterministic gates pass
- [ ] 40 previews complete, zero unexplained warnings, expectations matched
- [ ] hand-computed curve checkpoints match the preview
- [ ] at least three previews read by a human, not just diffed
- [ ] scorecard ≥4/5 in all five categories, each explained
- [ ] named human approval recorded with a timestamp
- [ ] apply is idempotent on `metadata.sourceIds` and writes provenance

No workflow can guarantee artistic quality. This one guarantees that every Unit
received traceable attention, that no Unit ships without source evidence,
catalog-valid choices, an explicit statement of how it differs from its
neighbours, deterministic mechanical tests, adversarial review, and a named human
approval — and that failures return to the dossier with actionable findings
instead of being patched in generated characters.

---

*Last verified against the codebase: 2026-07-28. Constants quoted from
`backend/combat/unit_generation.py`, `backend/combat/unit_management_services.py`,
`backend/combat/rules.py`, `backend/characters/services/inventory_rules.py`,
`backend/characters/race_rules.py`, `backend/core/competence_defaults.py`,
`backend/core/models.py`. Re-verify before relying on any of them.*

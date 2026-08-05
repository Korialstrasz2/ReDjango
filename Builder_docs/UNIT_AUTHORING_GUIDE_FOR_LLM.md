# Unit authoring contract for LLMs

This document is authoritative operating procedure for an LLM that creates or
edits `core.Unit` records in ReDjango. Follow it literally. It describes the
**live management API DTO**, not Django's stored field names.

Goal: create a blueprint that survives save validation, generates correctly in
Combat, preserves its intended identity across levels and variants, and has a
traceable explanation for every Skill, item, accessory, stat and action.

Read `Builder_docs/UNIT_GENERATION.md` for background only. Where it conflicts
with this document, this document and current source code win. In particular,
this document corrects obsolete claims about `animal`, curve shapes and custom
Cores.

---

## 0. Non-negotiable rules

1. **Use management API/service, never direct ORM writes.** The service
   validates current catalog references and creates Unit metadata safely.
2. **Discover before proposing.** Query live configuration, Skills and Items.
   Never invent an ID, race, subrace, family, slot, accessory profile,
   competence key, stat-curve key or Item type.
3. **Classify by mechanics, not lore.** A humanoid-looking Lich can be a
   `creature`; an Xivilai can be `humanoid`. The generation contract decides.
4. **Do not promise automation that Unit data does not implement.** Creature
   innate actions are authored rules/reminders, not combat executors.
5. **Create complete payload in one save request only after discovery.** Do not
   save a skeleton, then guess IDs or fields in later requests.
6. **Preview is mandatory.** A successful save is not proof that every level,
   prerequisite, perk, item and accessory outcome is valid.
7. **Treat catalog records as live dependencies.** Archiving/altering a Skill,
   Item, Perk or shared accessory catalog can change or break later output.

The user must have Master or Admin role. Backend independently enforces this.

---

## 1. What a Unit is and is not

A Unit is a reusable blueprint. Generator creates a normal `Personaggio` from
it at requested level `1..20`.

| Contract | Use when | Receives | Must not receive |
|---|---|---|---|
| `creature` | Animal, monster, construct, elemental, undead chassis, supernatural being without character progression | curves, chassis modifiers, innate actions, optional portrait | Skills, PE spending, perks, Competences, equipment, accessory profile |
| `humanoid` | Person/NPC using character progression and equipment | Core/archetype Skills, PE, perks, Competences, race/subrace, equipment, shared accessory profile, optional direct chassis growth | innate actions |

Only `creature` and `humanoid` are valid new values. Incoming legacy
`animal` is normalized to `creature`; never emit it.

### Mechanical decision test

Use `humanoid` only when all are true:

- role must learn current catalog Skills through XP;
- role must receive minor/major perk progression;
- role needs normal equipment or shared accessories;
- role benefits from race/subrace and weighted Competence progression.

Otherwise use `creature`. Examples:

- **Cannibal Bloodlord**: usually humanoid if it has weapon/armour, Skills and
  a racial/subracial progression. Make it creature only if its entire combat
  identity is fixed chassis curves plus authored actions.
- **Wild Stingbee**: creature. It has curves and authored `Sting`, `Venom` and
  `Flight` actions; it does not receive human Skills, jewelry or weapons.
- **Lich**: creature is valid when represented by a fixed magical chassis and
  actions; category `Non Morti` does not require humanoid progression.

---

## 2. Mandatory discovery phase

Do this before drafting payload. Persist discovery evidence in your proposal
notes: endpoint/query, selected IDs, reason for each selection, and excluded
alternatives.

### 2.1 Read live Unit configuration

```text
GET /api/v1/management/units
```

Use `data.configuration` as sole source for:

- `kinds`;
- five permitted `cores` and their profile vectors;
- `tags` and their `-5..5` bounds;
- `equipmentSlots`;
- active `accessoryProfiles` keys/descriptions;
- valid `competences` keys;
- `magicPolicies`;
- active Class and Religion family names;
- exact races and each race's exact subraces;
- supported stat-curve keys, labels and presets.

Also inspect five comparable existing Units:

```text
GET /api/v1/management/units/<id>
```

Choose comparable Units by mechanics, not only name/category. Inspect their
full serialized DTO, real equipment bands, pool widths, Skill families and
portrait. This endpoint does **not** return generation traces, full Item rules
or complete Skill mechanics; obtain those separately below.

### 2.2 Query candidate Skills and Items

```text
GET /api/v1/management/units/options?kind=skill&query=<term>&limit=200
GET /api/v1/management/units/options?kind=item&query=<term>&limit=200
```

Options endpoint returns lightweight data only. For every candidate, inspect
full source/catalog details through the stated catalog endpoints, management
workspace, database or code before using it:

| Dependency | Must inspect before selection |
|---|---|
| Skill | ID, archived state, group/family, Class/Religion/Perk flag, base price, dynamic price behavior, prerequisites including transitive chain, structured requirements, passives/actions, profile tags, `SpellDefinition` presence, and whether it is magic |
| Item | ID, archived state, `archiviato`, `tipo_1..tipo_4`, slot compatibility, one/two-handed weapon behavior, structured effects, `regole_speciali`, rarity, weight, level/tier text and material |
| Accessory profile | key, purpose, effect-kind pools, physical-slot pools, duplicate policy, count curve, tier jitter and live catalog fallback behavior |
| Race/subrace | exact strings from configuration, resulting automatic effects and whether subrace exists under every selected primary race |
| Perk catalog | active minor and major Perks, milestone-name availability, prerequisites and structured requirements at every target level |

`options` excludes archived Skills and both archived/`archiviato` Items. It
does not prove semantic compatibility.

Useful detailed reads:

```text
GET /api/v1/management/skills/<skillId>
GET /api/v1/management/items?query=<term>&limit=100
GET /api/v1/compendium/items?query=<term>&with_effects=true
```

`management/skills/<skillId>` exposes Skill detail including prerequisites.
Item catalog/compendium output provides Item type values, effects and special
rules. If an endpoint still omits a needed relation or a list is truncated,
inspect the management workspace, database or listed source before deciding.

### 2.3 Required source inspection when data is incomplete

If endpoint/UI does not expose a needed detail, inspect these source locations
before proposing a record:

```text
backend/combat/unit_management_services.py   save DTO and validation
backend/combat/unit_generation.py            actual generator semantics
backend/combat/accessory_profiles.py         shared accessory selection
backend/characters/race_rules.py             race/subrace effects
backend/characters/services/inventory_rules.py slot and hand rules
backend/core/skill_pricing.py                calculated Skill price
backend/core/skill_requirements.py           structured requirements
```

Never infer missing mechanics from names, descriptions or historical Elder
content.

---

## 3. Live write protocol

Normal actions use `POST /api/v1/actions` with project action envelope and
CSRF headers. Unit save payload:

```json
{
  "action": "management.units.save",
  "requestId": "uuid-or-other-client-id",
  "context": {"screen": "management"},
  "payload": {
    "unitId": null,
    "values": {}
  }
}
```

- `unitId: null`/omitted creates Unit.
- Existing integer `unitId` updates Unit.
- `values` uses DTO names in section 4.
- `metadata` is **read-only** in this path. New Unit metadata is set to
  `{"sourceProject":"redjango","authoring":"unit-management"}`. Do not
  submit Elder provenance, approval data, arbitrary metadata or seed values.
- `loreImageId` is optional. Omit it to preserve existing portrait on update;
  include `null`/blank to clear it. On create, omit or set `null` when no
  portrait is intended.

Preview only after save:

```json
{
  "action": "management.units.preview",
  "requestId": "uuid-or-other-client-id",
  "context": {"screen": "management"},
  "payload": {
    "unitId": 123,
    "level": 10,
    "variant": "audit-bloodlord-v1"
  }
}
```

Preview invokes real Combat generation then rolls database transaction back.
No preview character remains stored. Read:

```text
data.management.preview.totals
data.management.preview.skills
data.management.preview.equipment
data.management.preview.competences
data.management.preview.innateActions
data.management.preview.trace
```

`variant` rules:

- named non-empty string: deterministic seed from Unit ID + variant, subject
  to unchanged live catalog/order/profile configuration;
- empty, `auto`, `casuale`, `random`: new random variant each call.

---

## 4. Complete management DTO

All fields belong in `payload.values`. Use camelCase names exactly.

```json
{
  "name": "string, required, unique case-insensitively, max 180",
  "category": "string, optional, max 80",
  "loreImageId": "positive image ID or null",
  "archetypeDescription": "string",
  "loreDescription": "string",
  "notes": "string",

  "generation": {},
  "archetypeTags": {},
  "competenceProfile": {},
  "skillUnlocks": [],
  "equipmentSlots": [],
  "equipmentGroups": [],
  "accessoryCountByLevel": [],
  "accessoryProfileKey": "active profile key",
  "innateActions": [],
  "statProfile": {},
  "levels": []
}
```

`levels`, `statProfile.baseModifiers`, `statProfile.perLevelModifiers` and
`statProfile.milestones` are compatibility/advanced chassis controls. Do not
use them for new content unless source inspection confirms intended effect and
preview proves it. They accept modifier keys more broadly than stat curves;
never invent target keys. For humanoids, `perLevelModifiers`, `milestones`,
`levels` and curves have runtime effect only when
`generation.allowHumanoidStatGrowth` is `true`.

### 4.1 Stored-field mapping

Management DTO deliberately differs from stored model fields. Do not send
right-side names to API.

| API DTO | Stored Unit field |
|---|---|
| `name` | `nome` |
| `category` | `categoria` |
| `loreImageId` | `lore_image_id` |
| `archetypeDescription` | `archetipo_descrizione` |
| `archetypeTags` | `archetipo_tags` |
| `competenceProfile` | `profilo_competenze` |
| `generation` | `generation_rules` |
| `skillUnlocks` | `skill_unlocks` |
| `equipmentSlots`, `equipmentGroups`, `accessoryCountByLevel` | `equipment_profiles` |
| `accessoryProfileKey` | `accessory_profile` relation |
| `innateActions` | `skill_actions` |
| `statProfile` | `stat_profiles` |
| `loreDescription` | `lore_description` |

### 4.2 Identity fields

| Field | Rule |
|---|---|
| `name` | Required, trimmed, max 180, unique ignoring case. Use role name, not a random generated-character name. |
| `category` | Optional display taxonomy only. It never decides `generation.kind`. |
| `archetypeDescription` | Required by authoring quality, though save permits blank. State tactical role, range, defense, magic, behavior and why chosen contract fits. |
| `loreDescription` | Narrative only. Never place executable rules exclusively here. |
| `notes` | Authoring rationale, source references, dependency assumptions, manual mechanics and verification outcome. Do not claim false provenance. |
| `loreImageId` | Optional valid Unit portrait only; section 10. |

---

## 5. `generation` object

```json
{
  "kind": "humanoid",
  "coreKey": "warrior",
  "coreShare": 0.5,
  "startingXp": 0,
  "xpBase": 20,
  "xpGrowth": 1,
  "competenceStartingXp": 5,
  "competenceXpBase": 15,
  "competenceXpGrowth": 0,
  "finalSpendingPasses": 4,
  "magicPolicy": "none",
  "allowedClassFamilies": [],
  "allowedReligionFamilies": [],
  "allowedRaces": [],
  "allowedSubraces": [],
  "allowHumanoidStatGrowth": false
}
```

| Key | Validity and real effect |
|---|---|
| `kind` | Required: `creature` or `humanoid`. Legacy `animal` becomes `creature`; never use it. |
| `coreKey` | Humanoid required: exact configured one of `warrior`, `mage`, `stealth`, `support`, `specialist`. Creature stores empty Core and ignores it. Custom `coreProfile` is not accepted by management authoring. |
| `coreShare` | Number `0.1..0.9`. Guides Core/archetype spending preference from shared general XP; it does not create two currencies. |
| `startingXp` | Integer `>=0`, credited at level 1 for humanoids. |
| `xpBase`, `xpGrowth` | Integers `>=0`; every humanoid level after 1 earns `xpBase + (level - 1) * xpGrowth`. |
| `competenceStartingXp`, `competenceXpBase`, `competenceXpGrowth` | Integers `>=0`; drive weighted humanoid Competence spending. Ignored by creatures. |
| `finalSpendingPasses` | Integer `0..20`; additional final attempts to buy affordable configured Skills. |
| `magicPolicy` | `any` or `none`. `none` rejects magic Skills by school group/name, positive magic tags or `SpellDefinition`. |
| `allowedClassFamilies` | Exact configured Class-family names. Required in practice for every selected Class Skill. Do not rely on empty list acceptance during save: generator rejects Class Skills when no family is explicitly allowed. |
| `allowedReligionFamilies` | Exact configured Religion-family names. Every selected Religion Skill requires explicit allowance. |
| `allowedRaces` | Exact configured primary-race strings. Empty means **any current race**, not no race. Unknown submitted values are silently dropped, which can broaden restricted Unit to all races. |
| `allowedSubraces` | Exact configured subrace strings. They must belong to selected race(s). A subrace not available for selected generated race falls back to that race's complete subrace list. |
| `allowHumanoidStatGrowth` | Default `false`. Required before humanoid per-level modifiers, milestones or curves may be saved. Direct curves apply terminal `strong_set` effects and can override normal calculated totals; avoid unless explicitly designed/tested. |

### Race policy checklist

Before save:

1. Copy values from current `configuration.races`; spelling/case matters.
2. If concept demands exact race, send one exact `allowedRaces` value.
3. If concept demands exact subrace, send only values that occur under that
   allowed race.
4. Read returned saved Unit and assert serialized `generation.allowedRaces`
   and `allowedSubraces` exactly match intent.
5. Preview named variant and inspect `trace.race.primary/subrace`.

Never use empty race list for a race-specific bloodlord, Dremora, Xivilai,
Vampire, etc.

---

## 6. Humanoid-only authoring contract

Humanoid must contain all of following:

1. valid `generation.coreKey`;
2. nonempty identity (`archetypeTags` and/or `skillUnlocks`);
3. **at least one viable explicit non-Perk `core` Skill**;
4. **at least one viable explicit non-Perk `archetype` Skill**;
5. at least one fixed equipment entry/group or active accessory profile;
6. a viable minor and major Perk path through all requested levels;
7. no `innateActions`.

Save service checks only a weaker subset. Requirements 3, 4 and 6 are
generation requirements, proven only by previews.

### 6.1 Archetype tags

```json
{
  "archetypeTags": {
    "core_fisico": 3,
    "attacco": 4,
    "natura_magica": -5
  }
}
```

- Keys must come from `configuration.tags`.
- Values are numeric `-5..5`.
- Positive: affinity; zero: neutral; negative: selection pressure/exclusion.
- Tags score and weight candidates. **They do not discover or create Skill
  pools.** Explicit `skillUnlocks` remain source of ordinary Skills.

Use tags to express identity and improve Perk weighting. Do not use broad
physical tags to smuggle melee attacks into ranged or magical specialist Core.

### 6.2 Skill pools

```json
{
  "skillUnlocks": [
    {
      "skillId": 123,
      "pool": "core",
      "weight": 8,
      "minLevel": 1,
      "maxLevel": 10,
      "requiredAtLevel": 3
    },
    {
      "skillId": 456,
      "pool": "archetype",
      "weight": 6,
      "minLevel": 2,
      "maxLevel": 20
    },
    {
      "skillId": 789,
      "pool": "minor",
      "weight": 4,
      "minLevel": 1,
      "maxLevel": 20
    }
  ]
}
```

| Key | Rule |
|---|---|
| `skillId` | Active catalog Skill ID; unique across whole Unit. |
| `pool` | `core`, `archetype`, `minor`, `major`. Perk pools require a Perk-family Skill; ordinary pools reject Perk Skills. Persisted Perk entries become archetype entries with `perkTier`. |
| `weight` | Number `0.1..100`; higher means more likely among eligible choices. |
| `minLevel`, `maxLevel` | Inclusive integers `1..20`; `maxLevel >= minLevel`. |
| `requiredAtLevel` | Optional, inside that entry's level band. It is **priority after eligibility**, not a guaranteed unlock. |

#### Core and archetype rules

- Core: general/passive growth, health, energy, defense, mobility, utility.
- Archetype: defining attacks, stances, spell school, healing, control,
  assassination, weapon specialization or other role-specific power.
- Offer at least three viable choices in each bands `1–5`, `6–10`, `11–15`,
  `16–20`, including expanded prerequisites. Overlap bands to produce variety.
- Put an identity-critical early ability in pool with sensible weight and
  enough XP/prerequisite preparation; never assume `requiredAtLevel` forces it.
- Read every transitive prerequisite. Generator automatically adds ordinary
  prerequisite candidates, but they still consume XP and must remain coherent.
- Generator checks calculated dynamic price, prerequisite ownership and
  structured requirements before purchase. Base `costo_pe` alone is not enough.
- At most two purchases from each pool occur at each level before final passes;
  PE can remain when no configured candidate is affordable/eligible.

#### Class, Religion and magic rules

- Add Class Skill only when its exact family is in `allowedClassFamilies`.
- Add Religion Skill only when exact family is in `allowedReligionFamilies`.
- `magicPolicy: "none"` must exclude every magic Skill even if its name seems
  physical. Inspect tags, group and spell relation.
- Current backend does not enforce “maximum two Classes/one Religion.” Treat
  that as human content policy if desired, not server protection.

### 6.3 Perk viability

Each humanoid level independently chooses 50/50 between:

1. canonical Elder milestone selected by current Skill **name**; or
2. compatible weighted Perk choice.

Every level needs one minor Perk; every even level also needs one major Perk.
Both choices at even level use same milestone-vs-weighted branch.

If no explicit `minor`/`major` entries exist, generator searches active Perk
catalog and weights it by Core/archetype tags. If explicit entries exist for a
tier, they replace that tier's global candidates.

Before delivery preview at levels 1 through 20 using named variants. A failure
`combat.unit_perk_pool_incomplete` means this Unit cannot generate reliably.
Check current canonical milestone names, unavailable/archived Perks, Perk
prerequisites and structured requirements. Characteristic Perks can repeat as
character-owned +1 effects; legacy IDs are never stored.

### 6.4 Competence profile

```json
{
  "competenceProfile": {
    "percezione": 4,
    "furtivita": 3,
    "sopravvivenza": 2,
    "sapienza_magica": -5
  }
}
```

- Keys come only from `configuration.competences`.
- Values are numeric `-5..5`.
- Values become weighted preference, not fixed bars. Generator spends
  Competence XP on canonical bars with triangular cost.
- Do not submit fixed `{barra1, barra2, extra}` state for new Unit content;
  it remains legacy compatibility behavior.
- Use at least three positive priorities, several neutral omissions and real
  incompatibilities as negatives.

---

## 7. Humanoid equipment and jewelry

Humanoid needs at least one source: explicit slot pool, explicit group, or
active shared `accessoryProfileKey`. Use both fixed pools and profile when
needed; fixed equipment is equipped first, shared profile then fills valid
remaining ordinary accessory slots.

### 7.1 Fixed slot pools

```json
{
  "equipmentSlots": [
    {
      "slot": "arma",
      "itemId": 10,
      "minLevel": 1,
      "maxLevel": 8,
      "weight": 4,
      "chance": 1
    },
    {
      "slot": "arma",
      "itemId": 11,
      "minLevel": 5,
      "maxLevel": 13,
      "weight": 2,
      "chance": 0.9
    }
  ]
}
```

| Key | Rule |
|---|---|
| `slot` | Exact `configuration.equipmentSlots` value. |
| `itemId` | Active non-archived, non-`archiviato` Item ID compatible with that slot. |
| `minLevel`, `maxLevel` | Inclusive `1..20`; valid range. |
| `weight` | Number `0.1..100`. |
| `chance` | Number `0..1`; per-entry optionality. |

Rules:

- Same Item may appear only once in same fixed slot. Global duplicate selection
  is disabled; using same Item in multiple pools can leave later slot empty.
- Explicit slot pool has no global catalog fallback. No eligible successful
  entry means slot remains empty.
- `armatura`, `chainmail`, `veste` all together are rejected. Current service
  permits any pair, but do not rely on unintended layer combinations; preview
  totals and document intentional combination.
- `scudo` accepts shield or compatible one-handed weapon. Generator does not
  run full hand configuration validation. Never pair two-handed `arma` with
  occupied `scudo`; never put non-one-handed weapon in offhand.
- Generator also does not enforce active ring/earring/sack limits for explicit
  pools. Do not author locked-slot dependence; preview at high level.

### 7.2 Fixed accessory groups

Use groups only for exceptional identity-defining concrete accessories. Keep
each group physically homogeneous: every listed Item must fit **every** listed
slot. Service checks only compatibility with at least one slot; generator can
otherwise place a ring-like Item into incompatible group position.

```json
{
  "equipmentGroups": [
    {
      "name": "Anelli del predone",
      "slots": ["anello_1", "anello_2", "anello_3"],
      "minCount": 1,
      "maxCount": 3,
      "emptyChance": 0,
      "items": [
        {"itemId": 40, "minLevel": 1, "maxLevel": 7, "weight": 3, "chance": 1},
        {"itemId": 41, "minLevel": 5, "maxLevel": 12, "weight": 2, "chance": 1}
      ]
    }
  ]
}
```

- Group slots: unique valid slot names.
- `minCount`, `maxCount`: integers `0..number of slots`, max >= min.
- `emptyChance`: `0..1`.
- Group needs one or more valid Item entries.
- Without global accessory bands, generator chooses random count in group range;
  then `emptyChance` can zero it.
- With `accessoryCountByLevel`, generator equips every group minimum first and
  **ignores `emptyChance`**, then fills toward total. Do not mark a required
  group optional and expect it to remain optional under global bands.

### 7.3 Accessory count bands

Use only for exceptional explicit groups that need an exact total curve. Most
ordinary Unit jewelry should use shared profile instead. Bands constrain only
the explicit-group allocation. If a shared `accessoryProfileKey` is also
present, profile generation runs afterwards and can add accessories beyond the
band total. Do not combine them when exact overall accessory count is required;
otherwise verify final count in preview.

When present, bands must cover all levels exactly once, never overlap. Each
band total must be feasible:

```text
sum(group.minCount) <= band.minCount <= band.maxCount <= sum(group.maxCount)
```

Valid complete example:

```json
{
  "accessoryCountByLevel": [
    {"minLevel": 1, "maxLevel": 3, "minCount": 2, "maxCount": 3},
    {"minLevel": 4, "maxLevel": 7, "minCount": 3, "maxCount": 5},
    {"minLevel": 8, "maxLevel": 12, "minCount": 5, "maxCount": 7},
    {"minLevel": 13, "maxLevel": 16, "minCount": 7, "maxCount": 9},
    {"minLevel": 17, "maxLevel": 20, "minCount": 8, "maxCount": 10}
  ]
}
```

Adjust numbers to actual group capacity. Never copy this example blindly.

### 7.4 Shared accessory profile

```json
{"accessoryProfileKey": "exact-key-from-configuration"}
```

Always choose explicit key. If blank, service silently recommends profile from
Core, tags and Unit name; this is unsuitable for controlled authoring.

Profile behavior differs from fixed pool:

- dynamically queries live Item catalog by physical accessory type, `tipo_2`
  effect kind and tier parsed from `tipo_4`;
- applies profile core kinds with heavier weighting, one variant pool,
  duplicate exceptions, level count curve and tier jitter;
- can select different catalog Item after catalog changes;
- missing exact tier searches upward before downward;
- if requested effect kind lacks a match, can fall back to another compatible
  kind/item and records fallback in generation trace;
- respects existing equipment placements when filling remaining slots.

Thus named variant reproducibility assumes unchanged profile and catalog.
Inspect trace for profile, selected kind, requested/resolved tier and fallback.

### 7.5 Material/tier policy: author-enforced, not server-enforced

For every weapon and armour concept, decide:

- light or heavy path;
- allowed crossover period;
- narrative tier ceiling;
- exact Item IDs available at every level;
- whether Item special rules are manual or structured.

Canonical material paths:

| Tier | Light weapon/armour | Heavy weapon/armour |
|---:|---|---|
| 1 | wood / leather | iron |
| 2 | chitin | steel |
| 3 | elven | nordic |
| 4 | bone | orcish |
| 5 | dreugh | dwemer |
| 6 | glass | ebony |
| 7 | adamantium | daedric |

`lv_loot`/Item tier does not equal character level. Backend does not store or
validate Unit material path or tier cap. Build level × slot × eligible Item
matrix manually and test boundary levels. Never claim restriction exists merely
because guide names it.

### 7.6 Item special rules

An Item can contain structured effects plus descriptive `regole_speciali`.
Special text is not necessarily automatic. A healer robe that says “free
Restoration power” may not grant that through structured Item effects. Put
manual handling in Unit notes/description and do not promise engine execution
until relevant combat system implements it.

---

## 8. Creature-only authoring contract

Creature must have:

- `generation.kind: "creature"`;
- no `skillUnlocks`;
- no `equipmentSlots`, `equipmentGroups`, `accessoryCountByLevel` or
  `accessoryProfileKey`;
- empty `competenceProfile`;
- no race/Class/Religion/XP assumptions;
- optional `statProfile` and `innateActions`.

Save permits empty creature, but content quality does not. New creature should
define enough curves and/or actions to express its chassis and role.

### 8.1 Stat curves

```json
{
  "statProfile": {
    "baseModifiers": {},
    "perLevelModifiers": {},
    "milestones": [],
    "curves": [
      {"key": "pf", "profile": "high", "level1": 25, "level20": 150},
      {"key": "pa", "profile": "medium", "level1": 7, "level20": 25},
      {"key": "res_fuoco", "profile": "custom", "level1": 5, "level20": 5}
    ]
  }
}
```

- `key` must come from `configuration.statCurveVariables`; each key once.
- `profile` must be one configured profile label. It is preset/documentation
  label only after endpoints are supplied.
- `level1`, `level20`: numbers `-100000..100000`.
- Curve endpoints are exact; each curve becomes a `strong_set` chassis effect.
- Intermediate value is always rounded linear interpolation:

```text
round(level1 + (level20 - level1) * (level - 1) / 19)
```

Do not submit `curve: "exponential"`, `quadratic`, `logarithmic` or `hi_hi`.
Current save service drops it and generator ignores it. Omitted curve key does
not become zero; generated character keeps ordinary calculated baseline for it.

Supported curve keys currently include:

```text
pf, mana, energia, potere, pa, attacco, difesa, tier,
fortuna, forza, resistenza, velocita, agilita, intelligenza,
concentrazione, personalita, saggezza,
res_contundente, res_taglio, res_perforante, res_fuoco, res_gelo, res_elettro,
rd_fis, rd_fuoco, rd_gelo, rd_elettro, ap
```

Use endpoint lookup as final authority.

### 8.2 Advanced creature chassis modifiers

Only use after source/reference inspection:

| Field | Runtime effect |
|---|---|
| `baseModifiers` | Additive chassis modifiers at all levels. |
| `perLevelModifiers` | Additive modifier × `(level - 1)`. |
| `milestones` | Additive modifiers once milestone level reached. |
| `levels` | Legacy inclusive bands with additive `modifiers`/`stats`. |

These modifier target keys are less strictly validated than curve keys. Copy
only verified current effect targets. Curves and direct modifiers can combine;
curves use `strong_set`, so they may override additive totals for same target.

### 8.3 Innate actions

```json
{
  "innateActions": [
    {
      "key": "wild-stingbee-sting",
      "name": "Pungiglione selvatico",
      "description": "Rule text: target, range, hit, poison, damage, duration and resolution owner.",
      "minLevel": 1,
      "maxLevel": 20,
      "costs": {"energia": 2, "pa": 3},
      "trigger": "Azione",
      "duration": "Istantanea",
      "icon": "pungiglione"
    }
  ]
}
```

| Key | Rule |
|---|---|
| `key` | Optional stable string, max 120. Supply unique semantic key; service does not reject duplicates. |
| `name` | Required, max 180. |
| `description` | Rule text, unrestricted by Unit validator. Include targeting, range, roll, damage, condition, duration, limits and who resolves it. |
| `minLevel`, `maxLevel` | Inclusive integers `1..20`. |
| `costs` | Nonnegative integers. Only `pf`, `mana`, `energia`, `potere`, `pa`, `stanchezza` persist; unsupported keys are dropped. |
| `trigger`, `duration`, `icon` | Stored display metadata. Icon max 80. |

Critical limitation: generator copies eligible action data to
`Personaggio.abilita.known`. It does not execute costs, attacks, dice, poison,
range, movement, flight, targeting, duration, saves, conditions, summons,
healing, knockback or buffs. Author a complete rule reminder, then separately
implement combat system support if automatic resolution is required.

No natural attack is implied. Creature with no `innateActions` has none.

---

## 9. Portrait contract

Portrait is optional. Never invent image ID.

If supplying `loreImageId`, selected active `UploadedImage` must be:

```text
usage_type: character_portrait
category slug: personaggi
group: Unit e NPC
file: .webp
WebP quality metadata: 70
```

Generated character copies current Unit portrait. Later Unit portrait changes
affect future generation only, not existing generated characters. Image-less
Unit is valid.

---

## 10. One-shot build procedure

Use this exact sequence. Do not skip discovery because prompt sounds detailed.

### Phase A — turn request into a charter

Write compact internal charter before queries:

```text
Name/category:
Contract: humanoid or creature; mechanical reason:
Combat role/distance/defense/magic:
Level 1 identity:
Level 20 identity:
Required active mechanics versus reminder-only prose:
Race/subrace restrictions:
Skills/competences or curves/actions:
Equipment/jewelry/material/tier policy:
Variation allowed versus fixed identity:
Portrait need:
```

If charter demands an unimplemented automatic mechanic, label it manual or
stop and request combat feature work. Do not fake support with action prose.

### Phase B — gather dependencies

1. Fetch Unit configuration.
2. Fetch/read five closest comparable Units.
3. Query broad candidate Skills/Items, then inspect each chosen dependency.
4. Build tables:

```text
Humanoid Skill table:
id | name | pool | band | weight | price behavior | prereq chain | policy check | role reason

Humanoid equipment table:
slot/group | item ID | item name/types | Lmin-Lmax | weight/chance | material/tier | effects | manual rules

Creature curve table:
key | L1 | L20 | reason | overlaps/strong_set risk

Creature action table:
key | Lmin-Lmax | costs | complete rule text | automatic or reminder-only
```

5. Check every requested concept word against current systems. “Blood drain,”
   “cannibalism,” “venom,” “swarm,” “flight,” “resurrection” are not automatic
   just because a description exists.

### Phase C — construct full DTO

- Use all required fields from section 4.
- Include explicit empty arrays/objects for mutually forbidden systems. This
  makes contract unambiguous to human reviewer.
- Use only discovered exact values/IDs.
- Make humanoid fixed equipment bands cover intended level experience. Empty
  allowed slot at a level is allowed only when intentional and documented.
- Make creature curves/action bands cover intended role. Omitted is intentional
  only when baseline value is correct.
- Put authoring evidence and manual-mechanics warning in `notes`.

### Phase D — save once

Call `management.units.save`. On error:

1. Read exact error field/code.
2. Re-query dependency if stale/uncertain.
3. Correct full DTO in memory.
4. Re-submit complete DTO.

Never bypass failure with direct database edits, invented fallback IDs or
arbitrary modifier keys.

### Phase E — verify returned serialization

Compare returned `data.management.unit` to intended DTO:

- kind and Core unchanged;
- race/subrace lists exactly intended;
- every Skill/Item ID/name resolved;
- valid accessory profile retained;
- no action is present on humanoid;
- no Skills/equipment/competences/profile remain on creature;
- portrait and authoring metadata are correct;
- defaults did not silently change strategy.

### Phase F — preview matrix

At minimum preview named variant at levels:

```text
1, 3, 5, 6, 7, 9, 10, 11, 12, 15, 20
```

Use the broader boundary matrix whenever material/accessory bands change.
Then:

1. preview at least eight `auto` variants at key level(s), normally 1, 10, 20;
2. preview same named variant twice; compare Skills, perks, Competences,
   equipment, totals, trace and warnings;
3. for humanoid inspect PE earned/spent/remaining, every prerequisite,
   core/archetype identity, expected minor/major Perk counts, race/subrace,
   Item slots and accessory fallbacks;
4. for creature inspect exact endpoints, rounded linear intermediate values,
   action unlock bands and no humanoid systems;
5. inspect every `trace.warnings`; residual XP/fallback is a content signal,
   not a harmless success.

### Release gate

Unit is ready only when:

- all selected levels generate successfully;
- named variant is stable under unchanged catalog;
- automatic variants differ without losing identity;
- no out-of-pool fixed Item appears;
- no forbidden cross-contract data appears;
- every manual mechanic is explicitly labelled;
- reviewers can reproduce choices from `notes` and trace.

Correct blueprint, not generated preview character.

---

## 11. Complete one-shot payload templates

Templates are structural. Replace every placeholder only after live discovery.

### 11.1 Humanoid: Cannibal Bloodlord pattern

Do not use this as literal data; current catalog may lack blood/cannibal
mechanics. First decide whether those mechanics are Skills, Items, manual
rules, or unsupported.

```json
{
  "name": "Cannibal Bloodlord",
  "category": "Non Morti",
  "loreImageId": null,
  "archetypeDescription": "[Combat role, distance, defense, magic policy and progression rationale.]",
  "loreDescription": "[Narrative only.]",
  "notes": "Authored from live catalog on [date]. [List selected Skill/Item IDs]. Blood drain/cannibalism: [implemented Skill ID or explicitly manual rule].",
  "generation": {
    "kind": "humanoid",
    "coreKey": "[one configured core]",
    "coreShare": 0.5,
    "startingXp": 0,
    "xpBase": 20,
    "xpGrowth": 1,
    "competenceStartingXp": 5,
    "competenceXpBase": 15,
    "competenceXpGrowth": 0,
    "finalSpendingPasses": 4,
    "magicPolicy": "[any or none]",
    "allowedClassFamilies": ["[exact live family only if used]"],
    "allowedReligionFamilies": [],
    "allowedRaces": ["[exact intended live race]"],
    "allowedSubraces": ["[exact subrace belonging to race]"],
    "allowHumanoidStatGrowth": false
  },
  "archetypeTags": {
    "core_fisico": 0,
    "core_magico": 0,
    "attacco": 0,
    "difesa": 0
  },
  "competenceProfile": {
    "[live-competence-key]": 3
  },
  "skillUnlocks": [
    {"skillId": 0, "pool": "core", "weight": 1, "minLevel": 1, "maxLevel": 20},
    {"skillId": 0, "pool": "archetype", "weight": 1, "minLevel": 1, "maxLevel": 20}
  ],
  "equipmentSlots": [
    {"slot": "arma", "itemId": 0, "minLevel": 1, "maxLevel": 20, "weight": 1, "chance": 1}
  ],
  "equipmentGroups": [],
  "accessoryCountByLevel": [],
  "accessoryProfileKey": "[exact live key]",
  "innateActions": [],
  "statProfile": {"baseModifiers": {}, "perLevelModifiers": {}, "milestones": [], "curves": []},
  "levels": []
}
```

Before actual submission, replace all zero/placeholders and add wide enough
explicit pools. Placeholder payload must never reach API.

### 11.2 Creature: Wild Stingbee pattern

```json
{
  "name": "Wild Stingbee",
  "category": "Natura",
  "loreImageId": null,
  "archetypeDescription": "Fast flying venom creature; creature contract because it uses fixed chassis and authored actions, not Skills or equipment.",
  "loreDescription": "[Narrative ecology and behavior.]",
  "notes": "Flight and venom are authored action reminders. They require GM/manual resolution until combat executor exists.",
  "generation": {
    "kind": "creature",
    "coreKey": "",
    "coreShare": 0.5,
    "startingXp": 0,
    "xpBase": 20,
    "xpGrowth": 1,
    "competenceStartingXp": 5,
    "competenceXpBase": 15,
    "competenceXpGrowth": 0,
    "finalSpendingPasses": 4,
    "magicPolicy": "any",
    "allowedClassFamilies": [],
    "allowedReligionFamilies": [],
    "allowedRaces": [],
    "allowedSubraces": [],
    "allowHumanoidStatGrowth": false
  },
  "archetypeTags": {},
  "competenceProfile": {},
  "skillUnlocks": [],
  "equipmentSlots": [],
  "equipmentGroups": [],
  "accessoryCountByLevel": [],
  "accessoryProfileKey": "",
  "statProfile": {
    "baseModifiers": {},
    "perLevelModifiers": {},
    "milestones": [],
    "curves": [
      {"key": "pf", "profile": "low", "level1": 14, "level20": 75},
      {"key": "pa", "profile": "high", "level1": 9, "level20": 32},
      {"key": "velocita", "profile": "high", "level1": 11, "level20": 30},
      {"key": "agilita", "profile": "high", "level1": 11, "level20": 30}
    ]
  },
  "innateActions": [
    {
      "key": "wild-stingbee-sting",
      "name": "Pungiglione selvatico",
      "description": "[Complete manual combat rule for hit, damage, venom, target, range, duration and saves.]",
      "minLevel": 1,
      "maxLevel": 20,
      "costs": {"energia": 2, "pa": 3},
      "trigger": "Azione",
      "duration": "Istantanea",
      "icon": "pungiglione"
    },
    {
      "key": "wild-stingbee-flight",
      "name": "Volo erratico",
      "description": "[Complete manual movement/terrain rule.]",
      "minLevel": 1,
      "maxLevel": 20,
      "costs": {},
      "trigger": "Passiva",
      "duration": "Sempre attiva",
      "icon": "ali"
    }
  ],
  "levels": []
}
```

Curve endpoint values are examples only. Select final values from live presets,
comparable creature evidence and campaign balance requirements.

---

## 12. Author self-audit before human approval

Answer every question with evidence. Any “unknown” blocks submission.

### Universal

- [ ] Contract selected by actual mechanics, not category/lore.
- [ ] Every dropdown-like value came from current configuration.
- [ ] Every ID exists, is active and was semantically inspected.
- [ ] No metadata/provenance/seed is submitted through management API.
- [ ] Portrait either omitted or satisfies Unit portrait contract.
- [ ] Notes state source, dependencies, manual mechanics and test variants.
- [ ] Complete DTO uses live camelCase API field names.

### Humanoid

- [ ] Exact Core configured.
- [ ] Explicit viable ordinary Core and archetype pools both exist.
- [ ] Every Skill prereq chain is coherent and affordable under dynamic prices.
- [ ] Class/Religion/Magic policies permit every selected Skill.
- [ ] Minor/major Perk catalog is viable through level 20.
- [ ] Race/subrace saved values exactly preserve restriction.
- [ ] Competence keys are canonical; weights represent role.
- [ ] Fixed equipment is compatible, non-archived and level-banded.
- [ ] Hand configuration is legal; no hidden locked-slot dependence.
- [ ] Group Items fit every group slot.
- [ ] Accessory profile intentionally selected; live fallback accepted/documented.
- [ ] Material/tier matrix manually checked at each boundary level.
- [ ] Special Item rules labelled automatic or manual correctly.
- [ ] `innateActions` empty.

### Creature

- [ ] All humanoid-only arrays/profile are empty.
- [ ] Curves use supported keys once each; endpoint/linear behavior understood.
- [ ] Omitted stats intentionally retain baseline.
- [ ] Advanced modifiers use verified effect targets only.
- [ ] Every action has unique key, name, bands and allowed resource costs.
- [ ] Action description contains complete human-resolvable rule.
- [ ] Each claimed automatic mechanic exists outside Unit data, or is marked manual.

### Verification

- [ ] Save response matches intended Unit exactly.
- [ ] Named previews pass boundary levels and repeat identically.
- [ ] Eight automatic variants preserve role identity.
- [ ] Trace reviewed: XP, Skills, Perks, Competences, race, curves, Items,
  accessories, fallbacks and warnings.
- [ ] Blueprint corrected after any failure; preview character never edited.

---

## 13. Source-of-truth index

Use this index when this guide needs revalidation after a feature change:

```text
backend/combat/unit_management_services.py
  _clean_unit_values, _clean_skill_unlocks, _clean_equipment,
  _clean_actions, _clean_stat_curves, save_managed_unit, preview_managed_unit

backend/combat/unit_management_selectors.py
  unit_management_overview, unit_option_search, serialize_managed_unit

backend/combat/unit_generation.py
  UNIT_KINDS, DEFAULT_CORE_PROFILES, _skill_pools, _stat_curve_values,
  _stat_modifiers, _equip_humanoid, create_unit_character

backend/combat/accessory_profiles.py
  shared profile discovery, tier/fallback/duplicate behavior

backend/characters/race_rules.py
  RACE_NAMES, subraces_for, automatic race/subrace effects

backend/characters/services/inventory_rules.py
  equipment slots, Item compatibility, hand and active-slot rules

backend/api_v1/api.py
  management.units.save and management.units.preview dispatch
```

When code changes any listed contract, update this guide and add/adjust Unit
preview tests in same change.

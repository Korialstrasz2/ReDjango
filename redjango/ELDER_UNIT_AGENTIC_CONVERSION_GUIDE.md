# Elder Django → ReDjango: agentic Unit conversion guide

**1. Conversion contract and quality bar.** Treat every legacy row as evidence, never as an import-ready blueprint: group rows that share a normalized name into one ReDjango `Unit`, preserve every Elder source ID in `metadata.sourceIds`, and classify the result by behavior (`humanoid`, `animal`, or `creature`) rather than by the unreliable legacy `razza` string. The conversion agent must first write an identity brief covering fantasy, combat role, range, defenses, mobility, magic, signature actions, expected equipment rigidity, intended level range, and explicit exclusions; every later field must cite that brief or a source record. A unit passes only when it is recognizably itself at levels 1, 5, 10, 15, and 20, remains recognizably itself across at least eight automatic variants per checkpoint, differs meaningfully from neighboring units, and can be reproduced with a named variant. Legacy IDs, original JSON, lore, selected source skills, mapping decisions, rejected candidates, catalog query receipts, warnings, preview signatures, and reviewer approval belong in a per-unit conversion dossier so that no LLM decision becomes invisible.

### Example: minimum conversion dossier

This file is the durable working memory for one conversion. `proposal` uses the
Unit-management API field names; `sourceSnapshot` remains immutable after
`discover`.

```json
{
  "schemaVersion": 1,
  "conversionKey": "elder-unit:django_slim_unit:931",
  "status": "needs-review",
  "sourceSnapshot": {
    "project": "the_elder_django",
    "table": "django_slim_unit",
    "ids": [931],
    "normalizedName": "ordinatore",
    "sha256": "sha256:<source-snapshot-hash>"
  },
  "identityBrief": {
    "fantasy": "Soldato sacro del Tribunale",
    "role": "tank da prima linea",
    "range": "mischia",
    "defence": "armatura pesante e scudo",
    "magic": "secondaria, solo se sostenuta dalle Skill curate",
    "rigidity": "iconic-locked",
    "must": ["Armatura Indoril a ogni livello", "disciplina militare"],
    "mustNot": ["armature generiche", "armi a distanza casuali"]
  },
  "evidence": [
    {"claim": "Armatura Indoril", "source": "unit:931.armatura[0]"},
    {"claim": "Mazza Indoril", "source": "unit:931.arma[0]"},
    {"claim": "soldato della fede", "source": "unitlore:90"}
  ],
  "catalogReceipts": [],
  "proposal": {},
  "rejectedCandidates": [],
  "findings": [],
  "simulation": {},
  "approval": null
}
```

### ReDjango preflight blocker

`save_managed_unit` already preserves innate-action costs, maximum level,
trigger, duration, and icon, but it does not accept Unit `metadata`. Before
importing the full catalog, add a provenance input owned by the importer or
store an equally durable one-to-one import ledger. Notes alone are not an
idempotency or provenance key. Until that gap is fixed, dossiers may be
researched and simulated, but the workflow must block `apply`.

**2. Evidence and query packet.** For one normalized legacy name, the researcher agent must read all matching `django_slim_unit` rows, their seven `SkillNpc` relations, `profili_attributi_formule`, `UnitLore`, all named equipment fields, and the source implementation that interpreted those fields; it must then query the live ReDjango Skill, item, variable, competence, race, and slot catalogs by stable structured fields as well as normalized names. The repeatable query recipe is: `SELECT * FROM django_slim_unit WHERE lower(trim(nome))=:name ORDER BY id`; join each non-null `skill_1_id…skill_7_id` to `django_slim_skillnpc`; fetch lore with `WHERE nome=:name OR unit_id IN (:source_ids)`; search current items with `archiviato=0 AND archived_at IS NULL` plus `nome`, `tipo_1` (slot/weapon class), `tipo_2` (material), `tipo_3` (damage), `lv_loot`, `effects`, and `metadata`; search current Skills through `core_skill`→`core_famigliaskill` and `core_skill_prerequisiti`, returning description, active/passive payloads, costs, profile tags, archive state, and provenance; resolve an Elder Skill by `metadata.sourceProject='the_elder_django'` and `metadata.sourceId`, not by whichever current numeric ID happens to resemble it. The packet also includes the closest siblings with the same faction/creature family, role, material culture, and level band plus one deliberate contrast, and stores the exact parameters/result IDs as query receipts. Name similarity is only a lead: ambiguous matches, missing catalog objects, contradictory rows, and unsupported lore become blockers rather than invented IDs or silent fallbacks.

### Example: reproducible source and catalog queries

Legacy Unit rows and their innate SkillNpc records:

```sql
SELECT *
FROM django_slim_unit
WHERE lower(trim(nome)) = lower(trim(:unit_name))
ORDER BY id;

SELECT s.*
FROM django_slim_unit u
JOIN django_slim_skillnpc s
  ON s.id IN (
    u.skill_1_id, u.skill_2_id, u.skill_3_id, u.skill_4_id,
    u.skill_5_id, u.skill_6_id, u.skill_7_id
  )
WHERE u.id IN (:source_ids)
ORDER BY s.id;
```

Current item candidates for an Ordinator. The first query finds identity gear;
the second deliberately tests whether generic armor is trying to enter the
pool.

```sql
SELECT id, nome, tipo_1, tipo_2, tipo_3, lv_loot, effects
FROM core_oggetto
WHERE archived_at IS NULL
  AND archiviato = 0
  AND (
    lower(nome) LIKE '%indoril%'
    OR (tipo_1 = 'armatura' AND tipo_2 = 'ebano')
  )
ORDER BY tipo_1, nome;
```

Current Skill candidates and prerequisite closure:

```sql
SELECT s.id, s.nome, f.nome AS famiglia, g.nome AS gruppo,
       s.costo_pe, s.descrizione, s.azioni_attive,
       s.effetti_passivi, s.profile_tags
FROM core_skill s
JOIN core_famigliaskill f ON f.id = s.famiglia_id
JOIN core_gruppofamiglieskill g ON g.id = f.gruppo_id
WHERE s.archived_at IS NULL
  AND (
    lower(s.nome) LIKE :token
    OR lower(f.nome) LIKE :token
    OR lower(s.descrizione) LIKE :token
  )
ORDER BY f.ordine, s.ordine_famiglia;

SELECT p.from_skill_id AS skill_id, p.to_skill_id AS prerequisite_id
FROM core_skill_prerequisiti p
WHERE p.from_skill_id IN (:candidate_skill_ids);
```

A query receipt records database fingerprint, SQL identifier, parameters,
result IDs, timestamp, and result hash. An agent may rerun the query; it may
not replace the receipt with an unsupported prose assertion.

**3. Humanoid authoring policy.** The humanoid specialist must choose a Core, competence priorities from −5 to +5, two curated Skill pools (`core` for broadly reusable durability/mobility/resource tools and `archetype` for role-defining attacks, stances, magic, and tactics), real prerequisites, level windows, weights, and sparing `requiredAtLevel` anchors; it must explicitly reject weapon techniques incompatible with the authored loadout. Equipment is a constraint system, not a loot search: each slot uses explicit current item IDs with overlapping level windows, weights, and chances; weapon pools may widen by relevant weapon family and material tier, while armor obeys a documented rigidity class—`open` for bandits/mercenaries, `path-locked` for a chosen light/heavy material progression, `faction-locked` for Indoril/Redoran/legion uniforms at every level, and `iconic-locked` for Daedric or otherwise inseparable gear. Locked identity does not mean identical clones: variation should move to weapons, shields, accessories, enchantment effects, and optional utility items, never to the defining armor. A level×slot coverage query must prove that every supported level has at least one legal choice, no forbidden family appears, weapon competencies match every possible weapon, armor competencies match every possible armor, accessories respect slot capacity, and all choices remain below the unit’s narrative tier ceiling.

### Example: what the four rigidity policies mean

| Policy | Defining armor | Weapon behavior | Appropriate example |
|---|---|---|---|
| `open` | Several common families may overlap | Several compatible weapon types and materials | Mercenario |
| `path-locked` | Follows one authored light/heavy material route | Type stays coherent; material advances | Arciere Bandito |
| `faction-locked` | Faction model never leaves the pool | Several lore-valid faction weapons | Soldato Imperiale, Cavaliere Redoran |
| `iconic-locked` | One inseparable visual identity at all authored levels | Variation moves almost entirely to weapons/accessories | Ordinatore, Soldato Dremora |

If iconic equipment is too strong for level 1, do not replace it with generic
leather. Either start the Unit at a higher supported level or explicitly
balance the surrounding progression. Identity is not a loot tier.

### Worked humanoid payload: core, archetype, and overlapping choices

This is a shortened Unit-management payload using IDs verified in the current
database. The two bow Skills define the role; the general survivability Skills
belong to Core. The armor and bow windows deliberately overlap so copies differ
without ever ceasing to be archers.

```json
{
  "name": "Arciere Bandito",
  "category": "Banditi",
  "archetypeDescription": "Predone a distanza che apre dall'imboscata e usa il terreno.",
  "generation": {
    "kind": "humanoid",
    "coreKey": "warrior",
    "coreShare": 0.5,
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
    "percezione": 3,
    "rapidita_di_mano": 2,
    "strategia_militare": 2,
    "furtivita": 1,
    "sopravvivenza": 1,
    "sapienza_magica": -5
  },
  "skillUnlocks": [
    {"skillId": 71, "pool": "core", "weight": 9, "minLevel": 1, "maxLevel": 20},
    {"skillId": 64, "pool": "core", "weight": 8, "minLevel": 1, "maxLevel": 20},
    {"skillId": 335, "pool": "archetype", "weight": 10, "minLevel": 1, "maxLevel": 20},
    {"skillId": 336, "pool": "archetype", "weight": 10, "minLevel": 1, "maxLevel": 20},
    {"skillId": 601, "pool": "archetype", "weight": 8, "minLevel": 5, "maxLevel": 20}
  ],
  "equipmentSlots": [
    {"slot": "armatura", "itemId": 595, "minLevel": 1, "maxLevel": 3, "weight": 4, "chance": 1},
    {"slot": "armatura", "itemId": 596, "minLevel": 2, "maxLevel": 6, "weight": 5, "chance": 1},
    {"slot": "armatura", "itemId": 597, "minLevel": 4, "maxLevel": 11, "weight": 5, "chance": 1},
    {"slot": "armatura", "itemId": 598, "minLevel": 9, "maxLevel": 20, "weight": 4, "chance": 1},
    {"slot": "arma", "itemId": 510, "minLevel": 1, "maxLevel": 3, "weight": 4, "chance": 1},
    {"slot": "arma", "itemId": 511, "minLevel": 2, "maxLevel": 6, "weight": 5, "chance": 1},
    {"slot": "arma", "itemId": 512, "minLevel": 4, "maxLevel": 11, "weight": 5, "chance": 1},
    {"slot": "arma", "itemId": 513, "minLevel": 9, "maxLevel": 20, "weight": 4, "chance": 1}
  ],
  "equipmentGroups": [],
  "accessoryCountByLevel": [],
  "innateActions": [],
  "statProfile": {"baseModifiers": {}, "perLevelModifiers": {}, "milestones": [], "curves": []}
}
```

The excerpt illustrates shape, not a replacement for the complete approved
Bandit dossier. In particular, a production pool needs enough affordable
alternatives and prerequisite closure across all four level bands.

### Worked identity lock: Ordinator equipment

```json
[
  {"slot": "armatura", "itemId": 5785, "minLevel": 1, "maxLevel": 20, "weight": 1, "chance": 1},
  {"slot": "scudo", "itemId": 621, "minLevel": 1, "maxLevel": 20, "weight": 1, "chance": 1},
  {"slot": "arma", "itemId": 5718, "minLevel": 1, "maxLevel": 20, "weight": 5, "chance": 1},
  {"slot": "arma", "itemId": 228, "minLevel": 1, "maxLevel": 20, "weight": 2, "chance": 1}
]
```

Here every Ordinator wears Indoril armor. Variation comes from the weighted
Indoril maul versus ebony longsword, later Skill choices, accessories, and
variant seed—not from occasionally spawning in generic armor.

### Example: candidate rejection log

```json
{
  "candidate": {"skillId": 348, "name": "Affondo"},
  "decision": "reject",
  "unit": "Arciere Bandito",
  "reasonCode": "weapon-role-mismatch",
  "reason": "Melee attack conflicts with an equipment pool containing only short bows.",
  "evidence": ["equipment-matrix:arma:1-20", "identityBrief.range"]
}
```

The critic should prefer a documented rejection over lowering the candidate’s
weight. Weight controls frequency; it does not make an incoherent outcome
acceptable.

**4. Creature authoring policy.** Animals and creatures receive no humanoid Skill, perk, competence, inventory, or equipment pools; the creature specialist translates Elder formula profiles and `SkillNpc` records into current variable curves and innate `skill_actions`. Elder profile numbers are ordinal evidence, not safe ReDjango endpoints: compare them within the creature family, choose the closest current preset, then record any custom level-1 minimum and level-20 maximum. ReDjango’s actual generator now interpolates every curve linearly and ignores old `quadratic`, `exponential`, and `hi_hi` semantics, so never copy those labels as behavior; a legacy literal curve value such as `"0"`, `"-2"`, or `"5"` becomes a constant with `level1 == level20`, while a former shaped curve keeps its endpoints but becomes linear, with that deliberate change noted. Omit unknown variables and totals already derived by ReDjango. Each action needs a stable key, clear description, level window, parsed costs, and targeting/range/effects retained in the description where the schema has no dedicated field. The family matrix checks ecological and mechanical coherence—wolves share pack mobility but not dragon flight, frost beings share cold resistance but not identical attacks, and constructs share immunities without becoming palette swaps—and requires one or more signature axes (movement, resistance/vulnerability, control, summon, regeneration, phase behavior, or resource profile) plus explicit exclusions.

### Worked creature payload: Lupo

This example shows the ReDjango expectation: explicit endpoints, linear
interpolation, constants expressed by equal endpoints, no equipment or
humanoid pools, and Elder abilities translated into innate actions.

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
    "baseModifiers": {},
    "perLevelModifiers": {},
    "milestones": [],
    "curves": [
      {"key": "pf", "profile": "medium", "level1": 18, "level20": 100},
      {"key": "forza", "profile": "high", "level1": 11, "level20": 30},
      {"key": "velocita", "profile": "high", "level1": 11, "level20": 30},
      {"key": "agilita", "profile": "high", "level1": 11, "level20": 30},
      {"key": "intelligenza", "profile": "low", "level1": 6, "level20": 16},
      {"key": "mana", "profile": "custom", "level1": 0, "level20": 0},
      {"key": "res_taglio", "profile": "custom", "level1": -1, "level20": -1}
    ]
  },
  "innateActions": [
    {
      "key": "balzo-predatorio",
      "name": "Balzo Predatorio",
      "description": "Salta fino a 3 esagoni e attacca con +3 Attacco e un reroll.",
      "minLevel": 1,
      "maxLevel": 20,
      "costs": {"pa": 7, "energia": 2},
      "trigger": "Azione",
      "duration": "Istantanea",
      "icon": "artiglio"
    },
    {
      "key": "furia",
      "name": "Furia",
      "description": "Ottiene +4 Forza e +3 Attacco, ma -2 Difesa.",
      "minLevel": 1,
      "maxLevel": 20,
      "costs": {"pa": 4, "energia": 4},
      "trigger": "Azione",
      "duration": "3 turni",
      "icon": "artiglio"
    }
  ]
}
```

At level 10, `pf` is `round(18 + (100 - 18) × 9 / 19) = 57`. Mana and
`res_taglio` remain exactly 0 and −1 at every level. This arithmetic should be
asserted by tests, not merely eyeballed in preview.

### Example: family-coherence matrix

| Axis | Lupo `#986` | Cliff Racer `#971` | Drago `#1020` |
|---|---|---|---|
| Movement identity | fast ground leap | aerial dive | strategic flight |
| Durability evidence | PF profile 3 | PF profile 4 | PF profile 10 |
| Signature control | self-buff with defence cost | push/stun | breath zones and tail sweep |
| Intelligence evidence | 2 | 2 | 8 |
| Must not inherit | elemental breath | pack fury | low-animal cognition |

The matrix prevents “creature” from becoming one generic stat template with
renamed actions.

**5. Twenty-unit calibration examples grounded in the database.** All ten selected humanoid families have empty legacy `skill_1_id…skill_7_id`, so their equipment is preservation evidence but their new Skill/competence pools must be authored from current catalog semantics and Elder archetype unlock evidence, never fabricated as if they were copied. Their dossiers should begin as follows: Soldato Imperiale `#838–840`, one level-1–20 blueprint with faction-locked current item `#5782 Armatura di servizio Imperiale (acciaio)` and `#5789 Scudo Imperiale`, while sword/maul/axe materials progress iron→steel→Nordic and pools emphasize formation, shield, medium weapons, endurance, and military strategy; Mercenario `#848–851`, open overlapping iron/leather→steel/chitin→Nordic/elven→Orcish/glass armor, shields, and sword/axe/maul choices, but each generated weapon family must have compatible competency and the elite tier needs an authored ceiling; Arciere Bandito `#951–952`, preserve short bow plus knife evidence and light leather/chitin/elven overlap, extend to levels 1–20 only through a documented bandit ceiling, keep ranged/Ranger, ambush, perception, stealth, and survival Skills, and forbid generic melee attacks from the Core pool; Mago da Battaglia `#884–886`, preserve the staff-or-longsword choice and Evocation robe/armor path but test that every build can afford both defensive Core and a coherent spell/weapon branch; Guaritore `#887–890`, Restoration robes and staves from novice to master, support Core, healing/cleanse/protection/resource Skills, and no damage magic added merely to spend PE; Agente Morag Tong `#924–925`, faction-lock current `#5769 Armatura Morag Tong (chitina)`, vary current stilettos `#5711` glass and `#5713` ebony plus verified kriss equivalents, and weight stealth, poison, precision, composure, and short weapons; Ordinatore `#931`, iconic-lock current `#5785 Armatura Indoril (ebano)` at every level it is authored, prefer `#5718 Mazza Indoril (ebano)` with a controlled ebony longsword alternative, preserve shield/heavy defense and Tribunal discipline, and do not “downgrade” identity at low levels; Cavaliere Redoran `#940–941`, faction-lock current `#5773 Armatura rinforzata Redoran (ossa)`, preserve shield/tank identity, and vary the current Redoran longsword line `#5723–#5728` plus lore-valid axes by authored level; Mago Telvanni `#934–935`, Illusion robes/staves with mage/specialist Core, control, summons, mobility, and scholarship, avoiding generic healer or frontline pools; Soldato Dremora `#944`, classify as `humanoid` despite legacy `razza="Entità"`, iconic-lock current `#608 Armatura (daedrico)` and `#622 Scudo (daedrico)` at every supported level, vary only vetted Daedric sword/maul/axe choices, and emphasize disciplined heavy warfare rather than creature actions. The ten non-humanoid dossiers are: Lupo `#986`, Elder profile anchors PF 3, speed/agility 7 and actions `Balzo Predatorio`/`Furia`; Cliff Racer `#971`, PF 4 versus speed 8 and `Colpo d’Ala`/`Tuffo Aereo`/`Stridio Sonico`; Regina Kwama `#982`, PF 8, defense/physical reduction 7, constant speed/agility 1, and brood-control actions `Evoca Minion`/`Nuvola di Spore`/`Sputo Velenoso`; Dreugh `#978`, force/resistance 7, constant physical reduction 3, fire resistance 1, electric vulnerability −1, and its four sourced actions `Pelle di Pietra`/`Rigenerazione`/`Colpo di Coda`/`Sottrai Vita`; Atronach del Gelo `#1007`, force/resistance 8, constant cold resistance 5 and fire vulnerability −2, with `Soffio Gelido`/`Armatura di Ghiaccio`/`Tormenta`; Lich `#1013`, intelligence/mana/power 9, constant cold resistance 5, and `Sottrazione Spirituale`/`Rianima Morti`/`Barriera Mistica`/`Tocco Necrotico`; Spriggan `#1018`, PF/resistance 7, low fire profile 2, and `Radici Intrappolanti`/`Evoca Minion`/`Sottrai Vita`; Drago `#1020`, PF/force/resistance 10 with bounded intelligence 8, flight, three sourced elemental breaths, stone skin and tail sweep—prefer a variant policy over granting every breath to every dragon; Centurione Nanico `#1031`, PF 9, force/resistance/attack 8, slow 4, with the legacy Dwemer warhammer translated into an innate hammer action because creatures cannot equip items, plus authored steam/construct traits only when supported; Anomalia Magica `#1023`, low PF/force 3, mana 8, formerly `hi_hi` elemental profiles converted to documented linear endpoints, and `Distorsione Temporale`/`Bruciatura di Mana`/`Scudo di Mana`. These are proposals, not approved imports: every dossier must replace names with verified current IDs, five checkpoint expectations, and comparisons against at least three siblings.

### Example: turn a source observation into an expectation

Source observation: “Soldato Dremora `#944` has Daedric armor, Daedric shield,
and Daedric sword/maul.”

Bad conversion rule: “Prefer Daedric equipment.” This permits a low-weight
generic result and cannot be tested precisely.

Good expectation:

```json
{
  "unit": "Soldato Dremora",
  "levels": [1, 5, 10, 15, 20],
  "allVariants": {
    "generationKind": "humanoid",
    "armorItemIds": [608],
    "shieldItemIds": [622],
    "weaponMaterial": "daedrico",
    "innateActionCount": 0
  },
  "allowedVariation": ["weapon type", "skills", "competences", "accessories"],
  "forbidden": ["generic armor", "non-daedric weapons", "creature SkillNpc actions"]
}
```

For Centurione Nanico `#1031`, the inverse expectation applies:
`equipmentSlots` must be empty and the legacy hammer must be represented by a
traceable innate action. This pair is a useful classification regression test.

**6. Agentic workflow and gates.** Run a resumable state machine per unit: `discover` groups legacy rows and freezes a source snapshot; `research` builds the evidence/query packet; `design` produces the identity brief and proposed ReDjango JSON; `critic-humanoid` or `critic-creature` attacks incoherent choices; `family-review` compares the proposal with already approved siblings; `resolve` answers every finding or marks the unit blocked; `dry-run` submits through the Unit management service inside rollback-only transactions; `simulate` generates the checkpoint/variant matrix; `score` applies deterministic validators and qualitative rubrics; `human-approve` records an explicit decision; and only then may `apply` upsert idempotently by provenance key. Give agents read-only catalog tools and proposal-file write access, but reserve database mutation for one importer that requires an approved dossier hash. Never let an agent broaden a catalog pool, substitute an item/Skill, change classification, or suppress a warning autonomously; it may formulate a targeted query and revise the proposal, while unresolved ambiguity pauses only that unit so the rest of the queue can continue.

### Example: agent handoff contract

Every stage receives and returns structured data. It does not communicate
approval through prose or overwrite another stage’s evidence.

```json
{
  "stage": "critic-humanoid",
  "inputDossierHash": "sha256:<hash>",
  "checksRequested": [
    "identity",
    "skill-equipment-compatibility",
    "prerequisite-closure",
    "level-slot-coverage",
    "faction-lock"
  ],
  "result": "changes-requested",
  "findings": [
    {
      "severity": "blocker",
      "code": "equipment-gap",
      "path": "proposal.equipmentSlots[arma]",
      "levels": [12, 13],
      "message": "No eligible weapon exists at these levels.",
      "suggestedQuery": "current-items:slot=arma;material=ossa;weapon=arcocorto"
    }
  ],
  "outputDossierHash": "sha256:<new-hash>"
}
```

### Example: stage ownership

| Stage | May change | Must not change |
|---|---|---|
| `discover` | source grouping | source rows |
| `research` | evidence and query receipts | proposal |
| `design` | proposal and decision notes | frozen source snapshot |
| `critic-*` | findings only | proposal |
| `resolve` | proposal in response to findings | findings history |
| `dry-run` / `simulate` | receipts and results | approved expectations |
| `human-approve` | approval decision | evidence or simulation |
| `apply` | target record and import receipt | authored proposal |

This separation keeps an authoring agent from grading its own work and keeps an
importer from quietly “helping” a failed proposal.

**7. Validation, rollout, and guarantee boundary.** Deterministic gates must validate schema, source provenance, unique normalized names, legal kind, supported levels, exact linear endpoints (including constants), known variables/actions/slots/IDs, active Skill status, prerequisite closure and affordability, equipment coverage and exclusivity, weapon/armor-to-competence compatibility, race/faction policy, accessory capacities, seed determinism, absence of humanoid systems on creatures, and absence of innate actions on humanoids; simulation gates compare expected versus generated skills, PE spent/residual, perks, stats, actions, equipment, and warnings across 5×8 previews, while family tests detect accidental clones and power outliers. Use the twenty-unit calibration set to tune thresholds, then release in small faction/family batches with dry-run receipts, database backup, idempotent apply, post-import counts, and rollback by import batch—not by destructive table replacement. No workflow can literally guarantee artistic quality, but this one can guarantee that every unit receives traceable attention and that no unit is published without source evidence, catalog-valid choices, cross-unit coherence checks, deterministic mechanical tests, adversarial review, and a named human approval; failures return to the dossier with actionable findings instead of being “fixed” in generated characters.

### Example: executable acceptance scorecard

Hard gates are pass/fail; qualitative scores cannot compensate for a hard
failure.

| Gate | Requirement |
|---|---|
| Schema | Unit-management service accepts the complete payload |
| Provenance | immutable source hash plus all source IDs |
| Coverage | every required slot has ≥1 eligible item at every supported level |
| Compatibility | every possible weapon/armor has matching authored competencies |
| Skills | current, non-archived, prerequisite-closed, affordable, policy-compatible |
| Creature contract | no equipment/Skill pools; innate actions and linear endpoints only |
| Humanoid contract | equipment exists; no innate actions; direct stat growth off unless justified |
| Determinism | same named variant produces the same signature twice |
| Variety | eight automatic variants differ without breaking identity |
| Family | no unexplained power inversion or accidental clone |

```json
{
  "unit": "Lupo",
  "hardGates": {"passed": 10, "failed": 0},
  "previews": {
    "levels": [1, 5, 10, 15, 20],
    "variantsPerLevel": 8,
    "expected": 40,
    "completed": 40,
    "warnings": 0
  },
  "determinism": {
    "variant": "calibration-lupo",
    "signatureA": "sha256:<signature>",
    "signatureB": "sha256:<signature>",
    "match": true
  },
  "qualitative": {
    "identity": 5,
    "sourceFidelity": 5,
    "familyCoherence": 4,
    "meaningfulVariety": 4
  },
  "decision": "ready-for-human-approval"
}
```

A suggested qualitative threshold is at least 4/5 in every category, but the
reviewer must still explain the score. Rollout should begin only after the
twenty calibration dossiers pass this scorecard and the provenance write-path
gap identified in section 1 is closed.

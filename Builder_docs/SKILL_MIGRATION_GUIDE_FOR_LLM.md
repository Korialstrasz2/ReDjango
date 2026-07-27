# Elder Django to ReDjango Skill Migration Guide for LLM Agents

Date: 2026-07-19

## Approved implementation decisions

The following decisions supersede older cautions or optional mappings later in this document:

- import no characters and no `SkillPersonaggio` ownership records;
- do not create or retain Skill summaries;
- do not create or enforce a minimum-character-level unlock gate;
- keep `Skill.costo_pe` as the base price and use the configurable Elder dynamic-price curve at catalog/unlock time;
- enforce exact prerequisites for users, with master/admin bypass;
- represent spells through the separate one-to-one `SpellDefinition` contract and its safe linear formula configurator;
- collapse Order and Chaos completely into the unified magic conversion fields; do not store alignment, separate costs, or separate modifiers;
- treat Base, Apprendista, and Maestro as presentation tiers only;
- keep each ranked passive increment independent (for example every rank remains `+0.2`; the character total is produced by stacking owned ranks);
- preserve variable, recurring, alternative, and optional action costs as prose while structuring only compatible fixed cost components;
- apply the four legacy cost-reduction perks as system-managed unlock and pricing rules; removing the granting ownership automatically restores normal prices;
- flag ambiguous candidates for review and never apply them in the mass-import queue.

### Reviewed source-specific resolutions: batch 1

These rulings are explicit exceptions keyed by Elder source ID; they must not weaken generic conflict detection:

- `47`, `49`, `352`, `990`, `1350`: keep one active reminder. Alternate or equipment-dependent costs remain in its complete prose; use only the reviewed primary fixed cost when one exists.
- `515`: Scosso is one effect per 3 Mana, minimum 3 Mana, maintained for 3 Mana per turn.
- `522`: retain `Effetto = M` and the explicit thresholds 15, 35, 60, 90, 130.
- `523`, `524`, `525`: the old requirement text is not an unlock prerequisite. Use respectively 3, 4, and 4 Effect per Mana; enemy-specific adjustments are handled during play.
- `531`: damage is `Mana × 0.8`; at 10 resulting damage it also causes bleeding.
- `536`: resurrection is one fixed effect for 50 Mana.
- `555`: use one effect per 10 Mana with the alternate ally maintenance cost kept in prose.
- `1467`, `1472`: retain `Effetto = M`, minimum 10 Mana, and interpret the prose threshold during play.

### Reviewed source-specific resolutions: batch 2

- `576`: `Effetto = Mana × 2`; Effect is the maximum incoming spell Mana that Dispel can redirect.
- `632`: `CON` means the Concentration modifier, not Resistance.
- `714`: preserve the “at least one of four skills” requirement as text only; it is deliberately checked by the master and has no relational enforcement.
- `779`, `880`, `881`, `882`: complete descriptions are sufficient rule notes. Do not invent numeric effects or action buttons.
- Alchemy multipliers are character totals, not reagent-bag configuration. Colour ranks `871–879` add `0.2` to their own colour. `884` adds `0.5` and `885` adds `0.2` to level-3 effect. `886–887` each add `0.1` to every level-effect total.

### Reviewed source-specific resolutions: batch 3

- `1061`: preserve the three-way OR requirement as master-checked text and keep both Mana choices in one reminder.
- `1108`: description-only rule. Do not grant PE automatically or create duplicate ownership; the player records first/second acquisition in `Nota sullo sblocco`.
- `1205`: the source requirement `Paralisi` is erroneous; replace it with the exact `Rallenta` prerequisite.
- `1207`: enforce only `Paralisi da impatto`; the apprentice recovery-spell condition remains master-checked prose.

### Reviewed source-specific resolutions: batch 4

- `1312`: “all Hircine skills” remains master-checked text; structure 1 Stanchezza + 5 Potere.
- `1386`: “all previous skills” remains master-checked text; structure only 1 Stanchezza and keep 4 Potere per enemy in the reminder.
- `1458`: description-only minor-perk grant chosen and administered manually by the master.
- `1486`: the six-Peryite-skills threshold remains master-checked text; structure 1 Stanchezza.
- `1499`: the six-Vaermina-skills threshold remains master-checked text; structure only 1 Stanchezza and keep the variable 5+ Potere rule in the reminder.

## Purpose

This document is an operational specification for an LLM that analyzes and converts skill content from `the_elder_django` into ReDjango.

It is not permission to bulk-copy the legacy database. The LLM must produce evidence-backed candidates, validate them against the current ReDjango contract, import only deterministic cases through a dry-runnable and idempotent workflow, and set difficult or contradictory cases aside for an administrator.

The central architectural change is:

```text
Elder Django content:
FamigliaSkill + Skill + SkillProfileTags + EffettiSbloccabili + Attivabile

ReDjango content:
one Skill aggregate containing identity, progression, profile metadata,
passive effects, and reminder-only active actions,
plus a separate one-to-one SpellDefinition for actual spells
```

ReDjango still has separate runtime and ownership records such as `SkillPersonaggio` and character-owned effect snapshots. They are not additional skill-definition objects. Never place canonical skill rules in them.

## Non-negotiable instructions

An LLM performing this migration MUST follow these rules:

1. Open the Elder Django database read-only. Never mutate the original project or database.
2. Re-read the current ReDjango models, validators, and effect configuration before each migration run. This guide does not override newer code.
3. Treat `Skill` as the only ReDjango content aggregate for a skill.
4. Do not create or write `EffettiSkill`. It is a deprecated compatibility table.
5. Do not recreate or execute `Attivabile.effetto_attivabile`.
6. Do not infer executable mechanics from prose when the meaning is uncertain.
7. Do not turn an active or conditional rule into a passive character effect merely because it mentions a numeric bonus.
8. Do not silently resolve conflicting source fields. Quarantine the candidate for admin review.
9. Preserve source provenance and stable feature IDs.
10. Do not import character ownership at all.
11. Never use the normal `skills.unlock` command during migration: it deducts current PE and creates new passive snapshots.
12. A failed or uncertain conversion is not discarded. It goes into the admin-review artifact with exact evidence and precise questions.

## Files that define the current target contract

Before generating candidates, inspect at least:

```text
backend/core/models.py
backend/core/skill_services.py
backend/core/skill_selectors.py
backend/characters/models.py
backend/characters/services/custom_effects.py
backend/characters/services/refresh_personaggio.py
backend/api_v1/schemas.py
best_build_practices.md
Builder_docs/V2_DATABASE_STRUCTURE.md
```

Use the current backend-provided `effectConfiguration` as the authority for allowed passive targets, operations, icons, and formula help. Never rely only on a target or icon list remembered from a previous run.

## Observed legacy baseline

The Elder Django database inspected on 2026-07-17 contained:

| Record | Observed count | Migration significance |
|---|---:|---|
| `FamigliaSkill` | 79 | Already represented by ReDjango's five groups and curated family rows. |
| `Skill` | 1,477 | Each source row is a potential unified Skill candidate. |
| `SkillProfileTags` | 1,477 | One profile row existed for every Skill in this snapshot. |
| `Attivabile` | 1,342 | Most skills were classified as an active/reminder rule. |
| `EffettiSbloccabili` | 1,554 | Includes skill, race, and subrace proposals. Exactly 1,477 were linked to skills in this snapshot. |

Observed skill feature classification, derived from linked proposals:

| Derived class | Count | Meaning |
|---|---:|---|
| Active only | 1,247 | Linked `Attivabile`, no useful proposed passive. |
| Passive only | 203 | Useful `effetto_proposto`, no linked `Attivabile`. |
| Hybrid | 5 | Both a linked `Attivabile` and a proposed passive. |
| Neither | 22 | Neither source contains a usable feature definition. Inspect prose and normally send to admin review. |

These counts describe one snapshot, not permanent invariants. Every migration run must recompute them.

All 1,342 `Attivabile.effetto_attivabile` values in the inspected snapshot recursively decoded to an empty value such as `{}`, `"{}"`, or multiply encoded variants. The useful sources were descriptions, fixed cost columns, `Skill.formula_effetto`, and `EffettiSbloccabili.effetto_proposto`.

## Source schema: Elder Django

### `FamigliaSkill`

The legacy hierarchy is:

```text
FamigliaSkill.gruppo -> FamigliaSkill -> Skill
```

The five groups are:

```text
Generali
Religioni
Scuole di Magia
Classi
Perk
```

Important fields:

| Legacy field | Meaning |
|---|---|
| `nome` | Family name, for example `Viaggio e Inventario` or `Daedra – Sanguine`. |
| `gruppo` | One of the five group names above. |
| `note` | Family-facing notes. |
| `note_addizionali` | Additional family notes. |

Do not render or import a group as if it were a family. `Perk` is a group; `Perk Minori` and `Perk Maggiori` are families.

### `Skill`

The legacy `Skill` stores the primary identity, progression, descriptive, and magic fields.

| Legacy field | Meaning | ReDjango destination |
|---|---|---|
| `id` | Source identity | Provenance metadata only. |
| `nome` | Unique visible name | `name` / `Skill.nome`. |
| `numero` | Unique catalog number | `number` / `Skill.numero`. Preserve it. |
| `ordine_famiglia` | Order inside family | `familyOrder`. |
| `famiglia_id` | Family FK | Resolve to existing ReDjango `familyId`. |
| `magia` | Magic flag | Create `spell` / `SpellDefinition` only when true. |
| `costo_pe` | Base PE purchase price | `baseXpCost` / `Skill.costo_pe`; never replace it with a character-calculated price. |
| `tipo_pe` | Allowed PE color/category | `xpType` after explicit normalization. |
| `costo` | In-play rules/action cost | `rulesCost`. It is not the purchase price. |
| `descrizione` | Primary player-facing rule text | `description`. |
| `requisiti` | Free-text requirements | Always preserve in `requirementsText`; optionally resolve exact skill prerequisites. |
| `note` | Extra designer or rule notes | `notes`, or action usage notes when clearly player-facing. |
| `livello_magia` | Spell presentation tier | `spell.tier` after Base/Apprendista/Maestro normalization. |
| `raggio` | Range text | `spell.range`. |
| `formula_effetto` | Spell magnitude/mana relationship | Normalize to `spell.baseMana` and `spell.effectPerMana`, and preserve verbatim in `spell.legacyFormula`. Never treat it as a passive formula. |
| `effetto_da_aggiungere` | Old transitional field | Empty in the inspected snapshot. If populated later, preserve as evidence and require review. |

The legacy model has no dedicated `livello_minimo` field and no relational prerequisite graph. ReDjango intentionally adds no minimum-level field or unlock gate.

### `SkillProfileTags`

The legacy profile is a one-to-one object with 13 numeric tags on a scale from `-1` to `5`, plus notes:

```text
core_fisico
core_magico
focus_combat
range_skill
area_e_multi_target
natura_magica
difesa
attacco
sociale
supporto_party
esplorazione_infiltrazione
tecnica_crafting
controllo_situazionale
```

In ReDjango these become one `profileTags` JSON object and `profileNotes`. Preserve the keys and integer values. Do not reinterpret `-1`; it means irrelevant in the source profile.

### `EffettiSbloccabili`

This object is a proposal/link layer, not the final ReDjango destination.

Relevant fields:

| Legacy field | Meaning |
|---|---|
| `skill_collegata_id` | Skill linked to the proposal. |
| `attivabile_collegato_id` | Optional active/reminder definition. |
| `effetto_proposto` | Optional proposed passive effect. |
| `note_proposte` | Review context. |
| `confidence` | Confidence of the legacy proposal generator, not proof of correctness. |
| `fonte_tipo`, `fonte_nome` | Source type and name. |

A usable proposed passive normally has this shape:

```json
{
  "tipo": "effetto_extra",
  "effetto_extra": {
    "nome": "+ energia",
    "descrizione": "+1 Energia.",
    "origine": "Energico 1",
    "icona": "energia_extra",
    "effetti": [
      {"name": "energia", "operation": "+", "value": "1"}
    ]
  }
}
```

The following are not passives:

```json
{}
```

```json
{"tipo": "nessuno", "effetto_extra": null}
```

Never trust a proposal only because it is structurally populated. Compare its target, value, and description to the canonical Skill prose. The inspected data contains contradictory hybrid proposals.

### `Attivabile`

`Attivabile` was both an action definition and a generic container for any rule that needed to appear on the character sheet but could not be represented as a permanent numeric effect.

Relevant fields:

| Legacy field | Meaning | ReDjango destination |
|---|---|---|
| `nome` | Action/reminder name | `activeReminders[].name`. |
| `descrizione` | Main active rule | `activeReminders[].description`. |
| `costo_pf` | Fixed PF cost | `costs.pf` when unambiguous. |
| `costo_man` | Fixed mana cost | `costs.mana` when unambiguous. |
| `costo_en` | Fixed energy cost | `costs.energia` when unambiguous. |
| `costo_pow` | Fixed power cost | `costs.potere` when unambiguous. |
| `costo_pa` | Fixed action-point cost | `costs.pa` when unambiguous. |
| `costo_st` | Fixed fatigue cost | `costs.stanchezza` when unambiguous. |
| `durata_turni` | Optional duration | `duration`, as readable text. |
| `effetto_1` ... `effetto_4` | Old free-text ratios or modifiers | Evidence or `usageNotes`; never automatically executable. |
| `messaggio_ad_esecuzione`, `messaggio_a_fine_turno` | Optional reminder copy | `usageNotes` when meaningful. |
| `icona` | Legacy icon reference | Normalize against the current icon catalog or use `runa`. |
| `origine`, `gruppo` | Source/display grouping | Provenance and evidence. |
| `effetto_attivabile` | Nested experimental executor payload | Do not port or execute. |

The `effetto_1` fields often contain strings such as `1 Effetto = 4 Mana`. They are not equivalent to ReDjango passive operations.

### `NPC.abilita`

Legacy character ownership is a JSON object keyed by skill name. Values commonly contain strings under:

```text
rossi
verdi
blu
generali
testo
```

This is not canonical Skill content. It may later become `SkillPersonaggio`, but only in a separate historical ownership migration after the Skill catalog is final.

## Target schema: ReDjango

### Unified `Skill`

One ReDjango Skill contains:

```text
identity and catalog placement
purchase rules
descriptive details
relational Skill prerequisites
profile metadata
zero or more passive effects
zero or more active reminders
an optional separate SpellDefinition
provenance metadata
```

A representative authoring payload is:

```json
{
  "name": "Svelto 1",
  "slug": "svelto-1",
  "number": 4,
  "familyId": 123,
  "familyOrder": 10,
  "magic": false,
  "baseXpCost": 5,
  "xpType": "general",
  "rulesCost": "",
  "description": "+1 Punto Azione.",
  "requirementsText": "",
  "prerequisiteIds": [],
  "spell": null,
  "profileTags": {},
  "profileNotes": "",
  "passiveEffects": [],
  "activeReminders": [],
  "icon": "runa",
  "notes": "",
  "metadata": {}
}
```

### Passive feature

A passive is embedded in `Skill.passiveEffects`:

```json
{
  "id": "passivo-legacy-es-32",
  "name": "+ energia",
  "description": "+1 Energia.",
  "icon": "energia",
  "operations": [
    {
      "target": "energia",
      "operation": "add",
      "value": "1",
      "condition": ""
    }
  ]
}
```

At unlock, every passive must be accepted explicitly. ReDjango then snapshots it into character-owned `EffettoPersonalizzato` and `OperazioneEffettoPersonalizzato` rows.

Consequences:

- Passive IDs must remain stable forever after ownership exists.
- Editing a Skill passive later does not automatically rewrite existing character snapshots.
- Finalize and approve passive content before importing ownership.

### Active reminder

An active rule is embedded in `Skill.activeReminders`:

```json
{
  "id": "azione-legacy-attivabile-101",
  "name": "Scudo umano",
  "description": "Quando un nemico attacca un alleato vicino, puoi farti scegliere come bersaglio.",
  "trigger": "Quando un nemico attacca un alleato entro 1 casella",
  "duration": "Per quell'attacco",
  "usageNotes": "Hai -3 Difesa su quell'attacco.",
  "costs": {"energia": 3},
  "icon": "scudo"
}
```

An active reminder is deliberately non-executable. Its UI can reveal the rule and displayed costs, but it never spends resources, applies damage, changes combat state, or creates a passive effect.

Consequences:

- Complex combat, crafting, social, informational, conditional, and world rules can be preserved as reminders without pretending to automate them.
- Action IDs must remain stable because `SkillPersonaggio.configurazione_azioni` is keyed by them.
- Canonical action text and costs stay on Skill. Character configuration contains only visibility, order, and a personal note.

### `SkillPersonaggio`

`SkillPersonaggio` stores:

```text
personaggio
skill
spesa_pe
passivi_accettati
configurazione_azioni
note
```

It does not store a copy of the Skill description, passive definitions, or action rules.

## Source-of-truth precedence

Use this precedence when constructing a candidate:

1. `Skill` is authoritative for identity, family, catalog number, PE cost/type, primary description, requirements, notes, magic level, range, and `formula_effetto` display text.
2. A valid `EffettiSbloccabili.effetto_proposto` is the strongest structured passive candidate, but only when it agrees with Skill prose.
3. A linked `Attivabile` is the strongest active-reminder candidate, but its costs and description must be reconciled with `Skill.costo`, `Skill.descrizione`, and `Skill.note`.
4. `SkillProfileTags` supplies profile metadata.
5. `Attivabile.effetto_1...4` supplies supporting notes, not executable operations.
6. `Attivabile.effetto_attivabile` supplies no trusted information. If a future snapshot contains a non-empty decoded payload, quarantine it for admin review.
7. `NPC.abilita` supplies historical ownership evidence only.

When two sources conflict, do not use precedence as permission to hide the conflict. Preserve both values in staging evidence and require admin resolution when the choice changes mechanics.

## Formula systems are different

There are at least three formula-like languages in the legacy data. They must not be conflated.

### 1. Spell magnitude formula: `Skill.formula_effetto`

Examples:

```text
M*2
M/4
(m-10)/7
M*1,5
```

In the legacy spell/action UI, `M` was used as part of a mana-to-effect or magnitude relationship. It is not a ReDjango character-stat context variable.

Migration rule:

- Parse only the supported linear `M`, `M*k`, `M/k`, and `(M-base)/k` forms into `spell.baseMana` and `spell.effectPerMana`.
- Keep `spell.minimumMana` separate: `baseMana` is the formula offset, while `minimumMana` is the least legal cast inferred from an explicit, unambiguous source rule.
- Copy the original text verbatim into `spell.legacyFormula`.
- Do not place it in `passiveEffects[].operations[].value`.
- Do not evaluate arbitrary source text or replace `M` with a character-stat expression.
- Do not normalize decimal commas in `spell.legacyFormula`; normalize only the structured Decimal values.
- Treat `formula_effetto` as authoritative over a generated `effetto_1` line only when the formula and player-facing rule describe the same mechanic; flag real formula/prose disagreement for review.

`SpellDefinition` is evaluated only by the read-only spell preview. It does not spend resources; combat persistence remains future work.

### 2. Legacy proposed-passive formula

Examples:

```text
(f)Personaggio.livello
(f)Personaggio.modificatore_Saggezza * 2
(f)Personaggio.modificatore_Resistenza * 5 + (f)Personaggio.livello
```

These values may be converted when the target and rule are otherwise valid.

Deterministic token rewrites:

| Legacy token | ReDjango token |
|---|---|
| `(f)Personaggio.livello` | `personaggio.livello` |
| `(f)Personaggio.modificatore_Forza` | `final.mod_forza` |
| `(f)Personaggio.modificatore_Resistenza` | `final.mod_resistenza` |
| `(f)Personaggio.modificatore_Velocita` or accented variant | `final.mod_velocita` |
| `(f)Personaggio.modificatore_Agilita` or accented variant | `final.mod_agilita` |
| `(f)Personaggio.modificatore_Intelligenza` | `final.mod_intelligenza` |
| `(f)Personaggio.modificatore_Concentrazione` | `final.mod_concentrazione` |
| `(f)Personaggio.modificatore_Personalita` or accented variant | `final.mod_personalita` |
| `(f)Personaggio.modificatore_Saggezza` | `final.mod_saggezza` |
| `(f)Personaggio.modificatore_Fortuna` | `final.mod_fortuna` |

After rewriting:

1. Convert decimal commas to decimal points only in the candidate executable expression.
2. Validate the expression with the current ReDjango safe evaluator.
3. Confirm every referenced context field exists.
4. Confirm the description agrees with the referenced characteristic. A description mentioning Concentrazione with a formula using Resistenza is an admin-review conflict.
5. Test at representative low, medium, and high values.
6. Flag dynamic denominators, possible division by zero, circular `final.*` dependencies, and negative values that may violate the intended rule.

### 3. Prose and old free-text action formulas

Examples:

```text
1 Effetto = 4 Mana
1 Attacco = 1 Energia
2+ Energia
1 Mana per turno
10, 20 o 40 Mana
```

These are rules text, not safe passive expressions.

Migration rule:

- Preserve them in `rulesCost`, action `description`, or `usageNotes`.
- Do not convert them into passive operations.
- Do not encode alternatives as simultaneous fixed costs.
- Do not reduce a range or scaling cost to its smallest number.
- Use fixed action cost fields only when the amount and resource are unambiguous.

## ReDjango passive expression language

The current safe evaluator supports:

```text
contexts: base.<field>, pre.<field>, final.<field>, personaggio.<field>
arithmetic: +, -, *, /, **
comparison in conditions: ==, !=, >, >=, <, <=
functions: floor, ceil, round, abs, min, max
```

The operation order is:

```text
add -> subtract -> multiply -> percent -> min -> max/cap -> set
```

`formula_override` replaces a statistic's formula before normal operations. `strong_set` runs last after fatigue and general-modifier adjustments.

Do not choose `formula_override`, `set`, or `strong_set` merely because the prose says "becomes", "always", or "equals". These operations materially change calculation timing and require exact mechanical evidence.

## Field mapping rules

### PE type

Use only these mappings:

| Elder Django | ReDjango |
|---|---|
| `Tutti` | `all` |
| `Tutto` | `all` |
| `Generali` | `general` |
| `Rossi` | `red` |
| `Verdi` | `green` |
| `Blu` | `blue` |

Unknown or empty values require admin review. Do not infer PE type from family, color, description, or profile tags.

### Family

Resolve the legacy family against an existing ReDjango family using:

```text
canonical group + canonical family name
```

Comparison may normalize Unicode form, surrounding whitespace, repeated whitespace, and dash variants. The stored target must remain the canonical ReDjango row.

Do not create a new family automatically when no match exists. Send the Skill to admin review with the source group and family.

### Description only

Do not generate a summary. Preserve the complete player-facing rule in `description`; compact cards render that same field.

### Minimum level and prerequisites

Always copy `Skill.requisiti` into `requirementsText`.

Populate `prerequisiteIds` only when every prerequisite token resolves to exactly one staged/imported Skill by canonical name. Exact comma/semicolon-separated AND lists and explicitly approved legacy aliases are safe. Typical examples are exact rank chains such as:

```text
Svelto 2 requires Svelto 1
Svelto 3 requires Svelto 2
```

Do not create a Skill FK for:

- attribute thresholds such as `INT almeno 15`;
- magic-rank words such as `Adepto` unless there is an exact and intended Skill with that name;
- situational requirements;
- formulas or percentages;
- ambiguous prose whose separators do not clearly mean an AND list;
- a missing, duplicate, or archived name.

The legacy model has no explicit minimum-level field. Do not create one and do not infer an unlock gate. Preserve any level wording in `requirementsText` for review.

Resolve prerequisites in a second pass after every candidate identity is known. Detect self-dependencies, missing references, and cycles. Any cycle requires admin review.

### Profile tags

Copy the 13 legacy keys and integer values into `profileTags`. Copy legacy profile `notes` into `profileNotes`.

Validation rules:

- every known value must be an integer from `-1` through `5`;
- unknown future keys may be preserved in staging evidence but are not silently discarded;
- missing profile rows do not block identity import, but create a warning;
- do not regenerate legacy tags with an LLM unless the administrator requested retagging as a separate task.

### Icons

Every target icon must be present in the current backend-provided icon catalog.

- Normalize a clearly equivalent legacy icon to a current slug.
- If no exact semantic match exists, use `runa` and preserve the legacy icon value in staging evidence and provenance metadata.
- An icon mismatch alone need not block import, but it must generate a warning.

## Passive conversion algorithm

For each Skill-linked `EffettiSbloccabili`:

1. Recursively decode `effetto_proposto` if necessary.
2. Treat it as absent unless `tipo == "effetto_extra"` and `effetto_extra` is a populated object.
3. Compare `effetto_extra.descrizione` and every operation to `Skill.descrizione` and `Skill.note`.
4. Create one passive feature from the proposed effect unless the source clearly describes multiple separately named passive features.
5. Use a stable ID such as `passivo-legacy-es-<EffettiSbloccabili.id>`.
6. Map `+` to `add` and `-` to `subtract`.
7. Normalize the target through the current ReDjango target resolver.
8. Rewrite only the recognized legacy formula tokens described above.
9. Use an empty condition unless an exact, supported, machine-verifiable condition exists in the source.
10. Validate the complete passive with `validate_effect_values` through the Skill authoring validator.

Direct target equality is normally safe. The inspected snapshot contained 249 proposed passive operations; 177 used targets directly supported by ReDjango.

The following equipment-aware legacy target groups are current ReDjango targets and are automatically convertible:

- `atk_skill_corte`, `atk_skill_medie1`, `atk_skill_medie2`, `atk_skill_lunghe`, `atk_skill_precise`, `atk_skill_potenti`;
- `atk_skill_maninude`, `tier_skill_maninude`;
- `def_skill_leggera`, `def_skill_pesante`, `def_skill_noarmatura`, `def_skill_scudo`;
- `ogni_en_x_mana_ordine`, `ogni_en_x_mana_caos`, `ogni_pa_x_mana_ordine`, `ogni_pa_x_mana_caos` are approved aliases for the corresponding unified fields.

Weapon and armor specialization totals remain distinct targets. During character refresh, the backend projects only those matching the currently equipped weapon, armor, shield, or unarmed state into the general Attacco, Difesa, or Tier total; changing equipment removes the old projection. Order and Chaos must be collapsed into ReDjango's unified fields; never preserve their distinction in metadata, costs, casting, or UI.

If a passive target is unavailable, use one of these outcomes:

```text
rule is still useful as a player reminder -> propose an active reminder and require review
rule requires a new calculated target -> admin_required
proposal contradicts prose -> admin_required
rule has no reliable meaning -> admin_required
```

## Active reminder conversion algorithm

For each linked `Attivabile`:

1. Confirm that its name/origin plausibly matches the Skill.
2. Use a stable ID such as `azione-legacy-attivabile-<Attivabile.id>`.
3. Preserve the fullest non-contradictory rule text from `Skill.descrizione`, `Skill.note`, and `Attivabile.descrizione`.
4. Avoid duplicating a cost sentence already present in the description.
5. Extract `trigger` only when the trigger is explicit. Otherwise leave it empty and keep the source wording in the description.
6. Convert `durata_turni` or explicit duration prose into readable `duration` text. The value remains informational.
7. Put useful `effetto_1...4` and legacy execution/end messages in `usageNotes` when they aid the player.
8. Copy fixed integer costs only when their semantics are unambiguous.
9. Validate every cost as an integer from 0 through 999.
10. Normalize the icon or use `runa`.

Fixed cost mapping:

```text
costo_pf  -> costs.pf
costo_man -> costs.mana
costo_en  -> costs.energia
costo_pow -> costs.potere
costo_pa  -> costs.pa
costo_st  -> costs.stanchezza
```

Keep variable, ranged, optional, alternative, per-target, per-effect, and maintenance costs in the complete reminder prose. Omit those parts from the fixed `costs` object. Set the candidate aside for admin review when:

- `Skill.costo` conflicts with the numeric `Attivabile` cost;
- the prose and fixed source columns genuinely disagree about the same mandatory component;
- alternatives or maintenance rules cannot be preserved clearly in the reminder prose;
- the action automatically assumes combat state, target selection, resource mutation, or turn scheduling;
- the linked Attivabile appears to belong to another Skill.

Because ReDjango actions are reminders, many complex rules are still safely representable as prose. The migration must not promise automatic execution.

## Hybrid conversion

A hybrid legacy Skill becomes one ReDjango Skill with both arrays populated:

```text
Skill.passiveEffects = [validated passive definitions]
Skill.activeReminders = [validated reminders]
```

Do not split a hybrid into two Skill rows. Do not create `EffettiSkill`.

Hybrid cases require stronger review because the inspected legacy data includes examples where the proposed passive does not agree with the linked active description. A structurally valid pair is not necessarily a semantically valid pair.

## Provenance and stable identity

Use `Skill.metadata` for compact provenance, not for full raw source dumps.

Recommended metadata:

```json
{
  "sourceProject": "the_elder_django",
  "sourceTable": "django_slim_skill",
  "sourceId": 4,
  "sourceFamilyId": 1,
  "sourceProfileId": 4,
  "sourceEffettiSbloccabiliId": 32,
  "sourceAttivabileId": null,
  "migration": {
    "version": "skill-unification-v1",
    "status": "auto_import",
    "confidence": 0.99,
    "sourceHash": "sha256:...",
    "warnings": []
  }
}
```

Keep complete raw source rows and comparison evidence in the staging artifact, not in database metadata.

Idempotent matching order:

1. Existing Skill with matching `metadata.sourceProject` and `metadata.sourceId`.
2. If no provenance match exists but name, number, or slug collides, stop and request admin resolution.
3. Never overwrite an existing curated Skill merely because its visible name matches a legacy name.

Preserve legacy `numero`. Generate the slug deterministically from the source name unless the administrator has already curated one.

## LLM staging output

The LLM must produce a staging record before any write:

```json
{
  "source": {
    "skillId": 4,
    "skillName": "Svelto 1",
    "familyId": 1,
    "profileId": 4,
    "proposalId": 32,
    "attivabileId": null,
    "sourceHash": "sha256:..."
  },
  "decision": "auto_import",
  "confidence": 0.99,
  "evidence": {
    "sourceDescription": "+1 Punto Azione.",
    "sourceRulesCost": "",
    "sourceRequirement": "",
    "decodedActivablePayload": {},
    "passiveProposal": {}
  },
  "redjangoValues": {},
  "warnings": [],
  "adminQuestions": []
}
```

Allowed decisions:

```text
auto_import
needs_review
admin_required
skip_non_skill_source
```

`redjangoValues` must be null for `admin_required` unless the workflow explicitly supports non-published drafts outside the live Skill table.

The batch artifact must also include:

- counts by decision;
- unmatched families;
- name/number/slug conflicts;
- unresolved or cyclic prerequisites;
- unsupported passive targets;
- formula conversion failures;
- cost conflicts;
- missing linked records;
- a list of every candidate changed since the previous source hash.

## Decision policy

### `auto_import`

Use only when all of the following are true:

- family resolves exactly;
- name, number, and slug are conflict-free or match existing provenance;
- PE cost and type map exactly;
- requirements are empty or resolve without ambiguity;
- passive targets, operations, values, and formulas validate and agree with prose;
- action costs are fixed and non-contradictory, or are left entirely in prose without misrepresentation;
- all feature IDs are stable;
- current Skill validation succeeds;
- no source field with mechanical meaning is silently dropped.

### `needs_review`

Use for a complete, valid candidate that contains a non-blocking judgment call, for example:

- icon fallback;
- trigger/duration extraction that does not change mechanics;
- missing profile row;
- harmless source formatting cleanup.

Do not write `needs_review` candidates to the live catalog unless the administrator has explicitly approved that queue.

### `admin_required`

Use whenever any of these applies:

- unsupported or unknown target;
- prose and structured proposal disagree;
- fixed cost columns and cost prose disagree;
- variable or alternative costs cannot be represented faithfully;
- prerequisite is ambiguous or currently unenforceable;
- formula contains unknown symbols, unclear timing, text, or unsafe operations;
- a conditional passive depends on combat events, targets, inventory, world state, or previous-turn state;
- effect stacking, replacement, accumulation, or maximum rules are unclear;
- source describes a competence/check bonus that is not a supported calculated target;
- duplicate source identity or target collision;
- multiple proposals exist and cannot be merged deterministically;
- non-empty `effetto_attivabile` is found;
- the Skill would require a new ReDjango mechanic or schema field;
- confidence is low for any mechanical decision.

Admin-review questions must be narrow and actionable. Bad: `This is complicated; what should I do?` Good: `The description grants +1 Potere per Concentrazione, but the proposal formula references Resistenza. Which characteristic is authoritative?`

## Difficult-case examples

### Safe passive

Legacy:

```json
{"name": "pa", "operation": "+", "value": "1"}
```

ReDjango:

```json
{"target": "pa", "operation": "add", "value": "1", "condition": ""}
```

This is auto-convertible when the Skill description also grants `+1 Punto Azione`.

### Safe formula rewrite

Legacy:

```text
(f)Personaggio.modificatore_Saggezza * 2
```

ReDjango candidate:

```text
final.mod_saggezza * 2
```

Validate it and confirm the description also refers to Saggezza.

### Spell magnitude formula

Legacy:

```text
M/4
```

ReDjango:

```text
spell.baseMana = 0
spell.effectPerMana = 0.25
spell.legacyFormula = "M/4"
```

Do not create a passive operation.

### Variable cost

Legacy:

```text
2+ Energia
```

ReDjango:

- preserve `2+ Energia` in `rulesCost` and action prose;
- do not automatically set `costs.energia = 2` as if 2 were the complete price;
- request admin review if a structured fixed cost is required.

### Conditional combat rule

Legacy:

```text
Quando un nemico ti attacca, puoi spendere 4 Energia per dimezzare il danno.
```

ReDjango:

- create an active reminder, not a passive effect;
- set the explicit trigger and fixed cost;
- preserve `dimezzare il danno` as rule text;
- do not implement damage interception or resource spending.

### Contradictory hybrid

If the active description grants a competence bonus while the passive proposal grants `attacco`, `difesa`, or `pa` with no support in the Skill prose, set `admin_required`. Do not keep both merely because the legacy proposal classified the Skill as hybrid.

## Character ownership migration

Ownership migration is a separate phase.

For each legacy `NPC.abilita` entry:

1. Resolve the key to exactly one imported Skill using provenance-aware name mapping.
2. Convert `generali`, `rossi`, `verdi`, and `blu` strings to non-negative integers.
3. Map them to `general`, `red`, `green`, and `blue` in `SkillPersonaggio.spesa_pe`.
4. Preserve non-empty `testo` in ownership notes or a review artifact.
5. Compare the historical spend to the Skill's purchase cost and allowed pools.
6. If values are invalid, names do not resolve, or totals disagree, require admin review.
7. Do not map `pe_abilita` into an invented spend pool; the current unlock service supports general/red/green/blue only.
8. Do not deduct current character PE.
9. Do not call `skills.unlock`.
10. Create accepted passive IDs and passive snapshots only through a dedicated historical-import service, inside one transaction, after content approval.
11. Initialize action configuration from the imported Skill's stable action IDs.

Run content import first because passive definitions are snapshotted while actions remain live references to the Skill definition.

## Required migration workflow

### Phase 1: Read-only extraction

For every source Skill, extract one bundle containing:

```text
Skill
FamigliaSkill
SkillProfileTags
all linked EffettiSbloccabili
each linked Attivabile
```

Use bounded recursive JSON decoding for suspicious JSON-in-string values. Record decoding failures without evaluating content.

### Phase 2: Candidate construction

Build identity and descriptive fields first. Then resolve passive features, active reminders, profile tags, provenance, and warnings.

Never let a failed passive or action conversion erase the Skill's original prose from staging evidence.

### Phase 3: Cross-record resolution

After all candidate identities exist:

- resolve families;
- resolve prerequisites;
- detect duplicate identity;
- detect cycles;
- compare rank chains;
- compare repeated source hashes with prior runs.

### Phase 4: Validation

Validate every candidate through the same current functions used by Skill authoring. At minimum:

- `validate_skill_values` succeeds;
- every passive succeeds through `validate_effect_values`;
- feature counts stay within current limits;
- operation counts stay within current limits;
- action costs stay within range;
- formulas and conditions use only allowed AST constructs;
- names, numbers, slugs, passive IDs, and action IDs are unique where required;
- no prerequisite is missing, self-referential, or cyclic.

### Phase 5: Triage

Write three explicit artifacts:

```text
skills_auto_import.json
skills_needs_review.json
skills_admin_review.json
```

An equivalent structured format is acceptable, but the queues must remain separable and machine-readable.

The admin artifact must include source text, structured source values, the rejected or partial candidate, blockers, and exact questions.

### Phase 6: Dry run

The future importer must:

- run in a database transaction;
- support `--dry-run` and roll back all writes;
- be idempotent by source provenance;
- never write to the Elder Django database;
- report created, updated, unchanged, reviewed, and rejected counts;
- refuse to import `admin_required` records;
- refuse to overwrite curated target records without matching provenance and explicit policy.

### Phase 7: Admin approval

An administrator reviews:

- every `admin_required` record;
- any `needs_review` record selected by policy;
- any proposed new calculated targets;
- all formula timing changes;
- all prerequisite ambiguities.

Do not treat silence as approval.

### Phase 8: Real import and reconciliation

After approval:

1. Import or update approved Skill definitions.
2. Re-run the same importer and confirm the second run is unchanged.
3. Compare source and target counts by group, family, feature type, and decision.
4. Sample at least one active, passive, hybrid, magic, formula-bearing, variable-cost, and prerequisite-chain Skill.
5. Fetch the `/api/v1/skills` projection and verify the unified card payload.
6. Preview unlocks in a rollback-only test and confirm passive acceptance, PE rules, and action grants.
7. Only then begin the separate ownership migration.

## Required tests for an implemented importer

An importer is not complete until tests cover:

- read-only source connection;
- recursive empty-payload decoding;
- PE type normalization including `Tutti` and `Tutto`;
- family matching and mismatch quarantine;
- profile tag preservation;
- passive `+` and `-` conversion;
- legacy formula-token conversion;
- rejection of unknown formula variables;
- unsupported target quarantine;
- action fixed-cost mapping;
- variable and alternative cost quarantine;
- hybrid assembly into one Skill;
- stable passive/action IDs across reruns;
- exact prerequisite linking and cycle rejection;
- name/number/slug collision safety;
- provenance-based idempotency;
- dry-run rollback;
- no writes to `EffettiSkill`;
- no use of nested activable execution payloads;
- no permanent PE deduction during ownership reconstruction.

Run the normal project checks after implementation:

```bat
venv\Scripts\python.exe manage.py check
venv\Scripts\python.exe manage.py test
venv\Scripts\python.exe manage.py makemigrations --check --dry-run
cd frontend
npm run typecheck
npm run test
npm run build
```

Run the affected Playwright flow when importer work changes the catalog or card presentation.

## Final acceptance checklist for the LLM

Before marking any candidate importable, answer all of these with evidence:

- Is the family group correct?
- Is the family correct?
- Are name, number, order, magic flag, PE price, and PE type preserved?
- Is `Skill.costo` treated as a play cost rather than PE cost?
- Is all important prose preserved?
- Are relational prerequisites exact and non-cyclic?
- Is `formula_effetto` kept descriptive rather than mistaken for a passive formula?
- Does every passive operation use a current target and operation?
- Does every converted passive formula pass the safe evaluator?
- Does the passive agree with the Skill prose?
- Is every active rule a reminder rather than an executor?
- Are fixed costs truly fixed and cumulative rather than variable or alternative?
- Are stable feature IDs present?
- Is provenance complete?
- Would rerunning the import leave the same target state?
- Are difficult questions in the admin queue rather than answered by guesswork?

If any answer is unknown, the candidate is not `auto_import`.

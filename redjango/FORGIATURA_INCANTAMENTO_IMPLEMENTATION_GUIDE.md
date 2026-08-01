# Forgiatura and Incantamento: data audit and implementation guide

## Goal

Replace the two `EmptyWorkshop` placeholders in
`frontend/src/features/creation/CreationPage.tsx` with two complete, transactional
workbenches that match the Alchimia slice already shipped on tab 01.

This document answers three questions in order:

1. **Is there enough data in the system to build these tabs?** (Section: *Verdict*)
2. **What exactly exists, and where?** (Section: *Data inventory*)
3. **What must be built, in what order?** (everything after *Engine gaps*)

Every claim about existing data in this document was verified against
`db.sqlite3` and the source tree on 1 August 2026. Row counts are real.

---

## Verdict

**Forgiatura: YES — build it. The data is unusually complete.**

The blocker is not data, it is one authoring pass over 34 skills that today carry
their rules only as Italian prose. Everything else already exists: the 15
materials, the tier ladder, every improvement target, the tool ladder, the price
curve, and — critically — the effect pipeline that makes a forged improvement
show up on the character sheet with **zero new engine code**.

The authoring pass needs **no new database fields and no schema migration**: the
`tot` totals are a JSON field driven by a Python tuple, and the `Formule_base`
profile already self-heals when keys are added.

**Incantamento: YES, but it is the second slice, not the first.**

The data is arguably even richer (a fully level-indexed catalogue of ~4,200
enchanted accessories, 102 spells with mana formulas, 20 soul gems, 8 altars),
but the system has more moving parts: spell knowledge, charges, daily recharge,
multi-enchant stacking, and scrolls. It also depends on a resource the Forge
slice will establish first (per-instance item state).

**Neither can ship without the prerequisite in *Engine gaps* §1.** That is the
real answer to "is there enough data": the *content* is there in abundance; the
*machine-readable rules* are not, and writing them is the actual project.

Everything in this document was verified against the live database. Where a gap
has since been closed, the section says so and names the migration.

---

## Data inventory — what already exists

### Skills: the rules are all written, in prose

| Family | Skills | Have structured `effetti_passivi` |
|---|---|---|
| `Fabbro` | 34 | **0** |
| `Incantatore` | 45 | 2 (`Moda delle anime`, `Arte delle anime` → `anelli_max`/`orecchini_max`) |
| `Alchimista` (reference) | — | yes, targeting `moltiplicatore_reagenti_*` |

All 79 forge/enchant skills carry their entire rule in `Skill.descrizione` and a
placeholder `azioni_attive` entry with `"costs": {}`. They are readable by a
human and invisible to the engine.

The prose is high quality and complete. Selected examples:

**Fabbro — material gating (mirrors the 7 Elder tiers exactly):**

```
Fabbro 1                     forge and repair simple items
Fabbro 2                     ferro, pelle, legno            (tier 1)
Fabbro 3                     chitina, acciaio               (tier 2)
Fabbro 4                     elfico, nordico                (tier 3)
Specialista armaiolo         gateway; each unlocked sibling makes the others cost -1
  Lingotto di Ossa      (7)  ossa dunmer     (tier 4)   Fucina Orchesca      (7)  orchesco  (tier 4)
  Materiale Dreugh      (8)  dreugh          (tier 5)   Segreti Dwemer       (8)  dwemer    (tier 5)
  Lavorazione del Vetro (9)  vetro           (tier 6)   Maestria dell'Ebano  (9)  ebano     (tier 6)
  Lavorazione Adamantio (10) adamantio       (tier 7)   Fattura daedrica     (10) daedrico  (tier 7)
```

**Fabbro — improvement budget:**

```
Potenziato 1..7      max improvements = (N + 1) - material level, 1 ingot per +1
Specialista 1..3     +1..+3 improvements on ONE chosen material (rebindable for 3 Stanchezza)
Il meglio che posso  spend 1 Stanchezza for +1 improvement point
Scioglitore          melt metal items to recover material
Riplasmare           change an improved item's metal, carrying its improvement points over
Fabbricante di frecce / Design di freccia   arrow bonuses (+1 base; light → 10% AP, heavy → +1 tier)
Uso pratico 1/2/magico                      quivers, potion/scroll holders, cloaks; 2 leather +2 per level
Fucina improvvisata                         forge anywhere if you carry smith's tools
Converti oggetto                            ring↔brooch↔earring↔amulet; band↔belt; cloak→anything
```

**Incantatore — level gating and economy:**

```
Incantatore 1..3     scrolls AND items, levels 1..3
Scriba 1..7          scrolls only, levels 4..10
Gioielliere 1..7     jewellery/items only, levels 4..10
Infusore 1..5        mana per enchant level: 6, 7, 8, 9, 10   (base is 5)
Anima compressa 1/2  charges +25%, then a further +25%
Multi Incantamento 1/2   2, then 3 effects on one item; charges tracked independently per gem
Incantatore Esperto  re-enchant existing/looted items, at different times
Artigiano di anime   sum multiple gems: 1st counts 1, 2nd 1/2, 3rd 1/3 …
Riciclo di anime     disenchant and recover the soul (still needs a gem), 1 Stanchezza
Mana e anima         +1 enchant level, max +1, hard cap level 10, 1 Stanchezza
Danno da impatto / Paralisi da impatto / Assorbi danno / Assorbi PA / Assorbi Anima   weapon enchants
Infondi risorse      infuse PF, Mana, Potere, Energia
Rilegatore / Scrittore Esperto / Scrittore Eccezionale   grimoire authoring
```

Source: `core_skill` joined to `core_famigliaskill` where `f.nome IN ('Fabbro','Incantatore')`.

### The material system is already the item type system

`Oggetto.tipo_2` **is** the material key on every weapon and armour piece. The
14 forge materials map one-to-one onto the Elder tier ladder, and each has a
matching `lingotto` item with a price that encodes the tier:

| Tier | Light | Heavy | Ingot value |
|---|---|---|---|
| 1 | Legno / Pelle | Ferro | 25 |
| 2 | Chitina | Acciaio | 50 |
| 3 | Elfico | Nordico | 80 |
| 4 | Ossa | Orchesco | 120 |
| 5 | Dreugh | Dwemer | 400 |
| 6 | Vetro | Ebano | 800 |
| 7 | Adamantio | Daedrico | 1500 |

Item counts by `tipo_2`: legno 93, acciaio 64, ebano 58, ossa 54, adamantio 53,
vetro 52, daedrico 52, elfico 51, chitina 51, dreugh 49, dwemer 48, nordico 47,
ferro 47, orchesco 46, pelle 9.

Ingot rows (`tipo_1='lingotto'`, 15 rows): the 14 above plus
`Lingotto massiccio di oro` (rarità 5, weight 6, value 2500) which is **treasure,
not a crafting material** and must be excluded by key, not by type.

Note the naming irregularities the catalogue will have to normalise:
`Legno per armi` (not "Lingotto di legno"), `Scheletro di dreugh` (not an
ingot noun), and pelle has no ingot row at all — `Uso pratico` consumes
"unità di pelle" which currently has no item to consume.

### Every Elder improvement maps onto an existing engine target

`Oggetto.effects` is a structured list already populated on **3,369 of 5,895
items**, with the shape:

```json
[{"target": "attacco", "operation": "subtract", "value": 3, "source": "elder_import"}]
```

Mapping the Elder improvement menu onto real `tot` keys:

| Elder improvement | Cost | Engine target | Status |
|---|---|---|---|
| +1 Attacco | 1 | `attacco` | exists |
| +1 Tier Danno | 1 | `tier` | exists |
| −1 Peso | 1 | `Oggetto.peso` column on the instance | exists — direct column write |
| Effetto Sanguinamento | 1 | `Oggetto.regole_speciali` | exists — table rule |
| +1 Punti Azione | 2 | `pa` | exists |
| 1 Reroll per turno | 2 | `Oggetto.regole_speciali` | exists — table rule |
| +1 Difesa | 2 | `difesa` | exists |
| −1 Costo PA per Attacco (2H only) | 3 | `Oggetto.pa_per_attacco` column | exists |
| +1 Difesa (armour) | 1 | `difesa` | exists |
| +1 RD Fisica | 1 | `rd_fis` | exists |
| +1 Resistenza ×2 caratteristiche | 1 | `res_contundente/_taglio/_perforante/_fuoco/_gelo/_elettro` | exists |
| +1 Energia Massima | 1 | `energia` | exists |
| +3 RD Magica (one element) | 2 | `rd_fuoco/_gelo/_elettro` | exists |
| +1 Attacco (armour) | 2 | `attacco` | exists |
| +1 Punti Azione (armour) | 2 | `pa` | exists |

**All 14 improvements are expressible today.** Eleven are structured `effects`
operations that the totals engine already consumes; `−1 Peso` is a direct write
to the instance's `peso` column (`Martello (ferro)` is `peso 4.0`, so an improved
one is `3.0`); Sanguinamento and Reroll are written into `regole_speciali` and
adjudicated at the table. See *Engine gaps* §4 for the `regole_speciali` caveat.

### The enchanting output space is already a complete, level-indexed catalogue

The accessory catalogue is not decoration — it is the enchantment result table.
**4,217 accessories** across 7 wearable slots, keyed by:

- `tipo_1` = slot (`anello` 605, `mantello` 617, `orecchino` 601, `amuleto` 599,
  `cintura` 599, `fascia` 598, `spilla` 598)
- `tipo_2` = enchant kind (~70 distinct: `attacco_item`, `pf_item`, `mana_item`,
  `difesa_item`, `energia_item`, `potere_item`, `pa_item`, `rd_fis`, `res_fuoco`,
  `res_gelo`, `res_elettro`, `barr_fis_item`, `barr_mag_item`, `rigenerazionepf`,
  `rigenerazionemana`, `sifone_di_mana`, `reroll`, `recast`, `blink`,
  `darkvision`, `luce`, `estrazione`, `telecinesi`, `raggioarcano`,
  `materializzazione`, `shapeshifting`, `immaginispeculari`, `contingenza`,
  `illusioneminore`, `rangespell`, `rangespell(singola)`, `mod.gen.`,
  `*_extra` for each characteristic, `+skill*` for each competence …)
- `lv_loot` = **enchant level 1–10**

The value curve is identical across every kind:
`50, 120, 210, 320, 450, 600, 800, 1100, 1400, 1800`.

Consequence: **enchanting does not have to invent effects.** An enchant is a
lookup — `(slot, kind, level) → Oggetto` — and the resulting row already carries
the correct `effects`, price, and name. Some kinds only span levels 3–10
(the `*_extra` characteristic ones), which the picker must respect.

### Enchanting inputs all exist as items

| Input | `tipo_1` | Rows | Detail |
|---|---|---|---|
| Soul gems | `gemmaanima` | 20 | lv 1–10, empty (10/lv) and full (100/lv), weight 3 |
| Altars | `altareincantamento` | 8 | base +10%, apprendista +17%, qualificato +25%, avanzato +32%, maestro +40% mana; portable variants at 2× price |
| Scrolls | `pergamena` | 241 | 8 schools × minore/media/maggiore × lv 1–10 |
| Grimoires | `grimorio` | 7 | Del Mago, Del Negromante, Del Copiatore, Dello Sdoppiamento, Lungo, Del Ritualista |
| Smith's tools | `strumentidafabbro` | 7 | lv 1–7, values 50 → 1200 |
| Gems | `gemma` / `pietrapreziosa` | 52 / 24 | |
| Practical-use outputs | `portapozioni`, `portapergamene`, `faretra` | 4, 4, 16 | already exist as `Uso pratico` targets |

The altar mana bonus lives **only in `descrizione` as free text** (`"+ 10% mana"`)
— it must be parsed once and moved into a structured field.

### Spells are fully modelled

`SpellDefinition`: **102 rows** across 8 schools (Recupero 14, Evocazione 14,
Negromanzia 13, Illusione 13, Alterazione 13, Misticismo 12, Maledizioni 12,
Distruzione 11), each with `base_mana`, `effect_per_mana`, `minimum_mana`,
`rounding`, `fixed_costs`, and a `legacy_formula` such as `M/4`, `M*2`, `M/8`.

`backend/core/spell_services.py` (326 lines) already converts mana → effect and
handles the Potere/Energia/PA discount economy via `sconto_mana_per_potere`,
`sconto_pa_per_potere`, `ogni_en_x_mana`, `ogni_pa_x_mana`.

**Enchanting is exactly this calculation with a different mana source.** Elder:
*"Ogni livello dell'incantamento permette di castare come se usassi 5 mana"* →
`effective_mana = gem_level × mana_per_level × (1 + altar_bonus)`, then feed
that into the existing spell effect calculator. `Infusore 1..5` raises
`mana_per_level` from 5 to 6…10.

Scroll levels are given directly by the rules as a mana ladder:
`12, 22, 34, 46, 58, 70, 82, 94, 106, 118`.

### Materials and gems are already purchasable

`SettingDefinition` shop types (`backend/core/defaults.py:1955`) already stock
the crafting economy: `armaiolo` sells `lingotto` (rank 3), `generale` sells
`lingotto` (3) and `pergamena` (3) and `gemma` (4), `magia` sells `gemmaanima`
(rank 3) and `pergamena` (1), `alchimista` sells `gemma` (4).

### The diary section exists

`Note.crafting` is already a field (`backend/characters/models.py:403`), already
in the nine-section diary, and already surfaced by the Alchimia payload as
`"notes": character.note.crafting`. Both new tabs read and write the same field.

---

## Engine gaps — what does not exist

### 1. No machine-readable rules on the 79 skills — **the actual project**

This is the prerequisite, and it is authoring work rather than code.
**It requires no new database fields and no schema migration** — see
*How a new rule reaches the engine* below.

Alchimia works because `Alchimista 1` carries:

```json
[{"id": "passivo-legacy-risolto-886", "name": "Alchimista 1",
  "description": "Tutti i reagenti hanno effetto +0,1", "icon": "pozione",
  "operations": [
    {"target": "moltiplicatore_reagenti_livello_1", "operation": "add", "value": "0.1", "condition": ""},
    {"target": "moltiplicatore_reagenti_livello_2", "operation": "add", "value": "0.1", "condition": ""}
  ]}]
```

On unlock, `unlock_skill` (`backend/core/skill_services.py:794`) materialises
accepted passives into `EffettoPersonalizzato` rows and calls
`refresh_personaggio`, which folds them into `Personaggio.tot`.

`Fabbro 3` carries `effetti_passivi: []`. Until it carries operations, no service
can ask "can this character work acciaio?" without regex-ing Italian prose.

#### Two mechanisms are available, and both are already proven in this codebase

There is more than one way to make a skill machine-readable, and the right
answer differs per skill.

**Mechanism A — `effetti_passivi` → `tot` key.** The Alchimia route above. On
unlock, `unlock_skill` materialises the passive into an `EffettoPersonalizzato`
row and `refresh_personaggio` folds it into `Personaggio.tot`. Use this for
**magnitudes**: `mana_per_livello_incantamento`, `max_miglioramenti_base`,
`cariche_percento`. Its real advantage is that the value is not skill-specific —
an item, a race, or a hand-written custom effect can contribute to the same key,
and the service reads one number without caring where it came from.

**Mechanism B — structured rule in `Skill.metadata`.** Already used by
`backend/core/skill_pricing.py:113`, which reads a `pricingModifier` rule off the
skill and applies it:

```python
rule = metadata.get("pricingModifier", {})
if not isinstance(rule, dict) or rule.get("type") != "owned_skill_flat_discount":
    continue
```

Use this for **facts that are purely about the skill** and that nothing else
could ever grant: which material tier a skill unlocks, whether it permits
melting, which improvement it authorises. A `Skill.metadata.forgeRule` block such
as `{"type": "material_unlock", "materials": ["chitina", "acciaio"], "tier": 2}`
is more honest than encoding "tier 2" as a float, because tier unlocks are not
additive and a `tot` float would imply they are.

**Recommended split:** Mechanism A for the ~15 skills that carry a number,
Mechanism B for the ~60 that carry a permission. That is materially less work
than putting all 79 through `effetti_passivi`.

Note that `Specialista armaiolo`'s rule — *"per ogni skill già sbloccata tra
quelle sottostanti, le altre costano -1"* — is exactly the shape
`skill_pricing.py` already executes. Only 4 skills in the whole database
currently carry a `pricingModifier`, and none of them are Fabbro skills, so this
rule is unimplemented today but needs **no new code at all**: writing the
metadata is the entire task.

#### How a new rule reaches the engine — no migration required

This is the answer to "how many new fields on `Personaggio`?": **zero.**

`Personaggio.tot` is a `JSONField` with a callable default
(`default_personaggio_tot`, `backend/characters/models.py:98`) that simply builds
a dict from the `PERSONAGGIO_TOT_KEYS` tuple at the top of the same file. Adding
a total means adding a **string to a Python tuple**. There is no column, so
there is nothing to migrate on `Personaggio`.

The propagation path for one new key:

1. `PERSONAGGIO_TOT_KEYS` — `backend/characters/models.py:6`, for the default dict.
2. `PERSONAGGIO_FLOAT_TOTAL_KEYS` — `backend/core/defaults.py:~860`, so it exists
   in the `Formule_base` profile; add a non-zero base to
   `FORMULE_BASE_VALUE_FLOAT` only if the key needs one
   (`mana_per_livello_incantamento` needs `5`; the rest start at `0`).
3. Nothing else. `get_or_create_global_profile`
   (`backend/characters/services/refresh_personaggio.py:1080-1115`) **already
   self-heals existing profiles**:

```python
for key, value in defaults.get("value_float", {}).items():
    if key not in value_float:
        value_float[key] = value
        changed = True
```

So the live `Formule_base` row picks up new keys on the next refresh, and every
character's `tot` gains them the next time `refresh_personaggio` runs. The 18
proposed keys in §2 cost 18 lines across two Python files and zero schema
changes.

### 2. No `tot` keys for either system

`PERSONAGGIO_FLOAT_TOTAL_KEYS` (`backend/core/defaults.py:~860`) has
`moltiplicatore_reagenti_*` for alchemy and `atk_skill_*`/`def_skill_*` for
combat. Nothing for forging or enchanting. Proposed additions:

**Forge**

| Key | Base | Fed by |
|---|---|---|
| `livello_fabbro_max` | 0 | Fabbro 1–4 → 0,1,2,3; specialist branches → 4..7 |
| `max_miglioramenti_base` | 0 | Potenziato 1–7 → 2..8 (formula subtracts material level) |
| `bonus_miglioramenti_specialista` | 0 | Specialista 1–3 → +1..+3, only on the chosen material |
| `miglioramenti_per_stanchezza` | 0 | Il meglio che posso → 1 |
| `puo_fondere_oggetti` | 0 | Scioglitore |
| `puo_riplasmare` | 0 | Riplasmare |
| `puo_forgiare_ovunque` | 0 | Fucina improvvisata |
| `bonus_base_frecce` | 0 | Fabbricante di frecce → 1 |
| `livello_uso_pratico` | 0 | Uso pratico 1/2 → 1, 2 |

**Enchant**

| Key | Base | Fed by |
|---|---|---|
| `livello_incantamento_max_oggetti` | 0 | Incantatore 1–3 → 1..3; Gioielliere 1–7 → 4..10 |
| `livello_incantamento_max_pergamene` | 0 | Incantatore 1–3 → 1..3; Scriba 1–7 → 4..10 |
| `mana_per_livello_incantamento` | **5** | Infusore 1–5 → 6..10 |
| `cariche_percento` | 0 | Anima compressa 1/2 → 25, 50 |
| `max_incantamenti_per_oggetto` | 1 | Multi Incantamento 1/2 → 2, 3 |
| `puo_reincantare` | 0 | Incantatore Esperto |
| `puo_sommare_gemme` | 0 | Artigiano di anime |
| `puo_disincantare` | 0 | Riciclo di anime |
| `bonus_livello_per_stanchezza` | 0 | Mana e anima → 1 (hard cap 10) |

`PERSONAGGIO_FLOAT_TOTAL_KEYS` is float-only. **`Specialista`'s chosen material
is a string** and cannot live there — put it in `Personaggio.extra`
(`{"fabbro": {"specialistaMateriale": "acciaio"}}`), which is already a free
JSON field, and gate rebinding on the 3-Stanchezza cost.

### 3. No per-instance item state — **the architectural decision**

Every inventory and equipment slot is a `ForeignKey` to a **shared** `Oggetto`
row: `Equip` has ~38 item FKs, `Zaino`/`Faretra` have 50 each via
`ItemSlot50Mixin`, `VoceContenitoreInventario.oggetto` is one more. Today
**5,881 of 5,895 rows are `modello=True` templates**; only 14 legacy imports are
instances.

If two characters both carry `Ascia (ferro)`, they point at the same row. So
improvements, charges and enchantments **cannot** be written onto the template.

Three options:

| Option | Cost | Verdict |
|---|---|---|
| **A. Instance rows** — forging creates a new `Oggetto` with `modello=False, archiviato=True`, improvements written into its `effects` | Low. Works with every existing FK, effect, combat and market path immediately | **Recommended** |
| B. New `OggettoIstanza` model, migrate ~140 FKs | Very high; touches equipment, combat, market, backups, admin | No |
| C. Side table keyed on (Oggetto, Personaggio) | Cheap but wrong — the template is shared, so the join is ambiguous the moment two characters improve the same base item | No |

**Option A is the only one that pays off immediately**, because of the next
finding.

### The decisive fact: instance `effects` need no engine work

`collect_personaggio_effect_payloads`
(`backend/characters/services/refresh_personaggio.py:1141-1151`) already walks
every `Equip` FK and folds each item's `effects` into the totals:

```python
effects = getattr(item, "effects", None)
if effects:
    payloads.append({"source": f"equip.{field_info.name}:{item.nome}", "effects": effects})
```

So a forged `+1 Attacco` written as
`{"target": "attacco", "operation": "add", "value": 1, "source": "forge_improvement"}`
appears on the character sheet, in combat, and in the totals breakdown the moment
the item is equipped — **with no changes to the calculation engine at all.** The
same is true of an enchant.

Instance rows need:
- `nome` is `unique=True` → generate `"{base} #{n}"` or append a short token, and
  keep the display name in `metadata`.
- `archiviato=True` so instances never pollute the catalogue, compendium, or
  market generation. Verify each of those filters on `archiviato` before relying
  on this.
- a `metadata` provenance block:

```json
{"instance": {"kind": "forged", "baseItemId": 1234, "material": "acciaio",
              "materialTier": 2, "forgedBy": 17, "forgedAt": "…",
              "ingotsSpent": 6,
              "improvements": [{"key": "attacco", "stack": 2, "pointsPaid": 3}],
              "improvementPointsTotal": 3}}
```

The ledger must be the source of truth for the doubling rule; `effects` is the
derived projection. Never re-derive the ledger from `effects`.

### 4. Two improvements are table rules — and `regole_speciali` has a side effect

**Resolved.** `Effetto Sanguinamento` and `1 Reroll per turno` have no engine
mechanic (no bleed anywhere in `backend/combat/`; `reroll` exists only as an
accessory `tipo_2` and as prose in `backend/combat/defaults.py:411`). Both are
written into `Oggetto.regole_speciali` on the instance and adjudicated at the
table. That field is the established home for exactly this — **1,659 items
already use it** — and its help text says so: *"Regole leggibili al tavolo per
gli effetti che il sistema non sa calcolare."*

`−1 Peso` writes the instance's `peso` column directly.

**The caveat that matters:** writing `regole_speciali` is not inert.
`sync_special_rules_review` (`backend/core/item_services.py:144`) treats a
non-empty `regole_speciali` as *"the curated rules cover the Elder descriptive
effects"* and stamps `metadata["descriptiveEffectsReviewed"]` with the item's
current descriptive effects. On a forged instance cloned from a template that
still has unreviewed `effetto_N` text, appending a forge rule would silently
mark those Elder texts as reviewed — clearing them out of the curation queue
without anyone having read them.

Fix: the forge service must write `regole_speciali` **without** calling
`sync_special_rules_review`, or must preserve the base template's existing
`descriptiveEffectsReviewed` value verbatim. Add a regression test for this; it
is the kind of bug that is invisible until the review queue is quietly wrong.

### 4b. Forged instances will be flagged `speciale` unless exempted

`backend/core/item_special.py:80` assigns the `non_modello` reason:

```python
if not item.modello:
    reasons.append("non_modello")
```

Since every forged and enchanted instance is `modello=False` by design, **every
crafted item would land in the "needs review" queue** with the hint *"Attiva
'Modello riutilizzabile' … se l'oggetto deve comparire nel catalogo normale"* —
advice that is wrong for an instance. After a few sessions the queue would be
mostly player hammers.

Fix: `special_reasons` must skip `non_modello` when
`metadata["instance"]["kind"]` is set. Add the corresponding entry to
`SPECIAL_REASON_LABELS` only if instances should ever be flagged for a *different*
reason. Cover it in the Slice 1 tests.

### 5. Charges, recharge, and the campaign clock

Elder: *"Gli oggetti incantati si ricaricano automaticamente al 100% ogni giorno"*
and *"Incantare un oggetto richiede un'ora"* / forge time = ingots used.

`DatiCampagna` has a clock (`campaign.clock.update` exists as an action and
`creation_options_payload` reads `giocatore.active_campaign`), but nothing
consumes it for crafting, and there is no charge counter anywhere.

**Decision: charges and crafting time are table rules, tracked manually.**
Both are written into the instance's `regole_speciali` (e.g. *"3 cariche,
ricarica al 100% ogni giorno"*) alongside the ledger, subject to the same
`sync_special_rules_review` caveat in §4. A charge *counter* still lives in
`metadata.instance.charges` so the UI can show it, but nothing decrements it
automatically and nothing consumes the campaign clock in v1.

This matches how Alchimia already ships — its 15/10-minute narrative timers are
not tracked either, and the guide says so plainly. Automatic day-advance
recharge stays as Slice 6, optional.

### 6. `pelle` has no consumable row — **fixed, 1 August 2026**

`Uso pratico 1/2` consumes *"2 unità di pelle"* and *"+2 per livello"*. Elder
tier 1 is *"Ferro, Pelle, Legno"*, but the catalogue only had two of the three:
`Lingotto di ferro` and `Legno per armi`. Leather existed solely as `tipo_2` on
9 finished armour pieces, so the skill had nothing to consume.

Resolved by `backend/core/migrations/0050_seed_leather_crafting_material.py`,
which idempotently seeds:

```
Pelle conciata    tipo_1=lingotto  tipo_2=lingotto  valore=25  peso=1.0  rarità=1
                  metadata: {"seed_kind": "forge_material", "materialKey": "pelle", "materialTier": 1}
```

It sits under `tipo_1='lingotto'` despite not being an ingot, because that is the
type the Mercato already stocks as crafting material (`armaiolo` and `generale`
sell `lingotto` at rank 3) and the type the Forge bench will read stock from.
Value, weight and rarity match the other tier-1 materials. The migration is
reversible and deletes only rows carrying its own `seed_kind`.

Tier 1 is now complete: **Lingotto di ferro (25) · Legno per armi (25) ·
Pelle conciata (25)**, and the `lingotto` type holds 16 rows.

### 7. Ingot rows do not carry a machine-readable material key

A trap worth naming before Slice 2. Materials are `tipo_2` on **finished** items
(`Ascia (ferro)` → `tipo_2='ferro'`), but every ingot row has
`tipo_1='lingotto', tipo_2='lingotto'` — the material lives only in the Italian
name, and three of the sixteen names break the pattern entirely:
`Legno per armi`, `Scheletro di dreugh`, and now `Pelle conciata`.

So ingot → material cannot be derived; it must be an explicit table in
`forge_defaults.py`, keyed by item name or by the `metadata.materialKey` that
migration 0050 establishes. Prefer `materialKey` and backfill it onto the other
15 ingot rows in Slice 2, so the mapping stops depending on names a Master could
rename from the item editor.

`Lingotto massiccio di oro` (rarità 5, weight 6, value 2500) must be excluded by
key, not by type — it is treasure, not a crafting material.

---

## Recommended architecture

Mirror the Alchimia slice exactly. It is the proven pattern in this codebase.

```
backend/core/forge_defaults.py           material catalogue, tiers, ingot costs, improvement menu
backend/core/enchant_defaults.py         gem ladder, altar bonuses, scroll mana ladder, kind catalogue
backend/characters/forge_selectors.py    read model  (mirrors alchemy_selectors.py, 119 lines)
backend/characters/enchant_selectors.py  read model
backend/characters/services/forge.py     calculate_* + @transaction.atomic commands (mirrors alchemy.py, 229 lines)
backend/characters/services/enchant.py   same
backend/characters/services/item_instances.py   shared: create/clone/retire instance rows, rebuild effects from ledger
```

`item_instances.py` is shared infrastructure and must be built **first**, in the
Forge slice, because Enchant depends on it.

### Read-model contract (Forgiatura)

`GET /api/v1/characters/{id}/creation` currently returns only the alchemy payload.
Extend it to a discriminated bench payload, or add sibling routes
`/creation/forge` and `/creation/enchant`. Prefer siblings: the Alchimia payload
is already 120 lines of selector and merging three benches into one response
makes every tab pay for the others.

```jsonc
{
  "character": {"id": 17, "name": "…", "level": 8, "stanchezza": 3},
  "capability": {
    "maxMaterialTier": 3,
    "materials": [{"key": "acciaio", "label": "Acciaio", "tier": 2, "weight": "heavy",
                   "unlocked": true, "unlockedBy": "Fabbro 3", "ingotItemId": 5102}],
    "specialistMaterial": "acciaio",
    "canMelt": true, "canReshape": false, "canForgeAnywhere": false,
    "improvementBudgetFormula": "Potenziato N + 1 − livello materiale",
    "fatigueForExtraPoint": 1
  },
  "tools": {"bestTier": 3, "sourceItem": "Strumenti da Fabbro di livello 3", "portable": false},
  "stock": [{"material": "acciaio", "tier": 2, "itemId": 5102, "quantity": 11,
             "source": "container"}],
  "blueprints": [{"itemId": 812, "name": "Ascia (acciaio)", "category": "armiMedie",
                  "ingots": 4, "hours": 4, "material": "acciaio", "tier": 2,
                  "canForge": true, "blockedReason": ""}],
  "improvableItems": [{"instanceId": 6002, "name": "Ascia (acciaio) #1", "material": "acciaio",
                       "tier": 2, "kind": "weapon", "pointsSpent": 3, "pointsMax": 6,
                       "improvements": [{"key": "attacco", "stack": 2, "nextCost": 4}]}],
  "improvementMenu": {
    "weapon": [{"key": "attacco", "label": "+1 Attacco", "baseCost": 1,
                "apply": {"mode": "effect", "target": "attacco"}},
               {"key": "peso", "label": "−1 Peso", "baseCost": 1,
                "apply": {"mode": "column", "column": "peso", "delta": -1}},
               {"key": "sanguinamento", "label": "Effetto Sanguinamento", "baseCost": 1,
                "apply": {"mode": "tableRule",
                          "text": "Sanguinamento: applica l'effetto a discrezione del Master."}}],
    "armor": [ … ]
  },
  "notes": "…",
  "rules": {"doublingRule": "Ogni ripetizione dello stesso miglioramento raddoppia il costo.",
            "armorResistanceException": "Resistenze diverse non raddoppiano; la stessa sì.",
            "chainmailAndRobesCannotBeImproved": true}
}
```

### Command contract

New `Literal` action schemas in `backend/api_v1/schemas.py` (follow
`AlchemyBrewActionSchema` at line 1896) and branches in the `elif` chain in
`backend/api_v1/api.py` (follow `alchemy.brew` at line 1299). Every command
returns the refreshed bench payload so the client can
`queryClient.setQueryData` without a refetch, exactly as Alchimia does.

**Forgiatura**

| Action | Payload | Effect |
|---|---|---|
| `forge.craft` | `characterId, blueprintItemId, materialKey, quantity` | validate tier ≤ `livello_fabbro_max`, tools present, ingots in stock → consume ingots, create instance, place in Zaino |
| `forge.improve` | `characterId, instanceId, improvementKey, useFatigue` | validate budget and doubling cost → consume ingots (1 per point), append to ledger, rebuild `effects` |
| `forge.melt` | `characterId, instanceId` | requires `puo_fondere_oggetti` → destroy instance, return ingots |
| `forge.reshape` | `characterId, instanceId, newMaterialKey` | requires `puo_riplasmare` → swap material, carry improvement points |
| `forge.setSpecialist` | `characterId, materialKey` | costs 3 Stanchezza after the first binding |
| `forge.craftPractical` | `characterId, kind, level` | Uso pratico; blocked until leather exists |

**Incantamento**

| Action | Payload | Effect |
|---|---|---|
| `enchant.item` | `characterId, targetInstanceId, gemItemIds[], kind, altarItemId` | resolve level from gem(s), validate against `livello_incantamento_max_oggetti` and `max_incantamenti_per_oggetto` → consume gems, look up `(slot, kind, level)`, merge that row's `effects` into the instance, set charges |
| `enchant.scroll` | `characterId, spellId, manaSpent, altarItemId` | scroll effect is **half** the impressed spell; level from the mana ladder |
| `enchant.disenchant` | `characterId, instanceId, gemItemId` | requires `puo_disincantare`, costs 1 Stanchezza |
| `enchant.recharge` | `characterId, instanceId` | manual in v1 |
| `enchant.boostLevel` | `characterId, instanceId` | Mana e anima: 1 Stanchezza, +1 level, max +1, cap 10 |

Validation must be server-side and total. The client computes a **preview only** —
mirror `projectedBrew` in `frontend/src/features/creation/mechanics.ts`, and
mirror `calculate_brew` as a pure, separately-testable backend function so preview
and commit cannot drift.

---

## Frontend structure

`CreationPage.tsx` keeps its three top-level tabs. Each new bench gets sub-tabs,
because both systems have genuinely distinct modes.

### Tab 02 · Forgiatura

| Sub-tab | Purpose |
|---|---|
| **Fucina** | Blueprint picker filtered to unlocked tiers; material selector showing ingot stock; ingot cost and forge hours; "Forgia" button. Locked materials stay visible and greyed with the skill that unlocks them — the Alchimia stock matrix does exactly this. |
| **Miglioramenti** | Pick an owned instance → point budget meter (`spent / max`, where max = `Potenziato N + 1 − tier + specialista`) → improvement menu with the **doubling cost shown live** (1 → 2 → 4 → 8) → table-rule improvements (Sanguinamento, Reroll) rendered with a "regola da tavolo" badge showing the text that will be written to `regole_speciali`. Chainmail and vesti render a disabled panel with the rule text. |
| **Fusione e riplasmatura** | Melt (Scioglitore) and reshape (Riplasmare); both hidden unless the capability flag is set. |
| **Uso pratico** | Quivers, potion/scroll holders, cloaks, consuming `Pelle conciata` (2 units at level 1, +2 per level). Unblocked by migration 0050. |

The budget formula must be visible, not just its result. Alchimia's
`alchemy-formula-card` (`somma livelli × (set + abilità) = potenza`) is the
precedent: show `Potenziato 4 (5) − Acciaio (2) + Specialista (1) = 4 punti`.

### Tab 03 · Incantamento

| Sub-tab | Purpose |
|---|---|
| **Altare** | Altar picker (owned or campaign) showing the mana bonus; gem inventory by level, empty vs full; effective-mana readout `livello × mana/livello × (1 + bonus altare)`. |
| **Incanta oggetto** | Target picker (jewellery, bands, cloaks — **not** weapons/armour per the rules, except the impact-enchant skills) → effect kind → level from gem → resolved catalogue item preview with its real `effects` and charge count. |
| **Pergamene** | Spell picker from known spells → mana to impress → the scroll casts at **half** → level resolved against `12/22/34/46/58/70/82/94/106/118`. |
| **Cariche** | Enchanted items, charges remaining, manual recharge, disenchant. |

Both benches must read and write `Note.crafting` in a footer panel, the way the
Alchimia payload already exposes `notes`.

Styling: extend `frontend/src/styles/app.css`, which already carries the
`alchemy-*`, `creation-tabs` and `creation-roadmap-panel` classes. Reuse
`alchemy-stock-matrix` for the ingot grid and `alchemy-formula-card` for the
budget and mana readouts — the visual language should say "same laboratory".

Regenerate `frontend/src/lib/generated/api.ts` from the OpenAPI schema and add
type aliases in `frontend/src/lib/types.ts` next to the three `Alchemy*` ones at
lines 21–23.

---

## Testing

Follow `backend/characters/tests.py`, which already covers the alchemy slice.

**Forge**
- Tier gate: a character with `Fabbro 3` can forge acciaio and cannot forge elfico.
- Ingot consumption per category: 3/4/6/5/2, arrows 5 per ingot.
- Doubling: three stacks of `+1 Attacco` cost 1, 2, 4 → total 7.
- Armour resistance exception: two *different* resistances cost 1+1, the *same*
  one twice costs 1+2.
- Budget: `Potenziato 3` (max 4) on a tier-2 material yields 2 points, +1 with
  `Specialista` bound to that material, +1 more for 1 Stanchezza.
- Chainmail and vesti reject every improvement.
- Rollback: a failed improve leaves ingots, ledger and `effects` untouched.
- Instance `effects` reach `Personaggio.tot` after equipping (the integration
  test that proves §3 — assert `tot["attacco"]` moves).
- Melt and reshape are refused without the skill.
- `−1 Peso` moves the instance's `peso` from 4.0 to 3.0 and **does not** touch
  the base template's `peso`.
- A forged instance is **not** flagged `speciale` for `non_modello` (§4b).
- Writing a table rule into `regole_speciali` does not alter the instance's
  `metadata["descriptiveEffectsReviewed"]` (§4).
- `Uso pratico 1` consumes exactly 2 `Pelle conciata` and refuses at 1.

**Enchant**
- Level cap: `Incantatore 2` cannot use a level-3 gem.
- `Infusore 3` makes a level-4 enchant worth 32 mana, not 20.
- Altar bonus applies multiplicatively and is read from structured data, not prose.
- Charges = gem level, `Anima compressa 2` gives +50%.
- `Multi Incantamento 1` allows a second effect with independent charges and
  refuses a third.
- Scroll effect is exactly half the impressed spell.
- Catalogue lookup `(slot, kind, level)` resolves for every unlocked kind, and
  `*_extra` kinds correctly report levels 1–2 as unavailable.

**Frontend** — extend `frontend/tests/quick-tools.spec.ts`; assert the doubling
cost renders, and that a locked material shows its unlocking skill.

---

## Delivery order

**Slice 0 — skill authoring (prerequisite, no UI).**
Add the `tot` keys from §2 to `PERSONAGGIO_TOT_KEYS` and
`PERSONAGGIO_FLOAT_TOTAL_KEYS` (two Python files, no schema migration). Write the
idempotent data migration in the style of `race_skill_sync.py`: `effetti_passivi`
for the ~15 numeric skills, `Skill.metadata` rules for the ~60 gating ones. Test
that unlocking `Fabbro 3` makes acciaio forgeable and that unlocking `Infusore 3`
moves `tot["mana_per_livello_incantamento"]` to 8.
**Nothing else can start before this lands.**

**Slice 1 — item instances.**
`item_instances.py`: create, name uniquely, archive from catalogue listings,
ledger→`effects` projection, retire. Three integration points must be handled
here, not later:
- exempt instances from the `non_modello` reason in `item_special.py` (§4b);
- write `regole_speciali` without tripping `sync_special_rules_review` (§4);
- verify every catalogue, compendium and market query filters on `archiviato`.

This is the riskiest slice; it touches shared read paths.

**Slice 2 — Forgiatura: Fucina.**
Material catalogue, blueprint list, ingot consumption, instance creation.
Ship the tab with only the first sub-tab live.

**Slice 3 — Forgiatura: Miglioramenti.**
Doubling ledger, budget meter, the 11 supported improvements, honest badges on
the 3 unsupported ones. Forgiatura is now a complete vertical slice.

**Slice 4 — Incantamento: altar, gems, item enchanting.**
Reuses `item_instances.py` and `spell_services.py`.

**Slice 5 — Pergamene and cariche.**
Scroll authoring, charge tracking, manual recharge, disenchant.

**Slice 6 — clock integration.**
Forge hours and enchant hours consume campaign time; daily automatic recharge.

Slices 2 and 3 together are the minimum shippable Forgiatura. Slices 4 and 5
together are the minimum shippable Incantamento.

---

## Documentation to update when each slice lands

- `backend/core/guides_it.py:788-806` — the `_RULE_STATUS_NOTES` entries
  currently say `"missing"` for `Incantamento`, `Incantare Oggetti`,
  `Forgiatura`, `Creazione degli Oggetti`, `Miglioramento degli Oggetti`,
  `Cumulare Miglioramenti`, and `"partial"` for
  `ALCHIMIA, INCANTAMENTO E FORGIATURA` and `Materiali e Livelli`. Every one of
  these is a promise to the reader; move each to `"partial"` or `"implemented"`
  **in the same commit** that makes it true, and name the differences.
- `Builder_docs/CONVERSION_MATRIX.md:39` — "Forgiatura and Incantamento staged".
- `README.md`.
- `CreationPage.tsx:255-256` — the `<small>In ricostruzione</small>` tab labels.
- Delete `EmptyWorkshop` when the second bench lands.

---

## Decisions taken

Settled 1 August 2026; recorded so the slices do not reopen them.

- **Item instances.** Forging and enchanting clone the base template into a new
  `Oggetto` row (`modello=False`, `archiviato=True`) carrying the ledger in
  `metadata` and the results in `effects`. *"Aldric's hammer, cloned from
  Martello (ferro), then modified freely."*
- **Unsupported improvements.** Sanguinamento and Reroll consume points and are
  written into `regole_speciali` as table rules. Not cut, not faked.
- **−1 Peso.** Direct write to the instance's `peso` column.
- **Charges and crafting time.** Table rules in `regole_speciali`, tracked
  manually. No clock consumption in v1.
- **Leather.** Seeded as `Pelle conciata` under `tipo_1='lingotto'` by migration
  0050. Done.
- **New `Personaggio` fields.** None. `tot` is a JSON field driven by a Python
  tuple; the `Formule_base` profile self-heals.

## Open questions for the Master

Game-design calls that still change the data model. Answer before the slice
that needs them.

1. **Instance proliferation** *(before Slice 1)*. Every forged item becomes a
   row. Acceptable indefinitely, or should instances be garbage-collected when
   the owning character is archived?
2. **Weapon enchants** *(before Slice 4)*. The rules say *"Normalmente si
   incantano solo gioielli, fasce, mantelli… non armi, armature"*, but
   `Danno da impatto`, `Paralisi da impatto` and `Assorbi Anima` explicitly
   enchant weapons. Are those the only exceptions?
3. **Altar ownership** *(before Slice 4)*. Carried item (portable variants exist
   at 2× price) or campaign fixture? Decides whether the selector reads
   `Equip`/`Zaino` or `ContenitoreInventario` at campaign scope.
4. **Collaboration** *(before Slice 3)*. `Uso pratico magico` and magic bags
   require *"insieme a un incantatore"*. Is a two-character crafting action in
   scope, or adjudicated at the table?
5. **`Artigiano di anime` harmonic sum** *(before Slice 4)*. `1 + 1/2 + 1/3 …` —
   round down, or keep fractional levels?

# Shop creation guide for a small/cheap LLM

## Mission

Create new ReDjango shops from:

```text
redjango/reference/Elenco_negozi_Elder_Django.xlsx
```

The workbook supplies the required region, locality, shop type, and level for each
shop slot. Create new shop names, owner names, and short descriptions. Do not copy
the old names or owners.

This is a content migration, not a database migration. The Elder database is a
read-only reference and must never be modified.

## Non-negotiable rules

1. Preserve every row's region, locality, shop type, and level.
2. Never invent a location key or shop-type key. Resolve labels against the current
   Mercato configuration.
3. Shop and owner names must fit The Elder Scrolls setting and the locality.
4. Do not use joke names, puns, meme references, modern brands, or generic D&D names.
5. Do not reduce a culture to one cliché.
6. Do not repeat shop names within a locality.
7. Do not repeat an owner name anywhere in the completed plan.
8. Do not use a famous canonical NPC's full name unless the campaign data explicitly
   requires that NPC.
9. Do not write directly to SQLite and do not use `Negozio.objects.create()`.
   Creation must go through `backend.market.services.save_shop`.
10. Do not perform the full database write without an explicit dry-run report and
    user confirmation.

If any row cannot satisfy these rules, mark it `needs_review` instead of guessing.

## Files to read before working

Read these files in this order:

```text
redjango/SHOP_CREATION_LLM_GUIDE.md
redjango/MERCATO_IMPLEMENTATION_GUIDE.md
redjango/reference/Elenco_negozi_Elder_Django.xlsx
backend/market/config.py
backend/market/services.py
backend/market/selectors.py
backend/core/models.py
```

Use the spreadsheet skill when reading or updating the workbook. Preserve its
formatting, tables, filters, formulas, and yellow editable columns.

Do not assume that this guide's examples override the live configuration. The
current values returned by `get_market_locations()` and
`get_shop_type_definitions()` are authoritative.

## Meaning of the workbook

The `Elenco negozi` sheet contains one shop slot per row:

```text
ID piano
Regione
Località
Tipo negozio
Livello
Nuovo nome
Nuovo proprietario
Note
```

The first five columns are source facts. Do not change them.

The last three columns are editable:

- `Nuovo nome`: the new shop name;
- `Nuovo proprietario`: the owner or principal keeper;
- `Note`: a compact creation note or `needs_review: <reason>`.

There are 1,850 rows. Work in small batches. Never ask one model call to invent all
1,850 shops.

## Stable shop-type mapping

Resolve the live configuration first. The expected mapping is:

| Workbook label | Current stable key |
|---|---|
| Emporio generale | `generale` |
| Fabbro | `fabbro` |
| Armaiolo | `armaiolo` |
| Fabbricante di armi | `fabbricante-armi` |
| Arcieria | `arcieria` |
| Alchimista | `alchimista` |
| Oggetti magici | `oggetti-magici` |
| Abbigliamento | `abbigliamento` |
| Contenitori | `contenitori` |
| Taverna | `taverna` |
| Carovana Khajiit | `carovana-khajiit` |

If the live configuration disagrees, use the live configuration and report the
difference.

## Required batching strategy

Use batches of 12–25 rows.

Prefer one locality per batch. If a locality has more than 25 rows, split it while
keeping a shared locality ledger. Do not mix distant regions merely to fill a batch.

For every batch:

1. Read the rows.
2. Load the global owner-name and shop-name ledgers produced by earlier batches.
3. Inspect other shops in the same locality.
4. Generate candidates.
5. Run the mechanical validation checks.
6. Run the lore and prose review.
7. Repair failed rows once.
8. Mark unresolved rows `needs_review`.
9. Save the approved planning data.
10. Do not create database rows yet.

The content plan should be complete and reviewed before bulk creation begins.

## Naming philosophy

Names should sound as if they grew out of a place, trade, family, civic institution,
or local event. They should not sound as if they came from a generic fantasy-name
button.

### Good sources for a shop name

Vary these constructions:

- a local street, gate, canal, hill, dock, shrine, market, quarry, or district;
- a craft process, tool, material, finish, scent, sound, or working method;
- a founder, family, guild predecessor, inherited lease, or old civic office;
- a restrained historical or religious reference appropriate to the locality;
- a practical promise or reputation known to customers;
- a culturally plausible metaphor whose meaning is clear from the description.

Examples of useful *structures*, not names to copy:

```text
<local landmark> + <trade association>
<family or founder> + <workshop form>
<craft process> + <house/stall/rooms>
<civic or temple relation> + <practical noun>
<material or finish> + <specific trade object>
```

Do not force the shop type into every name. A blacksmith does not always need
`Forge`, an alchemist does not always need `Potion`, and a tavern does not always
need `Inn`.

### Weak patterns to avoid

Reject or rewrite:

- random adjective + random animal;
- `The Drunken <anything>`;
- `The Prancing <animal>`;
- `Dragon's Rest`, `The Golden Tankard`, `The Silver Sword`, and close imitations;
- repeated `Moon`, `Shadow`, `Dragon`, `Golden`, `Silver`, `Rusty`, or `Wandering`
  motifs without a specific local reason;
- alliterative names created only because they sound catchy;
- names that merely repeat the location and category;
- names that differ only by a number, color, or adjective;
- shop names copied from famous fantasy franchises;
- modern jokes, corporate language, or internet slang.

A familiar word is not globally banned. It is rejected when it is generic,
unmotivated, or repeatedly used as a shortcut.

## Owner-name rules

The owner is a person, not a shop mascot.

- Use culturally plausible morphology for the owner.
- Keep full owner names globally unique.
- Do not use the shop name as the owner's surname by default.
- Do not give every owner a profession-based surname.
- Do not make every owner a member of the region's majority culture.
- Cosmopolitan cities should contain plausible migrants and mixed communities.
- Do not turn minority cultures into comic relief, criminals, mystics, or exotic
  decoration.
- Use titles, particles, apostrophes, clan forms, and honorifics only when their form
  is understood. When uncertain, choose a simpler valid form.
- Avoid famous canonical full names and near-copies.

## Regional lore guidance

This is a naming direction, not a demand that every resident match the region.

| Region | Primary naming direction | Do not reduce it to |
|---|---|---|
| Skyrim | Nordic/Nord forms; old farms, holds, trades, family lines | mead, snow, axes, and shouting |
| Cyrodiil | Imperial/Roman-influenced forms; civic, mercantile, temple, legion history | every owner being a pompous senator |
| High Rock | Breton forms; local dynasties, guilds, ports, estates, scholarship | generic French words or fairy clichés |
| Hammerfell | Redguard forms; ports, lineages, sword traditions, scholarship, desert and coastal trade | every person being a warrior or desert mystic |
| Morrowind | Dunmer forms; Great House, temple, ashland, craft and mercantile contexts where appropriate | ash, ancestors, and hostility in every name |
| Summerset Isles | Altmer forms; lineage, craft precision, academies, estates, maritime settings | arrogance and magical superiority |
| Valenwood | Bosmer forms; settlements, paths, living landscapes and practical local craft | every shop being a tree pun |
| Elsweyr | Khajiit forms; caravan, city, clan and local landscape contexts | thieves, moon-sugar jokes, or excessive apostrophes |
| Black Marsh | Argonian and local Tamrielic forms; river, city, clan, craft and migrant communities | swamp jokes, hissing names, or every owner being Argonian |
| Altro | Infer culture from the locality or campaign material | guessing a culture from the shop type |

Search local campaign and lore material before inventing a very specific historical
claim. If the repo contains no support, write a locally plausible name without
asserting detailed canon.

## Diversity limits

Apply these limits independently to each locality:

- no exact shop-name duplicate;
- no normalized near-duplicate;
- no single naming construction for more than 35% of the locality;
- no shop-type noun in more than 50% of that type's names;
- no location name embedded in more than 25% of its shop names;
- no repeated leading content word more than twice, excluding articles and
  prepositions;
- no more than two consecutive shops with owners from the same naming tradition
  when the locality is plausibly cosmopolitan.

Across the global plan:

- owner full names are unique;
- repeated surnames require an intentional family relation in `Note`;
- repeated shop names in different localities are discouraged and must be below 1%;
- do not reuse the same description sentence structure mechanically.

Normalize comparisons by lowercasing, removing punctuation/diacritics, collapsing
spaces, and ignoring initial articles such as `The`, `Il`, `La`, and `L'`.

## Description rules

Create a 20–45 word description for the eventual JSON plan, even though the workbook
only needs a short note.

A description should contain:

1. one concrete physical or operational detail;
2. one detail about reputation, clientele, sourcing, or service;
3. no unsupported major lore event.

Do not write:

- `a cozy shop run by a friendly owner`;
- `the best goods at the best prices`;
- a biography of the owner;
- a list of generated stock;
- exaggerated claims repeated for every shop.

## Candidate-generation contract

For each input row, generate three candidate pairs internally. Select one only after
checking it against the ledgers.

Use this internal shape:

```json
{
  "planId": 217,
  "region": "High Rock",
  "location": "Daggerfall",
  "shopTypeLabel": "Fabbro",
  "shopTypeKey": "fabbro",
  "level": 4,
  "candidates": [
    {
      "shopName": "...",
      "ownerName": "...",
      "description": "...",
      "namingPattern": "local-landmark-and-craft",
      "ownerTradition": "Breton"
    }
  ]
}
```

Do not expose discarded candidates to the database-import stage.

The approved plan record is:

```json
{
  "planId": 217,
  "locationKey": "high-rock/daggerfall",
  "categoryKey": "fabbro",
  "level": 4,
  "name": "Approved in-lore name",
  "owner": "Approved in-lore owner",
  "description": "Twenty to forty-five words.",
  "seed": "elder-plan-0217",
  "status": "approved"
}
```

The seed must be `elder-plan-` plus the zero-padded workbook ID. This makes stock
generation reproducible.

## Mechanical validation

Reject a record when any of these checks fails:

```text
name is blank or longer than 180 characters
owner is blank or longer than 180 characters
description is blank
level differs from the workbook
location label cannot be resolved to exactly one enabled locationKey
shop type cannot be resolved to exactly one enabled categoryKey
shop name duplicates another shop in the same locality
owner full name already exists in the plan
name contains a banned modern/joke reference
status is not approved or needs_review
```

Also emit warnings for:

```text
same important shop-name token used repeatedly in the locality
same namingPattern over the 35% locality limit
same ownerTradition used mechanically
shop name is too close to location + category
description begins with a phrase already used in the batch
```

Warnings require a review; errors block creation.

## Lore-quality scoring

Score each approved candidate from 0 to 2 on five dimensions:

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Local fit | generic/contradictory | broadly plausible | tied naturally to locality |
| Cultural plausibility | caricature/incorrect | safe but generic | plausible and restrained |
| Distinctiveness | duplicate/cliché | acceptable | memorable without gimmicks |
| Shop relevance | unrelated | category is understandable | trade is implied naturally |
| Prose quality | silly/redundant | clear | concise and specific |

The total must be at least 8/10. No dimension may score 0.

Do not inflate the score to pass a weak candidate. Rewrite it.

## Plan review report

After every locality, report:

```text
locality
rows processed
approved
needs_review
duplicate names found
duplicate owners found
naming-pattern distribution
owner-tradition distribution
most repeated content words
unresolved location/type mappings
```

After the full planning phase, report the same information globally and list every
`needs_review` row.

## Database creation workflow

### Phase 1: dry run

Create an idempotent management command or equivalent reviewed service wrapper.
The default mode must be dry-run.

It must:

1. read the approved JSON plan;
2. validate every row again;
3. resolve the live location and category configuration;
4. detect existing shops;
5. calculate counts without writing;
6. print created/skipped/conflict/invalid totals;
7. exit non-zero when errors exist.

Do not treat the workbook as a direct database payload. Convert reviewed content to
JSON first so changes are diffable and auditable.

### Phase 2: pilot

After the dry-run report is clean and the user confirms:

1. back up `db.sqlite3` into `backups/` with a timestamp;
2. apply one locality or at most 25 shops;
3. generate stock using the deterministic seed;
4. inspect the Mercato UI and backend selector payload;
5. report results and request confirmation before the full import.

### Phase 3: staged apply

After pilot approval, apply batches of at most 25 shops in an outer
`transaction.atomic()` block.

For each record, call:

```python
save_shop(
    user,
    giocatore,
    {
        "name": record["name"],
        "owner": record["owner"],
        "locationKey": record["locationKey"],
        "categoryKey": record["categoryKey"],
        "level": record["level"],
        "description": record["description"],
        "seed": record["seed"],
        "generateStock": True,
        "featured": False,
        "priceModifierPercent": 0,
    },
)
```

Import:

```python
from backend.market.services import save_shop
```

Use an authenticated Admin or Master and its matching `Giocatore`. Do not bypass
`require_game_manager`.

### Idempotency

Before creation, look for a shop with the same normalized name and `location_key`.

- If name, owner, category, level, and description all match, mark it `skipped`.
- If the name/location exists but any field differs, mark it `conflict`.
- Never update or overwrite a conflict automatically.
- Never use a different generated name merely to make a rerun pass.

Write a batch receipt containing plan IDs and created database IDs. Receipts must be
saved before moving to the next batch.

### Failure behavior

If one record in a batch fails:

- roll back the entire batch;
- report the failing plan ID and structured error;
- fix the content or mapping;
- rerun the dry-run;
- do not continue with later batches.

## Post-creation checks

After each batch, verify:

- the database count increased by the expected amount;
- every created shop has the correct location, category, and level;
- every shop has a non-empty owner and description;
- every shop has version-2 stock, a deterministic seed, and `stock_revision >= 1`;
- no shop has zero distinct stock without a reported generator warning;
- the Mercato groups shops under the expected region and locality;
- selecting a shop exposes purchasable item rows;
- no browser console errors occur.

After the full run:

```text
python manage.py check
python manage.py test backend.market
npm.cmd run typecheck
npm.cmd run test
npm.cmd run build
```

Do not claim success merely because rows exist.

## Ready-to-use prompt for the content-generation pass

Use the following as the task prompt for each batch:

```text
You are creating new ReDjango Mercato content from a reviewed Elder shop-slot list.
Follow redjango/SHOP_CREATION_LLM_GUIDE.md exactly.

Work only on the supplied batch. Preserve plan ID, region, locality, shop type, and
level. Create an original in-lore shop name, globally unique owner name, and a
20–45-word description for every row.

Names must be culturally plausible but not stereotyped. Avoid jokes, generic fantasy
generator phrases, repeated adjective-animal constructions, famous canonical NPC
names, and mechanical reuse of the location or category. Treat cities as socially
mixed rather than culturally uniform.

Generate three internal candidates per row, validate them against the supplied global
and locality ledgers, and output only the selected approved record. Use status
needs_review instead of guessing. Apply the scoring rubric; every approved record
must score at least 8/10 with no zero dimension.

Do not write to the database. Return:
1. approved JSON records;
2. needs_review records with reasons;
3. the locality review report;
4. updated normalized name and owner ledgers.
```

## Ready-to-use prompt for the import pass

```text
You are applying an already reviewed ReDjango shop plan.
Follow redjango/SHOP_CREATION_LLM_GUIDE.md exactly.

Do not generate or rewrite names. Do not modify the Elder database. Do not write
directly with the ORM. Validate the approved JSON against the current Mercato
configuration and use backend.market.services.save_shop.

Start with a dry-run. Report all mappings, duplicates, conflicts, and invalid rows.
Stop if any error exists. Ask for confirmation before the pilot write and again
before the staged full apply. Use batches of at most 25, atomic rollback, deterministic
seeds, database backup, and batch receipts.
```

## Definition of done

The task is complete only when:

- all workbook rows are approved or explicitly listed as `needs_review`;
- shop and owner names pass uniqueness and diversity checks;
- lore review finds no caricatures, joke names, or unsupported canonical claims;
- the dry-run has zero errors;
- the user approved the pilot and full apply;
- every applied batch has a receipt;
- every created shop has working generated stock;
- backend, frontend, and browser checks pass;
- the Elder database remains unchanged.

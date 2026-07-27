# Mercato: analysis and implementation guide

## Goal

Rebuild the useful parts of The Elder Django's Mercato in ReDjango without creating
`Regione` or `Citta` database models just to support shops.

The recommended result is:

- `Negozio` remains the only persistent market entity.
- Regions and places are a validated, admin-managed picklist stored in the existing
  `SettingDefinition` game-parameter system.
- Shop types and generation rules are configurable through the same mechanism.
- Game masters can create one or several shops from a compact quick-create form.
- Stock generation remains reproducible and is implemented as a tested backend service.
- The normal Mercato UI is a route inside the existing React SPA.
- A real purchase workflow is a separate, atomic phase; it must not copy the legacy
  client-only checkout.

This design meets the location requirement without introducing world-location tables.
If regions and places later become first-class campaign/lore/map concepts, they can be
promoted into a shared world model then. The Mercato should not force that decision now.

## What the Elder Mercato actually does

### Persistence and navigation

The legacy implementation uses three models in
`the_elder_django/django_slim/models.py`:

- `Regione`: name plus a JSON list of city names.
- `Citta`: unique name plus a JSON list of shop names.
- `Negozio`: name, owner, category, level, background, JSON inventory, description,
  and a string `luogo`.

The relationships are therefore not real foreign keys. They are duplicated name-based
references:

```text
Regione.lista_citta -> Citta.nome
Citta.lista_negozi  -> Negozio.nome
Negozio.luogo       -> Citta.nome
```

The page loads regions, then cities, then shops, then a shop's stock through separate
legacy endpoints. The UI supports:

- region and city navigation;
- filtering shops by category;
- generated or cached stock;
- item search, type and price filtering, and sorting;
- an item detail panel;
- a cart and a manual percentage price modifier;
- random shop generation by region, type, level, and optional seed;
- creation of a custom shop under the special `Altro` region;
- hidden regeneration by clicking the same shop four times.

The relevant source files are:

```text
the_elder_django/django_slim/negozio.py
the_elder_django/django_slim/views.py
the_elder_django/django_slim/recupera_dati.py
the_elder_django/django_slim/templates/negozio.html
the_elder_django/django_slim/static/negozio_core.js
the_elder_django/django_slim/static/negozio_ui.js
```

### Generator rules worth preserving

The useful domain behavior is in `django_slim/negozio.py`.

1. Eleven shop categories have inventory-size multipliers.
2. A large item-type/shop-type matrix ranks item types from `0` to `5`.
   Rank `0` is most common and rank `5` is excluded.
3. The legacy rank-to-weight function is:

   ```text
   weight = 2.5 ^ (4 - rank)
   ```

4. Approximate inventory size is:

   ```text
   base = 25 + (shop_level * 5.5)
   target = base * shop_type_multiplier * 1.55
   final count = random value between 75% and 125% of target
   ```

5. Rarity rolls generate tiers `1..4` with probabilities `70%`, `15%`, `10%`,
   and `5%`.
6. Less suitable item types reduce the requested item level. If no item exists,
   the generator tries nearby levels in this order:

   ```text
   0, -1, +1, -2, +2, -3, +3
   ```

7. `Oggetto.regione` and `Oggetto.peso_regione` bias regional item selection.
8. No generated item appears more than five times.
9. Taverns add rooms, baths, stables, food, and drinks according to shop level.
   General shops and Khajiit caravans add some beverages.
10. Display price is calculated client-side:

    ```text
    round(item.value * (75 + 5 * shop_level) / 100)
    ```

These rules are useful as an initial compatibility preset. They should be moved into
configuration and services, not copied as a module-level global table mixed with
database access.

### Legacy data observed

The current Elder database contains:

- 10 regions;
- 118 city rows;
- 1,850 shops;
- 11 shop categories;
- shop levels from 1 to 10.

The configuration is not internally perfect:

- region JSON refers to 119 distinct place names, but two have no `Citta` row;
- one `Citta` row named `Altro` is not referenced by a region;
- one shop uses a location absent from the configured region lists;
- there is at least one duplicate shop name/category/location combination;
- 1,835 shops have `lista_oggetti` as an empty JSON list;
- only 15 shops currently have the later `{"items": [...]}` cache shape.

The empty-list/cache behavior is accidental. The loader calls `.get()` on the JSON
value; an empty list raises `AttributeError`, which triggers generation and replaces
the list with a dictionary. ReDjango must use one explicit, versioned stock shape.

### Legacy behavior not to preserve

- Seeding calls `random.seed()` globally and can affect unrelated random behavior.
- Regions are hardcoded both in the database and in HTML.
- Links between region, city, and shop are mutable display names.
- Inventory stores item names instead of stable ReDjango item IDs.
- Repeated database queries are made inside the generation loop.
- Empty stock has two incompatible JSON shapes.
- The four-click regeneration gesture is undiscoverable.
- Endpoint validation and permissions are weak.
- Checkout only shows an alert telling the user to remove coins manually. It does not
  subtract coins, add items to the character, or decrement shop stock.

## ReDjango starting point

ReDjango already has most of the required foundation:

- `backend/core/models.py` already contains `Negozio`.
- It deliberately stores `regione_nome` and `citta_nome` as strings and has no
  `Regione` or `Citta` model.
- `Oggetto` already has `tipo_1..tipo_4`, `rarita`, `lv_loot`, `regione_loot`,
  `peso_regione`, `valore`, and imported Elder provenance.
- The current database contains the full imported item catalog, so the generator can
  be built against ReDjango item IDs.
- `SettingDefinition` already supports JSON game parameters editable in Django Admin.
- The seed command preserves an administrator's current `value`.
- The application has role checks, a shared action envelope, Django Ninja/OpenAPI,
  generated TypeScript types, TanStack Query, and management workstations.

What is currently missing:

- market settings and validation;
- dedicated selectors and services;
- typed market endpoints/actions;
- a proper `NegozioAdmin`;
- a shop-management workstation;
- the player-facing Mercato route;
- shop import and reconciliation;
- tests.

`Negozio` currently has no rows in the ReDjango database, so this is a good point to
make the stock contract explicit before importing legacy shops.

## Recommended location configuration

### Do not create location models

Create an admin-managed JSON setting with the stable key:

```text
mercato.locations
```

Use `value_type="json"`, `minimum_role="admin"`, and disable player/master overrides.
Add it to `ADMIN_MANAGED_SETTING_KEYS` so it never appears as a personal preference.
The sanitized location options needed by the Mercato should be returned by the
dedicated market selector, not by the generic Settings screen.

Use stable keys independently from labels:

```json
{
  "version": 1,
  "regions": [
    {
      "key": "skyrim",
      "label": "Skyrim",
      "enabled": true,
      "places": [
        {"key": "whiterun", "label": "Whiterun", "enabled": true},
        {"key": "riften", "label": "Riften", "enabled": true}
      ]
    },
    {
      "key": "cyrodiil",
      "label": "Cyrodiil",
      "enabled": true,
      "places": [
        {
          "key": "imperial-city-arena",
          "label": "Città Imperiale — Arena",
          "enabled": true,
          "aliases": ["Città Imperiale-Arena"]
        }
      ]
    }
  ]
}
```

Rules:

- keys are lowercase slugs and never change after use;
- labels may be renamed;
- disabling is preferred to deleting;
- keys must be unique within their scope;
- a place belongs to exactly one region in this configuration;
- aliases are import aids, not values shown in new forms;
- configuration is global for the first slice, not campaign-specific.

Add a second admin-managed JSON setting:

```text
mercato.shop_types
```

It should contain category key, label, enabled status, default background, inventory
multiplier, and the item-type ranks used by the generator. This replaces both the
hardcoded HTML options and the two large Python dictionaries.

Put general numeric behavior in:

```text
mercato.generator_rules
```

This setting owns level bounds, count formula, count variance, rarity probabilities,
fallback level deltas, maximum copies, and pricing coefficients.

Keeping these three settings separate lets an administrator safely edit the common
location picklist without touching the large generation matrix.

### Validate configuration centrally

The existing JSON setting validation accepts any JSON value. Add
`backend/core/market_config.py` with:

```text
get_market_locations()
get_shop_type_definitions()
get_generator_rules()
validate_market_locations(value)
validate_shop_types(value)
validate_generator_rules(value)
resolve_location(location_key)
```

The functions should normalize values and raise clear `ValidationError`/`ApiError`
messages for duplicate keys, missing labels, invalid ranks, invalid probabilities,
and places without a region.

Use the same validators in:

- the Django Admin form for `SettingDefinition`;
- market selectors;
- quick-create and update services;
- seed/import validation tests.

Never let each caller parse the JSON independently.

## Recommended `Negozio` contract

Keep the existing model and make only additive changes.

Add:

```text
location_key       CharField(max_length=200, blank=True, db_index=True)
stock_revision     PositiveIntegerField(default=0)
last_restocked_at  DateTimeField(null=True, blank=True)
```

`location_key` uses `<region-key>/<place-key>`, for example
`skyrim/whiterun`. The existing `regione_nome` and `citta_nome` remain display
snapshots and preserve imported text. This avoids breaking a shop if an administrator
later changes a label.

Keep `categoria` as the stable shop-type key. Validate it against
`mercato.shop_types`.

For now, retain `regione_descrizione`, `citta_descrizione`, and their images for
legacy preservation, but hide them from the quick-create form. New shops should not
duplicate location configuration into these fields. They can be deprecated after
shop import and UI requirements are settled.

Use one versioned `lista_oggetti` shape:

```json
{
  "version": 2,
  "seed": "whiterun-fabbro-01",
  "generatedAt": "2026-07-26T10:00:00Z",
  "entries": [
    {
      "itemId": 42,
      "quantity": 3,
      "unitPrice": 125,
      "source": "generated"
    }
  ]
}
```

Stock rules:

- item IDs are authoritative; names come from `Oggetto` at read time;
- repeated generated items are collapsed into `quantity`;
- `unitPrice` is a restock snapshot, so later pricing changes do not silently alter
  an open shop;
- `source` is `generated` or `manual`;
- stock parsing accepts the legacy list/dictionary forms only in an importer or
  compatibility normalizer;
- every stock mutation increments `stock_revision`.

A separate `NegozioStockEntry` table is not necessary for the initial local,
single-machine implementation. Introduce it only if stock needs independent admin
editing, audit history, reservation, or high-concurrency querying.

## Backend structure

Use a small market package while leaving the existing model in `core`:

```text
backend/market/
  __init__.py
  config.py
  generator.py
  selectors.py
  services.py
  import_legacy.py
  tests/
```

The package does not need to be a new Django app in the first slice. It can use
`backend.core.models.Negozio` and `Oggetto`, avoiding a risky model/table move.

### Generator

`generator.py` should be pure apart from receiving already-selected candidate data.

Required behavior:

- instantiate `rng = random.Random(seed)`; never seed global randomness;
- validate level and category before querying;
- fetch candidate `Oggetto` rows in bounded queries, not one query per generated item;
- exclude archived items, rarity `Unico`, blank/invalid loot levels, and explicitly
  quarantined items unless a rule opts in;
- parse `lv_loot` through one tested helper;
- implement the legacy matrix as the initial compatibility preset;
- distinguish an exact regional match, a region-neutral item, and an item assigned to
  another region;
- clamp every calculated selection weight above zero;
- generate IDs, collapse duplicates, and enforce the configured copy cap;
- implement tavern services and beverage rules as named strategies rather than
  branches in the main loop;
- return a result DTO and diagnostics, not a saved model.

Example result:

```json
{
  "seed": "whiterun-fabbro-01",
  "entries": [{"itemId": 42, "quantity": 2, "unitPrice": 125}],
  "diagnostics": {
    "requestedRolls": 54,
    "fulfilledRolls": 51,
    "missingByItemType": {"trappola": 3}
  }
}
```

Diagnostics are especially useful while reconciling the imported catalog.

### Selectors

`selectors.py` should expose deliberate payloads:

```text
market_overview(character, region_key=None, place_key=None)
shop_detail(shop_id, character)
shop_management_overview()
shop_management_detail(shop_id)
```

The overview should return:

- sanitized regions/places;
- enabled shop types;
- shops grouped or filtered by `location_key`;
- character ID and coins when available;
- role capabilities;
- a market configuration version/hash.

Shop detail should resolve stock IDs with one `in_bulk()` query and serialize items
using the existing item serializer.

### Services and permissions

Use `require_game_manager` for create, update, archive, and regeneration. A normal
user may browse and later purchase only for an assigned/active character.

Services:

```text
preview_shop_generation(...)
create_shop_quick(...)
create_shop_batch(...)
update_shop(...)
archive_shop(...)
regenerate_shop_stock(...)
quote_purchase(...)
purchase_from_shop(...)  # second phase
```

All writes use `transaction.atomic`. Regeneration locks the shop with
`select_for_update`, replaces the full stock snapshot, increments the revision, and
returns the updated shop payload.

`create_shop_quick` input:

```json
{
  "locationKey": "skyrim/whiterun",
  "categoryKey": "fabbro",
  "level": 4,
  "name": "",
  "owner": "",
  "seed": "optional",
  "generateStock": true
}
```

When name is blank, derive it from a configurable template such as
`{typeLabel} di {placeLabel}`. Reject a duplicate normalized name at the same location
or append a predictable numeric suffix; do not silently reuse and overwrite a shop as
the legacy helper does.

For fast plural creation, `create_shop_batch` accepts a bounded `count` (for example
1–20), a base seed, and an optional name template. It should preview all proposed
shops before the user confirms creation.

## API contract

Add typed resource routes:

```text
GET /api/v1/market
GET /api/v1/market/shops/{shop_id}
GET /api/v1/management/shops
GET /api/v1/management/shops/{shop_id}
```

Add action schemas and dispatcher branches:

```text
market.shops.previewGeneration
market.shops.createQuick
market.shops.createBatch
market.shops.update
market.shops.archive
market.shops.regenerateStock
market.quote
market.purchase
```

The first six are master/admin operations. `market.quote` and `market.purchase` are
player operations against an allowed character.

Every response uses the existing envelope and returns enough updated state that the
SPA does not need several follow-up calls.

Do not accept the client's calculated price during checkout. The server recomputes
the quote from the saved stock. A master-only negotiation modifier may be accepted
within configured bounds and recorded in the response/event.

## Fast shop creation

Implement quick creation in both useful surfaces.

### Django Admin

Replace generic `V2Admin` registration with a dedicated `NegozioAdmin`:

- list columns: name, location, category, level, owner, stock count, last restock;
- filters: region key, place key, category, level, archived state;
- search: name, owner, display location;
- `save_as = True` for easy cloning;
- a visible `Regenerate stock` action with confirmation;
- a `Create shops quickly` button on the change list.

Use a virtual grouped `location` choice in the form. Its option groups are regions
and its options are places. On save, split the selected `location_key` and populate
the name snapshots through `resolve_location()`. `categoria` is also a choice sourced
from `mercato.shop_types`.

The quick-create admin page should show:

- location;
- category;
- level;
- number of shops;
- optional name pattern;
- optional owner;
- optional base seed;
- generate stock checkbox;
- preview, then confirm.

Do not expose the raw stock JSON in the main fieldset. Put it in a collapsed advanced
section or make it read-only and provide a structured stock editor later.

### SPA management workflow

Add `/tools/shops` and a card in the existing Management hub. This should be the best
day-to-day workflow for a game master:

- left: searchable/filterable shop list;
- center: selected shop and stock preview;
- right or modal: quick-create/batch-create form;
- explicit buttons for Preview, Create, Duplicate, Regenerate, and Archive.

The form should remember the last selected location/category during the current
session, making several shop creations fast without saving browser-only game data.

## Player-facing SPA

Add `/market` inside the existing shell:

- region and place selector;
- shop category filter;
- shop cards;
- item search, type filters, price range, and sorting;
- item detail;
- cart and quote summary;
- explicit regeneration controls only for master/admin;
- proper empty, loading, error, and stale-stock states.

Reuse existing item card/detail primitives where practical. Mark components with
`componentType` and `theme` according to project conventions.

The route should use TanStack Query keys such as:

```text
["market", regionKey, placeKey]
["market-shop", shopId]
```

After a write, update or invalidate only the affected overview/shop queries.

## Real purchase phase

For legacy visual parity, cart and quote can ship before real purchasing. Label that
state clearly as a quote/manual transaction.

When implementing `market.purchase`, make it atomic:

1. lock the shop and character;
2. compare the submitted `stockRevision`;
3. validate stock quantities and recompute price;
4. validate coins;
5. calculate all required backpack slots before changing anything;
6. reject the entire purchase if the fixed-slot inventory cannot accept every item;
7. deduct coins;
8. put item references into backpack slots;
9. decrement stock and increment the shop revision;
10. refresh and return the updated character sheet and shop.

Do not call the existing single-slot assignment command repeatedly without a
preflight. A multi-line purchase must be all-or-nothing and must never use the
existing displaced-item-loss behavior.

## Legacy import

Create `import_legacy_shops` following the same safety pattern as the item importer:

```text
venv\Scripts\python.exe manage.py import_legacy_shops
venv\Scripts\python.exe manage.py import_legacy_shops --apply
```

The default is dry-run. The importer reads Elder SQLite in read-only mode and is
idempotent using provenance:

```json
{
  "sourceProject": "the_elder_django",
  "sourceTable": "django_slim_negozio",
  "sourceId": 123
}
```

Import sequence:

1. Convert `Regione.lista_citta` into the initial `mercato.locations` default/value.
   Do not import `Regione` or `Citta` rows as models.
2. Reconcile missing and orphan location names and emit a report.
3. Import shops using `Negozio.luogo` as the primary place hint; use region JSON only
   to determine the parent region.
4. Normalize the 11 category values to configured category keys.
5. Store stable `location_key` plus legacy name snapshots.
6. Give empty-stock shops a deterministic seed such as
   `legacy-shop:<sourceId>` and mark them unstocked for lazy or batch generation.
7. For the 15 populated cache records, resolve item names to ReDjango item IDs,
   collapse duplicates into quantities, and quarantine missing/ambiguous names.
8. Report duplicates instead of merging them automatically.
9. Never treat `Citta.lista_negozi` as the authoritative relationship; use it only
   for reconciliation warnings.

Useful dry-run totals include created, updated, unchanged, invalid location,
duplicate identity, missing item, ambiguous item, and stock converted.

## Testing and quality gates

### Configuration tests

- duplicate region/place keys are rejected;
- missing labels and malformed JSON are rejected;
- disabled locations remain resolvable for existing shops but cannot be selected for
  a new one;
- seeding does not overwrite an administrator's edited `value`.

### Generator tests

- same seed and catalog produce the same result;
- generation does not change global random state;
- level bounds, rarity weights, fallback levels, regional bias, and copy cap work;
- archived, unique, invalid-level, and quarantined items are excluded;
- every configured shop type has at least one eligible item type;
- tavern/general/caravan special rules are covered;
- database query count stays bounded as inventory size grows.

### Service/API tests

- user cannot create, update, archive, or regenerate a shop;
- master/admin can quick-create;
- invalid location/category/level receives a structured 400 response;
- duplicate creation is handled explicitly;
- regeneration increments `stock_revision`;
- batch preview does not write;
- batch creation is atomic;
- market responses satisfy Ninja schemas;
- generated OpenAPI TypeScript types compile.

### Purchase tests

- stale revision, insufficient coins, insufficient stock, and insufficient backpack
  capacity roll back every change;
- successful purchase updates coins, inventory, stock, revision, and returned sheet;
- price modifier permission and bounds are enforced server-side;
- duplicate request IDs cannot cause accidental double purchase if idempotency is
  later enabled.

### Frontend tests

- location selection filters places and shops;
- quick-create preview and confirmation work;
- filters and sorting work on generated stock;
- regeneration requires an explicit confirmation;
- cart quote updates with quantities;
- role-specific controls are absent and backend-forbidden as appropriate;
- empty/error/stale stock states are understandable.

## Suggested delivery order

### Slice 1 — configuration and read model

- seed and validate the three market settings;
- add `location_key`, stock revision, and timestamp;
- add stock normalization;
- add selectors and read endpoints;
- create focused tests.

Exit gate: an admin can edit locations in Django Admin and a typed endpoint returns a
valid empty market grouped by those locations.

### Slice 2 — generator and quick creation

- port generator behavior into pure/tested services;
- add preview, quick-create, batch-create, archive, and regenerate actions;
- build dedicated `NegozioAdmin`;
- add `/tools/shops`.

Exit gate: a master can preview and create several deterministic shops without
touching JSON or creating location rows.

### Slice 3 — player Mercato

- add `/market`;
- add browsing, item details, filters, cart, and server quote;
- expose role-safe management controls.

Exit gate: the useful Elder browsing/generation workflow exists in the ReDjango SPA
with explicit controls and typed payloads.

### Slice 4 — shop import

- implement dry-run/apply importer;
- reconcile all locations/categories;
- import 1,850 shops and convert the small amount of populated cached stock;
- generate a reviewed report before applying.

Exit gate: a second dry-run is unchanged and all unresolved rows are reported rather
than silently dropped.

### Slice 5 — atomic purchasing

- implement purchase preflight and transaction;
- update character inventory and coins;
- handle stock revisions and return updated state.

Exit gate: no failure path can remove coins, lose items, or partially decrement stock.

## File-level checklist

```text
backend/core/defaults.py
  Seed mercato.locations, mercato.shop_types, mercato.generator_rules.

backend/core/settings_selectors.py
  Mark market definitions admin-managed.

backend/core/admin.py
  Validate market JSON settings and add dedicated NegozioAdmin/quick-create view.

backend/core/models.py
  Add location_key, stock_revision, last_restocked_at.

backend/core/migrations/
  Additive model migration.

backend/market/config.py
  Parse, normalize, validate, and resolve market parameters.

backend/market/generator.py
  Pure deterministic stock generation and strategies.

backend/market/selectors.py
  Market and management read models.

backend/market/services.py
  Atomic create/update/archive/regenerate/quote/purchase commands.

backend/market/import_legacy.py
  Read-only, idempotent legacy conversion.

backend/core/management/commands/import_legacy_shops.py
  Dry-run/apply command wrapper.

backend/api_v1/schemas.py
  Market DTO and action schemas.

backend/api_v1/api.py
  Resource routes and shared action dispatch.

frontend/src/features/market/
  Player-facing route, shop browser, item detail, cart.

frontend/src/features/management/ShopManagementPage.tsx
  Quick and batch creation workstation.

frontend/src/App.tsx
  /market and /tools/shops routes.

frontend/src/lib/generated/api.ts
  Regenerate from OpenAPI; do not edit manually.
```

## Definition of done

The Mercato slice is complete when:

- no `Regione` or `Citta` model exists;
- locations and shop types are configurable in Django Admin;
- existing shops remain stable when labels change;
- masters can create shops quickly, including a bounded previewed batch;
- stock generation is deterministic, validated, query-bounded, and server-side;
- the SPA uses typed ReDjango contracts;
- permissions are enforced on the backend;
- legacy shop import is dry-runnable, idempotent, and provenance-preserving;
- checkout is either clearly a quote/manual flow or a real atomic purchase—never the
  ambiguous legacy alert.

## Implementation status — 26 July 2026

The new Mercato is implemented in ReDjango.

- `/market` and `/tools/shops` use the same compact interaction rhythm as Abilità:
  regions in the left rail, localities as buttons, and shops as a third navigation
  layer before the stock workspace.
- Items support search, type/price filters, sorting, expandable detail, quantity,
  cart, server quote, and atomic purchase.
- Master and Admin can create, edit, highlight, and regenerate shops and configure
  regions, localities, and enabled shop types from the expandable Impostazioni
  Negozi section.
- The shop-type editor exposes inventory size and the complete catalog-category
  frequency matrix with guided ranks from principal to excluded. Admin additionally
  edits global level fallback, quantity, rarity, copy-limit, pricing, and negotiation
  rules through grouped controls rather than raw JSON.
- Admin additionally controls generator rules, bounded batch creation, and shop
  archival. The backend enforces these distinctions independently from the UI.
- Stock is deterministic, versioned, resolved from stable item IDs, and protected
  by `stock_revision` during purchase.
- The OpenAPI client is regenerated and the frontend and focused backend suites pass.

The legacy `import_legacy_shops` command remains a separate follow-up. The live market
does not depend on importing the Elder Django shops, and no legacy database was
mutated as part of this implementation.

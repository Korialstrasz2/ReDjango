# Best Build Practices

These practices define how ReDjango should grow from a minimum usable project into the rebuilt Elder Django workstation.

The goal is not only working code. The goal is a project that remains understandable after characters, inventory, skills, combat, media, lore, maps, and AI tools return.

## Core Principles

1. Keep Django as the source of truth.
2. Keep the frontend as one resource-efficient single-page application.
3. Use one frontend/backend communication style.
4. Keep data contracts explicit and predictable.
5. Build features as modular vertical slices.
6. Make UI components identifiable by `componentType` and `theme`.
7. Prefer clear naming over clever abstraction.
8. Keep content creation structured enough that future tools and agents can safely edit it.

## Hierarchical Security And Settings

The application has three permanent hierarchical levels:

```text
user < master < admin
```

- `user` owns personal appearance, accessibility, dice, and simple UI preferences.
- `master` inherits user capabilities and adds campaign-facing tools, hidden information, and dangerous-action safeguards.
- `admin` inherits everything and owns global branding, security policy, feature gates, setting definitions, and UI tokens.

Rules for every future feature:

- Declare the minimum role required to see and to mutate the feature.
- Enforce permissions on the backend. Hiding a button is never authorization.
- Use the shared role helpers in `backend/core/security.py`; do not add one-off `isMaster` localStorage flags.
- Put configurable behavior in `SettingDefinition` and personal values in `SettingOverride` instead of inventing new JSON keys or browser-only storage.
- Give every new setting a stable dotted key, category, value type, default, minimum role, and explicit user/master customization flags.
- Global baselines and setting definitions remain editable in Django Admin. Reseeding must never overwrite an administrator's current `value`.
- Player identity changes use `Giocatore.display_name`; character access requests use `CharacterAssignmentRequest` and become assignments only after an explicit Django Admin approval.
- Role-promotion codes are global admin-managed setting definitions. Never serialize their values to the SPA, store them as personal overrides, or accept them through the ordinary settings-save path.
- Frontend code may apply only known, validated UI settings. Do not treat arbitrary stored CSS or JavaScript as configuration.
- Add permission tests for user, master, and admin whenever a feature has privileged behavior.
- Keep Settings reachable from the application shell at all times.
- Treat role identifiers as backend security data. User and master interfaces show available controls without role tags, hierarchy diagrams, or role badges; only admin may receive and render the full hierarchy.
- Every game page and API requires a real authenticated Django session in all access modes. Only the login surfaces, Django Admin authentication flow, and required static assets may be anonymous.
- `security.access_mode` is a global admin-owned value with exactly `locked`, `lan`, and `online`. The active process mode is immutable: changing the configured value requires a launcher-managed or manual server restart.
- `locked` must bind to loopback and independently reject non-loopback sockets in middleware. `lan` may bind to all local interfaces but never weakens authentication. `online` must fail closed without an explicit production secret and allowed-host list, use secure cookies/HTTPS hardening, and normally remain behind a reverse proxy.
- Never restore an anonymous `local_master` fallback. A `Giocatore` must be linked to the authenticated Django user; Django staff permission and game role remain separate concerns.

## Project Origin And Direction

ReDjango originates from:

```text
C:\Users\alexo\PycharmProjects\firstDjango\the_elder_django
```

The original app contains valuable game data and domain logic, but it grew as a monolith. ReDjango should not recreate that monolith. When porting old features, extract the intent and data shape, then rebuild through the conventions in this file.

## Single Page Philosophy

The user experience should feel like one game-master workstation, not a set of disconnected pages.

- Keep `/` as the main application shell.
- Add new tools as panels, routes, tabs, drawers, inspectors, or modals inside the shell.
- Do not create a new Django template page for every feature.
- Use Django templates for the shell and server-provided bootstrap only.
- Use JavaScript modules for app behavior.
- Do not trigger full page reloads for normal workflows.
- Keep static assets small and local by default.

Acceptable exceptions:

- Django admin.
- Debug-only pages.
- Download/export endpoints.
- Authentication pages.

## One Communication Contract

All normal frontend/backend communication should use one AJAX-style contract. In this project, AJAX means browser `fetch`, not jQuery.

New interactive features should converge on a single action endpoint pattern rather than many unrelated response shapes. Existing prototype endpoints may stay temporarily, but new work should prefer this contract.

### Request Headers

Every JSON action request should include:

```text
Accept: application/json
Content-Type: application/json
X-CSRFToken: <django csrf token>
X-ReDjango-Action: <domain.action>
X-ReDjango-Request-Id: <client generated id>
```

Recommended optional headers:

```text
X-ReDjango-Client: web-spa
X-ReDjango-Screen: characters | media | inventory | combat | lore | maps
```

### Request Envelope

Use one envelope shape:

```json
{
  "action": "characters.save",
  "requestId": "client-generated-id",
  "context": {
    "screen": "characters",
    "selectedCharacterId": 1
  },
  "payload": {
    "anyFeatureSpecificData": true
  },
  "meta": {
    "clientVersion": "minimum"
  }
}
```

Rules:

- `action` is required and uses `domain.verb` naming.
- `requestId` is required for tracing, retries, and matching responses.
- `context` describes UI/session state, not the main mutation data.
- `payload` contains feature-specific input.
- `meta` is optional and should stay small.

### Response Envelope

Every action response should use:

```json
{
  "ok": true,
  "requestId": "client-generated-id",
  "data": {},
  "events": [],
  "warnings": [],
  "errors": []
}
```

Rules:

- `ok` is always present.
- `requestId` mirrors the request when available.
- `data` contains the updated state the UI needs now.
- `events` contains user-visible or loggable outcomes.
- `warnings` contains non-blocking problems.
- `errors` contains structured failures when `ok` is false.
- Use real HTTP status codes too: 200/201 for success, 400 for validation, 403 for permission, 404 for missing objects, 500 for unexpected failures.

### File Uploads

File uploads should still follow the same logical contract. Use `multipart/form-data` with:

```text
envelope: JSON string using the request envelope shape
file: one or more uploaded files
```

The response remains the same JSON response envelope.

### Action Names

Use short domain names and verbs:

```text
characters.list
characters.create
characters.save
characters.delete
media.list
media.upload
media.move
media.delete
inventory.moveItem
equipment.equipItem
skills.unlock
combat.resolveAttack
lore.linkEntries
maps.saveProgress
```

Do not invent a new communication pattern for each feature.

## Backend Structure

Use Django apps as domain boundaries.

Preferred domain layout:

```text
backend/<domain>/
  models.py          persistent data
  selectors.py       read-only query helpers
  services.py        write operations and game rules
  urls.py            URL routing
  views.py           thin HTTP/API layer
  admin.py           Django admin registration
  tests.py           focused tests when useful
```

For larger domains, split into packages:

```text
backend/characters/
  models.py
  selectors.py
  services/
    sheet.py
    resources.py
  api/
    actions.py
    schemas.py
```

Guidelines:

- Views parse requests, call one service or selector, and return a response.
- Views should not contain game rules.
- Selectors do not mutate data.
- Services own mutations, validation, transactions, and side effects.
- Use `transaction.atomic()` for multi-model state changes.
- Keep models meaningful, but avoid putting large workflows inside model methods.

## Backend Naming

Python files and functions use `snake_case`.

Django models use singular `PascalCase` nouns:

```python
Character
UserMediaAsset
InventoryContainer
InventorySlot
CampaignLoreEntry
```

Selectors use clear read names:

```python
get_character_sheet(character_id)
list_characters_for_user(user)
find_media_assets(owner, query)
```

Services use command names:

```python
create_character(owner, payload)
update_character(character, payload)
move_inventory_item(character, source, target)
apply_effect(character, effect_id)
```

Action handlers use `handle_<domain>_<verb>` when a dispatcher is introduced:

```python
handle_characters_save(request, envelope)
handle_media_upload(request, envelope)
```

Avoid vague names like:

```text
do_stuff
process_data
manager
helper2
new_function
```

## Frontend Structure

Keep the frontend organized by app shell, shared modules, and feature modules.

Preferred layout:

```text
frontend/static/frontend/
  css/
    app.css
    themes.css
  js/
    app.js
    api.js
    store.js
    components/
      modal.js
      card.js
      panel.js
    features/
      characters.js
      media.js
      inventory.js
      combat.js
      lore.js
```

Current files may be simpler, but new feature growth should move toward this shape.

Frontend naming:

- JavaScript files: `kebab-case.js` or clear single words for core modules.
- JavaScript variables/functions: `camelCase`.
- Constructor/factory names: `PascalCase` only for real classes.
- CSS classes: `kebab-case` with a stable prefix when components grow, such as `rd-card`, `rd-modal`, `rd-toolbar`.
- HTML data attributes: `data-component-type`, `data-theme`, `data-state`, `data-action`.

## Component Identity

Every reusable UI component must declare what it is and what theme it uses.

HTML example:

```html
<section class="rd-card" data-component-type="card" data-theme="parchment" data-state="active">
  ...
</section>
```

JavaScript descriptor example:

```js
const component = {
  id: "character-summary-1",
  componentType: "card",
  theme: "parchment",
  state: "active",
  data: {}
};
```

Rules:

- `componentType` describes structure and behavior.
- `theme` describes visual treatment.
- Do not encode visual themes into feature names.
- A card is still `componentType="card"` whether it displays a character, item, lore entry, or map note.
- A dangerous card should be `componentType="card"` and `theme="danger"`, not a special one-off class with hidden behavior.

Recommended component types:

```text
app-shell
nav
view
panel
card
modal
drawer
inspector
toolbar
button
form
field
list
table
grid
tabset
tab
toast
context-menu
```

Recommended base themes:

```text
default
parchment
dark
gold
danger
success
muted
arcane
combat
lore
media
```

## Themes

Themes should be data-driven and centralized.

- Put global theme tokens in CSS variables.
- Use `[data-theme="..."]` selectors for theme-specific styling.
- Avoid hard-coded colors scattered across feature CSS.
- Theme names should express intent, not exact colors.
- Store selectable application themes in `core.Theme`; do not add another hard-coded JavaScript theme list.
- Keep stable theme slugs, but let administrators add, archive, reorder, recolor, and rename themes through Django Admin.
- Use explicit `UploadedImage` relations for each screen background. New SPA routes must either reuse an existing background field deliberately or add an additive, documented field to `Theme`.
- Apply only validated colors, numeric opacity/blur values, safe same-origin media URLs, and known CSS tokens. Never store or execute administrator-provided CSS or JavaScript.
- Use the shared theme surfaces for every layered UI: `--theme-panel-surface`/`--theme-panel-strong-surface` for normal page panels and `--theme-overlay-surface`/`--theme-overlay-strong-surface` for sticky headers, toolbars, modals, drawers, tooltips, and drag previews. Do not add opaque white, black, sidebar-colored, or fixed-percentage backgrounds to those components.
- `Theme.panel_opacity` controls normal panel surfaces; `Theme.overlay_opacity` controls both the background veil and overlay surfaces. New overlays must therefore use the shared tokens so the administrator's opacity setting works on every page.
- Keep primary and secondary text at WCAG-readable contrast against both panel surfaces. Sidebar text must use the derived `--sidebar-text` and `--sidebar-muted` tokens because a light content theme may still use a dark navigation rail.
- Every font choice must flow through `--font-body` and `--font-display`, including feature workspaces. Font scaling must remain usable across the full configured range in navigation, forms, modals, quick tools, and dense workspaces.
- The optional global contrast outline is inherited from the document root and uses the active theme's primary text luminance to choose black or white. Its color-aware mode may refine that choice from each rendered text color, but must remain independent from `text-shadow`, glow, and feature-specific text effects so new pages receive the accessibility treatment without losing their visual identity.
- Active `Theme` rows are the source of truth for the theme selector. Backend validation must reject inactive or missing theme slugs.
- Bundled placeholder art belongs under `frontend/static/frontend/images/themes/`; the seed may copy it into managed media without overwriting administrator replacements.

Good:

```css
[data-component-type="card"][data-theme="danger"] {
  border-color: var(--danger);
}
```

Avoid:

```css
.character-red-card-special-case {
  border-color: #a13f3f;
}
```

## Italian User Interface

Italian is the canonical user-facing language for ReDjango.

- Write every visible heading, label, button, empty state, status, validation message, API error message, default guide, and launcher message in clear Italian.
- Keep stable technical identifiers, action names, JSON keys, model field names, and stored enum values unchanged when translation would break compatibility.
- Select choices may use stable English/internal values only when their visible labels are Italian objects such as `{ "value": "compact", "label": "Compatta" }`.
- Do not expose raw internal role names as a shortcut for explaining permissions.
- When importing legacy content, preserve source text as data where required, but translate new application chrome and explanatory copy.

## UI Coherence Rules

The same kind of UI should behave the same way everywhere.

### Modals

All modals must:

- Use `componentType="modal"`.
- Declare a `theme`.
- Be draggable unless explicitly marked static.
- Have a visible `X` close button in the top right.
- Close on `Escape` unless a dangerous unsaved action blocks it.
- Trap focus when open once accessibility helpers are introduced.
- Use the same header/body/footer structure.

Standard modal structure:

```html
<section data-component-type="modal" data-theme="default" role="dialog" aria-modal="true">
  <header data-modal-region="header">
    <h2>Title</h2>
    <button data-action="modal.close" aria-label="Close">X</button>
  </header>
  <div data-modal-region="body"></div>
  <footer data-modal-region="footer"></footer>
</section>
```

### Panels

Panels should:

- Use a header/body structure.
- Keep tools in a toolbar, not mixed randomly into content.
- Avoid nesting cards inside cards.
- Avoid page-level floating card sections when a full-width layout is clearer.

### Buttons

Buttons should:

- Use `data-action` when they trigger behavior.
- Have clear text or an accessible label.
- Use consistent visual themes for primary, secondary, and danger actions.
- Never rely on color alone to communicate danger.

### Forms

Forms should:

- Keep labels attached to inputs.
- Validate on the backend.
- Use frontend validation only for fast feedback.
- Submit through the standard AJAX contract.
- Show errors using the response envelope `errors` field.

## Content Creation Rules

Game content should be easy to search, import, validate, and later expose through tools.

For user-facing content records, prefer fields like:

```text
name
display_name
slug
category
tags
summary
description
rules_text
visibility
source
notes
metadata
created_at
updated_at
```

Guidelines:

- Use stable slugs for content that may be linked by other records.
- Keep display names human-friendly.
- Keep rules text separate from flavor text when possible.
- Use tags as arrays/lists, not comma-split strings, when the database field supports it.
- Store large media as files, not JSON blobs.
- Store references to media in the database.
- Keep imported old-project content marked with its source.

Recommended source format:

```json
{
  "sourceProject": "the_elder_django",
  "sourceTable": "django_slim_skill",
  "sourceId": 123
}
```

## Database Practices

- Use SQLite for the minimum local project.
- Keep migrations additive unless the user explicitly approves destructive changes.
- Do not delete seeded/user data casually.
- Preserve source IDs when importing from the old database.
- Use indexes for fields that are searched or filtered often.
- Prefer normalized tables for new systems, but do not prematurely normalize tiny prototypes.
- For slot-based systems, expose arrays to the frontend even if legacy data uses numbered fields.

## Item Catalog And Elder Import Contract

- `Oggetto.tipo_1` through `tipo_4` are ordered classifications. Their active values and labels come from `OpzioneTipoOggetto` and are managed in Django Admin; item authoring must not accept arbitrary new values.
- Preserve the exact four positions in API payloads even when an earlier position is blank. A compact `types` list may still be exposed for search and display.
- `Oggetto.rarita` is nullable; configured values are `Unico` (`0`) and numeric tiers `1...5`. Never infer that an Elder zero means `Unico` without an approved import rule.
- `Oggetto.effetto_1` through `effetto_8` preserve source text for review. They are compatibility data and never feed character calculations directly.
- `Oggetto.effects` remains the only item-owned structured calculation input. Conversion from Elder effect text must preserve the raw source and report ambiguous expressions instead of guessing.
- Import tooling must create or map type options before item rows, validate rarity explicitly, and remain dry-run-first.

## Character Inventory UX Contract

- The backend owns compatibility, capacity and weight rules; the frontend may preview but never replace validation.
- A swap succeeds only when each item is valid in the other item's source slot.
- Failed movement is atomic and returns a friendly, actionable Italian error.
- Direct catalog assignment validates compatibility before mutation. Replacing an occupied slot moves the previous item to the first free unlocked backpack slot, then to the first free locked slot; only a completely full 50-slot backpack may discard it, and that loss must be returned as an explicit warning.
- Every named equipment slot holds at most one item. Extra equipment slots accept any item and still contribute equipped weight/effects.
- Backpack capacity is `slot_magici + slot_non_magici`; items in the leading magical slots do not contribute weight.
- Backpack and quiver mutations compact their contents and order them from heaviest to lightest; equal-weight items keep their relative order. The leading magical backpack slots therefore always receive the heaviest carried items.
- Magical backpack slots are rendered before normal slots and keep a mana-blue border highlight except while movement-validity feedback is active.
- Quiver capacity comes from equipped quiver containers and quiver contents are restricted to projectiles.
- Never reduce a container's capacity while occupied slots would become inaccessible.
- Filling a slot is slot-first. Right-clicking a slot, or its `Scegli` command, opens the contextual picker anchored to that slot: it is a `context-menu` component portalled to `document.body`, opens already scoped to what the slot accepts, and closes on pick, on outside click, or on `Escape`. The search field keeps the caret while filters are used, so filter controls must suppress focus stealing rather than restore focus afterwards.
- The picker filters are Tipo 1, Tipo 2, Tipo 3, Rarità and Tipo arma. Their options come from the catalog payload the page already holds; never hard-code a type, rarity or weapon list in frontend code.
- `/api/v1/items` owns catalogue narrowing: `type_1`/`type_2`/`type_3`, `rarity`, `weapon_type_id` are database filters, while `group`+`slot` apply the same compatibility rule the mutation enforces. Compatibility depends on `metadata` type aliases, so it is evaluated in Python over a streamed queryset that stops at the first `limit` matches; do not turn it into an approximate database filter and do not serialize the whole catalogue to filter it afterwards.
- `Equipaggia` resolves its own destination: the first free compatible named slot wins, a single compatible slot is replaced outright, and only a genuine tie between occupied slots asks the player to pick which one to replace. Extra slots are never chosen automatically because they accept everything and are scarce.
- The catalogue search arms an item without overwriting the query, so one search can fill several slots. Catalogue rows are draggable onto slots and every drag keeps its click-based equivalent.
- Slot actions stay reachable long enough to reach the search column and come back; `SLOT_ACTIONS_HIDE_DELAY` is the single source of that timing.
- Inventory mutations save immediately. Resource controls keep local draft values until the user explicitly saves, then return the refreshed character projection.
- Theme-specific character visuals use shared tokens (`health`, `mana`, `energy`, `power`, `validSlot`, `invalidSlot`) and the character background relation.
- Dragging must have a click-based alternative and invalid targets must be communicated by text as well as color.

## Character Effects UX And Persistence Contract

- New user-authored active effects belong directly to one `Personaggio`; they are not catalog templates and are never copied from a preset during ordinary authoring.
- Persist the effect header in `EffettoPersonalizzato` and every ordered calculation change in `OperazioneEffettoPersonalizzato`. Do not store the custom effect as a JSON blob.
- Custom effects have no stacking state, turn counter, start/end timestamp, or model timestamps. `temporaneo` is only the visible `(t)` marker; it never implies remaining time.
- Preserve `Effetto`, `EffettiPersonaggio`, and its 50 slots for imported and existing data. Legacy entries remain calculation inputs. Editing one active legacy entry promotes only that slot to a character-owned custom effect.
- Keep the user-facing fields name, description, origin, icon, and temporary marker; custom effects deliberately have no type/category field. An effect contains one or more ordered operations with target, operation, value/formula, and optional condition.
- The calculation service is the only authority for applying operations and safe formula overrides. Normal `set` is last inside the effect phase and remains subject to fatigue/general adjustments. `strong_set` is a terminal field-only override after those adjustments; when several terminal overrides target the same field, the last effect in application order wins. Both phases must appear explicitly in calculation breakdowns.
- The authoring UI receives allowed targets, operations, searchable icon metadata, examples, operation timing, and exhaustive formula guidance from the backend contract. Target authoring must be a text autocomplete with exact allowed-value validation, not an unrestricted string or a long select.
- The character sheet always exposes a compact icon rail. Hover/focus identifies an effect; activating it collapses the object workspace to a vertical `OGGETTI` return strip and opens the searchable effect manager.
- Creation, editing, removal, and ordering save immediately through the standard action envelope and return the refreshed character projection.
- Effect icons first resolve convention-based square WebP assets from `frontend/static/frontend/images/effects/icons/`, named exactly like the catalog label, and retain the shared code-native SVG glyphs as automatic fallbacks. Keep at least one catalog entry per configurable target plus narrative alternatives. Their meaning must also be available as searchable text, title, and accessible name; color or icon shape alone is never the only identifier. Temporary effect buttons keep a slow red attention glow while preserving the textual `(t)` marker.

## Dice UX And Texture Contract

- The backend generates and validates every result. Animation presents the outcome but never decides it.
- Quick-dice rolls and competence rolls append immutable `DiceRollRecord` audit entries with player and character snapshots. The shared history selector is master/admin-only, returns at most the newest 100 entries, and is reused by both the Dadi drawer and the Competenze workspace.
- `master.show_hidden_rolls` is the session preference that shows or hides the shared-history tabs; it does not weaken the backend role check.
- The quick tool rolls one die at a time and shows modifiers as an explicit equation: die result, signed bonus, and final total.
- Prefer lightweight CSS/SVG silhouettes and transforms over a 3D engine until physically simulated dice become a demonstrated requirement.
- Each supported die must keep a recognizable physical silhouette; d100 uses a near-spherical Zocchihedron-style projection rather than reusing d10 geometry.
- Store texture artwork as `UploadedImage` files and reference it through `DiceTexture`; never place image data or base64 content inside `DiceSet` JSON.
- Enforce at most one texture for each die in a set at the database and service layers.
- Texture positioning data is limited to validated offset, scale, and rotation values. The editor must preview the exact shared die renderer used during a roll.
- Keep face numbers above artwork and use the set's validated number color so textured dice remain readable.
- Dice animation and ambient motion must honor both the dice animation preference and reduced-motion accessibility settings.

## Name Generator And NPC Dossier Contract

- `core.NomiRazzeInfo` is the only source of names. There is no code-level fallback: the 485 lines of hardcoded Elder lists were deliberately not ported, so an empty pool raises `names.pool_empty` instead of silently answering from somewhere the master never configured. Pools arrive through `import_legacy_names`, keyed on the culture `name`.
- A race owns many **cultures** (32 rows across 17 races). Quick mode picks the culture named after the race and needs no second choice; the picker is optional. Five races (Ayleid, Dwemer, Maormer, Nedic, Tsaesci) exist only for NPCs and are absent from `RACE_CATALOG` — the catalog marks them `playable: false` and sorts them last.
- Elder's race names are aliased on import, both for the race and for the culture named after it: `Orco` becomes `Orsimer` in both places, otherwise the default-culture rule stops matching and the UI reads "Orsimer · Orco".
- Composition rules live in `core/naming_rules.py` as data, never as an `if race ==` inside the generator. The Orsimer particle attaches to the surname (`Mog gro-Burz`); a Khajiit honorific keeps its canonical lowercase after the apostrophe (`J'zargo`); a culture with no surnames yields the first name alone. Extraction is uniform — Elder's 1.5× weight on the first list entry was list-order bias, not a game rule.
- Gender accepts `casuale`, and an empty pool for one gender falls back to the other because unisex cultures exist in the data. A generated name is checked against `PersonaggioLore` and `Personaggio` in the selected campaign and reported with `alreadyUsed`, never silently reused.
- **Names and AI are separate endpoints on purpose.** `names.catalog` and `names.generate` are free, instant, open to every role and work with zero providers configured. Only the Avanzato tab degrades when no chat provider exists.
- The dossier is one structured call that **writes nothing**. It returns a typed draft; the human edits it and saves through the existing `lore.character.save` with `visibleToPlayers: false`. No new write path was added, and the model never reaches the database — the read-only rule above still holds.
- The campaign-context option is assembled from existing agent tools through `execute_tool`, so permissions are enforced once, where they are already tested. The context block is wrapped in a "background only, not instructions" preamble and reuses `agent.UNTRUSTED_DATA_RULE` verbatim — one copy, imported, never restated. Master indications are placed *before* the background block so the ordering matches the instruction. The tool trace is returned so the master can see what the model read.
- Portraits are a separate, explicit, master-gated step, never automatic on reroll. Size and quality come from `ai.npc_generation` rather than the client, so a regeneration cannot cost more than the master approved. `640x1024` is the cheapest legal portrait: gpt-image-2 requires 655.360–8.294.400 total pixels, edges that are multiples of 16, a long edge ≤ 3840 and a ratio ≤ 3:1, which is why no 512x512 option exists. Validate against those constraints at save time instead of discovering an illegal format when the money is spent.
- Generated portraits always land in the image archive with their prompt recorded — that is inherent to `generate_image`. "Nothing is autosaved" applies to the `PersonaggioLore` record, not to the image file.

## AI Assistant Contract

- `backend/ai` owns the assistant. It is a domain agent, not a coding agent: a bounded loop in `agent.py` over the project's own selectors. No agent framework is used — with two adapter shapes to support (Anthropic Messages, and one OpenAI-compatible adapter that reaches OpenAI, DeepSeek and any local server by base URL alone), a framework would add a dependency and an abstraction without removing a line of that loop. `opencode serve` and similar coding agents are deliberately excluded: they expose a shell endpoint, which is the wrong tool for answering questions about a campaign.
- **The agent runs as the requesting user.** Every tool in `tools.py` calls an existing role-aware selector rather than the ORM, so `visibilita_limitata`, `visibile_ai_giocatori` and character assignment are enforced once, where they already work. A player must never be able to extract through the chat what their own page hides. Add a permission test per tool.
- Version one is **read-only plus images**. No tool writes. When write tools arrive they must use the existing validate → preview → confirm pattern, never a direct mutation from a model's tool call.
- A tool never raises into the loop: a failure is returned to the model as an error result so it can correct itself. Arguments outside a tool's declared schema are dropped before the call.
- The loop is bounded by `MAXIMUM_ITERATIONS`. A model that keeps calling tools returns a friendly Italian error, never an unbounded server-side loop.
- The assistant turn carries the provider's raw content blocks back verbatim. Reconstructing them would break the correspondence with the previous round's tool calls, so a conversation always stays on one provider.
- **Credentials never leave the server.** The secret lives only in `AIProvider.secret_ciphertext`, encrypted at rest with a key derived from `SECRET_KEY`, is `editable=False`, and is never serialized — the SPA receives `hasSecret`, a boolean. The write path is one-way: an empty string means "leave it alone", the sentinel `__clear__` removes it. Failed decryption returns empty rather than raising, so rotating `SECRET_KEY` asks for the key again instead of breaking the page.
- `auth_strategy` exists so a future device-code flow is a new strategy rather than a rewrite. Today API keys are the only practical option: subscription login (OpenAI Codex via OpenCode's community plugin, Claude Code) is offered by vendors for their own agent products and its terms exclude multi-user applications, which is exactly what ReDjango is. Do not add a ChatGPT-session workaround.
- A provider is *usable* only when it has the credential its strategy requires. `ready` and the chat provider list are filtered on that, so the tool tells the master to configure a key instead of offering a chat box that fails on the first message.
- The assistant is a **quick-tools modal**, so it can be asked about the character sheet while the sheet is on screen. Its configuration is a **separate master/admin workspace at `/tools/ai`** — the two are deliberately not the same surface.
- Image generation is master/admin only and has its own provider slot: chat and images are configured independently because Anthropic does not generate images. Both a cloud API and a local Stable Diffusion endpoint are selectable, and every field — provider, model, size, quality, base URL — is configurable. Output lands in the existing archive with `UploadedImage.prompt` recorded and `source` set to `ai_generated`; no new model for generated art.
- Model identifiers are configurable strings with a suggested default, never hard-coded constants — provider model names change faster than this repository does.

## Campaign Soundtrack Contract

- `media_library.AudioFile` is the campaign soundtrack. `tags` is the source of truth for its multi-select picklist; `primary_tag` is kept in sync with the first tag because the storage folder, the default ordering and the database index are built on it. `secondary_tags` remains an earlier V2 compatibility column and is never read.
- `backend/media_library/audio_defaults.py` owns the tag vocabulary. Like the weather table it is backend rule data, not admin-authored content: the API rejects any tag outside the catalog, so filters stay predictable and near-duplicate labels cannot accumulate. Adding a tag means adding an entry there.
- Every player may list and play. Uploading, renaming, retagging and deleting require master or above, enforced by `audio_services`; hiding the controls is presentation, not authorization.
- Uploads are validated by extension first. A browser that declares no content type for `.flac`, `.opus` or `.m4a` is still accepted, but a declared type must match its container. Tracks are capped at 50 MB and stored as files with metadata in SQLite, never as base64 in JSON.
- The browser is the only place that knows a track's real length. It measures the duration once and sends it with the upload; the backend clamps it but never invents it.
- `protected_media` answers `Range` requests with `206` for audio containers only, and advertises `Accept-Ranges` on them. Seeking inside a long ambient track must not depend on downloading it whole, and the range branch must send exactly the requested bytes so `Content-Length` stays truthful.
- The audio element lives in `AudioPlayerProvider`, mounted above the router. Moving between Combattimento and a character sheet must never interrupt playback, so no route, drawer or panel may own an `<audio>` element of its own.
- The provider passes `children` through as a prop: only context consumers re-render on each time update, never the whole application shell.
- The queue is whatever the drawer currently shows. Filtering the library therefore also changes what `Precedente` and `Successiva` reach, and skipping wraps around at both ends.
- `Interrompi` clears the current track and the miniature player but deliberately leaves the media source in place; clearing it makes browsers raise a spurious media error.
- The miniature player belongs to the quick-tools bar and exists only while a track is loaded, so the campaign readout keeps its room whenever the soundtrack is silent.
- `audio.volume` and `audio.autoplay_next` are ordinary personal settings. The slider stays instant and the preference is written once the hand stops; a save in flight must never be overwritten by the value it is replacing.
- The Audio drawer deliberately reuses the dice drawer background until a dedicated theme slot is approved.

## Image Library Taxonomy And Picker Contract

- `ImageCategory` is the source of truth for image categories. Categories are created, renamed, ordered, activated, and mapped to upload contexts only through Django Admin; the SPA may read them but must never create or mutate them.
- Every new `UploadedImage` receives one active category and a free-form `group`. Category is the stable top-level navigation; group is the user-authored subcategory inside it.
- Contextual uploads send a stable `usageType`; the backend resolves its category from the administrator-configured `ImageCategory.usage_types`. Context tools may prefill a useful group and title, such as `Oggetti` plus the item name, without hard-coding the available category list.
- The general image archive exposes a category picklist from the backend and a manual group field, then browses images by category and group with search and filters.
- Item and other media-aware editors use the shared thumbnail picker. It must support category, group, and text filters, show visual thumbnails, and allow contextual upload without leaving the current workflow.
- Picker results live in their own scrollable region and keep legible square thumbnails regardless of library size. Activating a thumbnail opens the shared `Apri`/`Seleziona` context menu: `Apri` previews the original image without leaving the picker, while `Seleziona` changes the draft and leaves final confirmation explicit.
- Existing theme, dice, map, character, and imported images should be classified during safe reseeding when their category or group is missing. Reseeding must never overwrite an administrator's existing classification.
- Moving and deleting archive images are Admin-only capabilities, enforced by the backend as well as hidden from every other role. Before either action, the archive fetches live reverse references and asks for explicit confirmation; used-image confirmations name the referencing records instead of showing the generic warning.
- Deletion previews distinguish links that will be cleared from dependent records that will be cascade-deleted. File storage is removed only after the database deletion succeeds, so a protected relation cannot leave a broken image record.

## Character Competence UX And Persistence Contract

- `core.Competenze` is the canonical ordered catalogue. The initial seed contains the 21 legacy competences, stable metadata keys, attribute associations, structured narrative descriptions, and source mapping tags; reseeding may refresh only seed-owned catalogue rows.
- Character-owned state remains in `Personaggio.competenze` under each stable key with exactly `barra1`, `barra2`, and `extra`. Both bars are integers from 0 through 7. `extra` is a freely editable permanent player value and does not spend experience.
- `barra1` is the flat roll rank; `barra2` is mastery. Increasing either bar spends `pe_abilita` using cumulative triangular cost; decreasing either bar atomically refunds the corresponding triangular difference. Both directions are server-validated. The player sees an advisory warning that points may be removed at most three times, but this limit is intentionally not counted or enforced. Never accept an unchanged or out-of-range rank, insufficient XP, or a client-calculated balance.
- Source-linked competence bonuses never mutate the manual `extra`. Evaluate equipped item effects, active effects, and accepted skill-passive snapshots when reading or rolling, then return manual, linked, effective, and source-breakdown values separately. Unequipping or removing a source must remove only its linked contribution.
- The shared structured effect vocabulary exposes targets as `competenza.<stable_key>`. Items, personal effects, legacy effects, and skill passives use that same target; competence formula overrides are not supported because the competence calculation has its own explicit pipeline.
- The backend generates every competence die result and stores a `TiroCompetenza` snapshot. The equation is die + base rank + effective extra, with optional mastery technique changes. Mastery 1 unlocks Impulso (+1 for 3 Energia), rank 2 uses d8, rank 3 unlocks Impulso maggiore (+2 for 6 Energia), rank 4 uses d10, rank 5 discounts each technique by 1 Energia, rank 6 uses d12, and rank 7 grants two free rerolls on one roll per campaign day.
- The `/competencies` route is a dedicated React workspace inside the existing shell, never a popup or Django template. Keep all 21 compact cards and both bars glanceable, then use an in-page focus stage for upgrades, extra sources, dice, descriptions, mastery, and history.
- Numeric description examples are narrative nuances, not hard rules. Parse them for readable presentation but never automatically highlight, select, or enforce the entry matching a rolled total.
- Reuse curated original competence artwork as local static assets, but keep the composition, interaction, and responsive treatment native to ReDjango. Ambient motion and dice animation must honor reduced-motion and dice-animation preferences.

## Campaign Lore And Faction Reputation Contract

- `backend/lore` owns the campaign lore domain. Its records are normalized tables, never JSON blobs on a single per-campaign row; the Elder `LoreCampagna` shape is a source of domain knowledge, not a model to reproduce.
- `PersonaggioLore` is a deliberately lightweight narrative record: name, role, description, portrait, optional faction, visibility. It has no relation to `characters.Personaggio` and must not grow sheet, stat, or inventory fields. A lore entry says who somebody is, not what they roll.
- A faction stores only `reputazione_base`. The current standing towards the party is **never persisted**: it is replayed from that base through the ordered event log every time it is read. Deleting or re-dating an event therefore genuinely rewrites the present, and no cached score can drift from the log.
- Replay order is `(giorno_campagna, created_at)`. `giorno_campagna` defaults to the campaign's current day, so a back-dated event is inserted where it belongs in the story. `ora_campagna` mirrors the campaign's free-text clock and is display only; it is never a sort key.
- `EventoReputazione` keeps the narrative act (mode, reason, day, visibility) and `EffettoEventoReputazione` keeps one ordered row per touched faction. Reason is mandatory: an unexplained reputation change is not recordable.
- `adjust` events spread through the reaction grid **one hop only**. A propagated effect never seeds further propagation, and a faction the master named explicitly in the event keeps its authored value: explicit intent always beats the grid.
- `set` events are absolute anchors and never propagate. They exist to correct a standing, not to narrate a consequence.
- Effects store the delta or absolute value that was authored, never a resolved score. Editing the grid changes future events only; it must not retroactively rewrite what already happened.
- Editing an event rebuilds its effects only when the mode or an authored value actually changed. Correcting a reason, a title, a day, or a visibility flag leaves the recorded reactions untouched, so imported history whose propagation came from a grid that no longer exists survives an ordinary typo fix.
- The `/lore` faction workspace keeps factions in the main column and the master tools in a right-hand rail with two tabs: `Aggiungi` records or re-authors an event, `Storico` lists the timeline with its edit and delete controls. Players receive the same rail with only the history.
- Lore character cards expose a portrait and a name and nothing else. Description, faction, and the master's edit and archive controls appear only once a card is opened, so the gallery stays a gallery.
- `core.TimelineEvent` belongs exclusively to the **Lore → Timeline** tab. Never reuse it for faction reputation, audit logs, quests, campaign clocks, static guide chronology, or Hall of Fame records; those domains keep their own models and invariants.
- Timeline dates are authored as signed integer offsets from the fall of Dagoth Ur and sorted by `ordine_cronologico`, never lexicographically by their display label. `data_evento` remains the compatibility/display value, while the numeric field is the ordering source of truth.
- Timeline authoring, editing, and soft-archiving are master/admin operations scoped to the active campaign. Every role may read active entries. Images are optional `UploadedImage` references and the no-image state is a first-class UI, not a validation failure.
- Timeline is the third tab of `/lore`, not a separate route. Its horizontally navigable chronology, search, keyboard controls, focused detail, and responsive presentation use shared theme tokens and honor reduced-motion preferences.
- `RelazioneFazione` is an asymmetric directed grid: origine→destinazione and destinazione→origine are independent rows, and a faction may not react to itself. A coefficient is how much the target moves per point the source gains.
- Reputation is clamped to `-100…100` at every write and at every replay step.
- The `/lore` route is readable by every role. Players see factions, current standings, the narrative tier, and the events that moved them. The reaction grid, the base values, and every authoring control are master/admin only, enforced by the backend and not merely hidden.
- `visibile_ai_giocatori` on an event hides its story from players while still counting in the replay, so a secret pact moves a standing the whole table can see. The same flag on a lore character hides the record entirely.
- Archiving a faction keeps its past events readable, drops its grid rows, and detaches its characters. Archived names are released, so the uniqueness constraints are conditional on `archived_at`.
- Narrative tier labels are reading aids derived from the score. They never replace the number in a rule, a payload, or a validation.

## Character Notes UX Contract

- Character notes are stable free-text sections, not titled records, cards, tasks, or dated journal entries.
- `Note` is the source of truth for `zaino`, `combat`, `competenze`, `crafting`, `viaggio`, `appunti`, `missioni`, and `background`.
- A contextual view and the global Diario must edit the same section through the shared note editor.
- Contextual notes live in the bottom sidebar bookmark for their page: hover or keyboard focus opens a transient preview, click pins it, and clicking again releases it. Opening and closing must animate both opacity and the book-page transform while respecting reduced motion.
- Appunti, Missioni, and Background remain general Diario sections. Zaino belongs to the character page, Combat belongs to Combattimento, and Competenze belongs to the dedicated competence workspace. Future Crafting and Viaggio pages follow the same mapping.
- Saves happen automatically after a short debounce and on blur; the interface always shows quiet saving, saved, or error feedback.
- Contextual pages must mount the existing editor inside the sidebar flyout instead of creating new note persistence.
- Fantasy atmosphere comes from theme, typography, and the writing surface, not from extra form fields or content-management ceremony.

## Character Creation Contract

- A new PG is born at level 1, with the nine characteristics at the profile base value, zero PE in every pool, no competence, no skill, no coin, and no equipment. Creation decides identity, race, subrace, and preferred characteristic; everything else is earned in play.
- The creation service must never write racial effects. `automatic_race_effects` already derives race modifiers, racial trait, and subrace from `razza_1`/`razza_2` on every refresh; writing them again doubles every bonus. This is the single most common way a converted Elder sheet comes out wrong.
- `razza_1` is the race and `razza_2` the subrace. A subrace not belonging to the chosen race is rejected. `razza_3` is not written at creation.
- The preferred characteristic is a real `EffettoPersonalizzato` named from `PREFERRED_CHARACTERISTIC_EFFECT_NAME`, carrying `PREFERRED_CHARACTERISTIC_FORMULA` on the chosen stat, with `origine` `"Creazione personaggio"`. It stacks on the automatic level bonus that every characteristic already receives, so the chosen stat advances twice as fast. Both constants live in `backend/core/defaults.py` and are the only place to change the amount.
- Creation is player-facing at `/new-character` and must stay outside the Master guard. It uses the `characters.create` action, never `management.characters.*`.
- Every playable character owns its own `Equip`, `Zaino`, `Faretra`, `Note`, and `EffettiPersonaggio`; the creation service builds all five in one transaction and assigns the result to the creating `Giocatore`.
- Creating a PG makes it the creator's active character, always — not only when they had none. The shell reads `activePersonaggioId` for the sidebar portrait, the brand name, and the "Scheda personaggio" link, so leaving the previous character active drops the player back onto it the moment they touch the menu.
- Name, age, and sex are required at creation; age is bounded by `MIN_CHARACTER_AGE`/`MAX_CHARACTER_AGE` and sex is limited to `SEX_CHOICES`. Both are validated in the service as well as the wizard: a required field enforced only in the frontend is not required.
- `RACE_CATALOG` is the single source for racial bonuses, but it is not what a real character reads. A character carrying `race.auto` skill ownerships takes its bonuses from the `Skill` rows in the `razze-sottorazze` group, and `collect_personaggio_effect_payloads` deliberately skips `automatic_race_effects` for it. Editing the catalog alone changes nothing in play: run `manage.py sync_race_skills --apply`, which projects the catalog onto those rows and recalculates the affected sheets.
- Every subrace declares `effects` for what the engine applies and `manual` for what the table must still track; a subrace with neither is a bug the tests catch. The creation panel renders the two separately and labels each power Automatico / In parte automatico / Solo promemoria, because a bonus that looks manual gets added twice and one that looks automatic gets forgotten.
- Subrace bonuses gain their base value again at levels 5, 10, 15 and 20 (`grows`), unless the subrace text redirects a threshold elsewhere (`at_levels`, `base_and_levels`) or says it does not grow. Race modifiers and race passives never grow. Express this with formulas over `personaggio.livello` — comparisons evaluate to 0/1 and are usable as arithmetic steps — never with hardcoded per-level tables.
- Formulas whose target is consumed as an integer must floor in the formula, not rely on the reader. `tier` picks a damage die from a table keyed by whole numbers, so `floor(personaggio.livello / 3)` is correct and a bare division is not.
- A creation step that asks for a mechanical choice shows what that choice does, in a panel beside it. Its content is derived — race bonuses from `RACE_CATALOG`, so the panel cannot promise a modifier `automatic_race_effects` will not apply; characteristic effects from the active `Formule_base` formulas, so an administrator's formula change moves the panel with it. Never hand-write these lists.
- Manual effects added later declare their provenance in `origine` (`Perk minore`, `Manuale Elder`, `Abilità: Vitale 3`). It is the only way to trace a stray +1 months later.

## Campaign Clock And Weather Contract

- The quick-tools bar carries the campaign state on its left: campaign name, `Meteo`, `Giorno`, `Ora`. It is the one place in the shell that answers "when and where are we", so no page duplicates that readout.
- `backend/core/weather.py` owns the six-entry weather table ported from the Elder `tempo` events, with its d100 ranges. It is backend rule data, not editable content: a table row is a rule the roll depends on, so it does not become an admin-authored model without a deliberate decision.
- `roll_weather` keeps the two Elder biases and must keep them together: a one-in-two chance prolongs the weather already in play, and a fresh roll is weighted towards `Soleggiato`, which alone covers `1-50`. Removing either bias changes how a session feels, not just its numbers.
- The d100 is rolled on the backend. The client asks for a roll and never sends one, so the table stays a backend rule.
- A stored weather is matched to its table row by name only. Hand-edited effect text still counts as the same weather when the roll prolongs it, and a name that left the table falls back to `Soleggiato`, as the Elder view did for an empty value.
- `DatiCampagna.meteo` keeps the full `Nome - effetti` string. The API splits it into `weatherLabel` and `weatherEffects`; the SPA renders those fields and never splits the string itself.
- The clock is a backend rule too: the hour wraps around midnight, the day stays inside `1…1000`, and `ora_corrente` holds the hour as a plain numeral. Free text already stored there reads as hour zero rather than raising.
- `campaign.clock.update` answers with `weatherReminder`, true every six campaign hours (`0`, `6`, `12`, `18`) and on any day change. The cadence belongs to the backend; the bar only opens the reminder when it is told to.
- Moving the clock and rolling the weather require master or above, enforced by `require_campaign_master` inside the service. Hiding the arrows is presentation, not authorization.
- Both actions target the campaign the player is effectively on, resolved by `selected_campaign_id` so the top bar and the actions behind it never disagree about which campaign is open.
- Overlays opened from the quick-tools bar must be portalled to `document.body`. The bar blurs its backdrop, which would otherwise trap a fixed overlay inside it.

## Keyboard Shortcut UX Contract

- Persist personal shortcuts through `SettingDefinition` and `SettingOverride` keys under `shortcuts.*`; do not keep them only in browser storage.
- Default shortcuts use unique `Alt + lettera` combinations that avoid common browser and operating-system commands. The selectable list excludes known browser conflicts such as `Alt+D`, `Alt+E`, and `Alt+F`.
- Every main navigation destination, including role-gated Strumenti, has a shortcut definition. Conflict previews use only the settings visible to the current role, matching backend validation.
- Show duplicate assignments inline while editing and prevent submission until every visible collision is resolved.
- Reject duplicate effective assignments on the backend so one keystroke always has one application action.
- Page shortcuts navigate through the SPA router. Quick-tool shortcuts open the same Diario and Dadi state used by their toolbar buttons.
- Expose configured combinations through `aria-keyshortcuts` and a visible hover title on the corresponding navigation or toolbar control.

## Unified Skill UX And Persistence Contract

- `Skill` is the aggregate root for player-facing content and authoring. Identity, progression, prerequisites, descriptive details, structured passive effects, reminder-only active actions, and profile metadata stay on that object.
- `SkillPersonaggio` records ownership, XP spent, the passive IDs explicitly accepted during purchase, and character-only action presentation settings (`enabled`, `order`, personal note). It must not become a second content-definition model or override the canonical action rules.
- Passive features use the same validated operation vocabulary as character custom effects. Unlocking creates character-owned effect snapshots inside the same transaction as prerequisite checks, XP deduction, and ownership creation.
- Active features are deliberate reminders. Their buttons reveal the rule text and fixed costs but never execute combat rules, spend resources, or add a passive character effect.
- Every passive shown by the preview must be explicitly accepted. Missing acceptance, invalid XP allocation, insufficient XP, or unmet prerequisites rolls back the entire unlock.
- `Skill.costo_pe` is always the editable base price. Character-specific catalog prices are calculated at read/unlock time from the admin-configurable curve plus live owned-skill modifiers, and the API must expose both values. Deleting a granting `SkillPersonaggio` automatically removes its discount; no cached price is stored.
- System-managed unlock requirements live with the canonical Skill rule and are enforced for players; master/admin operations may bypass them. The card must explain automatic price modifiers and their reversal without requiring the user to calculate them.
- Equipment specializations remain distinct effect targets. Character refresh projects only the targets matching current weapon length/power, unarmed state, armor weight, or shield into Attacco, Difesa, and Tier, so unequipping or changing gear automatically removes the previous contribution.
- Ranked passives store only their own increment (for example `+0.2` at every rank); totals emerge from stacking the owned effect snapshots, never from writing a cumulative value into the last rank.
- Alchemy colour multipliers and level-effect values are normal calculated `Personaggio.tot` variables. Their base values live in the administrator-controlled `Formule_base` profile, while equipment, skills, and custom effects use the shared operation engine. `BorsaReagenti` stores capacity and ingredient quantities only; its historical `moltiplicatori` JSON is compatibility data and is not a calculation source.
- New authoring must not write `EffettiSkill`; that table remains only as an additive compatibility surface for earlier V2 work. Do not recreate the legacy nested `Attivabile.effetto_attivabile` executor.
- The catalog hierarchy is always `GruppoFamiglieSkill → FamigliaSkill → Skill`. Groups are normalized, ordered database records managed from `/tools/skills`; never render a group as if it were a family. The seeded groups Generali, Religioni, Scuole di Magia, Classi, and Perk remain editable defaults rather than a hard-coded enum.
- The `/skills` SPA has three top-level areas: Skills, Azioni, and Analisi Skill PG. Skills navigates group then family then cards; Azioni configures only visibility/order/personal notes for actions granted to that character; Analisi summarizes normalized ownership.
- Player details and master/admin authoring stay in tabs of the same Skill card and use server-owned validation and permission checks.
- `/tools/skills` is the master/admin all-at-a-glance authoring workspace. It owns group/family lifecycle, complete catalog filtering, and the persistent Elder review queue. A blocked legacy candidate may enter the live catalog only through the same structured Skill validation used by ordinary authoring; syncing the queue never imports character ownership.
- `/tools/units` is the master/admin authoring workspace for quick-combat archetypes. Its preview must call the same generator as Combat inside a rolled-back transaction; do not maintain a second preview-only simulation.
- Every `Unit` declares exactly one generation kind. Animals and creatures have no humanoid Skill, equipment, or competence pools; both may add authored innate actions and per-variable level-1/level-20 curves. Humanoids use Core/archetype Skill budgets, real prices and prerequisites, level-scheduled perks, weighted competences, and explicit equipment pools.
- Humanoid progression must come from Skill/perk/equipment rules. Direct per-level modifiers, milestones, and legacy level bands are ignored unless `allowHumanoidStatGrowth` is explicitly enabled. Explicit weapon, armour and exceptional-accessory pools never fall back to unrelated catalogue objects; only the assigned shared accessory profile resolves ordinary accessories dynamically by physical type, effect kind and tier.
- Humanoid Unit imports use a fresh automatic variant by default; a named variant remains deterministic. Perk progression is a single non-configurable system: each level independently has a 50% chance to follow the Elder AI milestone resolved by current Skill names and a 50% chance to use the Unit-compatible weighted choice; both grants at an even level share that choice. Characteristic improvements remain repeatable character-owned effects and legacy IDs are never persisted. Core and archetype Skill lists are always curated explicitly per Unit, with only real prerequisites expanded. Final XP spending passes may consume either curated list from the shared general-XP carry, while every purchase still uses the canonical Skill price, prerequisite, unlock, and passive pipeline.
- Elder Unit portraits are imported only from the root `django_slim/static/media/images/pgs` files selected by Unit provenance; duplicate/animation subdirectories are never scanned. The dry-run stages and validates WebP output plus a manifest. Apply is all-or-nothing by default; an explicit partial mode may import only validated portraits while leaving every blocked Unit unchanged and reported. Imported assets use the existing `Personaggi` category, `character_portrait` usage and `Unit e NPC` group. Generation copies the Unit image relation to `Personaggio.portrait`, so later Unit artwork changes affect future characters without rewriting existing ones.
- Gestione Unit reuses the shared media picker but locks its portrait context to `Personaggi` / `Unit e NPC` / `character_portrait`. New files are converted client-side to dimension-preserving WebP quality 70 before upload, and the backend independently validates format, quality metadata and taxonomy before linking. Image selection is draft state: the previous Unit image remains authoritative until the complete Unit save transaction succeeds.
- Equipment entries may be optional through `chance`; accessory groups use `minCount`, `maxCount`, and `emptyChance`. Author overlapping level bands and multiple explicit alternatives, but never select outside the Unit pool. Follow `Builder_docs/UNIT_AUTHORING_GUIDE_FOR_LLM.md` for new Unit content.
- Treat light and heavy equipment as separate material paths, declare a Unit tier cap, and validate every boundary level. Use the shared accessory profile for the ordinary Elder-style total. Reserve `accessoryCountByLevel` and group minima for exceptional Units that guarantee identity-defining concrete categories or objects.
- Keep Core and archetype Skill expansion independent. A production humanoid Core should primarily contain explicit general/passive growth; weapon attacks belong to the archetype pool. Never rely on a broad physical-tag expansion for a specialized ranged Unit.
- Family artwork may be curated from the original project's assets, while skill mechanics are migrated deliberately from useful prose, costs, formulas, and proposed effects instead of bulk-copying empty execution payloads.
- The skills route intentionally reuses the character-workspace theme background until a dedicated theme slot is approved.

## Resource Efficiency

ReDjango should stay light.

### Market Management And Generation Profiles

- `/market` is the operational commerce workspace: navigation, stock inspection, purchase, negotiation and contextual shop actions. It must not embed the global market-settings editor.
- `/tools/shops` is the authoritative master/admin workspace for market structure, shop-type assortment, generation profiles, global generator rules and batch operations.
- `mercato.locations`, `mercato.shop_types`, `mercato.generation_profiles` and `mercato.generator_rules` remain validated `SettingDefinition` values. Their arrays are ordered authoring contracts; player-facing market navigation preserves that order instead of sorting it again.
- Region, location, shop-type and generation-profile keys are stable links. Their labels may be renamed and entries may be reordered or duplicated, but a key used by a shop may not disappear. Renaming a configured location must synchronize the denormalized shop display labels inside the same transaction.
- `Negozio.generation_profile_key` stores only an explicit per-shop override. Blank means “inherit `defaultProfileKey`”; changing the global default therefore updates every inheriting shop without rewriting its row.
- A generation profile owns a quantity multiplier, a price multiplier and a complete rarity distribution. Generation applies the global rules first, then the shop-type inventory multiplier, then the effective profile. Existing stock changes only when the shop is created or regenerated.
- Master and admin may assign enabled profiles to shops. Only admin may author profiles or the global generator rules, enforced by market services as well as by the SPA.

### Shared Unit Accessory Profiles

- `AccessoryProfile` is the reusable source of truth for ordinary humanoid accessory generation. A Unit stores one profile reference, not a materialized list of accessory object IDs.
- Profile pools contain catalogue effect kinds (`Oggetto.tipo_2`), physical slots, weights, duplicate exceptions, count curves and item-level jitter. Concrete objects are resolved from the live catalogue at generation time through `tipo_1`, `tipo_2` and the numeric `Livello N` tier.
- Preserve the Elder progression formula: expected item tier is `(character level + 1) // 2`, varied independently by `-2..+2` and clamped to `1..10`; a missing exact tier searches upward before downward.
- Preserve Elder weighting by combining the core pool three times with one randomly selected variant pool. Only explicitly repeatable kinds may appear more than once.
- Explicit Unit equipment slots and groups are exceptional overrides. Equip them first, count occupied accessory slots toward the profile target, and let the shared profile fill only valid empty slots.
- Never equip beyond the character's active ring, earring or sack limits. Record profile, effect kind, requested tier, resolved tier and fallback use in the Unit-generation trace.

### Combat Damage Rule Configuration

- `GlobalModifiers` profile `Formule_base`, key `combat_damage_rules`, is the source of truth for the resistance percentages, Tier dice formulas, and complete d20 × attack-difference damage grid.
- `/tools/variables/damage` is the only SPA editor for that large rule object. It remains Admin-only and requires server validation plus an expiring confirmation token before persistence.
- Combat must read the saved rule object through `backend.combat.damage_rules`; do not duplicate the grid or editable percentages in frontend code.
- Preserve the Elder lookup bounds: attack difference `-25...45`, d20 `1...20`, resistance levels `-4...9`, and Tier formulas `-5...30`. Resistance levels outside the authored range clamp to its endpoints; a Tier without a configured formula produces no automatic damage.
- Reseeding may add a missing `combat_damage_rules` object but must never overwrite an administrator's saved table.
- The combat workspace uses a compact combat-specific character projection. Do not replace it with the full character-sheet selector: owned-skill pricing and unlock analysis make that an N×M query path.
- A successful combat mutation already returns the updated workspace. Put that response directly in the query cache; only remote SSE event IDs absent from the cache should trigger a refetch.
- Combat SSE must run as an asynchronous iterator on the ASGI server used by the managed launcher. A waiting player must not reserve a synchronous request worker; reconnects prefer `Last-Event-ID` over the initial query cursor.
- Character-sheet and character-mutation responses call `personaggio_detail(..., include_skills=False)`. Skill cards, calculated prices, prerequisites and unlock analysis belong exclusively to the dedicated Skills endpoints.
- The character page loads item-editor configuration with `limit=0` and performs a bounded item query only after the user starts searching. Do not restore the eager full-catalog download to the sheet's critical path.

- Keep the chosen React stack focused; do not add overlapping state, form or drag libraries without a demonstrated need.
- Keep the initial payload small.
- Lazy-load large feature modules later if needed.
- Do not poll aggressively.
- Prefer one updated response after a mutation over multiple follow-up requests.
- Store files on disk and metadata in SQLite.
- Avoid embedding base64 media in normal JSON responses.

## Error Handling

Use structured errors:

```json
{
  "code": "character.name_required",
  "message": "Character name is required.",
  "field": "name"
}
```

Rules:

- Error `code` values use `domain.problem` naming.
- `message` is human-readable.
- `field` is optional and used for form errors.
- Backend logs may include details, but user responses should stay safe and clear.

## Verification

For small changes, run:

```bat
python manage.py check
```

For database changes, run:

```bat
python manage.py migrate --noinput
```

For the React/TypeScript frontend, run:

```bat
cd frontend
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

For API changes, smoke-test the affected endpoint with Django's test client or `curl`.

## When Porting From The Original Project

1. Identify the original feature and its source files/tables.
2. Write down the minimum useful behavior.
3. Create a clean ReDjango data shape.
4. Add selectors/services before UI behavior grows.
5. Add one AJAX action at a time.
6. Render the feature as a component with `componentType` and `theme`.
7. Keep old-project IDs/source metadata when importing content.
8. Verify that the original project was not modified.

## Anti-Patterns

Avoid these:

- A new endpoint shape for every feature.
- Large view functions that contain game rules.
- Frontend code that knows secret backend rules.
- Random one-off component class names.
- Full page reloads for normal app actions.
- Copying large original files into ReDjango without simplification.
- Storing large media in JSON.
- Hard-coding colors and fonts inside feature-specific CSS.
- Adding global mutable state without a clear owner.

## Living Document Rule

If a convention becomes real in code, update this file. If code and this file disagree, either fix the code or update the document in the same change.

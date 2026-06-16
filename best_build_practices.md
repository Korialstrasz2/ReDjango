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
- Authentication pages if login is later added.

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

## Resource Efficiency

ReDjango should stay light.

- Avoid heavy frontend frameworks until the user chooses one.
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

For frontend JavaScript syntax, run:

```bat
node --check frontend\static\frontend\js\app.js
```

When adding new JS modules, check those too.

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

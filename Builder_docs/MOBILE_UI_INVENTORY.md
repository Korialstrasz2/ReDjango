# ReDjango Mobile UI Inventory

Implementation branch: `mobile-optimized`  
Baseline branch: `main`  
Baseline commit: `da846aca31d31b15e4128f70b0cf0e6cb3b32283`  
Inventory started: 2026-08-05

This is the implementation-time inventory required by the responsive smartphone and tablet guide. It records the current repository rather than treating the guide as a frozen code description. Entries marked **pending deep audit** still require a complete JSX call-site, stylesheet, state, mutation, and screenshot pass before that route can be classified as mobile-complete.

## Protected global contracts

- `AppContext`, `ThemeSurfacesContext`, TanStack Query, authentication bootstrap, theme application, media cache activation, router, toast host, and accessibility preference handling remain global.
- `AudioPlayerProvider` is intentionally above `Shell` and `<Routes>` so route changes do not interrupt playback.
- The canonical desktop shell is currently implemented directly in `frontend/src/App.tsx` with `.app-shell`, `.side-nav`, `.quick-tools-bar`, `.workspace`, and `.workspace-content`.
- Desktop navigation order and permissions are derived in `Shell`.
- The phone navigation bridge reads the rendered desktop sidebar links so ordering and role filtering remain synchronized without a second route/permission declaration. Formal shared navigation-data extraction is still pending.
- The current desktop breakpoint/test contract is the Playwright `authenticated` project at 1440 × 900.

## Authoritative current routes

The following list is derived from the current `<Routes>` declaration in `frontend/src/App.tsx`.

### Player-facing routes

| Route | Current page component | Important current structures | Primary mobile risks | Audit status |
| --- | --- | --- | --- | --- |
| `/` | `Dashboard` in `App.tsx` | active-character panel, shortcut row, character list/preview, logout | desktop two-column selection layout, shortcut density, no-active-character state | initial; phone shell available, page layout pending |
| `/characters` | redirect to `/` | redirect only | browser history and requested URL behavior | initial |
| `/character/:characterId` | `CharacterPage` | sticky HUD, resources, equipment/inventory, effects, coin controls, notes, dnd-kit | touch drag/scroll arbitration, slot sizing, inspectors/editors, dirty state | pending deep audit — highest state risk |
| `/skills` | `SkillsPage` | catalog, groups/families, search/filter, details, unlock and editor flows | multi-panel collapse, full-screen documents, touch ordering, role controls | pending deep audit |
| `/competencies` | `CompetenciesPage` | competency index, selection, roll workspace, progression and history | narrow workbench proportions, persistent roll result, history sheet | pending deep audit |
| `/creation` | `CreationPage` | Alchemy, Forge, Enchant workbenches and contextual notes | selected ingredients visibility, formula preview, invalid intermediate states | pending deep audit |
| `/new-character` | `NewCharacterPage` | multi-step creation flow and pickers | state loss on Back, sticky actions, validation visibility, long option lists | pending deep audit |
| `/combat` | `CombatPage` | map canvas/SVG, attack/actions, participants, inspectors, pointer capture | dedicated full-screen workspace, pan/select/token drag, zoom, role-specific controls | pending deep audit — highest interaction risk |
| `/travel` | `TravelPage` | map/canvas, markers, route/journey and guide surfaces | dedicated full-screen workspace, marker selection without hover, touch map gestures | pending deep audit |
| `/market` | `MarketPage` | location/shop navigation, filters, catalog, purchase state and modals | progressive navigation, cart persistence, hover item details, horizontal forms | pending deep audit |
| `/lore` | `LorePage` | factions, characters, timeline, current sticky right rail | tab/index/detail navigation, authoring sheets, hover/tap parity | pending deep audit |
| `/media` | `MediaPage` in `App.tsx` | upload, filters, cards, preview, move and destructive confirmation | tap-visible actions, full-screen preview, file input, image memory | pending deep audit |
| `/guides` | `GuidesPage` in `App.tsx` | guide index/detail, variable references, item compendium | index/detail history, tables, anchors below fixed bars | pending deep audit |
| `/settings` | `SettingsPage` in `App.tsx` | tabs, setting groups, profile/media/session panels, sticky save actions | font/density extremes, keyboard-independent shortcut explanation, dirty state | pending deep audit |

### Management routes

Current protected routes are `/tools`, `/tools/characters`, `/tools/items`, `/tools/skills`, `/tools/units`, `/tools/shops`, `/tools/dungeon`, `/tools/ai`, `/tools/master-ai`, `/tools/players`, `/tools/backups`, `/tools/dice`, `/tools/themes`, `/tools/variables`, and `/tools/variables/damage`.

- `GameManagerOnly` and `AdminOnly` continue to enforce the existing role redirects.
- Phone navigation does not expose management destinations as usable links.
- Direct phone navigation to a `/tools` URL preserves the URL, hides the compressed workspace, and shows an intentional tablet/desktop-required screen with Back and Home actions.
- The limitation currently lives at the phone shell layer; the centralized route component remains mounted underneath. Moving the limitation into `GameManagerOnly`/`AdminOnly` is pending the formal `App.tsx` shell extraction.
- Tablet support requires per-route verification before being claimed.

## Shared shell inventory

### Phone chrome

Files:

- `frontend/src/features/mobile/MobileNavigation.tsx`
- `frontend/src/features/quick-tools/QuickTools.tsx`
- `frontend/src/styles/mobile.css`

Current phone presentation:

- safe-area-aware fixed app bar;
- campaign and current-destination context;
- quick-tools launcher in the app bar;
- fixed bottom navigation for Home, active character, Skills, Combat, and More;
- full-screen More sheet containing the remaining current player links;
- active-route indication and real React Router history;
- workspace padding above and below the fixed bars;
- role-aware management limitation notice.

Implementation note:

- the phone navigation observes `.side-nav .nav-list` and derives its link set from the desktop presentation;
- this avoids duplicating the current route order and permissions, but it is an additive bridge rather than the final shared-controller architecture;
- `DesktopShell`/`PhoneShell` extraction and tablet navigation remain pending.

## Shared overlay and interaction inventory

### `Modal`

File: `frontend/src/components/Modal.tsx`

Current desktop contract:

- portal to `document.body`;
- Escape close;
- backdrop close;
- header drag and optional body drag;
- optional four-edge resize;
- wide, headless, themed-surface variants;
- minimum dimensions 360 × 240;
- position and size stored locally for the mounted modal.

Mobile foundation on `mobile-optimized`:

- new `responsiveMode`: `auto | dialog | sheet | fullscreen`;
- desktop always retains the existing dialog presentation;
- ordinary phone modals default to a bottom sheet;
- wide, resizable, headless, or body-draggable phone modals default to full-screen;
- mobile disables drag and resize, locks body scrolling, restores focus, exposes a visible header/close control, and uses sticky header/footer styling;
- `closeOnBackdrop` is available for unsaved/destructive forms, but call sites still require classification.

Pending:

- enumerate every `<Modal>` call site and assign its mobile target;
- add focus-trap behavior only after nested pickers/popovers are audited;
- add unsaved-state confirmation at owning feature level;
- verify every density and font scale.

### `ToolDrawer` and Quick Tools

Files:

- `frontend/src/features/quick-tools/QuickTools.tsx`
- `frontend/src/features/quick-tools/ToolDrawer.tsx`

Desktop contract remains:

- persistent desktop quick-tools bar with campaign status and mini audio player;
- Journal, Dice, AI, Audio, Theft, and Name tools;
- drawers focus the close button, close on Escape, and may be draggable/resizable;
- drawer minimum dimensions are 360 × 320 and movement is constrained with `window.innerWidth`/`window.innerHeight`.

Phone foundation now provides:

- a single app-bar launcher and quick-tools chooser sheet;
- one active drawer at a time through the existing `QuickTools` state;
- full-screen drawer presentation using `100dvh` and safe-area padding;
- drag and resize disabled on phones;
- desktop position and size state reset when entering phone presentation;
- body scroll lock, Escape close, close-button focus, and trigger-focus restoration;
- drawer content scroll isolated from the application page.

Pending per-tool audit:

- Journal section navigation and keyboard behavior;
- Dice altar, history, and dice-set management at all font scales;
- AI form layout and generated media previews;
- Audio mini-player persistence above bottom navigation and progress gestures;
- Theft and Name result layouts;
- landscape and virtual-keyboard behavior.

### Contextual notes

File: `frontend/src/features/notes/ContextNoteDock.tsx`

- context is selected in `Shell` for character inventory, combat, competencies, and creation;
- the dock currently opens from hover, focus, or pin state;
- phone target is a visible trigger and sheet while preserving pinning/autosave semantics;
- phone conversion remains pending.

### Audio

File: `frontend/src/features/audio/AudioPlayerProvider.tsx`

- one persistent `<audio>` element lives above the router;
- queue, playback, position, volume, and settings persistence are provider-owned;
- this hierarchy is protected;
- phone mini-player layout and progress-gesture behavior remain pending.

## Current layout and CSS observations

- `--sidebar-width` is `clamp(163px, 10.875rem, 270px)` on desktop.
- `--quick-tools-height` remains globally defined for the desktop shell.
- phone CSS changes `.app-shell` to a block presentation, hides `.side-nav` and `.quick-tools-bar`, removes sidebar offsets from workspace backgrounds, and adds app/bottom-bar spacing.
- login and several global states currently use `100vh`; the phone stylesheet overrides the global states with `100dvh`.
- several modal backdrops use `:has(...)` and `left: var(--sidebar-width)`; the phone-only stylesheet resets modal backdrops to the full viewport.
- many route layouts already contain narrow breakpoints, but they are not evidence of complete touch UX.
- hover-only and `title`-only disclosures still require a repository-wide audit.
- every `touch-action: none` occurrence must be inspected individually before any global gesture rule is added.

## Test inventory

Current test suite contains route/workspace coverage for character, combat, competencies, guides/media, lore, quick tools, audio, appearance, authentication, skills, and management areas.

The `mobile-optimized` branch adds:

- pure breakpoint boundary tests for `responsiveCategoryFromWidth`;
- unit tests for deriving mobile navigation from the desktop sidebar and matching nested active routes;
- a shared Playwright document-overflow diagnostic helper;
- baseline-only projects for desktop 1920, two phone portraits, phone landscape, tablet portrait, and tablet landscape;
- baseline assertions for phone app/bottom bars and desktop sidebar preservation;
- phone tests for More navigation, quick-tools access, and direct management URL handling;
- diagnostic attachments containing viewport, touch/capability, and overflow data.

The existing `authenticated` 1440 × 900 project remains unchanged and continues to run the existing suite.

## Required next reconnaissance and implementation work

1. Run the full dependency-backed frontend suite and capture canonical desktop screenshots.
2. Enumerate `frontend/src/components/`, `frontend/src/features/`, and all modal/portal call sites.
3. Search all stylesheets and JSX for fixed/sticky positioning, viewport units, minimum widths, overflow, hover-only behavior, pointer handlers, wheel handlers, media queries, `ResizeObserver`, and `matchMedia`.
4. Record API mutations, optimistic updates, local dirty state, scroll containers, and drag systems per route.
5. Convert Login and Dashboard as the first page-specific phone layouts.
6. Convert Context Notes to a visible phone trigger and sheet.
7. Move management blocking into the route guard during the formal shell extraction.
8. Convert this route table into a complete per-route and per-overlay matrix before declaring any page complete.

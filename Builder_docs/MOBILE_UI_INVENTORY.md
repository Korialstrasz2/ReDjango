# ReDjango Mobile UI Inventory

Implementation branch: `mobile-optimized`  
Baseline branch: `main`  
Baseline commit: `da846aca31d31b15e4128f70b0cf0e6cb3b32283`  
Inventory started: 2026-08-05

This implementation-time inventory tracks the current repository. A responsive stylesheet alone is not treated as completion: routes require state, mutation, overlay, touch, orientation, and desktop-preservation checks.

## Protected global contracts

- `AppContext`, `ThemeSurfacesContext`, TanStack Query, authentication bootstrap, theme application, media cache activation, router, toast host, and accessibility preferences remain global.
- `AudioPlayerProvider` stays above `Shell` and `<Routes>` so route changes do not interrupt playback.
- The canonical desktop shell remains in `frontend/src/App.tsx`.
- Desktop navigation ordering and permissions remain authoritative.
- Phone navigation currently derives links from the rendered desktop sidebar; formal shared navigation-data extraction remains pending.
- The canonical desktop Playwright project remains 1440 × 900.

## Player route inventory

| Route | Main structures | Current responsive classification | Remaining risk |
| --- | --- | --- | --- |
| `/` | active character, shortcuts, character list/preview | verified phone/tablet checkpoint | integrated roles, font scale, screenshots |
| `/characters` | redirect to `/` | covered through shell/navigation | history and integrated route pass |
| `/character/:characterId` | HUD, resources, equipment, containers, inventory, effects, coins, values, editors, drag/drop | verified dedicated checkpoint | broader seeded states, roles, font scale, Stage F screenshots |
| `/skills` | groups, families, XP, search, catalog, detail, unlock/editor flows | verified dedicated checkpoint | integrated roles and full overlay matrix |
| `/competencies` | index, detail, rank controls, techniques, rolls, mastery, history | verified dedicated checkpoint | populated-result variants and Stage F |
| `/creation` | Alchemy, Forge, Enchant | verified dedicated checkpoint | mutation-result variants and Stage F |
| `/new-character` | four-step draft, validation, option pickers, summary | verified dedicated checkpoint | actual submit variants and Stage F |
| `/market` | locations, shops, catalog, cart, modals | verified lower-risk checkpoint | integrated role and data variants |
| `/lore` | factions, NPCs, timeline, authoring | verified lower-risk checkpoint | integrated role and data variants |
| `/media` | browse, filters, upload, preview, move/delete | verified lower-risk checkpoint | file/device and memory variants |
| `/guides` | index, documents, anchors, tables, references | verified lower-risk checkpoint | full font-scale and anchor matrix |
| `/settings` | tabs, preferences, profile/media panels, save bar | verified lower-risk checkpoint | every density/font combination |
| `/travel` | map, markers, route/journey, guide surfaces | pending dedicated implementation | full-screen workspace, touch gestures, role variants |
| `/combat` | map/canvas, tokens, actions, targets, participants, inspectors | pending dedicated implementation — highest interaction risk | touch pan/select/drag, panels, player/master states |

## Management routes

Protected routes remain under `/tools*`.

- Existing `GameManagerOnly` and `AdminOnly` permission behavior remains authoritative.
- Phone navigation does not expose management destinations as usable player links.
- Direct phone navigation preserves the URL and shows an explicit tablet/desktop-required screen with Back and Home actions.
- The underlying protected route component can still mount beneath the shell-level limitation; moving the block into route guards remains pending formal shell extraction.
- Tablet management support is not claimed without per-route verification.

## Shared shell and overlay inventory

### Phone navigation

Files:

- `frontend/src/features/mobile/MobileNavigation.tsx`
- `frontend/src/features/quick-tools/QuickTools.tsx`
- `frontend/src/styles/mobile.css`

Implemented:

- fixed safe-area-aware app bar;
- persistent Home, Character, Skills, Combat, and More bottom navigation;
- active-route indication and React Router history;
- full-screen More and Quick Tools sheets;
- workspace offsets around fixed chrome;
- explicit phone management limitation.

Pending:

- formal DesktopShell/PhoneShell extraction;
- shared navigation configuration instead of DOM-derived links;
- dedicated tablet navigation decision.

### Modal

File: `frontend/src/components/Modal.tsx`

Desktop contract remains portal, Escape, backdrop, drag, optional resize, wide/headless/themed variants, and local position/size state.

Phone foundation provides:

- `auto | dialog | sheet | fullscreen` responsive presentation;
- ordinary dialogs as sheets;
- wide/resizable/headless/body-draggable dialogs as full-screen;
- no phone drag/resize;
- body scroll lock, safe areas, `100dvh`, sticky header/footer;
- close-button focus and trigger-focus restoration.

Pending:

- final classification of every remaining call site;
- dirty/destructive state review;
- integrated focus, font-scale, and nested-popover pass.

### Quick Tools and ToolDrawer

Files:

- `frontend/src/features/quick-tools/QuickTools.tsx`
- `frontend/src/features/quick-tools/ToolDrawer.tsx`

Implemented foundation:

- one phone launcher and chooser;
- full-screen drawers;
- no phone drag/resize;
- body scroll lock, Escape, safe areas, focus restoration.

Pending internal audits:

- Journal navigation and editing;
- Dice altar/history/set management;
- AI forms and generated media;
- Audio controls, persistence, and progress gestures;
- Theft and Names result layouts;
- landscape and virtual-keyboard behavior.

### Context Notes

File: `frontend/src/features/notes/ContextNoteDock.tsx`

- desktop hover/focus/pin behavior remains;
- phone has a visible floating trigger and sheet;
- the existing autosave editor is reused;
- final cross-route and keyboard pass remains pending.

## Character route inventory

Primary files:

- `frontend/src/features/character/CharacterPage.tsx`
- `frontend/src/features/character/CharacterEquipment.tsx`
- `frontend/src/features/character/CharacterSlot.tsx`
- `frontend/src/features/character/CharacterEffectsWorkspace.tsx`
- `frontend/src/features/character/SlotItemPicker.tsx`
- `frontend/src/features/character/ItemEditorModal.tsx`
- `frontend/src/features/character/CoinControls.tsx`
- `frontend/src/styles/mobile-character.css`
- `frontend/src/styles/mobile-character-fixes.css`
- `frontend/tests/mobile-character.spec.ts`

Verified phone behavior:

- compact non-sticky identity/resource HUD;
- permanently visible resource mutation controls rather than hover-only controls;
- 44 px quick-stat and resource targets;
- sequential Objects/Effects presentation;
- horizontal effect rail and compact effect directory;
- single-column effects editor and operation controls;
- equipment and container workspaces stacked in document flow;
- character portrait retained while absolute desktop slot rails become readable phone slot groups;
- grid and figure equipment views remain available;
- container tabs use contained horizontal scrolling;
- item search/autocomplete remains inside the route width;
- slot picker becomes a safe-area-aware full-screen dialog above app chrome;
- item editor uses the responsive full-screen modal path;
- overview editor uses the sheet path;
- primary and advanced value pages remain reachable;
- tap selection, Choose, Equip, Empty, Move, and quantity controls remain available;
- existing pointer drag remains active on filled draggable slots with `touch-action: none` only on those slots;
- a real CDP touch sequence verifies that drag cursor and overlay activate;
- document horizontal overflow remains within the shared tolerance.

Verified desktop preservation assertions:

- sticky Character HUD;
- multi-column inventory workspace;
- vertical effects rail;
- existing desktop drag/modal path remains untouched by phone-only rules.

## Responsive test inventory

The branch adds:

- pure breakpoint tests;
- mobile navigation unit tests;
- shared document/element overflow diagnostics;
- 1920 desktop, phone portrait/landscape, and tablet portrait/landscape projects;
- route suites for baseline/lower-risk pages, Skills, Competencies, Creation, New Character, and Character;
- phone management limitation assertions;
- mobile modal presentation assertions;
- Character touch-drag activation coverage.

The workflow `.github/workflows/mobile-optimization-verification.yml` runs unit tests, TypeScript, production build, Django migration/system checks, and the responsive Chromium matrix.

## Required next work

1. Implement Travel as a dedicated full-screen mobile workspace.
2. Implement Combat after Travel returns to a green checkpoint.
3. Audit every Quick Tool internal workflow.
4. Move phone management blocking into route guards during shell extraction.
5. Complete the Stage F matrix across player/master roles, orientations, font scales, dirty states, overlays, touch drag systems, and canonical desktop screenshots.
6. Do not merge for public mobile release until the full guide completion gate passes.

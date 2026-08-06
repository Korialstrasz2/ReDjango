# ReDjango Mobile UI Inventory

Implementation branch: `mobile-optimized`  
Stage F audit branch: `agent/mobile-stage-f-completion`  
Baseline commit: `da846aca31d31b15e4128f70b0cf0e6cb3b32283`  
Updated: 2026-08-06

This is an implementation-time inventory, not a release declaration. A route is an “automated checkpoint” when current Chromium tests cover its principal responsive presentation. Physical-device and full transaction evidence remain separate gates.

## Protected global contracts

- `AppContext`, `ThemeSurfacesContext`, TanStack Query, authentication bootstrap, router, media-cache activation, theme/font/density/accessibility application, the original desktop toast host, and global shortcuts remain outside route-specific mobile presentations.
- `AudioPlayerProvider` remains above `Shell` and `<Routes>`; phone and desktop route changes must not interrupt playback.
- `frontend/src/lib/navigation.ts` is the shared source for desktop and phone destination order and permissions.
- The canonical 1440 × 900 desktop project remains the pre-existing suite; a separate pinned visual harness compares 1280 × 800, 1440 × 900, and 1920 × 1080 evidence.
- Mobile adaptations are breakpoint/capability scoped. No user-agent routing and no simultaneous hidden desktop/mobile page trees are permitted.

## Player routes

| Route | Main surfaces and interactions | Responsive state | Open release evidence |
| --- | --- | --- | --- |
| `/` | active character, campaign context, shortcuts, logout, role variants | automated checkpoint | physical Safari/Chrome, no-character state, large OS text |
| `/characters` | redirect to `/` | integrated navigation checkpoint | direct-entry/history refresh evidence |
| `/character/:characterId` | HUD, resources, equipment, containers, drag/drop, coins, effects, values, item/picker/editor modals | dedicated automated checkpoint | complete valid/invalid/swap/full/locked/auto-scroll/orientation drag matrix |
| `/skills` | catalog/group/family/search/filter/detail/unlock/editor/order | dedicated automated checkpoint | exhaustive success/failure/archived/permission and keyboard-open flows |
| `/competencies` | index, resource summary, techniques, roll, mastery, rerolls, group history | dedicated automated checkpoint | populated failure variants and physical-device roll history |
| `/creation` | Alchemy, Forge, Enchant, ingredient/reagent sources, previews, results | dedicated automated checkpoint | all invalid intermediate mutations and physical touch drag where present |
| `/new-character` | four-step draft, pickers, validation, sticky actions, final summary | dedicated automated checkpoint | browser-Back discard confirmation and actual-submit variants |
| `/combat` | map, gestures, tokens, active roster, character, attack, inspectors, notes, role controls | high-risk automated checkpoint | committed token-move matrix, complete planners/managers, physical role sign-off, performance review |
| `/travel` | map, pan/pinch, markers, controls, guide, placement, route/journey state | high-risk automated checkpoint | committed marker/route flows, sheet coexistence, empty/loading, physical sign-off |
| `/market` | region/locality/shop drill-down, filters, products, cart/purchase, item dialogs | lower-risk automated checkpoint | full stock/price/error and keyboard-open forms |
| `/lore` | factions, characters, timeline, history, details, authoring | lower-risk automated checkpoint | reserved role variants, all authoring dirty/destructive dialogs |
| `/media` | upload, filters, grid, preview, move, delete, visibility | lower-risk automated checkpoint | camera/library picker, large-image memory, complete hover-action audit |
| `/guides` | search/index/detail/anchors/tables/compendium | lower-risk automated checkpoint | anchor restoration and all large-font/table combinations |
| `/settings` | profile, media, session, dice, preferences, shortcuts, sticky save, restart | lower-risk automated checkpoint | restart/offline physical evidence and complete save-error matrix |

## Management routes

Routes: `/tools`, `/tools/characters`, `/tools/items`, `/tools/skills`, `/tools/units`, `/tools/shops`, `/tools/dungeon`, `/tools/ai`, `/tools/master-ai`, `/tools/players`, `/tools/backups`, `/tools/dice`, `/tools/themes`, `/tools/variables`, `/tools/variables/damage`.

- `GameManagerOnly` and `AdminOnly` remain authoritative.
- A phone with sufficient role keeps the requested URL but mounts only `mobile-unsupported-management`, with Back and Home actions.
- A phone without the role follows the existing permission redirect and does not learn hidden management content.
- Tablet projects include an exact 768 × 1024 minimum-width project plus portrait and landscape projects.
- `mobile-tablet-management.spec.ts` visits every route as Admin and rejects phone fallback or document overflow.
- Physical iPad/Android-tablet and hardware-keyboard evidence remains open.

## Shared navigation and chrome

Files:

- `frontend/src/lib/navigation.ts`
- `frontend/src/features/mobile/MobileNavigation.tsx`
- `frontend/src/features/quick-tools/QuickTools.tsx`
- `frontend/src/styles/mobile.css`

Phone contract:

- fixed safe-area-aware app bar;
- Home, Character, Skills, Combat, More bottom navigation with labels and active route;
- full-screen More sheet and explicit management limitation;
- Quick Tools chooser and one active mobile ToolDrawer;
- real React Router navigation and browser history;
- workspace padding that clears app bar, mini-player, toast stack, and bottom navigation.

Tablet currently retains the desktop sidebar where the width contract allows it. The 768px management matrix is the minimum automated claim.

## Modal and overlay inventory

### Shared `Modal`

File: `frontend/src/components/Modal.tsx`

Desktop behavior retained:

- portal rendering;
- default/wide/headless variants;
- dragging and optional resizing;
- desktop widths, transforms, Escape, and backdrop defaults.

Phone behavior:

- `responsiveMode="auto | dialog | sheet | fullscreen"`;
- stacked top-modal semantics with lower layers inert and hidden from accessibility APIs;
- focus trap, initial focus, exact trigger restoration;
- mobile body lock with nested accounting;
- safe areas, `100dvh`, sticky header/footer;
- no drag/resize in mobile presentations;
- explicit backdrop policy for destructive/dirty work.

Confirmed Stage F conversion:

- Audio delete: shared compact destructive dialog on phone; original native confirmation preserved on desktop.

### `ToolDrawer`

Phone: full-screen presentation, sticky header, no drag/resize, dynamic viewport, focus restoration, Escape, safe areas. Desktop: original movable/resizable window.

### Known custom/ad hoc overlays requiring final classification

- `CampaignSpecialResources` inline `role="dialog"` editor;
- AI custom portal/alert surfaces;
- Combat and Travel local inspectors/panels that are not shared `Modal` instances;
- media/image pickers and route-specific custom overlays;
- any remaining native `window.confirm`, `window.alert`, or portal call site discovered by the source audit.

For each call site, the release ledger must record desktop type/size, phone target, tablet target, footer behavior, Escape, backdrop, dirty/destructive protection, keyboard-open behavior, nested picker behavior, and focus restoration.

## Quick Tools

| Tool | Phone presentation | Stage F workflow evidence | Open evidence |
| --- | --- | --- | --- |
| Journal | full-screen drawer | edit, autosave, reopen persistence, special-resource editor | all sections, keyboard-open, conflict/error/offline, special-resource mutation approvals |
| Dice | full-screen drawer | roll, session history, group history, clear | complete dice-set management, error variants, animation/performance |
| AI | full-screen drawer | submit when ready or explicit unavailable state | successful provider completion, image flow, cancellation/retry across network states |
| Audio | full-screen drawer + persistent mini-player | play, route continuity, transport/stop, navigation clearance, destructive modal | real media formats, background/lock behavior only where supported, upload/edit failures |
| Theft | full-screen drawer | mode, base, circumstances, diversion/manual modifier, reset | complete rule combination fixture set |
| Names | full-screen drawer | race/culture selection, generation, reroll | dossier/portrait/save flows and provider errors |

Related phone surfaces still requiring deliberate release evidence: campaign/weather/day/time controls, special resources, Dice History, dice-set management, and every reachable mini-player state.

## Context Notes

- desktop hover/focus/pin behavior remains;
- phone uses a visible trigger and sheet;
- existing autosave editor/state is reused;
- Combat integrates note access into its local phone navigation to avoid map overlap;
- keyboard-open, offline/error, conflict, and cross-route persistence remain release tests.

## Touch and hover inventory

### Existing automated touch evidence

- Character: real CDP touch drag activates the dnd-kit overlay and cancellation path; tap fallback remains.
- Combat: real pinch, one-finger token-drag preview/cancel, map panel transitions, and Back/dirty protection.
- Travel: real one-finger pan, pinch, marker placement mode, cancellation, and Back sequencing.
- Phone touch-target evidence is attached per player route; critical navigation and modal controls have focused size assertions.

### Remaining touch transaction evidence

- Character valid drop, invalid drop, swap, full inventory, locked slot, magical storage, quiver, stacks, auto-scroll, finger offset, orientation change.
- Combat committed token movement, invalid/cancel/error feedback, selection-mode arbitration, panel coexistence, accidental page-scroll prevention.
- Travel committed marker selection/placement, route/journey interaction, invalid/cancel/error feedback, controls-sheet coexistence.

### Hover audit

Every `:hover`, title-only detail, tooltip, hover-open action, and pointer-only control must be mapped to visible text, a button, tap/focus disclosure, or another tested alternative. `npm run audit:mobile-ui` produces JSON and Markdown candidate lists for review. A finding is not automatically a defect, but every user-facing candidate requires classification.

## Global behavior inventory

- Audio continuity: provider above router; Stage F mini-player navigation test added.
- Loading: delayed bootstrap test and viewport containment.
- Fatal startup: injected failure, readable error, touch-sized retry, successful recovery.
- Notifications: `MobileToastStack` mirrors successive phone source messages into a bounded three-message accessible stack above fixed navigation. The original desktop single-toast host and desktop CSS remain unchanged. Consecutive-message stacking and viewport containment are automated.
- Restart: screen and polling exist; automated plus physical restart/reconnect evidence remains open.
- Offline/reconnect: controlled startup failure/recovery exists; genuine browser offline, service-worker/cache, and server-restart tests remain open.

## Performance evidence

Stage F records:

- startup/navigation wall-clock and Navigation Timing;
- transferred and decoded bytes;
- JS, CSS, image totals;
- largest resource and resource count;
- Chromium heap where exposed;
- Combat and Travel requestAnimationFrame samples.

These are evidence attachments with catastrophic guards, not approved release budgets. Baseline/candidate review on representative hardware is required.

## Automated test inventory

- `mobile-baseline.spec.ts`
- `mobile-skills.spec.ts`
- `mobile-competencies.spec.ts`
- `mobile-creation.spec.ts`
- `mobile-new-character.spec.ts`
- `mobile-character.spec.ts`
- `mobile-travel.spec.ts`
- `mobile-combat.spec.ts`
- `mobile-combat-roles.spec.ts`
- `mobile-quick-tools.spec.ts`
- `mobile-quick-tools-workflows.spec.ts`
- `mobile-integrated.spec.ts`
- `mobile-stage-f.spec.ts`
- `mobile-stage-f-roles.spec.ts`
- `mobile-modal-audit.spec.ts`
- `mobile-global-behavior.spec.ts`
- `mobile-tablet-management.spec.ts`
- `mobile-performance.spec.ts`

Project matrix:

- protected desktop 1440 × 900;
- desktop evidence 1920 × 1080;
- phone 360 × 740;
- phone 540 × 960;
- phone landscape 740 × 360;
- tablet minimum 768 × 1024;
- tablet portrait 820 × 1180;
- tablet landscape 1180 × 820;
- isolated phone/desktop Master and player sessions.

## Release state

Automated Stage F is in progress. Public activation remains blocked until `Builder_docs/MOBILE_RELEASE_EVIDENCE.md` has no unresolved critical/high item, physical-device coverage is signed, all modal/hover/touch transaction classifications are complete, performance budgets are reviewed, and protected desktop gates remain green.

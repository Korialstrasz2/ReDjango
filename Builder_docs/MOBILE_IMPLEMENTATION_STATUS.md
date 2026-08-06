# ReDjango Mobile Implementation Status

Branch: `mobile-optimized`  
Base: `main` at `da846aca31d31b15e4128f70b0cf0e6cb3b32283`  
Started: 2026-08-05

The public mobile experience remains incomplete and must not be treated as released. Work is isolated on one long-lived implementation branch, and the existing desktop experience remains a protected contract.

## Stage status

| Stage | Status | Notes |
| --- | --- | --- |
| A — Baseline and test harness | In progress | Responsive viewport projects, overflow diagnostics, route-specific tests, independent Combat role sessions, and branch CI are running. Canonical screenshot comparison, all overlays, font scales, and the complete integrated route matrix remain pending. |
| B — Shared responsive primitives | In progress | Responsive hook, modal presentations and stack management, phone app/bottom navigation, More and Quick Tools sheets, full-screen ToolDrawer, Context Notes sheet, phone management guard, and high-risk Travel/Combat phone runtimes are implemented. Formal shell extraction and tablet navigation remain pending. |
| C — Lower-risk player pages | Verified checkpoint | Login, Dashboard, Lore, Guides, Media, Settings, and Market have phone/tablet layouts and responsive Playwright coverage. |
| D — Stateful player pages | Verified checkpoint | Skills, Competencies, Creation, New Character, and Character have dedicated responsive layouts and route-specific Playwright coverage. Character includes real phone touch-drag activation coverage. |
| E — High-risk workspaces/global tools | In progress | Travel is verified. Combat has verified responsive, role-permission, and shared-modal checkpoints covering player/master sessions, map-first phone navigation, touch gestures, inspectors, role-gated controls, nested dialogs, tablet containment, and protected desktop assertions. Remaining exhaustive Combat planner/manager/destructive workflows and Quick Tool internals still require dedicated verification. |
| F — Integrated full-route pass | Not started | Public activation remains blocked. |

## Implemented foundations

### Responsive layout contract

File: `frontend/src/lib/responsive.ts`

- phone-narrow ≤ 479, phone ≤ 767, tablet ≤ 1199, desktop ≥ 1200;
- width is derived with `matchMedia`, not user-agent detection;
- pointer, hover, orientation, and reduced-motion capabilities are tracked separately;
- `useSyncExternalStore` provides a stable React subscription;
- pure boundary tests cover category transitions.

### Playwright viewport and role matrix

Files:

- `frontend/playwright.config.ts`
- `frontend/tests/auth.setup.ts`
- `backend/core/management/commands/ensure_combat_e2e_roles.py`

Coverage now includes:

- canonical `authenticated` desktop at 1440 × 900;
- 1920 × 1080 desktop;
- two phone portrait sizes;
- phone landscape;
- tablet portrait and landscape;
- isolated phone and desktop Combat projects for a real master session;
- isolated phone and desktop Combat projects for a real player session;
- API-level permission assertions and UI-level role assertions.

The Combat role fixture is additive, idempotent, test-only, uses existing seeded characters and map types, and does not change production authorization.

### Responsive modal foundation

Files:

- `frontend/src/components/Modal.tsx`
- `frontend/src/styles/mobile.css`
- `frontend/tests/mobile-combat-roles.spec.ts`

Desktop behavior remains the dialog path, including drag, resize, portal, headless, wide, and themed variants.

Phone behavior provides:

- `responsiveMode="auto | dialog | sheet | fullscreen"`;
- ordinary modal → sheet;
- wide/resizable/headless/body-draggable modal → full-screen;
- no mobile drag/resize;
- body scroll locking with nested-lock accounting;
- safe-area padding, `100dvh`, sticky header/footer, and touch-sized controls.

Shared behavior now provides:

- an explicit modal stack with one interactive top dialog;
- Escape closes only the top dialog;
- Tab and Shift+Tab remain trapped in the top dialog;
- initial focus and exact trigger-focus restoration;
- lower modal layers become `inert` and `aria-hidden` while a child is open;
- backdrop clicks are accepted only by the top dialog;
- wide, resizable, headless, and body-draggable workbenches require an explicit close action by default, protecting local drafts;
- simple dialogs retain backdrop dismissal unless they opt out.

Remaining modal call sites still need final integrated classification, and ad hoc non-`Modal` overlays require separate semantic review.

### Phone shell navigation

Files:

- `frontend/src/features/mobile/MobileNavigation.tsx`
- `frontend/src/features/quick-tools/QuickTools.tsx`
- `frontend/src/styles/mobile.css`

Implemented:

- safe-area-aware fixed app bar;
- persistent Home, Character, Skills, Combat, and More bottom navigation;
- route indication and React Router history;
- full-screen More and Quick Tools sheets;
- workspace offsets around fixed chrome;
- explicit phone management limitation.

The phone link set is still derived from rendered desktop sidebar links. Formal shared navigation-data extraction remains pending.

### Quick Tools and contextual notes

Implemented:

- full-screen phone ToolDrawer presentation for Journal, Dice, AI, Audio, Theft, and Names;
- drag/resize disabled on phones while desktop behavior remains intact;
- body scroll lock, focus restoration, Escape, safe areas, and dynamic viewport height;
- visible phone Context Notes trigger using the existing autosave editor;
- Combat integrates that existing trigger into its local five-action phone navigation, avoiding map-control overlap without duplicating note state.

The internal workflows of each Quick Tool are not yet mobile-complete.

## Verified route checkpoints

### Lower-risk routes

Files include:

- `frontend/src/styles/mobile-pages.css`
- `frontend/src/styles/mobile-lore.css`
- `frontend/src/styles/mobile-reference-pages.css`
- `frontend/tests/mobile-baseline.spec.ts`

Verified routes:

- Login and Dashboard;
- Lore;
- Guides;
- Media;
- Settings;
- Market.

### Stateful routes

Files include:

- `frontend/src/styles/mobile-skills.css`
- `frontend/src/styles/mobile-competencies.css`
- `frontend/src/styles/mobile-creation.css`
- `frontend/src/styles/mobile-new-character.css`
- `frontend/src/styles/mobile-character.css`
- `frontend/src/styles/mobile-character-fixes.css`
- `frontend/tests/mobile-skills.spec.ts`
- `frontend/tests/mobile-competencies.spec.ts`
- `frontend/tests/mobile-creation.spec.ts`
- `frontend/tests/mobile-new-character.spec.ts`
- `frontend/tests/mobile-character.spec.ts`

Verified behavior includes:

- Skills group/family navigation, XP/search/catalog/detail/editor layouts, and touch-safe ordering controls;
- Competencies index, rank controls, techniques, roll workspace, mastery, and history;
- Alchemy, Forge, and Enchant workbenches with contained dense matrices and non-destructive state checks;
- New Character validation, four-step navigation, responsive option lists, sticky actions, and draft preservation;
- Character identity, resources, quick stats, inventory, equipment, containers, coin controls, effects, values, slot picker, and item/overview modal presentations;
- phone Character resource controls exposed without hover;
- figure equipment slots converted from absolute desktop rails into readable phone flow;
- tap selection and picker controls retained alongside drag-and-drop;
- real phone touch-event activation of the existing item drag system;
- desktop Character assertions for sticky HUD, multi-column inventory, and vertical effect rail.

### Travel verified checkpoint

Files:

- `frontend/src/features/mobile/TravelMobileRuntime.tsx`
- `frontend/src/styles/mobile-travel.css`
- `frontend/tests/mobile-travel.spec.ts`
- `frontend/playwright.config.ts`
- `frontend/src/main.tsx`

Verified without changing the desktop Travel controller or declarations:

- map-first phone workspace with a state-preserving full-height controls surface;
- one-finger touch pan, tap selection, double-tap marker editing, and two-finger pinch arbitration;
- explicit zoom and marker-centering controls;
- marker palette taps converted into an explicit map-placement mode while the existing drop/save path remains authoritative;
- safe-area and dynamic-viewport handling in portrait and landscape;
- loading, empty, permission-derived, guide, quality, grid, effect, marker, and active-marker states remain in the shared Travel tree;
- phone focus trapping, Escape/Back behavior, inert map state, and body-scroll locking while controls are open;
- real CDP touch sequences and protected desktop two-column assertions.

### Combat verified responsive and role checkpoint

Files:

- `frontend/src/features/mobile/CombatMobileRuntime.tsx`
- `frontend/src/features/mobile/CombatMobileAttackSync.tsx`
- `frontend/src/features/mobile/CombatMobileNotesBridge.tsx`
- `frontend/src/styles/mobile-combat.css`
- `frontend/src/styles/mobile-combat-fixes.css`
- `frontend/tests/mobile-combat.spec.ts`
- `frontend/tests/mobile-combat-roles.spec.ts`
- `backend/core/management/commands/ensure_combat_e2e_roles.py`
- `frontend/tests/auth.setup.ts`
- `frontend/playwright.config.ts`
- `frontend/src/main.tsx`

The existing `CombatPage.tsx`, `CombatMapCanvas.tsx`, command payloads, mutations, backend authorization, and desktop declarations remain unchanged. The phone runtimes and later-loaded responsive styles provide:

- map-first phone presentation with mounted, state-preserving Map, Character, Active Roster, Attack, and Context Notes access;
- tablet release of forced map minimum widths and a contained overlay for the attack console;
- one-finger map pan and token drag left on the existing pointer controller;
- two-finger pinch arbitration through the existing zoom path, including cancellation of a pending one-finger drag;
- gesture listeners bound to the entire map stage and rebound when the active SVG map changes;
- long-press token context support plus the existing roster-card tap recovery path;
- touch-visible character resource controls, weapon details, roster cards, and attack controls;
- a full-height phone hex inspector that overrides desktop drag coordinates without altering the desktop window;
- attack drawer open/close synchronization, mounted draft preservation, unavailable-panel fallback, and modal-authoritative Escape handling;
- landscape map space protected by moving the duplicated toolbar workflow to the Active Roster panel;
- Context Notes integrated into the local navigation rather than floating above tactical controls;
- empty-map messaging prevented from intercepting map gestures;
- real CDP pinch/token-drag checks, phone panel and inspector checks, tablet containment checks, and desktop workstation assertions;
- independent player/master API permission checks and UI checks;
- player denial of map management verified with a real HTTP 403;
- player-controlled-token and master-all-token movement boundaries;
- role-gated map manager, new-map, character manager, and backup/version controls;
- phone full-screen presentation checks for map editor, character manager, map manager, and quick-action planner.

### Corrected verification record

The workflow originally stopped its explicit Playwright command at `mobile-character.spec.ts`; therefore earlier green runs did not execute the new Travel or Combat suites. The workflow was corrected to run Travel, general Combat, and Combat role suites explicitly. Earlier Travel/Combat run references are not treated as verification evidence.

True verified checkpoint:

- implementation commit: `3ef7012efacb97ef8a21d1695b25060f1a2f4e3f`;
- workflow run: `31050899615`;
- frontend unit tests: passed;
- TypeScript validation: passed;
- production build: passed;
- Django migration consistency and system checks: passed;
- corrected expanded responsive Chromium matrix: passed.

### Shared modal verified checkpoint

Verified on real Combat nested-dialog and wide-workbench paths:

- implementation commit: `7229c668bd39a303df4e76877218e8971b7d6948`;
- workflow run: `31076300535`;
- frontend unit tests: passed;
- TypeScript validation: passed;
- production build: passed;
- Django migration consistency and system checks: passed;
- expanded responsive Chromium matrix: passed;
- phone and desktop master nested-dialog assertions: passed;
- top-only Escape, focus trapping, parent inertness, exact focus restoration, and protected wide backdrop behavior: passed.

These checkpoints do not yet satisfy the complete release gate for every destructive confirmation, every advanced planner/manager mutation, every font scale, every overlay combination, or canonical screenshot comparison.

## Tests and continuous verification

The branch workflow `.github/workflows/mobile-optimization-verification.yml` now runs:

- frontend unit tests;
- TypeScript validation;
- production build;
- Django migration consistency;
- Django system checks;
- lower-risk and stateful responsive suites;
- Travel responsive suite;
- general Combat responsive suite;
- independent player/master Combat role suite.

## Immediate next slice

1. Complete the remaining Combat modal and workflow gate:
   - replace native duplicate-action, clear-queue, and snapshot-restore confirmations with accessible shared dialogs;
   - normalize image-picker preview and other ad hoc dialog overlays through the shared stack;
   - test cancellation, focus restoration, and state preservation for those paths;
   - participant removal, control transfer, activation, defeat, recovery, and relocation flows;
   - target selection and attack preparation across player/master permissions;
   - quick-action planner mutations and validation;
   - map import, version, snapshot, duplicate, editor, background, and deletion workflows;
   - portrait/landscape, larger font scales, overlay stacking, and state preservation;
   - protected canonical desktop screenshots for the same workflows.
2. Audit every Quick Tool internal workflow after Combat reaches the complete gate.
3. Run the integrated Stage F pass across roles, orientations, font scales, overlays, touch drag systems, and canonical desktop screenshots.

## Release block

Do not merge to `main` for public mobile release until every player route, modal, hover-only action, required touch drag system, Combat, Travel, navigation path, role variant, orientation, and desktop non-regression check passes the guide's completeness gate.

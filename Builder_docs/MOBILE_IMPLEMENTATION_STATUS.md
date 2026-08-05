# ReDjango Mobile Implementation Status

Branch: `mobile-optimized`  
Base: `main` at `da846aca31d31b15e4128f70b0cf0e6cb3b32283`  
Started: 2026-08-05

The public mobile experience remains incomplete and must not be treated as released. Work is isolated on one long-lived implementation branch, and the existing desktop experience remains a protected contract.

## Stage status

| Stage | Status | Notes |
| --- | --- | --- |
| A — Baseline and test harness | In progress | Responsive viewport projects, overflow diagnostics, route-specific tests, and branch CI are running. Canonical screenshot comparison, all roles, all overlays, font scales, and the full route matrix remain pending. |
| B — Shared responsive primitives | In progress | Responsive hook, modal presentations, phone app/bottom navigation, More and Quick Tools sheets, full-screen ToolDrawer, Context Notes sheet, and phone management guard are implemented. Formal shell extraction, tablet navigation, and reusable high-risk workspace primitives remain pending. |
| C — Lower-risk player pages | Verified checkpoint | Login, Dashboard, Lore, Guides, Media, Settings, and Market have phone/tablet layouts and responsive Playwright coverage. |
| D — Stateful player pages | Verified checkpoint | Skills, Competencies, Creation, New Character, and Character have dedicated responsive layouts and route-specific Playwright coverage. Character includes real phone touch-drag activation coverage. |
| E — High-risk workspaces/global tools | Started | Quick Tools and ToolDrawer have a phone presentation foundation. Travel, Combat, Journal internals, Dice internals, Audio internals, and the remaining tool workflows still require dedicated implementation. |
| F — Integrated full-route pass | Not started | Public activation remains blocked. |

## Implemented foundations

### Responsive layout contract

File: `frontend/src/lib/responsive.ts`

- phone-narrow ≤ 479, phone ≤ 767, tablet ≤ 1199, desktop ≥ 1200;
- width is derived with `matchMedia`, not user-agent detection;
- pointer, hover, orientation, and reduced-motion capabilities are tracked separately;
- `useSyncExternalStore` provides a stable React subscription;
- pure boundary tests cover category transitions.

### Playwright viewport matrix

File: `frontend/playwright.config.ts`

- canonical `authenticated` desktop project remains 1440 × 900;
- additional projects cover 1920 × 1080 desktop, two phone portraits, phone landscape, tablet portrait, and tablet landscape;
- shared diagnostics measure document and element overflow;
- route suites currently cover baseline/lower-risk pages, Skills, Competencies, Creation, New Character, and Character.

### Responsive modal foundation

Files:

- `frontend/src/components/Modal.tsx`
- `frontend/src/styles/mobile.css`

Desktop behavior remains the dialog path, including drag, resize, Escape, backdrop, portal, headless, wide, and themed variants.

Phone behavior provides:

- `responsiveMode="auto | dialog | sheet | fullscreen"`;
- ordinary modal → sheet;
- wide/resizable/headless/body-draggable modal → full-screen;
- no mobile drag/resize;
- body scroll locking with nested-lock accounting;
- close-button focus and prior-trigger restoration;
- safe-area padding, `100dvh`, sticky header/footer, and touch-sized controls.

Every remaining modal call site still needs final integrated classification and state-loss review.

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
- visible phone Context Notes trigger using the existing autosave editor.

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

## Tests and continuous verification

The branch workflow `.github/workflows/mobile-optimization-verification.yml` runs:

- frontend unit tests;
- TypeScript validation;
- production build;
- Django migration consistency;
- Django system checks;
- the responsive Chromium Playwright matrix.

Latest verified Character checkpoint before this documentation update: commit `2b2e3db9b43014ea950de75dae86a71aa8b4bdb3`. Both workflow jobs completed successfully.

## Immediate next slice

1. Implement Travel as a dedicated phone workspace:
   - full-screen map presentation;
   - marker and route selection without hover;
   - touch pan/zoom arbitration;
   - Back/Close and state preservation;
   - role-specific controls and empty states.
2. Implement Combat only after Travel returns to a green checkpoint:
   - map/token gestures;
   - action and target selection;
   - inspectors and panels;
   - phone navigation and state preservation;
   - player/master variants.
3. Audit every Quick Tool internal workflow.
4. Run the integrated Stage F pass across roles, orientations, font scales, overlays, touch drag systems, and canonical desktop screenshots.

## Release block

Do not merge to `main` for public mobile release until every player route, modal, hover-only action, required touch drag system, Combat, Travel, navigation path, role variant, orientation, and desktop non-regression check passes the guide's completeness gate.

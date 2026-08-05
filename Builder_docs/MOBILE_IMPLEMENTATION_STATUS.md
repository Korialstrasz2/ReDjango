# ReDjango Mobile Implementation Status

Branch: `mobile-optimized`  
Base: `main` at `da846aca31d31b15e4128f70b0cf0e6cb3b32283`  
Started: 2026-08-05

The public mobile experience remains incomplete and must not be treated as released. Work is intentionally isolated on one long-lived implementation branch, with small commits and the existing desktop experience treated as a protected contract.

## Stage status

| Stage | Status | Notes |
| --- | --- | --- |
| A — Baseline and test harness | In progress | Current routes and core overlays inventoried; viewport projects, overflow diagnostics, phone-shell assertions, and management-guard assertions added. Desktop screenshots and the full route/overlay matrix remain pending. |
| B — Shared responsive primitives | In progress | Responsive layout hook, modal presentations, phone app bar, bottom navigation, More sheet, quick-tools sheet, full-screen phone tool drawers, and a shell-level phone management guard are implemented. Formal desktop shell extraction, tablet navigation, contextual-note sheet, and reusable full-screen workspace remain pending. |
| C — Lower-risk player pages | Not started | Login, Dashboard, Lore, Guides, Media, Settings, Market. |
| D — Stateful player pages | Not started | Skills, Competencies, Creation, New Character, Character. |
| E — High-risk workspaces/global tools | Started | Quick Tools and ToolDrawer have a phone presentation foundation. Travel, Combat, Journal internals, Dice internals, Audio layout, and Context Notes still require dedicated audits. |
| F — Integrated full-route pass | Not started | Public activation remains blocked. |

## Implemented foundations

### Responsive layout contract

File: `frontend/src/lib/responsive.ts`

- width categories: phone-narrow ≤ 479, phone ≤ 767, tablet ≤ 1199, desktop ≥ 1200;
- layout is derived with `matchMedia`, not user-agent detection;
- pointer, hover, orientation, and reduced-motion capabilities are separate from layout width;
- React subscription uses `useSyncExternalStore` and a stable serialized snapshot;
- pure boundary tests cover every category transition.

### Playwright viewport matrix

File: `frontend/playwright.config.ts`

- canonical `authenticated` desktop project remains at 1440 × 900 and retains its existing suite;
- baseline-only projects added for 1920 × 1080 desktop, small/large portrait phones, phone landscape, tablet portrait, and tablet landscape;
- new projects currently run only `mobile-baseline.spec.ts` so incomplete page support does not duplicate the entire existing suite prematurely;
- baseline diagnostics attach viewport, touch/capability, and horizontal-overflow data.

### Responsive modal foundation

Files:

- `frontend/src/components/Modal.tsx`
- `frontend/src/styles/mobile.css`
- `frontend/src/main.tsx`

Desktop behavior is preserved:

- existing widths, transforms, drag, resize, Escape, backdrop, portal, headless, wide, and themed behavior remain the dialog path;
- no desktop selector in `app.css` was rewritten.

Phone behavior now provides:

- `responsiveMode="auto | dialog | sheet | fullscreen"`;
- ordinary modal → sheet;
- wide/resizable/headless/body-draggable modal → full-screen;
- drag/resize disabled outside dialog presentation;
- visible close header for formerly headless mobile presentations;
- body scroll lock with nested-lock accounting;
- focus moved to Close and restored to the prior trigger;
- sticky header/footer, safe-area padding, dynamic viewport height, touch-sized close/footer controls;
- `closeOnBackdrop` escape hatch for destructive or dirty forms.

This is a foundation only. Every modal call site still requires explicit classification and state-loss review.

### Phone shell navigation

Files:

- `frontend/src/features/mobile/MobileNavigation.tsx`
- `frontend/src/features/quick-tools/QuickTools.tsx`
- `frontend/src/styles/mobile.css`

Implemented:

- fixed safe-area-aware app bar;
- persistent five-position bottom navigation: Home, active character, Skills, Combat, and More;
- active-route indication and real React Router links;
- full-screen More sheet for the remaining player destinations;
- quick-tools sheet reachable from the app bar;
- phone workspace offsets that keep content clear of both fixed bars;
- mobile touch targets scoped to the phone presentation.

Navigation ordering and role filtering are currently derived from the already-rendered desktop sidebar links. This deliberately avoids duplicating route and permission declarations during the first additive slice. A formal shared navigation-data extraction from `App.tsx` is still required before the shell architecture can be considered final.

### Phone management limitation

Direct `/tools` URLs on a phone now:

- preserve the requested URL;
- preserve the existing permission wrappers;
- hide the compressed management presentation;
- show an explicit tablet/desktop-required screen;
- provide Back and Return to Home actions.

This is implemented at the phone shell layer. The underlying route component is still mounted by the current centralized `App.tsx`; moving the limitation into the route guard remains a later shell-extraction task.

### Quick Tools and ToolDrawer phone presentation

Files:

- `frontend/src/features/quick-tools/QuickTools.tsx`
- `frontend/src/features/quick-tools/ToolDrawer.tsx`

Phone behavior now provides:

- one quick-tools chooser instead of compressing the desktop toolbar;
- full-screen drawers for Journal, Dice, AI, Audio, Theft, and Names;
- drag and resize disabled on phones;
- desktop position and size cleared when entering phone presentation;
- body scroll locking, close-button focus, focus restoration, Escape support, safe areas, and dynamic viewport height.

The internal content of each tool is not yet classified as mobile-complete. Audio mini-player persistence, dense Dice layouts, Journal navigation, and AI forms require separate passes.

## Tests added or extended

- `frontend/src/features/mobile/MobileNavigation.test.tsx` verifies navigation extraction and active-route matching.
- `frontend/tests/mobile-baseline.spec.ts` now checks phone app/bottom bars, More destinations, quick-tools access, desktop/sidebar preservation in non-phone projects, and the direct management-URL limitation.

## Validation state

Validation available from the connector-backed environment:

- repository and write permission confirmed;
- base commit recorded;
- branch creation confirmed;
- changed files re-fetched from `mobile-optimized` after writes;
- branch comparisons can be inspected through the GitHub connector.

Not yet executed:

- `npm ci`;
- `npm run typecheck`;
- `npm test`;
- `npm run build`;
- `npm run test:e2e`;
- desktop screenshot capture.

The execution environment used for these slices cannot clone the repository or install its dependency tree. The checks must run through the repository's normal local or CI environment before the work is considered verified. Test failures must be fixed; desktop snapshots or assertions must not be weakened.

## Immediate next slice

1. Run the complete existing frontend checks and capture the 1440 × 900 desktop baseline in an environment with the repository dependencies.
2. Implement phone-safe Login and Dashboard layouts without changing their desktop presentation.
3. Add a visible mobile Context Notes trigger and sheet.
4. Classify the first lower-risk modal call sites rather than relying only on `responsiveMode="auto"`.
5. Extract shared shell/navigation data from `App.tsx` when a safe full-file refactor and validation environment are available.
6. Begin the lower-risk route sequence: Lore, Guides, Media, Settings, then Market.

## Release block

Mobile public activation remains blocked until every player-facing route, modal, hover-only action, required touch drag system, Combat, Travel, navigation path, and role variant passes the guide's mobile completeness and desktop non-regression gates.

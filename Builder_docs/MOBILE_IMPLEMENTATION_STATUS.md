# ReDjango Mobile Implementation Status

Branch: `mobile-optimized`  
Base: `main` at `da846aca31d31b15e4128f70b0cf0e6cb3b32283`  
Started: 2026-08-05

The public mobile experience remains incomplete and must not be treated as released. Work is intentionally isolated on one long-lived implementation branch, with small commits and the existing desktop experience treated as a protected contract.

## Stage status

| Stage | Status | Notes |
| --- | --- | --- |
| A — Baseline and test harness | In progress | Current routes and core overlays inventoried; viewport projects and overflow diagnostics added. Desktop screenshots and full route/overlay matrix remain pending. |
| B — Shared responsive primitives | Started | `useResponsiveLayout` and the first responsive `Modal` presentation are implemented. Shell, navigation, sheets, full-screen workspace, and phone management guard remain pending. |
| C — Lower-risk player pages | Not started | Login, Dashboard, Lore, Guides, Media, Settings, Market. |
| D — Stateful player pages | Not started | Skills, Competencies, Creation, New Character, Character. |
| E — High-risk workspaces/global tools | Not started | Travel, Combat, Quick Tools, Journal, Dice, Audio, Context Notes. |
| F — Integrated full-route pass | Not started | Public activation remains blocked. |

## Implemented in the initial slice

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

## Validation state

Validation available from the connector-backed environment:

- repository and write permission confirmed;
- base commit recorded;
- branch creation confirmed;
- changed files re-fetched from `mobile-optimized` after writes;
- existing main commit exposes no combined status checks through the connector.

Not yet executed:

- `npm ci`;
- `npm run typecheck`;
- `npm test`;
- `npm run build`;
- `npm run test:e2e`;
- desktop screenshot capture.

The execution environment used for this initial slice cannot clone the repository or install its dependency tree, so those checks must run through the repository's normal local/CI environment before the slice is considered verified. Test failures must be fixed; desktop snapshots or assertions must not be weakened.

## Immediate next slice

1. Run the complete existing frontend checks and capture the 1440 × 900 desktop baseline.
2. Finish the modal call-site inventory and assign `dialog`, `sheet`, or `fullscreen` behavior where `auto` is not sufficient.
3. Extract shared navigation data without changing the desktop `Shell` markup.
4. Add `PhoneShell`, `MobileAppBar`, `MobileBottomNavigation`, and `MoreNavigationSheet` behind width-based presentation selection.
5. Add the intentional phone-only management-route limitation screen.
6. Implement Login and Dashboard as the first visible player routes, then run desktop/mobile screenshot comparison.

## Release block

Mobile public activation remains blocked until every player-facing route, modal, hover-only action, required touch drag system, Combat, Travel, navigation path, and role variant passes the guide's mobile completeness and desktop non-regression gates.

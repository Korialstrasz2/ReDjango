# ReDjango Mobile Implementation Status

Branch: `mobile-optimized`  
Base: `main` at `da846aca31d31b15e4128f70b0cf0e6cb3b32283`  
Started: 2026-08-05

The public mobile experience remains incomplete and must not be treated as released. Work is intentionally isolated on one long-lived implementation branch, with small commits and the existing desktop experience treated as a protected contract.

## Stage status

| Stage | Status | Notes |
| --- | --- | --- |
| A — Baseline and test harness | In progress | Viewport projects, overflow diagnostics, authenticated shell assertions, route-specific phone/tablet checks, and a branch verification workflow are running. Canonical desktop screenshot coverage and the full route/overlay matrix remain pending. |
| B — Shared responsive primitives | In progress | Responsive layout hook, modal presentations, phone app bar, bottom navigation, More sheet, quick-tools sheet, full-screen phone tool drawers, visible Context Notes sheet, and a shell-level phone management guard are implemented. Formal desktop shell extraction, tablet navigation, and reusable full-screen workspace primitives remain pending. |
| C — Lower-risk player pages | Verified checkpoint | Login, Dashboard, Lore, Guides, Media, Settings, and Market have responsive phone/tablet layouts and route-specific Playwright coverage. The current branch head passed unit tests, TypeScript, production build, Django checks, and the responsive browser matrix. Integrated role, font-scale, and cross-route regression coverage remains part of Stage F. |
| D — Stateful player pages | Started | Skills is the next dedicated slice, followed by Competencies, Creation, New Character, and Character. |
| E — High-risk workspaces/global tools | Started | Quick Tools and ToolDrawer have a phone presentation foundation. Travel, Combat, Journal internals, Dice internals, Audio layout, and other tool internals still require dedicated audits. |
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
- baseline-only projects cover 1920 × 1080 desktop, small/large portrait phones, phone landscape, tablet portrait, and tablet landscape;
- shared diagnostics attach viewport, touch/capability, and horizontal-overflow data;
- the mobile baseline now covers the shell, Login, Dashboard, Context Notes, Lore, Guides, Media, Settings, Market, and the phone management limitation.

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

Every modal call site still requires classification and state-loss review before final release.

### Phone shell navigation

Files:

- `frontend/src/features/mobile/MobileNavigation.tsx`
- `frontend/src/features/quick-tools/QuickTools.tsx`
- `frontend/src/styles/mobile.css`

Implemented:

- fixed safe-area-aware app bar;
- persistent five-position bottom navigation: Home, active character, Skills, Combat, and More;
- active-route indication and real React Router links;
- full-screen More sheet for remaining player destinations;
- quick-tools sheet reachable from the app bar;
- phone workspace offsets that keep content clear of both fixed bars;
- mobile touch targets scoped to the phone presentation.

Navigation ordering and role filtering are currently derived from the rendered desktop sidebar links. Formal shared navigation-data extraction from `App.tsx` remains pending.

### Phone management limitation

Direct `/tools` URLs on a phone now:

- preserve the requested URL;
- preserve existing permission wrappers;
- hide the compressed management presentation;
- show an explicit tablet/desktop-required screen;
- provide Back and Return to Home actions.

Moving the limitation into route guards remains a later shell-extraction task.

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

The internal content of each tool is not yet classified as mobile-complete.

### Lower-risk route checkpoint

Files include:

- `frontend/src/styles/mobile-pages.css`
- `frontend/src/styles/mobile-lore.css`
- `frontend/src/styles/mobile-reference-pages.css`
- `frontend/tests/mobile-baseline.spec.ts`

Implemented and matrix-verified:

- phone-safe Login controls and short-landscape scrolling;
- Dashboard single-column selection and touch-sized actions;
- visible phone Context Notes trigger using the existing autosave editor;
- Lore tabs, cards, forms, NPC details, Timeline, and empty states;
- Guides horizontal index, readable documents, variable references, tables, and code overflow;
- Media browse-first layout, filters, upload form, cards, actions, and full-screen preview;
- Settings horizontal tabs, stacked controls, profile/media panels, and save bar above phone navigation;
- Market progressive single-column navigation, catalog, cart, touch controls, and full-screen item/editor modals.

## Tests and continuous verification

The branch workflow `.github/workflows/mobile-optimization-verification.yml` runs:

- frontend unit tests;
- TypeScript validation;
- production build;
- Django migration consistency;
- Django system checks;
- the responsive Chromium Playwright matrix.

Latest verified route checkpoint: commit `0daa4cbc4c3ee26001959dae021f38ebacd7aeec`. Both workflow jobs completed successfully.

## Immediate next slice

1. Audit and implement Skills as a dedicated stateful route:
   - group rail and family navigation;
   - XP ribbon and editor;
   - search and catalog cards;
   - touch-safe ordering controls;
   - detail, unlock, reminder, spell calculator, creation, and management flows.
2. Add populated and empty Skills assertions to the responsive matrix.
3. Continue with Competencies, Creation, New Character, and Character only after Skills returns to a green branch checkpoint.
4. Preserve the existing desktop contract and do not merge to `main` until the full release gate is satisfied.

## Release block

Mobile public activation remains blocked until every player-facing route, modal, hover-only action, required touch drag system, Combat, Travel, navigation path, role variant, orientation, and desktop non-regression check passes the guide's completeness gate.
# ReDjango Mobile Implementation Status

Implementation branch: `mobile-optimized`  
Stage F completion work: `agent/mobile-stage-f-completion` / draft PR #7  
Desktop baseline: `main` at `da846aca31d31b15e4128f70b0cf0e6cb3b32283`  
Updated: 2026-08-06

The mobile implementation is substantial, but the public mobile release is still blocked. Automated coverage has been expanded; physical-device, complete modal/hover classification, and several full transaction matrices still require recorded evidence. Desktop remains a protected contract.

## Stage status

| Stage | Status | Evidence and remaining work |
| --- | --- | --- |
| A — Baseline and test harness | Implemented | Canonical desktop suite, pinned desktop visual comparison, phone/tablet projects, overflow helpers, role sessions, and branch CI exist. Stage F adds a 768px tablet floor and performance/touch evidence attachments. |
| B — Shared responsive primitives | Implemented checkpoint | Responsive hook, shared navigation data, phone app/bottom navigation, More/Quick Tools sheets, responsive Modal stack, phone ToolDrawer, Context Notes sheet, mobile Combat/Travel workspace runtimes, and phone management guards are present. Desktop markup and presentation remain authoritative. |
| C — Lower-risk player pages | Automated checkpoint | Login, Dashboard, Lore, Guides, Media, Settings, and Market have responsive route tests. Physical browser/device variants remain release evidence, not implementation claims. |
| D — Stateful player pages | Automated checkpoint | Skills, Competencies, Creation, New Character, and Character have dedicated responsive suites. Character touch drag activation/cancellation is covered; the complete valid/invalid/swap/auto-scroll matrix remains open. |
| E — High-risk workspaces and tools | Automated checkpoint | Travel and Combat use dedicated phone workspaces and have real touch gesture tests. Quick Tools have full-screen phone drawers and now receive substantive Journal, Dice, Theft, Names, AI, Audio, special-resource, and mini-player workflow tests. Manual Combat/Travel sign-off remains mandatory. |
| F — Integrated full-route pass | In progress | PR #7 adds route, role, orientation-project, accessibility-setting, modal, global-state, tablet-management, Quick Tool workflow, memory/transfer, and map frame-rate evidence. It is not complete until all release blockers below are closed. |

## Current responsive architecture

- `frontend/src/lib/navigation.ts` is the shared source for player and management destinations. Phone and desktop ordering are synchronized from the same data; the old “DOM-derived navigation” note is obsolete.
- `AudioPlayerProvider` remains above `Shell` and `<Routes>`, preserving playback during route changes.
- `frontend/src/components/Modal.tsx` preserves the desktop dialog, drag, resize, wide, headless, and portal behavior. Phone presentations use dialog, sheet, or full-screen modes with modal stacking, focus trapping/restoration, body locking, safe areas, and sticky regions.
- `GameManagerOnly` and `AdminOnly` prevent phone management components from mounting and retain the requested `/tools*` URL while showing Back and Home actions.
- Combat and Travel retain shared controllers/business rules and add phone-specific workspace runtimes rather than rendering duplicate page trees.
- The canonical `authenticated` project and pinned desktop visual-regression workflow remain isolated from the responsive matrix.

## Stage F work in draft PR #7

### Integrated route and accessibility evidence

- every player route loads in compact projects and protected 1920 desktop coverage;
- primary heading, shell/navigation, console errors, document overflow, and fixed-chrome focus covering are checked;
- browser navigation remains covered by `mobile-integrated.spec.ts`;
- all supported font scales (`75`, `85`, `100`, `125`, `150`, `175`) cross all densities (`spacious`, `comfortable`, `compact`, `condensed`);
- visible touch targets are inventoried per route and attached as JSON evidence;
- a true 768 × 1024 tablet project verifies every management route at the supported width floor;
- independent player and Master phone sessions verify route permissions, the management notice, and the direct management limitation.

### Quick Tool workflows

`frontend/tests/mobile-quick-tools-workflows.spec.ts` now exercises more than drawer containment:

- Journal section editing, autosave completion, close/reopen persistence, and the special-resource editor;
- Dice roll execution, local result/history, group history, and session clearing;
- Theft tab changes, circumstances, diversion/manual modifiers, recalculation, and reset;
- Names catalog selection, generation, reroll, and tap-visible culture choices;
- AI submission when a configured chat is present, or the explicit unavailable state when it is not;
- Audio playback, mini-player reachability, route continuity, touch-sized transport controls, navigation clearance, and stop.

### Modal and overlay work

- confirmed defect fixed: phone Audio deletion no longer uses a native browser prompt;
- phone Audio deletion uses the shared compact destructive dialog with explicit close, blocked backdrop dismissal, Escape, focus restoration, and irreversible-action copy;
- desktop Audio deletion retains the original `window.confirm` path, avoiding a desktop interaction change;
- nested Journal special-resource editor containment is exercised;
- the complete repository-wide call-site classification is still open and tracked below.

### Global states and performance evidence

- delayed bootstrap verifies loading-screen viewport containment;
- injected startup failure verifies fatal copy, a touch-sized retry, and successful recovery;
- injected action failure verifies toast placement above phone navigation;
- route/startup wall-clock, navigation timing, JS/CSS/image transfer, largest resource, resource count, and optional Chromium heap are attached;
- Combat and Travel animation-frame samples are attached with a catastrophic minimum guard;
- the limits are safety rails, not final product budgets. Baseline and candidate numbers must be reviewed before release.

## Release blockers

The following prevent a truthful “mobile complete” status:

1. **Physical-device evidence** — iOS Safari narrow/large phone, Android Chrome mid-range phone, Android tablet, iPad Safari portrait/landscape, desktop Chrome/Firefox/WebKit, address-bar collapse, virtual keyboard, password manager, file picker, refresh in nested routes, slow network, real offline/reconnect, large OS text, reduced motion, and touch plus hardware keyboard.
2. **Manual Combat and Travel sign-off** — full participant, attack, token movement, map state, marker, route/journey, guide, empty/loading, and role flows on physical touch hardware.
3. **Complete drag transaction matrix** — Character valid drop, invalid drop, swap, full inventory, locked slot, cancel, auto-scroll, finger offset, and orientation change; Combat committed token move and invalid/cancel paths; Travel committed marker/route interactions and sheet coexistence. Existing tests cover activation/cancel and core map gestures but not every transaction.
4. **Complete modal/overlay classification** — every player-opened `Modal`, `ToolDrawer`, portal, inline `role="dialog"`, native confirmation, and custom overlay must have a recorded phone/tablet/desktop target and tests for keyboard-open state, sticky actions, destructive/dirty behavior, nested pickers, Escape, backdrop, and focus restoration. `CampaignSpecialResources` and AI/custom portals remain explicit audit items.
5. **Complete hover audit** — every visible hover-only action or detail must have a tested tap/focus alternative. Existing Character calculation surfaces, notes, navigation labels, map controls, media actions, campaign weather details, and management controls require a repository-wide evidence report.
6. **Global message stacking and restart evidence** — the current App toast host stores one message at a time; multiple-message stacking is not implemented. The restart screen exists, but automated and physical reconnect evidence is still required.
7. **Performance budget review** — the new measurements must be compared with the pinned desktop baseline and agreed phone budgets. A green catastrophic guard is not release approval.
8. **Documentation completion** — status, inventory, test instructions, and release ledger are updated in PR #7. The main README should link to the final release evidence when the physical-device record is complete.

## Desktop preservation gate

No responsive work may be merged if any of these fail:

- canonical pre-existing desktop tests;
- pinned visual comparisons at protected desktop viewports;
- sidebar order/presentation;
- modal default size, positioning, drag, and resize;
- ToolDrawer drag/resize;
- hover and keyboard behaviors;
- density, font, theme, route, permission, and audio continuity contracts;
- agreed startup, route, memory, and rendering budgets.

Snapshot changes must be reviewed as product changes; snapshots must not be updated merely to make CI pass.

## Verification record

- Draft PR: #7, `agent/mobile-stage-f-completion` → `mobile-optimized`.
- CI status must be read from the PR. Do not copy an older green run into this section as proof for the new Stage F matrix.
- Automated artifacts are uploaded from `frontend/playwright-report` and `frontend/test-results`, including overflow, touch-target, accessibility-profile, route, performance, and frame-rate JSON attachments.
- Manual evidence belongs in `Builder_docs/MOBILE_RELEASE_EVIDENCE.md` and must include device/browser version, viewport/orientation, role, test date, result, issue/trace reference, and tester.

## Release rule

Do not enable or describe the public mobile release as complete until every blocker is closed and both desktop and mobile gates pass. “Mostly responsive” is not a release state.

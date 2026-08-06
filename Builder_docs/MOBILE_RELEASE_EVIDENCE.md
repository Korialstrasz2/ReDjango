# ReDjango Mobile Release Evidence

Status: **BLOCKED — evidence incomplete**  
Implementation branch: `mobile-optimized`  
Stage F audit branch: `agent/mobile-stage-f-completion`  
Draft PR: #7  
Updated: 2026-08-06

This ledger is the release gate. A checked item requires a traceable automated artifact or a named manual record. Do not convert an unchecked item to “not applicable” without documenting the product decision and reviewer.

## Automated gates

| Gate | Evidence source | Status | Notes |
| --- | --- | --- | --- |
| Frontend unit tests | `frontend` CI job | Pending PR #7 | Must pass on candidate SHA. |
| TypeScript | `frontend` CI job | Pending PR #7 | Includes Stage F test sources. |
| Production build | `frontend` CI job | Pending PR #7 | No responsive-only build exception. |
| Django migrations/check | `responsive-e2e` CI job | Pending PR #7 | `makemigrations --check --dry-run` and `manage.py check`. |
| Canonical desktop suite | `desktop-e2e` CI job | Pending PR #7 | Complete pre-existing `authenticated` project. |
| Pinned desktop screenshots | `desktop-visual-regression` CI job | Pending PR #7 | Review changed pixels; do not update snapshots automatically. |
| Responsive route matrix | `mobile-stage-f.spec.ts` | Pending PR #7 | All player routes, headings, console, overflow, focus covering. |
| Browser navigation/history | `mobile-integrated.spec.ts` | Pending PR #7 | Primary/More destinations and Back behavior. |
| Phone/tablet orientations | Playwright projects | Pending PR #7 | 360/540 portrait, 740 landscape, 768/820 portrait, 1180 landscape. |
| Font scale × density | `mobile-stage-f.spec.ts` | Pending PR #7 | 6 scales × 4 densities. |
| Player/Master role matrix | `mobile-stage-f-roles.spec.ts`, Combat roles | Pending PR #7 | Independent sessions and permission behavior. |
| Tablet management floor | `mobile-tablet-management.spec.ts` | Pending PR #7 | Every `/tools*` route at 768px and larger tablets. |
| Quick Tool workflows | `mobile-quick-tools-workflows.spec.ts` | Pending PR #7 | Journal, Dice, Theft, Names, AI, Audio/mini-player. |
| Modal behavior | `mobile-modal-audit.spec.ts`, route suites | Pending PR #7 | Shared stack plus phone Audio destructive conversion. Not yet every call site. |
| Loading/fatal/retry/toast | `mobile-global-behavior.spec.ts` | Pending PR #7 | Controlled network states plus two-message phone stacking and fixed-navigation clearance. |
| Performance evidence | `mobile-performance.spec.ts` | Pending PR #7 | Attachments require review; guards are not approved budgets. |
| Source-level UI audit | `npm run audit:mobile-ui` | Pending PR #7 | Enumerates modal, portal, hover, pointer, touch-action, fixed/sticky, and overflow candidates. |

## Required artifact review

For every PR candidate, record links or artifact names:

| Artifact | Run/link | Reviewer | Result | Notes |
| --- | --- | --- | --- | --- |
| Desktop Playwright report |  |  | ☐ |  |
| Mobile Playwright report |  |  | ☐ |  |
| Desktop visual evidence |  |  | ☐ |  |
| Mobile UI source audit |  |  | ☐ | Every user-facing candidate must be classified. |
| Route/overflow JSON |  |  | ☐ |  |
| Touch-target JSON |  |  | ☐ |  |
| Accessibility-profile JSON |  |  | ☐ |  |
| Performance/transfer JSON |  |  | ☐ |  |
| Combat/Travel frame-rate JSON |  |  | ☐ |  |
| Failed-test traces/screenshots |  |  | ☐ | Must be empty or linked to resolved issues. |

## Manual device matrix

Each row requires device model, OS/browser version, test date, tester, role, orientation, result, and issue/trace reference.

| Device/browser | Required variants | Tester/date | Result | Evidence/issues |
| --- | --- | --- | --- | --- |
| iOS Safari narrow phone | portrait, landscape, address-bar expand/collapse, safe areas, keyboard, password manager |  | ☐ |  |
| iOS Safari large phone | portrait, landscape, nested routes, Back/refresh, audio mini-player |  | ☐ |  |
| Android Chrome mid-range phone | portrait/landscape, touch drag, maps, slow network, memory |  | ☐ |  |
| Android Chrome tablet | minimum supported width, management screens, keyboard |  | ☐ |  |
| iPad Safari | portrait/landscape, management screens, touch + hardware keyboard |  | ☐ |  |
| Desktop Chrome | all protected desktop flows and screenshots |  | ☐ |  |
| Desktop Firefox | routes, modals, drag, audio, shortcuts |  | ☐ |  |
| Desktop Safari/WebKit | routes, modals, audio, shortcuts |  | ☐ |  |

## Manual global-state scenarios

| Scenario | Required result | Status | Evidence/issues |
| --- | --- | --- | --- |
| Browser address bar expands/collapses | no clipped fixed chrome; sheets remain `100dvh`-safe | ☐ |  |
| Virtual keyboard in forms/sheets | active field and sticky actions remain visible | ☐ |  |
| Password manager on Login | no zoom/overlap; errors remain visible | ☐ |  |
| Camera/library file picker | Media upload remains reachable and cancellable | ☐ |  |
| Orientation change | state retained; no dead-end or document overflow | ☐ |  |
| Browser Back from nested view | closes child state first and preserves drafts as specified | ☐ |  |
| Refresh inside nested route | route and permission restore without deadlock | ☐ |  |
| Slow network | loading states remain useful; no duplicate mutation | ☐ |  |
| Server restart | restart screen readable; reconnects automatically | ☐ |  |
| Genuine offline/reconnect | explicit error/recovery; cached behavior matches product promise | ☐ |  |
| Large OS/browser text | no clipped primary actions at all supported scales | ☐ |  |
| Reduced motion | no required information depends on animation | ☐ |  |
| Touch + hardware keyboard | focus/shortcuts/Escape remain predictable | ☐ |  |
| Multiple notifications | messages stack within viewport and clear predictably | ☐ | Automated phone stack is pending CI; physical assistive-technology review remains required. |

## Modal and overlay classification gate

A row is complete only when desktop, phone, tablet, keyboard-open, sticky action, destructive/dirty, nested picker, Escape, backdrop, and focus restoration behavior is recorded and tested where applicable.

| Family | Classification status | Automated | Manual | Open issue |
| --- | --- | --- | --- | --- |
| Shared `Modal` ordinary dialogs | Partial | ☐ | ☐ | Complete all call sites. |
| Shared `Modal` wide/resizable/draggable/headless | Partial | ☐ | ☐ | Verify mobile disablement never affects desktop handlers. |
| ToolDrawer / Quick Tools | Partial | ☐ | ☐ | Internal workflows and keyboard-open states. |
| Character pickers/editors/effects | Partial | ☐ | ☐ | Dirty and nested picker matrix. |
| Skills/Competencies/Creation/New Character | Partial | ☐ | ☐ | Every success/failure/dirty path. |
| Combat overlays/planners/managers | Partial | ☐ | ☐ | Complete destructive and nested state matrix. |
| Travel controls/guide/marker/route overlays | Partial | ☐ | ☐ | Route/journey and committed marker flows. |
| Market/Lore/Media/Guides/Settings | Partial | ☐ | ☐ | Full call-site audit and keyboard-open states. |
| CampaignSpecialResources inline dialog | Open | ☐ | ☐ | Custom overlay requires complete classification. |
| AI custom portal/alerts | Open | ☐ | ☐ | Custom overlay requires complete classification. |
| Native confirmations/alerts | Open | ☐ | ☐ | Audio delete fixed on phone; search and classify remaining calls. |

## Touch drag and map transaction gate

| System | Required scenarios | Automated status | Manual status | Notes |
| --- | --- | --- | --- | --- |
| Character inventory/equipment | scroll without drag, activation, valid, invalid, swap, cancel, auto-scroll, finger offset, orientation, full/locked/magical/quiver/stack rules | Partial | ☐ | Activation/cancel and tap recovery exist; full transaction matrix open. |
| Combat map/tokens | pan, explicit zoom, pinch, select, committed token drag, invalid/cancel, selection mode, panel coexistence, accidental-scroll prevention | Partial | ☐ | Pinch and drag preview/cancel covered. |
| Travel map/markers/routes | pan, zoom, pinch, marker select/place, route interaction, cancel/error, controls coexistence | Partial | ☐ | Pan/pinch/placement mode/cancel covered. |
| Tablet management drag systems | each supported system at 768px and orientation variants | Open | ☐ | Inventory required. |

## Hover and touch-alternative gate

Complete a source-level search for `:hover`, `title`, tooltip, hover-open handlers, `onMouse*`, and pointer-only actions. For every user-visible result, record the tap/focus alternative and its test.

| Area | Status | Evidence/issues |
| --- | --- | --- |
| Shell/navigation/campaign weather | ☐ |  |
| Character/effects/calculation tooltips | ☐ |  |
| Skills/Competencies/Creation | ☐ |  |
| Combat tokens/map/inspectors | ☐ |  |
| Travel markers/map/guide | ☐ |  |
| Market/Lore/Media/Guides | ☐ |  |
| Quick Tools/Context Notes/audio | ☐ |  |
| Tablet management screens | ☐ |  |

## Performance budget approval

Record baseline, candidate, device, methodology, and reviewer. The values below are intentionally blank until measured artifacts exist.

| Metric | Desktop baseline | Desktop candidate | Phone candidate | Approved budget | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Startup |  |  |  |  | ☐ |
| Route transition |  |  |  |  | ☐ |
| Memory after route sequence |  |  |  |  | ☐ |
| Combat frame rate |  |  |  |  | ☐ |
| Travel frame rate |  |  |  |  | ☐ |
| Drag latency |  |  |  |  | ☐ |
| Input latency |  |  |  |  | ☐ |
| CSS parse/style cost |  |  |  |  | ☐ |
| Largest image transfer |  |  |  |  | ☐ |

## Final approvals

- [ ] No critical/high accessibility defect remains.
- [ ] Every player route is complete.
- [ ] Every player-opened modal/overlay is classified and verified.
- [ ] Every hover-only action has a tap/focus alternative.
- [ ] Every required drag system completes real touch transactions.
- [ ] Combat and Travel have dedicated physical-device sign-off.
- [ ] Management routes intentionally handle phones and pass supported tablets.
- [ ] Navigation and browser Back have no dead ends.
- [ ] No content is hidden under fixed bars.
- [ ] No unapproved document-level horizontal overflow remains.
- [ ] Performance budgets are reviewed and accepted.
- [ ] All protected desktop gates pass.
- [ ] Product owner approves activation/removal of the mobile release flag.

Public mobile activation is prohibited until every final approval is checked.

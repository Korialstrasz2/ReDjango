# Frontend Test Guide

## Test layers

- `npm test` — frontend unit tests.
- `npm run typecheck` — TypeScript validation.
- `npm run build` — production asset build.
- `npx playwright test --project=authenticated` — canonical pre-existing desktop suite at 1440 × 900.
- `npx playwright test --config=playwright.desktop-visual.config.ts` — pinned desktop screenshot comparison.
- Stage F responsive suites — phone, tablet, protected desktop, and independent role projects defined in `frontend/playwright.config.ts`.

The Playwright web server resets and seeds `frontend/e2e.sqlite3`; these tests must never target a development or production database.

## Responsive projects

| Project | Viewport/capability | Purpose |
| --- | --- | --- |
| `desktop-1920` | 1920 × 1080 | large protected desktop evidence for responsive suites |
| `phone-small-portrait` | 360 × 740, touch/mobile | narrow phone and full font/density matrix |
| `phone-large-portrait` | 540 × 960, touch/mobile | wide phone, touch-target and performance evidence |
| `phone-landscape` | 740 × 360, touch/mobile | landscape below the phone/tablet boundary |
| `tablet-minimum` | 768 × 1024, touch/mobile | minimum supported tablet and management floor |
| `tablet-portrait` | 820 × 1180, touch/mobile | representative portrait tablet |
| `tablet-landscape` | 1180 × 820, touch/mobile | representative landscape tablet |
| `phone-combat-master` | 390 × 844 | real Master permissions |
| `phone-combat-player` | 390 × 844 | real player permissions |
| desktop role projects | 1440 × 900 | role behavior without phone presentation |

## Stage F suites

- `mobile-integrated.spec.ts` — phone destination ordering, More navigation, browser history, headings, overflow.
- `mobile-stage-f.spec.ts` — all player routes, console errors, fixed-chrome focus, overflow, all font-scale/density combinations, touch-target evidence.
- `mobile-stage-f-roles.spec.ts` — independent player/Master route and management behavior.
- `mobile-tablet-management.spec.ts` — every supported management route at minimum and representative tablet widths.
- `mobile-quick-tools.spec.ts` — drawer presentation, close, focus restoration, containment.
- `mobile-quick-tools-workflows.spec.ts` — Journal/autosave, Dice/history, Theft, Names, AI readiness/submission, Audio continuity and mini-player.
- `mobile-modal-audit.spec.ts` — destructive dialog, backdrop, Escape, focus restoration, nested custom editor containment.
- `mobile-global-behavior.spec.ts` — loading, fatal startup, retry/recovery, toast placement.
- `mobile-performance.spec.ts` — startup/route/transfer/heap evidence and Combat/Travel animation-frame samples.
- route-specific suites — Skills, Competencies, Creation, New Character, Character, Travel, Combat, and role-specific Combat behavior.

## Common commands

Run all responsive and Stage F suites through the configured project matrix:

```bash
cd frontend
npx playwright test \
  tests/mobile-baseline.spec.ts \
  tests/mobile-skills.spec.ts \
  tests/mobile-competencies.spec.ts \
  tests/mobile-creation.spec.ts \
  tests/mobile-new-character.spec.ts \
  tests/mobile-character.spec.ts \
  tests/mobile-travel.spec.ts \
  tests/mobile-combat.spec.ts \
  tests/mobile-combat-roles.spec.ts \
  tests/mobile-quick-tools.spec.ts \
  tests/mobile-quick-tools-workflows.spec.ts \
  tests/mobile-integrated.spec.ts \
  tests/mobile-stage-f.spec.ts \
  tests/mobile-stage-f-roles.spec.ts \
  tests/mobile-modal-audit.spec.ts \
  tests/mobile-global-behavior.spec.ts \
  tests/mobile-tablet-management.spec.ts \
  tests/mobile-performance.spec.ts
```

Run one project while diagnosing a compact-layout failure:

```bash
npx playwright test tests/mobile-stage-f.spec.ts --project=phone-small-portrait
npx playwright test tests/mobile-tablet-management.spec.ts --project=tablet-minimum
```

Run Quick Tool workflows on a representative phone:

```bash
npx playwright test tests/mobile-quick-tools-workflows.spec.ts --project=phone-large-portrait
```

Run the role matrix:

```bash
npx playwright test tests/mobile-combat-roles.spec.ts tests/mobile-stage-f-roles.spec.ts
```

## Evidence attachments

Stage F tests attach JSON to `test-results` and the Playwright report:

- route matrix;
- overflow offenders;
- touch-target inventory and undersized controls;
- font-scale/density profiles;
- tablet management routes;
- startup/navigation/transfer/image/CSS/heap measurements;
- Combat/Travel animation-frame samples.

A green test exit code is not sufficient. Review attachments, traces, screenshots, and desktop visual differences before marking an item complete in `Builder_docs/MOBILE_RELEASE_EVIDENCE.md`.

## Failure rules

- Do not update desktop snapshots solely to make CI green.
- Do not reduce viewports, delete assertions, increase tolerance, or skip a seeded scenario without documenting the product limitation.
- Do not replace touch drag with tap-only tests; tap actions are recovery/accessibility alternatives.
- Do not classify a controlled Chromium network failure as proof of physical offline/server-restart behavior.
- Do not mark manual device rows complete from emulation alone.

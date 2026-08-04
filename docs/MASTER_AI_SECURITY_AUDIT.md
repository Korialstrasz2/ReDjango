# Master AI Proposal System — Security Audit

Date: 2026-08-04  
Branch: `agent/master-ai-proposal-system`  
Pull request: `#2`  
Audited implementation head before this record: `a050cc9dd92756955a5978f49b63da3632e0da6d`

## Scope

This audit covers the four-part Master AI implementation for:

- Item;
- Skill;
- Spell, as a façade over Skill authoring;
- Theme, restricted to Admin users;
- proposer-agent mode and proposal-only tools;
- persisted proposal review, validation, apply, discard, expiry, and audit;
- contextual launchers and browser workflow;
- cleanup, operational logging, API documentation, and regression verification.

It does not authorize support for Unit, Shop, Character, Player, Variables, arbitrary settings, arbitrary Django models, arbitrary ORM paths, raw SQL, or arbitrary Python execution.

## Security invariants reviewed

### 1. The model cannot apply domain changes

**Result: PASS**

- Proposal tools can create, edit, remove, and summarize only `AIChangeSet` and `AIChangeOperation` rows.
- No model-facing tool calls `apply_change_set`.
- The only apply path is the authenticated `POST /api/ai/change-sets/<uuid>/apply/` endpoint.
- The browser apply action sends the signed validation token through a separate explicit user interaction.

### 2. Read-only agents remain read-only

**Result: PASS**

- Proposer tools are marked separately from ordinary read-only tools.
- Tool definition, reachability, and execution all enforce agent mode.
- A corrupted stored tool list cannot make proposal tools available to a read-only agent.
- Ordinary tools remain declared read-only; proposal tools are explicitly non-read-only because they write proposal rows, not domain rows.

### 3. The entity surface is closed and explicit

**Result: PASS**

- The registry accepts only `item`, `skill`, `spell`, and `theme`.
- Handlers declare supported actions, roles, fields, choices, search behavior, snapshots, validation, and apply services.
- Unknown entity types, model names, field paths, context keys, and unsupported launch surfaces fail closed.

### 4. Permissions are rechecked at every boundary

**Result: PASS**

- Proposal creation, search, read, update, archive, validation, and apply use current user and game-role checks.
- Context hints are resolved through the same explicit handler permission boundary.
- Target hints require update access; source/page hints require create access.
- Theme search, proposal, validation, and apply remain Admin-only.
- Normal proposal APIs are owner-scoped; Admin role does not grant access to another user's proposal.

### 5. Hidden and unsupported fields cannot be injected

**Result: PASS**

- Handlers expose explicit editable field sets.
- Unknown proposal fields are rejected during preparation and revalidation.
- Provider secrets, credentials, archive timestamps, internal metadata, arbitrary model fields, and unrestricted relations are not exposed as proposal fields.
- Browser picklists and relation IDs come from server field schemas rather than prompt-maintained constants.

### 6. Apply authorization is short-lived and replay-resistant

**Result: PASS**

The signed token binds:

- proposal ID;
- revision;
- selected ordered operations;
- entity/action/target/source;
- effective values digest;
- target base timestamp and snapshot digest.

Controls:

- every proposal mutation increments revision and clears authorization;
- tokens expire after 15 minutes;
- successful apply clears the token and makes the proposal immutable;
- replay after apply returns conflict;
- stale apply clears the ready token and returns the proposal to draft for explicit revalidation.

### 7. Stale writes cannot overwrite newer records

**Result: PASS**

- Update/archive preparation records both `updated_at` and a canonical digest of the permitted snapshot.
- Apply locks records in deterministic order and compares timestamp and digest.
- Stale targets return HTTP 409 instead of being overwritten.
- The stale response invalidates the previous signed authorization.

### 8. Apply is atomic

**Result: PASS**

- Selected operations execute inside one database transaction.
- Targets are locked before mutation.
- Existing Item, Skill, and Theme domain services perform final writes.
- A later operation failure rolls back earlier writes.
- Delete intent maps to soft archive behavior, never physical deletion.

### 9. Spell authoring preserves the Skill root

**Result: PASS**

- Spell is an explicit proposal façade over a magic Skill.
- Proposal code does not write `SpellDefinition` directly.
- Skill services remain the authoring and transaction root.
- Skill and Spell share conflict detection for target and create-name collisions.

### 10. Proposal audit survives normal conversation lifecycle

**Result: PASS**

- Proposals with operations survive failed or cancelled agent runs.
- Empty failed proposals may be cleaned up.
- Applied, discarded, and expired rows are immutable audit records.
- Discarding a proposal does not delete its conversation.
- Conversation cleanup does not silently remove applied/discarded proposal history.

### 11. Cleanup does not mutate domain data

**Result: PASS**

The management command:

```bash
python manage.py cleanup_ai_change_sets --dry-run
python manage.py cleanup_ai_change_sets --review-days 14 --empty-days 2
```

- deletes only old empty drafts;
- expires abandoned draft/ready proposals;
- clears validation authorization;
- retains applied/discarded rows;
- never deletes Item, Skill, Spell, Theme, provider, user, or conversation records.

No implicit background scheduler was added.

### 12. Operational logs avoid sensitive content

**Result: PASS**

Logged fields are limited to:

- user, agent, run, and proposal identifiers;
- counts by entity/action;
- outcome and error code;
- duration;
- stale-conflict indicator.

Prompts, descriptions, snapshots, proposed values, credentials, provider secrets, and full tool output are not logged by the added operational events.

### 13. Contextual launchers are hints, not authority

**Result: PASS**

- Direct reusable launch buttons exist only on Item, Skill/Spell, and Admin Theme management pages.
- Unsupported management pages have no launcher.
- URL parameters only prefill context and prompt; they do not auto-submit.
- The backend rejects unknown context fields and resolves IDs through permission-aware handlers.
- Display labels remain browser-only and are not sent as authorization context.

### 14. Prompt-injection boundary

**Result: PASS WITH RESIDUAL MODEL RISK**

- The proposer system prompt declares record text untrusted data.
- The model receives only explicit tools and schemas.
- Record content cannot introduce a new tool, bypass handler fields, obtain apply capability, or alter server permission checks.
- A model may still produce a poor proposal after reading adversarial prose; human review and server validation remain mandatory controls.

## Test and verification coverage

The final branch workflow runs:

### Backend

- OpenAPI JSON parsing;
- `makemigrations --check --dry-run`;
- migrations on an isolated database;
- Django system checks;
- all `backend.ai` tests;
- all `backend.core` tests;
- cleanup command dry run.

### Frontend

- Vitest component and API tests;
- TypeScript checking;
- production Vite build.

### Authenticated browser flow

Playwright verifies without contacting an external AI provider:

- manual proposal creation does not mutate the Item catalog;
- validation produces a signed token;
- explicit apply creates the Item;
- token replay fails;
- discard leaves the domain unchanged;
- contextual Item clone navigation carries source context;
- prompt prefill does not auto-submit an AI request;
- Theme launcher is available to the Admin fixture;
- Unit management does not advertise unsupported AI support;
- the Master AI workspace fits a 390 px viewport without horizontal overflow.

## Issues found and corrected during audit

1. The first contextual integration used DOM observation for management-page launchers. It was replaced with direct reusable component integration.
2. Stale apply initially returned conflict without clearing ready authorization. The lifecycle now returns the proposal to draft and clears the token.
3. Clone diff initially compared against an empty record. Clone operations now compare against the captured source snapshot and expose explicit clone intent.
4. The standalone workspace overflowed a narrow mobile viewport. Width containment and wrapping rules were added and retained as an E2E assertion.
5. Existing AI compatibility tests assumed every tool was read-only and directly runnable without context. The invariants now distinguish ordinary read-only tools from proposal-only staging tools while preserving legacy empty-message and permission-error behavior.

## Residual limitations

These are not security bypasses, but they remain implementation constraints:

- Nested Item/Skill/Spell structures use a validated structured-JSON fallback rather than every specialized existing editor.
- The browser E2E fixture deliberately avoids a real external model call; provider protocol behavior remains covered by existing provider tests rather than this proposal-flow test.
- Proposal endpoints are legacy `/api/ai` views, so their contract is versioned in `Builder_docs/openapi-master-ai-proposals.json` instead of the generated Django Ninja `/api/v1` document.
- The feature supports only the four audited entity handlers. Adding another entity requires a new explicit handler, service integration, permissions, tests, documentation, and launcher decision.

## Final assessment

No unresolved Critical or High-severity authorization, direct-write, replay, stale-write, cross-user, or transaction-integrity issue was identified in the audited design.

Merge readiness remains conditional on the final GitHub Actions workflow completing successfully against the audit-record head.

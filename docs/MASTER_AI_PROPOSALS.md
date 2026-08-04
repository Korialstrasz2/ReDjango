# Master AI Proposal System

## Purpose

Master AI is a controlled authoring workflow for ReDjango. A proposer agent may inspect records the current user can manage and persist a draft proposal. It cannot commit Item, Skill, Spell, or Theme changes.

A domain change occurs only after an authenticated human reviews the field-aware proposal, edits it if necessary, validates it, and confirms the dedicated apply request.

The feature intentionally separates:

- `/tools/ai`: provider and agent configuration;
- `/tools/master-ai`: proposal generation, review, validation, apply, discard, and audit;
- contextual buttons on supported management pages: navigation and prompt hints only.

## Security boundary

```text
User request
    |
    v
Proposer agent + explicit proposal tools
    |
    | writes only AIChangeSet / AIChangeOperation
    v
Persisted review queue
    |
    | human edits and validates
    v
Signed apply token
    |
    | explicit authenticated POST /apply/
    v
Atomic apply service
    |
    | existing domain permission + validation services
    v
Item / Skill(+SpellDefinition) / Theme records
```

Non-negotiable rules:

1. No model-facing tool calls the apply service.
2. Proposal tools never execute arbitrary ORM, SQL, Python expressions, model names, or field paths supplied by the model.
3. The entity registry is explicit and closed.
4. The apply service rechecks ownership, role, token, revision, selected operations, values, target versions, and snapshot digests.
5. Every selected operation is committed in one transaction or none are committed.
6. Delete requests map to domain-specific soft archive behavior.
7. Provider secrets, credentials, hidden model fields, and unrestricted metadata are not proposal fields.

## Supported entities and permissions

| Entity | Search/read | Propose | Apply service | Notes |
|---|---|---|---|---|
| Item | Master/Admin | Master/Admin | `item_services` | Create, update, clone, archive |
| Skill | Master/Admin | Master/Admin | `skill_services` | Create, update, clone, archive |
| Spell | Master/Admin | Master/Admin | `skill_services` | Façade over a magic Skill; never writes `SpellDefinition` directly |
| Theme | Admin only | Admin only | `theme_services` | Default and seeded restrictions remain active |

Units, Shops, Characters, Players, Variables, arbitrary settings, and arbitrary Django models are not supported in this release and have no contextual launchers.

## Data model

### `AIChangeSet`

The set is the human review and audit root. It stores:

- owner;
- optional conversation and agent;
- title and original request text;
- safe contextual hint;
- lifecycle status and revision;
- validation summary, signed token, and validation time;
- apply/discard/expiry audit timestamps;
- applying user.

### `AIChangeOperation`

Each operation stores:

- ordered position;
- explicit entity type and action;
- target or source ID;
- source/target snapshot containing only handler-permitted fields;
- AI-proposed values;
- human-edited values;
- server field schema and choices;
- base timestamp and canonical digest;
- validation errors and warnings;
- selected flag and application result.

Effective values are deterministic:

```text
edited values, when present; otherwise proposed values
```

## Lifecycle

```text
                  edit/select/reorder
                 +-------------------+
                 |                   |
                 v                   |
new ----------> draft --validate--> ready
                 |                   |
                 | discard           | apply with valid token
                 v                   v
             discarded            applied
                 
old draft/ready --cleanup--> expired
```

- `draft`, `ready`: editable/reviewable.
- `applied`, `discarded`, `expired`: immutable audit states.
- Every proposal mutation increments the revision and clears validation authorization.
- Validation tokens expire after 15 minutes.
- A stale apply clears the ready token and returns the proposal to draft for explicit revalidation.

## Entity handler contract

Handlers live under `backend/ai/changes/handlers/` and are registered in `backend/ai/changes/registry.py`.

Each handler must provide:

- stable `entity_type`, label, minimum role, and supported actions;
- permission enforcement;
- server-driven field schema and current choices;
- minimal permission-aware search;
- permitted record snapshot and canonical digest;
- non-mutating create/update/archive preparation;
- apply methods that delegate to existing domain services.

A handler must never become a generic model adapter. Registering a Django model is not sufficient authorization or validation.

## Proposal tools

The proposer runtime exposes only these proposal-oriented capabilities:

- list editable entity types;
- search manageable records;
- read an allowed record snapshot;
- propose create, including clone from a source;
- propose update;
- propose archive;
- remove a proposed operation;
- summarize the current proposal.

The runtime enforces proposer mode at tool definition, reachability, and execution. A corrupted read-only agent tool list still cannot expose or invoke proposal tools.

Record text is untrusted data. The proposer system prompt instructs the model not to treat descriptions, notes, lore, or imported text as instructions.

## API contract

All mutation requests use the normal ReDjango CSRF and action-envelope behavior.

```text
GET    /api/ai/change-sets/
POST   /api/ai/change-sets/
GET    /api/ai/change-sets/<uuid>/
PATCH  /api/ai/change-sets/<uuid>/
DELETE /api/ai/change-sets/<uuid>/

POST   /api/ai/change-sets/<uuid>/operations/
PATCH  /api/ai/change-sets/<uuid>/operations/<id>/
DELETE /api/ai/change-sets/<uuid>/operations/<id>/

POST   /api/ai/change-sets/<uuid>/validate/
POST   /api/ai/change-sets/<uuid>/apply/

GET    /api/ai/change-entities/
GET    /api/ai/change-entities/<type>/search/
```

Action names:

```text
ai.changeSet.create
ai.changeSet.update
ai.changeSet.discard
ai.changeOperation.add
ai.changeOperation.update
ai.changeOperation.remove
ai.changeSet.validate
ai.changeSet.apply
```

Important responses:

- validation returns the complete set and an opaque signed token when ready;
- apply returns HTTP 409 for stale/token/revision conflicts;
- normal API access is owner-scoped, including for Admin users;
- entity search is role checked and returns minimal records only.

## Contextual launchers

Supported URL hints:

```text
/tools/master-ai?entity=item&target=123&surface=item-management
/tools/master-ai?entity=item&source=123&surface=item-management
/tools/master-ai?entity=spell&source=456&surface=skill-management
```

The browser may also include a display-only `label` and a prefilled `prompt`. Neither is sent as authorization context.

Safe backend context:

```json
{
  "entityType": "item",
  "targetId": 123,
  "sourceSurface": "item-management"
}
```

Context is a hint only. The backend:

- rejects unknown fields;
- rejects unsupported entity types and surfaces;
- rejects simultaneous target and source;
- checks the current user's handler permission;
- resolves the target/source through the handler;
- caps encoded context size;
- still requires model search/read tools before a proposal operation.

Opening a contextual launcher only prefills the workspace. It never automatically sends a prompt or creates an operation.

## Review workspace

`/tools/master-ai` provides:

- proposer-agent selection;
- persisted conversation and run restoration;
- recent proposal selection;
- operation selection/removal;
- generic field-aware editing using the server schema;
- server-provided choice/relation/image options;
- visible handling of unknown field kinds;
- structured JSON fallback for nested structures;
- authoritative before/after diff;
- source-based clone diff;
- validation problems and warnings;
- explicit apply/discard confirmation;
- immutable applied/discarded/expired audit views.

Apply confirmation lists operation counts, create/update/archive breakdown, archive targets, warnings, and the all-or-nothing transaction rule.

## Concurrency and replay protection

For update/archive operations, preparation records:

- target `updated_at`;
- digest of the permitted snapshot.

Apply:

1. locks the change set and operations;
2. verifies the stored token and signed payload;
3. locks targets in deterministic order;
4. compares timestamp and digest;
5. reruns handler validation and permissions;
6. applies all selected operations atomically.

A token is tied to:

- set ID;
- revision;
- ordered selected operation IDs;
- entity/action/target/source;
- effective value digest;
- base timestamp and digest.

A replay after successful apply fails because the set is immutable and the token is cleared.

## Limits and cleanup

Current limits:

- request text: 8,000 characters;
- operations per set: 50;
- entity query: 160 characters;
- entity results: maximum 25;
- validation token lifetime: 15 minutes;
- safe context: 4 KiB encoded.

Manual cleanup command:

```bash
python manage.py cleanup_ai_change_sets --dry-run
python manage.py cleanup_ai_change_sets --review-days 14 --empty-days 2
```

Policy:

- old empty drafts may be deleted;
- abandoned draft/ready proposals become `expired` and immutable;
- applied and discarded audit rows are retained;
- cleanup never deletes domain records.

No unconfigured background scheduler is installed.

## Operational logging

Safe summary events record:

- user, agent, run/change-set identifiers;
- operation counts by entity/action;
- validation/apply outcome;
- error code;
- duration;
- stale-conflict flag.

Logs do not contain prompts, descriptions, snapshots, proposed values, credentials, or provider secrets.

## Adding another entity

1. Identify the existing management permission.
2. Identify existing domain validation and apply services.
3. Create an explicit handler.
4. Declare safe editable fields and server choices.
5. Implement minimal search and permitted snapshots.
6. Implement non-mutating preparation.
7. Implement apply only through domain services.
8. Add timestamp/digest concurrency checks.
9. Add backend permission, validation, atomicity, and stale tests.
10. Add a specialized frontend widget only where the generic contract is insufficient.
11. Add a contextual launcher only after complete backend and review support exists.

Never add support merely by registering a model.

## Verification checklist

```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py check
python manage.py test backend.ai --verbosity 2
python manage.py test backend.core
python manage.py cleanup_ai_change_sets --dry-run

cd frontend
npm ci
npm test
npm run typecheck
npm run build
```

The branch includes `.github/workflows/master-ai-verification.yml` to run this focused verification on pushes and pull requests.

## Independent audit checklist

- Can a read-only agent reach or call a proposal tool?
- Can any model-facing tool invoke apply directly or indirectly?
- Can a Master create or archive a Theme through raw payloads?
- Can one user read another user's change set?
- Can hidden fields be injected into `editedValues`?
- Can stale targets be overwritten?
- Can a signed token be replayed?
- Can applied/discarded/expired sets be mutated?
- Can conversation cleanup remove proposal audit rows?
- Can a later failure leave earlier domain writes committed?
- Can source text alter tool/system policy?
- Are choices generated by the server rather than duplicated in prompts/browser code?
- Does Spell authoring remain rooted in Skill services?

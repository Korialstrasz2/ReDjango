# Master AI Unit integration

## Scope

The `unit` entity is a first-class Master AI proposal handler for `core.Unit` records.
It supports:

- create;
- clone through create-with-source;
- update;
- archive through the Unit management soft-archive service.

The model never applies a Unit directly. It can only add a persisted operation to an
owner-scoped `AIChangeSet`. The authenticated user must review, edit, validate and
apply the proposal through the normal signed-token workflow.

## Source of truth

Unit authoring follows, in this order:

1. `Builder_docs/UNIT_AUTHORING_GUIDE_FOR_LLM.md`;
2. the current Unit management services and selectors;
3. the real Combat Unit generator;
4. live Skill, Item, race, accessory and configuration records.

The handler uses the management API DTO. It never accepts Django stored-field names,
arbitrary metadata or direct ORM paths from the model.

## Handler

Implementation:

```text
backend/ai/changes/handlers/unit.py
```

The handler delegates permissions and writes to:

```text
backend/combat/unit_management_services.py
  require_unit_manager
  save_managed_unit
  set_managed_unit_archived
  preview_managed_unit

backend/combat/unit_management_selectors.py
  serialize_managed_unit
  unit_management_overview
```

The handler is registered explicitly in `backend/ai/changes/registry.py`. Registering
the Django model alone is not sufficient.

## Editable DTO

The proposal exposes these Unit management fields:

```text
name
category
loreImageId
archetypeDescription
loreDescription
notes
generation
archetypeTags
competenceProfile
skillUnlocks
equipmentSlots
equipmentGroups
accessoryCountByLevel
accessoryProfileKey
innateActions
statProfile
levels
```

`auditPreview` is proposal-only and read-only. It is recalculated by the backend and
is removed before the domain save service is called.

## Discovery contract

The generic entity catalogue contains field schemas for every manageable entity and
can exceed the AI runtime's 24,000-character result budget. Unit authoring therefore
does not depend on receiving the complete generic schema.

`elenca_entita_modificabili` returns a stable `scopertaUnit` instruction. The proposer
then calls the already-authorized generic search tool with:

```json
{
  "tipo": "unit-config",
  "query": "contratto"
}
```

Available bounded sections are:

```text
contratto
progressione
razze_competenze
equipaggiamento
statistiche_creature
```

Each section is generated from live configuration and current services. The equipment
section also exposes the complete active `AccessoryProfile.rules`, not only profile
labels and descriptions. Each response is kept below the normal tool-result budget.
This path remains available to existing proposer agents because it reuses
`cerca_record_gestibili`; no newly selected tool permission is required.

The proposer must:

1. read the `contratto` section and every mechanical section needed by the requested Unit;
2. search and read at least five mechanically comparable Units;
3. search and read every selected Skill through the Skill handler;
4. search and read every selected Item through the Item handler;
5. use only current server choices for Cores, tags, races, subraces, families,
   competences, slots, accessory profiles and stat curves;
6. create a complete DTO rather than a skeleton record.

The Unit editor also uses the existing Unit option endpoint for interactive Skill and
Item searches during human review.

## Validation audit

Every Unit create or update preparation is validated with the real Unit management
save service inside an outer rollback-only transaction. A temporary Unit is saved,
normalized and then exercised through `preview_managed_unit`.

Default named-variant boundary matrix:

```text
1, 3, 5, 6, 7, 9, 10, 11, 12, 15, 20
```

The audit additionally:

- repeats the same named variant at levels 1, 10 and 20 and requires identical output;
- runs three automatic variants at levels 1, 10 and 20;
- records totals, Skill source counts, Perk count, equipment count, innate actions,
  race, XP, competences, stat curves and generator warnings;
- requires a humanoid level-20 result to contain Core and Archetipo purchases;
- requires the complete 20 minor / 10 major Perk path by level 20;
- reports low automatic variation and generator trace warnings as proposal warnings;
- raises a validation error on generator failure or named-variant instability.

`preview_managed_unit` rolls each generated character back. The outer audit transaction
then rolls the temporary Unit or temporary update back. No preview Unit or character
remains stored.

The audit is recalculated when the operation is proposed, edited, validated and again
inside apply preparation. This intentionally favors correctness over cheap validation.

## Review interface

`frontend/src/features/master-ai/UnitProposalEditor.tsx` replaces the generic JSON-only
review for Unit operations. It provides:

- identity, lore, notes and portrait selection;
- creature/humanoid contract switching;
- Core, XP, magic, Class, Religion, race and subrace controls;
- signed tag and competence controls;
- live Skill and Item search;
- Skill pool and equipment band editing;
- shared accessory profile selection;
- explicit group and accessory-band advanced editors;
- creature stat curves and innate-action editors;
- advanced chassis compatibility controls;
- visible rollback audit results.

The editor is selected by the server-provided `unitDefinition` widget. Other entity
handlers continue to use the generic renderer.

## Context launcher

The safe context allowlists now accept:

```text
entityType: unit
sourceSurface: unit-management
```

The Unit management page receives a portal-based `Master AI Unit` launcher. For a
selected saved Unit it supplies the exact target ID, so normal timestamp/digest stale
protection applies. For a new unsaved Unit it supplies Unit scope without a target.
The portal keeps a stable DOM node while the management page updates, avoiding click
races during asynchronous detail rendering.

The current label and prefilled prompt are hints, not authorization; the agent must
still search and read the record through the handler. Opening the launcher never sends
the prompt automatically.

## Security properties

- Master/Admin permission is rechecked by the Unit service.
- The model cannot call apply.
- Unknown top-level Unit fields are rejected.
- `auditPreview` cannot be edited.
- Create/update uses only `save_managed_unit`.
- Archive uses only `set_managed_unit_archived`.
- Update/archive retains timestamp and canonical snapshot stale checks.
- Apply remains atomic across every selected proposal operation.
- Unit previews and temporary records are rolled back.
- Unit discovery is owner/change-set scoped and rechecks Unit permissions.

## Tests

Focused tests live in:

```text
backend/ai/test_master_unit_handler.py
```

They cover:

- explicit registry and server configuration;
- bounded `unit-config` discovery and result-size limits;
- Master-only access;
- create, validate and apply lifecycle;
- real rollback preview execution;
- absence of leaked preview characters;
- read-only audit data;
- Unit soft archive behavior.

Frontend and browser coverage includes:

- specialized Unit proposal rendering and edits;
- Unit launch-context parsing;
- deterministic active Unit fixture;
- selected-Unit target ID and context label;
- stable portal click behavior;
- no automatic prompt submission.

Run:

```bash
python manage.py test backend.ai.test_master_unit_handler --verbosity 2
python manage.py test backend.ai --verbosity 2
python manage.py test backend.combat.tests.UnitGenerationTests --verbosity 2

cd frontend
npm test
npm run typecheck
npm run build
```

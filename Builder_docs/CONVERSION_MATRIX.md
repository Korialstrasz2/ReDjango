# ReDjango Conversion Matrix

Date: 2026-07-17

This is the living parity tracker between `the_elder_django` and ReDjango. A database model alone does not mean a feature is migrated.

## Definition Of Migrated

A feature is complete only when it has the parts it needs from this chain:

```text
legacy analysis -> V2 persistence -> idempotent import -> selector/service -> typed API -> SPA UI -> tests -> data reconciliation
```

Read-only features may omit a mutation service. Features without legacy data may omit an importer. Every intentional omission must be recorded here.

## Current Baseline

- Original database: 68 tables, about 31.8 MB.
- High-gravity original content: 5,887 items, 1,850 shops, 1,476 skills, 1,340 activables, 203 units, 138 lore entries, and 298 lore relations.
- ReDjango database: POC/default seed data only; no rows currently carry `sourceProject = the_elder_django` provenance.
- Current verified UI slices: dashboard/navigation, character selection, complete character overview/inventory/effects workspace, item authoring, unified skill cards and unlocking, Guide, Settings, and UploadedImage Media Vault.
- Combat, units, shops, lore, maps, audio, and AI tools are not yet migrated workflows.

## Domain Matrix

| Domain | Legacy source / volume | V2 persistence | Import | API / service | SPA UI | Tests | Status / next gate |
|---|---|---|---|---|---|---|---|
| Platform shell | 42 templates, 251 routes | Django shell, shared API envelope, hierarchical roles, structured settings, image-backed Theme catalog | n/a | Health/bootstrap/settings plus Ninja `/api/v1/` and OpenAPI generation | React/TypeScript SPA with BrowserRouter, Italian navigation/settings and per-screen themes | Contract, role, theme, settings, generated types, unit and browser tests | Modern SPA foundation complete; split/lazy-load bundles as further domains arrive. |
| Personaggi | `NPC`, `Giocatore` | `Personaggio`, related containers, `Giocatore` | Seed only | Detailed typed selector; atomic overview/resource/rest commands | Selection; overview HUD; resources; statistics; effects; equipment and inventory workspace | Calculation, command/API, POC and Playwright tests | Current sample-data workflow complete; legacy import/reconciliation remains. |
| Diario/note | `Note` fixed text fields | One `Note` document with seven text sections | Seed only | Typed read plus atomic `notes.updateSection` | Global parchment diary; shared autosaving Zaino editor | API validation and Playwright round-trip | Immediate shared-text workflow complete; mount the same editor in Combat, Crafting and Viaggio when those views arrive. |
| Character rules/effects | `Formule`, NPC totals/effects | `GlobalModifiers`, `Effetto`, `EffettiPersonaggio`, `tot`, `effetti_finali` | Defaults only | Safe AST calculation service, atomic refresh | Read-only breakdown surfaces | Focused calculation tests | Strong backend foundation; add imported-formula reconciliation fixtures. |
| Media images | `UploadedImage`, `GlobalImage` | `UploadedImage` | None | List/upload/get/delete working for local images | Media Vault working | Upload/list/delete/error tests | Minimum slice working; image versions, campaign ownership, and legacy import later. |
| Guides | `Guida` | `Guida` | Seed defaults | Bootstrap read | Guide reader | Bootstrap test | Minimum read-only slice working. |
| Items | `Oggetto` / 5,887 | `Oggetto`, `TipoArma` | Sample seed only | Typed catalog plus master/admin create/update/archive services | Search, inspection and complete friendly authoring modal | Permissions, validation, CRUD and frontend compatibility tests | Sample-data workflow complete; idempotent legacy catalog import is next. |
| Skills | `Skill` / 1,477 in the 2026-07-17 snapshot; 79 `FamigliaSkill` under 5 groups; `Attivabile` / 1,342; `EffettiSbloccabili` proposals | Unified `Skill`, grouped `FamigliaSkill`, `SkillPersonaggio` ownership/action configuration; deprecated `EffettiSkill` retained only for compatibility | Family taxonomy and artwork only; the staged, admin-gated process is specified in `SKILL_MIGRATION_GUIDE_FOR_LLM.md` | Typed hierarchical catalog, preview, atomic unlock, PG action configuration and master/admin authoring services | Group → family → card navigation; Skills/Azioni/Analisi Skill PG tabs; explicit passive acceptance | API hierarchy/configuration/permissions/rollback/content tests plus frontend unit and browser checks | Complete curated sample-data workflow. A future importer must be read-only against Elder Django, idempotent, dry-runnable, provenance-preserving, and must quarantine ambiguous mechanics for admin review. |
| Inventory/equipment | `Zaino`, `Faretra`, `Equip` | Legacy-compatible V2 slot fields | Seed only | Atomic assign/swap, bidirectional compatibility, weight and capacity services | DnD plus click movement; named equip, extra slots, magical backpack slots and quiver sections | Atomic rollback, compatibility, capacity, weight payload, unit and browser tests | Interactive sample-data workflow complete; legacy inventory reconciliation remains. |
| Units/bestiary | `Unit` / 203 plus lore/archetypes | `Unit` | None | None | None | None | Migrate after item and skill catalogs. |
| Shops/crafting | `Negozio` / 1,850 plus regional/item rules; 42 `IngredientiAlchimia` | `Negozio`, `Oggetto` profiles, `ContenitoreInventario`, `ReagenteAlchemico` | Idempotent 42-reagent catalog and canonical container stock | Typed Creazione read model; atomic extraction and brew/consume actions | Creazione route with complete Alchimia workbench; Forgiatura and Incantamento staged | Catalog, 12-stock contract, formula, thresholds, rollback, frontend mechanics and browser checks | Alchimia vertical slice complete; migrate forging and enchanting recipes next, then shops. |
| Campaign/lore | 138 entries, 298 relations | `DatiCampagna`, `CampaignLoreEntry`, `CampaignLoreRelation` | None | None | None | None | Build after core compendia and Personaggio mutations. |
| Maps | `CampaignMap`, `GlobalImage` | `DatiMappa`, `UploadedImage` | None | None | None | None | Postpone canvas/realtime work until campaign slice. |
| Audio/messages | `AudioFile`, tags, messages | `AudioFile`, `Messaggio` | None | None | None | None | Later support slice. |
| Timeline/fame | Timeline and hall-of-fame tables | `TimelineEvent`, `HallOfFameCharacter` | None | None | None | None | Later read-only content slice. |
| AI/orchestration | prompts, logs, Comfy/TTS/orchestrator tools | Contract still expects `LLMPrompt`, `LLMLog`, `LogControl`, `ToolControl` | None | None | None | None | Persistence not implemented; intentionally last after background-job design. |
| Combat | large cross-domain workflow | Partial durable data only | None | None | None | None | Intentionally late: depends on characters, rules, effects, inventory, maps, and events. |

## Ordered Migration Queue

1. Stabilize the current working tree and keep this matrix current.
2. Build the idempotent legacy importer framework with dry-run and provenance.
3. Import the complete legacy item catalog into the finished item/inventory workflow.
4. Curate legacy skill content into unified cards only as a separately approved content project, then migrate Units/bestiary.
5. Reconcile legacy characters and their inventory assignments against the completed workspace.
6. Migrate campaign/lore and shops/crafting.
7. Rebuild maps, combat/realtime, and AI/media jobs last.

## Quality Gate Per Slice

- Original source tables/files and minimum useful behavior are documented.
- Imports are read-only against the original project, idempotent, dry-runnable, and provenance-preserving.
- Views stay thin; selectors own reads and services own mutations/transactions.
- The frontend consumes typed, deliberate payloads rather than raw model JSON.
- Reconciliation tests compare imported counts and representative records.
- No legacy feature is declared replaced until its complete user flow works in the SPA.

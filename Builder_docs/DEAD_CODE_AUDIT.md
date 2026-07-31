# ReDjango — Unused Code & Asset Audit

Snapshot taken 2026-07-30, against commit `7e37394`.

**Note on timing:** a concurrent session committed `7e37394` and added
`backend/characters/services/creation.py` + migration `0030` *while this audit was
running*. All findings below were re-verified against the post-commit tree. The
in-flight character-creation work (`NUOVO_PG_PLAN.md`) is deliberately excluded.

Method: AST + reference-graph analysis over 340 Python files, 106 TS/TSX files,
1374 CSS classes, 339 static assets, cross-checked against the SQLite database
for DB-driven references. Every candidate below was manually confirmed.

---

## A. Confirmed dead — safe to remove

### A1. Stale pre-Vite stylesheet (largest single item)

| File | Size | Status |
|---|---|---|
| `frontend/static/frontend/css/app.css` | 840 lines / 18.8 KB | **tracked in git**, superseded |

`frontend/templates/index.html` loads only `frontend/dist/app.css` and
`frontend/dist/app.js`. This file is a leftover from the pre-Vite build and is
referenced by nothing. Last touched Jul 10.

### A2. Self-declared dead constants in `backend/combat/rules.py:22-31`

The file literally labels them: *"Backward-compatible exports for callers that
imported the former constants."* No such callers remain.

- `RESISTANCE_PERCENT` (line 23)
- `TIER_DAMAGE_FORMULAS` (line 27)
- `LEGACY_DAMAGE_MULTIPLIERS` (line 31)

The live source is `backend/combat/damage_rules.py` via `configured_damage_rules()`.

### A3. Dead Python functions (defined once, referenced nowhere)

| Symbol | File |
|---|---|
| `can_use_ai` | `backend/ai/selectors.py:23` |
| `active_combat_buttons_payload` | `backend/characters/services/combat_buttons.py:62` |
| `resolve_formula_overrides` | `backend/characters/services/refresh_personaggio.py:887` |
| `_core_affinity` | `backend/combat/unit_generation.py:488` |
| `parse_loot_level` | `backend/market/generator.py:29` |
| `location_for_shop` | `backend/market/selectors.py:206` |
| `load_approvals` | `backend/combat/legacy_unit_import.py:807` |

Note `parse_loot_level` (singular) is dead; `parse_loot_levels` (plural, line 10)
is live and used by `item_compendium.py` — do not confuse them.

### A4. Dead module-level constants

| Symbol | File |
|---|---|
| `DOSSIER_SCHEMA_KEYS` | `backend/ai/npc_dossier.py:46` |
| `ALL_SCOPES` | `backend/ai/tools.py:1272` |
| `LEGACY_EFFECT_ICONS`, `LEGACY_EFFECT_OPERATIONS`, `LEGACY_FORMULA_GUIDE` | `backend/characters/services/custom_effects.py` |
| `V2_POC_SKILL_DEFAULTS` | `backend/core/defaults.py:1579` |
| `RULE_COST_RE` | `backend/core/legacy_skill_import.py:96` |
| `V2_SCHEMA_VERSION` | `backend/core/models.py:7` |

### A5. Dead TypeScript types

Both in `frontend/src/lib/types.ts`, declared and never referenced anywhere:

- `CompendiumGlossaryEntry`
- `ItemSpecialReason`

### A6. Unused CSS — 73 classes in a 4954-line file

Full list in appendix. The notable cluster:

**10 `.skill-review-*` classes orphaned by a deleted model.** Migration
`core/0040_drop_skill_migration_review.py` (2026-07-29) ran `DeleteModel(SkillMigrationReview)`.
Zero code references remain, but the styles stayed:

`.skill-review-callout`, `.skill-review-comparison`, `.skill-review-filters`,
`.skill-review-issues`, `.skill-review-layout`, `.skill-review-notes`,
`.skill-review-toolbar`, `.skill-workspace-tabs`, `.skill-family-rail`, `.skill-group-nav`

Other clusters: `.combat-*` (25), `.market-*` (11), `.competence-*` (9), `.guide-*` (3).

### A7. Orphaned static assets

Confirmed absent from source **and** from the database:

| File | Size |
|---|---|
| `frontend/static/frontend/images/competencies/backgrounds/arcane-scholar.jpg` | 474 KB |
| `frontend/static/frontend/images/competencies/backgrounds/tamriel-scholar.jpg` | 520 KB |
| `frontend/static/frontend/images/competencies/backgrounds/war-council.jpg` | 439 KB |
| `frontend/static/frontend/images/skills/families/Daedra – Nocturnal 2.png` | 450 KB |

`backend/characters/competence_selectors.py:296` serves backgrounds as
`{index}.jpg for index in range(1, 22)` — strictly numeric, so the three named
files can never be selected. The `Nocturnal 2.png` file is a duplicate-download
artifact sitting beside the live `Daedra – Nocturnal.png`.

### A8. Documentation describing removed schema

- `Builder_docs/V2_DATABASE_STRUCTURE.md:187` — a `### SkillMigrationReview`
  section for a model deleted in migration `core/0040`.
- `Builder_docs/V2_DATABASE_STRUCTURE.md:847` — references `BorsaReagenti`,
  removed in migration `characters/0023_remove_reagent_bag`. No code references remain.
- `Builder_docs/V2_DBSTRUCT - Copy.md` — a stale duplicate of
  `V2_DATABASE_STRUCTURE.md` (30.9 KB vs 53.7 KB, last touched Jun 14 vs Jul 29),
  **tracked in git**, 682 differing lines. The " - Copy" filename is accidental.

---

## B. Probably dead — your call, not mine

### B1. `backend/combat/legacy_unit_import.py` — 917 lines, no Python caller

Not imported by any module, has no management command, and is not in `urls.py`.
Its only documentation is `redjango/ELDER_UNIT_CONVERSION_GUIDE_V2.md`, which
describes invoking `apply_import_run` "or a shell call" — i.e. it is reachable
only by hand from `manage.py shell`.

Public API: `build_import_run`, `write_import_artifacts`, `load_approvals` (dead),
`apply_import_run`, `validate_import_write_path`.

Keep if the Elder unit conversion is still an active pipeline; delete if that
migration is finished.

### B2. Management commands with zero references anywhere

Not mentioned in any doc, `.bat`, or code. They are still invocable by CLI name,
so "unreferenced" means undocumented, not unreachable.

| Command | Lines |
|---|---|
| `backend/lore/management/commands/import_legacy_lore.py` | 31 |
| `backend/lore/management/commands/import_legacy_timeline.py` | 46 |
| `backend/core/management/commands/import_shop_plan.py` | 59 |
| `backend/core/management/commands/import_v2_data.py` | 36 |

`import_v2_data` is the counterpart to `export_v2_data` — check whether the
backup/restore path still needs it before removing.

### B3. `redjango/scripts/` — 8,258 lines of one-off scripts, zero references

| File | Lines |
|---|---|
| `elder_unit_calibration_v2.py` | 4,654 |
| `elder_unit_batch6_v2.py` | 645 |
| `elder_unit_final_batch_v2.py` | 606 |
| `elder_unit_batch2_v2.py` | 588 |
| `elder_unit_batch5_v2.py` | 549 |
| `elder_unit_batch4_v2.py` | 468 |
| `elder_unit_batch3_v2.py` | 415 |
| `rebuild_shop_plan.py` | 246 |
| `rebalance_unit_protection.py` | 87 |

These are dated one-shot data-conversion runs. Their output lives in
`redjango/elder-unit-batch-*-v2/` (168 tracked files, ~5.5 MB) which is also
committed. If the conversion is done, both the scripts and their JSON output are
historical record — consider archiving to a branch or tag rather than keeping in `main`.

### B4. Model fields never read or written

All confirmed unreachable — not accessed dynamically, not exposed via API, not in
the frontend. Each still costs a column and a migration.

| Model | Field | File |
|---|---|---|
| `CampaignLoreRelation` | `activation_context` | `backend/core/models.py:1095` |
| `Giocatore` | `dice_profile` | `backend/core/models.py:97` |
| `Giocatore` | `password_hash` | `backend/core/models.py:80` |
| `Messaggio` | `read_at` | `backend/core/models.py:1118` |
| `Messaggio` | `recipient` | `backend/core/models.py:1106` |
| `DatiMappa` | `canvas_state` | `backend/media_library/models.py:134` |
| `DatiMappa` | `fog_image` | `backend/media_library/models.py:123` |
| `DatiMappa` | `progressi` | `backend/media_library/models.py` |

`Giocatore.password_hash` deserves a second look — it is a dormant credential
column that Django auth does not use. Either it is a legacy import remnant that
should be dropped, or it holds imported hashes that should not be sitting there.

The whole `Messaggio` model is worth reviewing: it appears only in `admin.py` and
`v2_registry.py`, with no selector, service, view, or endpoint. It looks like a
messaging feature that was scaffolded and never built.

### B5. Over-exported symbols (cosmetic)

76 symbols carry `export` but are used only inside their own file — mostly types
in `features/combat/types.ts`, `features/management/types.ts`, `theftRules.ts`,
and `lib/shortcuts.ts`. Harmless, but dropping the keyword shrinks the public
surface and helps future dead-code detection. Not itemised here; regenerate on demand.

---

## C. Repository hygiene (not code, but found on the way)

| Item | Detail |
|---|---|
| `redjango/.git/` | An **empty directory**. Not a submodule, no `.gitmodules`, not a gitlink. Harmless today but it can make git and tooling treat `redjango/` as a nested repo. Delete it. |
| `.git/objects/` | **38 `tmp_obj_*` garbage files** from interrupted operations, and 5,281 loose objects with `size-pack: 0` — the repo has never been packed. `git gc` is overdue. |
| `test-results/` | Untracked and **not gitignored** — only `frontend/test-results/` is covered. Add the root path to `.gitignore`. |
| `backups/` | **1.8 GB**, 58 `db-before-*.sqlite3` snapshots. Gitignored, so this is disk only. |
| `media/` | 355 MB. Gitignored. |
| `Builder_docs/skill_migration_output/` | 14 MB of output from the now-deleted skill-migration-review feature. Gitignored; safe to delete with A6. |
| Root `*.log` | 13 files, 11 of them zero-byte. All gitignored. |
| `shop-import-receipts/` | Exists at root **and** at `redjango/shop-import-receipts/`, both with a `resume-20260726` subdir. Duplicated path — worth confirming which one the importer writes to. |
| `frontend/e2e.sqlite3` | 2.7 MB Playwright fixture DB. Gitignored. |

---

## D. Ruled out — things that look dead but are NOT

Recording these so the next audit does not re-flag them.

| Candidate | Why it is live |
|---|---|
| `ItemSlot50Mixin.slot_1…slot_50` (47 flagged) | Accessed via `getattr(obj, f"slot_{index}")` — `backend/market/services.py:359,374`, `backend/api_v1/tests.py`. |
| `EffectSlot50Mixin.effetto_1…effetto_50` (42 flagged) | Consumed generically via `effetti._meta.get_fields()` — `backend/characters/services/refresh_personaggio.py:1155`. |
| `redjango/runtime_server.py` | Invoked by `start_server.bat:106` as `python -m redjango.runtime_server`. |
| Character portraits in `images/characters/match/` | Resolved by naming convention at runtime — `backend/characters/selectors.py:681`. Characters *Mog gro-Ghor*, *Ra'Zirr*, *Rhyss Arcane* all exist in the DB. |
| 5 item images + `dado_fortunato_di_sanguine.webp` | Referenced from DB rows in `core_oggetto` / `core_opzionetipooggetto`. |
| `Personaggio.caratteristica_preferita` | Newly wired by the concurrent session's `services/creation.py`. |
| `.dice-shape-*`, `.color-*`, `.figure-slot-group-*`, `.figure-slot-rail-*` | Built by template literal; 22 dynamic class prefixes were excluded from the CSS scan. |
| `redjango/settings.py` constants | Consumed by the Django framework, not by name. |

---

## E. Clean bills of health

These came back with nothing, which is worth knowing:

- **API surface** — all 29 `api_v1` routes are called by the frontend; no orphaned endpoints.
- **Ninja schemas** — all 297 classes in `schemas.py` are reachable.
- **URL wiring** — every view in every `urls.py` resolves; no view defined-but-unrouted.
- **Frontend module graph** — no orphaned `.ts`/`.tsx` files; `main.tsx` is the only entry.
- **Migrations** — `makemigrations --check` reports *No changes detected*. No model drift.
- **Dependencies** — all 5 npm runtime deps, all 9 devDeps, and all 7 pip packages are used.

---

## Appendix: full list of 73 unused CSS classes

```
.attack-opponent-hint          .combat-quick-modifier        .market-settings
.attack-result                 .combat-versus                .market-settings-content
.character-combat-buttons      .combat-weapon-actions        .market-shop-rule-editor
.combat-active-focus           .competence-atlas             .market-shop-rules
.combat-active-focus-meta      .competence-card-extra        .market-type-settings
.combat-active-focus-title     .competence-extra-editor      .media-layout
.combat-attack-actions         .competence-lore-grid         .metric-grid
.combat-attack-weapon          .competence-progress-grid     .overlay-fields
.combat-attribute-bonus        .competence-progress-panel    .race-guide-index
.combat-brush-tools            .competence-rank-bar          .settings-admin-tool
.combat-compact-type           .competence-source-list       .skill-action-belt
.combat-damage-presets         .competencies-hero-art        .skill-family-rail
.combat-direct-damage          .competencies-hero-copy       .skill-group-nav
.combat-enemy-effect           .count-badge                  .skill-review-callout
.combat-fast-attack            .danger-confirmation          .skill-review-comparison
.combat-fog-tools              .effect-add                   .skill-review-filters
.combat-hex-drawer             .guide-cross-link             .skill-review-issues
.combat-hex-drawer-body        .guide-implementation-note    .skill-review-layout
.combat-hex-selection          .guide-status-implemented     .skill-review-notes
.combat-modifier-grid          .is-current                   .skill-review-toolbar
.combat-number-grid            .is-previous                  .skill-workspace-tabs
.combat-power-picker           .locked-toggle                .terrain-tag-grid
                               .lore-timeline-header
                               .market-batch-settings
                               .market-density-buttons
                               .market-density-editor
                               .market-setting-add
                               .market-setting-place-list
                               .market-setting-region-buttons
```

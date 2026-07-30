# V2 Schema Changelog

## v0.1 - 2026-06-16

`V2_DATABASE_STRUCTURE.md` is frozen as the initial implementation contract.

Rules for future changes:

- Record the intended schema change here before editing models or migrations.
- State whether the change is additive, a rename, a merge, or a removal.
- Keep migrations additive unless destructive changes are explicitly approved.
- If the feature report disagrees with `V2_DATABASE_STRUCTURE.md`, the structure document wins until this changelog says otherwise.

## v0.2 working implementation - 2026-07-10

Changes represented by migrations already present in the working tree:

- Reshape: replace individual `Personaggio.*_tot` columns with the validated `Personaggio.tot` JSON contract.
- Merge: consolidate duplicate mana-conversion total keys into canonical keys.
- Additive: add `Effetto` as the canonical structured runtime effect definition.
- Additive: add `EffettiPersonaggio` as the legacy-compatible 50-slot assignment container.
- Additive: link `Personaggio.effetti` and store calculated audit/report data in `Personaggio.effetti_finali`.
- Removal: delete the superseded prototype `Character` and `UserMediaAsset` models after the V2 models replaced their proof-of-concept role.

Compatibility decisions:

- `Zaino`, `Faretra`, `EffettiPersonaggio`, and `Equip` keep explicit legacy-compatible persistence fields for the current V2 stage.
- API selectors must expose those fields as arrays or named slot objects; frontend code must not depend on numbered database columns.
- Normalized inventory/equipment slot tables remain a future additive migration, to be introduced only with the inventory mutation slice and a data migration.
- Media Vault uses `UploadedImage` plus existing `metadata` provenance; this adds no schema migration.

## v0.3 hierarchical settings - 2026-07-10

- Rename and formalize the role hierarchy as `user < master < admin`.
- Data migration maps `guest` and `player` to `user`, and `dm` to `master`.
- Add `SettingDefinition` for admin-editable global values, types, choices, role requirements, feature gates, and safe UI tokens.
- Add `SettingOverride` for validated per-Giocatore preferences.
- Preserve the old `Giocatore.settings` JSON field for compatibility, but new application settings must use the structured tables.
- Add a permanent Settings SPA view and expose settings through the standard API envelope.
- Keep the Django Admin link role-gated in the SPA while relying on Django authentication for actual admin authorization.

## v0.4 Italian UI and image-backed themes - 2026-07-10

- Add `Theme` as an administrator-managed catalog with stable slugs, centralized colors, opacity, positioning, blur, and per-screen `UploadedImage` relations.
- Add separate background slots for dashboard, character selection, character sheet, media, guides, settings, dice, and journal.
- Seed three active themes and four optimized, generated WebP placeholder backgrounds without overwriting administrator edits.
- Populate the personal theme selector dynamically from active database rows and validate selected slugs on the backend.
- Make Italian the canonical user-facing language for the SPA, API messages, default guides, administration labels, and launcher output.
- Return role hierarchy labels only to administrators; user and master interfaces render available sections without role tags or badges.

## v0.5 character workspace themes - 2026-07-10

- Add theme colors for PF, Mana, Energia and Potere resource controls.
- Add theme colors for valid and invalid inventory destinations.
- Keep character backgrounds in the existing per-screen `Theme` relationship; the React workspace consumes it through shared theme tokens.
- Set a useful default backpack capacity only when both legacy capacity values are still zero. Existing configured values remain untouched.
- No inventory schema normalization was required: selectors expose deliberate slot DTOs while transactional services preserve the legacy-compatible numbered persistence fields.

## v0.6 immediate character notes - 2026-07-12

- Destructive removal, explicitly approved during active development: delete `JournalEntry` and its titled/card-based workflow.
- Simplify `Note` to seven text fields: `zaino`, `combat`, `crafting`, `viaggio`, `appunti`, `missioni`, and `background`.
- Remove the duplicate `Note.personaggio_ref`, legacy JSON note fields, and unused tracker state; `Personaggio.note` remains the owning relation.
- Replace journal-entry CRUD with `notes.updateSection`, returning the complete current note document.
- Reuse one autosaving frontend editor in the global Diario and contextual game views, beginning with Zaino.

## v0.7 automatic inventory ordering - 2026-07-15

- Data-only migration: compact existing `Zaino` and `Faretra` contents and order them from heaviest to lightest without changing the numbered-slot schema or removing any item.
- Apply the same stable descending-weight order after every backpack or quiver assignment, removal, swap, and cross-container move.
- Preserve the relative order of equal-weight items and keep overflow items in the lightest trailing slots.
- Render the leading magical backpack slots first with the theme's mana-blue highlight, so they visibly contain the heaviest carried items whose weight is ignored.

## v0.8 character-owned custom effects - 2026-07-15

- Add `EffettoPersonalizzato`, owned by one `Personaggio`, with user-facing name, description, origin, icon, temporary marker, and explicit order fields.
- Add `OperazioneEffettoPersonalizzato` for normalized ordered target/operation/value/condition rows. Custom effect rules are not stored in a JSON blob.
- Deliberately omit templates, stacking state, duration counters, lifecycle timestamps, and model timestamps from the new custom-effect persistence.
- Define `temporaneo` as the boolean behind the visible `(t)` suffix only; no remaining-time value is stored or displayed.
- Preserve `Effetto`, `EffettiPersonaggio`, all 50 legacy slots, and their calculation behavior. Editing an active legacy effect promotes only that assignment to the custom tables.
- Extend the typed action API with `effects.create`, `effects.update`, `effects.move`, and custom-aware `effects.remove`; keep `effects.apply` for compatibility with existing catalog data.

## v0.9 effect authoring and terminal overrides - 2026-07-15

- Remove the custom-effect `tipo` field from persistence, API authoring, admin, search, and presentation while leaving the legacy catalog schema intact for imports.
- Expand the code-native icon catalog with one searchable entry per configurable target and more than twenty narrative alternatives; temporary rail icons use a slow red pulse while `(t)` remains a marker only.
- Replace the long target selector with a validated text autocomplete backed by the server-owned allowlist.
- Extend formula and operation guidance with evaluation contexts, accepted fields/operators/functions, examples, and deterministic timing.
- Add `strong_set` as a terminal field-only override applied after fatigue, general modifier, caps, and rounding. Preserve ordinary `set` as the last normal effect operation; for multiple values of either kind, the last applicable effect wins.
- Add an explicit `imposta_forte` contribution to every affected “Come viene calcolato” breakdown so the displayed parts continue to reconcile exactly to the final total.

## v1.0 unified skill cards - 2026-07-17

- Add family artwork and make `Skill` the authoritative aggregate for identity, progression, prerequisites, descriptive details, structured passives, reminder-only active actions, and profile metadata.
- Add `SkillPersonaggio` as the unique ownership and purchase-audit relation between a character and a skill.
- Make unlock one atomic service operation: validate prerequisites and level, validate and deduct the exact XP allocation, require explicit acceptance of every passive, create ownership, and snapshot passive operations into character-owned custom effects.
- Keep active actions non-executable. The SPA exposes them as buttons that reveal their description and fixed costs without spending resources or adding passive effects.
- Retain `EffettiSkill` as a deprecated compatibility table; new authoring and runtime flows do not use it. Do not reproduce the legacy nested `Attivabile` JSON executor.
- Intentionally omit a legacy bulk importer. Family artwork is reused, while skill rules will be curated deliberately from useful descriptions, costs, formulas, and proposed effects.

## v1.1 skill group hierarchy and character actions - 2026-07-17

- Correct the catalog hierarchy to `family group → family → skill`, matching the useful legacy structure instead of treating group labels as families.
- Constrain `FamigliaSkill.gruppo` to Generali, Religioni, Scuole di Magia, Classi, and Perk; seed the 79 real family names and their bundled artwork without importing legacy Skill mechanics.
- Soft-archive the incorrect flat seed categories after moving the five POC skills into real families such as Gestione PA, Combat, Attacchi Melee, Alchimia, and Misticismo.
- Add `SkillPersonaggio.configurazione_azioni` for character-specific action visibility, ordering, and personal notes. Canonical action description, trigger, duration, costs, and metadata remain on `Skill.azioni_attive`.
- Replace the Skills-page action belt with top-level Skills, Azioni, and Analisi Skill PG tabs. The Azioni tab saves presentation configuration; the analysis tab reads normalized ownership.

## v1.2 Elder Skill migration and separate spells - 2026-07-17

- Explicitly approved removal: delete `Skill.riassunto` and the ReDjango-only `Skill.livello_minimo` gate from persistence, API, search, editor, and cards.
- Restore the Elder dynamic PE-price curve. Keep `Skill.costo_pe` as the base price, expose base and calculated prices separately, recompute the calculated price inside the locked unlock transaction, and store its breakdown in ownership metadata.
- Add the Skill-pricing constants to the existing `Formule_base` `GlobalModifiers` admin form.
- Enforce exact relational prerequisites for users; masters and admins may bypass missing prerequisites without bypassing ownership or PE validation.
- Add canonical one-to-one `SpellDefinition` rows with tier, range, safe linear effect formula, legacy provenance, and future-combat configuration. Spell preview is read-only and never spends resources.
- Remove Order/Chaos as a spell classification and price/conversion distinction. Existing unified Mana/Energia/PA/Potere fields are the only runtime contract.
- Treat spell tier as presentation metadata, not an unlock gate; cards receive only slight visual differences per tier.
- Retire POC Skill seeding and archive existing POC Skill rows while preserving characters and `SkillPersonaggio` history.
- Add a read-only-first bulk importer. It imports no characters or ownerships, applies only the `auto_import` queue, and writes ambiguous candidates to review artifacts.

## v1.3 Gestione Skill and persistent Elder review - 2026-07-19

- Normalize the first catalog level into `GruppoFamiglieSkill` and migrate every existing `FamigliaSkill.gruppo` value to a protected foreign key without changing families, skills, spells, or ownerships.
- Archive the nine lowercase prototype groups that are referenced only by already archived flat seed families; their historical links remain intact and can be revealed from the management filter.
- Add the `/tools/skills` SPA workspace with panoramic metrics, a complete searchable catalog, structured Skill editor reuse, and create/edit/archive/restore workflows for groups, families, and skills.
- Add `SkillMigrationReview` for persistent blocked-candidate source snapshots, proposed/working values, findings, notes, status, and the resolved live Skill link.
- Synchronize the review queue from the Elder SQLite database in read-only mode. Common fallback-icon warnings do not bury the 247 actual decision records.
- Require every reviewed import to pass the same canonical Skill and separate Spell validation as normal authoring. Review imports never create characters or `SkillPersonaggio` ownerships.
- Fix repeat analysis after a successful mass import by validating a legacy candidate against its own provenance-linked Skill instance instead of reporting its unchanged name as a duplicate.

## v1.4 Creazione: catalogo e banco Alchimia - 2026-07-22

- Add `ReagenteAlchemico` as the managed global catalog for the 42 named Elder ingredients, constrained to Rosso/Verde/Blu and levels 1–4.
- Make the 12 canonical color/level stacks in personal `ContenitoreInventario` the authoritative reagent contract; migration `characters.0023` removes the redundant reagent bag after preserving unclassified historical keys in container metadata.
- Keep level and color multipliers in `Personaggio.tot`, where skills, equipment, and effects already contribute; the obsolete bag multiplier JSON is not authoritative for new calculations.
- Add a typed read model for `/characters/{id}/creation` plus atomic `alchemy.extract` and `alchemy.brew` actions. A failed or understocked brew does not partially consume inventory.
- Rebuild the first Creazione slice in React with a 3×4 stock matrix, four-slot draft, live formula preview, potion thresholds, historical catalog, and contextual Crafting notes.

## v1.5 item import readiness - 2026-07-22

- Keep exactly four ordered item classifications (`tipo_1...tipo_4`) and remove the unused fifth and sixth fields after confirming that current ReDjango rows contain no values there.
- Add `OpzioneTipoOggetto` as the Django-Admin-managed source for the four picklists; existing ReDjango values are preserved and seeded as options.
- Constrain rarity to the picklist `Unico, 1, 2, 3, 4, 5`, using target value `0` for `Unico` while leaving the eventual meaning of Elder rarity zero for import review.
- Add `effetto_1...effetto_8` as lossless Elder text fields. They remain separate from `Oggetto.effects` and never execute calculations without an explicit conversion.
- Expose positional type values, type options, rarity labels, and Elder effect text through the typed item-management contract and editor.

## v1.6 Alchimia&Contenitori source of truth - 2026-07-27

- Remove `BorsaReagenti` and `Personaggio.borsa_reagenti`; personal `ContenitoreInventario` rows are now the only reagent stock.
- Migrate bag JSON and imported legacy reagent objects into canonical reagent stacks without doubling stock already mirrored by migration 0022.
- Preserve unknown historical reagent keys in container metadata and expand capacity when required so migration never drops a stack.
- Make extraction, brewing, character summaries, imports, seeds, and combat clones operate directly on container entries.
- Normalize legacy `Oggetto` rows such as `Reagente Verde lv 2` into canonical stock when assigned to Alchimia&Contenitori.

## v1.7 curated item special rules - 2026-07-30

- Additive: add `Oggetto.regole_speciali`, free text holding the master-curated, table-readable version of a rule the engine cannot compute (migration `core.0043`). The eight `effetto_1...effetto_8` Elder fields are untouched and remain the provenance record.
- Make the field an input to the `speciale` decision rather than display only: saving it records the Elder texts it covers under `metadata.descriptiveEffectsReviewed`, and `compute_special_reasons` reports `effetti_descrittivi` only for texts absent from that list. Editing an `effetto_N` afterwards returns the item to the review queue, because the new wording is not covered.
- Keep curation and mutation separate: writing the rules removes the reason, the existing `items.recheckSpecial` action clears the flag. Market logic is unchanged; items re-enter shops only by losing `speciale`.
- Expose `specialRules` through the item and compendium contracts, the item editor, the comparer, the compendium sheet, market detail, and the equipment inspector.
- Review procedure, text families, and the 236 items blocked by seven missing effect targets are documented in `ITEM_SPECIAL_RULES_REVIEW_GUIDE.md`.

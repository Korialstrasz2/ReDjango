# The Elder Django V2 Database Structure

Date: 2026-06-14
Schema version: v1.1 working implementation
Status: Evolving implementation contract; changes are recorded in `V2_SCHEMA_CHANGELOG.md`

This document is the v2 database contract. Later schema changes should be deliberate and recorded in `V2_SCHEMA_CHANGELOG.md` before models or migrations are changed.

## Common Fields

Unless a model is explicitly a pure join/slot table, these fields should exist on every v2 table.

| Field | Type | Why it exists |
|---|---|---|
| `id` | UUID or integer primary key | Stable identifier for API routes, relations, imports, and exports. |
| `created_at` | datetime | Lets the app sort newly created content and debug import or generation batches. |
| `updated_at` | datetime | Lets the app refresh cached frontend data and audit recent changes. |
| `archived_at` | datetime nullable | Soft-deletes content without losing campaign history or curated records. |
| `metadata` | JSON, default `{}` | Stores rare or experimental per-row details without creating throwaway columns. |

## Models

### Giocatore

Represents the real human player account and its application security level.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | Human-readable player name used around the table. |
| `display_name` | string nullable | Allows a nicer visible name without changing login identity. |
| `password_hash` | string nullable | Replaces the current plain-ish `psw` field with a safer account credential slot. |
| `role` | enum: `user`, `master`, `admin` | Implements the permanent hierarchical security contract. |
| `active_character_id` | FK to `Personaggio`, nullable | Lets the UI open the player on their current character by default. |
| `character_ids` | JSON | A list of characters' `nome_interno` that the Giocatore has control over and can select. |
| `dice_profile` | string nullable | Preserves the current player dice preference. |
| `settings` | JSON | Compatibility field for rare player metadata; structured application preferences belong in `SettingOverride`. |
| `notes` | JSON | Replaces the old `note_1...note_4` fields with flexible player notes. |

### SettingDefinition

Admin-editable catalog of global baselines, security requirements, feature gates, and safe UI customization tokens.

| Field | Type | Why it exists |
|---|---|---|
| `key` | string unique | Stable dotted identifier used by backend and frontend features. |
| `label` | string | Human-readable name shown in Settings and Django Admin. |
| `category` | string | Groups appearance, accessibility, dice, master, branding, security, and feature settings. |
| `description` | text | Explains intent and future-use constraints. |
| `minimum_role` | enum: `user`, `master`, `admin` | Minimum hierarchical level allowed to see the setting. |
| `value_type` | enum: `bool`, `int`, `string`, `color`, `select`, `json` | Drives backend validation and frontend controls. |
| `default_value` | JSON scalar/object/list | Code-owned fallback and factory default. |
| `value` | JSON nullable | Administrator-owned global baseline; reseeding preserves it. |
| `choices` | JSON list | Allowed select values. |
| `user_customizable` | boolean | Allows user-level personal overrides. |
| `master_customizable` | boolean | Allows master-level personal overrides. |
| `ui_token` | string nullable | Marks a known, safely applied UI customization value. |
| `active` | boolean | Disables a setting without deleting its history. |
| `order` | integer | Stable display order inside a category. |

### SettingOverride

Validated per-player value layered over a `SettingDefinition` global baseline.

| Field | Type | Why it exists |
|---|---|---|
| `setting_id` | FK to `SettingDefinition` | Identifies the stable setting contract. |
| `giocatore_id` | FK to `Giocatore` | Owns the personal override. |
| `value` | JSON scalar/object/list | Stores the validated personal value. |

The pair `(setting_id, giocatore_id)` is unique. Backend services enforce role and customization flags before writes.

### Theme

Admin-editable visual theme selected through `appearance.theme`. Active rows automatically populate the personal theme selector.

| Field | Type | Why it exists |
|---|---|---|
| `slug` | string unique | Stable stored value used by settings and frontend state. |
| `name`, `description` | string/text | Italian display copy maintained by administrators. |
| `is_active`, `is_default`, `order` | boolean/boolean/integer | Controls availability, fallback, and selector ordering. |
| color fields | hex strings | Central tokens for background, panels, text, borders, accent, gold, and sidebar. |
| `overlay_opacity`, `panel_opacity` | decimal 0..1 | Keeps page artwork readable behind content. |
| `background_position`, `background_blur` | string/integer | Controls safe presentation without arbitrary CSS. |
| `*_background_id` | FK to `UploadedImage`, nullable | Distinct images for dashboard, character selection, character sheet, media, guides, settings, dice, and journal. |

Only safe serialized tokens and same-origin media URLs are applied by the SPA. Theme rows never contain executable CSS or JavaScript.

### DatiCampagna

Represents the active campaign and world state.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Names the campaign. |
| `attiva` | boolean | Keeps one campaign as the current active campaign. |
| `meteo` | string nullable | Preserves current weather state for travel, narration, and UI display. |
| `ora_corrente` | string nullable | Stores in-world time in the format you prefer for the table. |
| `giorni_da_inizio` | integer | Supports campaign clocks, travel timelines, and day-reset trackers. |
| `risorse_speciali` | JSON | Supports limited resources such as luck, shared points, or staged resource changes. |
| `default_global_map_id` | FK to `UploadedImage`, nullable | |
| `state` | JSON | Holds campaign-level flags that do not deserve first-class columns yet. |

### GlobalModifiers

Stores global rule profiles, including the merged `Formule` data.

| Field | Type | Why it exists |
|---|---|---|
| `name` | string unique | Allows profiles such as `Formule_base`, `Hardcore`, or campaign variants. |
| `value_float` | JSON | Stores global level values. |
| `value_string` | JSON | Stores global formulas and configurable rule profiles, including `skill_pricing` beside the existing quick-stat settings. |
| `rule_notes` | text nullable | Documents why a modifier exists and when to use it. |

### GruppoFamiglieSkill

First, administrator-managed level of the skill catalog.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | Visible group name. Seeded defaults remain editable. |
| `slug` | string unique | Stable management identity independent of the display order. |
| `ordine` | integer | Controls group order in player and management workspaces. |
| `note` | text nullable | Designer-facing explanation for the group. |

### FamigliaSkill

Groups skills into families, schools, classes, perk tracks, or religions.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | The visible name of the skill family. |
| `gruppo_id` | protected FK to `GruppoFamiglieSkill` | First catalog level. A group contains families; it is never itself rendered as a family. |
| `ordine` | integer | Allows stable ordering in skill trees and management UI. |
| `is_classe` | boolean | Keeps class-like families easy to filter. |
| `is_religione` | boolean | Keeps divine/Daedric/religious tracks easy to filter. |
| `is_perk` | boolean | Keeps perk tracks distinct from ordinary skill groups. |
| `note` | text nullable | Stores designer-facing family notes. |
| `note_addizionali` | text nullable | Preserves secondary notes from the current model. |
| `immagine_id` | FK to `UploadedImage`, nullable | Gives every family curated artwork without embedding media in JSON. |

### Skill

Represents a purchasable or unlockable skill. 

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | The visible skill name. |
| `slug` | string unique | Stable identifier for API payloads, seed updates, and future curated imports. |
| `numero` | integer unique | Preserves existing skill numbering and import stability. |
| `famiglia_id` | FK to `FamigliaSkill`, non nullable | Keeps skill tree grouping. |
| `prerequisiti` | self many-to-many | Stores validated skill prerequisites without parsing prose. |
| `ordine_famiglia` | integer | Supports ordered display inside a family. |
| `costo_pe` | integer | Stores the author-controlled base XP cost. The catalog and unlock service calculate the character-specific price from this value. |
| `tipo_pe` | enum: `all`, `general`, `red`, `green`, `blue` | Defines the XP pools eligible for an exact purchase allocation. |
| `costo_testuale` | string nullable | Preserves human-readable costs such as mana, PA, fatigue, or conditions. |
| `descrizione` | text | Main player-facing skill explanation. |
| `requisiti` | text nullable | Stores prerequisite text until prerequisites become fully structured. |
| `profile_tags` | JSON | Merged `SkillProfileTags`; expected keys include physical, magical, combat, range, area, defense, attack, social, support, exploration, crafting, and control scores. |
| `profile_notes` | text nullable | Replaces `SkillProfileTags.notes`. |
| `effetti_passivi` | JSON list | Contains validated named passive definitions and normalized effect operations authored as part of the skill. |
| `azioni_attive` | JSON list | Contains validated reminder-only actions, descriptions, icons, and fixed displayed costs. |
| `icona` | string nullable | Gives the card and its fallbacks a stable visual marker. |
| `note` | text nullable | Designer-facing note field. |

Skill purchase has no minimum-character-level gate. Relational prerequisites are enforced exactly for users and may be bypassed only by masters and admins. Dynamic pricing restores the Elder curve and reads its configurable constants from `GlobalModifiers.value_string.skill_pricing`; the editor always reads and writes `costo_pe`, never the calculated price.

### SpellDefinition

Defines the spell-only contract separately from ordinary Skill effects. A Skill is magical exactly when it owns one active `SpellDefinition`; no Order/Chaos alignment is stored or applied.

| Field | Type | Why it exists |
|---|---|---|
| `skill_id` | one-to-one FK to `Skill` | Makes spell data a separate canonical definition while retaining Skill as the authoring aggregate. |
| `tier` | enum: `base`, `apprentice`, `master` | Drives spell presentation only; it does not enforce an unlock sequence. |
| `range_text` | string nullable | Preserves human-readable range. |
| `effect_unit` | string | Names the magnitude being configured, such as damage, metres, or turns. |
| `base_mana` | decimal | Fixed Mana offset in the linear formula. |
| `effect_per_mana` | positive decimal | Defines the safe formula `effect = max(0, (mana - base_mana) × effect_per_mana)`. |
| `minimum_mana` | decimal | Supplies the minimum projected Mana requirement. |
| `rounding` | enum | Controls effect presentation without evaluating arbitrary code. |
| `legacy_formula` | string nullable | Preserves the Elder expression for provenance and review only. |
| `cost_notes` | text nullable | Preserves human-readable spell cost qualifications. |
| `combat_configuration` | JSON | Marks the definition as prepared for combat while explicitly keeping resource mutation disabled. |

Spell previews are read-only. They may project unified Mana, Energia, PA, and Potere conversions, but the combat subsystem will decide which resource option to use and when to persist a spend.

### SkillMigrationReview

Persistent review desk for Elder candidates that were not safe to auto-import. It stores no character or ownership data.

| Field | Type | Why it exists |
|---|---|---|
| `source_project`, `source_id` | unique source identity | Keeps the queue repeatable and links a decision to one Elder row. |
| `nome`, `severity`, `decision`, `status` | review state | Supports blocked/open/imported/ignored filtering without changing live Skill state. |
| `blockers`, `warnings` | JSON lists | Preserves machine-readable analyzer findings and their UI explanations. |
| `suggested_values` | JSON object | Immutable-style latest proposal rebuilt from the source. |
| `working_values` | JSON object | Stores the master's editable correction before import. |
| `source_snapshot` | JSON object | Keeps the exact Elder fields visible for side-by-side comparison. |
| `edited`, `resolution_notes` | audit fields | Distinguishes an untouched proposal and records the review decision. |
| `resolved_skill_id` | nullable FK to `Skill` | Links the review to the created or corrected live Skill. |

Queue synchronization reads the Elder database in read-only mode. A corrected record is imported through the canonical Skill validator, retains source provenance, and never creates a `SkillPersonaggio` row.

### SkillPersonaggio

Records the atomic purchase of one skill by one character. It stores ownership and the purchase audit only; all current player-facing content still comes from `Skill`.

| Field | Type | Why it exists |
|---|---|---|
| `personaggio_id` | FK to `Personaggio` | Gives the purchase one character owner. |
| `skill_id` | FK to `Skill` | Identifies the unified skill definition that was unlocked. |
| `spesa_pe` | JSON | Audits the exact general/red/green/blue XP allocation deducted by the service. |
| `passivi_accettati` | JSON list | Records the stable passive IDs the player explicitly accepted at unlock time. |
| `configurazione_azioni` | JSON object | Stores character-only visibility, order, and personal note keyed by canonical Skill action ID. It never stores or overrides action mechanics. |
| `note` | text nullable | Allows rare purchase-specific administrative notes without duplicating skill content. |

The pair `(personaggio_id, skill_id)` is unique. Unlocking also snapshots accepted passives into the character's normalized custom-effect rows; active actions remain live reminder content derived from the owned `Skill`.

### EffettiSkill

Deprecated compatibility model from the earlier V2 design. It remains in the additive schema so existing development data is not destroyed, but unified skill authoring and unlocking do not read or write it. `Skill.effetti_passivi` and `Skill.azioni_attive` replace it for all new work.

| Field | Type | Why it exists |
|---|---|---|
| `skill_id` | FK to `Skill`, nullable | Links the effect/action to the skill that grants it. |
| `nome` | string | Visible effect or action name. |
| `fonte_tipo` | enum: `skill`, `razza`, `subrazza`, `manuale`, `unit`, `oggetto` | Preserves the old source model while allowing new sources. |
| `fonte_nome` | string nullable | Stores the source label when no direct FK exists. |
| `tipo` | enum: `passivo`, `attivabile`, `ibrido` | Distinguishes permanent bonuses from manual actions. |
| `descrizione` | text | Player/DM-facing explanation of the effect. |
| `note_proposte` | text | Notes to be added to the Player upon unlocking the skill, if any. |
| `costi` | JSON | Replaces `costo_pf`, `costo_man`, `costo_en`, `costo_pow`, `costo_pa`, and `costo_st`. |
| `durata_turni` | integer nullable | Supports temporary effects and timed actions. |
| `messaggi` | JSON | Replaces execution/end-turn message fields. |
| `icona` | string nullable | Supports action buttons and skill UI. |
| `effect_payload` | JSON | Structured rules payload applied by the rules engine. |

### Effetto

Canonical structured effect definition used by active character-effect slots and the calculation service.

| Field | Type | Why it exists |
|---|---|---|
| `tipo` | string nullable | Groups runtime effects for filtering and display. |
| `nome` | string unique | Stable visible effect name. |
| `descrizione` | text | Human-readable rules and fiction text. |
| `effect_payload` | JSON | Structured operations and optional formula overrides consumed by the rules engine. |
| `durata_turni` | integer nullable | Stores a default or current duration when the definition is time-bound. |
| `stacking_rule` | string nullable | Describes stacking, refresh, replace, or blocking behavior. |
| `icona` | string nullable | Supports condition chips and combat UI. |
| `origine_tipo` | string nullable | Records whether the effect came from an item, skill, manual action, or other domain. |
| `origine_nome` | string nullable | Human-readable source name for provenance and debugging. |
| `notes` | text nullable | Designer-facing notes. |

### EffettiEMalattie

Canonical table for non-skill effects, status conditions, diseases, injuries, and environmental effects.

| Field | Type | Why it exists |
|---|---|---|
| `tipo` | enum/string | Separates effect, disease, injury, curse, blessing, weather, or environment. |
| `nome` | string unique | The visible effect name used by autocomplete and character state. |
| `descrizione` | text | Human-readable rules and fiction text. |
| `effect_payload` | JSON | Structured rules payload applied by the rules engine. |
| `default_duration_turns` | integer nullable | Provides a default for temporary conditions. |
| `stacking_rule` | enum/string | Defines whether duplicates stack, refresh, replace, or are blocked. |
| `icon` | string nullable | Supports condition chips and combat UI. |


### Competenze

Catalog of non-combat abilities and checks.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | Visible competence/check name. |
| `descrizione` | text | Explains what the competence covers. |
| `mapping_tag` | JSON | Links the competence to skill profile tags, stats, or AI recommendation categories. |
| `ordine` | integer | Keeps the character sheet stable and readable. |
| `categoria` | string nullable | Groups social, survival, knowledge, stealth, crafting, or movement checks. |

### TipoArma

Weapon category metadata.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | Weapon type name such as sword, dagger, bow, or mace. |
| `lunghezza` | string nullable | Preserves reach/length category. |
| `potenza` | string nullable | Preserves weapon power category. |
| `bonus_1` | string nullable | Stores first category-specific weapon trait. |
| `bonus_2` | string nullable | Stores second category-specific weapon trait. |
| `rules` | JSON | Allows future weapon-type rules without adding columns. |

### Oggetto

Item catalog. `IngredientiAlchimia` is merged here.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | Item name. |
| `modello` | boolean | Distinguishes reusable item templates from instantiated campaign items. |
| `temporaneo` | boolean | Marks temporary/generated items. |
| `archiviato` | boolean | Keeps old items hidden without deleting them. |
| `numero_ordine` | integer nullable | Supports manual ordering in item manager. |
| `icona` | string nullable | Supports inventory and equipment UI. |
| `tipo_1` | string nullable | Supports inventory and equipment UI. |
| `tipo_2` | string nullable | Supports inventory and equipment UI. |
| `tipo_3` | string nullable | Supports inventory and equipment UI. |
| `tipo_4` | string nullable | Supports inventory and equipment UI. |
| `descrizione` | text nullable | Player/DM-facing item description. |
| `valore` | integer nullable | Item value for shops and loot. |
| `peso` | float nullable | Item weight for carry capacity. |
| `rarita` | integer nullable, choice | `0` means Unico; `1...5` are the numbered rarity tiers. |
| `lv_loot` | string nullable | Preserves current loot level bands. |
| `regione_loot` | string nullable | Keeps regional weighting without needing a `Regione` table. |
| `peso_regione` | float nullable | Controls how strongly the item is favored in its region. |
| `tipo_arma_id` | FK to `TipoArma`, nullable | Links weapons to weapon-category rules. |
| `pa_per_attacco` | integer nullable | Stores item-specific attack action cost. |
| `effetto_1...effetto_8` | string | Preserves Elder effect text losslessly for migration review; it does not run calculations. |
| `effects` | JSON | Stores validated structured item effects used by calculations. |
| `alchemy_profile` | JSON | Merged `IngredientiAlchimia`; stores reagent type, color, tier, category, and crafting metadata. |
| `crafting_profile` | JSON | Stores forge/enchant/alchemy requirements, outputs, and tool interactions. |
| `media_id` | FK to `UploadedImage`, nullable | Allows item images without hardcoding paths. |
| `notes` | text nullable | Designer-facing item notes. |

### OpzioneTipoOggetto

Administrator-managed picklist entries for each of the four ordered `Oggetto.tipo_*` fields. `posizione` identifies Tipo 1-4; `valore` is the stable stored value; `etichetta`, `attiva`, and `ordine` control presentation without hard-coding choices in the SPA.

### Zaino

Character backpack, kept as a named object with explicit item slots.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Visible backpack name. |
| `slot_1` | FK to `Oggetto`, nullable | Stores the item in backpack slot 1. |
| `slot_2` | FK to `Oggetto`, nullable | Stores the item in backpack slot 2. |
| `slot_3` | FK to `Oggetto`, nullable | Stores the item in backpack slot 3. |
| `slot_4` | FK to `Oggetto`, nullable | Stores the item in backpack slot 4. |
| `slot_5` | FK to `Oggetto`, nullable | Stores the item in backpack slot 5. |
| `slot_6` | FK to `Oggetto`, nullable | Stores the item in backpack slot 6. |
| `slot_7` | FK to `Oggetto`, nullable | Stores the item in backpack slot 7. |
| `slot_8` | FK to `Oggetto`, nullable | Stores the item in backpack slot 8. |
| `slot_9` | FK to `Oggetto`, nullable | Stores the item in backpack slot 9. |
| `slot_10` | FK to `Oggetto`, nullable | Stores the item in backpack slot 10. |
| `slot_11` | FK to `Oggetto`, nullable | Stores the item in backpack slot 11. |
| `slot_12` | FK to `Oggetto`, nullable | Stores the item in backpack slot 12. |
| `slot_13` | FK to `Oggetto`, nullable | Stores the item in backpack slot 13. |
| `slot_14` | FK to `Oggetto`, nullable | Stores the item in backpack slot 14. |
| `slot_15` | FK to `Oggetto`, nullable | Stores the item in backpack slot 15. |
| `slot_16` | FK to `Oggetto`, nullable | Stores the item in backpack slot 16. |
| `slot_17` | FK to `Oggetto`, nullable | Stores the item in backpack slot 17. |
| `slot_18` | FK to `Oggetto`, nullable | Stores the item in backpack slot 18. |
| `slot_19` | FK to `Oggetto`, nullable | Stores the item in backpack slot 19. |
| `slot_20` | FK to `Oggetto`, nullable | Stores the item in backpack slot 20. |
| `slot_21` | FK to `Oggetto`, nullable | Stores the item in backpack slot 21. |
| `slot_22` | FK to `Oggetto`, nullable | Stores the item in backpack slot 22. |
| `slot_23` | FK to `Oggetto`, nullable | Stores the item in backpack slot 23. |
| `slot_24` | FK to `Oggetto`, nullable | Stores the item in backpack slot 24. |
| `slot_25` | FK to `Oggetto`, nullable | Stores the item in backpack slot 25. |
| `slot_26` | FK to `Oggetto`, nullable | Stores the item in backpack slot 26. |
| `slot_27` | FK to `Oggetto`, nullable | Stores the item in backpack slot 27. |
| `slot_28` | FK to `Oggetto`, nullable | Stores the item in backpack slot 28. |
| `slot_29` | FK to `Oggetto`, nullable | Stores the item in backpack slot 29. |
| `slot_30` | FK to `Oggetto`, nullable | Stores the item in backpack slot 30. |
| `slot_31` | FK to `Oggetto`, nullable | Stores the item in backpack slot 31. |
| `slot_32` | FK to `Oggetto`, nullable | Stores the item in backpack slot 32. |
| `slot_33` | FK to `Oggetto`, nullable | Stores the item in backpack slot 33. |
| `slot_34` | FK to `Oggetto`, nullable | Stores the item in backpack slot 34. |
| `slot_35` | FK to `Oggetto`, nullable | Stores the item in backpack slot 35. |
| `slot_36` | FK to `Oggetto`, nullable | Stores the item in backpack slot 36. |
| `slot_37` | FK to `Oggetto`, nullable | Stores the item in backpack slot 37. |
| `slot_38` | FK to `Oggetto`, nullable | Stores the item in backpack slot 38. |
| `slot_39` | FK to `Oggetto`, nullable | Stores the item in backpack slot 39. |
| `slot_40` | FK to `Oggetto`, nullable | Stores the item in backpack slot 40. |
| `slot_41` | FK to `Oggetto`, nullable | Stores the item in backpack slot 41. |
| `slot_42` | FK to `Oggetto`, nullable | Stores the item in backpack slot 42. |
| `slot_43` | FK to `Oggetto`, nullable | Stores the item in backpack slot 43. |
| `slot_44` | FK to `Oggetto`, nullable | Stores the item in backpack slot 44. |
| `slot_45` | FK to `Oggetto`, nullable | Stores the item in backpack slot 45. |
| `slot_46` | FK to `Oggetto`, nullable | Stores the item in backpack slot 46. |
| `slot_47` | FK to `Oggetto`, nullable | Stores the item in backpack slot 47. |
| `slot_48` | FK to `Oggetto`, nullable | Stores the item in backpack slot 48. |
| `slot_49` | FK to `Oggetto`, nullable | Stores the item in backpack slot 49. |
| `slot_50` | FK to `Oggetto`, nullable | Stores the item in backpack slot 50. |

### Faretra

Arrow and projectile container, kept as a named object with explicit item slots.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Visible quiver name. |
| `slot_1` | FK to `Oggetto`, nullable | Stores the item in quiver slot 1. |
| `slot_2` | FK to `Oggetto`, nullable | Stores the item in quiver slot 2. |
| `slot_3` | FK to `Oggetto`, nullable | Stores the item in quiver slot 3. |
| `slot_4` | FK to `Oggetto`, nullable | Stores the item in quiver slot 4. |
| `slot_5` | FK to `Oggetto`, nullable | Stores the item in quiver slot 5. |
| `slot_6` | FK to `Oggetto`, nullable | Stores the item in quiver slot 6. |
| `slot_7` | FK to `Oggetto`, nullable | Stores the item in quiver slot 7. |
| `slot_8` | FK to `Oggetto`, nullable | Stores the item in quiver slot 8. |
| `slot_9` | FK to `Oggetto`, nullable | Stores the item in quiver slot 9. |
| `slot_10` | FK to `Oggetto`, nullable | Stores the item in quiver slot 10. |
| `slot_11` | FK to `Oggetto`, nullable | Stores the item in quiver slot 11. |
| `slot_12` | FK to `Oggetto`, nullable | Stores the item in quiver slot 12. |
| `slot_13` | FK to `Oggetto`, nullable | Stores the item in quiver slot 13. |
| `slot_14` | FK to `Oggetto`, nullable | Stores the item in quiver slot 14. |
| `slot_15` | FK to `Oggetto`, nullable | Stores the item in quiver slot 15. |
| `slot_16` | FK to `Oggetto`, nullable | Stores the item in quiver slot 16. |
| `slot_17` | FK to `Oggetto`, nullable | Stores the item in quiver slot 17. |
| `slot_18` | FK to `Oggetto`, nullable | Stores the item in quiver slot 18. |
| `slot_19` | FK to `Oggetto`, nullable | Stores the item in quiver slot 19. |
| `slot_20` | FK to `Oggetto`, nullable | Stores the item in quiver slot 20. |
| `slot_21` | FK to `Oggetto`, nullable | Stores the item in quiver slot 21. |
| `slot_22` | FK to `Oggetto`, nullable | Stores the item in quiver slot 22. |
| `slot_23` | FK to `Oggetto`, nullable | Stores the item in quiver slot 23. |
| `slot_24` | FK to `Oggetto`, nullable | Stores the item in quiver slot 24. |
| `slot_25` | FK to `Oggetto`, nullable | Stores the item in quiver slot 25. |
| `slot_26` | FK to `Oggetto`, nullable | Stores the item in quiver slot 26. |
| `slot_27` | FK to `Oggetto`, nullable | Stores the item in quiver slot 27. |
| `slot_28` | FK to `Oggetto`, nullable | Stores the item in quiver slot 28. |
| `slot_29` | FK to `Oggetto`, nullable | Stores the item in quiver slot 29. |
| `slot_30` | FK to `Oggetto`, nullable | Stores the item in quiver slot 30. |
| `slot_31` | FK to `Oggetto`, nullable | Stores the item in quiver slot 31. |
| `slot_32` | FK to `Oggetto`, nullable | Stores the item in quiver slot 32. |
| `slot_33` | FK to `Oggetto`, nullable | Stores the item in quiver slot 33. |
| `slot_34` | FK to `Oggetto`, nullable | Stores the item in quiver slot 34. |
| `slot_35` | FK to `Oggetto`, nullable | Stores the item in quiver slot 35. |
| `slot_36` | FK to `Oggetto`, nullable | Stores the item in quiver slot 36. |
| `slot_37` | FK to `Oggetto`, nullable | Stores the item in quiver slot 37. |
| `slot_38` | FK to `Oggetto`, nullable | Stores the item in quiver slot 38. |
| `slot_39` | FK to `Oggetto`, nullable | Stores the item in quiver slot 39. |
| `slot_40` | FK to `Oggetto`, nullable | Stores the item in quiver slot 40. |
| `slot_41` | FK to `Oggetto`, nullable | Stores the item in quiver slot 41. |
| `slot_42` | FK to `Oggetto`, nullable | Stores the item in quiver slot 42. |
| `slot_43` | FK to `Oggetto`, nullable | Stores the item in quiver slot 43. |
| `slot_44` | FK to `Oggetto`, nullable | Stores the item in quiver slot 44. |
| `slot_45` | FK to `Oggetto`, nullable | Stores the item in quiver slot 45. |
| `slot_46` | FK to `Oggetto`, nullable | Stores the item in quiver slot 46. |
| `slot_47` | FK to `Oggetto`, nullable | Stores the item in quiver slot 47. |
| `slot_48` | FK to `Oggetto`, nullable | Stores the item in quiver slot 48. |
| `slot_49` | FK to `Oggetto`, nullable | Stores the item in quiver slot 49. |
| `slot_50` | FK to `Oggetto`, nullable | Stores the item in quiver slot 50. |

### Equip

Character equipment, kept as a named object with explicit named equipment fields.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Visible equipment set name. |
| `arma` | FK to `Oggetto`, nullable | Equipped main weapon. |
| `armatura` | FK to `Oggetto`, nullable | Equipped armor. |
| `scudo` | FK to `Oggetto`, nullable | Equipped shield. |
| `chainmail` | FK to `Oggetto`, nullable | Equipped chainmail layer. |
| `veste` | FK to `Oggetto`, nullable | Equipped robe layer. |
| `anello_1` | FK to `Oggetto`, nullable | Equipped ring slot 1. |
| `anello_2` | FK to `Oggetto`, nullable | Equipped ring slot 2. |
| `anello_3` | FK to `Oggetto`, nullable | Equipped ring slot 3. |
| `anello_4` | FK to `Oggetto`, nullable | Equipped ring slot 4. |
| `anello_5` | FK to `Oggetto`, nullable | Equipped ring slot 5. |
| `anello_6` | FK to `Oggetto`, nullable | Equipped ring slot 6. |
| `anello_7` | FK to `Oggetto`, nullable | Equipped ring slot 7. |
| `anello_8` | FK to `Oggetto`, nullable | Equipped ring slot 8. |
| `orecchino_1` | FK to `Oggetto`, nullable | Equipped earring slot 1. |
| `orecchino_2` | FK to `Oggetto`, nullable | Equipped earring slot 2. |
| `orecchino_3` | FK to `Oggetto`, nullable | Equipped earring slot 3. |
| `orecchino_4` | FK to `Oggetto`, nullable | Equipped earring slot 4. |
| `orecchino_5` | FK to `Oggetto`, nullable | Equipped earring slot 5. |
| `orecchino_6` | FK to `Oggetto`, nullable | Equipped earring slot 6. |
| `spilla` | FK to `Oggetto`, nullable | Equipped brooch slot. |
| `fascia` | FK to `Oggetto`, nullable | Equipped headband or band slot. |
| `amuleto` | FK to `Oggetto`, nullable | Equipped amulet slot. |
| `cintura` | FK to `Oggetto`, nullable | Equipped belt slot. |
| `vestiti` | FK to `Oggetto`, nullable | Equipped clothing slot. |
| `mantello` | FK to `Oggetto`, nullable | Equipped cloak slot. |
| `borsello` | FK to `Oggetto`, nullable | Equipped pouch slot. |
| `sacco_1` | FK to `Oggetto`, nullable | Equipped sack slot 1. |
| `sacco_2` | FK to `Oggetto`, nullable | Equipped sack slot 2. |
| `sacco_3` | FK to `Oggetto`, nullable | Equipped sack slot 3. |
| `faretra_1` | FK to `Oggetto`, nullable | Equipped quiver item slot 1. |
| `faretra_2` | FK to `Oggetto`, nullable | Equipped quiver item slot 2. |
| `extra_slot_1` | FK to `Oggetto`, nullable | Flexible equipped item slot 1. |
| `extra_slot_2` | FK to `Oggetto`, nullable | Flexible equipped item slot 2. |
| `extra_slot_3` | FK to `Oggetto`, nullable | Flexible equipped item slot 3. |
| `extra_slot_4` | FK to `Oggetto`, nullable | Flexible equipped item slot 4. |

### EffettiPersonaggio

Legacy-compatible active-effect assignment container. The API exposes populated entries as an array and hides numbered persistence fields from the frontend.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Visible/debuggable name for the assignment set. |
| `effetto_1` through `effetto_50` | FK to `Effetto`, nullable | Preserves stable effect slots while the rules service and API use array-shaped data. |

### EffettoPersonalizzato

Character-owned active effect authored from the SPA. It is deliberately independent from the canonical `Effetto` catalog and has no timer, stacking state, or timestamps.

| Field | Type | Why it exists |
|---|---|---|
| `personaggio_id` | FK to `Personaggio` | Gives the effect one clear owner and removes the need for a reusable template. |
| `nome` | string | User-facing name, unique inside the owning character. |
| `descrizione` | text | Preserves fiction and human-readable rules; includes exactly one `(t)` suffix when temporary. |
| `origine` | string nullable | Preserves the source/origin field without requiring another catalog record. |
| `icona` | string | Selects one of the shared code-native effect glyphs. |
| `temporaneo` | boolean | Means only that the `(t)` marker is shown; it does not start a countdown. |
| `ordine` | integer | Controls display and application order among custom effects. |

### OperazioneEffettoPersonalizzato

One normalized, ordered calculation change belonging to an `EffettoPersonalizzato`.

| Field | Type | Why it exists |
|---|---|---|
| `effetto_id` | FK to `EffettoPersonalizzato` | Deletes operation rows with their owning effect. |
| `ordine` | integer | Keeps multi-operation effects deterministic. |
| `bersaglio` | string | Names an allowed character total such as `forza`, `mana`, or `attacco`. |
| `operazione` | enum/string | Supports add, subtract, multiply, percent, min, max/cap, set, terminal `strong_set`, and safe formula replacement. |
| `valore` | text | Stores a number or safe formula expression without executing arbitrary code. |
| `condizione` | text nullable | Optional safe boolean expression controlling whether the row applies. |

### ReagenteAlchemico

Catalogo globale dei 42 ingredienti alchemici recuperati dall'Elder. Il nome descrive l'ingrediente, mentre colore e livello sono la regola autorevole usata da Alchimia&Contenitori e dal banco di distillazione.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | Conserva il nome storico mostrato durante estrazione e consultazione. |
| `colore` | enum `rosso/verde/blu` | Collega l'ingrediente a una delle tre famiglie di pozione. |
| `livello` | integer 1–4 | Seleziona il moltiplicatore di livello del personaggio. |
| `attivo` | boolean | Permette di escludere un ingrediente dalle estrazioni senza cancellarlo. |
| `ordine` | integer | Mantiene stabile l'ordine del catalogo. |

### ContenitoreInventario e VoceContenitoreInventario

`Alchimia&Contenitori` è il contenitore personale autorevole per reagenti e oggetti impilabili. Non esiste una borsa alchemica parallela.

| Field | Type | Why it exists |
|---|---|---|
| `scope` | enum `personal/campaign` | Distingue il contenitore personale dalle risorse condivise della campagna. |
| `personaggio_id` | FK to `Personaggio`, nullable | Possiede il contenitore personale. |
| `capacita` | integer | Numero reale di spazi disponibili. |
| `senza_peso` | boolean | Esclude queste pile dal peso dello zaino. |
| `Voce.reagent_stock_key` | string nullable | Identifica una delle 12 pile canoniche `r1–r4`, `v1–v4`, `b1–b4`. |
| `Voce.oggetto_id` | FK to `Oggetto`, nullable | Memorizza pozioni, pergamene e altri oggetti impilabili. |
| `Voce.quantita` | integer | Quantità della pila; ogni tipo occupa un solo spazio. |
| `metadata.legacyUnclassifiedReagents` | JSON optional | Conserva senza perdita eventuali chiavi storiche non classificabili. |

### Note

Documento di note del personaggio. Le stesse sezioni sono modificabili dalle viste di gioco contestuali e dal Diario globale.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Names the note set. |
| `zaino` | text | Scorte, oggetti affidati e promemoria visibili anche nella scheda Zaino. |
| `combat` | text | Tattiche, avversari e promemoria per gli scontri. |
| `crafting` | text | Materiali, ricette e progetti in corso. |
| `viaggio` | text | Rotte, luoghi, incontri e pericoli sulla strada. |
| `appunti` | text | Testo libero che non appartiene a un sottosistema. |
| `missioni` | text | Obiettivi, indizi e prossimi passi. |
| `background` | text | Storia personale, legami e motivazioni. |

`Personaggio.note` è l'unica relazione proprietaria. Non esistono voci, titoli, tag, date, tracker o stati di completamento separati.

### Personaggio

The main character object for player characters and NPCs. This stays close to the old `NPC` model, but removes direct `_base`, `_extra`, and `_tot` numeric column groups. Base/default values are records in `GlobalModifiers`, temporary/custom modifiers live in `extra`, and final calculated totals live in the `tot` JSON field.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Visible character name. |
| `tipologia` | enum: `giocabile`, `npc`, `nemico`, `evocazione`, `altro` | Distinguishes PCs, NPCs, enemies, summons, and extras. |
| `nome_interno` | string unique | Stable internal identifier for APIs, imports, and references. |
| `razza_1` | string | Primary race, kept explicit because it is core character identity. |
| `razza_2` | string nullable | Secondary race/subrace slot, kept explicit like the old model. |
| `razza_3` | string nullable | Tertiary race/subrace slot, kept explicit like the old model. |
| `livello` | integer | Drives progression, formulas, and unlocks. |
| `eta` | integer nullable | Preserves character age. |
| `sesso` | string nullable | Preserves character identity metadata. |
| `monete` | integer | Stores character money. |
| `dettagli_personaggio` | text nullable | Stores background, personality, fears, ambitions, and DM notes. |
| `danno` | integer | Stores current damage taken. |
| `mana_speso` | integer | Stores spent mana for the current state. |
| `energia_spesa` | integer | Stores spent energy for the current state. |
| `potere_speso` | integer | Stores spent power for the current state. |
| `mana_in_sifone` | integer | Stores mana currently held in siphon mechanics. |
| `competenze` | JSON | Stores per-character competence bars, bonuses, and notes. |
| `pe_generali` | integer | Stores general experience points. |
| `pe_rossi` | integer | Stores red experience points. |
| `pe_verdi` | integer | Stores green experience points. |
| `pe_blu` | integer | Stores blue experience points. |
| `pe_abilita` | integer | Stores ability-specific experience points. |
| `equip` | FK to `Equip`, nullable | Links the character to their equipment object. |
| `zaino` | FK to `Zaino`, nullable | Links the character to their backpack object. |
| `note` | FK to `Note`, nullable | Links the character to their notes object. |
| `faretra` | FK to `Faretra`, nullable | Links the character to their quiver object. |
| `effetti` | FK to `EffettiPersonaggio`, nullable | Links active structured effect assignments used as calculation input. |
| `abilita` | JSON | Stores unlocked skills and skill-related character state. |
| `abilita_desiderate` | JSON | Stores planned or desired skills. |
| `effetti_finali` | JSON | Stores calculation breakdown, applied operations, resolved overrides, and modified-stat audit data; it is report output, not refresh input. |
| `extra` | JSON | Replaces old individual `_extra` fields; stores custom/temporary modifiers by key before totals are recalculated. |
| `bottoni` | JSON | Stores per-character combat/action button state. |
| `crit_min` | string | Stores minimum critical threshold. |
| `crit_nor` | string | Stores normal critical threshold. |
| `crit_mag` | string | Stores magical critical threshold. |
| `custom_overrides` | JSON | Replaces custom adjustment fields such as level, luck, fatigue, and general-modifier custom formulas. |
| `tot` | JSON | Stores final calculated totals and derived modifiers previously held in individual `_tot` columns, keyed without the redundant suffix, such as `forza`, `mana`, `attacco`, `difesa`, `mod_forza`, `malus_carico`, and `atk_skill_taglio`. |

### Unit

Blueprint for playable and non-playable units. Merges `ArchetipoNPC`, `NPCArchetypeSkillUnlock`, `SkillNpc`, and `UnitLore`.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | Unit or creature name. |
| `razza` | string | Preserves race/species grouping. |
| `categoria` | enum/string | Groups humanoid, nature, undead, Daedra, extra, or future categories. |
| `archetipo_key` | string nullable | Merged archetype identifier such as battlemage or assassin. |
| `archetipo_tags` | JSON | Merged `ArchetipoNPC.tags`. |
| `archetipo_descrizione` | text nullable | Merged `ArchetipoNPC.descrizione`. |
| `profilo_equip` | string nullable | Merged `ArchetipoNPC.profilo_equip`. |
| `profilo_competenze` | JSON | Merged `ArchetipoNPC.profilo_competenze`. |
| `levels` | JSON | Stores supported level bands or level variants. |
| `preset` | enum/string | Preserves heavy/light/any/randomized generation behavior. |
| `equipment_profiles` | JSON | Replaces separate outfit/armor/weapon JSON fields with one structured equipment profile. |
| `stat_profiles` | JSON | Merges unit attribute/formula profiles. |
| `skill_actions` | JSON | Merged `SkillNpc`; stores unit-specific actions, costs, boosts, and effects. |
| `skill_unlocks` | JSON | Merged `NPCArchetypeSkillUnlock`; stores unlock order, level, and skill references. |
| `lore_description` | rich text nullable | Merged `UnitLore.descrizione`. |
| `lore_image_id` | FK to `UploadedImage`, nullable | Merged `UnitLore.immagine`. |
| `generation_rules` | JSON | Supports AI unit designer and import-as-character logic. |
| `notes` | text nullable | Designer-facing unit notes. |

### Negozio

Shop data. `Regione` and `Citta` are merged here.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Shop name. |
| `proprietario` | string nullable | Preserves owner flavor text. |
| `categoria` | string | Drives shop inventory generation. |
| `livello` | integer | Drives item level/rank for generated inventory. |
| `regione_nome` | string | Merged region name from `Regione`. |
| `regione_descrizione` | text nullable | Merged region description for shop/location UI. |
| `regione_immagine` | string/FK nullable | Merged region background image. |
| `citta_nome` | string | Merged city name from `Citta`; replaces `luogo` as the main city field. |
| `citta_descrizione` | text nullable | Merged city description for shop/location UI. |
| `citta_immagine` | string/FK nullable | Merged city background image. |
| `immagine_sfondo` | string/FK nullable | Shop-specific background image. |
| `lista_oggetti` | JSON | Preserves generated or manually curated inventory. |
| `generation_seed` | string nullable | Allows repeatable random shop regeneration. |
| `descrizione` | text nullable | Shop description. |

### Guida

Game guides and reference pages.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | Guide name. |
| `contenuto` | rich text/text | Stores guide body. |
| `immagine_sfondo` | string/FK nullable | Preserves visual guide backgrounds. |
| `categoria` | string nullable | Groups guides by player, DM, crafting, lore, audio, or systems. |
| `ordine` | integer | Controls guide menu ordering. |

### Curiosita

Loading tips and world curiosities.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | Short title or key. |
| `descrizione` | text | Curiosity body. |
| `categoria` | string nullable | Lets the app filter by lore, mechanics, travel, or campaign. |
| `visibile` | boolean | Allows hiding weak or outdated tips. |

### UploadedImage

Generic image/media record. Merges `GlobalImage`.

| Field | Type | Why it exists |
|---|---|---|
| `title` | string | Visible image title. |
| `folder` | string | Keeps gallery organization. |
| `file` | file/image | Main stored image. |
| `thumbnail` | file/image nullable | Speeds up gallery and picker views. |
| `parent_id` | self FK nullable | Supports generated/edit versions of an image. |
| `usage_type` | enum/string | Distinguishes generic, character, unit_lore, global_map, combat_map, timeline, hall_of_fame, item, and guide images. |
| `campagna_id` | FK to `DatiCampagna`, nullable | Supports campaign-specific image libraries and replaces `GlobalImage.campagna`. |
| `is_default_for_usage` | boolean | Replaces default global image behavior without a separate table. |
| `source` | enum/string nullable | Records uploaded, generated, imported, edited, or external source. |
| `prompt` | text nullable | Stores image generation prompt when applicable. |

### DatiMappa

Map-specific state linked to an uploaded image. Replaces `CampaignMap` and map-specific parts of `GlobalImage`.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Visible map name. |
| `campagna_id` | FK to `DatiCampagna`, nullable | Links map state to a campaign. |
| `image_id` | FK to `UploadedImage` | Points to the map image. |
| `tipo` | enum: `globale`, `viaggio`, `combattimento`, `dungeon`, `altro` | Separates global travel maps from combat and dungeon maps. |
| `fog_image_id` | FK to `UploadedImage`, nullable | Replaces `CampaignMap.grigia` when fog/gray map is needed. |
| `progressi` | JSON | Stores fog-of-war/progress drawing state. |
| `grid_data` | JSON | Stores hex/square grid size, origin, colors, and alignment. |
| `markers` | JSON | Stores marker positions and labels. |
| `hex_effects` | JSON | Stores travel-map hex effects or overlays. |
| `canvas_state` | JSON | Stores combat-map objects, drawings, tokens, and projectiles. |
| `dimensioni` | JSON | Stores image dimensions or board coordinate metadata. |
| `default_for_campaign` | boolean | Marks a default campaign/global map. |

### AudioFile

Audio library for music, ambience, sound effects, dialogue, and generated clips.

| Field | Type | Why it exists |
|---|---|---|
| `title` | string | Visible audio name. |
| `file` | file | Stored audio asset. |
| `primary_tag` | enum/string | Main category such as song, ambience, animal sound, dialogue, effect, or short music. |
| `secondary_tags` | JSON | Replaces the currently empty separate tag table with flexible tags. |
| `source` | enum/string nullable | Records uploaded, generated, imported, or external source. |
| `duration_seconds` | float nullable | Helps UI previews and playlists. |
| `notes` | text nullable | Stores usage notes for the DM. |

### TimelineEvent

Historical timeline and campaign-history events.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Event title. |
| `data_evento` | integer/string | Supports TES-style years and custom campaign dating. |
| `immagine_id` | FK to `UploadedImage`, nullable | Replaces direct image path with shared media. |
| `descrizione` | text | Event body. |
| `campagna_id` | FK to `DatiCampagna`, nullable | Allows global history and campaign-specific history. |
| `tags` | JSON | Supports filtering by era, location, faction, or campaign. |

### HallOfFameCharacter

Memorial/gallery entry for important characters.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Character name. |
| `immagine_id` | FK to `UploadedImage`, nullable | Links to gallery image. |
| `campaign` | string nullable | Preserves free-text campaign grouping. |
| `personaggio_id` | FK to `Personaggio`, nullable | Allows entries to link to a live or archived character. |
| `descrizione` | text | Hall-of-fame text. |
| `ordine` | integer | Supports curated display order. |

### CampaignLoreEntry

Canonical campaign lore graph node.

| Field | Type | Why it exists |
|---|---|---|
| `campagna_id` | FK to `DatiCampagna` | Lore belongs to a campaign. |
| `tipo` | string | Node type such as character, city, quest, faction, place, item, event, or secret. |
| `slug` | string | Stable graph/API identifier. |
| `nome` | string | Visible lore entry name. |
| `sommario` | text nullable | Short context for quick recall and AI context windows. |
| `contenuto` | JSON | Flexible structured body for DM notes, public notes, secrets, and sections. |
| `tags` | JSON | Supports filtering and retrieval. |
| `aliases` | JSON | Helps search, AI matching, and alternate names. |
| `stato` | enum/string | Tracks canon, rumor, deprecated, draft, or contradicted state. |
| `visibilita` | enum/string | Controls DM-only, player-visible, or mixed visibility. |
| `image_id` | FK to `UploadedImage`, nullable | Allows lore nodes to have images. |

### CampaignLoreRelation

Canonical campaign lore graph edge.

| Field | Type | Why it exists |
|---|---|---|
| `campagna_id` | FK to `DatiCampagna` | Relation belongs to a campaign. |
| `source_id` | FK to `CampaignLoreEntry` | Starting node of the relationship. |
| `target_id` | FK to `CampaignLoreEntry` | Ending node of the relationship. |
| `relation_type` | string | Names the relationship such as ally, enemy, born_in, owns, knows, controls, or visited. |
| `relevance` | integer | Scores importance for UI sorting and AI context selection. |
| `activation_context` | JSON | Stores situations where the relation matters. |
| `note` | text nullable | Human-readable explanation. |

### Messaggio

Player/campaign messaging. Replaces the duplicate current `Chat`/`Message`/`Messaggio` split for v2.

| Field | Type | Why it exists |
|---|---|---|
| `campagna_id` | FK to `DatiCampagna`, nullable | Allows messages to be campaign-specific. |
| `sender_id` | FK to `Giocatore` | Stores the sender. |
| `recipient_id` | FK to `Giocatore`, nullable | Null means table-wide/common message. |
| `thread_key` | string nullable | Supports private threads or named channels without a separate chat table at first. |
| `content` | text | Message body. |
| `created_at` | datetime | Orders messages. |
| `read_at` | datetime nullable | Supports unread markers. |
| `message_type` | enum/string | Separates chat, note, system, reaction, TTS, or handout messages. |

### NomiRazzeInfo

Renamed replacement for `GroupNames`.

| Field | Type | Why it exists |
|---|---|---|
| `name` | string unique | Name of the naming group, tribe, culture, or subculture. |
| `race` | string nullable | Race/culture the pool belongs to. |
| `names_male` | JSON | Male given-name pool. |
| `names_female` | JSON | Female given-name pool. |
| `surnames` | JSON | Surname/family-name pool. |
| `description` | text nullable | Explains cultural usage for the group. |

### LLMPrompt

Managed prompt library for AI features.

| Field | Type | Why it exists |
|---|---|---|
| `name` | string unique | Stable prompt key used by services. |
| `content` | text | Prompt body. |
| `importanza` | integer | Existing priority/importance concept. |
| `version` | string nullable | Lets prompts evolve without losing traceability. |
| `feature` | string nullable | Groups prompts by feature such as images, character creation, lore, items, or skills. |

### LLMLog

Short-lived AI call log.

| Field | Type | Why it exists |
|---|---|---|
| `service` | string | Records which feature/service called the model. |
| `call` | text/JSON | Stores request and response summary for debugging. |
| `created_time` | datetime | Supports pruning and recent-log inspection. |
| `status` | enum/string nullable | Records success, failure, timeout, or validation error. |
| `cost_metadata` | JSON | Allows later tracking of token/cost usage. |

### LogControl

Runtime logging switches.

| Field | Type | Why it exists |
|---|---|---|
| `debug` | boolean | Enables debug logs. |
| `methods` | boolean | Enables method-entry logs. |
| `calls` | boolean | Enables external-call logs. |
| `feature_flags` | JSON | Allows per-feature log switches without more columns. |

### ToolControl

Technical tool and maintenance toggles.

| Field | Type | Why it exists |
|---|---|---|
| `enable_startup_indexing` | boolean | Keeps startup indexing explicit. |
| `install_comfy` | boolean | Tracks whether local image tooling should be installed/started. |
| `import_massivo` | boolean | Controls bulk import tooling. |
| `vacuum_database` | boolean | Controls manual DB cleanup tasks. |
| `setup_open_code_orchestrator` | boolean | Controls local orchestrator setup. |
| `tool_flags` | JSON | Replaces one-column-per-maintenance-script growth. |
| `last_run` | JSON | Records last execution result per tool. |

## Dropped Or Merged Current Models

| Current model | V2 decision |
|---|---|
| `Attivabile` | Useful prose and costs are curated into `Skill.azioni_attive`; nested execution payloads are intentionally not reproduced. |
| `EffettiSbloccabili` | Proposed passives are curated into validated `Skill.effetti_passivi` definitions. |
| `SkillProfileTags` | Merged into `Skill.profile_tags`. |
| `Formule` | Merged into `GlobalModifiers.formulae`; create `Formule_base`. |
| `Alchimia` | Renamed to `BorsaReagenti`. |
| `IngredientiAlchimia` | Merged into `Oggetto.alchemy_profile`. |
| `Regione` | Merged into `Negozio.regione_*` fields. |
| `Citta` | Merged into `Negozio.citta_*` fields. |
| `ArchetipoNPC` | Merged into `Unit` archetype fields. |
| `NPCArchetypeSkillUnlock` | Merged into `Unit.skill_unlocks`. |
| `SkillNpc` | Merged into `Unit.skill_actions`. |
| `UnitLore` | Merged into `Unit.lore_description` and `Unit.lore_image_id`. |
| `GlobalImage` | Merged into `UploadedImage` and `DatiMappa`. |
| `CampaignMap` | Replaced by `DatiMappa` plus `UploadedImage`. |
| `LoreCampagna` | Replaced by `CampaignLoreEntry` and `CampaignLoreRelation`. |
| `Chat` and `Message` | Replaced by unified `Messaggio`; old chatbot can be rebuilt later. |
| `Persona` | Dropped for v2 initial scope; future chatbot/persona system should get a new design. |
| `Evento` | Dropped for v2 initial scope because random travel events are being removed. |
| `Missione` | Dropped for v2 initial scope; random mission generation can be reintroduced later. |
| `SecondaryAudioTag` | Merged into `AudioFile.secondary_tags` unless advanced audio search needs a table later. |

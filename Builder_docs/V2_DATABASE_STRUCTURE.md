# The Elder Django V2 Database Structure

Date: 2026-06-14
Schema version: v0.1
Status: Frozen implementation contract as of 2026-06-16

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

Represents the real human player or DM account.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | Human-readable player name used around the table. |
| `display_name` | string nullable | Allows a nicer visible name without changing login identity. |
| `password_hash` | string nullable | Replaces the current plain-ish `psw` field with a safer account credential slot. |
| `role` | enum: `dm`, `player`, `guest` | Drives permissions for DM-only lore, tools, and character control. |
| `active_character_id` | FK to `Personaggio`, nullable | Lets the UI open the player on their current character by default. |
| `character_ids` | JSON | A list of characters' `nome_interno` that the Giocatore has control over and can select. |
| `dice_profile` | string nullable | Preserves the current player dice preference. |
| `settings` | JSON | Stores per-player UI preferences, audio settings, permissions, and table options. |
| `notes` | JSON | Replaces the old `note_1...note_4` fields with flexible player notes. |

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
| `value_string` | JSON | Stores global level values. |
| `rule_notes` | text nullable | Documents why a modifier exists and when to use it. |

### FamigliaSkill

Groups skills into families, schools, classes, perk tracks, or religions.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | The visible name of the skill family. |
| `gruppo` | enum/string | Preserves high-level grouping such as general, religion, magic school, class, or perk. |
| `ordine` | integer | Allows stable ordering in skill trees and management UI. |
| `is_classe` | boolean | Keeps class-like families easy to filter. |
| `is_religione` | boolean | Keeps divine/Daedric/religious tracks easy to filter. |
| `is_perk` | boolean | Keeps perk tracks distinct from ordinary skill groups. |
| `note` | text nullable | Stores designer-facing family notes. |
| `note_addizionali` | text nullable | Preserves secondary notes from the current model. |

### Skill

Represents a purchasable or unlockable skill. 

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | The visible skill name. |
| `numero` | integer unique | Preserves existing skill numbering and import stability. |
| `famiglia_id` | FK to `FamigliaSkill`, non nullable | Keeps skill tree grouping. |
| `ordine_famiglia` | integer | Supports ordered display inside a family. |
| `magia` | boolean | Keeps magic skills easy to filter and validate. |
| `costo_pe` | integer | Stores XP cost. |
| `tipo_pe` | enum/string | Stores whether the skill consumes general/red/green/blue/ability XP. |
| `costo_testuale` | string nullable | Preserves human-readable costs such as mana, PA, fatigue, or conditions. |
| `descrizione` | text | Main player-facing skill explanation. |
| `requisiti` | text nullable | Stores prerequisite text until prerequisites become fully structured. |
| `livello_magia` | string nullable | Supports magic-level sorting and validation. |
| `raggio` | string nullable | Preserves range text for magic/actions and AI range checks. |
| `formula_effetto` | string nullable | Keeps legacy formula text when a skill has a simple direct effect. |
| `profile_tags` | JSON | Merged `SkillProfileTags`; expected keys include physical, magical, combat, range, area, defense, attack, social, support, exploration, crafting, and control scores. |
| `profile_notes` | text nullable | Replaces `SkillProfileTags.notes`. |
| `note` | text nullable | Designer-facing note field. |

### EffettiSkill

New model replacing `Attivabile` and `EffettiSbloccabili`.

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
| `tipo_5` | string nullable | Supports inventory and equipment UI. |
| `tipo_6` | string nullable | Supports inventory and equipment UI. |
| `descrizione` | text nullable | Player/DM-facing item description. |
| `valore` | integer nullable | Item value for shops and loot. |
| `peso` | float nullable | Item weight for carry capacity. |
| `rarita` | integer nullable | Supports loot generation and shop availability. |
| `lv_loot` | string nullable | Preserves current loot level bands. |
| `regione_loot` | string nullable | Keeps regional weighting without needing a `Regione` table. |
| `peso_regione` | float nullable | Controls how strongly the item is favored in its region. |
| `tipo_arma_id` | FK to `TipoArma`, nullable | Links weapons to weapon-category rules. |
| `pa_per_attacco` | integer nullable | Stores item-specific attack action cost. |
| `effects` | JSON | Replaces `effetto_1...effetto_15` with structured item effects. |
| `alchemy_profile` | JSON | Merged `IngredientiAlchimia`; stores reagent type, color, tier, category, and crafting metadata. |
| `crafting_profile` | JSON | Stores forge/enchant/alchemy requirements, outputs, and tool interactions. |
| `media_id` | FK to `UploadedImage`, nullable | Allows item images without hardcoding paths. |
| `notes` | text nullable | Designer-facing item notes. |

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

### BorsaReagenti

Renamed replacement for `Alchimia`.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Visible reagent bag name. |
| `personaggio_id` | FK to `Personaggio` | Connects reagents to a character. |
| `slot_max_reagenti` | integer | Preserves the current reagent capacity concept. |
| `ingredienti` | JSON | Replaces fixed red/green/blue numbered fields with flexible reagent counts. |
| `moltiplicatori` | JSON | Stores level/color multipliers for alchemy calculations. |
| `notes` | text nullable | Stores crafting notes tied to reagents. |

### Note

Character diary, background, and tracker state.

| Field | Type | Why it exists |
|---|---|---|
| `personaggio_id` | FK to `Personaggio` | Links notes to a character. |
| `nome` | string | Names the note set. |
| `personaggio` | JSON/text | Stores general character-facing notes, diary text, personality reminders, and personal context. |
| `appunti` | JSON/text | Stores freeform scratch notes that do not belong to a specific subsystem. |
| `note_combat` | JSON/text | Stores combat-specific notes, tactical reminders, enemy observations, and action notes. |
| `note_skill` | JSON/text | Stores skill-related notes, planned unlocks, build ideas, and rule reminders. |
| `crafting` | JSON/text | Stores forging, enchanting, item-work, and generic crafting notes. |
| `alchimia` | JSON/text | Stores alchemy-specific notes, reagent experiments, recipes, and potion reminders. |
| `background` | text nullable | Stores character background. |
| `tracker_config` | JSON | Stores custom note tracker definitions. |
| `tracker_state` | JSON | Stores current tracker values. |

### Personaggio

The main character object for player characters and NPCs. This stays close to the old `NPC` model, but removes direct `_base` and `_extra` numeric columns. Base/default values are records in `GlobalModifiers`, temporary/custom modifiers live in `extra`, and final calculated values are explicit `_tot` fields.

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
| `borsa_reagenti` | FK to `BorsaReagenti`, nullable | Links the character to their reagent bag, renamed from old `Alchimia`. |
| `faretra` | FK to `Faretra`, nullable | Links the character to their quiver object. |
| `abilita` | JSON | Stores unlocked skills and skill-related character state. |
| `abilita_desiderate` | JSON | Stores planned or desired skills. |
| `act` | JSON | Stores active effects after item/effect/skill processing. |
| `extra` | JSON | Replaces old individual `_extra` fields and the old `tot` JSON; stores custom/temporary modifiers by key before totals are recalculated. |
| `bottoni` | JSON | Stores per-character combat/action button state. |
| `crit_min` | string | Stores minimum critical threshold. |
| `crit_nor` | string | Stores normal critical threshold. |
| `crit_mag` | string | Stores magical critical threshold. |
| `custom_overrides` | JSON | Replaces custom adjustment fields such as level, luck, fatigue, and general-modifier custom formulas. |
| `stanchezza_tot` | number | Final calculated fatigue value. |
| `modificatore_generale_tot` | number | Final calculated general modifier. |
| `fortuna_tot` | number | Final calculated luck value. |
| `forza_tot` | number | Final calculated strength value. |
| `resistenza_tot` | number | Final calculated endurance/resistance attribute value. |
| `velocita_tot` | number | Final calculated speed value. |
| `agilita_tot` | number | Final calculated agility value. |
| `intelligenza_tot` | number | Final calculated intelligence value. |
| `concentrazione_tot` | number | Final calculated concentration value. |
| `personalita_tot` | number | Final calculated personality value. |
| `saggezza_tot` | number | Final calculated wisdom value. |
| `pf_tot` | number | Final calculated hit points. |
| `mana_tot` | number | Final calculated mana. |
| `energia_tot` | number | Final calculated energy. |
| `potere_tot` | number | Final calculated power. |
| `pa_tot` | number | Final calculated action points. |
| `attacco_tot` | number | Final calculated attack. |
| `difesa_tot` | number | Final calculated defense. |
| `attacco_npc` | number | Keeps the current NPC-side attack adjustment separate from general totals. |
| `difesa_npc` | number | Keeps the current NPC-side defense adjustment separate from general totals. |
| `rd_fis_tot` | number | Final calculated physical damage reduction. |
| `res_contundente_tot` | number | Final calculated blunt resistance. |
| `res_taglio_tot` | number | Final calculated slash resistance. |
| `res_perforante_tot` | number | Final calculated piercing resistance. |
| `res_fuoco_tot` | number | Final calculated fire resistance. |
| `res_gelo_tot` | number | Final calculated frost resistance. |
| `res_elettro_tot` | number | Final calculated shock resistance. |
| `rd_fuoco_tot` | number | Final calculated fire damage reduction. |
| `rd_gelo_tot` | number | Final calculated frost damage reduction. |
| `rd_elettro_tot` | number | Final calculated shock damage reduction. |
| `ap_tot` | number | Final calculated armor penetration. |
| `ap_percento_tot` | number | Final calculated percentage armor penetration. |
| `slot_magici_tot` | number | Final calculated magical slot count. |
| `slot_non_magici_tot` | number | Final calculated non-magical slot count. |
| `monete_per_slot_tot` | number | Final calculated coin-per-slot capacity. |
| `tier_tot` | number | Final calculated damage tier. |
| `sifone_di_mana_tot` | number | Final calculated mana siphon capacity or bonus. |
| `en_per_mana_ordine_tot` | number | Final calculated order-magic energy-to-mana conversion. |
| `pa_per_mana_ordine_tot` | number | Final calculated order-magic PA-to-mana conversion. |
| `en_per_mana_caos_tot` | number | Final calculated chaos-magic energy-to-mana conversion. |
| `pa_per_mana_caos_tot` | number | Final calculated chaos-magic PA-to-mana conversion. |
| `ogni_en_x_mana_ordine_tot` | number | Final calculated order-magic mana gained per energy interval. |
| `ogni_pa_x_mana_ordine_tot` | number | Final calculated order-magic mana gained per PA interval. |
| `ogni_en_x_mana_caos_tot` | number | Final calculated chaos-magic mana gained per energy interval. |
| `ogni_pa_x_mana_caos_tot` | number | Final calculated chaos-magic mana gained per PA interval. |
| `sconto_mana_per_potere_tot` | number | Final calculated mana discount per power. |
| `sconto_pa_per_potere_tot` | number | Final calculated PA discount per power. |
| `mod_carico_tot` | number | Final calculated carry modifier. |
| `mod_peso_equip_tot` | number | Final calculated equipped-weight modifier. |
| `orecchini_max_tot` | number | Final calculated maximum earring slots. |
| `anelli_max_tot` | number | Final calculated maximum ring slots. |
| `sacchi_max_tot` | number | Final calculated maximum sack slots. |
| `atk_skill_taglio_tot` | number | Final calculated slash-skill attack bonus. |
| `atk_skill_contundente_tot` | number | Final calculated blunt-skill attack bonus. |
| `atk_skill_perforante_tot` | number | Final calculated piercing-skill attack bonus. |

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
| `Attivabile` | Merged into `EffettiSkill`. |
| `EffettiSbloccabili` | Merged into `EffettiSkill`, linked to `Skill`. |
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

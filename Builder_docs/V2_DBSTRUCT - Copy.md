# The Elder Django V2 Database Structure

Date: 2026-06-14

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

### ContenitoreInventario

Normalized replacement for `Zaino` and `Faretra` as slot-heavy models.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Visible container name. |
| `personaggio_id` | FK to `Personaggio` | Connects the container to its owner. |
| `tipo` | enum: `zaino`, `faretra`, `borsello`, `sacco`, `altro` | Keeps old container concepts without separate tables. |
| `slot_max` | integer | Controls how many slots the UI should show. |
| `peso_massimo` | float nullable | Supports future capacity rules. |
| `rules` | JSON | Stores restrictions such as arrows only, reagents only, or item types allowed. |

### SlotInventario

One item slot inside an inventory container.

| Field | Type | Why it exists |
|---|---|---|
| `contenitore_id` | FK to `ContenitoreInventario` | Identifies the parent container. |
| `indice` | integer | Keeps slots ordered and addressable by drag/drop UI. |
| `oggetto_id` | FK to `Oggetto`, nullable | Stores the item in that slot. |
| `quantita` | integer | Allows stackable items. |
| `stato` | JSON | Stores per-instance durability, charges, custom names, or temporary flags. |

### Equipaggiamento

Replacement for the current `Equip` table.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Visible equipment loadout name. |
| `personaggio_id` | FK to `Personaggio` | Connects the loadout to its owner. |
| `attivo` | boolean | Allows future alternate loadouts while keeping one active. |
| `rules` | JSON | Stores max rings, earrings, sacks, quivers, and other equip limits. |

### SlotEquipaggiamento

One named equipment slot in a loadout.

| Field | Type | Why it exists |
|---|---|---|
| `equipaggiamento_id` | FK to `Equipaggiamento` | Identifies the parent loadout. |
| `slot_key` | string | Stable key such as `arma`, `armatura`, `anello_1`, or `mantello`. |
| `slot_label` | string | User-facing label for the slot. |
| `oggetto_id` | FK to `Oggetto`, nullable | Stores the equipped item. |
| `ordine` | integer | Keeps UI ordering stable. |
| `rules` | JSON | Stores allowed item types or custom slot restrictions. |

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
| `sezioni` | JSON | Replaces fixed fields such as zaino notes, crafting notes, travel notes, and appunti. |
| `background` | text nullable | Stores character background. |
| `tracker_config` | JSON | Stores custom note tracker definitions. |
| `tracker_state` | JSON | Stores current tracker values. |

### Personaggio

The main character object for player characters and NPCs.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string | Visible character name. |
| `nome_interno` | string unique | Stable internal identifier for APIs, imports, and references. |
| `tipologia` | enum: `giocabile`, `npc`, `nemico`, `evocazione`, `altro` | Distinguishes PCs, NPCs, enemies, summons, and extras. |
| `giocatore_id` | FK to `Giocatore`, nullable | Connects a character to a real player. |
| `unit_id` | FK to `Unit`, nullable | Records which unit blueprint produced or inspired the character. |
| `razze` | JSON | Replaces `razza_1`, `razza_2`, and `razza_3`. |
| `sesso` | string nullable | Preserves character identity metadata. |
| `eta` | integer nullable | Preserves character age. |
| `livello` | integer | Drives progression, formulas, and unlocks. |
| `monete` | integer | Stores character money. |
| `dettagli_personaggio` | text nullable | Stores background, personality, fears, ambitions, and DM notes. |
| `risorse_spese` | JSON | Replaces damage, mana spent, energy spent, power spent, and mana siphon fields. |
| `pe` | JSON | Replaces separate general/red/green/blue/ability XP fields. |
| `attributi_base` | JSON | Stores base stats such as strength, resistance, speed, agility, intelligence, concentration, personality, wisdom, and luck. |
| `attributi_extra` | JSON | Stores bonuses and penalties to base attributes. |
| `combat_base` | JSON | Stores base combat/resource values such as PF, mana, energy, PA, attack, defense, power, RD, resistances, slots, carry modifiers, and skill attacks. |
| `combat_extra` | JSON | Stores bonuses and penalties to combat/resource values. |
| `totals_cache` | JSON | Stores calculated totals for fast character-sheet reads. |
| `competenze_state` | JSON | Stores per-character competence bars, bonuses, and notes. |
| `skill_state` | JSON | Replaces old `abilita`; stores unlocked skills, levels, active flags, and provenance. |
| `desired_skill_state` | JSON | Replaces old `abilita_desiderate`; stores planned skills or wishlist choices. |
| `active_effects` | JSON | Replaces old `act`; stores current item, condition, and temporary effect applications. |
| `button_state` | JSON | Stores per-character combat/action button state. |
| `formula_profile_id` | FK to `GlobalModifiers` | Selects which formula profile calculates this character. |
| `custom_formula_overrides` | JSON | Replaces custom adjustment fields with one structured override map. |

### BottoneModificatoreCombat

Reusable combat modifier/action buttons.

| Field | Type | Why it exists |
|---|---|---|
| `label` | string | Internal and DM-facing button label. |
| `descrizione` | text nullable | Explains what the button does. |
| `effetti` | JSON | Stores attacker/target damage, attack, tier, and RD modifications. |
| `utilizzabile_visibile` | boolean | Controls whether players can see/use the button. |
| `testo_visibile_pg` | string nullable | Player-facing text for the PC side. |
| `testo_visibile_nemico` | string nullable | Player-facing text for the enemy side. |
| `ordine` | integer | Allows custom button ordering. |

### Unit

Blueprint for playable and non-playable units. Merges `ArchetipoNPC`, `NPCArchetypeSkillUnlock`, `SkillNpc`, and `UnitLore`.

| Field | Type | Why it exists |
|---|---|---|
| `nome` | string unique | Unit or creature name. |
| `slug` | string unique | Stable API/import identifier. |
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

### NomiRazze

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


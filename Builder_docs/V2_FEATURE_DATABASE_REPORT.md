# The Elder Django V2 Feature And Database Support Report

Date: 2026-06-14

This report maps the current game features to the proposed v2 database structure. The goal is to check whether the new schema can support the important parts of the current project while intentionally dropping or postponing features that should be redesigned.

Status meanings:

- Supported: v2 schema directly supports the feature.
- Redesigned: v2 supports the feature, but through cleaner objects than the current app.
- Postponed: intentionally excluded from the first v2 scope, but can be rebuilt later.
- Removed: intentionally dropped from first v2 and not worth preserving as-is.

## Summary

The v2 structure supports the core game: characters, players, skills, skill effects, effects and diseases, items, equipment, inventory, reagent bags, shops, campaign state, maps, lore graph, guides, curiosities, units, media, audio, timeline, hall of fame, LLM prompts/logs, and technical tools.

The highest-risk current models that should not simply disappear are handled by merges:

- `Attivabile` + `EffettiSbloccabili` -> `EffettiSkill`.
- `SkillProfileTags` -> `Skill.profile_tags`.
- `Formule` -> `GlobalModifiers.formulae`.
- `ArchetipoNPC` + `NPCArchetypeSkillUnlock` + `SkillNpc` + `UnitLore` -> `Unit`.
- `Regione` + `Citta` -> `Negozio`.
- `IngredientiAlchimia` -> `Oggetto.alchemy_profile`, then dropped entirely in migration `0049` (no rule ever read the column).
- `GlobalImage` + `CampaignMap` -> `UploadedImage` + `DatiMappa`.
- `LoreCampagna` -> `CampaignLoreEntry` + `CampaignLoreRelation`.

The first v2 scope intentionally drops or postpones the current random travel event page, random mission generator, old chatbot/persona flow, and old duplicate chat/message schema.

## Regione And Citta Check

The current `Regione` and `Citta` model classes are effectively shop-support data.

Direct model usage found:

- `django_slim/negozio.py`: fetches city by id, creates city rows, appends cities to region JSON, and creates generated shops.
- `django_slim/recupera_dati.py`: reads regions and cities for the shop selection UI.
- `django_slim/views.py`: uses `Regione.objects.get(...)` only during random shop creation.
- `django_slim/admin.py`: registers both in Django admin.

Non-shop references to "region" or "regione" are plain strings or prompt text, not relationships to the `Regione`/`Citta` models:

- `Oggetto.regione` and `Oggetto.peso_regione` are regional loot-weight fields.
- Location and dungeon generators use textual region fields.
- Campaign lore entries may store place-region text in JSON.

Conclusion: for v2, standalone `Regione` and `Citta` can be removed if `Negozio` stores `regione_nome`, `regione_descrizione`, `regione_immagine`, `citta_nome`, `citta_descrizione`, and `citta_immagine`.

## Feature Map

| Feature | Current database objects | V2 database objects | Status | Notes |
|---|---|---|---|---|
| Player accounts and identity | `Giocatore` | `Giocatore` | Supported | V2 keeps players, adds role/settings, and links an active character. |
| Player-owned characters | `NPC`, `Giocatore` | `Personaggio`, `Giocatore` | Redesigned | `NPC` becomes `Personaggio`, with cleaner JSON groups for stats/resources instead of many scattered columns. |
| NPCs and enemies | `NPC`, `Unit` | `Personaggio`, `Unit` | Redesigned | A live enemy/NPC is a `Personaggio`; a reusable blueprint is a `Unit`. |
| Character sheet identity | `NPC` fields such as name, race, age, sex, details | `Personaggio` | Supported | V2 keeps identity fields, but combines multi-race fields into `razze` JSON. |
| Character resources | `NPC` damage/mana/energy/power spent fields | `Personaggio.risorse_spese`, `Personaggio.combat_base`, `Personaggio.combat_extra`, `Personaggio.totals_cache` | Redesigned | Current resources are preserved as grouped data. |
| Character attributes and derived totals | `NPC` many base/extra/tot columns, `Formule`, `GlobalModifiers` | `Personaggio.attributi_base`, `Personaggio.attributi_extra`, `Personaggio.combat_base`, `Personaggio.combat_extra`, `Personaggio.totals_cache`, `GlobalModifiers` | Redesigned | Formula logic moves into `GlobalModifiers`, with `Formule_base` as the default profile. |
| XP and progression | `NPC.pe_generali`, `pe_rossi`, `pe_verdi`, `pe_blu`, `pe_abilita`, `Skill` | `Personaggio.pe`, `Skill` | Redesigned | XP pools become a JSON object so adding future XP colors does not require migrations. |
| Skills catalog | `Skill`, `FamigliaSkill` | `Skill`, `FamigliaSkill` | Supported | V2 keeps the catalog and family concept. |
| Skill profile tags | `SkillProfileTags` | `Skill.profile_tags`, `Skill.profile_notes` | Redesigned | The one-to-one tag table becomes embedded structured skill metadata. |
| Skill unlock/effect rules | `EffettiSbloccabili`, `Attivabile`, `Skill` | `EffettiSkill`, `Skill` | Redesigned | V2 has one clear model for passive effects, activable actions, and hybrid effects granted by skills. |
| Skill action buttons | `Attivabile`, `NPC.bottoni`, `BottoneModificatoreCombat` | `EffettiSkill`, `Personaggio.button_state`, `BottoneModificatoreCombat` | Redesigned | Skill-origin actions live in `EffettiSkill`; reusable combat modifier buttons remain separate. |
| Skill recommendations and AI skill review | `Skill`, `SkillProfileTags`, `EffettiSbloccabili`, `LLMPrompt`, `LLMLog` | `Skill`, `EffettiSkill`, `LLMPrompt`, `LLMLog` | Supported | The data needed for AI recommendations remains available in cleaner fields. |
| Skill integrity checks | `Skill`, `SkillProfileTags`, `EffettiSbloccabili`, `Attivabile` | `Skill`, `EffettiSkill` | Supported | Checks become simpler because skill effect data has one target table. |
| General effects and diseases | `EffettiEMalattie` | `EffettiEMalattie` | Supported | Kept as non-skill effects, diseases, injuries, blessings, curses, environment effects. |
| Effect presets | `EffettoPreset` | `EffettoPreset` | Supported | Kept because the current effect manager uses quick-apply preset payloads. |
| Active character effects | `NPC.act`, `Attivabile`, `EffettiEMalattie`, `Oggetto` | `Personaggio.active_effects`, `EffettiSkill`, `EffettiEMalattie`, `Oggetto.effects` | Redesigned | Runtime effects remain on the character; definitions live in content tables. |
| Competence/check list | `Competenze`, `NPC.competenze` | `Competenze`, `Personaggio.competenze_state` | Supported | V2 keeps the catalog and per-character state separately. |
| Items catalog | `Oggetto`, `Tipo_Arma` | `Oggetto`, `TipoArma` | Supported | V2 keeps items and weapon categories. |
| Item effects | `Oggetto.effetto_1...effetto_15` | `Oggetto.effects` | Redesigned | Item effects become a structured list instead of fifteen text columns. |
| Regional loot weighting | `Oggetto.regione`, `Oggetto.peso_regione` | `Oggetto.regione_loot`, `Oggetto.peso_regione` | Supported | This does not need `Regione` as a table. |
| Alchemy ingredient catalog | `IngredientiAlchimia` | — | Dropped | Became `Oggetto.alchemy_profile`, a schemaless JSON column no rule ever read; removed in migration `0049`. Ingredients are ordinary items classified by `tipo_*` until crafting ships with real tables. |
| Reagent bag / alchemy state | `Alchimia` | `BorsaReagenti` | Redesigned | Same feature, clearer name and flexible JSON counts. |
| Crafting notes and crafting UI | `Note`, `Alchimia`, `IngredientiAlchimia`, `Oggetto` | `Note.sezioni`, `BorsaReagenti` | Postponed | The item-side JSON profiles were dropped in migration `0049`; only the reagent bag and the character notes survive. Alchemy/forging/enchanting need a dedicated schema, not free-form columns on `Oggetto`. |
| Inventory backpack | `Zaino` with `slot_1...slot_50` | `ContenitoreInventario`, `SlotInventario` | Redesigned | V2 keeps zaino as a container type, avoiding fixed slot columns. |
| Quiver | `Faretra` with `slot_1...slot_50` | `ContenitoreInventario`, `SlotInventario` | Redesigned | V2 keeps faretra as a container type, with rules for arrows/projectiles. |
| Equipment loadout | `Equip` with named FK fields | `Equipaggiamento`, `SlotEquipaggiamento` | Redesigned | V2 keeps named equipment slots but makes slots data-driven. |
| Drag/drop inventory and equip | `Zaino`, `Faretra`, `Equip`, `Oggetto` | `ContenitoreInventario`, `SlotInventario`, `Equipaggiamento`, `SlotEquipaggiamento`, `Oggetto` | Supported | Drag/drop becomes easier because slots are real rows. |
| Carry capacity and equipment weight | `NPC` stat fields, `Oggetto.peso`, `Equip`, `Zaino` | `Personaggio.combat_base`, `Personaggio.combat_extra`, `Oggetto.peso`, inventory/equipment slots, `GlobalModifiers` | Supported | Formula-driven capacity can be recalculated from structured inventory. |
| Character notes and diary | `Note` fixed fields | `Note` | Redesigned | V2 stores note sections as JSON instead of many fixed note columns. |
| Note trackers | `Note.tracker_config`, `Note.tracker_state`, `DatiCampagna.giorni_da_inizio` | `Note.tracker_config`, `Note.tracker_state`, `DatiCampagna.giorni_da_inizio` | Supported | Kept directly. |
| Combat main page | `NPC`, `BottoneModificatoreCombat`, `DatiCampagna`, `EffettiEMalattie`, `Messaggio` | `Personaggio`, `BottoneModificatoreCombat`, `DatiCampagna`, `EffettiEMalattie`, `Messaggio` | Supported | V2 keeps all durable data needed for combat. |
| Damage and resource updates | `NPC` live fields | `Personaggio.risorse_spese`, `Personaggio.combat_*`, `Personaggio.totals_cache` | Redesigned | The backend service should update grouped state atomically. |
| Dice throws, luck, and limited resources | `Giocatore`, `DatiCampagna`, runtime logs | `Giocatore.dice_profile`, `DatiCampagna.risorse_speciali`, `Messaggio` or future event log | Supported | Durable preferences/resources are covered; detailed roll history can be added later if desired. |
| Combat modifier buttons | `BottoneModificatoreCombat`, `DatiCampagna.status_bottoni` | `BottoneModificatoreCombat`, `DatiCampagna.status_bottoni` | Supported | Kept because this is a current live combat feature. |
| Combat map canvas | `CampaignMap`, JSON canvas state in files/endpoints | `DatiMappa`, `UploadedImage` | Redesigned | V2 stores map image and map state cleanly. |
| Map fog/progress | `CampaignMap.originale`, `CampaignMap.grigia`, `CampaignMap.progressi` | `UploadedImage`, `DatiMappa.fog_image_id`, `DatiMappa.progressi` | Redesigned | Same data, but separated into media and map metadata. |
| Global travel map | `GlobalImage`, `DatiCampagna` | `UploadedImage`, `DatiMappa`, `DatiCampagna.default_global_map_id` | Redesigned | `GlobalImage` disappears as a standalone table. |
| Travel hex markers/effects | `GlobalImage.grid_data`, endpoint JSON | `DatiMappa.grid_data`, `DatiMappa.markers`, `DatiMappa.hex_effects` | Supported | V2 keeps this feature if travel-map UI remains. |
| Random travel event page | `Evento`, `DatiCampagna` | None in first scope | Removed | You said this feature should go away. Rebuild later as campaign-lore or encounter tooling if needed. |
| Random mission generator | `Missione` | None in first scope | Postponed | You said it can be reintroduced later. A future `MissionTemplate` can be added cleanly. |
| Shops | `Negozio`, `Regione`, `Citta`, `Oggetto` | `Negozio`, `Oggetto` | Redesigned | Region and city are embedded in `Negozio`; item regional weighting stays on `Oggetto`. |
| Random shop generation | `Negozio`, `Regione`, `Citta`, `Oggetto` | `Negozio`, `Oggetto` | Supported | Shop generation has all needed fields: shop category/level/location and item rarity/region/level. |
| Shop city/region browser | `Regione`, `Citta`, `Negozio` | `Negozio` | Redesigned | UI can group shops by `regione_nome` and `citta_nome`. |
| Guides | `Guida` | `Guida` | Supported | Kept, with category/order added. |
| Loading/world curiosities | `Curiosita` | `Curiosita` | Supported | Kept. |
| Master ideas scratchpad | `Master Ideas.txt` file | `Guida`, `CampaignLoreEntry`, or `DatiCampagna.state` | Redesigned | Current feature is file-backed, not DB-backed; v2 should store durable ideas in campaign/lore or guide data. |
| Altars/enchanting helper | `Oggetto` filtered by item type | `Oggetto` | Postponed | Altars remain ordinary items, but the enchanting metadata column was dropped in migration `0049` and no replacement exists yet. |
| Unit designer / unit tool | `Unit`, `SkillNpc`, `Oggetto`, `Formule`, `UnitLore` | `Unit`, `Oggetto`, `GlobalModifiers`, `UploadedImage` | Redesigned | Unit holds actions, lore, archetype data, unlocks, equipment profiles, and stat profiles. |
| Import unit as character | `Unit`, `NPC`, `Equip`, `Zaino`, `Note`, `Alchimia`, `Faretra`, `Formule`, `SkillNpc` | `Unit`, `Personaggio`, inventory/equipment tables, `Note`, `BorsaReagenti`, `GlobalModifiers` | Supported | V2 supports the workflow with clearer target structures. |
| Unit lore/bestiary page | `UnitLore`, `Unit`, image fields | `Unit.lore_description`, `Unit.lore_image_id`, `UploadedImage` | Redesigned | Lore and image data are merged into `Unit`. |
| NPC archetype manager | `ArchetipoNPC`, `Competenze`, `NPCArchetypeSkillUnlock` | `Unit` | Redesigned | Archetype tags, competence profile, equipment profile, and skill unlocks are fields on `Unit`. |
| AI character creation wizard | `NPC`, `Unit`, `ArchetipoNPC`, `Competenze`, `EffettiSbloccabili`, `Skill`, `Oggetto` | `Personaggio`, `Unit`, `Competenze`, `EffettiSkill`, `Skill`, `Oggetto` | Supported | The data model supports the workflow; service code should be rebuilt around new APIs. |
| Auto-generate NPC from name/audio | `NPC`, AI services, `GroupNames` | `Personaggio`, `NomiRazze`, `LLMPrompt`, `LLMLog` | Supported | The feature can be rebuilt without old `Persona` chatbot storage. |
| Random name generation | `GroupNames` | `NomiRazze` | Supported | Same data, clearer name. |
| Campaign lore graph | `CampaignLoreEntry`, `CampaignLoreRelation`, `DatiCampagna` | `CampaignLoreEntry`, `CampaignLoreRelation`, `DatiCampagna` | Supported | Kept as the preferred lore future. |
| Legacy campaign lore JSON | `LoreCampagna` | `CampaignLoreEntry`, `CampaignLoreRelation` | Redesigned | Old JSON aggregate should be migrated into graph entries/relations or dropped after export. |
| Lore image references | `UploadedImage`, `LoreCampagna`, `HallOfFameCharacter` | `UploadedImage`, `CampaignLoreEntry.image_id`, `HallOfFameCharacter` | Supported | V2 has shared media and direct lore image links. |
| Timeline | `TimelineEvent` | `TimelineEvent`, `UploadedImage`, `DatiCampagna` | Supported | Kept with shared image references. |
| Hall of Fame | `HallOfFameCharacter`, image fields | `HallOfFameCharacter`, `UploadedImage`, optional `Personaggio` link | Supported | Kept and made more relational. |
| Main image gallery | `UploadedImage`, `CollabFocus` | `UploadedImage` | Supported | Basic gallery is supported; live shared focus can be a frontend/session feature or added later. |
| Image versions/edits | `UploadedImage.parent` | `UploadedImage.parent_id` | Supported | Kept. |
| Global image gallery maps | `GlobalImage`, `UploadedImage` | `UploadedImage`, `DatiMappa` | Redesigned | One image table with map metadata. |
| LLM image generation | `UploadedImage`, `LLMPrompt`, `LLMLog` | `UploadedImage`, `LLMPrompt`, `LLMLog` | Supported | Generated images store source/prompt metadata. |
| Comfy/local image tooling | `ToolControl`, local files/logs | `ToolControl`, `UploadedImage`, `LLMLog` | Supported | The database supports control/status; runtime code should own process details. |
| Audio library | `AudioFile`, `SecondaryAudioTag` | `AudioFile` | Redesigned | Secondary tags are JSON unless advanced relational search is needed. |
| TTS events/reactions | `AudioFile`, `Messaggio`, runtime endpoints | `AudioFile`, `Messaggio`, `DatiCampagna.state` | Supported | Durable audio and event messages are covered. |
| Player table messages | `Giocatore`, `Messaggio` | `Giocatore`, `Messaggio` | Supported | Kept as one unified message table. |
| Old chat sessions | `Chat`, `Message` | `Messaggio` or future chat module | Redesigned | Duplicate message models should not be kept. |
| Old chatbot/persona system | `Persona`, `Chat`, `Message`, `NPC`, `Guida`, `Skill`, `Attivabile` | None in first scope | Removed | You want to remove and rebuild it later. Future chatbot should use `CampaignLoreEntry`, `Personaggio`, `Guida`, `Skill`, and vector/search indexes. |
| LLM prompt management | `LLMPrompt` | `LLMPrompt` | Supported | Kept. |
| LLM call logs | `LLMLog` | `LLMLog` | Supported | Kept, with optional status/cost metadata. |
| Dungeon generator | `Dungeon`, `DatiCampagna`, AI services | `CampaignLoreEntry`, `DatiMappa`, optional future `Dungeon` | Postponed/Redesigned | Current `Dungeon` table has no data. Persist generated dungeons as lore/map records unless a dedicated dungeon feature returns. |
| Location generator | text outputs, campaign/lore endpoints | `CampaignLoreEntry`, `UploadedImage`, `DatiMappa` | Supported | Generated locations can become lore entries and map/image records. |
| Bulk import/editor tools | Many current models, `ToolControl` | Target content models, `ToolControl`, `LLMLog` | Supported | Tool code should target the new schema explicitly. |
| Object manager | `Oggetto`, `Tipo_Arma`, LLM item creation | `Oggetto`, `TipoArma`, `LLMPrompt`, `LLMLog` | Supported | Strongly supported; item effects/ingredient data are cleaner. |
| Tool-calling audio/object creation | `Oggetto`, `tool_calling.py`, `LLMPrompt` | `Oggetto`, `LLMPrompt`, `LLMLog` | Supported | Regional and alchemy fields remain on `Oggetto`. |
| Skill management page | `Skill`, `SkillProfileTags`, `EffettiSbloccabili`, `Attivabile`, `LLMPrompt`, `LLMLog` | `Skill`, `EffettiSkill`, `LLMPrompt`, `LLMLog` | Supported | Cleaner because tags and effects are closer to skills. |
| Skill-attivabili generator | `Skill`, `Attivabile`, `EffettiSbloccabili` | `Skill`, `EffettiSkill` | Redesigned | Output schema should become a single `EffettiSkill` proposal. |
| Character cleanup/orphan cleanup | `NPC`, `Equip`, `Zaino`, `Note`, `Alchimia`, `Faretra`, `Formule` | `Personaggio`, inventory/equipment, `Note`, `BorsaReagenti`, `GlobalModifiers` | Supported | Cleanup rules become clearer due to ownership FKs. |
| Export selected character | `NPC` plus immediate relations | `Personaggio` plus owned inventory/equipment/notes/reagents | Supported | V2 should have a dedicated export serializer. |
| Admin controls | Django admin over many models | Admin over v2 models | Supported | Fewer models, but richer JSON validation required. |
| Runtime logging control | `LogControl` | `LogControl` | Supported | Kept. |
| Tool toggles/startup operations | `ToolControl` | `ToolControl` | Supported | Kept, but flexible `tool_flags` avoids column sprawl. |
| Orchestrator/OpenCode integration | `ToolControl`, runtime files | `ToolControl`, `LLMLog`, optional settings | Supported | Database stores switches/status; external runtime stores process data. |
| Database backup/vacuum/startup maintenance | `ToolControl`, scripts | `ToolControl`, `LLMLog`/logs | Supported | Keep as technical operations, not core game data. |

## Support By V2 Model

### Giocatore

Supports player identity, permissions, active-character selection, dice preferences, player settings, table messages, and future account UX.

### Personaggio

Supports character sheets, NPCs, enemies, combat state, skill ownership, active effects, XP, resources, derived totals, competence state, and formula-profile selection.

### Unit

Supports unit blueprints, creature catalog, archetypes, AI unit designer, import-as-character, bestiary/lore, unit actions, unit skill unlock tracks, and unit equipment/stat profiles.

### Skill, FamigliaSkill, EffettiSkill

Support skill trees, class/perk/religion tracks, XP unlocks, skill filtering, AI recommendations, passive skill effects, activable skill actions, skill review workflows, and future structured prerequisites.

### EffettiEMalattie and EffettoPreset

Support status conditions, diseases, injuries, blessings/curses, environment effects, manual effect application, and reusable DM presets.

### Oggetto and TipoArma

Support item catalog, equipment, weapons, item effects, loot generation, regional item weighting, shop inventory generation, crafting, alchemy ingredient metadata, item manager, and voice/LLM item creation.

### ContenitoreInventario, SlotInventario, Equipaggiamento, SlotEquipaggiamento, BorsaReagenti

Support backpack/quiver/container inventory, drag/drop, equipment slots, stackable items, reagent counts, alchemy multipliers, and future capacity rules.

### DatiCampagna, CampaignLoreEntry, CampaignLoreRelation

Support current campaign state, campaign clock, weather, special resources, lore graph, faction/location/quest relations, and AI context retrieval.

### UploadedImage and DatiMappa

Support generic image gallery, generated images, image versions, map images, global/travel maps, combat maps, grid data, markers, hex effects, fog-of-war, and canvas state.

### Negozio

Supports shops, shop owners, shop categories, shop levels, shop inventory, region/city display, custom city creation, and random shop generation without standalone region/city tables.

### Guida, Curiosita, TimelineEvent, HallOfFameCharacter

Support guide pages, loading/world tips, historical timeline, campaign history, and hall-of-fame galleries.

### AudioFile and Messaggio

Support audio library, TTS/reaction events, table messages, player-private messages, common messages, and future named channels.

### NomiRazze

Supports random name generation by race/culture/subculture.

### LLMPrompt, LLMLog, LogControl, ToolControl

Support AI prompts, AI call logging, debugging switches, local tool toggles, startup operations, bulk import controls, image tooling, and orchestrator/comfy integration.

## Postponed Or Removed Features

| Feature | Reason | Future path |
|---|---|---|
| Random travel events | You want to remove the current travel event feature. | Rebuild later as encounter/lore event templates if needed. |
| Random mission generator | You want to remove it for now. | Add `MissionTemplate` and `GeneratedMission` later if the feature returns. |
| Old chatbot/persona flow | You want to remove current chatbot and rebuild later. | Future chatbot should query `CampaignLoreEntry`, `Personaggio`, `Guida`, `Skill`, `Oggetto`, and embeddings/search indexes. |
| Standalone `Regione`/`Citta` pages | Their real role is shop support. | Group shops by embedded region/city fields or add a world atlas later if cities become first-class lore. |
| Standalone `Dungeon` table | Current table has no data and the feature is mostly generator/runtime. | Persist generated dungeons as `CampaignLoreEntry` plus `DatiMappa`; add a dedicated model only if dungeon management becomes a real workflow. |
| Duplicate `Chat`/`Message` tables | Overlaps with `Messaggio` and old chatbot. | Use unified `Messaggio`; add `ChatThread` later only if needed. |

## Main Risks

1. JSON fields make v2 simpler, but they need validation at the service/API layer. The schema should define allowed keys for `profile_tags`, `effects`, `formulae`, `active_effects`, `skill_actions`, and `skill_unlocks`.
2. Merging `EffettiSbloccabili` and `Attivabile` into `EffettiSkill` is correct, but the rules engine must distinguish passive effects from manual actions.
3. Merging `Regione` and `Citta` into `Negozio` is safe for current behavior, but if you later want a real world atlas, add `Luogo` or `WorldLocation` rather than reviving the old shop-only region/city tables.
4. Merging `UnitLore` into `Unit` is clean, but long rich-text lore and generated images should be imported carefully.
5. `Personaggio` should not expose raw JSON blobs directly to the frontend. Build typed API responses such as `CharacterSummary`, `CharacterSheet`, `CharacterInventory`, `CharacterCombatState`, and `CharacterProgression`.

## Recommended First Build Order

1. Build content tables first: `Oggetto`, `TipoArma`, `FamigliaSkill`, `Skill`, `EffettiSkill`, `EffettiEMalattie`, `Competenze`, `GlobalModifiers`.
2. Build character state second: `Giocatore`, `Personaggio`, `Note`, inventory/equipment tables, `BorsaReagenti`.
3. Build campaign state and media third: `DatiCampagna`, `UploadedImage`, `DatiMappa`, `CampaignLoreEntry`, `CampaignLoreRelation`.
4. Build support content fourth: `Unit`, `Negozio`, `Guida`, `Curiosita`, `AudioFile`, `TimelineEvent`, `HallOfFameCharacter`, `NomiRazze`.
5. Build technical support last: `LLMPrompt`, `LLMLog`, `LogControl`, `ToolControl`.

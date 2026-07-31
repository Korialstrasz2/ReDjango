# GPT Image 2 — Theme Surface Prompt Matrix

## Scope

Current selectable application themes: `parchment`, `midnight`, `arcane`,
`skyrim`, `morrowind`, `oblivion`.

Current configurable image surfaces: 56. This matrix covers all **336**
theme × surface images: 12 pages, 38 modals, 5 quick tools, and the shared
management workspace. It follows `backend/core/theme_surfaces.py`, source of
truth for assignable theme backgrounds.

`ThemeBackground` images sit behind translucent application panels. Generate
background art, never mockups of a UI. Images need calm negative space so text,
forms, tables, maps, and opaque modal content remain legible.

## Prompt assembly

For every row, paste this exact sequence into GPT Image 2:

```text
{GLOBAL INSTRUCTIONS} {THEME PROMPT} {SURFACE PROMPT} {OUTPUT INSTRUCTIONS}
```

Replace only the two braced blocks with one complete entry from the sections
below. This produces one distinct, copy-ready image brief for every theme and
surface while keeping a visual family coherent.

### Global instructions

```text
Create original high-fantasy environmental concept art for a desktop game-master workstation background. It is background art, not an interface: no words, letters, numbers, logos, labels, seals, UI panels, frames, borders, buttons, cards, character sheets, maps with labels, or watermarks. No recognizable copyrighted characters or exact game assets. Keep the central 55 percent quiet, low-contrast, and readable beneath translucent content; place detail along outer edges and corners. Cinematic painterly realism, subtle material texture, controlled contrast, crisp enough for a 2560×1440 desktop background.
```

### Output instructions

```text
Wide 16:9 landscape composition. One complete background image only. No text or typography anywhere.
```

## Theme prompts

| Theme key | Prompt |
| --- | --- |
| `parchment` — Pergamena | `Warm candlelit tabletop fantasy: aged ivory parchment, walnut wood, worn brass, muted burgundy wax, faded sepia ink ornament that never forms readable writing, soft amber light, grounded scholarly atmosphere.` |
| `midnight` — Notte | `Deep midnight high fantasy: blue-black stone, moonlit silver, restrained indigo haze, distant stars and soft rain-slick reflections, quiet mysterious atmosphere, cool palette with tiny warm candle accents.` |
| `arcane` — Arcano | `Refined arcane high fantasy: deep indigo and teal, violet magical luminescence, ancient slate, brass instruments, non-readable geometric sigils and drifting motes, elegant controlled magic rather than chaotic spell effects.` |
| `skyrim` — Skyrim | `Nordic winter high fantasy: weathered pine, carved dark timber, granite, snow, cold blue daylight, distant crags and restrained warm hearth glow. Original setting art; no franchise symbols, characters, or logos.` |
| `morrowind` — Morrowind | `Volcanic ashland high fantasy: charcoal basalt, ash haze, rust-red volcanic glow, weathered adobe and chitin-like texture, sparse bioluminescent giant fungi at edges, alien yet solemn atmosphere. Original setting art; no franchise symbols, characters, or logos.` |
| `oblivion` — Oblivion | `Imperial-gothic high fantasy: pale carved stone, dark oak, antique gold, mossy green and amber light, dignified arches and distant autumnal landscape, stately adventurous atmosphere. Original setting art; no franchise symbols, characters, or logos.` |

## Surface prompts

Use every row once with every theme prompt. Keys exactly match Theme Management.

### Pages

| Surface key | UI surface | Surface prompt |
| --- | --- | --- |
| `dashboard` | Sala principale | `Grand campaign hall seen from a slightly elevated angle: a broad communal table at edges, distant hearth and tall windows, subtle suggestion of travel and adventure, generous empty center.` |
| `personaggio` | Scheda personaggio | `Private adventurer's study: travel-worn leather satchel, sheathed weapon and small personal keepsakes at outer edges, a cleared work surface through the center, intimate and practical.` |
| `skills` | Abilità | `Quiet spell and skill archive: tall shelves, rolled diagrams, a few closed grimoires and training tools at edges, subdued magical light, uncluttered central reading area.` |
| `competencies` | Competenze | `Mastery workshop: measured practice implements, rope, tools, wooden targets and small tokens arranged at edges, disciplined atmosphere, open neutral center for dense information.` |
| `creation` | Creazione | `Ritual of beginnings: a simple workbench with a compass, blank parchment, unlit candle, natural talismans and a distant dawn, hopeful empty central space with no readable marks.` |
| `combat` | Combattimento | `Tactical war table in a fortified chamber: stone floor, scattered pebbles, shield rim and torchlight at edges, faint grid-like geometry that is not a map and contains no labels, broad calm center.` |
| `travel` | Viaggio | `High overlook above an original fantasy wilderness: winding unlabeled roads, forest, river and distant mountains around edges, atmospheric depth, an open misty valley through center.` |
| `market` | Mercato | `Covered fantasy market at dawn: awnings, crates, lanterns, produce and merchant cloth at outer edges, warm trading atmosphere, empty central aisle and no signs or lettering.` |
| `lore` | Lore | `Ancient history chamber: sculpted alcoves, faded fresco fragments that form no narrative text, heirlooms and a distant ceremonial hall, contemplative muted center.` |
| `media` | Archivio immagini | `Curator's archive: stacked framed paintings turned away, sealed portfolios, glass lanterns and storage drawers at edges, gallery-like calm with a broad blank viewing surface.` |
| `guide` | Guide | `Scholar's library reading room: shelves fading into shadow, open but blank-looking book forms at edges, magnifying lens and candlelight, clean central study space.` |
| `settings` | Impostazioni | `Orderly keeper's desk: carefully arranged tools, keys, blank ledgers and measuring instruments at edges, balanced symmetrical composition, understated calm center.` |

### Modals — archive and settings

| Surface key | UI surface | Surface prompt |
| --- | --- | --- |
| `media-preview` | Anteprima immagine | `Darkened gallery alcove with empty hanging frames and soft spotlights at edges, restrained vignette, wide calm center reserved for an image viewer.` |
| `media-move` | Sposta immagine | `Archive sorting table with unlabeled portfolios, small drawers and colored thread tags at corners, orderly neutral center, low visual density.` |
| `media-confirm` | Conferma sull'immagine | `Minimal archival desk with a closed folder, soft lamp and deliberate shadow at edges, calm center, restrained serious mood without danger symbols or text.` |
| `settings-restart` | Riavvio necessario | `Quiet engine-room study: brass clockwork, a dormant lantern and a distant window at edges, stable symmetrical composition, muted center for an important confirmation.` |
| `image-picker` | Scegli un'immagine | `Curated image vault: rows of unlabeled framed art and portfolio drawers receding at edges, soft diffuse gallery lighting, very clear neutral center for thumbnail selection.` |
| `weather` | Tempo atmosferico | `Open observatory window framing dramatic but gentle fantasy weather in distant sky, weather instruments at edges, calm middle, no symbols, calendars, maps, or writing.` |

### Modals — character

| Surface key | UI surface | Surface prompt |
| --- | --- | --- |
| `character-overview` | Modifica panoramica | `Personal writing desk with a travel cloak, compass and blank sealed correspondence pushed to corners, warm focused lamplight, uncluttered center for editing identity details.` |
| `character-rest` | Riposa | `Sheltered camp at night: rolled bedroll, low fire, pack and boots around outer edge, peaceful dim light and a very quiet central area.` |
| `effect-preset` | Preset effetto | `Arcane apothecary shelf: stoppered bottles, dried herbs and small glowing tokens at edges, carefully controlled color, blank calm center for choosing an effect.` |
| `item-editor` | Editor oggetto | `Craftsperson's workbench with tools, an unfinished blade, leather, gems and a blank parchment pattern at edges, even workshop light, large clean center for a detailed form.` |

### Modals — combat

| Surface key | UI surface | Surface prompt |
| --- | --- | --- |
| `combat-map-editor` | Editor della mappa | `Cartographer's stone worktable with blank tiles, compass, rulers and unlabeled terrain miniatures at edges, diffuse top light, expansive clear center for map editing.` |
| `combat-map-settings` | Impostazioni della mappa | `Orderly field-command desk with folded blank canvas, measuring tools and lantern at edges, low contrast center, precise practical atmosphere.` |
| `combat-import-fighters` | Importa combattenti | `Fortified hall antechamber with shields, cloaks and weapon racks around outer edges, open central floor, ready but not violent atmosphere.` |
| `combat-manage-characters` | Gestisci personaggi | `Campaign command room: grouped packs, helmets and personal banners without heraldry at edges, balanced empty center for roster management.` |
| `combat-import-copy` | Importare una copia? | `Dim strategy desk with a second rolled blank map beside a lantern, visual suggestion of duplication without text or symbols, sober empty center.` |
| `combat-map-backups` | Backup della mappa | `Secure archive niche with stacked unlabeled map tubes, sealed cases and timeworn shelves at edges, protected quiet center.` |
| `combat-character-public` | Personaggio in combattimento | `Battlefield observation point: distant silhouettes, shield edge and windblown cloak at corners, no visible faces, open center with readable low contrast.` |
| `combat-character-manage` | Personaggio: controlli | `Master's tactical desk with command tokens, compass and extinguished candle at edges, authoritative but restrained, broad neutral center.` |
| `combat-map-manager` | Gestione mappe | `Map vault with rolled unlabeled canvases and terrain boxes arranged along walls, clean central aisle, practical archival lighting.` |
| `combat-quick-actions` | Azioni rapide | `Close tactical still life: gauntlet, dice, small command tokens and sword hilt at corners, energetic lighting kept away from a clear central action area.` |

### Modals — guides, lore, and market

| Surface key | UI surface | Surface prompt |
| --- | --- | --- |
| `item-detail` | Dettaglio oggetto | `Museum display alcove with one indistinct artifact silhouette under warm light at an outer edge, dark velvet and wood texture, broad quiet center for item details.` |
| `lore-npc` | Scheda PNG | `Narrative portrait chamber with a distant empty chair, personal keepsake and soft window light at edges, no person present, intimate neutral center.` |
| `lore-faction-editor` | Editor fazione | `Ceremonial council table with blank banners, sealed wax and carved stone at edges, equal balanced composition, open center for faction authoring.` |
| `lore-npc-editor` | Editor PNG | `Character chronicler's desk with quill, folded blank cloth, unmarked portrait frame and token at edges, warm quiet center for writing.` |
| `lore-reactions` | Matrice delle reazioni | `Diplomatic chamber with several empty chairs, interwoven colored threads and neutral emblems that contain no marks, cool balanced lighting, clean center for a relationship matrix.` |
| `lore-faction-history` | Storico della fazione | `Old archive corridor with stacked sealed records, empty niche and soft dust-lit depth at edges, sense of time without readable documents, calm center.` |
| `lore-timeline-event` | Evento della Timeline | `Ancient hall with a long shadowed passage, relic fragments and a distant shaft of light at edges, evocative sense of chronology, clear central authoring space.` |
| `market-shop-editor` | Editor bottega | `Merchant's back office: scales, folded cloth, crates and unlabeled bottles around the border, warm practical lamp light, central work area clean for shop settings.` |

### Modals — skills

| Surface key | UI surface | Surface prompt |
| --- | --- | --- |
| `skills-reminder` | Promemoria abilità | `Small spell-study alcove with a single glowing token, closed books and a feather at edges, intimate focused lighting, simple quiet center for a reminder.` |
| `skills-unlock` | Sblocco abilità | `Threshold of mastery: a softly lit archway, practice weapon and faint magical motes at edges, aspirational but restrained, empty center for a decision.` |
| `skills-detail` | Dettaglio abilità | `Scholarly examination table with an open but unreadable grimoire, diagrams that contain no symbols, tools and candle at edges, broad low-contrast center.` |
| `skills-create` | Crea abilità | `Fresh academy workbench with blank materials, ink, tools and a small unlit crystal at edges, dawn-like creative light, open center for a detailed editor.` |
| `skills-xp` | Modifica Punti Esperienza | `Training hall ledger desk with unlabeled weights, practice marks and a small pile of neutral tokens at edges, calm precise center for numerical controls.` |
| `skills-progression` | Progressione del personaggio | `Ascending archive staircase fading upward at outer edge, scattered milestones and a lantern, gentle depth with a clear center for progression analysis.` |
| `skills-stats` | Statistiche delle skill | `Orderly observatory study with instruments, beads and unlabeled measuring charts at edges, analytical calm, neutral central area for statistics.` |
| `skills-effects` | Effetti e azioni dalle skill | `Controlled magical laboratory: contained colored light in glass vessels and prepared action tools at edges, no explosive effects, very readable central space.` |
| `skills-button-editor` | Editor pulsante rapido | `Compact command desk with smooth stones, simple unmarked tokens and leather straps at corners, balanced grid-like arrangement without actual labels, quiet center.` |

### Modals — travel

| Surface key | UI surface | Surface prompt |
| --- | --- | --- |
| `travel-marker` | Icona sulla mappa | `Explorer's field table with blank map paper, compass, pin-like markers and a distant terrain glimpse at edges, high clarity center for placing a location marker.` |

### Quick tools

| Surface key | UI surface | Surface prompt |
| --- | --- | --- |
| `journal` | Diario | `Open traveler’s journal on a wood desk, pages intentionally blank and without marks, fountain pen, dried flower and candle at edges, warm quiet writing surface through center.` |
| `dice` | Dadi | `Felt gaming table with a few elegant polyhedral dice and coin-like tokens placed only around corners, rich directional light, uncluttered center for rolling results.` |
| `ai` | AI | `Arcane consultation chamber: crystal lens, brass astrolabe and very faint non-readable constellations along outer edges, thoughtful teal-violet glow, calm central conversation space.` |
| `audio` | Audio | `Enchanted music room: lute, hand drum, strings and warm lanterns resting at edges, dark acoustic wood, smooth low-noise center for a soundtrack library.` |
| `theft` | Furto | `Shadowed lockpicker's workshop: lock mechanisms, fine tools, gloves and coin purse arranged at edges, cool stealthy lighting, clear center with no criminal symbols or text.` |

### Master and administrator workspace

| Surface key | UI surface | Surface prompt |
| --- | --- | --- |
| `tools` | Strumenti | `Game-master operations hall: organized shelves, campaign cases, map tubes, tools and soft lanterns at edges, confident neutral command atmosphere, exceptionally clear center for dense administration panels.` |

## Coverage checklist

For each theme, create images in this order:

```text
dashboard, personaggio, skills, competencies, creation, combat, travel, market,
lore, media, guide, settings,
media-preview, media-move, media-confirm, settings-restart, image-picker, weather,
character-overview, character-rest, effect-preset, item-editor,
combat-map-editor, combat-map-settings, combat-import-fighters,
combat-manage-characters, combat-import-copy, combat-map-backups,
combat-character-public, combat-character-manage, combat-map-manager,
combat-quick-actions,
item-detail, lore-npc, lore-faction-editor, lore-npc-editor, lore-reactions,
lore-faction-history, lore-timeline-event, market-shop-editor,
skills-reminder, skills-unlock, skills-detail, skills-create, skills-xp,
skills-progression, skills-stats, skills-effects, skills-button-editor,
travel-marker,
journal, dice, ai, audio, theft,
tools
```

Six themes × 56 surfaces = **336 images**. Current seeds assign placeholder
art to pages, quick tools, and `tools`; all 38 modal surfaces are intentionally
blank until artwork is selected in **Gestione → Temi**.

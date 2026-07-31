# Item Special-Rules Review Guide

Date: 2026-07-30

How to review the `speciale` items, move their unconvertible Elder effects into the new
`regole_speciali` field, and let the flag clear itself. Written for a human master working
through the Item Management triage panel, and for an LLM or script doing the same pass in bulk.

## 1. What the new field is

`Oggetto.regole_speciali` ("Regole speciali") is free text: the curated, table-readable version
of a rule the engine cannot compute. It is additive — the eight `effetto_1…effetto_8` fields keep
the original Elder wording untouched as provenance.

It is not only a display field. Saving it also **records which Elder texts it covers**, in
`metadata.descriptiveEffectsReviewed`. That list is what actually releases an item:

- `compute_special_reasons()` (`backend/core/item_special.py`) reports `effetti_descrittivi`
  only for unconvertible texts **not** in that list;
- so an item whose descriptive texts are all covered stops being flagged for that reason;
- and if an `effetto_N` is later edited, the new wording is not covered, and the item returns
  to the review queue by itself.

The acknowledgement is stored rather than inferred from the text, because a curated rule is a
rewrite, not a quote — it could never be matched back to the original wording.

**Saving `regole_speciali` does not clear `speciale` on its own.** It only removes the *reason*.
The flag is cleared by the existing **Ricontrolla** action (`items.recheckSpecial`), which
re-derives every reason from live fields and clears the flag only when none remain. That
separation is deliberate: curation and mutation stay two explicit steps.

### Editing surfaces

| Surface | Where |
| --- | --- |
| Item editor modal | `frontend/src/features/character/ItemEditorModal.tsx`, section "Effetti Elder conservati" |
| Item comparer | `frontend/src/features/management/ItemManagementPage.tsx`, row "Regole speciali" |
| Item compendium | own section, shown above the raw Elder text |
| Market detail, equipment inspector | `specialRules` in the item payload |

## 2. Ground truth before the pass

Measured on `db.sqlite3` on 2026-07-30, with the new field in place and empty everywhere:

| Figure | Count |
| --- | --- |
| Items flagged `speciale` | 2 103 |
| …whose only reason is `effetti_descrittivi` | 2 086 |
| …of those, template + not archived (the market-relevant set) | **1 834** |
| Items flagged for anything else (non-model, temporary, missing type) | 17 |
| Distinct unconvertible effect texts | 421 |
| Total occurrences of those texts | 2 111 |

Rarity of the 1 838 flagged templates: 187 at 1, 161 at 2, **1 285 at 3**, 198 at 4, 7 at 5.
Types are dominated by worn accessories — anello 254, orecchino 253, spilla 252, fascia 252,
cintura 252, amuleto 246, pozione 198.

Re-check these numbers before starting; they are the baseline the diff report is judged against.

### Decisions taken on 2026-07-30, and their effect on the baseline

| Decision | Effect |
| --- | --- |
| `barr_fis` / `barr_mag` are a mistake — the 140 barrier items were archived, not deleted (zero inventory and shop references, so restoring them is a flag flip) | −120 active flagged |
| `Cammuffare` is Elder's misspelling of the competenza `Camuffare` — aliased in `COMPETENCE_TARGETS`, then `repair_legacy_item_effects --apply` backfilled 56 structured effects | −48 active flagged, all 21 competences now import |
| Restore potions (`danno`, `mana_speso`, `energia_spesa`, `potere_speso`) stay curated text until a consumable-restore effect exists | 40 items curable, not escalated |
| `mod gen A (B)` stays undecoded | 60 items deliberately left flagged |

Active flagged templates after those three actions: **1 670**. Market pool: 3 491.

The first full curation pass then ran on the same day and wrote **1 168** items, all of which left
the queue. Active flagged templates: **502**. Market pool: **4 659**, up from 3 443 at the start.
The residue was `mod.gen.` (60), `blink` (60), `recast` (60), `raggioarcano` (60), `pontedimana` (42)
and a tail of families with fewer than 30 items each.

A second pass on 2026-07-31 curated `mod_gen`, `ponte_di_mana` and `recast` (162 items) once their
meaning was confirmed with the table master:

- **`mod gen A (B)`**: for 2 turns, +A to the modificatore generale, then pay B stanchezza.
  Activatable, usable once per combat. `A` and `B` are read straight off the item text — no
  formula needed at the table.
- **`Ponte di Mana SI`**: fixed sentence regardless of level — *"Permette di scambiare mana tra
  persone che vogliono. Tocco."*
- **`fino a X mana: N mana`** (recast): recast an identical spell already cast this session for
  free in mana, provided its original cost was ≤ N, paying 1 PA and 3 Energia instead. Max 2 per
  combat, max 1 per hour outside combat.

Active flagged templates after that batch: **340**.

A third pass, same day, curated `teletrasporto` (60 items — `Anello blink` items, same `A (B)`
shape as `mod_gen`; confirmed meaning: teleport A metres at a cost of B PA, B mana and a flat
1 Energia, no stated per-use limit). Active flagged templates: **280**.

A fourth pass curated `danno_raggio` and three duration-tiered potion families (87 items total),
each confirmed against the item's own `descrizione` field, not guessed from the effect text alone:

- **`danno raggio: <base> + lvpg<*/mult>`** ("raggio arcano" items) — the item's `descrizione`
  spells out the full ability (*"casti un raggio arcano fino a 20 metri. infligge danno puro.
  + 1pa/lv oggetto + 1 en/lv oggetto. Una volta a combat."*), so the curated text states the full
  cast, not just the damage formula.
- **`Invisibile per X turni -M`** / **`Voli per X turni -M`** — `X` is a literal placeholder, `M`
  (which equals the `(M)` in the item name) is the actual duration in turns.
- **`Curati da Effetti nocivi -M`** — the item's own `descrizione` ("Ne curi X random") confirms
  `M` random harmful effects/illnesses are cured, not a flat list.

Active flagged templates after that batch: **193**.

A fifth pass, same day, curated the remaining potion families once the table master supplied what
`descrizione` alone couldn't (28 items):

- **`crei fumo per 2 turni -M`** (fumogeno) — `M` is a radius (per `descrizione`); confirmed unit
  is metres (1 hex = 1 metro in this system).
- **`50% di evitare danno fisico -M`** (intangibilità) — `M` counts **attacks that had a chance
  to hit**, not attacks actually evaded: the effect wears off after `M` such attacks regardless of
  whether the 50% ever favoured the drinker, and an attack the enemy misses on its own doesn't
  count. Easy to get wrong from the text alone — this needed the master's ruling, not a guess.
- **`Attacco 5 Turni -M`** — for 5 turns, +M to `Personaggio.attacco`. Left as curated text rather
  than a structured effect because the field only carries permanent equipment bonuses, not timed
  consumable buffs.
- **`Dopo 10 turni, -50% energia(sul massimale)`** (15 items, all alcoholic drinks) — no formula
  to derive, just "you get drunk": max Energia halves 10 turns after drinking.

Active flagged templates after that batch: **165**. Residue: `mod_gen`'s sibling families are
gone; what's left is smaller and more heterogeneous — light/darkvision utility texts, a
`-PA nemico` / `+ danno a nemico` counter-attack family, and a long tail of near-unique texts.

## 3. Decision tree for one descriptive text

For each unconvertible text on an item, pick exactly one outcome:

1. **Convert it.** The rule is arithmetic on a stat ReDjango already has → add a structured
   entry to `effects` and leave `regole_speciali` alone. Preferred whenever possible: a
   structured effect actually changes the sheet.
2. **Curate it.** The rule is real and playable but the engine has no concept for it → write it
   into `regole_speciali` in plain Italian and let the flag clear.
3. **Leave it flagged.** The text is ambiguous, contradictory, or you cannot tell what it means
   without the original rulebook → change nothing. The review queue is for exactly this.
4. **Escalate it.** The text is arithmetic on a stat ReDjango *does not have yet* → do **not**
   curate it into prose. See §6; hiding a missing stat behind free text is the one outcome that
   makes the data worse.

An item leaves the queue only when every one of its texts has landed on outcome 1 or 2.

## 4. Text families observed in the data

Occurrence counts over the 2 111 unconvertible texts. Use these as batching units: one family at
a time, one decision rule per family, is far more reviewable than one item at a time.

| Family | Occurrences | Examples | Recommended outcome |
| --- | --- | --- | --- |
| Structured shape, unknown target | 236 | `Personaggio.barr_fis +2`, `Cammuffare + 1` | **Escalate** (§6) |
| Contingency / teleport / illusion counters | 364 | `Contingenza spell 1`, `teletrasporto 1 (1)`, `immagini: 3 imm(15 en 3pa)` | Curate |
| Boolean capabilities | 231 | `Ponte di Mana SI`, `Cast Silenzioso SI`, `Sostentamento: SI` | Curate |
| Action / extraction / reroll costs | 189 | `costo 5 en 1 pa 1 magia`, `1 reroll, costo en: 9`, `costo estrazione: gratis` | Curate |
| Range multipliers | 168 | `Range spell * 1.5`, `Range scuola * 3.5`, `Range tutte * 3` | Curate |
| Timed regeneration | 140 | `Rigenera 1 pf ogni 1 ora`, `Rigenera 1 mana ogni 10 min` | Curate |
| Free spell power by school | 98 | `+1 potere free Alterazione`, `+1 potere free Recupero` | Curate |
| Turn-threshold effects | 91 | `Dopo 10 turni, -50% energia(sul massimale)`, `Difesa 5 Turni -1` | Curate |
| Generic modifier shorthand | 73 | `+ mod gen1 (1)`, `+ mod gen2 (2)` | Leave flagged until the shorthand is decoded |
| Everything else | ~521 | `danno fuoco 5 x 10t area 3 hex`, `Iconica!` | Case by case |

Two families deserve a note:

- **Boolean capabilities** are the cheapest win in the whole set: `Cast Silenzioso SI` needs one
  sentence of prose and nothing else. Start here.
- **`+ mod gen1 (1)`** appears 73 times and nobody has yet written down what "mod gen" maps to.
  Decode it once, then the whole family converts or curates in a single batch. Until then it is
  outcome 3 — a guess repeated 73 times is worse than 73 honest flags.

## 5. How to write the rule text

The field is read at the table, mid-session, by someone who has never seen the Elder database.

- Write full Italian sentences, not the Elder shorthand. `Cast Silenzioso SI` becomes
  *"Chi lo indossa può lanciare incantesimi senza pronunciare formule."*
- State cost, duration, and frequency explicitly when the original implies them:
  `1 reroll, costo en: 9` becomes *"Concede 1 reroll al costo di 9 Energia."*
- Keep the table's own vocabulary. **"reroll" is the term in use — never paraphrase it as
  "ripetere il tiro".** The same goes for any other word the group already says out loud.
- One rule per line. Several Elder texts on one item become several lines in one field.
- Do not restate what the structured effects already do — the sheet shows those.
- Do not invent numbers the original did not have. If a value is missing, that is outcome 3.
- Keep the Elder wording out of it; `effetto_N` is still there for anyone who wants the original.

## 6. Escalation: texts blocked by a missing stat

A text already in perfect `Personaggio.<stat> +N` form that fails conversion is a **system gap,
not a text problem**. Curating it into prose hides the gap; the fix is to add the stat, or to map
it in `LEGACY_TARGET_ALIASES` / `COMPETENCE_TARGETS` (`backend/core/legacy_item_import.py`) when
ReDjango already models it under another name. Then `repair_legacy_item_effects --apply` converts
every affected item at once, and they clear with no prose written.

Two such gaps were closed on 2026-07-30 and are worth keeping as worked examples:

- **`cammuffare`** — the label matched nothing because Elder doubles the m. One alias entry, and
  56 competence bonuses imported. Check spelling before concluding a target is missing.
- **`barr_fis` / `barr_mag`** — *not* an alias of `rd_fis`. The `Amuleto rd lv. N` line converts
  cleanly today and the `Amuleto barriera fisica lv. N` line ran alongside it in Elder, so folding
  one into the other would have merged two mechanics. They were archived as a mistake instead.

The remaining resource targets (`danno`, `mana_speso`, `energia_spesa`, `potere_speso`, 40 potions)
are a deliberate exception: they are not passive equipment bonuses but "using this restores N", a
mechanic the engine has no concept for. They are curated as text until a consumable-restore effect
exists, at which point they should be converted properly.

## 7. The bulk revalidation pass

`manage.py curate_item_special_rules` implements this pass. It is a dry run unless `--apply` is
passed, and its rule table — one Elder shorthand to one Italian sentence — is the artefact to
review. Rules that render `None` leave their items flagged on purpose.

```bash
python manage.py curate_item_special_rules
```

Useful flags: `--rule <key>` (repeatable) to run one family at a time, `--limit N` to cap the
write, `--samples N` to widen the examples in the report. The command writes through
`sync_special_rules_review`, so the acknowledgement is recorded exactly as the item editor
records it, and it recomputes `speciale` per item as it goes.

A curated item is no longer `speciale`, so a later change to the rule table would never reach it.
`--recurate` reopens exactly the items this command wrote — they carry
`metadata.specialRulesSource` — and rewrites them with the current wording. Rules a master typed
by hand carry no marker and are never overwritten.

When you edit a sentence in the table, re-run the affected family:

```bash
python manage.py curate_item_special_rules --recurate --rule rigenerazione --apply
```

Dry-run first, always. The pass mutates the live catalogue and there is no undo beyond `backups/`.

1. **Snapshot.** Take a backup before any write.
2. **Select a batch.** One text family (§4) or one `tipo_1` — not "all 1 834".
3. **Dry run.** Produce a report with, per item: id, `nome`, `tipo_1`, each unconvertible text,
   the proposed outcome, and the proposed `regole_speciali` body. Write nothing.
4. **Review the report.** Spot-check at minimum: every item where the proposal drops a text
   without covering it, and a random 10% of the rest.
5. **Apply.** Write `regole_speciali` through `update_item()` so the acknowledgement list is
   recorded — never with a raw `.update()` on the queryset, which bypasses it and leaves the item
   flagged forever.
6. **Recheck.** Run `items.recheckSpecial` over the batch. Confirm `cleared` matches the number
   of items whose last reason was `effetti_descrittivi`.
7. **Verify in a shop.** Regenerate one shop's stock and confirm the released items can appear.
8. **Record.** Note batch, counts, and date in `Builder_docs/V2_SCHEMA_CHANGELOG.md`.

An LLM pass may propose outcomes 1–4 and draft the prose, but step 4 stays human, and step 5 must
run only on an approved report.

### Market impact — do not release all 1 834 at once

Clearing the whole set roughly doubles the accessory pool in shops with items the engine does not
compute: 1 285 of them sit at rarity 3, and six of the seven commonest types are worn slots
(anello, orecchino, spilla, fascia, cintura, amuleto). Every one of them carries a rule a master
must remember to apply by hand.

Market logic is unchanged and needs no change — `speciale=False` is what puts an item back in
circulation. But release in batches, regenerate a shop after each, and look at what the generator
actually produces before moving on. If a family turns out to be too strong for open sale, the
answer is not to re-flag it as `speciale`: use rarity, `lv_loot`, or the region weight, which is
what those fields are for. `speciale` should end this exercise meaning "a human still needs to
look at this", and nothing else.

## 8. Invariants

- Never edit `effetto_1…effetto_8` to clear a flag. The original text is the provenance record.
- Never write `metadata.descriptiveEffectsReviewed` by hand; it is derived by
  `item_services.sync_special_rules_review()` from the current texts at save time.
- Never use **Forza rimozione** (`items.setSpecial`) to clear a batch. It skips every check and
  destroys the evidence that the review was real.
- An item with an empty `regole_speciali` and an unconvertible text must stay flagged. That is
  the queue working, not a bug.

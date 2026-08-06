import { Fragment, type DragEvent as ReactDragEvent, type FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { useApp } from "../../App";
import { ConfirmationModal } from "../../components/ConfirmationModal";
import { ImagePickerModal } from "../../components/ImagePickerModal";
import { Modal } from "../../components/Modal";
import { apiRequest, command, getData, requestId, uploadCombatMapImage } from "../../lib/api";
import type { MediaAsset } from "../../lib/types";
import { CombatMapCanvas } from "./CombatMapCanvas";
import { AttackPanel as CompactAttackPanel } from "./AttackPanel";
import { combatFocusedCharacterId } from "./focus";
import { cellKey, offsetToAxial } from "./hex";
import { MapCalibrationPreview, type MapCalibrationDraft } from "./MapCalibrationPreview";
import { NoteSectionEditor } from "../notes/NoteSectionEditor";
import type { AttackResult, Axial, CombatMap, CombatResource, CombatWorkspace, MapParticipant, PathResult, SpellEconomy, TerrainBadge } from "./types";

const HEX_COLOR_PRESETS = ["#c96e3f", "#d7a63d", "#779447", "#3f8c78", "#397fa9", "#545bb2", "#8755a5", "#b64f78", "#8b6550", "#d8d1b8"] as const;
const EMPTY_COSTS = { pf: 0, mana: 0, energia: 0, potere: 0, pa: 0, stanchezza: 0 };
const FIXED_COST_KEYS = Object.keys(EMPTY_COSTS);
const EMPTY_SPELL_ECONOMY: SpellEconomy = { manaDiscountPerPower: 0, actionPointDiscountPerPower: 0, manaPerEnergy: 0, manaPerActionPoint: 0 };

/** "no tag" non viene mai salvato: appartiene a ogni azione rimasta senza etichette. */
export const UNTAGGED_ACTION_TAG = "no tag";
export const ACTION_TAGS = ["preferito", "incantesimo", "utility", "combat", "non combat", "distanza", "melee", "modalità", UNTAGGED_ACTION_TAG] as const;
export const STORABLE_ACTION_TAGS = ACTION_TAGS.filter((tag) => tag !== UNTAGGED_ACTION_TAG);
export const DEFAULT_ACTION_TAG_FILTERS = ["preferito", "combat", UNTAGGED_ACTION_TAG];

/**
 * Sigle brevi e univoche per i tipi di esagono: le iniziali delle parole nei nomi
 * composti ("Acqua bassa" → AB) e altrimenti il prefisso del nome, allungato finché
 * non smette di collidere ("Sabbia" → SA, "Salita" → SAL).
 */
function terrainLabelCandidates(name: string): string[] {
  const words = name.normalize("NFD").replace(/\p{Diacritic}/gu, "").toUpperCase().split(/[^A-Z0-9]+/).filter(Boolean);
  if (!words.length) return [];
  const candidates = words.length > 1
    ? [words.map((word) => word[0]).join(""), `${words[0].slice(0, 2)}${words[1][0]}`, `${words[0].slice(0, 3)}${words[1][0]}`]
    : [];
  for (let size = 2; size <= 4; size += 1) candidates.push(words[0].slice(0, size));
  return [...new Set(candidates.map((candidate) => candidate.slice(0, 4)).filter((candidate) => candidate.length > 1))];
}

/** Inchiostro leggibile sopra il colore del terreno. */
function terrainInk(color: string): string {
  const hex = /^#[0-9a-f]{6}$/i.test(color) ? color.slice(1) : "808080";
  const [red, green, blue] = [0, 2, 4].map((index) => parseInt(hex.slice(index, index + 2), 16) / 255);
  return .2126 * red + .7152 * green + .0722 * blue > .55 ? "#12160f" : "#fdf6e3";
}

/** Etichette pronte per la mappa: sigla univoca, colore del terreno e testo del tooltip. */
export function buildTerrainBadges(types: CombatWorkspace["hexTypes"]): Record<number, TerrainBadge> {
  const used = new Set<string>();
  const badges: Record<number, TerrainBadge> = {};
  types.forEach((entry) => {
    const candidates = terrainLabelCandidates(entry.name);
    let label = candidates.find((candidate) => !used.has(candidate));
    if (!label) {
      const base = candidates[0] || "TP";
      let suffix = 2;
      while (used.has(`${base}${suffix}`)) suffix += 1;
      label = `${base}${suffix}`;
    }
    used.add(label);
    badges[entry.id] = {
      id: entry.id,
      label,
      name: entry.name,
      color: entry.color,
      ink: terrainInk(entry.color),
      detail: entry.impassable ? "Intransitabile" : `Costo ×${entry.movementMultiplier}`,
    };
  });
  return badges;
}

/**
 * Un incantesimo può costare solo Mana per effetto ("2 Mana per effetto") oppure
 * una parte fissa più una variabile ("15 Mana più 3 Mana per effetto"). `baseMana`
 * è la parte fissa e concorre alla conversione in Energia e PA; `fixedCosts`
 * raccoglie invece i costi fissi nelle altre risorse, che si sommano senza essere
 * convertiti.
 */
type SpellFormula = {
  baseMana: number; effectPerMana: number; minimumMana: number; effectUnit: string; formula: string;
  costSummary: string; fixedCosts: Record<string, number>;
};
type ActiveOption = {
  key: string; name: string; description: string; costs: Record<string, number>;
  sourceSkillId?: number; kind: "cast" | "power"; spell?: SpellFormula;
};
type AttackSelection = { attackerId: number; defenderId: number; sequence: number };

const COMBATANT_DRAG_TYPE = "application/x-redjango-combatant";

function startCombatantDrag(event: ReactDragEvent<HTMLElement>, characterId: number, onDragChange: (id: number | null) => void) {
  event.dataTransfer.effectAllowed = "link";
  event.dataTransfer.setData(COMBATANT_DRAG_TYPE, String(characterId));
  event.dataTransfer.setData("text/plain", String(characterId));
  onDragChange(characterId);
}

function droppedCombatantId(event: ReactDragEvent<HTMLElement>, fallback: number | null) {
  return Number(event.dataTransfer.getData(COMBATANT_DRAG_TYPE) || event.dataTransfer.getData("text/plain")) || fallback;
}

function normalizedCosts(raw: unknown): Record<string, number> {
  const values = raw && typeof raw === "object" ? raw as Record<string, unknown> : {};
  const number = (...keys: string[]) => Math.max(0, Number(keys.map((key) => values[key]).find((value) => value != null) || 0));
  return {
    pf: number("pf", "health"),
    mana: number("mana"),
    energia: number("energia", "energy"),
    potere: number("potere", "power"),
    pa: number("pa", "actionPoints", "action_points"),
    stanchezza: number("stanchezza", "fatigue"),
  };
}

function normalizedSpell(raw: unknown): SpellFormula | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const values = raw as Record<string, unknown>;
  const effectPerMana = Number(values.effectPerMana || 0);
  if (!Number.isFinite(effectPerMana) || effectPerMana <= 0) return undefined;
  return {
    baseMana: Math.max(0, Number(values.baseMana || 0)),
    effectPerMana,
    minimumMana: Math.max(0, Number(values.minimumMana || 0)),
    effectUnit: String(values.effectUnit || "effetto"),
    formula: String(values.formula || ""),
    costSummary: String(values.costSummary || ""),
    fixedCosts: normalizedCosts(values.fixedCosts),
  };
}

/** Mana fisso, Mana comprato con l'effetto e totale richiesto, tenuti distinti. */
export function spellManaBreakdown(effect: number, spell?: SpellFormula, extraFixedMana = 0) {
  const normalizedEffect = Math.max(0, Math.round(effect || 0));
  const fixedMana = Math.max(0, spell?.baseMana || 0) + Math.max(0, Math.round(extraFixedMana || 0));
  const variableMana = spell ? normalizedEffect / spell.effectPerMana : normalizedEffect;
  const requiredMana = Math.ceil(Math.max(spell?.minimumMana || 0, fixedMana + variableMana));
  return { fixedMana, variableMana, requiredMana };
}

export function manaForEffect(effect: number, spell?: SpellFormula, extraFixedMana = 0) {
  return spellManaBreakdown(effect, spell, extraFixedMana).requiredMana;
}

/** Etichette mostrate per un'azione: senza etichette salvate vale "no tag". */
export function actionTagsFor(stored: Record<string, string[]> | undefined, key: string): string[] {
  const saved = stored?.[key];
  const cleaned = Array.isArray(saved) ? STORABLE_ACTION_TAGS.filter((tag) => saved.includes(tag)) : [];
  return cleaned.length ? cleaned : [UNTAGGED_ACTION_TAG];
}

/** Aggiunge o toglie un'etichetta; svuotandola l'azione torna automaticamente "no tag". */
export function toggledActionTags(current: string[], tag: string): string[] {
  const assigned = current.filter((entry) => entry !== UNTAGGED_ACTION_TAG);
  const next = assigned.includes(tag) ? assigned.filter((entry) => entry !== tag) : [...assigned, tag];
  return STORABLE_ACTION_TAGS.filter((entry) => next.includes(entry));
}

export function actionMatchesTagFilters(tags: string[], filters: string[]): boolean {
  return tags.some((tag) => filters.includes(tag));
}

/**
 * Costi di un incantesimo secondo il regolamento originario: Mana, Energia e PA
 * si pagano insieme. Energia e PA nascono dal Mana richiesto prima degli sconti,
 * il Potere totale (usato più gratuito) sconta soltanto Mana e PA, e solo il
 * Potere usato viene speso davvero. I costi fissi dell'incantesimo si sommano ai
 * valori convertiti: non li sostituiscono e non vengono riconvertiti a loro volta.
 * `fixedCosts.mana` non compare qui perché è già dentro `requiredMana`.
 */
export function spellCastCosts(
  fixedCosts: Record<string, number>,
  requiredMana: number,
  powerUsed: number,
  freePower: number,
  economy: SpellEconomy,
): Record<string, number> {
  const mana = Math.max(0, Math.round(requiredMana || 0));
  const spentPower = Math.max(0, Math.round(powerUsed || 0));
  const totalPower = spentPower + Math.max(0, Math.round(freePower || 0));
  const fixed = (key: string) => Math.max(0, Math.round(fixedCosts?.[key] || 0));
  const actionPoints = economy.manaPerActionPoint > 0
    ? Math.ceil(Math.max(0, mana / economy.manaPerActionPoint - totalPower * economy.actionPointDiscountPerPower))
    : 0;
  return {
    pf: fixed("pf"),
    mana: Math.ceil(Math.max(0, mana - totalPower * economy.manaDiscountPerPower)),
    energia: (economy.manaPerEnergy > 0 ? Math.ceil(mana / economy.manaPerEnergy) : 0) + fixed("energia"),
    potere: spentPower + fixed("potere"),
    pa: actionPoints + fixed("pa"),
    stanchezza: fixed("stanchezza"),
  };
}

export function persistentCombatButtonIds(
  buttons: Array<{ id: number; keepActiveInCombat: boolean }>,
  activeIds: number[],
) {
  return buttons.filter((button) => button.keepActiveInCombat && activeIds.includes(button.id)).map((button) => button.id);
}

export function combatEventNeedsRefresh(
  eventId: number,
  cachedEvents: Array<{ id: number }>,
) {
  return !eventId || !cachedEvents.some((entry) => entry.id === eventId);
}

/** Riga leggibile che tiene separata la parte fissa da quella per effetto. */
export function spellCostExplanation(
  mana: { fixedMana: number; variableMana: number; requiredMana: number },
  costs: Record<string, number>,
  totalPower: number,
  economy: SpellEconomy,
): string[] {
  const rounded = Math.round(mana.variableMana * 100) / 100;
  return [
    mana.fixedMana
      ? `Mana richiesto ${mana.fixedMana} fissi + ${rounded} per effetto = ${mana.requiredMana}`
      : `Mana richiesto ${mana.requiredMana} (tutto per effetto)`,
    `Mana ${mana.requiredMana} − ${totalPower} Potere × ${economy.manaDiscountPerPower} = ${costs.mana}`,
    economy.manaPerEnergy > 0
      ? `Energia ${mana.requiredMana} / ${economy.manaPerEnergy} = ${costs.energia}`
      : "Energia: nessuna conversione configurata",
    economy.manaPerActionPoint > 0
      ? `PA ${mana.requiredMana} / ${economy.manaPerActionPoint} − ${totalPower} × ${economy.actionPointDiscountPerPower} = ${costs.pa}`
      : "PA: nessuna conversione configurata",
    `Potere speso ${costs.potere}`,
  ];
}

/** Costi fissi di partenza: la definizione dell'incantesimo vince sui promemoria. */
function fixedCostsForOption(option: ActiveOption) {
  return { ...EMPTY_COSTS, ...(option.spell ? option.spell.fixedCosts : option.costs) };
}

/** L'effetto parte dal minimo che l'incantesimo richiede comunque di pagare. */
function initialEffectForOption(option: ActiveOption) {
  if (!option.spell) return 0;
  const spell = option.spell;
  return Math.max(0, Math.round((spell.minimumMana - spell.baseMana) * spell.effectPerMana));
}

function characterActiveOptions(character: CombatMap["participants"][number]["character"] | undefined): ActiveOption[] {
  if (!character) return [];
  const options: ActiveOption[] = [];
  character.skills.forEach((skill) => {
    const reminders = Array.isArray(skill.activeReminders) ? skill.activeReminders as Array<Record<string, unknown>> : [];
    const spell = normalizedSpell(skill.spell);
    reminders.forEach((reminder, index) => options.push({
      key: `skill:${String(skill.id || index)}:${String(reminder.id || index)}`,
      name: String(reminder.name || skill.name || "Azione attiva"),
      description: String(reminder.description || skill.description || ""),
      costs: normalizedCosts(reminder.costs),
      sourceSkillId: Number(skill.id) || undefined,
      kind: spell || skill.magic ? "cast" : "power",
      spell,
    }));
  });
  character.abilities.forEach((ability, index) => options.push({
    key: `ability:${String(ability.key || index)}`,
    name: String(ability.name || ability.nome || "Potere"),
    description: String(ability.description || ability.descrizione || ""),
    costs: normalizedCosts(ability.costs),
    kind: "power",
  }));
  return options;
}

async function combatAction(action: string, payload: Record<string, unknown>) {
  const id = requestId();
  return apiRequest<CombatWorkspace>("/api/combat/actions/", {
    method: "POST",
    headers: { "X-ReDjango-Action": action, "X-ReDjango-Request-Id": id, "X-ReDjango-Screen": "combat" },
    body: JSON.stringify({ action, requestId: id, context: { screen: "combat" }, payload, meta: { clientVersion: "react-v1" } }),
  });
}

const RESOURCE_SHORT_LABELS: Record<string, string> = { pf: "PF", mana: "MA", energia: "EN", potere: "PO", pa: "PA", stanchezza: "ST" };

/**
 * I giocatori non leggono i PF esatti degli altri combattenti: vedono solo una
 * barra a scaglioni, lunga quanto il limite superiore della fascia raggiunta.
 * Master e admin continuano a vedere barra proporzionale e numeri.
 */
export const HEALTH_BANDS = [
  { key: "empty", width: 0, label: "Nessun PF" },
  { key: "very-low", width: 15, label: "PF molto bassi" },
  { key: "low", width: 40, label: "PF bassi" },
  { key: "ok", width: 70, label: "PF discreti" },
  { key: "high", width: 95, label: "PF alti" },
  { key: "full", width: 100, label: "PF pieni" },
] as const;

export function healthBand(percent: number) {
  const value = Number(percent) || 0;
  if (value <= 0) return HEALTH_BANDS[0];
  if (value < 15) return HEALTH_BANDS[1];
  if (value < 40) return HEALTH_BANDS[2];
  if (value < 70) return HEALTH_BANDS[3];
  if (value < 95) return HEALTH_BANDS[4];
  return HEALTH_BANDS[5];
}

/** Slot sempre leggibili a colpo d'occhio: il resto si scopre solo a 0 PF. */
export const PUBLIC_EQUIPMENT_SLOTS = ["arma", "scudo", "armatura", "chainmail", "veste"];

export function publicEquipmentValue(slot: { slot: string; item: { name: string } | null }, revealAll: boolean) {
  if (!revealAll && !PUBLIC_EQUIPMENT_SLOTS.includes(slot.slot)) return "Vedi a 0 PF";
  return slot.item?.name || "VUOTO";
}

function characterHealth(character: MapParticipant["character"]) {
  return character.resources.find((resource) => resource.key === "pf");
}

function activeCombatWeapon(character: MapParticipant["character"] | undefined) {
  if (!character) return undefined;
  const slot = character.equipment.primaryWeaponSlot || "arma";
  return character.equipment.slots.find((entry) => entry.slot === slot)?.item;
}

function CombatRailResource({ resource, editable, busy, onSave }: {
  resource: CombatResource; editable: boolean; busy: boolean; onSave: (current: number) => void;
}) {
  const [value, setValue] = useState(resource.current);
  useEffect(() => setValue(resource.current), [resource.current]);
  const clamp = (next: number) => Math.max(0, Math.min(resource.maximum, Math.round(next || 0)));
  const commit = (next: number) => {
    const normalized = clamp(next);
    setValue(normalized);
    if (normalized !== resource.current) onSave(normalized);
  };
  const percent = resource.maximum ? Math.max(0, Math.min(100, value / resource.maximum * 100)) : 0;
  return <article className={`combat-rail-resource ${resource.key}`} data-resource={resource.key} tabIndex={editable ? 0 : undefined}>
    <div className="combat-rail-resource-heading"><abbr title={resource.label}>{RESOURCE_SHORT_LABELS[resource.key] || resource.label.slice(0, 2).toUpperCase()}</abbr><span>{resource.label}</span><strong>{value}/{resource.maximum}</strong></div>
    <i className="combat-rail-resource-track"><b style={{ width: `${percent}%`, background: `var(${resource.colorToken}, var(--gold))` }} /></i>
    {editable && <div className="combat-rail-resource-actions">
      <div className="combat-resource-adjustment combat-resource-decrement">
        <button type="button" disabled={busy || value <= 0} onClick={() => commit(value - 20)} aria-label={`Riduci ${resource.label} di 20`}>−20</button>
        <button type="button" disabled={busy || value <= 0} onClick={() => commit(value - 5)} aria-label={`Riduci ${resource.label} di 5`}>−5</button>
        <button type="button" className="combat-resource-adjustment-main" disabled={busy || value <= 0} onClick={() => commit(value - 1)} aria-label={`Riduci ${resource.label}`}>−</button>
      </div>
      <input type="number" min="0" max={resource.maximum} value={value} disabled={busy} aria-label={`Valore ${resource.label}`} onChange={(event) => setValue(clamp(Number(event.target.value)))} onBlur={() => commit(value)} onKeyDown={(event) => { if (event.key === "Enter") event.currentTarget.blur(); }} />
      <div className="combat-resource-adjustment combat-resource-increment">
        <button type="button" className="combat-resource-adjustment-main" disabled={busy || value >= resource.maximum} onClick={() => commit(value + 1)} aria-label={`Aumenta ${resource.label}`}>+</button>
        <button type="button" disabled={busy || value >= resource.maximum} onClick={() => commit(value + 5)} aria-label={`Aumenta ${resource.label} di 5`}>+5</button>
        <button type="button" disabled={busy || value >= resource.maximum} onClick={() => commit(value + 20)} aria-label={`Aumenta ${resource.label} di 20`}>+20</button>
      </div>
    </div>}
  </article>;
}

function CombatantRail({ map, busy, canManage, controlledCharacterId, onSelect, onRemove, onContext, onUpdateResource, onSwitchPrimary }: {
  map: CombatMap; busy: boolean; canManage: boolean; controlledCharacterId: number | null;
  onSelect: (id: number) => void; onRemove: (id: number) => void; onContext?: (participant: MapParticipant) => void;
  onUpdateResource: (characterId: number, resource: string, current: number) => void;
  onSwitchPrimary: (characterId: number) => void;
}) {
  const participant = map.participants.find((entry) => entry.character.id === map.activeCharacterId) || map.participants[0];
  if (!participant) return <aside className="combat-character-rail empty" data-component-type="drawer" data-theme="combat"><strong>Nessun PG</strong><span>Usa “Gestisci personaggi”.</span></aside>;
  const character = participant.character;
  const weapon = activeCombatWeapon(character);
  const projectiles = character.quiver.slots.filter((slot) => slot.item).slice(0, 4);
  const equippedCount = character.equipment.slots.filter((slot) => slot.item).length;
  const editable = canManage || character.id === controlledCharacterId;
  return <aside className="combat-character-rail" data-component-type="drawer" data-theme="combat" aria-label="Combattente attivo" tabIndex={0}>
    <header className="combat-rail-identity" onContextMenu={(event) => { if (!onContext) return; event.preventDefault(); onContext(participant); }}>
      <div className="combat-rail-portrait">{character.portrait ? <img src={character.portrait} alt="" /> : <span>{character.name.slice(0, 2).toUpperCase()}</span>}<small>{character.effects.length || ""}</small></div>
      <div><small>{character.type || "Personaggio"} · lv {character.level}</small><strong>{character.name}</strong><span>{editable ? "Risorse modificabili" : "Solo lettura"}</span></div>
    </header>
    <div className="combat-rail-stats"><span><small>ATK</small><strong>{character.combat.attacco || 0}</strong></span><span><small>DEF</small><strong>{character.combat.difesa || 0}</strong></span><span><small>TIER</small><strong>{character.combat.tier || 0}</strong></span></div>
    <div className="combat-rail-resources">{character.resources.map((resource) => <CombatRailResource key={resource.key} resource={resource} editable={editable} busy={busy} onSave={(current) => onUpdateResource(character.id, resource.key, current)} />)}</div>
    <section className="combat-rail-weapon">
      <span className="action-glyph attack">⚔</span><div><small>Arma pronta</small><strong>{weapon?.name || "Mani nude"}</strong><p>{weapon ? [weapon.weaponType, weapon.weaponLength, weapon.actionPointCost != null ? `${weapon.actionPointCost} PA` : ""].filter(Boolean).join(" · ") : "Nessun costo arma"}</p></div>
      {character.equipment.dualWield && <button type="button" className="button secondary small" disabled={busy || !editable} onClick={() => onSwitchPrimary(character.id)}>Cambia · 0 PA</button>}
    </section>
    <section className="combat-rail-kit"><header><strong>Pronti</strong><small>{equippedCount} equip · {character.quiver.occupied}/{character.quiver.capacity} faretra</small></header><div>{projectiles.length ? projectiles.map((slot) => <span key={slot.id} title={slot.item?.name}>{slot.item?.imageUrl ? <img src={slot.item.imageUrl} alt="" /> : "➶"}</span>) : <small>Faretra vuota</small>}</div></section>
    <section className="combat-rail-effects"><header><strong>Effetti</strong><small>{character.effects.length}</small></header><div>{character.effects.length ? character.effects.slice(0, 8).map((effect) => <span key={`${effect.scope}:${effect.id}:${effect.slot}`} className={effect.temporary ? "temporary" : ""} title={`${effect.name}${effect.description ? ` — ${effect.description}` : ""}`}>{effect.icon || "✦"}</span>) : <small>Nessun effetto</small>}</div></section>
    <nav className="combat-rail-roster" aria-label="Combattenti sulla mappa">{map.participants.map((entry) => {
      const health = entry.character.resources.find((resource) => resource.key === "pf");
      return <div key={entry.id} className={entry.id === participant.id ? "active" : ""} onContextMenu={(event) => { if (!onContext) return; event.preventDefault(); onContext(entry); }}>
        <button type="button" onClick={() => onSelect(entry.character.id)} title={entry.character.name}>{entry.character.portrait ? <img src={entry.character.portrait} alt="" /> : <span>{entry.character.name.slice(0, 2).toUpperCase()}</span>}<span><strong>{entry.character.name}</strong><small>PF {health?.current ?? 0}/{health?.maximum ?? 0}</small></span></button>
        {canManage && <button type="button" className="combat-rail-remove" disabled={busy} onClick={() => onRemove(entry.id)} title={`Rimuovi ${entry.character.name}`}>×</button>}
      </div>;
    })}</nav>
  </aside>;
}

function ActiveCombatantStrip({ map, busy, canManage, draggedCharacterId, onDragChange, onRemove, onContext, onPairSelect, toolbar }: {
  map: CombatMap; busy: boolean; canManage: boolean;
  draggedCharacterId: number | null; onDragChange: (id: number | null) => void;
  onRemove: (id: number) => void; onContext?: (participant: MapParticipant) => void;
  onPairSelect: (attackerId: number, defenderId: number) => void;
  toolbar: ReactNode;
}) {
  const participant = map.participants.find((entry) => entry.character.id === map.activeCharacterId) || map.participants[0];
  const [dropTargetId, setDropTargetId] = useState<number | null>(null);
  if (!participant) return <section className="combat-active-strip combat-active-strip-empty" data-component-type="list" data-theme="combat">
    <header className="combat-active-strip-heading"><div className="combat-active-strip-summary"><span className="combat-live-dot" /><strong>Personaggi attivi</strong><small>0 disponibili · 0 sulla mappa</small></div>{toolbar}</header>
    <div className="combat-active-empty-state"><strong>Nessun personaggio attivo</strong><span>Apri Personaggi per aggiungerne uno alla mappa.</span></div>
  </section>;
  const visibleParticipants = map.participants.filter((entry) => entry.id !== participant.id);
  return <section className="combat-active-strip" data-component-type="list" data-theme="combat" aria-label="Personaggi attivi">
    <header className="combat-active-strip-heading"><div className="combat-active-strip-summary"><span className="combat-live-dot" /><strong>Personaggi attivi</strong><small>{visibleParticipants.length} disponibili · {map.participants.length} sulla mappa</small></div>{toolbar}</header>
    <nav className={`combat-active-roster ${visibleParticipants.length ? "" : "empty"}`}>{visibleParticipants.length ? visibleParticipants.map((entry) => {
      const health = characterHealth(entry.character);
      const healthPercent = health?.maximum ? Math.max(0, Math.min(100, health.current / health.maximum * 100)) : 0;
      const band = healthBand(healthPercent);
      const isDropTarget = dropTargetId === entry.character.id && draggedCharacterId !== entry.character.id;
      return <div
        key={entry.id}
        className={`${draggedCharacterId === entry.character.id ? "dragging" : ""} ${isDropTarget ? "drop-target" : ""}`}
        onContextMenu={(event) => { if (!onContext) return; event.preventDefault(); onContext(entry); }}
        onDragEnter={(event) => { event.preventDefault(); setDropTargetId(entry.character.id); }}
        onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "link"; }}
        onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDropTargetId(null); }}
        onDrop={(event) => {
          event.preventDefault();
          const attackerId = droppedCombatantId(event, draggedCharacterId);
          setDropTargetId(null);
          onDragChange(null);
          if (attackerId && attackerId !== entry.character.id) onPairSelect(attackerId, entry.character.id);
        }}
      >
        <button
          type="button"
          data-combat-character-id={entry.character.id}
          draggable={map.participants.length > 1}
          onDragStart={(event) => startCombatantDrag(event, entry.character.id, onDragChange)}
          onDragEnd={() => { setDropTargetId(null); onDragChange(null); }}
          onClick={() => onContext?.(entry)}
          title={`${entry.character.name} · clic per le azioni, trascina per preparare un attacco`}
        >
          {entry.character.portrait ? <img src={entry.character.portrait} alt="" /> : <span className="combat-active-avatar">{entry.character.name.slice(0, 2).toUpperCase()}</span>}
          <span className="combat-active-copy">
            <strong>{entry.character.name}</strong>
            {canManage && <small>{entry.character.type || "Personaggio"} · lv {entry.character.level}</small>}
            <i className={canManage ? "" : `combat-health-band ${band.key}`} title={canManage ? undefined : band.label} aria-label={canManage ? undefined : `${entry.character.name}: ${band.label}`}><b style={{ width: `${canManage ? healthPercent : band.width}%` }} /></i>
            {canManage && <em>PF {health?.current ?? 0}/{health?.maximum ?? 0}</em>}
          </span>
        </button>
        {canManage && <button type="button" className="combat-active-remove" disabled={busy} onClick={() => onRemove(entry.id)} title={`Rimuovi ${entry.character.name}`}>×</button>}
      </div>;
    }) : <p className="combat-active-empty-copy">Il personaggio selezionato è già nel pannello laterale. Aggiungi un altro combattente per preparare un attacco.</p>}</nav>
  </section>;
}

function SelectedCharacterSidebar({ map, busy, canManage, controlledCharacterId, draggedCharacterId, onDragChange, onContext, onPairSelect, onUpdateResource, onSwitchPrimary, onRemoveQuiverItem }: {
  map: CombatMap; busy: boolean; canManage: boolean; controlledCharacterId: number | null;
  draggedCharacterId: number | null; onDragChange: (id: number | null) => void;
  onContext?: (participant: MapParticipant) => void;
  onPairSelect: (attackerId: number, defenderId: number) => void;
  onUpdateResource: (characterId: number, resource: string, current: number) => void;
  onSwitchPrimary: (characterId: number) => void;
  onRemoveQuiverItem: (characterId: number, slot: string) => void;
}) {
  const participant = map.participants.find((entry) => entry.character.id === map.activeCharacterId) || map.participants[0];
  const [isDropTarget, setIsDropTarget] = useState(false);
  const [quiverMenuSlot, setQuiverMenuSlot] = useState<string | null>(null);
  if (!participant) return null;
  const character = participant.character;
  const weapon = activeCombatWeapon(character);
  const editable = canManage || character.id === controlledCharacterId;
  const projectileSlots = character.quiver.slots.filter((slot) => slot.item);
  return <aside className="combat-selected-character" data-component-type="inspector" data-theme="combat" aria-label={`Dettagli di ${character.name}`}>
    <header
      className={`${draggedCharacterId === character.id ? "dragging" : ""} ${isDropTarget ? "drop-target" : ""}`}
      data-combat-character-id={character.id}
      draggable={map.participants.length > 1}
      tabIndex={0}
      aria-label={`${character.name}: clic per le azioni, trascina per preparare un attacco`}
      onClick={() => onContext?.(participant)}
      onKeyDown={(event) => { if ((event.key === "Enter" || event.key === " ") && onContext) { event.preventDefault(); onContext(participant); } }}
      onContextMenu={(event) => { if (!onContext) return; event.preventDefault(); onContext(participant); }}
      onDragStart={(event) => startCombatantDrag(event, character.id, onDragChange)}
      onDragEnd={() => { setIsDropTarget(false); onDragChange(null); }}
      onDragEnter={(event) => { event.preventDefault(); setIsDropTarget(true); }}
      onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "link"; }}
      onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setIsDropTarget(false); }}
      onDrop={(event) => {
        event.preventDefault();
        const attackerId = droppedCombatantId(event, draggedCharacterId);
        setIsDropTarget(false);
        onDragChange(null);
        if (attackerId && attackerId !== character.id) onPairSelect(attackerId, character.id);
      }}
    >
      <div className="combat-selected-portrait">{character.portrait ? <img src={character.portrait} alt="" /> : <span>{character.name.slice(0, 2).toUpperCase()}</span>}</div>
      <div><strong>{character.name}</strong></div>
    </header>
    <div className="combat-rail-stats"><span><small>ATK</small><strong>{character.combat.attacco || 0}</strong></span><span><small>DEF</small><strong>{character.combat.difesa || 0}</strong></span><span><small>TIER</small><strong>{character.combat.tier || 0}</strong></span></div>
    <div className="combat-selected-resources">{character.resources.map((resource) => <CombatRailResource key={resource.key} resource={resource} editable={editable} busy={busy} onSave={(current) => onUpdateResource(character.id, resource.key, current)} />)}</div>
    <section className="combat-selected-weapon" tabIndex={0}>
      <div className="combat-selected-weapon-heading"><div><strong>{weapon?.name || "Mani nude"}</strong><span>{weapon ? [weapon.weaponType, weapon.weaponLength, weapon.actionPointCost != null ? `${weapon.actionPointCost} PA` : ""].filter(Boolean).join(" · ") : "Nessun costo arma"}</span></div></div>
      {weapon && <div className="combat-weapon-power-popover"><small>Bonus tipo arma</small><strong>{weapon.weaponType || "Tipo non configurato"}</strong>{weapon.weaponTypeBonuses.length ? <ul>{weapon.weaponTypeBonuses.map((bonus) => <li key={bonus}>{bonus}</li>)}</ul> : <p>Nessun bonus speciale configurato per questo tipo.</p>}<span>Lunghezza {weapon.weaponLength || "—"} · profilo {weapon.weaponPower || "—"}</span></div>}
      {character.equipment.dualWield && <button type="button" className="button secondary small" disabled={busy || !editable} onClick={() => onSwitchPrimary(character.id)}>Cambia arma primaria · 0 PA</button>}
    </section>
    <section className="combat-selected-quiver"><header><strong>Faretra</strong><span>{character.quiver.occupied}/{character.quiver.capacity}</span></header><div>{projectileSlots.length ? projectileSlots.map((slot) => <article key={slot.id} className={quiverMenuSlot === slot.slot ? "menu-open" : ""}>
      <button type="button" title={`${slot.item?.name || "Proiettile"}: apri menu`} disabled={!editable || busy} onClick={() => setQuiverMenuSlot((current) => current === slot.slot ? null : slot.slot)}>{slot.item?.imageUrl ? <img src={slot.item.imageUrl} alt="" /> : <span>➶</span>}<small>{slot.item?.name}</small></button>
      {quiverMenuSlot === slot.slot && <div className="combat-quiver-menu" data-component-type="context-menu" data-theme="combat"><strong>{slot.item?.name}</strong><button type="button" disabled={busy} onClick={() => { onRemoveQuiverItem(character.id, slot.slot); setQuiverMenuSlot(null); }}>Rimuovere</button></div>}
    </article>) : <p>Faretra vuota</p>}</div></section>
  </aside>;
}

type MapDraft = {
  mapId?: number; name: string; mapTypeId: number; imageId: number | null; orientation: "pointy" | "flat"; rows: number; columns: number;
  hexSize: number; gridOffsetX: number; gridOffsetY: number; imageScale: number; imageOffsetX: number; imageOffsetY: number;
  viewportScale: number; viewportOffsetX: number; viewportOffsetY: number; fogEnabled: boolean; fogOpacity: number;
};

function MapEditorModal({ workspace, onClose, onSave, onCreateType, busy }: {
  workspace: CombatWorkspace; onClose: () => void; onSave: (draft: MapDraft) => void;
  onCreateType: (values: Record<string, unknown>) => void; busy: boolean;
}) {
  const map = workspace.map;
  const defaultType = workspace.mapTypes[0];
  const [step, setStep] = useState(1);
  const [imagePicker, setImagePicker] = useState(false);
  const [image, setImage] = useState<MediaAsset | null>(null);
  const [draft, setDraft] = useState<MapDraft>({
    mapId: map?.id, name: map?.name || "Nuova mappa", mapTypeId: map?.mapTypeId || defaultType?.id || 0,
    imageId: map?.imageId || null, orientation: map?.orientation || defaultType?.orientation || "pointy",
    rows: map?.rows || defaultType?.rows || 24, columns: map?.columns || defaultType?.columns || 32,
    hexSize: map?.hexSize || 34, gridOffsetX: map?.gridOffsetX || 0, gridOffsetY: map?.gridOffsetY || 0,
    imageScale: map?.imageScale || 1, imageOffsetX: map?.imageOffsetX || 0, imageOffsetY: map?.imageOffsetY || 0,
    viewportScale: map?.viewportScale || 1, viewportOffsetX: map?.viewportOffsetX || 0, viewportOffsetY: map?.viewportOffsetY || 0,
    fogEnabled: map?.fogEnabled || false, fogOpacity: map?.fogOpacity ?? .88,
  });
  const number = (key: keyof MapDraft, value: string) => setDraft((current) => ({ ...current, [key]: Number(value) }));
  const selectedType = workspace.mapTypes.find((entry) => entry.id === draft.mapTypeId);
  return <>
    <Modal surface="combat-map-editor" title={map ? "Editor della mappa" : "Crea una mappa di combattimento"} onClose={onClose} wide footer={<>
      <span className="wizard-progress">Passo {step} di 3</span>
      {step > 1 && <button className="button secondary" onClick={() => setStep(step - 1)}>Indietro</button>}
      {step < 3 ? <button className="button primary" onClick={() => setStep(step + 1)}>Continua</button> : <button className="button primary" disabled={busy || !draft.mapTypeId} onClick={() => onSave(draft)}>Salva mappa</button>}
    </>}>
      <div className="combat-map-wizard">
        <nav><button className={step === 1 ? "active" : ""} onClick={() => setStep(1)}>1 · Identità</button><button className={step === 2 ? "active" : ""} onClick={() => setStep(2)}>2 · Griglia</button><button className={step === 3 ? "active" : ""} onClick={() => setStep(3)}>3 · Immagine e vista</button></nav>
        {step === 1 && <div className="combat-wizard-step">
          <label>Nome<input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
          <label>Tipo mappa<select value={draft.mapTypeId} onChange={(event) => {
            const next = workspace.mapTypes.find((entry) => entry.id === Number(event.target.value));
            setDraft({ ...draft, mapTypeId: Number(event.target.value), orientation: next?.orientation || draft.orientation, rows: next?.rows || draft.rows, columns: next?.columns || draft.columns });
          }}>{workspace.mapTypes.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select><small>{selectedType?.description}</small></label>
          <div className="combat-map-image-choice">{(image?.url || map?.imageUrl) ? <img src={image?.thumbnailUrl || image?.url || map?.imageUrl} alt="" /> : <div>Nessuna immagine selezionata</div>}<button className="button secondary" type="button" onClick={() => setImagePicker(true)}>Scegli o carica immagine</button></div>
          <details><summary>Crea un nuovo tipo mappa</summary><form className="compact-form" onSubmit={(event) => { event.preventDefault(); const values = new FormData(event.currentTarget); onCreateType({ name: values.get("name"), slug: values.get("slug"), description: values.get("description"), orientation: values.get("orientation"), rows: Number(values.get("rows")), columns: Number(values.get("columns")) }); }}>
            <label>Nome<input name="name" required /></label><label>Chiave<input name="slug" required /></label><label>Descrizione<input name="description" /></label>
            <label>Orientamento<select name="orientation"><option value="pointy">Punta in alto</option><option value="flat">Lato in alto</option></select></label>
            <label>Righe<input name="rows" type="number" min="1" defaultValue="24" /></label><label>Colonne<input name="columns" type="number" min="1" defaultValue="32" /></label>
            <button className="button secondary" disabled={busy}>Crea tipo</button>
          </form></details>
        </div>}
        {step === 2 && <div className="combat-wizard-step grid-controls">
          <label>Orientamento<select value={draft.orientation} onChange={(event) => setDraft({ ...draft, orientation: event.target.value as "pointy" | "flat" })}><option value="pointy">Punta in alto</option><option value="flat">Lato in alto</option></select></label>
          <label>Righe<input type="number" min="1" max="200" value={draft.rows} onChange={(event) => number("rows", event.target.value)} /></label>
          <label>Colonne<input type="number" min="1" max="200" value={draft.columns} onChange={(event) => number("columns", event.target.value)} /></label>
          <label>Dimensione esagono<input type="range" min="8" max="90" value={draft.hexSize} onChange={(event) => number("hexSize", event.target.value)} /><output>{draft.hexSize}px</output></label>
          <label>Griglia X<input type="number" value={draft.gridOffsetX} onChange={(event) => number("gridOffsetX", event.target.value)} /></label>
          <label>Griglia Y<input type="number" value={draft.gridOffsetY} onChange={(event) => number("gridOffsetY", event.target.value)} /></label>
        </div>}
        {step === 3 && <div className="combat-wizard-step grid-controls">
          <label>Scala immagine<input type="range" min=".1" max="4" step=".05" value={draft.imageScale} onChange={(event) => number("imageScale", event.target.value)} /><output>{draft.imageScale.toFixed(2)}×</output></label>
          <label>Immagine X<input type="number" value={draft.imageOffsetX} onChange={(event) => number("imageOffsetX", event.target.value)} /></label>
          <label>Immagine Y<input type="number" value={draft.imageOffsetY} onChange={(event) => number("imageOffsetY", event.target.value)} /></label>
          <label>Zoom vista<input type="range" min=".2" max="3" step=".05" value={draft.viewportScale} onChange={(event) => number("viewportScale", event.target.value)} /><output>{draft.viewportScale.toFixed(2)}×</output></label>
          <label>Vista X<input type="number" value={draft.viewportOffsetX} onChange={(event) => number("viewportOffsetX", event.target.value)} /></label>
          <label>Vista Y<input type="number" value={draft.viewportOffsetY} onChange={(event) => number("viewportOffsetY", event.target.value)} /></label>
          <p className="callout">Tutti questi valori restano modificabili qui e dall'Amministrazione Django anche dopo il salvataggio.</p>
        </div>}
      </div>
    </Modal>
    {imagePicker && <ImagePickerModal selectedId={draft.imageId} usageType="map" defaultGroup="Mappe combattimento" defaultTitle={draft.name} onSelect={(asset) => { setImage(asset); setDraft({ ...draft, imageId: asset?.id || null }); }} onClose={() => setImagePicker(false)} />}
  </>;
}

function UnifiedMapEditorModal({ workspace, createNew, onClose, onSave, onCreateType, busy }: {
  workspace: CombatWorkspace;
  createNew: boolean;
  onClose: () => void;
  onSave: (draft: MapCalibrationDraft, file: File | null, convertToWebp: boolean) => Promise<void>;
  onCreateType: (values: Record<string, unknown>) => void;
  busy: boolean;
}) {
  const { media } = useApp();
  const map = createNew ? null : workspace.map;
  const defaultType = workspace.mapTypes[0];
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState("");
  const [convertToWebp, setConvertToWebp] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<MapCalibrationDraft>({
    mapId: map?.id,
    name: map?.name || "Nuova mappa",
    mapTypeId: map?.mapTypeId || defaultType?.id || 0,
    imageId: map?.imageId || null,
    orientation: map?.orientation || defaultType?.orientation || "pointy",
    rows: map?.rows || defaultType?.rows || 24,
    columns: map?.columns || defaultType?.columns || 32,
    hexSize: map?.hexSize || 34,
    gridOffsetX: map?.gridOffsetX || 0,
    gridOffsetY: map?.gridOffsetY || 0,
    imageScale: map?.imageScale || 1,
    imageOffsetX: map?.imageOffsetX || 0,
    imageOffsetY: map?.imageOffsetY || 0,
    viewportScale: map?.viewportScale || 1,
    viewportOffsetX: map?.viewportOffsetX || 0,
    viewportOffsetY: map?.viewportOffsetY || 0,
    fogEnabled: map?.fogEnabled || false,
    fogOpacity: map?.fogOpacity ?? .88,
  });
  useEffect(() => {
    if (!file) { setFilePreview(""); return; }
    const url = URL.createObjectURL(file);
    setFilePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  const number = (key: keyof MapCalibrationDraft, value: string) => setDraft((current) => ({ ...current, [key]: Number(value) }));
  const adjustHexSize = (delta: number) => setDraft((current) => ({ ...current, hexSize: Math.max(8, Math.min(100, Math.round((current.hexSize + delta) * 10) / 10)) }));
  const selectedType = workspace.mapTypes.find((entry) => entry.id === draft.mapTypeId);
  const mapAssets = media.filter((asset) => asset.usageType === "map" || asset.id === map?.imageId);
  const selectedAsset = media.find((asset) => asset.id === draft.imageId);
  const imageUrl = filePreview || selectedAsset?.url || (draft.imageId === map?.imageId ? map.imageUrl : "");
  const save = async () => {
    setSaving(true);
    setError("");
    try { await onSave(draft, file, convertToWebp); }
    catch (saveError) { setError((saveError as Error).message); }
    finally { setSaving(false); }
  };

  return <Modal surface="combat-map-settings"
    title={map ? `Modifica ${map.name}` : "Nuova mappa di combattimento"}
    onClose={onClose}
    wide
    className="combat-map-editor-modal"
    footer={<><span className="wizard-progress">Anteprima e valori vengono salvati nello stesso oggetto mappa.</span><button className="button secondary" onClick={onClose}>Annulla</button><button className="button primary" disabled={busy || saving || !draft.mapTypeId || !draft.name.trim()} onClick={save}>{saving ? "Preparazione…" : "Salva mappa"}</button></>}
  >
    <div className="combat-map-editor-layout">
      <aside className="combat-map-editor-controls">
        {error && <p className="form-error">{error}</p>}
        <fieldset><legend>Mappa</legend>
          <label>Nome<input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
          <label>Tipo<select value={draft.mapTypeId} onChange={(event) => {
            const next = workspace.mapTypes.find((entry) => entry.id === Number(event.target.value));
            setDraft({ ...draft, mapTypeId: Number(event.target.value), orientation: next?.orientation || draft.orientation, rows: next?.rows || draft.rows, columns: next?.columns || draft.columns });
          }}>{workspace.mapTypes.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select><small>{selectedType?.description}</small></label>
        </fieldset>

        <fieldset><legend>Immagine</legend>
          <label className="map-file-input">Importa file<input type="file" accept="image/*" onChange={(event) => {
            const next = event.target.files?.[0] || null;
            setFile(next);
            if (next) setDraft((current) => ({ ...current, imageId: null, imageScale: 1, imageOffsetX: 0, imageOffsetY: 0 }));
          }} /></label>
          <label>Oppure dall'archivio<select value={file ? "" : draft.imageId || ""} onChange={(event) => { setFile(null); setDraft({ ...draft, imageId: Number(event.target.value) || null }); }}><option value="">Nessuna</option>{mapAssets.map((asset) => <option key={asset.id} value={asset.id}>{asset.title} · {asset.group}</option>)}</select></label>
          <label className="combat-webp-choice"><input type="checkbox" checked={convertToWebp} disabled={!file} onChange={(event) => setConvertToWebp(event.target.checked)} /><span><strong>Converti in WebP al 75%</strong><small>Stessa larghezza e altezza in pixel, file più leggero.</small></span></label>
          <div className="combat-editor-number-grid"><label>Scala<input type="number" min=".1" max="4" step=".05" value={draft.imageScale} onChange={(event) => number("imageScale", event.target.value)} /></label><label>X<input type="number" step="1" value={Math.round(draft.imageOffsetX)} onChange={(event) => number("imageOffsetX", event.target.value)} /></label><label>Y<input type="number" step="1" value={Math.round(draft.imageOffsetY)} onChange={(event) => number("imageOffsetY", event.target.value)} /></label></div>
        </fieldset>

        <fieldset><legend>Griglia esagonale</legend>
          <div className="combat-editor-number-grid"><label>Orientamento<select value={draft.orientation} onChange={(event) => setDraft({ ...draft, orientation: event.target.value as "pointy" | "flat" })}><option value="pointy">Punta in alto</option><option value="flat">Lato in alto</option></select></label><label>Colonne<input type="number" min="1" max="200" value={draft.columns} onChange={(event) => number("columns", event.target.value)} /></label><label>Righe<input type="number" min="1" max="200" value={draft.rows} onChange={(event) => number("rows", event.target.value)} /></label></div>
          <label className="combat-editor-range combat-hex-size-control"><span>Dimensione esagono</span><button type="button" aria-label="Riduci la dimensione di 0,1 pixel" onClick={() => adjustHexSize(-.1)}>−</button><input type="range" min="8" max="100" step=".1" value={draft.hexSize} onChange={(event) => number("hexSize", event.target.value)} /><button type="button" aria-label="Aumenta la dimensione di 0,1 pixel" onClick={() => adjustHexSize(.1)}>+</button><output>{draft.hexSize.toFixed(1)} px</output></label>
          <div className="combat-editor-number-grid"><label>Griglia X<input type="number" step="1" value={Math.round(draft.gridOffsetX)} onChange={(event) => number("gridOffsetX", event.target.value)} /></label><label>Griglia Y<input type="number" step="1" value={Math.round(draft.gridOffsetY)} onChange={(event) => number("gridOffsetY", event.target.value)} /></label></div>
        </fieldset>

        <details className="combat-editor-advanced"><summary>Vista iniziale e nuovo tipo</summary>
          <div className="combat-editor-number-grid"><label>Zoom vista<input type="number" min=".05" max="4" step=".05" value={draft.viewportScale} onChange={(event) => number("viewportScale", event.target.value)} /></label><label>Vista X<input type="number" value={draft.viewportOffsetX} onChange={(event) => number("viewportOffsetX", event.target.value)} /></label><label>Vista Y<input type="number" value={draft.viewportOffsetY} onChange={(event) => number("viewportOffsetY", event.target.value)} /></label></div>
          <label className="combat-webp-choice"><input type="checkbox" checked={draft.fogEnabled} onChange={(event) => setDraft({ ...draft, fogEnabled: event.target.checked })} /><span><strong>Nebbia di guerra iniziale</strong><small>Gli esagoni restano nascosti finche il Master non li rivela.</small></span></label>
          <label className="combat-editor-range">Opacita nebbia<input type="range" min=".25" max="1" step=".05" value={draft.fogOpacity} onChange={(event) => number("fogOpacity", event.target.value)} /><output>{Math.round(draft.fogOpacity * 100)}%</output></label>
          <form className="combat-map-type-form" onSubmit={(event) => { event.preventDefault(); const values = new FormData(event.currentTarget); onCreateType({ name: values.get("name"), slug: values.get("slug"), description: values.get("description"), orientation: values.get("orientation"), rows: Number(values.get("rows")), columns: Number(values.get("columns")) }); }}>
            <strong>Crea tipo mappa</strong><label>Nome<input name="name" required /></label><label>Chiave<input name="slug" required /></label><label>Orientamento<select name="orientation"><option value="pointy">Punta in alto</option><option value="flat">Lato in alto</option></select></label><label>Righe<input name="rows" type="number" min="1" defaultValue="24" /></label><label>Colonne<input name="columns" type="number" min="1" defaultValue="32" /></label><button className="button secondary small" disabled={busy}>Crea tipo</button>
          </form>
        </details>
      </aside>
      <MapCalibrationPreview draft={draft} imageUrl={imageUrl} onChange={setDraft} />
    </div>
  </Modal>;
}

function CharacterImportModal({ workspace, busy, onClose, onImport }: {
  workspace: CombatWorkspace; busy: boolean; onClose: () => void;
  onImport: (source: { characterId?: number; templateId?: number; count: number; footprint: Axial[] }) => void;
}) {
  const [tab, setTab] = useState<"existing" | "templates">("existing");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [count, setCount] = useState(1);
  const [shape, setShape] = useState("1");
  const footprint: Record<string, Axial[]> = { "1": [{ q: 0, r: 0 }], "2h": [{ q: 0, r: 0 }, { q: 1, r: 0 }], "2v": [{ q: 0, r: 0 }, { q: 0, r: 1 }], "3": [{ q: 0, r: 0 }, { q: 1, r: 0 }, { q: 0, r: 1 }], "4": [{ q: 0, r: 0 }, { q: 1, r: 0 }, { q: 0, r: 1 }, { q: 1, r: 1 }] };
  const entries = tab === "existing" ? workspace.characterCatalog : workspace.templates;
  const visible = entries.filter((entry) => `${entry.name} ${"description" in entry ? entry.description : ""}`.toLocaleLowerCase("it").includes(query.toLocaleLowerCase("it")));
  return <Modal surface="combat-import-fighters" title="Importa combattenti" onClose={onClose} wide footer={<><button className="button secondary" onClick={onClose}>Annulla</button><button className="button primary" disabled={!selected || busy} onClick={() => onImport({ [tab === "existing" ? "characterId" : "templateId"]: selected, count, footprint: footprint[shape] })}>Importa {count > 1 ? `${count} copie` : "copia completa"}</button></>}>
    <div className="combat-import-layout">
      <aside>
        <div className="segmented"><button className={tab === "existing" ? "active" : ""} onClick={() => { setTab("existing"); setSelected(null); }}>Esistenti</button><button className={tab === "templates" ? "active" : ""} onClick={() => { setTab("templates"); setSelected(null); }}>Template</button></div>
        <label>Cerca<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <label>Numero copie<input type="number" min="1" max="20" value={count} onChange={(event) => setCount(Math.max(1, Number(event.target.value)))} /></label>
        <label>Sagoma<select value={shape} onChange={(event) => setShape(event.target.value)}><option value="1">1 esagono</option><option value="2h">2 orizzontali</option><option value="2v">2 verticali</option><option value="3">3 a triangolo</option><option value="4">4 compatta</option></select></label>
        <p>Ogni importazione crea un personaggio indipendente con equipaggiamento, zaino, faretra, effetti, note, competenze e skill. Potrai eliminarlo da Gestione Personaggi.</p>
      </aside>
      <div className="combat-import-list">{visible.map((entry) => <button key={entry.id} className={selected === entry.id ? "active" : ""} onClick={() => setSelected(entry.id)}>
        {"imageUrl" in entry && entry.imageUrl ? <img src={entry.imageUrl} alt="" /> : <span>{entry.name.slice(0, 2).toUpperCase()}</span>}
        <div><strong>{entry.name}</strong><small>{"description" in entry ? entry.description : `${entry.type} · livello ${entry.level} · ${entry.races.join(" / ") || "nessuna razza"}`}</small></div>
      </button>)}</div>
    </div>
  </Modal>;
}

type CharacterManagerSource = { characterId?: number; templateId?: number; footprint: Axial[] };
type UnitGenerationSource = { unitId: number; level: number; variant: string; footprint: Axial[] };
const LEVEL_PRESETS = [1, 5, 10, 15, 20];
const clampLevel = (value: number) => Math.max(1, Math.min(20, Math.round(value) || 1));

function LevelControl({ value, onChange, label }: { value: number; onChange: (level: number) => void; label: string }) {
  return <div className="combat-level-control" role="group" aria-label={label}>
    <input type="range" min="1" max="20" value={value} onChange={(event) => onChange(clampLevel(Number(event.target.value)))} />
    <input type="number" min="1" max="20" value={value} onChange={(event) => onChange(clampLevel(Number(event.target.value)))} />
  </div>;
}

function CharacterManagerModal({ workspace, busy, onClose, onActivate, onDuplicate, onGenerate, onRemove }: {
  workspace: CombatWorkspace;
  busy: boolean;
  onClose: () => void;
  onActivate: (characterId: number, footprint: Axial[]) => Promise<void>;
  onDuplicate: (source: CharacterManagerSource) => Promise<void>;
  onGenerate: (source: UnitGenerationSource) => Promise<void>;
  onRemove: (participantId: number) => Promise<void>;
}) {
  const map = workspace.map;
  const [tab, setTab] = useState<"existing" | "templates" | "units">("existing");
  const [query, setQuery] = useState("");
  const [shape, setShape] = useState("1");
  const [unitLevels, setUnitLevels] = useState<Record<number, number>>({});
  const [unitVariant, setUnitVariant] = useState("auto");
  const [unitCategory, setUnitCategory] = useState("");
  const [unitKind, setUnitKind] = useState("");
  const [unitReadyOnly, setUnitReadyOnly] = useState(false);
  const [defaultUnitLevel, setDefaultUnitLevel] = useState(1);
  const [working, setWorking] = useState(false);
  const [duplicate, setDuplicate] = useState<{ id: number; name: string } | null>(null);
  const unitCategories = useMemo(
    () => Array.from(new Set(workspace.unitCatalog.map((unit) => unit.category).filter(Boolean))).sort((left, right) => left.localeCompare(right, "it")),
    [workspace.unitCatalog],
  );
  const unitFiltersActive = Boolean(unitCategory || unitKind || unitReadyOnly);
  const footprints: Record<string, Axial[]> = {
    "1": [{ q: 0, r: 0 }],
    "2h": [{ q: 0, r: 0 }, { q: 1, r: 0 }],
    "2v": [{ q: 0, r: 0 }, { q: 0, r: 1 }],
    "3": [{ q: 0, r: 0 }, { q: 1, r: 0 }, { q: 0, r: 1 }],
    "4": [{ q: 0, r: 0 }, { q: 1, r: 0 }, { q: 0, r: 1 }, { q: 1, r: 1 }],
  };
  if (!map) return null;
  const activeIds = new Set(map.activeCharacterIds);
  const entries = tab === "existing"
    ? workspace.characterCatalog
    : tab === "templates"
      ? workspace.templates
      : workspace.unitCatalog;
  const visible = [...entries]
    .filter((entry) => `${entry.name} ${"description" in entry ? entry.description : ""} ${"category" in entry ? entry.category : ""}`.toLocaleLowerCase("it").includes(query.toLocaleLowerCase("it")))
    .filter((entry) => tab !== "units" || !unitCategory || ("category" in entry && entry.category === unitCategory))
    .filter((entry) => tab !== "units" || !unitKind || ("generationKind" in entry && (unitKind === "none" ? entry.generationKind === "" : entry.generationKind === unitKind)))
    .filter((entry) => tab !== "units" || !unitReadyOnly || ("ready" in entry && entry.ready))
    .sort((left, right) => {
      if (tab === "units" && "ready" in left && "ready" in right) return Number(right.ready) - Number(left.ready) || left.name.localeCompare(right.name, "it");
      return Number(tab === "existing" && activeIds.has(left.id)) - Number(tab === "existing" && activeIds.has(right.id)) || left.name.localeCompare(right.name, "it");
    });
  const run = async (operation: () => Promise<void>) => {
    setWorking(true);
    try { await operation(); }
    finally { setWorking(false); }
  };
  const locked = busy || working;

  return <>
    <Modal surface="combat-manage-characters" title="Gestisci personaggi" onClose={onClose} wide className="combat-character-manager-modal" footer={<><span className="wizard-progress">I personaggi attivi restano associati a questa mappa.</span><button className="button secondary" onClick={onClose}>Chiudi</button></>}>
      <div className="combat-character-manager">
        <section className="combat-manager-active">
          <header><div><p className="eyebrow">Sulla mappa</p><h3>Personaggi attivi</h3></div><strong>{map.participants.length}</strong></header>
          <div className="combat-manager-active-list">{map.participants.map((participant) => {
            const health = participant.character.resources.find((resource) => resource.key === "pf");
            return <article key={participant.id}>
              <span className="combat-manager-avatar">{participant.character.portrait ? <img src={participant.character.portrait} alt="" /> : participant.character.name.slice(0, 2).toUpperCase()}</span>
              <div><strong>{participant.character.name}</strong><span><i><b style={{ width: `${Math.max(0, Math.min(100, health?.percent || 0))}%` }} /></i><small>{health?.current ?? 0}/{health?.maximum ?? 0} PF</small></span></div>
              <button type="button" disabled={locked} onClick={() => run(() => onRemove(participant.id))} title="Rimuovi dalla mappa">×</button>
            </article>;
          })}</div>
        </section>

        <section className="combat-manager-catalog">
          <aside>
            <p className="eyebrow">Aggiungi</p>
            <div className="segmented"><button className={tab === "existing" ? "active" : ""} onClick={() => setTab("existing")}>Personaggi</button><button className={tab === "templates" ? "active" : ""} onClick={() => setTab("templates")}>Template</button><button className={tab === "units" ? "active" : ""} onClick={() => setTab("units")}>Unità rapide</button></div>
            <label>Cerca<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nome o tipo…" /></label>
            {tab === "units" && <>
              <div className="combat-unit-filters">
                <header><span>Filtri</span>{unitFiltersActive && <button type="button" className="lore-link-button" onClick={() => { setUnitCategory(""); setUnitKind(""); setUnitReadyOnly(false); }}>Reimposta</button>}</header>
                <label>Categoria<select value={unitCategory} onChange={(event) => setUnitCategory(event.target.value)}>
                  <option value="">Tutte</option>
                  {unitCategories.map((category) => <option key={category} value={category}>{category}</option>)}
                </select></label>
                <label>Tipo<select value={unitKind} onChange={(event) => setUnitKind(event.target.value)}>
                  <option value="">Tutti</option>
                  <option value="humanoid">Umanoide</option>
                  <option value="creature">Creatura</option>
                  <option value="none">Non configurato</option>
                </select></label>
                <label className="combat-unit-filter-check"><input type="checkbox" checked={unitReadyOnly} onChange={(event) => setUnitReadyOnly(event.target.checked)} />Solo pronte</label>
              </div>
              <label>Variante<input value={unitVariant} maxLength={80} onChange={(event) => setUnitVariant(event.target.value)} placeholder="auto" /></label>
              <label>Livello predefinito<LevelControl value={defaultUnitLevel} onChange={setDefaultUnitLevel} label="Livello predefinito" /></label>
              <div className="combat-level-presets">{LEVEL_PRESETS.map((level) => <button key={level} type="button" className={defaultUnitLevel === level ? "active" : ""} onClick={() => setDefaultUnitLevel(level)}>Lv {level}</button>)}</div>
              <button type="button" className="button secondary small" disabled={!Object.keys(unitLevels).length} onClick={() => setUnitLevels({})}>Reimposta livelli personalizzati</button>
              <p className="combat-unit-count">{visible.length} unità corrispondenti</p>
            </>}
            <label>Sagoma<select value={shape} onChange={(event) => setShape(event.target.value)}><option value="1">1 esagono</option><option value="2h">2 orizzontali</option><option value="2v">2 verticali</option><option value="3">3 a triangolo</option><option value="4">4 compatta</option></select></label>
            <p>{tab === "units" ? "Auto crea ogni volta una combinazione diversa. Scrivi una Variante per riprodurre le stesse Skill, i perk e l'equipaggiamento di una squadra coerente." : "Un personaggio non attivo viene aggiunto senza copiarlo. Se è già attivo, puoi creare una copia del personaggio dopo conferma."}</p>
          </aside>
          <div className="combat-manager-list">{visible.map((entry) => {
            const isTemplate = tab === "templates";
            const isUnit = tab === "units";
            const isActive = !isTemplate && !isUnit && activeIds.has(entry.id);
            const unit = isUnit && "generationKind" in entry ? entry : null;
            const unitTargetLevel = unit
              ? clampLevel(unitLevels[unit.id] ?? defaultUnitLevel)
              : 1;
            const subtitle = unit
              ? `${unit.generationKindLabel}${unit.coreLabel ? ` · Core ${unit.coreLabel}` : ""} · lv 1-20${unit.description ? ` · ${unit.description}` : ""}`
              : "description" in entry
                ? entry.description
                : `${entry.type} · livello ${entry.level} · ${entry.races.join(" / ") || "nessuna razza"}`;
            return <article key={`${tab}:${entry.id}`} className={isActive ? "is-active" : ""}>
              {"imageUrl" in entry && entry.imageUrl ? <img src={entry.imageUrl} alt="" /> : <span>{entry.name.slice(0, 2).toUpperCase()}</span>}
              <div><header><strong>{entry.name}</strong>{isActive && <em>Attivo</em>}{unit && !unit.ready && <em>Da configurare</em>}</header><small>{subtitle}</small></div>
              {unit ? <div className="combat-unit-generate">
                <LevelControl value={unitTargetLevel} onChange={(level) => setUnitLevels((current) => ({ ...current, [unit.id]: level }))} label={`Livello di ${unit.name}`} />
                <button type="button" className="button primary small" disabled={locked || !unit.ready} onClick={() => run(() => onGenerate({ unitId: unit.id, level: unitTargetLevel, variant: unitVariant.trim() || "auto", footprint: footprints[shape] }))}>Genera lv {unitTargetLevel}</button>
              </div> : <button type="button" className={isActive ? "button secondary small" : "button primary small"} disabled={locked} onClick={() => {
                if (isTemplate) run(() => onDuplicate({ templateId: entry.id, footprint: footprints[shape] }));
                else if (isActive) setDuplicate({ id: entry.id, name: entry.name });
                else run(() => onActivate(entry.id, footprints[shape]));
              }}>{isTemplate ? "Crea e aggiungi" : isActive ? "Importa copia" : "Aggiungi"}</button>}
            </article>;
          })}</div>
        </section>
      </div>
    </Modal>
    {duplicate && <Modal surface="combat-import-copy" title="Importare una copia?" onClose={() => setDuplicate(null)} footer={<><button className="button secondary" onClick={() => setDuplicate(null)}>No</button><button className="button primary" disabled={locked} onClick={() => run(async () => { await onDuplicate({ characterId: duplicate.id, footprint: footprints[shape] }); setDuplicate(null); })}>Sì, crea una copia</button></>}>
      <p><strong>{duplicate.name}</strong> è già attivo sulla mappa. Vuoi creare e aggiungere una copia indipendente del personaggio? Equipaggiamento, zaino, faretra, note ed effetti personali saranno duplicati; gli oggetti e gli effetti del catalogo resteranno record condivisi.</p>
    </Modal>}
  </>;
}

function hexSelectionArea(map: CombatMap, center: Axial, radius: number) {
  const centerAxial = offsetToAxial(center, map.orientation);
  return Array.from({ length: map.rows * map.columns }, (_, index) => ({ q: index % map.columns, r: Math.floor(index / map.columns) })).filter((cell) => {
    const axial = offsetToAxial(cell, map.orientation);
    const x = axial.q - centerAxial.q;
    const z = axial.r - centerAxial.r;
    return Math.max(Math.abs(x), Math.abs(z), Math.abs(-x - z)) <= radius;
  });
}

export function HexInspector({ workspace, selectedCells, canManage, tab, terrainBadges, onTabChange, onSelectionChange, onApply, onFog }: {
  workspace: CombatWorkspace; selectedCells: Axial[]; canManage: boolean;
  tab: "colors" | "types";
  terrainBadges: Record<number, TerrainBadge>;
  onTabChange: (tab: "colors" | "types") => void;
  onSelectionChange: (cells: Axial[]) => void;
  onApply: (payload: Record<string, unknown>) => void;
  onFog: (payload: Record<string, unknown>) => void;
}) {
  const map = workspace.map;
  const anchor = selectedCells.at(-1) || null;
  const setTab = onTabChange;
  const activeTab = canManage ? tab : "colors";
  const [color, setColor] = useState<string>(HEX_COLOR_PRESETS[0]);
  const [opacity, setOpacity] = useState(.42);
  const [radius, setRadius] = useState(0);
  const apply = (payload: Record<string, unknown>) => {
    if (!selectedCells.length) return;
    onApply({ cells: selectedCells, ...payload });
    onSelectionChange([]);
  };
  const selectRadius = () => {
    if (!map || !anchor) return;
    const combined = new Map(selectedCells.map((cell) => [cellKey(cell), cell]));
    hexSelectionArea(map, anchor, radius).forEach((cell) => combined.set(cellKey(cell), cell));
    onSelectionChange([...combined.values()]);
  };
  return <div className="combat-hex-inspector-redesign">
    <section className="combat-hex-selector" data-component-type="toolbar" data-theme="combat">
      <header><div><strong>{selectedCells.length ? `${selectedCells.length} esagoni selezionati` : "Seleziona gli esagoni"}</strong><span>{anchor ? `Ultimo: ${anchor.q},${anchor.r}` : "Clicca o trascina sulla mappa"}</span></div><button type="button" disabled={!selectedCells.length} onClick={() => onSelectionChange([])}>Deseleziona</button></header>
      <p>Un clic aggiunge o rimuove un esagono. Trascina per selezionare o deselezionare più celle con lo stesso gesto.</p>
      <div className="combat-radius-selector"><label>Raggio<button type="button" onClick={() => setRadius(Math.max(0, radius - 1))}>−</button><input type="number" min="0" max="12" value={radius} onChange={(event) => setRadius(Math.max(0, Math.min(12, Number(event.target.value))))} /><button type="button" onClick={() => setRadius(Math.min(12, radius + 1))}>+</button></label><button type="button" className="button secondary small" disabled={!anchor} onClick={selectRadius}>Aggiungi area</button><small>Raggio 0 seleziona un solo esagono.</small></div>
    </section>
    <section className="combat-hex-editor-tabs">
      {canManage && <nav role="tablist" aria-label="Personalizzazione esagoni"><button role="tab" aria-selected={activeTab === "colors"} className={activeTab === "colors" ? "active" : ""} onClick={() => setTab("colors")}>Colori</button><button role="tab" aria-selected={activeTab === "types"} className={activeTab === "types" ? "active" : ""} onClick={() => setTab("types")}>Tipologia</button></nav>}
      {activeTab === "colors" ? <div className="combat-color-tab" role="tabpanel">
        <div className="combat-color-presets" aria-label="Colori predefiniti">{HEX_COLOR_PRESETS.map((preset, index) => <button key={preset} type="button" className={color === preset ? "active" : ""} style={{ "--hex-preset": preset } as React.CSSProperties} onClick={() => setColor(preset)} aria-label={`Colore predefinito ${index + 1}`} />)}</div>
        <div className="combat-color-controls"><label>Personalizzato<input type="color" value={color} onChange={(event) => setColor(event.target.value)} /></label><label>Opacità<input type="range" min=".1" max="1" step=".05" value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} /><output>{Math.round(opacity * 100)}%</output></label></div>
        <div className="combat-hex-apply-row"><button className="button primary" disabled={!selectedCells.length} onClick={() => apply({ overlayColor: color, overlayOpacity: opacity })}>Applica colore</button><button className="button secondary" disabled={!selectedCells.length} onClick={() => apply({ clear: true })}>Rimuovi colore</button></div>
        {canManage && <><div className="combat-fog-preset"><div><strong>Nebbia di guerra</strong><span>Desatura, scurisce e sfoca gli esagoni scelti.</span></div><button className="button secondary" disabled={!selectedCells.length} onClick={() => apply({ fogEffect: true })}>Applica nebbia</button><button className="button secondary" disabled={!selectedCells.length} onClick={() => apply({ fogEffect: false })}>Rimuovi</button></div>
        <details><summary>Visibilità per i giocatori</summary><div className="button-row"><button className="button secondary" onClick={() => onFog({ enabled: !map?.fogEnabled })}>{map?.fogEnabled ? "Disattiva maschera globale" : "Attiva maschera globale"}</button><button className="button secondary" disabled={!anchor} onClick={() => onFog({ mode: "reveal", center: anchor, radius, enabled: true })}>Rivela area</button><button className="button secondary" disabled={!anchor} onClick={() => onFog({ mode: "hide", center: anchor, radius })}>Nascondi area</button></div></details></>}
      </div> : <div className="combat-type-tab" role="tabpanel">
        <p>Scegli una tipologia: il tag, il costo di movimento e l'eventuale blocco vengono applicati a tutti gli esagoni selezionati. Finché resti su questa scheda la mappa mostra la sigla di ogni esagono già tipizzato.</p>
        <div className="combat-hex-type-grid">{workspace.hexTypes.map((terrain) => <button key={terrain.id} type="button" style={{ "--terrain-color": terrain.color } as React.CSSProperties} disabled={!selectedCells.length} onClick={() => apply({ terrainTypeIds: [terrain.id], blocked: terrain.impassable })}><span style={{ background: terrain.color, color: terrainBadges[terrain.id]?.ink }}>{terrainBadges[terrain.id]?.label}</span><strong>{terrain.name}</strong><small>{terrain.impassable ? "Intransitabile" : `Costo ×${terrain.movementMultiplier}`}</small></button>)}</div>
        <button className="button secondary" disabled={!selectedCells.length} onClick={() => apply({ terrainTypeIds: [], blocked: false })}>Rimuovi tipologia</button>
      </div>}
    </section>
  </div>;
}

function DraggableHexTool({ open, selectionCount, onToggle, children }: { open: boolean; selectionCount: number; onToggle: () => void; children: React.ReactNode }) {
  const [position, setPosition] = useState(() => ({ x: typeof window === "undefined" ? 16 : Math.max(16, window.innerWidth - 406), y: 72 }));
  const drag = useRef<{ pointerX: number; pointerY: number; startX: number; startY: number } | null>(null);
  const windowRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const clamp = (x: number, y: number) => {
      const bounds = windowRef.current?.getBoundingClientRect();
      const width = bounds?.width || 390;
      const height = bounds?.height || 520;
      return {
        x: Math.max(0, Math.min(Math.max(0, window.innerWidth - width), x)),
        y: Math.max(0, Math.min(Math.max(0, window.innerHeight - Math.min(height, window.innerHeight)), y)),
      };
    };
    const move = (event: PointerEvent) => {
      if (!drag.current) return;
      const nextX = drag.current.startX + event.clientX - drag.current.pointerX;
      const nextY = drag.current.startY + event.clientY - drag.current.pointerY;
      setPosition(clamp(nextX, nextY));
    };
    const stop = () => { drag.current = null; };
    const resize = () => setPosition((current) => clamp(current.x, current.y));
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
      window.removeEventListener("resize", resize);
    };
  }, []);
  if (!open) return <button type="button" className="combat-hex-tool-launcher" onClick={onToggle}><span>⬡</span><strong>Esagono</strong><small>Apri strumenti</small></button>;
  return createPortal(<section ref={windowRef} className="combat-hex-tool-window" data-component-type="drawer" data-theme="combat" style={{ left: position.x, top: position.y }}>
    <header className="combat-hex-tool-titlebar" onPointerDown={(event) => { if (event.button !== 0) return; drag.current = { pointerX: event.clientX, pointerY: event.clientY, startX: position.x, startY: position.y }; event.currentTarget.setPointerCapture(event.pointerId); }}>
      <span>⠿</span><div><strong>Esagoni</strong><small>{selectionCount ? `${selectionCount} selezionati` : "Trascina questa finestra"}</small></div><button type="button" aria-label="Chiudi strumenti esagono" onPointerDown={(event) => event.stopPropagation()} onClick={onToggle}>×</button>
    </header>
    <div className="combat-hex-tool-body">{children}</div>
  </section>, document.body);
}

function MapVersionsModal({ map, busy, onClose, onCreate, onRestore, onDuplicate }: {
  map: CombatMap; busy: boolean; onClose: () => void;
  onCreate: (label: string) => void; onRestore: (snapshotId: number) => void; onDuplicate: (name: string) => void;
}) {
  const [label, setLabel] = useState("");
  const [duplicateName, setDuplicateName] = useState(`${map.name} (copia)`);
  const [restoreSnapshot, setRestoreSnapshot] = useState<CombatMap["snapshots"][number] | null>(null);
  const confirmRestore = () => {
    if (!restoreSnapshot) return;
    const snapshotId = restoreSnapshot.id;
    setRestoreSnapshot(null);
    onRestore(snapshotId);
  };
  return <>
    <Modal surface="combat-map-backups" title="Backup e copie della mappa" onClose={onClose} wide footer={<button className="button secondary" onClick={onClose}>Chiudi</button>}>
      <div className="combat-version-layout" data-component-type="panel" data-theme="combat">
        <section><h3>Crea backup</h3><p>Salva griglia, nebbia, personaggi, sagome e modificatori.</p><label>Etichetta<input value={label} onChange={(event) => setLabel(event.target.value)} placeholder={`Revisione ${map.revision}`} /></label><button className="button primary" disabled={busy} onClick={() => { onCreate(label || `Revisione ${map.revision}`); setLabel(""); }}>Crea backup</button></section>
        <section><h3>Duplica mappa</h3><p>La copia è indipendente e parte dalla revisione 1.</p><label>Nome<input value={duplicateName} onChange={(event) => setDuplicateName(event.target.value)} /></label><button className="button primary" disabled={busy || !duplicateName.trim()} onClick={() => onDuplicate(duplicateName.trim())}>Duplica</button></section>
        <section className="combat-snapshot-list"><h3>Versioni disponibili</h3>{map.snapshots.length ? map.snapshots.map((snapshot) => <article key={snapshot.id}><div><strong>{snapshot.label}</strong><small>rev. {snapshot.revision} · {new Date(snapshot.createdAt).toLocaleString("it")} · {snapshot.createdBy}</small></div><button className="button secondary small" disabled={busy} onClick={() => setRestoreSnapshot(snapshot)}>Ripristina</button></article>) : <p>Nessun backup disponibile.</p>}</section>
      </div>
    </Modal>
    {restoreSnapshot && <ConfirmationModal
      title="Ripristinare il backup?"
      message={<p><strong>{restoreSnapshot.label}</strong> sostituirà lo stato corrente della mappa. Prima del ripristino verrà creato automaticamente un backup dello stato attuale.</p>}
      confirmLabel="Ripristina backup"
      busy={busy}
      destructive
      onCancel={() => setRestoreSnapshot(null)}
      onConfirm={confirmRestore}
    />}
  </>;
}

function CharacterContextModal({ participant, busy, canManage, onClose, onSelect, onDetails, onTakeControl }: {
  participant: MapParticipant; busy: boolean; canManage: boolean;
  onClose: () => void; onSelect: () => void; onDetails: () => void; onTakeControl: () => void;
}) {
  const character = participant.character;
  const weapon = activeCombatWeapon(character);
  const health = characterHealth(character);
  const band = healthBand(health?.maximum ? Math.max(0, Math.min(100, health.current / health.maximum * 100)) : 0);
  // Il giocatore non comanda gli altri: legge solo cosa impugnano e cosa indossano.
  // Il resto dell'equipaggiamento si scopre quando il personaggio è a 0 PF o meno.
  if (!canManage) {
    const revealAll = (health?.current ?? 0) <= 0;
    const slots = character.equipment.slots.filter((slot) => !slot.isLocked || PUBLIC_EQUIPMENT_SLOTS.includes(slot.slot));
    return <Modal surface="combat-character-public" title={character.name} onClose={onClose} footer={<button className="button secondary" onClick={onClose}>Chiudi</button>}>
      <div className="combat-context-character" data-component-type="card" data-theme="combat">{character.portrait && <img src={character.portrait} alt="" />}<div><p>Livello {character.level} · {character.type || "Personaggio"}</p><strong>{band.label}</strong><span>{revealAll ? "Equipaggiamento completo visibile." : "Solo l'equipaggiamento in vista."}</span></div></div>
      <dl className="combat-context-equipment">{slots.map((slot) => {
        const value = publicEquipmentValue(slot, revealAll);
        return <Fragment key={slot.id}>
          <dt>{slot.label}</dt>
          <dd className={value === "Vedi a 0 PF" ? "hidden-slot" : value === "VUOTO" ? "empty-slot" : ""}>{value}</dd>
        </Fragment>;
      })}</dl>
    </Modal>;
  }
  return <Modal surface="combat-character-manage" title={character.name} onClose={onClose} footer={<><button className="button secondary" onClick={onClose}>Chiudi</button><button className="button secondary" onClick={onDetails}>Vedi dettagli</button><button className="button secondary" disabled={busy} onClick={onSelect}>Metti in primo piano</button><button className="button primary" disabled={busy} onClick={onTakeControl}>Prendi il controllo</button></>}>
    <div className="combat-context-character" data-component-type="card" data-theme="combat">{character.portrait && <img src={character.portrait} alt="" />}<div><p>Livello {character.level} · {character.type || "Personaggio"}</p><strong>{weapon?.name || "Mani nude"}</strong><span>{character.effects.length} effetti · {character.quiver.occupied}/{character.quiver.capacity} faretra · sagoma {participant.footprint.length} esa.</span></div></div>
  </Modal>;
}

function MapManagerModal({ workspace, busy, onClose, onSelect, onEdit, onVersions, onCharacters }: {
  workspace: CombatWorkspace; busy: boolean; onClose: () => void; onSelect: (id: number) => void;
  onEdit: () => void; onVersions: () => void; onCharacters: () => void;
}) {
  const current = workspace.map;
  return <Modal surface="combat-map-manager" title="Gestione mappe" onClose={onClose} wide className="combat-map-manager-modal" footer={<button className="button secondary" onClick={onClose}>Chiudi</button>}>
    <div className="combat-map-manager" data-component-type="panel" data-theme="combat">
      <header><div><p className="eyebrow">Tavoli disponibili</p><h3>Scegli, prepara, gioca</h3><p>Le operazioni sulla mappa sono raccolte qui; durante il combattimento resta visibile solo ciò che serve.</p></div>{workspace.permissions.canManageMaps && <button className="button primary" onClick={onEdit}>{current ? "Modifica mappa attiva" : "Crea mappa"}</button>}</header>
      <div className="combat-map-card-grid">{workspace.maps.map((entry) => <article key={entry.id} className={entry.id === current?.id ? "active" : ""}>
        <div className="combat-map-card-preview">{entry.imageUrl ? <img src={entry.imageUrl} alt="" /> : <span>Mappa</span>}{workspace.permissions.canManageMaps && <em>{entry.isDefault ? "Predefinita" : `rev. ${entry.revision}`}</em>}</div>
        <div><strong>{entry.name}</strong><small>{entry.mapType} · aggiornata {new Date(entry.updatedAt).toLocaleDateString("it")}</small></div>
        <button className={entry.id === current?.id ? "button secondary small" : "button primary small"} disabled={busy || entry.id === current?.id} onClick={() => onSelect(entry.id)}>{entry.id === current?.id ? "In uso" : "Apri"}</button>
      </article>)}</div>
      {current && <footer><div><strong>{current.name}</strong><span>{current.rows} × {current.columns} esagoni{workspace.permissions.canManageMaps ? ` · revisione ${current.revision}` : ""} · {current.participants.length} personaggi</span></div><div>{workspace.permissions.canImportCharacters && <button className="button secondary" onClick={onCharacters}>Personaggi</button>}{workspace.permissions.canManageMaps && <button className="button secondary" onClick={onVersions}>Backup e copie</button>}{workspace.permissions.canManageMaps && <button className="button primary" onClick={onEdit}>Calibra e modifica</button>}</div></footer>}
    </div>
  </Modal>;
}

type QuickActionConfirmation =
  | { kind: "duplicate"; name: string; payload: Record<string, unknown> }
  | { kind: "clear"; count: number; actionIds: number[] };

function QuickActionsPanel({ map, paths, busy, notify, onCreate, onCommit, onDelete, onClearQueue, onSaveActionSettings }: {
  map: CombatMap; paths: PathResult | null; busy: boolean;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
  onCreate: (payload: Record<string, unknown>) => void; onCommit: (id: number) => void; onDelete: (id: number) => void;
  onClearQueue: (actionIds: number[]) => void;
  onSaveActionSettings: (characterId: number, settings: { tags?: Record<string, string[]>; tagFilters?: string[] }) => void;
}) {
  const characterId = map.activeCharacterId || map.participants[0]?.character.id || 0;
  const character = map.participants.find((entry) => entry.character.id === characterId)?.character;
  const options = useMemo(() => characterActiveOptions(character), [character]);
  const economy = character?.spellEconomy || EMPTY_SPELL_ECONOMY;
  const storedTags = character?.actionSettings?.tags || {};
  const savedFilters = character?.actionSettings?.tagFilters;
  const [costs, setCosts] = useState<Record<string, number>>(EMPTY_COSTS);
  const [actionType, setActionType] = useState("movement");
  const [name, setName] = useState("Movimento");
  const [description, setDescription] = useState("Movimento tattico");
  const [sourceSkillId, setSourceSkillId] = useState<number | undefined>();
  const [selectedKey, setSelectedKey] = useState("movement");
  const [spellIntensity, setSpellIntensity] = useState(0);
  const [powerUsed, setPowerUsed] = useState(0);
  const [freePower, setFreePower] = useState(0);
  const [tagsExpanded, setTagsExpanded] = useState(false);
  const [confirmation, setConfirmation] = useState<QuickActionConfirmation | null>(null);
  const selectedOption = options.find((entry) => entry.key === selectedKey);
  const activeFilters = savedFilters ?? DEFAULT_ACTION_TAG_FILTERS;
  // `costs` tiene i costi fissi dell'azione. Per un incantesimo il Mana fisso della
  // definizione è già dentro la formula, quindi costs.mana è solo l'eventuale Mana
  // fisso aggiuntivo dichiarato a mano, che partecipa comunque alla conversione.
  const mana = spellManaBreakdown(spellIntensity, selectedOption?.spell, costs.mana);
  const requiredMana = mana.requiredMana;
  const resolvedCosts = actionType === "cast"
    ? spellCastCosts(costs, requiredMana, powerUsed, freePower, economy)
    : costs;
  const updateEffect = (next: number) => setSpellIntensity(Math.max(0, Math.min(500, Math.round(next || 0))));
  const chooseOption = (key: string) => {
    setSelectedKey(key);
    if (key === "movement") { setActionType("movement"); setName("Movimento"); setDescription(paths ? "Percorso selezionato sulla mappa" : "Movimento tattico"); setCosts({ ...EMPTY_COSTS, pa: paths?.fastest.actionPoints || 0 }); setSourceSkillId(undefined); setSpellIntensity(0); setPowerUsed(0); setFreePower(0); return; }
    const option = options.find((entry) => entry.key === key);
    if (!option) return;
    const initialEffect = initialEffectForOption(option);
    setActionType(option.kind); setName(option.name); setDescription(option.description);
    setCosts(fixedCostsForOption(option));
    setSourceSkillId(option.sourceSkillId); setSpellIntensity(initialEffect); setPowerUsed(0); setFreePower(0);
  };
  const toggleFilter = (tag: string) => {
    const next = activeFilters.includes(tag) ? activeFilters.filter((entry) => entry !== tag) : [...activeFilters, tag];
    onSaveActionSettings(characterId, { tagFilters: ACTION_TAGS.filter((entry) => next.includes(entry)) });
  };
  const toggleOptionTag = (key: string, tag: string) => {
    const next = toggledActionTags(actionTagsFor(storedTags, key), tag);
    const tags = { ...storedTags };
    if (next.length) tags[key] = next; else delete tags[key];
    onSaveActionSettings(characterId, { tags });
    // Un'etichetta fuori dai filtri attivi fa sparire l'azione dall'elenco: va detto subito.
    const resulting = next.length ? next : [UNTAGGED_ACTION_TAG];
    if (!actionMatchesTagFilters(resulting, activeFilters)) {
      const label = options.find((entry) => entry.key === key)?.name || "L'azione";
      notify(`${label} esce dall'elenco: attiva il filtro “${resulting.join("” o “")}” per rivederla.`, "info");
    }
  };
  const actions = map.plannedActions.filter((entry) => entry.characterId === characterId);
  const pendingActions = actions.filter((entry) => !entry.committedAt);
  const plannedActionPayload = () => {
    const effectNote = selectedKey === "movement" ? "" : `Effetto ${spellIntensity}${selectedOption?.spell?.effectUnit ? ` ${selectedOption.spell.effectUnit}` : ""} · Mana richiesto ${requiredMana}`;
    const powerNote = actionType === "cast" ? `Potere usato ${powerUsed} · Potere gratis ${freePower}` : "";
    return { characterId, actionType, name, description: [description, effectNote, powerNote].filter(Boolean).join(" · "), costs: resolvedCosts, sourceSkillId, path: actionType === "movement" ? paths?.fastest.path || [] : [] };
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload = plannedActionPayload();
    const alreadyQueued = pendingActions.some((entry) => entry.actionType === actionType
      && entry.name.trim().toLocaleLowerCase("it") === name.trim().toLocaleLowerCase("it"));
    if (alreadyQueued) {
      setConfirmation({ kind: "duplicate", name, payload });
      return;
    }
    onCreate(payload);
  };
  const clearQueue = () => {
    if (!pendingActions.length) return;
    setConfirmation({ kind: "clear", count: pendingActions.length, actionIds: pendingActions.map((entry) => entry.id) });
  };
  const confirmPendingAction = () => {
    if (!confirmation) return;
    if (confirmation.kind === "duplicate") onCreate(confirmation.payload);
    else onClearQueue(confirmation.actionIds);
    setConfirmation(null);
  };
  const projectedResources = character?.resources.filter((resource) => resource.key in resolvedCosts).map((resource) => ({ ...resource, after: Math.max(0, resource.current - (resolvedCosts[resource.key] || 0)) })) || [];
  const movementOption = { key: "movement", name: "Movimento", description: paths?.fastest.actionPoints != null ? `${paths.fastest.distance ?? 0} esagoni · ${paths.fastest.actionPoints} PA suggeriti` : "Scegli liberamente i PA usati.", kind: "movement" as const };
  // Il Movimento non è un'azione etichettabile: resta sempre in cima all'elenco.
  const visibleOptions = options.filter((option) => actionMatchesTagFilters(actionTagsFor(storedTags, option.key), activeFilters));
  const availableOptions = [movementOption, ...visibleOptions];
  return <>
    <div className="combat-quick-actions">
    <aside className="combat-quick-catalog">
      <header
        className="combat-quick-catalog-heading"
        role="button"
        tabIndex={0}
        aria-expanded={tagsExpanded}
        title={tagsExpanded ? "Chiudi i filtri per etichetta" : "Apri i filtri per etichetta"}
        onClick={() => setTagsExpanded((current) => !current)}
        onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setTagsExpanded((current) => !current); } }}
      >
        <strong className="combat-quick-catalog-title">Azioni disponibili{tagsExpanded ? " (Chiudi)" : ""}</strong>
        <span>{character?.name || "Nessun personaggio"}</span>
      </header>
      {/* Chiuse, le etichette sono solo un'anteprima cliccabile che apre i filtri; aperte, filtrano davvero. */}
      <div
        className={`combat-quick-tag-filters ${tagsExpanded ? "expanded" : ""}`}
        role="group"
        aria-label={tagsExpanded ? "Filtri per etichetta" : "Etichette: apri i filtri"}
        onClick={tagsExpanded ? undefined : () => setTagsExpanded(true)}
      >
        {ACTION_TAGS.map((tag) => {
          const on = activeFilters.includes(tag);
          return <button
            key={tag}
            type="button"
            className={on ? "on" : "off"}
            disabled={busy || !characterId}
            aria-pressed={tagsExpanded ? on : undefined}
            title={tagsExpanded ? `Filtra per “${tag}”` : "Apri i filtri per etichetta"}
            onClick={() => tagsExpanded ? toggleFilter(tag) : setTagsExpanded(true)}
          >{tag}</button>;
        })}
      </div>
      <div className="combat-quick-option-list">{availableOptions.map((option) => <Fragment key={option.key}>
        <button type="button" className={`${selectedKey === option.key ? "active" : ""} ${option.kind}`} onClick={() => chooseOption(option.key)}><span className={`action-glyph ${option.kind}`}>{option.kind === "cast" ? "✦" : option.key === "movement" ? "↝" : "◆"}</span><span><strong>{option.name}</strong><small>{option.description || "Promemoria attivo"}</small></span></button>
        {tagsExpanded && option.key !== "movement" && <div className="combat-quick-action-tags" role="group" aria-label={`Etichette di ${option.name}`}>
          {((assigned) => STORABLE_ACTION_TAGS.map((tag) => <button key={tag} type="button" className={assigned.includes(tag) ? "on" : "off"} aria-pressed={assigned.includes(tag)} disabled={busy || !characterId} onClick={() => toggleOptionTag(option.key, tag)}>{tag}</button>))(actionTagsFor(storedTags, option.key))}
        </div>}
      </Fragment>)}
      {!visibleOptions.length && <p className="combat-quick-empty">{options.length ? "Nessuna azione corrisponde ai filtri attivi." : "Nessuna azione sbloccata."}</p>}</div>
    </aside>
    <main className="combat-quick-compose">
      <section className="combat-quick-resource-preview"><header><strong>Risorse dopo l'azione</strong><small>Anteprima: nulla viene sottratto ora.</small></header><div>{projectedResources.map((resource) => { const percent = resource.maximum ? resource.after / resource.maximum * 100 : 0; return <article key={resource.key} data-resource={resource.key} className={resource.after < resource.current ? "spending" : ""}><span><b>{resource.label}</b><em>{resource.current} → {resource.after}</em></span><i><b style={{ width: `${percent}%`, background: `var(${resource.colorToken}, var(--gold))` }} /></i></article>; })}</div></section>
      <form className="combat-quick-form" onSubmit={submit}>
        <header><div><p className="eyebrow">Preparazione rapida</p><h3>{selectedKey === "movement" ? "Movimento" : selectedOption?.name || name}</h3></div>{selectedKey !== "movement" && <label>Tipo<select value={actionType} onChange={(event) => setActionType(event.target.value)}><option value="attack">Attacco</option><option value="cast">Incantesimo</option><option value="power">Potere</option><option value="other">Altro</option></select></label>}</header>
        {selectedKey === "movement" ? <section className="combat-movement-cost"><label>PA utilizzati<input type="range" min="0" max={Math.max(20, character?.resources.find((resource) => resource.key === "pa")?.current || 0)} value={costs.pa || 0} onChange={(event) => setCosts({ ...EMPTY_COSTS, pa: Number(event.target.value) })} /><input type="number" min="0" value={costs.pa || 0} onChange={(event) => setCosts({ ...EMPTY_COSTS, pa: Math.max(0, Number(event.target.value)) })} /></label>{paths?.fastest.actionPoints != null && <button type="button" onClick={() => setCosts({ ...EMPTY_COSTS, pa: paths.fastest.actionPoints || 0 })}>Usa il percorso calcolato: {paths.fastest.actionPoints} PA</button>}<p>Scegli soltanto i Punti Azione consumati. Il percorso viene allegato automaticamente quando lo hai calcolato sulla mappa.</p></section> : <>
          <label>Nome azione<input value={name} onChange={(event) => setName(event.target.value)} required placeholder="Nome breve e riconoscibile" /></label>
          <label>Promemoria<textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} placeholder="Bersaglio, formula, bonus o note…" /></label>
          <fieldset className="combat-spell-controls"><legend>{selectedOption?.spell ? "Controlli incantesimo" : "Controlli effetto"}</legend><div className="combat-effect-control" role="group" aria-label="Regola effetto"><span>Effetto{selectedOption?.spell?.effectUnit ? ` · ${selectedOption.spell.effectUnit}` : ""}</span><button type="button" disabled={spellIntensity <= 0} onClick={() => updateEffect(spellIntensity - 1)} aria-label="Riduci effetto">−</button><input aria-label="Effetto" type="range" min="0" max="500" value={spellIntensity} onChange={(event) => updateEffect(Number(event.target.value))} /><button type="button" disabled={spellIntensity >= 500} onClick={() => updateEffect(spellIntensity + 1)} aria-label="Aumenta effetto">+</button><output>{spellIntensity}</output></div>{actionType === "cast" && <><label>Potere usato<input type="range" min="0" max={Math.max(0, character?.resources.find((resource) => resource.key === "potere")?.current || 0)} value={powerUsed} onChange={(event) => setPowerUsed(Number(event.target.value))} /><output>{powerUsed}</output></label><label>Potere gratis<input type="number" min="0" max="50" value={freePower} onChange={(event) => setFreePower(Math.max(0, Number(event.target.value)))} /></label></>}<small>{selectedOption?.spell?.costSummary || (selectedOption?.spell ? selectedOption.spell.formula : "Conversione generica: 1 effetto = 1 Mana")}</small>
            {actionType === "cast" && <p className="combat-spell-economy">{spellCostExplanation(mana, resolvedCosts, powerUsed + freePower, economy).join(" · ")}</p>}</fieldset>
          {actionType === "cast" && <fieldset><legend>Costi fissi dell'azione</legend><div className="planner-costs">{FIXED_COST_KEYS.map((key) => <label key={key}>{key === "mana" ? "mana extra" : key}<input type="number" min="0" value={costs[key] || 0} onChange={(event) => setCosts({ ...costs, [key]: Math.max(0, Number(event.target.value)) })} /></label>)}</div><small>Si pagano a ogni lancio a prescindere dall'intensità. Il Mana fisso entra nella conversione in Energia e PA; le altre risorse si sommano al totale senza essere convertite.</small></fieldset>}
          <fieldset><legend>Costi{actionType === "cast" ? " totali" : ""}</legend><div className="planner-costs">{Object.entries(resolvedCosts).map(([key, value]) => <label key={key}>{key}<input type="number" min="0" value={value} readOnly={actionType === "cast"} onChange={(event) => setCosts({ ...costs, [key]: Math.max(0, Number(event.target.value)) })} /></label>)}</div>{actionType === "cast" && <small>Mana, Energia e PA si pagano insieme; il Potere gratuito sconta senza essere speso.</small>}</fieldset>
        </>}
        <button className="button primary" disabled={busy || !characterId}>Aggiungi {selectedKey === "movement" ? "Movimento" : "alla coda"}</button>
      </form>
    </main>
    <aside className="combat-quick-side"><section className="combat-quick-notes"><header><strong>Note</strong><span>Salvataggio automatico</span></header>{characterId && <NoteSectionEditor characterId={characterId} section="combat" notify={notify} rows={6} compact minimal />}</section><section className="combat-quick-queue"><header><strong>Coda azioni</strong><span>{pendingActions.length} da pagare</span><button type="button" className="combat-quick-queue-reset" disabled={busy || !pendingActions.length} onClick={clearQueue} title="Rimuove tutte le azioni non ancora pagate">Svuota</button></header><div className="planned-action-list">{actions.map((action) => <article key={action.id} className={action.committedAt ? "committed" : ""}>
      <span className={`action-glyph ${action.actionType}`}>{({ movement: "↝", attack: "⚔", cast: "✦", power: "◆", other: "•" } as Record<string, string>)[action.actionType]}</span>
      <div><strong>{action.name}</strong><small>{Object.entries(action.costs).filter(([, value]) => value).map(([key, value]) => `${value} ${key.toUpperCase()}`).join(" · ") || "Nessun costo"}{action.path.length ? ` · ${action.path.length - 1} esagoni` : ""}</small>{action.description && <p>{action.description}</p>}</div>
      {action.committedAt ? <span className="paid">Pagata</span> : <div><button disabled={busy} onClick={() => onCommit(action.id)}>Paga</button><button disabled={busy} onClick={() => onDelete(action.id)}>×</button></div>}
    </article>)}</div>{!actions.length && <p className="combat-quick-empty">La coda è vuota. Scegli Movimento o una delle azioni sbloccate.</p>}<p className="planner-note">Solo “Paga” scala le risorse. La coda non impone un ordine di turno.</p></section></aside>
    </div>
    {confirmation && <ConfirmationModal
      title={confirmation.kind === "duplicate" ? "Aggiungere un duplicato?" : "Svuotare la coda?"}
      message={confirmation.kind === "duplicate"
        ? <p><strong>{confirmation.name}</strong> è già presente nella coda e non è ancora stata pagata. Vuoi aggiungerla una seconda volta?</p>
        : <p>{confirmation.count} azioni non pagate verranno rimosse. Le azioni già pagate resteranno nello storico.</p>}
      confirmLabel={confirmation.kind === "duplicate" ? "Aggiungi comunque" : "Rimuovi azioni"}
      busy={busy}
      destructive={confirmation.kind === "clear"}
      onCancel={() => setConfirmation(null)}
      onConfirm={confirmPendingAction}
    />}
  </>;
}

export function CombatPage() {
  const { notify } = useApp();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mapId, setMapId] = useState<number | null>(null);
  const [mapEditorMode, setMapEditorMode] = useState<"create" | "edit" | null>(null);
  const [mapManagerOpen, setMapManagerOpen] = useState(false);
  const [characterManager, setCharacterManager] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [contextParticipant, setContextParticipant] = useState<MapParticipant | null>(null);
  const [masterForegroundByMap, setMasterForegroundByMap] = useState<Record<number, number>>({});
  const autoPresenceAttempt = useRef(new Set<string>());
  const [selectedHex, setSelectedHex] = useState<Axial | null>(null);
  const [selectedHexes, setSelectedHexes] = useState<Axial[]>([]);
  const [pathStart, setPathStart] = useState<Axial | null>(null);
  const [pathMode, setPathMode] = useState(false);
  const [paths, setPaths] = useState<PathResult | null>(null);
  const [attackResult, setAttackResult] = useState<AttackResult | null>(null);
  const [attackSelection, setAttackSelection] = useState<AttackSelection | null>(null);
  const [draggedCharacterId, setDraggedCharacterId] = useState<number | null>(null);
  const [hexOpen, setHexOpen] = useState(false);
  const [hexTab, setHexTab] = useState<"colors" | "types">("colors");
  const [plannerOpen, setPlannerOpen] = useState(false);
  const [attackOpen, setAttackOpen] = useState(false);
  const [localActionPoints, setLocalActionPoints] = useState<Record<number, number>>({});
  const query = useQuery({ queryKey: ["combat", mapId], queryFn: () => getData<CombatWorkspace>(`/api/combat/${mapId ? `?map_id=${mapId}` : ""}`) });
  const workspace = query.data;
  const terrainBadges = useMemo(() => buildTerrainBadges(workspace?.hexTypes || []), [workspace?.hexTypes]);
  const rawMap = workspace?.map;
  const focusedCharacterId = combatFocusedCharacterId(
    rawMap,
    workspace?.viewerCharacterId,
    Boolean(workspace?.permissions.canControlCharacters),
    rawMap ? masterForegroundByMap[rawMap.id] : null,
  );
  const map = useMemo(() => rawMap ? {
    ...rawMap,
    activeCharacterId: focusedCharacterId,
    participants: rawMap.participants.map((participant) => ({
      ...participant,
      character: {
        ...participant.character,
        resources: participant.character.resources.map((resource) => {
          if (resource.key !== "pa") return resource;
          const current = Math.max(0, Math.min(resource.maximum, localActionPoints[participant.character.id] ?? resource.maximum));
          return { ...resource, current, spent: resource.maximum - current, percent: resource.maximum ? current / resource.maximum * 100 : 0 };
        }),
      },
    })),
  } : rawMap, [focusedCharacterId, localActionPoints, rawMap]);
  useEffect(() => { if (!mapId && map?.id) setMapId(map.id); }, [map?.id, mapId]);
  useEffect(() => {
    // Scorciatoia fissa della pagina Combattimento: Ctrl + Alt apre e chiude le Azioni rapide.
    // Si attiva al rilascio e solo se nessun altro tasto è stato premuto nel frattempo,
    // così AltGr (che su Windows equivale a Ctrl + Alt) non apre la finestra mentre si scrive.
    let armed = false;
    const isModifier = (key: string) => key === "Control" || key === "Alt";
    const onKeyDown = (event: KeyboardEvent) => {
      if (!isModifier(event.key)) { armed = false; return; }
      if (event.ctrlKey && event.altKey && !event.shiftKey && !event.metaKey) armed = true;
    };
    const onKeyUp = (event: KeyboardEvent) => {
      if (!isModifier(event.key) || !armed) return;
      armed = false;
      setPlannerOpen((current) => !current);
      setHexOpen(false);
      setAttackOpen(false);
    };
    const disarm = () => { armed = false; };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", disarm);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", disarm);
    };
  }, []);
  useEffect(() => {
    if (!map) return;
    const after = map.events[0]?.id || 0;
    const stream = new EventSource(`/api/combat/maps/${map.id}/events/?after=${after}`);
    let refreshTimer: number | null = null;
    let refreshRunning = false;
    let newestRemoteEventId = after;
    let lastAttemptedEventId = after;

    const refreshRemoteEvents = async () => {
      refreshTimer = null;
      if (refreshRunning) return;
      refreshRunning = true;
      try {
        // A server read can include every event received during that read. At
        // most one follow-up is needed if a newer event landed just after it.
        for (let attempt = 0; attempt < 2; attempt += 1) {
          const cached = queryClient.getQueryData<CombatWorkspace>(["combat", map.id]);
          if (!combatEventNeedsRefresh(newestRemoteEventId, cached?.map?.events || [])) break;
          lastAttemptedEventId = newestRemoteEventId;
          await queryClient.invalidateQueries(
            { queryKey: ["combat", map.id] },
            { cancelRefetch: false },
          );
        }
      } finally {
        refreshRunning = false;
        const cached = queryClient.getQueryData<CombatWorkspace>(["combat", map.id]);
        if (
          newestRemoteEventId > lastAttemptedEventId
          && combatEventNeedsRefresh(newestRemoteEventId, cached?.map?.events || [])
          && refreshTimer === null
        ) {
          refreshTimer = window.setTimeout(() => { void refreshRemoteEvents(); }, 100);
        }
      }
    };
    stream.addEventListener("combat", (event) => {
      const eventId = Number((event as MessageEvent).lastEventId || 0);
      newestRemoteEventId = Math.max(newestRemoteEventId, eventId);
      const cached = queryClient.getQueryData<CombatWorkspace>(["combat", map.id]);
      if (!combatEventNeedsRefresh(eventId, cached?.map?.events || [])) return;
      if (refreshTimer === null && !refreshRunning) {
        refreshTimer = window.setTimeout(() => { void refreshRemoteEvents(); }, 100);
      }
    });
    return () => {
      stream.close();
      if (refreshTimer !== null) window.clearTimeout(refreshTimer);
    };
  }, [map?.id, queryClient]);
  const mutation = useMutation({
    mutationFn: ({ action, payload }: { action: string; payload: Record<string, unknown> }) => combatAction(action, payload),
    onSuccess: (response) => {
      if (response.data.map?.id) {
        setMapId(response.data.map.id);
        queryClient.setQueryData(["combat", response.data.map.id], response.data);
      }
      if (response.data.paths) setPaths(response.data.paths);
      if (response.data.attackResult) setAttackResult(response.data.attackResult);
      response.events.forEach((event) => notify(event.message));
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  /* All'ingresso si garantisce soltanto la presenza del personaggio di chi guarda.
     Il focus dell'inspector è personale e non deve mai diventare un aggiornamento
     condiviso capace di cambiare il pannello degli altri utenti. */
  useEffect(() => {
    if (!map || !workspace?.viewerCharacterId) return;
    const key = `${map.id}:${workspace.viewerCharacterId}`;
    const alreadyPresent = map.activeCharacterIds.includes(workspace.viewerCharacterId);
    if (alreadyPresent || autoPresenceAttempt.current.has(key)) return;
    autoPresenceAttempt.current.add(key);
    combatAction("combat.ensureViewerCharacter", { mapId: map.id }).then((response) => {
      if (response.data.map?.id) queryClient.setQueryData(["combat", response.data.map.id], response.data);
      response.events.forEach((event) => notify(event.message));
    }).catch((error: Error) => notify(error.message, "error"));
  }, [map, notify, queryClient, workspace?.viewerCharacterId]);
  const act = (action: string, payload: Record<string, unknown>) => mutation.mutate({ action, payload: { mapId: map?.id, ...payload } });
  const setLocalActionPointValue = (characterId: number, requested: number) => {
    const maximum = rawMap?.participants.find((entry) => entry.character.id === characterId)?.character.resources.find((resource) => resource.key === "pa")?.maximum || 0;
    setLocalActionPoints((current) => ({ ...current, [characterId]: Math.max(0, Math.min(maximum, Math.round(requested || 0))) }));
  };
  const spendLocalActionPoints = (characterId: number, amount: number) => {
    const resource = map?.participants.find((entry) => entry.character.id === characterId)?.character.resources.find((entry) => entry.key === "pa");
    if (!resource || amount <= 0) return;
    setLocalActionPointValue(characterId, resource.current - amount);
  };
  const commitPlannedAction = async (actionId: number) => {
    const action = map?.plannedActions.find((entry) => entry.id === actionId);
    const resource = map?.participants.find((entry) => entry.character.id === action?.characterId)?.character.resources.find((entry) => entry.key === "pa");
    const actionPointCost = Math.max(0, Number(action?.costs.pa || 0));
    if (resource && resource.current < actionPointCost) { notify("Punti Azione locali insufficienti per questa azione.", "error"); return; }
    try {
      await mutation.mutateAsync({ action: "combat.commitPlannedAction", payload: { mapId: map?.id, actionId } });
      if (action) spendLocalActionPoints(action.characterId, actionPointCost);
    } catch { /* onError already reports the API failure. */ }
  };
  // Le cancellazioni vanno in sequenza: ogni risposta riporta l'intera mappa e
  // richieste parallele finirebbero per riscrivere la cache con uno stato già superato.
  const clearPlannedActions = async (actionIds: number[]) => {
    for (const actionId of actionIds) {
      try { await mutation.mutateAsync({ action: "combat.deletePlannedAction", payload: { mapId: map?.id, actionId } }); }
      catch { return; }
    }
  };
  const resolveAttackAndSpendLocalActionPoints = async (payload: Record<string, unknown>) => {
    try {
      const response = await mutation.mutateAsync({ action: "combat.resolveAttack", payload: { mapId: map?.id, ...payload } });
      const result = response.data.attackResult;
      if (result?.applied) spendLocalActionPoints(result.attackerId, Number(result.resourceCosts?.pa || 0));
      return result;
    } catch { return undefined; }
  };
  const rollCombatD20 = async (characterId: number) => {
    try {
      const response = await command<{ diceRoll: { total: number } }>("dice.roll", {
        sides: 20,
        count: 1,
        modifier: 0,
        characterId,
      }, "combat");
      return response.data.diceRoll.total;
    } catch (error) {
      notify(error instanceof Error ? error.message : "Tiro d20 non riuscito.", "error");
      return undefined;
    }
  };
  const handleHex = (cell: Axial) => {
    if (!pathMode) { setSelectedHex(cell); return; }
    if (!pathStart) { setPathStart(cell); notify("Ora scegli la destinazione del percorso.", "info"); return; }
    act("maps.calculatePaths", { start: pathStart, end: cell, participantId: map?.participants.find((entry) => entry.character.id === map.activeCharacterId)?.id });
    setSelectedHex(cell); setPathMode(false);
  };
  const handleHexSelection = (cells: Axial[]) => {
    setSelectedHexes(cells);
    setSelectedHex(cells.at(-1) || null);
  };
  const selectAttackPair = (attackerId: number, defenderId: number) => {
    if (attackerId === defenderId) return;
    setAttackSelection((current) => ({ attackerId, defenderId, sequence: (current?.sequence || 0) + 1 }));
    setAttackOpen(true);
    setHexOpen(false);
    setPlannerOpen(false);
    const attacker = map?.participants.find((entry) => entry.character.id === attackerId)?.character.name || "Attaccante";
    const defender = map?.participants.find((entry) => entry.character.id === defenderId)?.character.name || "Difensore";
    notify(`${attacker} → ${defender}: attacco pronto.`, "info");
  };
  if (query.isLoading) return <div className="page combat-page"><div className="panel">Preparo il tavolo di combattimento…</div></div>;
  if (!workspace) return <div className="page combat-page"><div className="panel">Impossibile caricare il combattimento.</div></div>;
  // La modale legge i PF correnti: va riagganciata al partecipante aggiornato dal server.
  const openParticipant = contextParticipant
    ? map?.participants.find((entry) => entry.id === contextParticipant.id) || contextParticipant
    : null;
  const mapToolbar = <div className="combat-map-toolbar">
    <button className="button secondary combat-map-manager-trigger" onClick={() => setMapManagerOpen(true)}><span>▧</span><span><small>Mappa attiva</small><strong>{map?.name || "Nessuna mappa"}</strong></span><b>Gestisci</b></button>
    {workspace.permissions.canManageMaps && <button className="button primary combat-new-map-trigger" onClick={() => setMapEditorMode("create")}>Nuova Mappa</button>}
    {map && workspace.permissions.canImportCharacters && <button className="button secondary" onClick={() => setCharacterManager(true)}>Personaggi</button>}
    {map && <button className={pathMode ? "button primary" : "button secondary"} onClick={() => { const origin = map.participants.find((entry) => entry.character.id === map.activeCharacterId)?.anchor || map.participants[0]?.anchor || null; setPathMode(true); setPathStart(origin); setPaths(null); setSelectedHex(origin); notify(origin ? "Scegli sulla mappa la destinazione del percorso." : "Seleziona prima un personaggio attivo.", "info"); }}>{pathMode ? "Scegli destinazione…" : "Percorso"}</button>}
    {map && <button className={plannerOpen ? "button primary" : "button secondary"} onClick={() => { setPlannerOpen(true); setHexOpen(false); setAttackOpen(false); }}>Azioni rapide <span className="combat-toolbar-count">{map.plannedActions.filter((action) => !action.committedAt).length}</span></button>}
    {map && <button className={attackOpen ? "button primary combat-attack-trigger" : "button secondary combat-attack-trigger"} onClick={() => { setAttackOpen((current) => !current); setHexOpen(false); }}>⚔ Attacco</button>}
  </div>;
  return <div className="page combat-page">
    {!map ? <section className="hero-panel"><div><p className="eyebrow">Nessuna mappa</p><h2>Crea il primo tavolo tattico</h2><p>L'editor salva immagine, orientamento, griglia e trasformazioni in un vero oggetto amministrabile.</p></div>{workspace.permissions.canManageMaps && <button className="button primary" onClick={() => setMapEditorMode("create")}>Apri il creator</button>}</section> : <>
      <ActiveCombatantStrip map={map} busy={mutation.isPending} canManage={workspace.permissions.canControlCharacters} draggedCharacterId={draggedCharacterId} onDragChange={setDraggedCharacterId} onRemove={(participantId) => act("combat.deactivateParticipant", { participantId })} onContext={setContextParticipant} onPairSelect={selectAttackPair} toolbar={mapToolbar} />
      <div className="combat-stage-layout">
        <SelectedCharacterSidebar map={map} busy={mutation.isPending} canManage={workspace.permissions.canControlCharacters} controlledCharacterId={workspace.viewerCharacterId} draggedCharacterId={draggedCharacterId} onDragChange={setDraggedCharacterId} onContext={workspace.permissions.canControlCharacters ? setContextParticipant : undefined} onPairSelect={selectAttackPair} onUpdateResource={(characterId, resource, current) => resource === "pa" ? setLocalActionPointValue(characterId, current) : act("combat.updateResource", { characterId, resource, current })} onSwitchPrimary={(characterId) => act("equipment.switchPrimaryWeapon", { characterId })} onRemoveQuiverItem={(characterId, slot) => act("combat.removeQuiverItem", { characterId, slot })} />
        <section className="combat-map-panel">
          <div className="combat-map-status"><span>{map.name}{workspace.permissions.canManageMaps ? ` · revisione ${map.revision}` : ""}</span>{pathMode && <strong>{pathStart ? "Scegli la destinazione" : "Scegli la partenza"}</strong>}{paths && <div><b>Rapido</b> {paths.fastest.distance ?? "—"} esa. · {paths.fastest.actionPoints ?? "—"} PA <i /> <b>Diretto</b> {paths.direct.distance} esa.</div>}</div>
          <div className="combat-map-surface">
            <DraggableHexTool open={hexOpen} selectionCount={selectedHexes.length} onToggle={() => setHexOpen((current) => { const next = !current; if (next) { setPlannerOpen(false); setAttackOpen(false); if (selectedHex && !selectedHexes.length) setSelectedHexes([selectedHex]); } return next; })}>
              <HexInspector workspace={workspace} selectedCells={selectedHexes} canManage={workspace.permissions.canManageMaps} tab={hexTab} terrainBadges={terrainBadges} onTabChange={setHexTab} onSelectionChange={handleHexSelection} onApply={(payload) => act("maps.paintHexes", payload)} onFog={(payload) => act("maps.updateFog", payload)} />
            </DraggableHexTool>
            <CombatMapCanvas map={map} selected={selectedHex} selectedCells={selectedHexes} selectionEnabled={hexOpen} terrainBadges={hexOpen && hexTab === "types" && workspace.permissions.canManageMaps ? terrainBadges : null} paths={paths} pathStart={pathStart} controlledCharacterId={workspace.viewerCharacterId} canControlAll={workspace.permissions.canControlCharacters} onHexClick={handleHex} onSelectionChange={handleHexSelection} onMoveParticipant={(participantId, cell) => act("combat.moveParticipant", { participantId, ...cell })} onContextParticipant={setContextParticipant} />
          </div>
        </section>
        <aside className={`combat-attack-drawer ${attackOpen ? "open" : ""}`} data-component-type="drawer" data-theme="combat">
          <button type="button" className="combat-attack-drawer-toggle" aria-expanded={attackOpen} onClick={() => setAttackOpen((current) => { const next = !current; if (next) { setHexOpen(false); setPlannerOpen(false); } return next; })}><span>⚔</span><strong>Attacco</strong><small>{attackOpen ? "›" : "‹"}</small></button>
          {attackOpen && <div className="combat-attack-drawer-body"><CompactAttackPanel map={map} selection={attackSelection} result={attackResult} busy={mutation.isPending} onResolve={resolveAttackAndSpendLocalActionPoints} onRollD20={rollCombatD20} /></div>}
        </aside>
      </div>
    </>}
    {plannerOpen && map && <Modal surface="combat-quick-actions" title={`Azioni rapide · ${map.participants.find((entry) => entry.character.id === map.activeCharacterId)?.character.name || "Combattimento"}`} onClose={() => setPlannerOpen(false)} wide resizable hideHeader dragFromBody className="combat-quick-actions-modal" footer={<><details className="combat-event-log"><summary>Registro sincronizzato ({map.events.length})</summary>{map.events.slice(0, 8).map((event) => <p key={event.id}><time>{new Date(event.createdAt).toLocaleTimeString("it", { hour: "2-digit", minute: "2-digit" })}</time>{event.message}</p>)}</details><button className="button secondary" onClick={() => setPlannerOpen(false)}>Chiudi</button></>}><QuickActionsPanel map={map} paths={paths} busy={mutation.isPending} notify={notify} onCreate={(payload) => act("combat.planAction", payload)} onCommit={commitPlannedAction} onDelete={(actionId) => act("combat.deletePlannedAction", { actionId })} onClearQueue={clearPlannedActions} onSaveActionSettings={(targetCharacterId, settings) => act("combat.updateActionSettings", { characterId: targetCharacterId, ...settings })} /></Modal>}
    {mapManagerOpen && <MapManagerModal workspace={workspace} busy={mutation.isPending} onClose={() => setMapManagerOpen(false)} onSelect={(id) => { setMapId(id); setPaths(null); setSelectedHex(null); setSelectedHexes([]); setMapManagerOpen(false); }} onEdit={() => { setMapManagerOpen(false); setMapEditorMode("edit"); }} onVersions={() => { setMapManagerOpen(false); setVersionsOpen(true); }} onCharacters={() => { setMapManagerOpen(false); setCharacterManager(true); }} />}
    {mapEditorMode && <UnifiedMapEditorModal workspace={workspace} createNew={mapEditorMode === "create"} busy={mutation.isPending} onClose={() => setMapEditorMode(null)} onSave={async (draft, file, convertToWebp) => {
      let imageId = draft.imageId;
      if (file) {
        const uploaded = await uploadCombatMapImage(file, draft.name, convertToWebp);
        imageId = uploaded.data.asset.id;
        await queryClient.invalidateQueries({ queryKey: ["media"] });
      }
      await mutation.mutateAsync({ action: "maps.save", payload: { ...draft, imageId } });
      setMapEditorMode(null);
    }} onCreateType={(values) => act("maps.createType", values)} />}
    {characterManager && map && <CharacterManagerModal workspace={workspace} busy={mutation.isPending} onClose={() => setCharacterManager(false)} onActivate={async (characterId, footprint) => {
      await mutation.mutateAsync({ action: "combat.activateCharacter", payload: { mapId: map.id, characterId, footprint } });
    }} onDuplicate={async (source) => {
      await mutation.mutateAsync({ action: "combat.importCharacter", payload: { mapId: map.id, ...source } });
    }} onGenerate={async (source) => {
      await mutation.mutateAsync({ action: "combat.generateUnit", payload: { mapId: map.id, ...source } });
    }} onRemove={async (participantId) => {
      await mutation.mutateAsync({ action: "combat.deactivateParticipant", payload: { mapId: map.id, participantId } });
    }} />}
    {versionsOpen && map && <MapVersionsModal map={map} busy={mutation.isPending} onClose={() => setVersionsOpen(false)} onCreate={(label) => act("maps.createSnapshot", { label })} onRestore={(snapshotId) => act("maps.restoreSnapshot", { snapshotId })} onDuplicate={(name) => act("maps.duplicate", { name })} />}
    {openParticipant && <CharacterContextModal participant={openParticipant} busy={mutation.isPending} canManage={workspace.permissions.canControlCharacters} onClose={() => setContextParticipant(null)} onSelect={async () => {
      if (map?.id) {
        setMasterForegroundByMap((current) => ({ ...current, [map.id]: openParticipant.character.id }));
      }
      setContextParticipant(null);
    }} onDetails={() => { navigate(`/character/${openParticipant.character.id}`); setContextParticipant(null); }} onTakeControl={async () => {
      await mutation.mutateAsync({ action: "combat.takeControl", payload: { mapId: map?.id, characterId: openParticipant.character.id } });
      if (map?.id) {
        setMasterForegroundByMap((current) => {
          const next = { ...current };
          delete next[map.id];
          return next;
        });
      }
      await queryClient.invalidateQueries({ queryKey: ["personaggi"] });
      setContextParticipant(null);
    }} />}
  </div>;
}

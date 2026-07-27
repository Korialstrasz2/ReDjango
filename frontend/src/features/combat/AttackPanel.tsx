import { useEffect, useMemo, useState } from "react";

import type { AttackResult, CombatAttackButton, CombatMap } from "./types";

const DAMAGE_TYPES = ["Contundente", "Perforante", "Taglio", "Gelo", "Fuoco", "Elettro", "Puro"] as const;

type AttackSelection = { attackerId: number; defenderId: number; sequence: number };
type ManualValues = {
  attackBonus: number;
  damageBonus: number;
  damageTierBonus: number;
  damagePercentBonus: number;
  penetrationFlat: number;
  penetrationPercent: number;
};
type ManualKey = keyof ManualValues;

const EMPTY_MANUAL_VALUES: ManualValues = {
  attackBonus: 0,
  damageBonus: 0,
  damageTierBonus: 0,
  damagePercentBonus: 0,
  penetrationFlat: 0,
  penetrationPercent: 0,
};

const MANUAL_FIELDS: Array<{ key: ManualKey; short: string; label: string }> = [
  { key: "attackBonus", short: "ATK", label: "Attacco" },
  { key: "damageBonus", short: "DMG", label: "Danno" },
  { key: "damageTierBonus", short: "TIER", label: "Tier" },
  { key: "damagePercentBonus", short: "FIN %", label: "Danno finale %" },
  { key: "penetrationFlat", short: "PERF", label: "Perforazione" },
  { key: "penetrationPercent", short: "PERF %", label: "Perforazione %" },
];

type ButtonModifierTotals = CombatAttackButton["modifiers"];

function signed(value: number) {
  return value > 0 ? "+" + value : String(value);
}

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

export function adjustedAttackDamage(baseDamage: number, percent: number) {
  return Math.max(0, Math.floor(Math.max(0, baseDamage) * Math.max(0, 100 + percent) / 100));
}

export function attackButtonModifierSummary(button: Pick<CombatAttackButton, "modifiers">) {
  const entries: Array<[keyof ButtonModifierTotals, string]> = [
    ["attackBonus", "ATK"],
    ["damageBonus", "Danno"],
    ["damageTierBonus", "Tier"],
    ["penetrationFlat", "Perforazione"],
    ["penetrationPercent", "Perforazione %"],
  ];
  const summary = entries
    .filter(([key]) => button.modifiers[key])
    .map(([key, label]) => label + " " + signed(button.modifiers[key]));
  return summary.length ? summary.join(" · ") : "Nessun bonus numerico";
}

export function selectedCombatButtonTotals(buttons: Array<Pick<CombatAttackButton, "id" | "modifiers">>, activeIds: number[]): ButtonModifierTotals {
  return buttons.reduce<ButtonModifierTotals>((totals, button) => {
    if (!activeIds.includes(button.id)) return totals;
    totals.attackBonus += button.modifiers.attackBonus;
    totals.damageBonus += button.modifiers.damageBonus;
    totals.damageTierBonus += button.modifiers.damageTierBonus;
    totals.penetrationFlat += button.modifiers.penetrationFlat;
    totals.penetrationPercent += button.modifiers.penetrationPercent;
    return totals;
  }, { attackBonus: 0, damageBonus: 0, damageTierBonus: 0, penetrationFlat: 0, penetrationPercent: 0 });
}

export function combatButtonTotalsSummary(totals: ButtonModifierTotals) {
  return attackButtonModifierSummary({ modifiers: totals });
}

function persistentButtonIds(buttons: CombatAttackButton[], activeIds: number[]) {
  return buttons.filter((button) => button.keepActiveInCombat && activeIds.includes(button.id)).map((button) => button.id);
}

function generatedModifierValue(totals: ButtonModifierTotals, key: ManualKey) {
  return key === "damagePercentBonus" ? 0 : totals[key];
}

function activeWeapon(character: CombatMap["participants"][number]["character"] | undefined) {
  if (!character) return null;
  const slotName = character.equipment.primaryWeaponSlot || "arma";
  return character.equipment.slots.find((slot) => slot.slot === slotName)?.item || null;
}

export function AttackPanel({ map, selection, result, busy, onResolve, onRollD20 }: {
  map: CombatMap;
  selection: AttackSelection | null;
  result: AttackResult | null;
  busy: boolean;
  onResolve: (payload: Record<string, unknown>) => Promise<AttackResult | undefined>;
  onRollD20: (characterId: number) => Promise<number | undefined>;
}) {
  const active = map.activeCharacterId || map.participants[0]?.character.id || 0;
  const [attackerId, setAttackerId] = useState(active);
  const [defenderId, setDefenderId] = useState(map.participants.find((entry) => entry.character.id !== active)?.character.id || active);
  const [damageType, setDamageType] = useState<(typeof DAMAGE_TYPES)[number]>("Contundente");
  const [values, setValues] = useState<ManualValues>(EMPTY_MANUAL_VALUES);
  const [activeButtonIdsByCharacter, setActiveButtonIdsByCharacter] = useState<Record<number, number[]>>({});
  const [manualMenu, setManualMenu] = useState<ManualKey | null>(null);
  const [damageMenuOpen, setDamageMenuOpen] = useState(false);
  const [attackRoll, setAttackRoll] = useState(0);
  const [damageBase, setDamageBase] = useState(0);
  const [damageAdjustment, setDamageAdjustment] = useState(0);
  const [preview, setPreview] = useState<AttackResult | null>(null);
  const [rollingD20, setRollingD20] = useState(false);
  const [automaticDamage, setAutomaticDamage] = useState(false);
  const [automaticStage, setAutomaticStage] = useState("");
  const [automaticRunning, setAutomaticRunning] = useState(false);

  const attacker = map.participants.find((entry) => entry.character.id === attackerId)?.character;
  const defender = map.participants.find((entry) => entry.character.id === defenderId)?.character;
  const weapon = activeWeapon(attacker);
  const combatButtons = attacker?.combatButtons || [];
  const activeCombatButtonIds = (activeButtonIdsByCharacter[attackerId] || []).filter((id) => combatButtons.some((button) => button.id === id));
  const selectedButtons = combatButtons.filter((button) => activeCombatButtonIds.includes(button.id));
  const selectedTotals = useMemo(() => selectedCombatButtonTotals(combatButtons, activeCombatButtonIds), [combatButtons, activeCombatButtonIds]);
  const selectedTotalsLabel = combatButtonTotalsSummary(selectedTotals);
  const adjustedDamage = adjustedAttackDamage(damageBase, damageAdjustment);
  const sameCombatant = attackerId === defenderId;

  useEffect(() => {
    if (!selection) return;
    setAttackerId(selection.attackerId);
    setDefenderId(selection.defenderId);
  }, [selection]);

  useEffect(() => {
    const configured = String(weapon?.weaponProfile.damageType || "");
    const matching = DAMAGE_TYPES.find((entry) => entry.toLocaleLowerCase("it") === configured.toLocaleLowerCase("it"));
    if (matching) setDamageType(matching);
  }, [weapon?.id, weapon?.weaponProfile.damageType]);

  useEffect(() => {
    if (!result || result.attackerId !== attackerId || result.defenderId !== defenderId) return;
    setPreview(result);
    setAttackRoll(result.attackRoll);
    setDamageBase(result.rawDamage);
    setDamageAdjustment(0);
  }, [attackerId, defenderId, result]);

  const resetSequence = () => {
    setAttackRoll(0);
    setDamageBase(0);
    setDamageAdjustment(0);
    setDamageMenuOpen(false);
    setPreview(null);
  };

  const attackPayload = (options: { apply: boolean; roll: number; rawDamage: number; damagePercentBonus?: number; damageType?: (typeof DAMAGE_TYPES)[number] }) => ({
    attackerId,
    defenderId,
    damageType: options.damageType || damageType,
    ...values,
    attackRoll: options.roll,
    rawDamage: options.rawDamage,
    damagePercentBonus: options.damagePercentBonus ?? values.damagePercentBonus,
    combatButtonIds: activeCombatButtonIds,
    attributeKeys: [],
    powerName: "",
    resourceCosts: {},
    apply: options.apply,
  });

  const retainPersistentButtons = (resolved: AttackResult | undefined) => {
    if (!resolved?.applied) return;
    setActiveButtonIdsByCharacter((current) => ({
      ...current,
      [attackerId]: persistentButtonIds(combatButtons, activeCombatButtonIds),
    }));
  };

  const rollD20 = async () => {
    if (!attackerId) return;
    setRollingD20(true);
    try {
      const rolled = await onRollD20(attackerId);
      if (!rolled) return;
      setAttackRoll(rolled);
      setDamageBase(0);
      setDamageAdjustment(0);
      setPreview(null);
    } finally {
      setRollingD20(false);
    }
  };

  const rollDamage = async () => {
    if (!attackRoll) return;
    const resolved = await onResolve(attackPayload({ apply: false, roll: attackRoll, rawDamage: 0 }));
    if (!resolved) return;
    setPreview(resolved);
    setDamageBase(resolved.rawDamage);
    setDamageAdjustment(0);
  };

  const applyAttack = async (selectedDamageType = damageType) => {
    if (!attackRoll) return;
    const resolved = await onResolve(attackPayload({
      apply: true,
      roll: attackRoll,
      rawDamage: adjustedDamage,
      damagePercentBonus: 0,
      damageType: selectedDamageType,
    }));
    if (!resolved) return;
    setPreview(resolved);
    retainPersistentButtons(resolved);
  };

  const automaticAttack = async () => {
    if (!attackerId || automaticRunning) return;
    setAutomaticRunning(true);
    try {
      setAutomaticStage("1 · Tiro d20…");
      await wait(400);
      const rolled = await onRollD20(attackerId);
      if (!rolled) return;
      setAttackRoll(rolled);
      setAutomaticStage(`1 · d20: ${rolled}`);
      await wait(400);
      setAutomaticStage("2 · Calcolo attacco e danno…");
      const previewResult = await onResolve(attackPayload({ apply: false, roll: rolled, rawDamage: 0 }));
      if (!previewResult) return;
      setPreview(previewResult);
      setDamageBase(previewResult.rawDamage);
      setDamageAdjustment(0);
      setAutomaticStage(previewResult.hit ? `2 · Colpito, danno ${previewResult.rawDamage}` : "2 · Mancato");
      if (!automaticDamage) {
        await wait(400);
        return;
      }
      await wait(400);
      setAutomaticStage(previewResult.hit ? "3 · Applicazione danno…" : "3 · Registrazione mancato…");
      const applied = await onResolve(attackPayload({ apply: true, roll: rolled, rawDamage: previewResult.rawDamage, damagePercentBonus: 0 }));
      if (applied) {
        setPreview(applied);
        retainPersistentButtons(applied);
      }
    } finally {
      setAutomaticStage("");
      setAutomaticRunning(false);
    }
  };

  const selectAndApplyDamageType = async (type: (typeof DAMAGE_TYPES)[number]) => {
    setDamageType(type);
    if (attackRoll && preview?.hit !== false && adjustedDamage > 0) await applyAttack(type);
  };

  const updateManualValue = (key: ManualKey, value: number) => {
    setValues((current) => ({ ...current, [key]: Number.isFinite(value) ? value : 0 }));
  };

  const toggleCombatButton = (buttonId: number) => {
    const selected = activeCombatButtonIds.includes(buttonId);
    setActiveButtonIdsByCharacter((current) => ({
      ...current,
      [attackerId]: selected ? activeCombatButtonIds.filter((id) => id !== buttonId) : [...activeCombatButtonIds, buttonId],
    }));
  };

  const status = preview
    ? preview.applied
      ? preview.hit
        ? "APPLICATO · " + preview.finalDamage + " " + preview.damageType
        : "APPLICATO · mancato"
      : preview.hit
        ? "COLPITO · " + preview.attackTotal + " vs " + preview.defense + " · T" + preview.damageTier + " " + preview.damageFormula + " · " + damageBase + " → " + adjustedDamage
        : "MANCATO · " + preview.attackTotal + " vs " + preview.defense
    : attackRoll
      ? "d20 " + attackRoll + " · tira o inserisci il danno"
      : "Pronto";

  return <div className="combat-compact-attack" data-component-type="panel" data-theme="combat">
    <div className="combat-compact-versus">
      <label><span>Attaccante</span><select value={attackerId} onChange={(event) => { setAttackerId(Number(event.target.value)); resetSequence(); }}>{map.participants.map((entry) => <option key={entry.id} value={entry.character.id}>{entry.character.name}</option>)}</select></label>
      <button type="button" title="Scambia" aria-label="Scambia attaccante e difensore" onClick={() => { setAttackerId(defenderId); setDefenderId(attackerId); resetSequence(); }}>⇄</button>
      <label><span>Difensore</span><select value={defenderId} onChange={(event) => { setDefenderId(Number(event.target.value)); resetSequence(); }}>{map.participants.map((entry) => <option key={entry.id} value={entry.character.id}>{entry.character.name}</option>)}</select></label>
    </div>

    {combatButtons.length > 0 && <div className="combat-compact-modifiers">
      <div className="combat-compact-line-label"><strong>Bottoni</strong><output aria-live="polite">{selectedButtons.length ? "Applicati: " + selectedTotalsLabel : "Nessuno attivo"}</output></div>
      <div className="combat-compact-button-strip">{combatButtons.map((button) => {
        const selected = activeCombatButtonIds.includes(button.id);
        const summary = attackButtonModifierSummary(button);
        return <button type="button" key={button.id} className={selected ? "active" : ""} aria-pressed={selected} onClick={() => toggleCombatButton(button.id)}>
          <span className="combat-compact-check" aria-hidden="true">{selected ? "✓" : ""}</span>
          <strong>{button.name}</strong>
          <small>{summary === "Nessun bonus numerico" ? "Effetto" : summary}</small>
          <span className="combat-compact-tooltip" role="tooltip"><strong>{summary}</strong>{button.helpText && <em>{button.helpText}</em>}</span>
        </button>;
      })}</div>
    </div>}

    <div className="combat-compact-manual">
      <div className="combat-manual-button-strip"><span>Manuali</span>{MANUAL_FIELDS.map((field) => <button
        type="button"
        key={field.key}
        className={(manualMenu === field.key ? "open " : "") + (values[field.key] ? "changed" : "")}
        aria-expanded={manualMenu === field.key}
        title={field.label}
        onClick={() => setManualMenu((current) => current === field.key ? null : field.key)}
      ><small>{field.short}</small><strong>{signed(values[field.key])}</strong>{generatedModifierValue(selectedTotals, field.key) !== 0 && <em title="Da bottoni attivi">{signed(generatedModifierValue(selectedTotals, field.key))}</em>}</button>)}</div>
      {manualMenu && <div className="combat-instant-menu">
        <strong>{MANUAL_FIELDS.find((field) => field.key === manualMenu)?.label}</strong>
        <button type="button" onClick={() => updateManualValue(manualMenu, values[manualMenu] - 1)}>−1</button>
        <input type="number" aria-label={MANUAL_FIELDS.find((field) => field.key === manualMenu)?.label} value={values[manualMenu]} onChange={(event) => updateManualValue(manualMenu, Number(event.target.value))} />
        <button type="button" onClick={() => updateManualValue(manualMenu, values[manualMenu] + 1)}>+1</button>
        <button type="button" className="reset" onClick={() => updateManualValue(manualMenu, 0)}>Azzera</button>
      </div>}
    </div>

    <div className="combat-compact-sequence">
      <div className="combat-compact-roll"><span>1 · d20</span><input type="number" min="1" max="20" value={attackRoll || ""} onChange={(event) => { setAttackRoll(Number(event.target.value)); setPreview(null); }} /><button type="button" title="Tira d20" disabled={busy || rollingD20 || sameCombatant} onClick={rollD20}>↻</button></div>
      <div className="combat-compact-roll"><span>2 · Danno</span><input type="number" min="0" value={damageBase || ""} onChange={(event) => { setDamageBase(Math.max(0, Number(event.target.value))); setPreview((current) => current?.applied ? null : current); }} /><button type="button" title="Tira danno" disabled={busy || !attackRoll || sameCombatant} onClick={rollDamage}>↻</button></div>
      <button type="button" className={(damageMenuOpen ? "open " : "") + (damageAdjustment ? "changed" : "")} aria-expanded={damageMenuOpen} onClick={() => setDamageMenuOpen((current) => !current)}><span>3 · Mod.</span><strong>{signed(damageAdjustment)}%</strong></button>
    </div>

    <div className="combat-compact-damage-types" aria-label="Tipo di danno"><span>4 · Tipo — seleziona per applicare</span><div className="damage-type-grid">{DAMAGE_TYPES.map((entry) => <button type="button" key={entry} className={`${entry.toLocaleLowerCase("it")} ${damageType === entry ? "active" : ""}`} aria-pressed={damageType === entry} disabled={busy || automaticRunning || !attackRoll || preview?.hit === false || adjustedDamage <= 0} onClick={() => selectAndApplyDamageType(entry)}>{entry}</button>)}</div></div>

    {damageMenuOpen && <div className="combat-instant-menu combat-damage-menu">
      <strong>{damageBase} → {adjustedDamage}</strong>
      <button type="button" onClick={() => setDamageAdjustment((current) => current - 10)}>−10%</button>
      <button type="button" onClick={() => setDamageAdjustment((current) => current + 10)}>+10%</button>
      <button type="button" onClick={() => setDamageAdjustment((current) => current + 33)}>+33%</button>
      <button type="button" onClick={() => setDamageAdjustment((current) => current + 50)}>+50%</button>
      <button type="button" className="reset" onClick={() => setDamageAdjustment(0)}>Azzera</button>
    </div>}

    <div className={(preview?.applied ? "applied " : "") + (preview?.hit === false ? "miss " : "") + "combat-compact-status"} aria-live="polite"><strong>{automaticStage || status}</strong>{sameCombatant && <span>Scegli un altro difensore</span>}</div>
    <div className="combat-compact-actions">
      <button type="button" className="button secondary small" disabled={busy || rollingD20} onClick={resetSequence}>Reset</button>
      <label className="combat-auto-damage"><input type="checkbox" checked={automaticDamage} onChange={(event) => setAutomaticDamage(event.target.checked)} /> Danno automatico</label>
      <button type="button" className="button secondary small" disabled={busy || rollingD20 || automaticRunning || sameCombatant} onClick={automaticAttack}>{automaticRunning ? "In corso…" : "Automatico"}</button>
      {preview?.hit === false && <button type="button" className="button primary small" disabled={busy || !attackRoll || sameCombatant} onClick={() => applyAttack()}>Registra mancato</button>}
    </div>
  </div>;
}

import { useEffect, useMemo, useState } from "react";

import type { AttackResult, CombatAttackButton, CombatMap } from "./types";

const DAMAGE_TYPES = ["Contundente", "Perforante", "Taglio", "Gelo", "Fuoco", "Elettro", "Puro"] as const;
type DamageType = (typeof DAMAGE_TYPES)[number];
/** Etichette corte: a piena larghezza i nomi non stanno in una griglia da quattro colonne. */
const DAMAGE_TYPE_LABELS: Record<DamageType, string> = {
  Contundente: "Cont.", Perforante: "Perf.", Taglio: "Tagl.", Gelo: "Gelo",
  Fuoco: "Fuoco", Elettro: "Elet.", Puro: "Puro",
};
const DAMAGE_ADJUSTMENT_PRESETS = [-10, 10, 33, 50] as const;

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
  const [damageType, setDamageType] = useState<DamageType>("Contundente");
  const [values, setValues] = useState<ManualValues>(EMPTY_MANUAL_VALUES);
  const [activeButtonIdsByCharacter, setActiveButtonIdsByCharacter] = useState<Record<number, number[]>>({});
  const [attackRoll, setAttackRoll] = useState(0);
  const [damageBase, setDamageBase] = useState(0);
  const [damageRolled, setDamageRolled] = useState(false);
  const [damageAdjustment, setDamageAdjustment] = useState(0);
  const [preview, setPreview] = useState<AttackResult | null>(null);
  const [rollingD20, setRollingD20] = useState(false);
  const [automaticDamage, setAutomaticDamage] = useState(false);
  const [automaticStage, setAutomaticStage] = useState("");
  const [automaticRunning, setAutomaticRunning] = useState(false);

  const attacker = map.participants.find((entry) => entry.character.id === attackerId)?.character;
  const weapon = activeWeapon(attacker);
  const combatButtons = attacker?.combatButtons || [];
  const activeCombatButtonIds = (activeButtonIdsByCharacter[attackerId] || []).filter((id) => combatButtons.some((button) => button.id === id));
  const selectedButtons = combatButtons.filter((button) => activeCombatButtonIds.includes(button.id));
  const selectedTotals = useMemo(() => selectedCombatButtonTotals(combatButtons, activeCombatButtonIds), [combatButtons, activeCombatButtonIds]);
  const selectedTotalsLabel = combatButtonTotalsSummary(selectedTotals);
  const adjustedDamage = adjustedAttackDamage(damageBase, damageAdjustment);
  const sameCombatant = attackerId === defenderId;
  const missed = preview?.hit === false;
  const canAttack = Boolean(attackRoll) && !sameCombatant && !busy && !automaticRunning;
  const canRollDamage = Boolean(preview) && !missed && canAttack;
  const canApply = damageRolled && adjustedDamage > 0 && !missed && canAttack;

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
    setDamageRolled(result.rawDamage > 0);
    setDamageAdjustment(0);
  }, [attackerId, defenderId, result]);

  const resetSequence = () => {
    setAttackRoll(0);
    setDamageBase(0);
    setDamageRolled(false);
    setDamageAdjustment(0);
    setPreview(null);
  };

  const attackPayload = (options: {
    apply: boolean;
    roll: number;
    rawDamage: number;
    rollDamage: boolean;
    damagePercentBonus?: number;
    damageType?: DamageType;
  }) => ({
    attackerId,
    defenderId,
    damageType: options.damageType || damageType,
    ...values,
    attackRoll: options.roll,
    rawDamage: options.rawDamage,
    rollDamage: options.rollDamage,
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
      if (!rolled) return rolled;
      setAttackRoll(rolled);
      setDamageBase(0);
      setDamageRolled(false);
      setDamageAdjustment(0);
      setPreview(null);
      return rolled;
    } finally {
      setRollingD20(false);
    }
  };

  /** Passo 2: risolve l'attacco e pubblica la formula, senza tirare il danno. */
  const resolveAttackStep = async (roll = attackRoll) => {
    if (!roll) return undefined;
    const resolved = await onResolve(attackPayload({ apply: false, roll, rawDamage: 0, rollDamage: false }));
    if (!resolved) return undefined;
    setPreview(resolved);
    setDamageBase(0);
    setDamageRolled(false);
    setDamageAdjustment(0);
    return resolved;
  };

  /** Passo 3: tira la formula appena pubblicata. */
  const rollDamage = async (roll = attackRoll) => {
    if (!roll) return undefined;
    const resolved = await onResolve(attackPayload({ apply: false, roll, rawDamage: 0, rollDamage: true }));
    if (!resolved) return undefined;
    setPreview(resolved);
    setDamageBase(resolved.rawDamage);
    setDamageRolled(true);
    setDamageAdjustment(0);
    return resolved;
  };

  /** Passo 5: applica il danno già tirato. rollDamage resta false per non ritirarlo mai. */
  const applyAttack = async (selectedDamageType = damageType, rawDamage = adjustedDamage) => {
    if (!attackRoll) return;
    const resolved = await onResolve(attackPayload({
      apply: true,
      roll: attackRoll,
      rawDamage,
      rollDamage: false,
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
      const rolled = await rollD20();
      if (!rolled) return;
      setAutomaticStage(`2 · d20 ${rolled} · risoluzione attacco…`);
      await wait(400);
      const attacked = await resolveAttackStep(rolled);
      if (!attacked) return;
      if (!attacked.hit) {
        setAutomaticStage("2 · Mancato");
        await wait(400);
        return;
      }
      setAutomaticStage(`3 · ${attacked.damageFormula} · tiro danno…`);
      await wait(400);
      const rolledDamage = await rollDamage(rolled);
      if (!rolledDamage) return;
      setAutomaticStage(`3 · Danno ${rolledDamage.rawDamage}`);
      if (!automaticDamage) {
        await wait(400);
        return;
      }
      await wait(400);
      setAutomaticStage("5 · Applicazione danno…");
      await applyAttack(damageType, rolledDamage.rawDamage);
    } finally {
      setAutomaticStage("");
      setAutomaticRunning(false);
    }
  };

  const selectAndApplyDamageType = async (type: DamageType) => {
    setDamageType(type);
    if (canApply) await applyAttack(type);
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

  const statusHeadline = preview
    ? preview.applied
      ? preview.hit ? `Applicato · ${preview.finalDamage} ${preview.damageType}` : "Applicato · mancato"
      : preview.hit ? `Colpito · ${preview.attackTotal} vs ${preview.defense}` : `Mancato · ${preview.attackTotal} vs ${preview.defense}`
    : attackRoll ? `d20 ${attackRoll} · premi Attacca` : "Pronto";
  const statusDetail = preview && preview.hit && !preview.applied
    ? [
      `T${preview.damageTier}`,
      preview.damageFormula,
      preview.critical !== "none" ? `critico ${preview.critical}` : "",
      damageRolled ? `danno ${damageBase}${damageAdjustment ? ` → ${adjustedDamage}` : ""}` : "",
    ].filter(Boolean).join(" · ")
    : "";

  return <div className="combat-attack" data-component-type="panel" data-theme="combat">

    <section className="ca-combatants">
      <div className="ca-versus">
        <label><span>Attaccante</span><select value={attackerId} onChange={(event) => { setAttackerId(Number(event.target.value)); resetSequence(); }}>{map.participants.map((entry) => <option key={entry.id} value={entry.character.id}>{entry.character.name}</option>)}</select></label>
        <button type="button" className="ca-swap" title="Scambia" aria-label="Scambia attaccante e difensore" onClick={() => { setAttackerId(defenderId); setDefenderId(attackerId); resetSequence(); }}>⇄</button>
        <label><span>Difensore</span><select value={defenderId} onChange={(event) => { setDefenderId(Number(event.target.value)); resetSequence(); }}>{map.participants.map((entry) => <option key={entry.id} value={entry.character.id}>{entry.character.name}</option>)}</select></label>
      </div>

      {combatButtons.length > 0 && <div className="ca-buttons">
        <p className="ca-heading"><strong>Bottoni</strong><output aria-live="polite">{selectedButtons.length ? selectedTotalsLabel : "Nessuno attivo"}</output></p>
        <div className="ca-button-strip">{combatButtons.map((button) => {
          const selected = activeCombatButtonIds.includes(button.id);
          const summary = attackButtonModifierSummary(button);
          return <button type="button" key={button.id} className={selected ? "active" : ""} aria-pressed={selected} onClick={() => toggleCombatButton(button.id)}>
            <span className="ca-check" aria-hidden="true">{selected ? "✓" : ""}</span>
            <strong>{button.name}</strong>
            <small>{summary === "Nessun bonus numerico" ? "Effetto" : summary}</small>
            <span className="ca-tooltip" role="tooltip"><strong>{summary}</strong>{button.helpText && <em>{button.helpText}</em>}</span>
          </button>;
        })}</div>
      </div>}
    </section>

    <div className="ca-split">
      <section className="ca-modifiers">
        <p className="ca-heading"><strong>Modificatori</strong><output>man. + bottoni</output></p>
        <div className="ca-mod-list">{MANUAL_FIELDS.map((field) => {
          const generated = generatedModifierValue(selectedTotals, field.key);
          const total = values[field.key] + generated;
          return <div className={`ca-mod-row${total ? " changed" : ""}`} key={field.key}>
            <span title={field.label}>{field.short}</span>
            <button type="button" aria-label={`${field.label}: meno uno`} onClick={() => updateManualValue(field.key, values[field.key] - 1)}>−</button>
            <input type="number" aria-label={field.label} value={values[field.key]} onChange={(event) => updateManualValue(field.key, Number(event.target.value))} />
            <button type="button" aria-label={`${field.label}: più uno`} onClick={() => updateManualValue(field.key, values[field.key] + 1)}>+</button>
            <b title={generated ? `manuale ${signed(values[field.key])} + bottoni ${signed(generated)}` : "Totale"}>{signed(total)}</b>
          </div>;
        })}</div>
      </section>

      <section className="ca-sequence">
        <p className="ca-heading"><strong>Sequenza</strong></p>

        <div className="ca-step">
          <span>1 · d20</span>
          <div className="ca-field">
            <input type="number" min="1" max="20" aria-label="Tiro d20" value={attackRoll || ""} onChange={(event) => { setAttackRoll(Number(event.target.value)); setPreview(null); setDamageRolled(false); }} />
            <button type="button" title="Tira d20" disabled={busy || rollingD20 || automaticRunning || sameCombatant} onClick={() => rollD20()}>↻</button>
          </div>
        </div>

        <div className="ca-step">
          <span>2 · Attacca</span>
          <button type="button" className="ca-action" disabled={!canAttack} onClick={() => resolveAttackStep()}>Attacca</button>
          {preview && <em className="ca-note">{preview.damageFormula}</em>}
        </div>

        <div className="ca-step">
          <span>3 · Tira danno</span>
          <div className="ca-field">
            <input type="number" min="0" aria-label="Danno" value={damageBase || ""} onChange={(event) => { setDamageBase(Math.max(0, Number(event.target.value))); setDamageRolled(Number(event.target.value) > 0); }} />
            <button type="button" title="Tira il danno" disabled={!canRollDamage} onClick={() => rollDamage()}>↻</button>
          </div>
        </div>

        <div className="ca-step">
          <span>4 · Mod. danno</span>
          <div className="ca-presets">
            {DAMAGE_ADJUSTMENT_PRESETS.map((preset) => <button type="button" key={preset} disabled={!damageRolled} onClick={() => setDamageAdjustment((current) => current + preset)}>{signed(preset)}</button>)}
            <button type="button" className={damageAdjustment ? "ca-preset-total changed" : "ca-preset-total"} title="Azzera la modifica" disabled={!damageAdjustment} onClick={() => setDamageAdjustment(0)}>{signed(damageAdjustment)}%</button>
          </div>
          {damageAdjustment !== 0 && <em className="ca-note">{damageBase} → {adjustedDamage}</em>}
        </div>
      </section>
    </div>

    <section className="ca-outcome">
      <div className={`ca-status${preview?.applied ? " applied" : ""}${missed ? " miss" : ""}`} aria-live="polite">
        <strong>{automaticStage || statusHeadline}</strong>
        {!automaticStage && statusDetail && <span>{statusDetail}</span>}
        {sameCombatant && <span className="ca-warning">Scegli un altro difensore</span>}
      </div>

      <div className="ca-types">
        <p className="ca-heading"><strong>5 · Tipo</strong><output>seleziona per applicare</output></p>
        <div className="ca-type-grid">{DAMAGE_TYPES.map((entry) => <button
          type="button"
          key={entry}
          className={`${entry.toLocaleLowerCase("it")}${damageType === entry ? " active" : ""}`}
          title={entry}
          aria-pressed={damageType === entry}
          disabled={!canApply}
          onClick={() => selectAndApplyDamageType(entry)}
        >{DAMAGE_TYPE_LABELS[entry]}</button>)}</div>
      </div>

      <div className="ca-actions">
        <button type="button" className="button secondary small" disabled={busy || rollingD20} onClick={resetSequence}>Reset</button>
        <label className="ca-auto"><input type="checkbox" checked={automaticDamage} onChange={(event) => setAutomaticDamage(event.target.checked)} /> Danno automatico</label>
        <button type="button" className="button secondary small" disabled={busy || rollingD20 || automaticRunning || sameCombatant} onClick={automaticAttack}>{automaticRunning ? "In corso…" : "Automatico"}</button>
        {missed && !preview?.applied && <button type="button" className="button primary small" disabled={!canAttack} onClick={() => applyAttack(damageType, 0)}>Registra mancato</button>}
      </div>
    </section>
  </div>;
}

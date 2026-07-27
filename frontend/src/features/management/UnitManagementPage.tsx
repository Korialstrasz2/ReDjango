import { type Dispatch, type SetStateAction, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import type {
  ManagedUnitDetail,
  UnitEquipmentGroup,
  UnitGenerationPreview,
  UnitInnateAction,
  UnitItemOption,
  UnitManagementOverview,
  UnitSkillOption,
  UnitStatCurve,
} from "./types";

type UnitActionData = {
  management?: {
    unit?: ManagedUnitDetail;
    overview?: UnitManagementOverview;
    created?: boolean;
    preview?: UnitGenerationPreview;
  };
};

const emptyUnit = (): ManagedUnitDetail => ({
  id: null,
  name: "",
  category: "",
  archetypeDescription: "",
  competenceProfile: {},
  archetypeTags: {
    core_fisico: 3,
    focus_combat: 3,
    attacco: 2,
    difesa: 2,
  },
  statProfile: { baseModifiers: {}, perLevelModifiers: {}, milestones: [], curves: [] },
  skillUnlocks: [],
  equipmentSlots: [],
  equipmentGroups: [],
  accessoryCountByLevel: [],
  innateActions: [],
  levels: [],
  loreDescription: "",
  notes: "",
  archived: false,
  generation: {
    kind: "humanoid",
    coreKey: "warrior",
    coreShare: 0.5,
    startingXp: 0,
    xpBase: 20,
    xpGrowth: 1,
    competenceStartingXp: 5,
    competenceXpBase: 15,
    competenceXpGrowth: 0,
    finalSpendingPasses: 4,
    magicPolicy: "none",
    allowedClassFamilies: [],
    allowedReligionFamilies: [],
    allowedRaces: [],
    allowHumanoidStatGrowth: false,
  },
  metadata: {},
});

function cloneUnit(unit: ManagedUnitDetail): ManagedUnitDetail {
  return JSON.parse(JSON.stringify(unit)) as ManagedUnitDetail;
}

function SearchPicker<T extends UnitSkillOption | UnitItemOption>({
  kind,
  label,
  onChoose,
}: {
  kind: "skill" | "item";
  label: string;
  onChoose: (entry: T) => void;
}) {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const result = useQuery({
    queryKey: ["management-unit-options", kind, query],
    queryFn: () => getData<{ kind: string; options: T[] }>(
      `/api/v1/management/units/options?kind=${kind}&query=${encodeURIComponent(query)}&limit=80`,
    ),
    enabled: query.length >= 2,
  });
  return <div className="unit-option-picker" data-component-type="panel" data-theme="muted">
    <form onSubmit={(event) => { event.preventDefault(); setQuery(input.trim()); }}>
      <label>{label}<input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Almeno due caratteri…" /></label>
      <button className="button secondary small" disabled={input.trim().length < 2}>Cerca</button>
    </form>
    {result.isFetching && <small>Ricerca…</small>}
    {result.error && <small className="form-error">{(result.error as Error).message}</small>}
    {result.data && <div className="unit-option-results">
      {result.data.options.map((entry) => <button key={entry.id} type="button" onClick={() => onChoose(entry)}>
        <strong>{entry.name}</strong>
        <small>{"family" in entry ? `${entry.group} · ${entry.family} · ${entry.baseXpCost} PE` : `${entry.types.join(" / ") || "Senza tipo"}${entry.rarity == null ? "" : ` · rarità ${entry.rarity}`}`}</small>
      </button>)}
      {!result.data.options.length && <small>Nessun risultato.</small>}
    </div>}
  </div>;
}

function ModifierEditor({
  title,
  values,
  onChange,
}: {
  title: string;
  values: Record<string, number>;
  onChange: (values: Record<string, number>) => void;
}) {
  const rows = Object.entries(values);
  return <section className="unit-subpanel">
    <header><div><h3>{title}</h3><small>Modificatori deterministici, non tiri casuali.</small></div><button type="button" className="button secondary small" onClick={() => onChange({ ...values, nuova_variabile: 0 })}>Aggiungi</button></header>
    <div className="unit-modifier-list">
      {rows.map(([key, value], index) => <div key={`${key}-${index}`}>
        <input aria-label="Variabile" value={key} onChange={(event) => {
          const next = { ...values };
          delete next[key];
          next[event.target.value] = value;
          onChange(next);
        }} />
        <input aria-label="Valore" type="number" step="0.05" value={value} onChange={(event) => onChange({ ...values, [key]: Number(event.target.value) })} />
        <button className="icon-button" type="button" aria-label={`Rimuovi ${key}`} onClick={() => {
          const next = { ...values };
          delete next[key];
          onChange(next);
        }}>×</button>
      </div>)}
      {!rows.length && <p className="management-empty-inline">Nessun modificatore.</p>}
    </div>
  </section>;
}

function SkillPoolEditor({
  draft,
  setDraft,
}: {
  draft: ManagedUnitDetail;
  setDraft: Dispatch<SetStateAction<ManagedUnitDetail>>;
}) {
  const update = (index: number, values: Record<string, unknown>) => setDraft((current) => ({
    ...current,
    skillUnlocks: current.skillUnlocks.map((entry, row) => row === index ? { ...entry, ...values } : entry),
  }));
  return <section className="unit-editor-section" data-component-type="panel" data-theme="arcane">
    <header><div><p className="eyebrow">Metà personalizzata</p><h2>Pool Skill dell'archetipo</h2><p>Il Core usa metà dei PE. Queste Skill competono soltanto per l'altra metà, rispettando costi e prerequisiti reali.</p></div></header>
    <SearchPicker<UnitSkillOption> kind="skill" label="Aggiungi Skill al pool" onChoose={(skill) => {
      if (draft.skillUnlocks.some((entry) => entry.skillId === skill.id)) return;
      setDraft((current) => ({
        ...current,
        skillUnlocks: [...current.skillUnlocks, {
          skillId: skill.id,
          skillName: skill.name,
          family: skill.family,
          group: skill.group,
          pool: "archetype",
          weight: 5,
          minLevel: 1,
          maxLevel: 20,
        }],
      }));
    }} />
    <div className="unit-pool-table">
      <div className="unit-pool-head"><span>Skill</span><span>Pool</span><span>Livelli</span><span>Peso</span><span>Obbligo</span><span /></div>
      {draft.skillUnlocks.map((entry, index) => <div className="unit-pool-row" key={entry.skillId}>
        <span><strong>{entry.skillName}</strong><small>{entry.group} · {entry.family}</small></span>
        <select value={entry.perkTier || entry.pool} onChange={(event) => {
          const value = event.target.value;
          update(index, value === "minor" || value === "major"
            ? { pool: "archetype", perkTier: value }
            : { pool: value, perkTier: undefined });
        }}>
          <option value="archetype">Archetipo</option>
          <option value="core">Core personalizzato</option>
          <option value="minor">Perk minore</option>
          <option value="major">Perk maggiore</option>
        </select>
        <span className="range-pair"><input aria-label="Livello minimo" type="number" min="1" max="20" value={entry.minLevel} onChange={(event) => update(index, { minLevel: Number(event.target.value) })} /><b>–</b><input aria-label="Livello massimo" type="number" min="1" max="20" value={entry.maxLevel} onChange={(event) => update(index, { maxLevel: Number(event.target.value) })} /></span>
        <input aria-label="Peso" type="number" min="0.1" step="0.1" value={entry.weight} onChange={(event) => update(index, { weight: Number(event.target.value) })} />
        <input aria-label="Livello obbligatorio" type="number" min="1" max="20" value={entry.requiredAtLevel ?? ""} placeholder="—" onChange={(event) => update(index, { requiredAtLevel: event.target.value ? Number(event.target.value) : undefined })} />
        <button className="icon-button" type="button" aria-label={`Rimuovi ${entry.skillName}`} onClick={() => setDraft((current) => ({ ...current, skillUnlocks: current.skillUnlocks.filter((_, row) => row !== index) }))}>×</button>
      </div>)}
      {!draft.skillUnlocks.length && <p className="management-empty-inline">Il profilo a 13 assi può costruire il pool automaticamente; aggiungi qui le Skill che definiscono davvero questo archetipo.</p>}
    </div>
  </section>;
}

function ItemRows({
  entries,
  onChange,
  onRemove,
  showSlot = false,
  slotOptions = [],
}: {
  entries: Array<{ itemId: number; itemName: string; minLevel: number; maxLevel: number; weight: number; chance: number; slot?: string }>;
  onChange: (index: number, values: Record<string, unknown>) => void;
  onRemove: (index: number) => void;
  showSlot?: boolean;
  slotOptions?: Array<{ value: string; label: string }>;
}) {
  return <div className="unit-item-rows">
    {entries.map((entry, index) => <div key={`${entry.itemId}-${entry.slot || "group"}-${index}`}>
      <span><strong>{entry.itemName}</strong><small>#{entry.itemId}</small></span>
      {showSlot && <select value={entry.slot} onChange={(event) => onChange(index, { slot: event.target.value })}>{slotOptions.map((slot) => <option key={slot.value} value={slot.value}>{slot.label}</option>)}</select>}
      <span className="range-pair"><input aria-label="Livello minimo" type="number" min="1" max="20" value={entry.minLevel} onChange={(event) => onChange(index, { minLevel: Number(event.target.value) })} /><b>–</b><input aria-label="Livello massimo" type="number" min="1" max="20" value={entry.maxLevel} onChange={(event) => onChange(index, { maxLevel: Number(event.target.value) })} /></span>
      <input aria-label="Peso" type="number" min="0.1" step="0.1" value={entry.weight} onChange={(event) => onChange(index, { weight: Number(event.target.value) })} />
      <input aria-label="Probabilità equipaggiamento" title="Probabilità da 0 a 1" type="number" min="0" max="1" step="0.05" value={entry.chance} onChange={(event) => onChange(index, { chance: Number(event.target.value) })} />
      <button className="icon-button" type="button" aria-label={`Rimuovi ${entry.itemName}`} onClick={() => onRemove(index)}>×</button>
    </div>)}
  </div>;
}

function EquipmentEditor({
  draft,
  setDraft,
  configuration,
}: {
  draft: ManagedUnitDetail;
  setDraft: Dispatch<SetStateAction<ManagedUnitDetail>>;
  configuration: UnitManagementOverview["configuration"];
}) {
  const [slot, setSlot] = useState("arma");
  const addGroup = () => setDraft((current) => ({
    ...current,
    equipmentGroups: [...current.equipmentGroups, { name: "Nuovo gruppo accessori", slots: ["orecchino_1", "orecchino_2"], minCount: 0, maxCount: 1, emptyChance: 0, items: [] }],
  }));
  const updateGroup = (index: number, values: Partial<UnitEquipmentGroup>) => setDraft((current) => ({
    ...current,
    equipmentGroups: current.equipmentGroups.map((entry, row) => row === index ? { ...entry, ...values } : entry),
  }));
  return <section className="unit-editor-section" data-component-type="panel" data-theme="gold">
    <header><div><p className="eyebrow">Pool a fasce</p><h2>Equipaggiamento coerente</h2><p>Ogni oggetto ha livello minimo, massimo e peso. Nessun oggetto fuori pool può essere assegnato.</p></div><button type="button" className="button secondary" onClick={addGroup}>Nuovo gruppo accessori</button></header>
    <div className="unit-add-item-row"><label>Slot<select value={slot} onChange={(event) => setSlot(event.target.value)}>{configuration.equipmentSlots.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label><SearchPicker<UnitItemOption> kind="item" label={`Aggiungi a ${configuration.equipmentSlots.find((entry) => entry.value === slot)?.label || slot}`} onChoose={(item) => {
      setDraft((current) => ({
        ...current,
        equipmentSlots: [...current.equipmentSlots, { slot, itemId: item.id, itemName: item.name, minLevel: 1, maxLevel: 20, weight: 1, chance: 1 }],
      }));
    }} /></div>
    <h3>Slot fissi</h3>
    <ItemRows
      showSlot
      slotOptions={configuration.equipmentSlots}
      entries={draft.equipmentSlots}
      onChange={(index, values) => setDraft((current) => ({ ...current, equipmentSlots: current.equipmentSlots.map((entry, row) => row === index ? { ...entry, ...values } : entry) }))}
      onRemove={(index) => setDraft((current) => ({ ...current, equipmentSlots: current.equipmentSlots.filter((_, row) => row !== index) }))}
    />
    {!draft.equipmentSlots.length && <p className="management-empty-inline">Nessun oggetto in slot fisso.</p>}
    <div className="unit-section-heading">
      <div><h3>Quantità accessori per livello</h3><p>Se configurata, questa curva stabilisce il totale di gioielli/accessori; i minimi dei gruppi restano garantiti.</p></div>
      <button className="button secondary small" type="button" onClick={() => setDraft((current) => ({ ...current, accessoryCountByLevel: [...current.accessoryCountByLevel, { minLevel: 1, maxLevel: 20, minCount: 2, maxCount: 4 }] }))}>Aggiungi fascia</button>
    </div>
    <div className="unit-item-rows">
      {draft.accessoryCountByLevel.map((band, index) => <div className="unit-item-row" key={`${band.minLevel}-${band.maxLevel}-${index}`}>
        <label>Livello min<input type="number" min="1" max="20" value={band.minLevel} onChange={(event) => setDraft((current) => ({ ...current, accessoryCountByLevel: current.accessoryCountByLevel.map((entry, row) => row === index ? { ...entry, minLevel: Number(event.target.value) } : entry) }))} /></label>
        <label>Livello max<input type="number" min={band.minLevel} max="20" value={band.maxLevel} onChange={(event) => setDraft((current) => ({ ...current, accessoryCountByLevel: current.accessoryCountByLevel.map((entry, row) => row === index ? { ...entry, maxLevel: Number(event.target.value) } : entry) }))} /></label>
        <label>Accessori min<input type="number" min="0" max="30" value={band.minCount} onChange={(event) => setDraft((current) => ({ ...current, accessoryCountByLevel: current.accessoryCountByLevel.map((entry, row) => row === index ? { ...entry, minCount: Number(event.target.value) } : entry) }))} /></label>
        <label>Accessori max<input type="number" min={band.minCount} max="30" value={band.maxCount} onChange={(event) => setDraft((current) => ({ ...current, accessoryCountByLevel: current.accessoryCountByLevel.map((entry, row) => row === index ? { ...entry, maxCount: Number(event.target.value) } : entry) }))} /></label>
        <button className="button danger small" type="button" onClick={() => setDraft((current) => ({ ...current, accessoryCountByLevel: current.accessoryCountByLevel.filter((_, row) => row !== index) }))}>Rimuovi</button>
      </div>)}
      {!draft.accessoryCountByLevel.length && <p className="management-empty-inline">Nessuna curva globale: ogni gruppo usa soltanto Minimo, Massimo e Prob. vuoto.</p>}
    </div>
    <h3>Gruppi accessori</h3>
    <div className="unit-equipment-groups">
      {draft.equipmentGroups.map((group, groupIndex) => <section key={`${group.name}-${groupIndex}`} className="unit-subpanel">
        <header>
          <input aria-label="Nome gruppo" value={group.name} onChange={(event) => updateGroup(groupIndex, { name: event.target.value })} />
          <label>Minimo<input type="number" min="0" max={group.slots.length} value={group.minCount} onChange={(event) => updateGroup(groupIndex, { minCount: Number(event.target.value) })} /></label>
          <label>Massimo<input type="number" min={group.minCount} max={group.slots.length} value={group.maxCount} onChange={(event) => updateGroup(groupIndex, { maxCount: Number(event.target.value) })} /></label>
          <label>Prob. vuoto<input type="number" min="0" max="1" step="0.05" value={group.emptyChance} onChange={(event) => updateGroup(groupIndex, { emptyChance: Number(event.target.value) })} /></label>
          <button className="button danger small" type="button" onClick={() => setDraft((current) => ({ ...current, equipmentGroups: current.equipmentGroups.filter((_, row) => row !== groupIndex) }))}>Rimuovi gruppo</button>
        </header>
        <label>Slot possibili<select multiple value={group.slots} onChange={(event) => updateGroup(groupIndex, { slots: Array.from(event.target.selectedOptions, (option) => option.value) })}>{configuration.equipmentSlots.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>
        <ItemRows
          entries={group.items}
          onChange={(index, values) => updateGroup(groupIndex, { items: group.items.map((entry, row) => row === index ? { ...entry, ...values } : entry) })}
          onRemove={(index) => updateGroup(groupIndex, { items: group.items.filter((_, row) => row !== index) })}
        />
        <SearchPicker<UnitItemOption> kind="item" label="Aggiungi oggetto al gruppo" onChoose={(item) => updateGroup(groupIndex, { items: [...group.items, { itemId: item.id, itemName: item.name, minLevel: 1, maxLevel: 20, weight: 1, chance: 1 }] })} />
      </section>)}
      {!draft.equipmentGroups.length && <p className="management-empty-inline">Nessun gruppo accessori. Usali per scegliere, per esempio, un solo orecchino fra più varianti coerenti.</p>}
    </div>
  </section>;
}

function ActionEditor({
  actions,
  onChange,
}: {
  actions: UnitInnateAction[];
  onChange: (actions: UnitInnateAction[]) => void;
}) {
  const update = (index: number, values: Partial<UnitInnateAction>) => onChange(
    actions.map((entry, row) => row === index ? { ...entry, ...values } : entry),
  );
  const updateCost = (index: number, key: string, value: number) => update(index, {
    costs: { ...actions[index].costs, [key]: value },
  });
  return <section className="unit-subpanel">
    <header><div><h3>Abilità innate</h3><small>Morso, balzo, soffio, volo o mutaforma: sono azioni proprie dell'Unit, non Skill acquistate con PE.</small></div><button className="button secondary small" type="button" onClick={() => onChange([...actions, { key: `azione-${actions.length + 1}`, name: "", description: "", minLevel: 1, maxLevel: 20, costs: {}, trigger: "", duration: "", icon: "runa" }])}>Aggiungi</button></header>
    <div className="unit-action-list">
      {actions.map((action, index) => <div className="unit-action-entry" key={`${action.key}-${index}`}>
        <div className="unit-action-main">
          <input placeholder="Nome" value={action.name} onChange={(event) => update(index, { name: event.target.value })} />
          <textarea rows={2} placeholder="Regola o promemoria" value={action.description} onChange={(event) => update(index, { description: event.target.value })} />
          <span className="range-pair"><input aria-label="Livello minimo abilità" type="number" min="1" max="20" value={action.minLevel} onChange={(event) => update(index, { minLevel: Number(event.target.value) })} /><b>–</b><input aria-label="Livello massimo abilità" type="number" min="1" max="20" value={action.maxLevel} onChange={(event) => update(index, { maxLevel: Number(event.target.value) })} /></span>
        </div>
        <div className="unit-action-rules">
          <label>Attivazione<input value={action.trigger} placeholder="Azione, passiva…" onChange={(event) => update(index, { trigger: event.target.value })} /></label>
          <label>Durata<input value={action.duration} placeholder="Istantanea, 3 turni…" onChange={(event) => update(index, { duration: event.target.value })} /></label>
          <label>Icona<input value={action.icon} onChange={(event) => update(index, { icon: event.target.value })} /></label>
          {(["pa", "energia", "mana", "potere"] as const).map((key) => <label key={key}>Costo {key.toUpperCase()}<input type="number" min="0" value={action.costs[key] || 0} onChange={(event) => updateCost(index, key, Number(event.target.value))} /></label>)}
        </div>
        <button className="icon-button" type="button" onClick={() => onChange(actions.filter((_, row) => row !== index))}>×</button>
      </div>)}
    </div>
  </section>;
}

function StatCurveEditor({
  curves,
  configuration,
  onChange,
}: {
  curves: UnitStatCurve[];
  configuration: UnitManagementOverview["configuration"];
  onChange: (curves: UnitStatCurve[]) => void;
}) {
  const variables = configuration.statCurveVariables;
  const presetFor = (key: string, profile: UnitStatCurve["profile"]) => (
    profile === "custom" ? null : variables.find((entry) => entry.key === key)?.presets[profile]
  );
  const update = (index: number, values: Partial<UnitStatCurve>) => onChange(
    curves.map((entry, row) => row === index ? { ...entry, ...values } : entry),
  );
  const add = () => {
    const key = variables.find((entry) => !curves.some((curve) => curve.key === entry.key))?.key || variables[0]?.key;
    if (!key) return;
    const preset = presetFor(key, "medium") || { level1: 0, level20: 0 };
    onChange([
      ...curves,
      {
        key,
        profile: "medium",
        ...preset,
      },
    ]);
  };
  return <section className="unit-subpanel unit-stat-curves">
    <header><div><h3>Curve livello 1 → 20</h3><small>Minimo e massimo sono valori finali esatti. Il profilo propone una coppia sensata, poi puoi personalizzarla.</small></div><button className="button secondary small" type="button" onClick={add}>Aggiungi variabile</button></header>
    <div className="unit-curve-list">
      <div className="unit-curve-head"><span>Variabile</span><span>Profilo</span><span>Lv 1</span><span>Lv 20</span><span /></div>
      {curves.map((entry, index) => <div className="unit-curve-row" key={`${entry.key}-${index}`}>
        <select aria-label="Variabile" value={entry.key} onChange={(event) => {
          const key = event.target.value;
          const preset = presetFor(key, entry.profile);
          update(index, { key, ...(preset || {}) });
        }}>{variables.map((variable) => <option key={variable.key} value={variable.key} disabled={curves.some((curve, row) => row !== index && curve.key === variable.key)}>{variable.label}</option>)}</select>
        <select aria-label="Profilo" value={entry.profile} onChange={(event) => {
          const profile = event.target.value as UnitStatCurve["profile"];
          const preset = presetFor(entry.key, profile);
          update(index, { profile, ...(preset || {}) });
        }}>{configuration.statCurveProfiles.map((profile) => <option key={profile.value} value={profile.value}>{profile.label}</option>)}</select>
        <input aria-label="Valore al livello 1" type="number" step="1" value={entry.level1} onChange={(event) => update(index, { level1: Number(event.target.value), profile: "custom" })} />
        <input aria-label="Valore al livello 20" type="number" step="1" value={entry.level20} onChange={(event) => update(index, { level20: Number(event.target.value), profile: "custom" })} />
        <button className="icon-button" type="button" aria-label={`Rimuovi ${entry.key}`} onClick={() => onChange(curves.filter((_, row) => row !== index))}>×</button>
      </div>)}
      {!curves.length && <p className="management-empty-inline">Aggiungi PF, PA, attributi, attacco, difesa e resistenze. Le variabili non configurate conservano le formule base.</p>}
    </div>
  </section>;
}

function PreviewPanel({
  draft,
  preview,
  pending,
  onPreview,
}: {
  draft: ManagedUnitDetail;
  preview: UnitGenerationPreview | null;
  pending: boolean;
  onPreview: (level: number, variant: string) => void;
}) {
  const [level, setLevel] = useState(1);
  const [variant, setVariant] = useState("standard");
  useEffect(() => setLevel(Math.max(1, Math.min(20, level))), [level]);
  const principal = ["pf", "mana", "energia", "potere", "pa", "attacco", "difesa", "forza", "resistenza", "velocita", "agilita", "tier", "rd_fis"];
  return <section className="unit-editor-section unit-preview-panel" data-component-type="panel" data-theme="combat">
    <header><div><p className="eyebrow">Generatore reale</p><h2>Anteprima senza salvataggio</h2><p>Usa esattamente lo stesso servizio della pagina Combattimento e annulla tutte le scritture al termine.</p></div></header>
    {!draft.id && <p className="form-warning">Salva prima la nuova Unit per provarla.</p>}
    <div className="unit-preview-controls"><label>Livello<select value={level} onChange={(event) => setLevel(Number(event.target.value))}>{Array.from({ length: 20 }, (_, index) => index + 1).map((option) => <option key={option} value={option}>Livello {option}</option>)}</select></label><label>Variante<input value={variant} onChange={(event) => setVariant(event.target.value)} /></label><button className="button primary" disabled={!draft.id || pending} onClick={() => onPreview(level, variant.trim() || "standard")}>{pending ? "Generazione…" : "Genera anteprima"}</button></div>
    {preview && <div className="unit-preview-result">
      <section><h3>{preview.name} · livello {preview.level}</h3><div className="unit-preview-stats">{principal.filter((key) => preview.totals[key] != null).map((key) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{preview.totals[key]}</strong></div>)}</div></section>
      <section><h3>Equipaggiamento</h3>{preview.equipment.length ? <ul>{preview.equipment.map((entry) => <li key={entry.slot}><strong>{entry.slot.replaceAll("_", " ")}</strong> {entry.name}</li>)}</ul> : <p>Nessuno, come previsto dal tipo.</p>}</section>
      <section><h3>Skill sbloccate</h3>{preview.skills.length ? <ul>{preview.skills.map((entry) => <li key={entry.id}><strong>{entry.name}</strong> · {entry.family}{entry.xpSpent ? ` · ${entry.xpSpent} PE` : ""}</li>)}</ul> : <p>Nessuna Skill.</p>}</section>
      <section><h3>Abilità innate</h3>{preview.innateActions.length ? <ul>{preview.innateActions.map((entry) => <li key={entry.key}><strong>{entry.name}</strong>{entry.description ? ` · ${entry.description}` : ""}</li>)}</ul> : <p>Nessuna abilità innata a questo livello.</p>}</section>
      <section><h3>Competenze</h3>{Object.keys(preview.competences).length ? <ul>{Object.entries(preview.competences).map(([key, value]) => <li key={key}><strong>{key.replaceAll("_", " ")}</strong> · {value.barra1}/{value.barra2}</li>)}</ul> : <p>Nessuna competenza.</p>}</section>
      <section><h3>Traccia</h3><p>{preview.trace.perks?.length || 0} perk · {preview.trace.xp?.earned || 0} PE Skill · {preview.trace.competences?.spent || 0} PE competenze spesi.</p>{preview.trace.warnings?.map((warning) => <p className="form-warning" key={warning}>{warning}</p>)}</section>
    </div>}
  </section>;
}

export function UnitManagementPage() {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<ManagedUnitDetail>(emptyUnit);
  const [tab, setTab] = useState<"profile" | "skills" | "equipment" | "preview">("profile");
  const [filter, setFilter] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [preview, setPreview] = useState<UnitGenerationPreview | null>(null);

  const overviewQuery = useQuery({
    queryKey: ["management-units"],
    queryFn: () => getData<UnitManagementOverview>("/api/v1/management/units"),
  });
  const detailQuery = useQuery({
    queryKey: ["management-unit", selectedId],
    queryFn: () => getData<ManagedUnitDetail>(`/api/v1/management/units/${selectedId}`),
    enabled: selectedId != null,
  });
  useEffect(() => {
    if (detailQuery.data) {
      setDraft(cloneUnit(detailQuery.data));
      setDirty(false);
      setPreview(null);
    }
  }, [detailQuery.data]);
  const setEditedDraft: Dispatch<SetStateAction<ManagedUnitDetail>> = (next) => {
    setDraft(next);
    setDirty(true);
  };
  const saveMutation = useMutation({
    mutationFn: () => command<UnitActionData>("management.units.save", { unitId: draft.id, values: draft }, "management-units"),
    onSuccess: async (response) => {
      const saved = response.data.management?.unit;
      if (saved) {
        setDraft(cloneUnit(saved));
        setSelectedId(saved.id);
        setDirty(false);
      }
      await queryClient.invalidateQueries({ queryKey: ["management-units"] });
      await queryClient.invalidateQueries({ queryKey: ["management-unit"] });
      notify(response.data.management?.created ? "Unit creata e pronta per Combattimento." : "Unit aggiornata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const stateMutation = useMutation({
    mutationFn: (archived: boolean) => command<UnitActionData>("management.units.state", { unitId: draft.id, archived }, "management-units"),
    onSuccess: async (_, archived) => {
      await queryClient.invalidateQueries({ queryKey: ["management-units"] });
      await queryClient.invalidateQueries({ queryKey: ["management-unit", draft.id] });
      notify(archived ? "Unit archiviata." : "Unit ripristinata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const previewMutation = useMutation({
    mutationFn: ({ level, variant }: { level: number; variant: string }) => command<UnitActionData>("management.units.preview", { unitId: draft.id, level, variant }, "management-units"),
    onSuccess: (response) => {
      setPreview(response.data.management?.preview || null);
      notify("Anteprima completata senza creare personaggi.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const overview = overviewQuery.data;
  const normalizedFilter = filter.trim().toLocaleLowerCase("it");
  const units = useMemo(() => (overview?.units || []).filter((unit) => {
    const searchable = `${unit.name} ${unit.category} ${unit.generationKindLabel}`.toLocaleLowerCase("it");
    return (includeArchived || !unit.archived) && (!normalizedFilter || searchable.includes(normalizedFilter));
  }), [overview, includeArchived, normalizedFilter]);
  useEffect(() => {
    if (selectedId == null && units.length && !dirty) setSelectedId(units[0].id);
  }, [units, selectedId, dirty]);

  const changeKind = (kind: ManagedUnitDetail["generation"]["kind"]) => setEditedDraft((current) => ({
    ...current,
    generation: {
      ...current.generation,
      kind,
      coreKey: kind === "humanoid" ? (current.generation.coreKey || "warrior") : "",
      allowedRaces: kind === "humanoid" ? current.generation.allowedRaces : [],
    },
    skillUnlocks: kind === "humanoid" ? current.skillUnlocks : [],
    equipmentSlots: kind === "humanoid" ? current.equipmentSlots : [],
    equipmentGroups: kind === "humanoid" ? current.equipmentGroups : [],
    accessoryCountByLevel: kind === "humanoid" ? current.accessoryCountByLevel : [],
    competenceProfile: kind === "humanoid" ? current.competenceProfile : {},
    innateActions: kind === "humanoid" ? [] : current.innateActions,
    statProfile: kind === "humanoid"
      ? { ...current.statProfile, curves: [] }
      : current.statProfile,
  }));
  const canSave = Boolean(draft.name.trim() && draft.generation.kind && !saveMutation.isPending);

  return <div className="page management-page unit-management-page">
    <header className="page-header"><div><p className="eyebrow">Gestione del gioco</p><h1>Gestione Unit</h1><p>Autore, valida e prova gli archetipi usati da Unità rapide in Combattimento.</p></div><div className="button-row"><Link className="button secondary" to="/tools">Tutti gli strumenti</Link><button className="button primary" onClick={() => { setSelectedId(null); setDraft(emptyUnit()); setDirty(true); setPreview(null); setTab("profile"); }}>Nuova Unit</button></div></header>
    <section className="panel unit-generation-guide" data-component-type="guide" data-theme="parchment">
      <h2>Come viene creato il personaggio importato</h2>
      <p>Per un Umanoide il generatore parte dal livello 1 e ripercorre ogni livello fino a quello richiesto. Accredita i PE, sceglie Skill coerenti fra Core e archetipo, verifica prezzi dinamici e prerequisiti con gli stessi servizi della scheda, applica i passivi e prova nuovamente a spendere i PE rimasti. Il Core dovrebbe contenere bonus generali e passivi; gli attacchi identitari appartengono all’archetipo. I perk seguono di default la progressione dell’AI di Elder Django.</p>
      <p>Competenze ed equipaggiamento sono costruiti dai profili della Unit e dalla fascia di livello. Armi e armature rispettano i percorsi materiale leggero o pesante, le sovrapposizioni e il tier massimo dichiarati; gli accessori possono usare un totale variabile per livello, garantendo categorie come anelli e orecchini tramite i minimi dei gruppi. Una generazione automatica usa ogni volta una variante nuova, mentre una Variante scritta a mano riproduce esattamente le stesse scelte.</p>
      <p>Animali e Creature seguono un contratto diverso: non acquistano Skill, perk, Competenze o equipaggiamento umanoide. Ricevono invece le curve statistiche e le azioni innate configurate per il livello. In entrambi i casi il personaggio creato è un record completo e indipendente; il resoconto conservato nei metadati indica seed, PE guadagnati e residui, Skill, perk, miglioramenti, oggetti e avvisi.</p>
    </section>
    {overviewQuery.isLoading && <section className="panel"><p>Caricamento Unit…</p></section>}
    {overviewQuery.error && <section className="panel danger-panel"><p>{(overviewQuery.error as Error).message}</p></section>}
    {overview && <div className="unit-management-layout">
      <aside className="panel unit-management-list" data-component-type="list" data-theme="dark">
        <header><label>Cerca<input type="search" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Nome, razza, categoria…" /></label><label className="inline-check"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} /> Archiviati</label></header>
        <strong>{units.length} Unit</strong>
        <div>{units.map((unit) => <button key={unit.id} className={selectedId === unit.id ? "active" : ""} data-state={unit.archived ? "archived" : unit.ready ? "ready" : "invalid"} onClick={() => {
          if (dirty && !window.confirm("Scartare le modifiche non salvate?")) return;
          setSelectedId(unit.id);
          setDirty(false);
          setPreview(null);
        }}><span><strong>{unit.name}</strong><small>{unit.generationKindLabel}{unit.coreLabel ? ` · ${unit.coreLabel}` : ""}</small></span><b>{unit.ready ? "Pronta" : "Da completare"}</b></button>)}</div>
      </aside>
      <main className="unit-management-editor">
        {detailQuery.isFetching && selectedId && <section className="panel"><p>Caricamento profilo…</p></section>}
        <nav className="management-mode-tabs unit-editor-tabs" role="tablist" aria-label="Sezioni Gestione Unit">
          <button role="tab" aria-selected={tab === "profile"} className={tab === "profile" ? "active" : ""} onClick={() => setTab("profile")}>Profilo</button>
          <button role="tab" aria-selected={tab === "skills"} className={tab === "skills" ? "active" : ""} onClick={() => setTab("skills")}>Progressione</button>
          <button role="tab" aria-selected={tab === "equipment"} className={tab === "equipment" ? "active" : ""} onClick={() => setTab("equipment")}>Equipaggiamento</button>
          <button role="tab" aria-selected={tab === "preview"} className={tab === "preview" ? "active" : ""} onClick={() => setTab("preview")}>Anteprima</button>
        </nav>
        {tab === "profile" && <>
          <section className="unit-editor-section" data-component-type="form" data-theme="parchment">
            <header><div><p className="eyebrow">{draft.id ? `Unit #${draft.id}` : "Nuova Unit"}{draft.archived ? " · archiviata" : ""}</p><h2>Identità e contratto</h2></div>{draft.metadata.sourceProject === "the_elder_django" && <span className="source-badge">Elder · {Array.isArray(draft.metadata.sourceIds) ? draft.metadata.sourceIds.join(", ") : ""}</span>}</header>
            <div className="unit-form-grid">
              <label>Nome<input value={draft.name} onChange={(event) => setEditedDraft((current) => ({ ...current, name: event.target.value }))} /></label>
              <label>Tipo<select value={draft.generation.kind} onChange={(event) => changeKind(event.target.value as ManagedUnitDetail["generation"]["kind"])}>{overview.configuration.kinds.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>
              <label>Categoria<input value={draft.category} onChange={(event) => setEditedDraft((current) => ({ ...current, category: event.target.value }))} placeholder="Banditi, Animali, Daedra…" /></label>
              {draft.generation.kind === "humanoid" && <label>Core<select value={draft.generation.coreKey} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, coreKey: event.target.value } }))}>{overview.configuration.cores.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>}
              {draft.generation.kind === "humanoid" && <label className="wide">Razze disponibili<select multiple size={6} value={draft.generation.allowedRaces} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, allowedRaces: Array.from(event.target.selectedOptions, (option) => option.value) } }))}>{overview.configuration.races.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select><small>Nessuna selezione = tutte le razze, estratte casualmente.</small></label>}
              <label className="wide">Descrizione dell'archetipo<textarea rows={3} value={draft.archetypeDescription} onChange={(event) => setEditedDraft((current) => ({ ...current, archetypeDescription: event.target.value }))} /></label>
              <label className="wide">Lore<textarea rows={5} value={draft.loreDescription} onChange={(event) => setEditedDraft((current) => ({ ...current, loreDescription: event.target.value }))} /></label>
              <label className="wide">Note di authoring<textarea rows={3} value={draft.notes} onChange={(event) => setEditedDraft((current) => ({ ...current, notes: event.target.value }))} /></label>
            </div>
          </section>
          {draft.generation.kind === "humanoid" && <section className="unit-editor-section" data-component-type="form" data-theme="arcane">
            <header><div><p className="eyebrow">Affinità firmate</p><h2>Profilo archetipo</h2><p>Da −5 a +5. I valori negativi penalizzano; non diventano affinità accidentali.</p></div></header>
            <div className="unit-tag-grid">{overview.configuration.tags.map((tag) => <label key={tag.key}><span>{tag.label}<b>{draft.archetypeTags[tag.key] ?? 0}</b></span><input type="range" min={tag.minimum} max={tag.maximum} value={draft.archetypeTags[tag.key] ?? 0} onChange={(event) => setEditedDraft((current) => ({ ...current, archetypeTags: { ...current.archetypeTags, [tag.key]: Number(event.target.value) } }))} /></label>)}</div>
          </section>}
          {draft.generation.kind === "humanoid" && <section className="unit-editor-section" data-component-type="form" data-theme="default">
            <header><div><p className="eyebrow">PE abilità</p><h2>Profilo competenze</h2><p>−5 esclude; +5 privilegia. Il generatore spende i PE con costo triangolare e seed riproducibile.</p></div></header>
            <div className="unit-competence-grid">{overview.configuration.competences.map((entry) => <label key={entry.key}><span>{entry.label}<b>{draft.competenceProfile[entry.key] ?? 0}</b></span><input type="range" min="-5" max="5" value={draft.competenceProfile[entry.key] ?? 0} onChange={(event) => setEditedDraft((current) => ({ ...current, competenceProfile: { ...current.competenceProfile, [entry.key]: Number(event.target.value) } }))} /></label>)}</div>
          </section>}
          <section className="unit-editor-section" data-component-type="form" data-theme="default">
            <header><div><p className="eyebrow">Chassis</p><h2>Statistiche deterministiche</h2><p>Gli umanoidi crescono tramite Skill salvo esplicita eccezione. Animali e Creature possono scalare fisicamente per livello.</p></div></header>
            {draft.generation.kind === "humanoid" ? <>
              <div className="unit-stat-editors"><ModifierEditor title="Base" values={draft.statProfile.baseModifiers || {}} onChange={(values) => setEditedDraft((current) => ({ ...current, statProfile: { ...current.statProfile, baseModifiers: values } }))} /><ModifierEditor title="Per livello" values={draft.statProfile.perLevelModifiers || {}} onChange={(values) => setEditedDraft((current) => ({ ...current, statProfile: { ...current.statProfile, perLevelModifiers: values } }))} /></div>
              <label className="inline-check"><input type="checkbox" checked={draft.generation.allowHumanoidStatGrowth} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, allowHumanoidStatGrowth: event.target.checked } }))} /> Consenti eccezionalmente crescita statistica diretta all'umanoide</label>
            </> : <>
              <StatCurveEditor curves={draft.statProfile.curves || []} configuration={overview.configuration} onChange={(curves) => setEditedDraft((current) => ({ ...current, statProfile: { ...current.statProfile, curves } }))} />
              <ActionEditor actions={draft.innateActions} onChange={(actions) => setEditedDraft((current) => ({ ...current, innateActions: actions }))} />
              <p className="contract-callout">Contratto non umanoide: nessuna Skill a PE, competenza o equipaggiamento. Le abilità innate e le curve statistiche sono invece configurabili qui.</p>
            </>}
          </section>
        </>}
        {tab === "skills" && (draft.generation.kind === "humanoid" ? <>
          <section className="unit-editor-section" data-component-type="form" data-theme="default">
            <header><div><p className="eyebrow">Regole di livello</p><h2>Budget e vincoli</h2></div></header>
            <div className="unit-form-grid">
              <label>Quota Core<input type="number" min="0.1" max="0.9" step="0.05" value={draft.generation.coreShare} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, coreShare: Number(event.target.value) } }))} /></label>
              <label>PE iniziali<input type="number" min="0" value={draft.generation.startingXp} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, startingXp: Number(event.target.value) } }))} /></label>
              <label>PE base per livello<input type="number" min="0" value={draft.generation.xpBase} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, xpBase: Number(event.target.value) } }))} /></label>
              <label>Crescita PE<input type="number" min="0" value={draft.generation.xpGrowth} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, xpGrowth: Number(event.target.value) } }))} /></label>
              <label>PE competenze iniziali<input type="number" min="0" value={draft.generation.competenceStartingXp} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, competenceStartingXp: Number(event.target.value) } }))} /></label>
              <label>PE competenze per livello<input type="number" min="0" value={draft.generation.competenceXpBase} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, competenceXpBase: Number(event.target.value) } }))} /></label>
              <label>Passaggi PE residui<input type="number" min="0" max="20" value={draft.generation.finalSpendingPasses} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, finalSpendingPasses: Number(event.target.value) } }))} /></label>
              <label>Magia<select value={draft.generation.magicPolicy} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, magicPolicy: event.target.value as "none" | "any" } }))}>{overview.configuration.magicPolicies.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>
              <label className="wide">Famiglie Classe consentite<select multiple value={draft.generation.allowedClassFamilies} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, allowedClassFamilies: Array.from(event.target.selectedOptions, (option) => option.value) } }))}>{overview.configuration.classFamilies.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select><small>Vuoto = nessuna Classe. Usa Ctrl/Cmd per selezionare più famiglie.</small></label>
              <label className="wide">Famiglie Religione consentite<select multiple value={draft.generation.allowedReligionFamilies} onChange={(event) => setEditedDraft((current) => ({ ...current, generation: { ...current.generation, allowedReligionFamilies: Array.from(event.target.selectedOptions, (option) => option.value) } }))}>{overview.configuration.religionFamilies.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select><small>Vuoto = nessuna Religione. Usa Ctrl/Cmd per selezionare più famiglie.</small></label>
            </div>
            <p className="contract-callout">Le Skill acquistabili sono curate esplicitamente per ogni Unit. A ogni livello la progressione perk combina automaticamente, con pari probabilità, una tappa caratteristica e una scelta coerente con i pesi dell'Unit.</p>
          </section>
          <SkillPoolEditor draft={draft} setDraft={setEditedDraft} />
        </> : <section className="unit-editor-section" data-component-type="panel" data-theme="muted"><h2>Nessuna progressione Skill a PE</h2><p>Animali e Creature usano le abilità innate e le curve configurate nel Profilo, non il catalogo Skill umanoide.</p></section>)}
        {tab === "equipment" && (draft.generation.kind === "humanoid" ? <EquipmentEditor draft={draft} setDraft={setEditedDraft} configuration={overview.configuration} /> : <section className="unit-editor-section" data-component-type="panel" data-theme="muted"><h2>Nessun equipaggiamento</h2><p>Il contratto di Animali e Creature blocca ogni pool equipaggiamento.</p></section>)}
        {tab === "preview" && <PreviewPanel draft={draft} preview={preview} pending={previewMutation.isPending} onPreview={(level, variant) => previewMutation.mutate({ level, variant })} />}
        <div className="sticky-actions unit-editor-actions">
          <span>{dirty ? "Modifiche non salvate" : draft.id ? "Profilo salvato" : "Nuova Unit"}</span>
          {draft.id && <button className={draft.archived ? "button secondary" : "button danger"} type="button" disabled={stateMutation.isPending} onClick={() => {
            const action = draft.archived ? "ripristinare" : "archiviare";
            if (window.confirm(`${action[0].toUpperCase()}${action.slice(1)} ${draft.name}?`)) stateMutation.mutate(!draft.archived);
          }}>{draft.archived ? "Ripristina" : "Archivia"}</button>}
          <button className="button primary" type="button" disabled={!canSave} onClick={() => saveMutation.mutate()}>{saveMutation.isPending ? "Salvataggio…" : draft.id ? "Salva modifiche" : "Crea Unit"}</button>
        </div>
      </main>
    </div>}
  </div>;
}

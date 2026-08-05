import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getData } from "../../lib/api";
import type {
  UnitItemOption,
  UnitManagementOverview,
  UnitSkillOption,
} from "../management/types";
import type { AIChangeField, AIChangeProblem } from "./types";

type Props = {
  fields: AIChangeField[];
  values: Record<string, unknown>;
  errors: AIChangeProblem[];
  disabled: boolean;
  onChange: (name: string, value: unknown) => void;
};

type Configuration = UnitManagementOverview["configuration"];
type JsonValue = Record<string, unknown> | unknown[] | null;

const asObject = (value: unknown): Record<string, any> => value && typeof value === "object" && !Array.isArray(value)
  ? value as Record<string, any>
  : {};
const asArray = <T,>(value: unknown): T[] => Array.isArray(value) ? value as T[] : [];
const numberValue = (value: unknown, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;

function JsonEditor({ label, value, disabled, onChange, rows = 7, help }: {
  label: string;
  value: JsonValue;
  disabled: boolean;
  onChange: (value: JsonValue) => void;
  rows?: number;
  help?: string;
}) {
  const formatted = useMemo(() => JSON.stringify(value ?? {}, null, 2), [value]);
  const [text, setText] = useState(formatted);
  const [error, setError] = useState("");
  return <label className="master-ai-field full structured">
    <span><strong>{label}</strong><small>JSON avanzato</small></span>
    <textarea rows={rows} value={text} disabled={disabled} onFocus={() => {
      if (text !== formatted) return;
      setText(formatted);
    }} onChange={(event) => {
      const next = event.target.value;
      setText(next);
      try {
        const parsed = JSON.parse(next) as JsonValue;
        setError("");
        onChange(parsed);
      } catch {
        setError("JSON non valido.");
      }
    }} />
    {help && <small>{help}</small>}
    {error && <small className="form-error" role="alert">{error}</small>}
  </label>;
}

function OptionSearch<T extends UnitSkillOption | UnitItemOption>({ kind, disabled, onChoose }: {
  kind: "skill" | "item";
  disabled: boolean;
  onChoose: (entry: T) => void;
}) {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const result = useQuery({
    queryKey: ["master-ai-unit-option", kind, query],
    queryFn: () => getData<{ kind: string; options: T[] }>(
      `/api/v1/management/units/options?kind=${kind}&query=${encodeURIComponent(query)}&limit=200`,
    ),
    enabled: query.length >= 2,
  });
  return <div className="unit-option-picker" data-component-type="panel" data-theme="muted">
    <form onSubmit={(event) => { event.preventDefault(); setQuery(input.trim()); }}>
      <label>{kind === "skill" ? "Cerca Skill" : "Cerca oggetto"}<input value={input} disabled={disabled} onChange={(event) => setInput(event.target.value)} placeholder="Almeno due caratteri…" /></label>
      <button type="submit" className="button secondary small" disabled={disabled || input.trim().length < 2}>Cerca</button>
    </form>
    {result.isFetching && <small>Ricerca…</small>}
    {result.error && <small className="form-error">{(result.error as Error).message}</small>}
    {result.data && <div className="unit-option-results">
      {result.data.options.map((entry) => <button key={entry.id} type="button" disabled={disabled} onClick={() => onChoose(entry)}>
        <strong>{entry.name}</strong>
        <small>{"family" in entry
          ? `${entry.group} · ${entry.family} · ${entry.baseXpCost} PE`
          : `${entry.types.join(" / ") || "Senza tipo"}${entry.rarity == null ? "" : ` · rarità ${entry.rarity}`}`}</small>
      </button>)}
      {!result.data.options.length && <small>Nessun risultato.</small>}
    </div>}
  </div>;
}

function MultiSelect({ label, values, choices, disabled, onChange, help }: {
  label: string;
  values: string[];
  choices: Array<{ value: string; label: string }>;
  disabled: boolean;
  onChange: (values: string[]) => void;
  help?: string;
}) {
  return <label className="master-ai-field full">
    <span><strong>{label}</strong></span>
    <select multiple size={Math.min(8, Math.max(4, choices.length))} value={values} disabled={disabled} onChange={(event) => onChange(Array.from(event.target.selectedOptions, (option) => option.value))}>
      {choices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
    </select>
    {help && <small>{help}</small>}
  </label>;
}

function AuditPanel({ audit }: { audit: Record<string, any> }) {
  if (!audit.passed) return <section className="unit-editor-section" data-theme="muted"><h3>Audit non ancora disponibile</h3><p>Salva la bozza per eseguire le anteprime rollback-only.</p></section>;
  const named = asArray<Record<string, any>>(audit.named);
  const repeats = asArray<Record<string, any>>(audit.repeatability);
  const automatic = asArray<Record<string, any>>(audit.automatic);
  return <section className="unit-editor-section master-ai-unit-audit" data-component-type="panel" data-theme={audit.warningCount ? "gold" : "default"}>
    <header><div><p className="eyebrow">Generatore reale</p><h3>Audit Unit superato</h3><p>Le anteprime sono state create dentro transazioni annullate; nessun personaggio di prova rimane salvato.</p></div><strong>{audit.warningCount || 0} avvisi</strong></header>
    <div className="master-ai-unit-audit-grid">
      {named.map((row) => <article key={row.level}>
        <strong>Livello {row.level}</strong>
        <span>{row.skills} Skill · {row.perks} Perk</span>
        <span>{row.equipment} oggetti · {row.innateActions} azioni</span>
        <small>{asArray(row.warnings).length ? `${asArray(row.warnings).length} avvisi trace` : "Trace pulita"}</small>
      </article>)}
    </div>
    <div className="master-ai-unit-audit-summary">
      <span><strong>Ripetibilità</strong>{repeats.every((row) => row.stable) ? "Varianti nominate stabili" : "Instabilità rilevata"}</span>
      <span><strong>Varianti automatiche</strong>{automatic.map((row) => `L${row.level}: ${row.unique}/${row.variants}`).join(" · ")}</span>
      <span><strong>Livelli verificati</strong>{asArray(audit.levels).join(", ")}</span>
    </div>
  </section>;
}

export function UnitProposalEditor({ fields, values, errors, disabled, onChange }: Props) {
  const rootField = fields.find((field) => field.ui.widget === "unitDefinition");
  const configuration = (rootField?.ui.configuration || {}) as Configuration;
  const generation = asObject(values.generation);
  const kind = String(generation.kind || "humanoid");
  const tags = asObject(values.archetypeTags);
  const competences = asObject(values.competenceProfile);
  const skills = asArray<Record<string, any>>(values.skillUnlocks);
  const equipment = asArray<Record<string, any>>(values.equipmentSlots);
  const groups = asArray<Record<string, any>>(values.equipmentGroups);
  const accessoryBands = asArray<Record<string, any>>(values.accessoryCountByLevel);
  const statProfile = asObject(values.statProfile);
  const curves = asArray<Record<string, any>>(statProfile.curves);
  const actions = asArray<Record<string, any>>(values.innateActions);
  const audit = asObject(values.auditPreview);
  const portraitField = fields.find((field) => field.name === "loreImageId");
  const errorFor = (name: string) => errors.find((error) => error.field === name || error.field?.startsWith(`${name}.`) || error.field?.endsWith(`.${name}`));

  const setGeneration = (name: string, value: unknown) => onChange("generation", { ...generation, [name]: value });
  const updateSkill = (index: number, patch: Record<string, unknown>) => onChange("skillUnlocks", skills.map((entry, row) => row === index ? { ...entry, ...patch } : entry));
  const updateEquipment = (index: number, patch: Record<string, unknown>) => onChange("equipmentSlots", equipment.map((entry, row) => row === index ? { ...entry, ...patch } : entry));
  const updateCurve = (index: number, patch: Record<string, unknown>) => onChange("statProfile", { ...statProfile, curves: curves.map((entry, row) => row === index ? { ...entry, ...patch } : entry) });
  const updateAction = (index: number, patch: Record<string, unknown>) => onChange("innateActions", actions.map((entry, row) => row === index ? { ...entry, ...patch } : entry));

  const selectedRaces = asArray<string>(generation.allowedRaces);
  const subraceChoices = asArray<Configuration["races"][number]>(configuration.races)
    .filter((race) => selectedRaces.includes(race.value))
    .flatMap((race) => race.subraces.map((entry) => ({ value: entry.value, label: `${race.label} · ${entry.label}` })));

  return <div className="master-ai-unit-editor">
    <section className="unit-editor-section" data-component-type="form" data-theme="parchment">
      <header><div><p className="eyebrow">Unit proposta</p><h2>Identità e contratto</h2><p>{rootField?.help}</p></div></header>
      <div className="unit-form-grid">
        <label>Nome<input value={String(values.name || "")} disabled={disabled} onChange={(event) => onChange("name", event.target.value)} />{errorFor("name") && <small className="form-error">{errorFor("name")?.message}</small>}</label>
        <label>Categoria<input value={String(values.category || "")} disabled={disabled} onChange={(event) => onChange("category", event.target.value)} /></label>
        <label>Contratto<select value={kind} disabled={disabled} onChange={(event) => {
          const nextKind = event.target.value;
          setGeneration("kind", nextKind);
          if (nextKind === "creature") {
            onChange("skillUnlocks", []);
            onChange("equipmentSlots", []);
            onChange("equipmentGroups", []);
            onChange("accessoryCountByLevel", []);
            onChange("accessoryProfileKey", "");
            onChange("competenceProfile", {});
          } else {
            onChange("innateActions", []);
          }
        }}>{asArray<Configuration["kinds"][number]>(configuration.kinds).map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>
        <label>Ritratto<select value={values.loreImageId == null ? "" : String(values.loreImageId)} disabled={disabled} onChange={(event) => onChange("loreImageId", event.target.value ? Number(event.target.value) : null)}><option value="">— Nessuno —</option>{portraitField?.choices.map((entry) => <option key={String(entry.value)} value={String(entry.value)}>{entry.label}</option>)}</select></label>
        <label className="wide">Descrizione archetipo<textarea rows={4} value={String(values.archetypeDescription || "")} disabled={disabled} onChange={(event) => onChange("archetypeDescription", event.target.value)} /></label>
        <label className="wide">Lore<textarea rows={5} value={String(values.loreDescription || "")} disabled={disabled} onChange={(event) => onChange("loreDescription", event.target.value)} /></label>
        <label className="wide">Note di authoring<textarea rows={5} value={String(values.notes || "")} disabled={disabled} onChange={(event) => onChange("notes", event.target.value)} /><small>Annotare fonti, query, ID scelti, alternative escluse, regole manuali e risultato dell'audit.</small></label>
      </div>
    </section>

    <section className="unit-editor-section" data-component-type="form" data-theme="default">
      <header><div><p className="eyebrow">Progressione</p><h2>Regole di generazione</h2></div></header>
      <div className="unit-form-grid">
        {kind === "humanoid" && <label>Core<select value={String(generation.coreKey || "")} disabled={disabled} onChange={(event) => setGeneration("coreKey", event.target.value)}>{asArray<Configuration["cores"][number]>(configuration.cores).map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>}
        <label>Quota Core<input type="number" min="0.1" max="0.9" step="0.05" value={numberValue(generation.coreShare, 0.5)} disabled={disabled} onChange={(event) => setGeneration("coreShare", Number(event.target.value))} /></label>
        <label>PE iniziali<input type="number" min="0" value={numberValue(generation.startingXp)} disabled={disabled} onChange={(event) => setGeneration("startingXp", Number(event.target.value))} /></label>
        <label>PE base<input type="number" min="0" value={numberValue(generation.xpBase, 20)} disabled={disabled} onChange={(event) => setGeneration("xpBase", Number(event.target.value))} /></label>
        <label>Crescita PE<input type="number" min="0" value={numberValue(generation.xpGrowth, 1)} disabled={disabled} onChange={(event) => setGeneration("xpGrowth", Number(event.target.value))} /></label>
        <label>PE competenze iniziali<input type="number" min="0" value={numberValue(generation.competenceStartingXp, 5)} disabled={disabled} onChange={(event) => setGeneration("competenceStartingXp", Number(event.target.value))} /></label>
        <label>PE competenze base<input type="number" min="0" value={numberValue(generation.competenceXpBase, 15)} disabled={disabled} onChange={(event) => setGeneration("competenceXpBase", Number(event.target.value))} /></label>
        <label>Crescita competenze<input type="number" min="0" value={numberValue(generation.competenceXpGrowth)} disabled={disabled} onChange={(event) => setGeneration("competenceXpGrowth", Number(event.target.value))} /></label>
        <label>Passaggi finali<input type="number" min="0" max="20" value={numberValue(generation.finalSpendingPasses, 4)} disabled={disabled} onChange={(event) => setGeneration("finalSpendingPasses", Number(event.target.value))} /></label>
        <label>Magia<select value={String(generation.magicPolicy || "any")} disabled={disabled} onChange={(event) => setGeneration("magicPolicy", event.target.value)}>{asArray<Configuration["magicPolicies"][number]>(configuration.magicPolicies).map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>
        {kind === "humanoid" && <label className="inline-check wide"><input type="checkbox" checked={Boolean(generation.allowHumanoidStatGrowth)} disabled={disabled} onChange={(event) => setGeneration("allowHumanoidStatGrowth", event.target.checked)} /> Consenti crescita statistica diretta eccezionale</label>}
      </div>
      {kind === "humanoid" && <div className="unit-form-grid">
        <MultiSelect label="Famiglie Classe consentite" values={asArray(generation.allowedClassFamilies)} choices={asArray(configuration.classFamilies)} disabled={disabled} onChange={(next) => setGeneration("allowedClassFamilies", next)} help="Vuoto significa nessuna Classe consentita dal contenuto Unit." />
        <MultiSelect label="Famiglie Religione consentite" values={asArray(generation.allowedReligionFamilies)} choices={asArray(configuration.religionFamilies)} disabled={disabled} onChange={(next) => setGeneration("allowedReligionFamilies", next)} help="Ogni Skill Religione richiede una famiglia esplicita." />
        <MultiSelect label="Razze consentite" values={selectedRaces} choices={asArray(configuration.races).map((entry: any) => ({ value: entry.value, label: entry.label }))} disabled={disabled} onChange={(next) => { setGeneration("allowedRaces", next); setGeneration("allowedSubraces", []); }} help="Vuoto significa tutte le razze correnti." />
        <MultiSelect label="Sottorazze consentite" values={asArray(generation.allowedSubraces)} choices={subraceChoices} disabled={disabled} onChange={(next) => setGeneration("allowedSubraces", next)} />
      </div>}
    </section>

    {kind === "humanoid" && <>
      <section className="unit-editor-section" data-component-type="form" data-theme="arcane">
        <header><div><p className="eyebrow">Affinità firmate</p><h2>Tag e competenze</h2></div></header>
        <div className="unit-tag-grid">{asArray<Configuration["tags"][number]>(configuration.tags).map((tag) => <label key={tag.key}><span>{tag.label}<b>{numberValue(tags[tag.key])}</b></span><input type="range" min={tag.minimum} max={tag.maximum} value={numberValue(tags[tag.key])} disabled={disabled} onChange={(event) => onChange("archetypeTags", { ...tags, [tag.key]: Number(event.target.value) })} /></label>)}</div>
        <h3>Competenze</h3>
        <div className="unit-competence-grid">{asArray<Configuration["competences"][number]>(configuration.competences).map((entry) => <label key={entry.key}><span>{entry.label}<b>{numberValue(competences[entry.key])}</b></span><input type="range" min="-5" max="5" value={numberValue(competences[entry.key])} disabled={disabled} onChange={(event) => onChange("competenceProfile", { ...competences, [entry.key]: Number(event.target.value) })} /></label>)}</div>
      </section>

      <section className="unit-editor-section" data-component-type="panel" data-theme="arcane">
        <header><div><p className="eyebrow">Catalogo vivo</p><h2>Pool Skill</h2><p>Servono almeno una Skill Core e una Archetipo realmente acquistabili; l'audit verifica la generazione fino al livello 20.</p></div></header>
        <OptionSearch<UnitSkillOption> kind="skill" disabled={disabled} onChoose={(skill) => {
          if (skills.some((entry) => Number(entry.skillId) === skill.id)) return;
          onChange("skillUnlocks", [...skills, { skillId: skill.id, skillName: skill.name, family: skill.family, group: skill.group, pool: skill.isPerk ? "minor" : "archetype", weight: 5, minLevel: 1, maxLevel: 20 }]);
        }} />
        <div className="unit-pool-table">
          <div className="unit-pool-head"><span>Skill</span><span>Pool</span><span>Livelli</span><span>Peso</span><span>Obbligo</span><span /></div>
          {skills.map((entry, index) => <div className="unit-pool-row" key={`${entry.skillId}-${index}`}>
            <span><strong>{entry.skillName || `Skill #${entry.skillId}`}</strong><small>{entry.group || ""} {entry.family || ""}</small></span>
            <select value={String(entry.pool || "archetype")} disabled={disabled} onChange={(event) => updateSkill(index, { pool: event.target.value })}><option value="core">Core</option><option value="archetype">Archetipo</option><option value="minor">Perk minore</option><option value="major">Perk maggiore</option></select>
            <span className="range-pair"><input type="number" min="1" max="20" value={numberValue(entry.minLevel, 1)} disabled={disabled} onChange={(event) => updateSkill(index, { minLevel: Number(event.target.value) })} /><b>–</b><input type="number" min="1" max="20" value={numberValue(entry.maxLevel, 20)} disabled={disabled} onChange={(event) => updateSkill(index, { maxLevel: Number(event.target.value) })} /></span>
            <input type="number" min="0.1" max="100" step="0.1" value={numberValue(entry.weight, 1)} disabled={disabled} onChange={(event) => updateSkill(index, { weight: Number(event.target.value) })} />
            <input type="number" min="1" max="20" value={entry.requiredAtLevel ?? ""} disabled={disabled} onChange={(event) => updateSkill(index, { requiredAtLevel: event.target.value ? Number(event.target.value) : undefined })} />
            <button type="button" className="icon-button" disabled={disabled} onClick={() => onChange("skillUnlocks", skills.filter((_item, row) => row !== index))}>×</button>
          </div>)}
          {!skills.length && <p className="management-empty-inline">Nessuna Skill selezionata.</p>}
        </div>
      </section>

      <section className="unit-editor-section" data-component-type="panel" data-theme="gold">
        <header><div><p className="eyebrow">Slot e accessori</p><h2>Equipaggiamento</h2></div></header>
        <label className="master-ai-field full"><span><strong>Profilo accessori condiviso</strong></span><select value={String(values.accessoryProfileKey || "")} disabled={disabled} onChange={(event) => onChange("accessoryProfileKey", event.target.value)}><option value="">— Nessuno —</option>{asArray<Configuration["accessoryProfiles"][number]>(configuration.accessoryProfiles).map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>
        <OptionSearch<UnitItemOption> kind="item" disabled={disabled} onChoose={(item) => onChange("equipmentSlots", [...equipment, { slot: configuration.equipmentSlots?.[0]?.value || "arma", itemId: item.id, itemName: item.name, minLevel: 1, maxLevel: 20, weight: 1, chance: 1 }])} />
        <div className="unit-item-rows">{equipment.map((entry, index) => <div key={`${entry.slot}-${entry.itemId}-${index}`}>
          <span><strong>{entry.itemName || `Oggetto #${entry.itemId}`}</strong><small>#{entry.itemId}</small></span>
          <select value={String(entry.slot || "")} disabled={disabled} onChange={(event) => updateEquipment(index, { slot: event.target.value })}>{asArray<Configuration["equipmentSlots"][number]>(configuration.equipmentSlots).map((slot) => <option key={slot.value} value={slot.value}>{slot.label}</option>)}</select>
          <span className="range-pair"><input type="number" min="1" max="20" value={numberValue(entry.minLevel, 1)} disabled={disabled} onChange={(event) => updateEquipment(index, { minLevel: Number(event.target.value) })} /><b>–</b><input type="number" min="1" max="20" value={numberValue(entry.maxLevel, 20)} disabled={disabled} onChange={(event) => updateEquipment(index, { maxLevel: Number(event.target.value) })} /></span>
          <input type="number" min="0.1" max="100" step="0.1" value={numberValue(entry.weight, 1)} disabled={disabled} onChange={(event) => updateEquipment(index, { weight: Number(event.target.value) })} />
          <input type="number" min="0" max="1" step="0.05" value={numberValue(entry.chance, 1)} disabled={disabled} onChange={(event) => updateEquipment(index, { chance: Number(event.target.value) })} />
          <button type="button" className="icon-button" disabled={disabled} onClick={() => onChange("equipmentSlots", equipment.filter((_item, row) => row !== index))}>×</button>
        </div>)}</div>
        <div className="master-ai-fields">
          <JsonEditor label="Gruppi accessori espliciti" value={groups} disabled={disabled} onChange={(next) => onChange("equipmentGroups", next)} help="Ogni Item deve essere compatibile con tutti gli slot del gruppo." />
          <JsonEditor label="Fasce quantità accessori" value={accessoryBands} disabled={disabled} onChange={(next) => onChange("accessoryCountByLevel", next)} help="Quando presenti devono coprire i livelli 1–20 senza sovrapposizioni o vuoti." />
        </div>
      </section>
    </>}

    {kind === "creature" && <section className="unit-editor-section" data-component-type="panel" data-theme="default">
      <header><div><p className="eyebrow">Chassis non umanoide</p><h2>Curve e azioni innate</h2><p>Le azioni sono promemoria completi; costi, danni, condizioni, movimento e bersagli non vengono eseguiti automaticamente dalla Unit.</p></div></header>
      <div className="unit-stat-curves">{curves.map((curve, index) => <div key={`${curve.key}-${index}`}>
        <select value={String(curve.key || "")} disabled={disabled} onChange={(event) => updateCurve(index, { key: event.target.value })}>{asArray<Configuration["statCurveVariables"][number]>(configuration.statCurveVariables).map((entry) => <option key={entry.key} value={entry.key}>{entry.label}</option>)}</select>
        <select value={String(curve.profile || "custom")} disabled={disabled} onChange={(event) => updateCurve(index, { profile: event.target.value })}>{asArray<Configuration["statCurveProfiles"][number]>(configuration.statCurveProfiles).map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select>
        <input type="number" value={numberValue(curve.level1)} disabled={disabled} onChange={(event) => updateCurve(index, { level1: Number(event.target.value) })} />
        <input type="number" value={numberValue(curve.level20)} disabled={disabled} onChange={(event) => updateCurve(index, { level20: Number(event.target.value) })} />
        <button type="button" className="icon-button" disabled={disabled} onClick={() => onChange("statProfile", { ...statProfile, curves: curves.filter((_item, row) => row !== index) })}>×</button>
      </div>)}</div>
      <button type="button" className="button secondary small" disabled={disabled || !configuration.statCurveVariables?.length} onClick={() => onChange("statProfile", { ...statProfile, curves: [...curves, { key: configuration.statCurveVariables[0].key, profile: "custom", level1: 0, level20: 0 }] })}>Aggiungi curva</button>
      <div className="unit-innate-actions">{actions.map((action, index) => <article key={`${action.key}-${index}`}>
        <div className="unit-form-grid"><label>Chiave<input value={String(action.key || "")} disabled={disabled} onChange={(event) => updateAction(index, { key: event.target.value })} /></label><label>Nome<input value={String(action.name || "")} disabled={disabled} onChange={(event) => updateAction(index, { name: event.target.value })} /></label><label>Livello minimo<input type="number" min="1" max="20" value={numberValue(action.minLevel, 1)} disabled={disabled} onChange={(event) => updateAction(index, { minLevel: Number(event.target.value) })} /></label><label>Livello massimo<input type="number" min="1" max="20" value={numberValue(action.maxLevel, 20)} disabled={disabled} onChange={(event) => updateAction(index, { maxLevel: Number(event.target.value) })} /></label><label>Trigger<input value={String(action.trigger || "")} disabled={disabled} onChange={(event) => updateAction(index, { trigger: event.target.value })} /></label><label>Durata<input value={String(action.duration || "")} disabled={disabled} onChange={(event) => updateAction(index, { duration: event.target.value })} /></label><label>Icona<input value={String(action.icon || "runa")} disabled={disabled} onChange={(event) => updateAction(index, { icon: event.target.value })} /></label><label className="wide">Descrizione completa<textarea rows={5} value={String(action.description || "")} disabled={disabled} onChange={(event) => updateAction(index, { description: event.target.value })} /></label></div>
        <JsonEditor label="Costi" value={asObject(action.costs)} disabled={disabled} rows={4} onChange={(next) => updateAction(index, { costs: next })} help="Sono ammessi pf, mana, energia, potere, pa e stanchezza." />
        <button type="button" className="button danger small" disabled={disabled} onClick={() => onChange("innateActions", actions.filter((_item, row) => row !== index))}>Rimuovi azione</button>
      </article>)}</div>
      <button type="button" className="button secondary small" disabled={disabled} onClick={() => onChange("innateActions", [...actions, { key: `unit-action-${actions.length + 1}`, name: "", description: "", minLevel: 1, maxLevel: 20, costs: {}, trigger: "Azione", duration: "Istantanea", icon: "runa" }])}>Aggiungi azione</button>
    </section>}

    <section className="unit-editor-section" data-component-type="form" data-theme="muted">
      <header><div><p className="eyebrow">Controlli avanzati</p><h2>Chassis e compatibilità</h2><p>Usare soltanto target verificati nel codice e confermati dall'audit.</p></div></header>
      <div className="master-ai-fields">
        <JsonEditor label="Modificatori base" value={asObject(statProfile.baseModifiers)} disabled={disabled} onChange={(next) => onChange("statProfile", { ...statProfile, baseModifiers: next })} />
        <JsonEditor label="Modificatori per livello" value={asObject(statProfile.perLevelModifiers)} disabled={disabled} onChange={(next) => onChange("statProfile", { ...statProfile, perLevelModifiers: next })} />
        <JsonEditor label="Milestone" value={asArray(statProfile.milestones)} disabled={disabled} onChange={(next) => onChange("statProfile", { ...statProfile, milestones: next })} />
        <JsonEditor label="Fasce legacy" value={asArray(values.levels)} disabled={disabled} onChange={(next) => onChange("levels", next)} />
      </div>
    </section>

    <AuditPanel audit={audit} />
  </div>;
}

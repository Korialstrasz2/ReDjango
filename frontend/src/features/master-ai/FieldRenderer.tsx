import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import type { AIChangeField, AIChangeProblem } from "./types";
import { UnitProposalEditor } from "./UnitProposalEditor";

type Props = {
  fields: AIChangeField[];
  values: Record<string, unknown>;
  errors: AIChangeProblem[];
  disabled: boolean;
  onChange: (name: string, value: unknown) => void;
};

const valueKey = (value: unknown) => value === null ? "__null__" : String(value);
const parseChoice = (field: AIChangeField, raw: string) => {
  if (raw === "__null__") return null;
  return field.choices.find((choice) => valueKey(choice.value) === raw)?.value ?? raw;
};

function StructuredField({ field, value, disabled, onChange }: { field: AIChangeField; value: unknown; disabled: boolean; onChange: (value: unknown) => void }) {
  const formatted = useMemo(() => JSON.stringify(value ?? (field.nullable ? null : {}), null, 2), [field.nullable, value]);
  const [text, setText] = useState(formatted);
  const [error, setError] = useState("");
  useEffect(() => { setText(formatted); setError(""); }, [formatted]);
  return <label className="master-ai-field full structured">
    <span><strong>{field.label}</strong><small>{field.ui.widget && field.ui.widget !== "json" ? `Editor strutturato · ${field.ui.widget}` : "JSON strutturato"}</small></span>
    <textarea rows={10} value={text} disabled={disabled} onChange={(event) => {
      const next = event.target.value; setText(next);
      try { const parsed = JSON.parse(next); setError(""); onChange(parsed); }
      catch { setError("JSON non valido: correggi la sintassi prima di salvare la bozza."); }
    }} />
    {error && <small className="form-error" role="alert">{error}</small>}
    {field.help && <small>{field.help}</small>}
  </label>;
}

function RelationField({ field, value, disabled, multiple, onChange }: { field: AIChangeField; value: unknown; disabled: boolean; multiple: boolean; onChange: (value: unknown) => void }) {
  const [query, setQuery] = useState("");
  const selected = new Set((multiple ? (Array.isArray(value) ? value : []) : [value]).filter((entry) => entry !== null && entry !== undefined).map(valueKey));
  const visible = field.choices.filter((choice) => !query || choice.label.toLocaleLowerCase("it").includes(query.toLocaleLowerCase("it")));
  if (!multiple) return <label className={`master-ai-field ${field.ui.width || "half"}`}>
    <span><strong>{field.label}{field.required ? " *" : ""}</strong></span>
    {field.choices.length > 12 && <input type="search" value={query} disabled={disabled} placeholder="Filtra le opzioni…" onChange={(event) => setQuery(event.target.value)} />}
    <select disabled={disabled} value={value === null || value === undefined ? "__null__" : valueKey(value)} onChange={(event) => onChange(parseChoice(field, event.target.value))}>
      {field.nullable && <option value="__null__">— Nessuna —</option>}
      {visible.map((choice) => <option key={valueKey(choice.value)} value={valueKey(choice.value)}>{choice.label}</option>)}
    </select>
    {field.help && <small>{field.help}</small>}
  </label>;
  return <fieldset className="master-ai-field full relation-multiple" disabled={disabled}>
    <legend>{field.label}{field.required ? " *" : ""}</legend>
    <input type="search" value={query} placeholder="Cerca tra le opzioni…" onChange={(event) => setQuery(event.target.value)} />
    <div className="master-ai-choice-grid">{visible.map((choice) => <label key={valueKey(choice.value)}>
      <input type="checkbox" checked={selected.has(valueKey(choice.value))} onChange={(event) => {
        const next = new Set(selected); if (event.target.checked) next.add(valueKey(choice.value)); else next.delete(valueKey(choice.value));
        onChange(field.choices.filter((entry) => next.has(valueKey(entry.value))).map((entry) => entry.value));
      }} /><span>{choice.label}</span>
    </label>)}</div>
    {field.help && <small>{field.help}</small>}
  </fieldset>;
}

export function ProposalFieldRenderer({ fields, values, errors, disabled, onChange }: Props) {
  if (fields.some((field) => field.ui.widget === "unitDefinition")) {
    return <UnitProposalEditor fields={fields} values={values} errors={errors} disabled={disabled} onChange={onChange} />;
  }
  const groups = useMemo(() => fields.reduce<Record<string, AIChangeField[]>>((result, field) => {
    (result[field.group || "Campi"] ||= []).push(field); return result;
  }, {}), [fields]);
  const errorFor = (name: string) => errors.find((error) => error.field === name || error.field?.endsWith(`.${name}`));

  return <div className="master-ai-field-groups">{Object.entries(groups).map(([group, groupFields]) => <fieldset key={group} className="master-ai-field-group">
    <legend>{group}</legend><div className="master-ai-fields">{groupFields.map((field) => {
      const value = values[field.name];
      const fieldError = errorFor(field.name);
      if (field.readOnly) return <div key={field.name} className={`master-ai-field ${field.ui.width || "half"} readonly`}><strong>{field.label}</strong><output>{String(value ?? "—")}</output></div>;
      if (field.kind === "structured") return <StructuredField key={field.name} field={field} value={value} disabled={disabled} onChange={(next) => onChange(field.name, next)} />;
      if (field.kind === "relation" || field.kind === "image") return <RelationField key={field.name} field={field} value={value} disabled={disabled} multiple={false} onChange={(next) => onChange(field.name, next)} />;
      if (field.kind === "multiRelation") return <RelationField key={field.name} field={field} value={value} disabled={disabled} multiple onChange={(next) => onChange(field.name, next)} />;
      if (field.kind === "boolean") return <label key={field.name} className={`master-ai-field ${field.ui.width || "half"} boolean`}><input type="checkbox" checked={Boolean(value)} disabled={disabled} onChange={(event) => onChange(field.name, event.target.checked)} /><span><strong>{field.label}</strong>{field.help && <small>{field.help}</small>}</span>{fieldError && <small className="form-error">{fieldError.message}</small>}</label>;
      if (field.kind === "choice") {
        const current = value === null || value === undefined ? "__null__" : valueKey(value);
        const known = field.choices.some((choice) => valueKey(choice.value) === current);
        return <label key={field.name} className={`master-ai-field ${field.ui.width || "half"}`}><span><strong>{field.label}{field.required ? " *" : ""}</strong></span><select disabled={disabled} value={current} onChange={(event) => onChange(field.name, parseChoice(field, event.target.value))}>
          {field.nullable && <option value="__null__">— Nessuno —</option>}{!known && current !== "__null__" && <option value={current} disabled>Valore precedente: {current}</option>}
          {field.choices.map((choice) => <option key={valueKey(choice.value)} value={valueKey(choice.value)}>{choice.label}</option>)}</select>{field.help && <small>{field.help}</small>}{fieldError && <small className="form-error">{fieldError.message}</small>}</label>;
      }
      if (["text", "longText", "integer", "number", "color"].includes(field.kind)) {
        const common = { disabled, required: field.required, value: value === null || value === undefined ? "" : String(value), onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
          const raw = event.target.value; onChange(field.name, field.kind === "integer" ? (raw === "" ? null : Number.parseInt(raw, 10)) : field.kind === "number" ? (raw === "" ? null : Number(raw)) : raw);
        }};
        return <label key={field.name} className={`master-ai-field ${field.ui.width || (field.kind === "longText" ? "full" : "half")}`}><span><strong>{field.label}{field.required ? " *" : ""}</strong></span>
          {field.kind === "longText" ? <textarea rows={5} {...common} /> : <input type={field.kind === "integer" || field.kind === "number" ? "number" : field.kind === "color" ? "color" : "text"} min={field.ui.minimum} max={field.ui.maximum} step={field.kind === "integer" ? 1 : field.ui.step} {...common} />}
          {field.help && <small>{field.help}</small>}{fieldError && <small className="form-error">{fieldError.message}</small>}</label>;
      }
      return <div key={field.name} className="master-ai-field full unsupported" role="alert"><strong>{field.label}</strong><p>Tipo di campo non supportato: <code>{field.kind}</code>. Il dato non è stato nascosto.</p></div>;
    })}</div>
  </fieldset>)}</div>;
}

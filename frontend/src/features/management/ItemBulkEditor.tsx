import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import type {
  BulkActionRow,
  BulkApplyResult,
  BulkField,
  BulkFieldCatalog,
  BulkFilterRow,
  BulkPreview,
} from "./types";

type BulkActionData = { management?: { bulkPreview?: BulkPreview; bulkApply?: BulkApplyResult } };

type Preset = { label: string; detail: string; filters: BulkFilterRow[]; actions: BulkActionRow[] };

const newFilter = (field: string, operator: string, value = ""): BulkFilterRow => ({ field, operator, value });

const newAction = (field: string, operator: string, value = "", extra: Partial<BulkActionRow> = {}): BulkActionRow => ({
  field, operator, value, replacement: "", rounding: "keep", decimals: 0, ...extra,
});

// Shortcuts for the batches that actually come up while curating the catalogue.
// The first one is the recipe the Elder Django tool shipped with; the others
// cover the two cleanups that used to be done by hand, row by row.
const PRESETS: Preset[] = [
  {
    label: "Pozioni non bevande · valore −50%",
    detail: "tipo 1 = pozione, tipo 2 ≠ bevanda → valore × 0,5",
    filters: [newFilter("tipo_1", "eq", "pozione"), newFilter("tipo_2", "ne", "bevanda")],
    actions: [newAction("valore", "mul", "0.5")],
  },
  {
    label: "Arrotonda i pesi a 2 decimali",
    detail: "peso non vuoto → peso × 1 arrotondato",
    filters: [newFilter("peso", "notempty")],
    actions: [newAction("peso", "mul", "1", { rounding: "round", decimals: 2 })],
  },
  {
    label: "Ripulisci gli spazi nei nomi",
    detail: "tutti gli oggetti → nome senza spazi ai lati",
    filters: [],
    actions: [newAction("nome", "strip")],
  },
];

function fieldValueInput(
  field: BulkField | undefined,
  value: string,
  onChange: (next: string) => void,
  placeholder: string,
) {
  if (!field) return <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} disabled />;
  if (field.choices.length) {
    const known = field.choices.some((choice) => choice.value === value);
    return <select value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">— scegli —</option>
      {value && !known && <option value={value}>{value} · non configurato</option>}
      {field.choices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
    </select>;
  }
  if (field.kind === "integer" || field.kind === "number") {
    return <input type="number" step={field.kind === "number" ? "any" : "1"} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />;
  }
  return <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />;
}

function FieldSelect({ fields, value, onChange }: { fields: BulkField[]; value: string; onChange: (next: string) => void }) {
  const groups = useMemo(() => {
    const collected = new Map<string, BulkField[]>();
    fields.forEach((field) => collected.set(field.group, [...(collected.get(field.group) || []), field]));
    return [...collected.entries()];
  }, [fields]);
  return <select value={value} onChange={(event) => onChange(event.target.value)}>
    <option value="">— scegli il campo —</option>
    {groups.map(([group, entries]) => <optgroup key={group} label={group}>
      {entries.map((field) => <option key={field.name} value={field.name}>{field.label}</option>)}
    </optgroup>)}
  </select>;
}

export function ItemBulkEditor({ onApplied }: { onApplied: () => void }) {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<BulkFilterRow[]>([]);
  const [actions, setActions] = useState<BulkActionRow[]>([]);
  const [limit, setLimit] = useState(25);
  const [preview, setPreview] = useState<BulkPreview | null>(null);
  const [error, setError] = useState("");

  const catalogQuery = useQuery({
    queryKey: ["management-items-bulk-fields"],
    queryFn: () => getData<BulkFieldCatalog>("/api/v1/management/items/bulk-fields"),
    staleTime: 5 * 60 * 1000,
  });
  const catalog = catalogQuery.data;
  const fieldsByName = useMemo(() => new Map((catalog?.fields || []).map((field) => [field.name, field])), [catalog]);

  // The recipe the in-flight preview was asked for. A reply that arrives after
  // the form moved on is dropped: its token belongs to rows the operator is no
  // longer looking at, and showing it would re-enable Apply for the wrong batch.
  const pending = useRef("");
  const previewMutation = useMutation({
    mutationFn: (requested: string) => {
      pending.current = requested;
      return command<BulkActionData>("items.bulkPreview", { filters, actions, limit }, "management-items");
    },
    onSuccess: (response, requested) => {
      if (requested !== pending.current) return;
      setPreview(response.data.management?.bulkPreview || null);
      setError("");
    },
    onError: (caught: Error, requested) => {
      if (requested !== pending.current) return;
      setPreview(null);
      setError(caught.message);
    },
  });

  const applyMutation = useMutation({
    mutationFn: (token: string) => command<BulkActionData>("items.bulkApply", { filters, actions, token }, "management-items"),
    onSuccess: async (response) => {
      const result = response.data.management?.bulkApply;
      await queryClient.invalidateQueries({ queryKey: ["management-items"] });
      onApplied();
      setPreview(null);
      setError("");
      notify(
        result
          ? `${result.updated} oggetti aggiornati su ${result.matched} selezionati${result.refreshedCharacters ? `, ${result.refreshedCharacters} schede ricalcolate` : ""}.`
          : "Modifica applicata.",
      );
    },
    onError: (caught: Error) => { setPreview(null); setError(caught.message); notify(caught.message, "error"); },
  });

  // Editing the recipe voids the preview: the token the server issued belongs
  // to the rows the operator looked at, not to whatever the form says now.
  const recipe = JSON.stringify({ filters, actions });
  const lastRecipe = useRef(recipe);
  useEffect(() => {
    if (lastRecipe.current !== recipe) {
      lastRecipe.current = recipe;
      pending.current = "";
      setPreview(null);
    }
  }, [recipe]);

  // The preview is read-only, so it can follow the form. Waiting out a pause in
  // typing keeps a request per keystroke away from a scan of the catalogue.
  const complete = actions.length > 0 && actions.every((row) => row.field && row.operator) && filters.every((row) => row.field && row.operator);
  useEffect(() => {
    if (!complete) return undefined;
    const timer = window.setTimeout(() => previewMutation.mutate(recipe), 700);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recipe, limit, complete]);

  if (catalogQuery.isLoading) return <section className="panel"><p>Caricamento dei campi modificabili…</p></section>;
  if (catalogQuery.error) return <section className="panel danger-panel"><p>{(catalogQuery.error as Error).message}</p></section>;
  if (!catalog) return null;

  const valuelessFilter = new Set(catalog.valuelessFilterOperators);
  const valuelessAction = new Set(catalog.valuelessActionOperators);
  const needsReplacement = new Set(catalog.replacementActionOperators);

  const updateFilter = (index: number, patch: Partial<BulkFilterRow>) =>
    setFilters((current) => current.map((row, position) => position === index ? { ...row, ...patch } : row));
  const updateAction = (index: number, patch: Partial<BulkActionRow>) =>
    setActions((current) => current.map((row, position) => position === index ? { ...row, ...patch } : row));

  // Changing the field can strand an operator the new field does not offer, so
  // the row falls back to that field's first operator instead of staying broken.
  const changeFilterField = (index: number, name: string) => {
    const field = fieldsByName.get(name);
    updateFilter(index, { field: name, operator: field?.filterOperators[0]?.value || "eq", value: "" });
  };
  const changeActionField = (index: number, name: string) => {
    const field = fieldsByName.get(name);
    updateAction(index, { field: name, operator: field?.actionOperators[0]?.value || "set", value: "", replacement: "", rounding: "keep", decimals: 0 });
  };

  const usePreset = (preset: Preset) => {
    setFilters(preset.filters.map((row) => ({ ...row })));
    setActions(preset.actions.map((row) => ({ ...row })));
  };

  const applyBatch = () => {
    if (!preview?.token) return;
    const scope = preview.total === preview.changed
      ? `${preview.changed} oggetti`
      : `${preview.changed} oggetti su ${preview.total} selezionati`;
    if (!window.confirm(`Applicare la modifica a ${scope}? L'operazione riscrive il catalogo e non è annullabile.`)) return;
    applyMutation.mutate(preview.token);
  };

  const usedFields = new Set(actions.map((row) => row.field).filter(Boolean));

  return <section className="item-bulk-editor" data-component-type="panel" data-theme="default">
    <div className="callout guide-warning" role="note">
      <strong>Modifica molti oggetti in una volta sola</strong>
      <p>
        I <em>filtri</em> scelgono le righe, le <em>modifiche</em> dicono cosa farne. Nulla viene scritto finché non
        premi <em>Applica</em>, e Applica accetta solo l'anteprima che stai guardando: se cambi una riga o il catalogo si
        muove, l'anteprima va rifatta.
      </p>
      <p>
        Le modifiche passano dalle stesse verifiche dell'editor singolo, quindi un tipo non configurato, una rarità fuori
        scala o un peso negativo fermano l'intera operazione senza toccare niente. Effetti strutturati, profili arma,
        alchimia, crafting e immagini non sono modificabili qui: vanno cambiati dalla scheda <em>Catalogo</em>.
      </p>
    </div>

    <div className="bulk-presets" data-component-type="toolbar" data-theme="gold">
      <span>Ricette pronte</span>
      {PRESETS.map((preset) => <button key={preset.label} type="button" className="button secondary small" title={preset.detail} onClick={() => usePreset(preset)}>{preset.label}</button>)}
      <button type="button" className="button secondary small" disabled={!filters.length && !actions.length} onClick={() => { setFilters([]); setActions([]); }}>Svuota tutto</button>
    </div>

    <div className="bulk-recipe">
      <section className="panel bulk-card" data-component-type="panel" data-theme="default">
        <header>
          <div><strong>Filtri</strong><small>Tutte le condizioni devono essere vere (AND).</small></div>
          <div className="button-row">
            <button type="button" className="button secondary small" onClick={() => setFilters([...filters, newFilter("", "eq")])}>+ Filtro</button>
            <button type="button" className="button secondary small" disabled={!filters.length} onClick={() => setFilters([])}>Svuota</button>
          </div>
        </header>
        {!filters.length && <p className="bulk-scope-warning" data-state="all">Nessun filtro: la modifica riguarderebbe <strong>ogni oggetto del catalogo</strong>, archiviati compresi.</p>}
        <div className="bulk-rows">
          {filters.map((row, index) => {
            const field = fieldsByName.get(row.field);
            return <div className="bulk-row" key={index}>
              <FieldSelect fields={catalog.fields} value={row.field} onChange={(name) => changeFilterField(index, name)} />
              <select value={row.operator} disabled={!field} onChange={(event) => updateFilter(index, { operator: event.target.value, value: "" })}>
                {(field?.filterOperators || []).map((operator) => <option key={operator.value} value={operator.value}>{operator.label}</option>)}
              </select>
              {valuelessFilter.has(row.operator)
                ? <span className="bulk-row-note">nessun valore richiesto</span>
                : row.operator === "in"
                  ? <input value={row.value} onChange={(event) => updateFilter(index, { value: event.target.value })} placeholder="valori separati da virgola" />
                  : fieldValueInput(field, row.value, (value) => updateFilter(index, { value }), "valore")}
              <button type="button" className="icon-button" aria-label="Togli il filtro" onClick={() => setFilters(filters.filter((_, position) => position !== index))}>✕</button>
            </div>;
          })}
        </div>
      </section>

      <section className="panel bulk-card" data-component-type="panel" data-theme="gold">
        <header>
          <div><strong>Modifiche</strong><small>Un campo per riga: due modifiche sullo stesso campo sono rifiutate.</small></div>
          <div className="button-row">
            <button type="button" className="button secondary small" onClick={() => setActions([...actions, newAction("", "set")])}>+ Modifica</button>
            <button type="button" className="button secondary small" disabled={!actions.length} onClick={() => setActions([])}>Svuota</button>
          </div>
        </header>
        {!actions.length && <p className="bulk-scope-warning">Aggiungi almeno una modifica per vedere l'anteprima.</p>}
        <div className="bulk-rows">
          {actions.map((row, index) => {
            const field = fieldsByName.get(row.field);
            const duplicated = Boolean(row.field) && actions.filter((entry) => entry.field === row.field).length > 1;
            return <div className="bulk-row bulk-action-row" key={index} data-state={duplicated ? "invalid" : undefined}>
              <FieldSelect fields={catalog.fields.filter((entry) => entry.name === row.field || !usedFields.has(entry.name))} value={row.field} onChange={(name) => changeActionField(index, name)} />
              <select value={row.operator} disabled={!field} onChange={(event) => updateAction(index, { operator: event.target.value, value: "", replacement: "" })}>
                {(field?.actionOperators || []).map((operator) => <option key={operator.value} value={operator.value}>{operator.label}</option>)}
              </select>
              {valuelessAction.has(row.operator)
                ? <span className="bulk-row-note">nessun valore richiesto</span>
                : fieldValueInput(field, row.value, (value) => updateAction(index, { value }), needsReplacement.has(row.operator) ? "testo da cercare" : "valore")}
              {needsReplacement.has(row.operator)
                ? <input value={row.replacement} onChange={(event) => updateAction(index, { replacement: event.target.value })} placeholder="testo sostitutivo" />
                : field?.kind === "number" && !valuelessAction.has(row.operator)
                  ? <span className="bulk-rounding">
                    <select value={row.rounding} onChange={(event) => updateAction(index, { rounding: event.target.value })}>
                      {catalog.roundingModes.map((mode) => <option key={mode.value} value={mode.value}>{mode.label}</option>)}
                    </select>
                    {row.rounding !== "keep" && <input type="number" min={0} max={6} value={row.decimals} aria-label="Decimali" onChange={(event) => updateAction(index, { decimals: Number(event.target.value) || 0 })} />}
                  </span>
                  : <span className="bulk-row-note">{field?.kind === "integer" && !valuelessAction.has(row.operator) ? "risultato arrotondato all'intero" : field?.hint || ""}</span>}
              <button type="button" className="icon-button" aria-label="Togli la modifica" onClick={() => setActions(actions.filter((_, position) => position !== index))}>✕</button>
            </div>;
          })}
        </div>
      </section>
    </div>

    <section className="panel bulk-preview" data-component-type="panel" data-theme="default">
      <header>
        <div>
          <strong>Anteprima</strong>
          <small>{previewMutation.isPending ? "Calcolo in corso…" : preview ? `${preview.changed} oggetti cambierebbero su ${preview.total} selezionati` : "Completa filtri e modifiche per vedere il risultato."}</small>
        </div>
        <div className="button-row">
          <label className="bulk-limit">Righe mostrate<input type="number" min={1} max={200} value={limit} onChange={(event) => setLimit(Math.max(1, Math.min(200, Number(event.target.value) || 25)))} /></label>
          <button type="button" className="button secondary" disabled={!complete || previewMutation.isPending} onClick={() => previewMutation.mutate(recipe)}>Ricalcola</button>
        </div>
      </header>

      {error && <p className="form-error" role="alert">{error}</p>}

      {preview?.truncated && <p className="bulk-scope-warning" data-state="all">
        Anteprima ferma ai primi {preview.scanned} oggetti dei {preview.total} selezionati. Applica lavorerebbe su tutti:
        controlla i filtri, oppure restringili e procedi a scaglioni.
      </p>}

      {Boolean(preview?.issues.length) && <div className="bulk-issues" role="alert">
        <strong>{preview!.issues.length === 1 ? "Un problema blocca la modifica" : `${preview!.issues.length} problemi bloccano la modifica`}</strong>
        <ul>{preview!.issues.map((issue, index) => <li key={index}>{issue.id ? `#${issue.id} ${issue.name}: ` : ""}{issue.message}</li>)}</ul>
      </div>}

      {preview && !preview.issues.length && !preview.changed && <div className="management-empty-state">
        <strong>Nessun oggetto cambierebbe</strong>
        <p>{preview.total ? "Le righe selezionate hanno già questi valori." : "Nessun oggetto corrisponde ai filtri."}</p>
      </div>}

      {Boolean(preview?.sample.length) && <div className="bulk-preview-table">
        <table>
          <thead><tr><th>ID</th><th>Oggetto</th><th>Cosa cambia</th></tr></thead>
          <tbody>
            {preview!.sample.map((row) => <tr key={row.id}>
              <td>#{row.id}</td>
              <td>{row.name}</td>
              <td><ul className="bulk-change-list">{row.changes.map((change) => <li key={change.field}>
                <span>{change.label}</span><del>{change.before}</del><ins>{change.after}</ins>
              </li>)}</ul></td>
            </tr>)}
          </tbody>
        </table>
        {preview!.changed > preview!.sample.length && <small>Mostrati {preview!.sample.length} dei {preview!.changed} oggetti che cambierebbero.</small>}
      </div>}

      <footer className="bulk-apply-bar">
        <span>{preview?.token ? "Anteprima valida: Applica userà esattamente queste righe." : "Applica si sblocca quando l'anteprima è pulita e c'è qualcosa da cambiare."}</span>
        <button type="button" className="button danger" disabled={!preview?.token || applyMutation.isPending} onClick={applyBatch}>
          {applyMutation.isPending ? "Applicazione…" : `Applica a ${preview?.changed ?? 0} oggetti`}
        </button>
      </footer>
    </section>
  </section>;
}

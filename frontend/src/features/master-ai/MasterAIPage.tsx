import { type FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiClientError, getData } from "../../lib/api";
import type { AIConversationBubble, AIHistoryEntry } from "../../lib/types";
import {
  applyAIChangeSet,
  askMasterAssistant,
  cancelMasterAIExecutionRun,
  discardAIChangeSet,
  getAIChangeSet,
  getAIChangeSets,
  getMasterAIExecutionRun,
  removeAIChangeOperation,
  updateAIChangeOperation,
  validateAIChangeSet,
} from "./api";
import { ProposalFieldRenderer } from "./FieldRenderer";
import type {
  AIChangeField,
  AIChangeOperation,
  AIChangeSet,
  MasterAIChatResult,
  MasterAIExecutionRun,
  MasterAIWorkspaceData,
} from "./types";

type NoticeKind = "success" | "error" | "info";
type Props = { notify: (message: string, kind?: NoticeKind) => void };
const bubbleId = () => globalThis.crypto?.randomUUID?.() ?? `b-${Date.now()}-${Math.random().toString(16).slice(2)}`;
const isWorking = (run: MasterAIExecutionRun | null) => run?.status === "queued" || run?.status === "running";
const actionLabel = { create: "Crea", update: "Modifica", archive: "Archivia" } as const;
const statusLabel: Record<string, string> = { proposed: "Bozza", valid: "Valida", invalid: "Non valida", applied: "Applicata", skipped: "Esclusa" };

function ConfirmDialog({ title, children, confirmLabel, danger = false, onConfirm, onClose, pending }: {
  title: string; children: ReactNode; confirmLabel: string; danger?: boolean; onConfirm: () => void; onClose: () => void; pending: boolean;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { confirmRef.current?.focus(); }, []);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pending) { onClose(); return; }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = [...dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]")];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable.at(-1)!;
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose, pending]);
  return <div className="master-ai-dialog-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !pending && onClose()}>
    <section ref={dialogRef} className="master-ai-dialog" role="dialog" aria-modal="true" aria-labelledby="master-ai-dialog-title">
      <h2 id="master-ai-dialog-title">{title}</h2><div>{children}</div>
      <footer><button type="button" className="button secondary" disabled={pending} onClick={onClose}>Annulla</button>
        <button ref={confirmRef} type="button" className={`button ${danger ? "danger" : "primary"}`} disabled={pending} onClick={onConfirm}>{pending ? "Operazione…" : confirmLabel}</button></footer>
    </section>
  </div>;
}

function DiffValue({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") return <span className="master-ai-empty">—</span>;
  if (typeof value === "object") return <pre>{JSON.stringify(value, null, 2)}</pre>;
  if (typeof value === "boolean") return <span>{value ? "Sì" : "No"}</span>;
  return <span>{String(value)}</span>;
}

function ProposalDiff({ operation }: { operation: AIChangeOperation }) {
  const [showAll, setShowAll] = useState(false);
  if (operation.action === "archive") return null;
  const rows = showAll ? operation.diff : operation.diff.filter((entry) => entry.changed);
  return <details className="master-ai-diff" open>
    <summary><span>Diff tecnico</span><small>{operation.diff.filter((entry) => entry.changed).length} campi modificati</small></summary>
    <header><span /><label><input type="checkbox" checked={showAll} onChange={(event) => setShowAll(event.target.checked)} /> Mostra invariati</label></header>
    {rows.length ? <div className="master-ai-diff-list">{rows.map((entry) => <article key={entry.field} data-changed={entry.changed}><strong>{entry.label}</strong><div><span>Prima</span><DiffValue value={entry.before} /></div><div><span>Dopo</span><DiffValue value={entry.after} /></div></article>)}</div>
      : <p className="empty-copy">Nessuna differenza nei campi esposti.</p>}
  </details>;
}

function OperationList({ changeSet, selectedId, dirty, onSelect, onToggle, onRemove }: {
  changeSet: AIChangeSet; selectedId: number | null; dirty: boolean;
  onSelect: (id: number) => void; onToggle: (operation: AIChangeOperation, selected: boolean) => void; onRemove: (operation: AIChangeOperation) => void;
}) {
  return <div className="master-ai-operation-list" aria-label="Operazioni proposte">
    {changeSet.operations.length ? changeSet.operations.map((operation) => <article key={operation.id} className={selectedId === operation.id ? "active" : ""} data-action={operation.action}>
      <label className="master-ai-operation-select"><input type="checkbox" checked={operation.selected} disabled={!changeSet.canEdit} onChange={(event) => onToggle(operation, event.target.checked)} /><span className="sr-only">Seleziona {operation.displayLabel}</span></label>
      <button type="button" onClick={() => onSelect(operation.id)} aria-current={selectedId === operation.id ? "true" : undefined}>
        <span className="master-ai-action-icon" aria-hidden="true">{operation.action === "create" ? "+" : operation.action === "update" ? "↻" : "⌫"}</span>
        <span><small>{operation.entityLabel} · {actionLabel[operation.action]}</small><strong>{operation.displayLabel || "Senza nome"}</strong><em>{statusLabel[operation.status] || operation.status} · {operation.diff.filter((entry) => entry.changed).length} campi</em></span>
        {(operation.errors.length > 0 || operation.warnings.length > 0) && <b aria-label={`${operation.errors.length} errori e ${operation.warnings.length} avvisi`}>{operation.errors.length ? `!${operation.errors.length}` : `⚠${operation.warnings.length}`}</b>}
      </button>
      {changeSet.canEdit && <button type="button" className="icon-button" title="Rimuovi operazione" disabled={dirty && selectedId === operation.id} onClick={() => onRemove(operation)}>×</button>}
    </article>) : <p className="empty-copy">L'agente non ha ancora aggiunto operazioni.</p>}
  </div>;
}

const choiceLabel = (field: AIChangeField, value: unknown) => field.choices.find((choice) => String(choice.value) === String(value))?.label;

function SnapshotValue({ field, value }: { field?: AIChangeField; value: unknown }) {
  if (value === null || value === undefined || value === "") return <span className="master-ai-empty">—</span>;
  if (field?.kind === "boolean" || typeof value === "boolean") return <span>{value ? "Sì" : "No"}</span>;
  if (field && ["choice", "relation", "image"].includes(field.kind)) return <span>{choiceLabel(field, value) || String(value)}</span>;
  if (field?.kind === "multiRelation" && Array.isArray(value)) return <span>{value.map((entry) => choiceLabel(field, entry) || String(entry)).join(", ") || "—"}</span>;
  if (typeof value === "object") return <pre>{JSON.stringify(value, null, 2)}</pre>;
  return <span>{String(value)}</span>;
}

function RecordSnapshot({ operation }: { operation: AIChangeOperation }) {
  const values = { ...(operation.original.values || {}), ...(operation.original.display || {}) };
  const groups = operation.fields.reduce<Record<string, AIChangeField[]>>((result, field) => {
    if (Object.prototype.hasOwnProperty.call(values, field.name)) (result[field.group || "Campi"] ||= []).push(field);
    return result;
  }, {});
  const knownNames = new Set(operation.fields.map((field) => field.name));
  const extras = Object.entries(values).filter(([name]) => !knownNames.has(name));
  const title = operation.action === "update"
    ? "Dati attuali"
    : operation.action === "archive"
      ? "Record attuale"
      : operation.sourceId || operation.intent === "clone"
        ? "Modello esistente"
        : "Riferimento esistente";
  return <section className="master-ai-comparison-pane master-ai-current-record">
    <header><div><p className="eyebrow">Prima</p><h3>{title}</h3></div>{operation.original.label && <span>{operation.original.label}</span>}</header>
    {Object.keys(values).length ? <div className="master-ai-snapshot-groups">
      {Object.entries(groups).map(([group, fields]) => <section key={group}><h4>{group}</h4><dl>{fields.map((field) => <div key={field.name}><dt>{field.label}</dt><dd><SnapshotValue field={field} value={values[field.name]} /></dd></div>)}</dl></section>)}
      {extras.length > 0 && <section><h4>Altri dati</h4><dl>{extras.map(([name, value]) => <div key={name}><dt>{name}</dt><dd><SnapshotValue value={value} /></dd></div>)}</dl></section>}
    </div> : <div className="master-ai-snapshot-empty"><strong>Nessun modello collegato</strong><p>{operation.action === "create" ? "La proposta non indica ancora un record simile usato come modello." : "I dati correnti non sono disponibili nella proposta."}</p></div>}
  </section>;
}

function ProposalEditor({ operation, changeSet, localValues, dirty, saving, onChange, onSave }: {
  operation: AIChangeOperation;
  changeSet: AIChangeSet;
  localValues: Record<string, unknown>;
  dirty: boolean;
  saving: boolean;
  onChange: (name: string, value: unknown) => void;
  onSave: () => void;
}) {
  return <section className="master-ai-comparison-pane master-ai-proposed-record">
    <header><div><p className="eyebrow">Dopo</p><h3>{operation.action === "archive" ? "Archiviazione" : "Proposta"}</h3></div><span data-state={operation.status}>{statusLabel[operation.status] || operation.status}</span></header>
    {operation.action === "archive" ? <div className="master-ai-deletion-preview" role="note"><span aria-hidden="true">⌫</span><strong>Il record verrà archiviato</strong><p>«{operation.displayLabel}» non comparirà più nel gioco attivo. L'operazione usa il servizio di dominio e non elimina fisicamente il record.</p></div> : <>
      <ProposalFieldRenderer fields={operation.fields} values={localValues} errors={operation.errors} disabled={!changeSet.canEdit || saving} onChange={onChange} />
      <div className="master-ai-draft-actions"><span>{dirty ? "Modifiche locali non salvate" : "Bozza sincronizzata"}</span><button type="button" className="button primary" disabled={!dirty || saving || !changeSet.canEdit} onClick={onSave}>Salva bozza operazione</button></div>
    </>}
  </section>;
}

function OperationDetail({ operation, changeSet, localValues, dirty, saving, onChange, onSave }: {
  operation: AIChangeOperation;
  changeSet: AIChangeSet;
  localValues: Record<string, unknown>;
  dirty: boolean;
  saving: boolean;
  onChange: (name: string, value: unknown) => void;
  onSave: () => void;
}) {
  return <>
    <header className="master-ai-detail-heading"><div><p className="eyebrow">{operation.entityLabel}</p><h2>{actionLabel[operation.action]} · {operation.displayLabel}</h2></div><span data-state={operation.status}>{statusLabel[operation.status] || operation.status}</span></header>
    {operation.errors.length > 0 && <aside className="master-ai-problems error" role="alert" aria-live="polite"><strong>Errori</strong><ul>{operation.errors.map((error, index) => <li key={`${error.code}-${index}`}>{error.message}</li>)}</ul></aside>}
    {operation.warnings.length > 0 && <aside className="master-ai-problems warning" aria-live="polite"><strong>Avvisi</strong><ul>{operation.warnings.map((warning, index) => <li key={`${warning.code}-${index
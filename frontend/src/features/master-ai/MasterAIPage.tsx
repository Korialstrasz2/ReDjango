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
    {operation.warnings.length > 0 && <aside className="master-ai-problems warning" aria-live="polite"><strong>Avvisi</strong><ul>{operation.warnings.map((warning, index) => <li key={`${warning.code}-${index}`}>{warning.message}</li>)}</ul></aside>}
    <div className="master-ai-comparison">
      <RecordSnapshot operation={operation} />
      <ProposalEditor operation={operation} changeSet={changeSet} localValues={localValues} dirty={dirty} saving={saving} onChange={onChange} onSave={onSave} />
    </div>
    <ProposalDiff operation={operation} />
  </>;
}

export function MasterAIPage({ notify }: Props) {
  const queryClient = useQueryClient();
  const workspace = useQuery({ queryKey: ["aiWorkspace"], queryFn: () => getData<MasterAIWorkspaceData>("/api/ai/") });
  const recentSets = useQuery({ queryKey: ["aiChangeSets"], queryFn: getAIChangeSets });
  const [agentId, setAgentId] = useState<number | "">("");
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<AIHistoryEntry[]>([]);
  const [bubbles, setBubbles] = useState<AIConversationBubble[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [activeRun, setActiveRun] = useState<MasterAIExecutionRun | null>(null);
  const [changeSetId, setChangeSetId] = useState<string | null>(null);
  const [selectedOperationId, setSelectedOperationId] = useState<number | null>(null);
  const [localValues, setLocalValues] = useState<Record<string, unknown>>({});
  const [conflict, setConflict] = useState("");
  const [confirm, setConfirm] = useState<"apply" | "discard" | null>(null);
  const handledRun = useRef("");
  const hydrated = useRef(false);
  const changeSetPicked = useRef(false);
  const transcriptRef = useRef<HTMLDivElement>(null);

  const proposerAgents = useMemo(() => (workspace.data?.agents || []).filter((agent) => agent.mode === "proposer" || agent.canProposeChanges), [workspace.data]);
  const proposerAgentIds = useMemo(() => new Set(proposerAgents.map((agent) => agent.id)), [proposerAgents]);
  const proposerConversations = useMemo(() => (workspace.data?.conversations || []).filter((conversation) => proposerAgentIds.has(conversation.agentId || 0)), [proposerAgentIds, workspace.data?.conversations]);
  useEffect(() => { if (!agentId && proposerAgents[0]) setAgentId(proposerAgents[0].id); }, [agentId, proposerAgents]);
  useEffect(() => { const node = transcriptRef.current; if (node) node.scrollTop = node.scrollHeight; }, [bubbles, activeRun?.progress]);
  useEffect(() => {
    if (hydrated.current || !workspace.data || !proposerAgents.length) return;
    hydrated.current = true;
    const restoredRun = workspace.data.activeRun;
    const restoredConversation = restoredRun?.conversation && proposerAgentIds.has(restoredRun.conversation.agentId || 0)
      ? restoredRun.conversation
      : proposerConversations[0];
    if (restoredRun && restoredConversation && isWorking(restoredRun)) setActiveRun(restoredRun);
    if (restoredConversation) {
      setConversationId(restoredConversation.id);
      setAgentId(restoredConversation.agentId || proposerAgents[0].id);
      setHistory(restoredConversation.history);
      setBubbles(restoredConversation.bubbles);
    }
    const runChangeSet = restoredRun?.result && "changeSet" in restoredRun.result ? (restoredRun.result as MasterAIChatResult).changeSet : undefined;
    if (runChangeSet) setChangeSetId(runChangeSet.id);
  }, [proposerAgentIds, proposerAgents, proposerConversations, workspace.data]);

  const changeSetQuery = useQuery({
    queryKey: ["aiChangeSet", changeSetId], enabled: Boolean(changeSetId),
    queryFn: () => getAIChangeSet(changeSetId!).then((data) => data.changeSet),
  });
  const changeSet = changeSetQuery.data || null;
  const selectedOperation = changeSet?.operations.find((operation) => operation.id === selectedOperationId) || changeSet?.operations[0] || null;
  useEffect(() => {
    if (!changeSet) return;
    const exists = changeSet.operations.some((operation) => operation.id === selectedOperationId);
    if (!exists) setSelectedOperationId(changeSet.operations.at(-1)?.id ?? null);
  }, [changeSet, selectedOperationId]);
  useEffect(() => { setLocalValues(selectedOperation?.effectiveValues || {}); }, [selectedOperation?.id, selectedOperation?.effectiveValues, changeSet?.revision]);
  useEffect(() => {
    if (!changeSet?.conversationId || !workspace.data) return;
    const conversation = workspace.data.conversations.find((entry) => entry.id === changeSet.conversationId);
    if (!conversation || conversation.id === conversationId) return;
    setConversationId(conversation.id);
    setAgentId(conversation.agentId || agentId);
    setHistory(conversation.history);
    setBubbles(conversation.bubbles);
  }, [agentId, changeSet?.conversationId, conversationId, workspace.data]);
  const dirty = Boolean(selectedOperation && JSON.stringify(localValues) !== JSON.stringify(selectedOperation.effectiveValues));

  const storeSet = (next: AIChangeSet) => {
    setChangeSetId(next.id);
    queryClient.setQueryData(["aiChangeSet", next.id], next);
    void queryClient.invalidateQueries({ queryKey: ["aiChangeSets"] });
  };
  const clearConversation = () => {
    setConversationId(null); setHistory([]); setBubbles([]); setQuestion(""); setChangeSetId(null); setSelectedOperationId(null); setLocalValues({}); setConflict("");
  };
  const startNewChat = () => {
    if (isWorking(activeRun)) return;
    if (dirty && !window.confirm("Scartare le modifiche locali non salvate e iniziare una nuova chat?")) return;
    changeSetPicked.current = true;
    clearConversation();
  };
  const chooseAgent = (nextId: number) => {
    if (nextId === agentId) return;
    if (dirty && !window.confirm("Scartare le modifiche locali non salvate e cambiare agente?")) return;
    changeSetPicked.current = true;
    clearConversation();
    setAgentId(nextId);
  };
  const chooseConversation = (nextId: number | null) => {
    if (!nextId) { startNewChat(); return; }
    if (nextId === conversationId) return;
    if (dirty && !window.confirm("Scartare le modifiche locali non salvate e cambiare chat?")) return;
    const conversation = proposerConversations.find((entry) => entry.id === nextId);
    if (!conversation) return;
    changeSetPicked.current = true;
    setConversationId(conversation.id); setAgentId(conversation.agentId || agentId); setHistory(conversation.history); setBubbles(conversation.bubbles); setQuestion(""); setSelectedOperationId(null); setLocalValues({}); setConflict("");
    const linked = recentSets.data?.changeSets.find((entry) => entry.conversationId === conversation.id);
    setChangeSetId(linked?.id || null);
  };
  const chooseChangeSet = (nextId: string | null) => {
    if (nextId === changeSetId) return;
    if (dirty && !window.confirm("Scartare le modifiche locali non salvate e cambiare proposta?")) return;
    changeSetPicked.current = true;
    setChangeSetId(nextId); setSelectedOperationId(null); setLocalValues({}); setConflict("");
  };

  useEffect(() => {
    if (changeSetPicked.current || changeSetId) return;
    const sets = recentSets.data?.changeSets;
    if (!sets?.length) return;
    const linked = conversationId ? sets.find((entry) => entry.conversationId === conversationId) : undefined;
    setChangeSetId((linked || sets[0]).id);
  }, [changeSetId, conversationId, recentSets.data]);

  useEffect(() => {
    if (!activeRun || !isWorking(activeRun)) return;
    const timer = window.setTimeout(() => void getMasterAIExecutionRun(activeRun.id).then((response) => setActiveRun(response.data.run)).catch((error: Error) => { notify(error.message, "error"); setActiveRun(null); }), 800);
    return () => window.clearTimeout(timer);
  }, [activeRun, notify]);
  useEffect(() => {
    if (!activeRun || isWorking(activeRun) || handledRun.current === activeRun.id) return;
    handledRun.current = activeRun.id;
    if (activeRun.status === "completed") {
      const result = activeRun.result as MasterAIChatResult;
      setHistory(result.history || []);
      if (activeRun.conversation) { setConversationId(activeRun.conversation.id); setBubbles(activeRun.conversation.bubbles); }
      else setBubbles((current) => [...current, { id: bubbleId(), role: "assistant", text: result.reply || "Proposta aggiornata.", tools: result.toolTrace || [] }]);
      if (result.changeSet) { storeSet(result.changeSet); setSelectedOperationId(result.changeSet.operations.at(-1)?.id ?? null); notify("Proposta pronta per la revisione."); }
      else notify("L'agente ha concluso senza creare operazioni.", "info");
      void workspace.refetch();
    } else if (activeRun.status === "failed") {
      const message = activeRun.error.message || "L'esecuzione AI non è riuscita."; notify(message, "error");
      setBubbles((current) => [...current, { id: bubbleId(), role: "assistant", text: `⚠ ${message}`, tools: [] }]);
      if (changeSetId) void changeSetQuery.refetch();
    } else if (activeRun.status === "cancelled") notify("Esecuzione annullata.", "info");
    setActiveRun(null);
  }, [activeRun, changeSetId, changeSetQuery, notify, workspace]);

  const ask = useMutation({
    mutationFn: (message: string) => askMasterAssistant({ message, history, agentId: Number(agentId), conversationId: conversationId || undefined, changeSetId: changeSetId || undefined }),
    onSuccess: (result) => setActiveRun(result.data.run),
    onError: (error: Error) => notify(error.message, "error"),
  });
  const saveOperation = useMutation({
    mutationFn: () => updateAIChangeOperation(changeSet!.id, selectedOperation!.id, { editedValues: localValues }),
    onSuccess: (result) => { storeSet(result.data.changeSet); setConflict(""); notify("Bozza operazione salvata."); },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const patchOperation = useMutation({
    mutationFn: ({ operation, values }: { operation: AIChangeOperation; values: Record<string, unknown> }) => updateAIChangeOperation(changeSet!.id, operation.id, values),
    onSuccess: (result) => { storeSet(result.data.changeSet); setConflict(""); },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const removeOperation = useMutation({
    mutationFn: (operation: AIChangeOperation) => removeAIChangeOperation(changeSet!.id, operation.id),
    onSuccess: (result) => { storeSet(result.data.changeSet); notify("Operazione rimossa.", "info"); },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const validateSet = useMutation({
    mutationFn: () => validateAIChangeSet(changeSet!.id),
    onSuccess: (result) => { storeSet(result.data.changeSet); setConflict(""); notify(result.data.changeSet.status === "ready" ? "Proposta convalidata: pronta per l'applicazione." : "La proposta contiene errori.", result.data.changeSet.status === "ready" ? "success" : "error"); },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const applySet = useMutation({
    mutationFn: () => applyAIChangeSet(changeSet!.id, changeSet!.validation.token),
    onSuccess: async (result) => {
      storeSet(result.data.changeSet); setConfirm(null); setConflict(""); notify("Proposta applicata.");
      await Promise.all(["items", "itemCatalog", "skills", "skillCatalog", "themes", "settings", "aiWorkspace", "aiChangeSets"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
    },
    onError: (error: Error) => {
      setConfirm(null);
      if (error instanceof ApiClientError && error.status === 409) { setConflict(error.message); void changeSetQuery.refetch(); }
      notify(error.message, "error");
    },
  });
  const discardSet = useMutation({
    mutationFn: () => discardAIChangeSet(changeSet!.id),
    onSuccess: (result) => { storeSet(result.data.changeSet); setConfirm(null); notify("Proposta scartata. Nessun record di gioco è stato modificato.", "info"); },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault(); const message = question.trim();
    if (!message || !agentId || isWorking(activeRun)) return;
    setBubbles((current) => [...current, { id: bubbleId(), role: "user", text: message, tools: [] }]); setQuestion(""); ask.mutate(message);
  };
  const counts = changeSet?.operations.filter((operation) => operation.selected).reduce((result, operation) => ({ ...result, [operation.action]: result[operation.action] + 1 }), { create: 0, update: 0, archive: 0 }) || { create: 0, update: 0, archive: 0 };
  const selectedCount = counts.create + counts.update + counts.archive;
  const canApply = Boolean(changeSet?.canApply && changeSet.validation.token && !dirty && !conflict && !applySet.isPending);

  if (workspace.isLoading) return <div className="page master-ai-page"><p className="empty-copy">Preparazione del Master AI…</p></div>;
  if (workspace.isError) return <div className="page master-ai-page"><p className="form-error">{(workspace.error as Error).message}</p></div>;
  if (!proposerAgents.length) return <div className="page master-ai-page"><header className="page-header"><div><p className="eyebrow">Revisione controllata</p><h1>Master AI</h1></div></header>
    <section className="panel"><h2>Nessun agente proponente disponibile</h2><p>Configura un agente in modalità «Proposte di modifica», con ruolo minimo Master e almeno uno strumento di proposta.</p><Link className="button primary" to="/tools/ai">Apri Gestione AI</Link></section></div>;

  return <div className="page master-ai-page">
    <section className="panel master-ai-commandbar master-ai-statusbar" data-component-type="toolbar" data-theme="gold">
      <header><div><p className="eyebrow">Revisione controllata</p><h1>Master AI</h1></div><p>L'AI prepara una bozza. Convalida e applicazione restano azioni umane separate.</p></header>
      <div className="master-ai-controls">
        <label><span>Agente</span><select value={agentId} disabled={Boolean(isWorking(activeRun))} onChange={(event) => chooseAgent(Number(event.target.value))}>{proposerAgents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name} · {agent.effectiveProviderName || agent.providerName}</option>)}</select></label>
        <label><span>Chat</span><select value={conversationId || ""} disabled={Boolean(isWorking(activeRun))} onChange={(event) => chooseConversation(event.target.value ? Number(event.target.value) : null)}><option value="">Nuova chat</option>{proposerConversations.map((conversation) => <option key={conversation.id} value={conversation.id}>{conversation.title} · {new Date(conversation.updatedAt).toLocaleString("it", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</option>)}</select></label>
        <button type="button" className="button primary master-ai-new-chat" disabled={Boolean(isWorking(activeRun))} onClick={startNewChat}>Nuova chat</button>
        <label><span>Proposta</span><select value={changeSetId || ""} disabled={Boolean(isWorking(activeRun))} onChange={(event) => chooseChangeSet(event.target.value || null)}><option value="">Nessuna proposta</option>{(recentSets.data?.changeSets => [...current, { id: bubbleId(), role: "user", text: message, tools: [] }]); setQuestion(""); ask.mutate(message);
  };
  const counts = changeSet?.operations.filter((operation) => operation.selected).reduce((result, operation) => ({ ...result, [operation.action]: result[operation.action] + 1 }), { create: 0, update: 0, archive: 0 }) || { create: 0, update: 0, archive: 0 };
  const selectedCount = counts.create + counts.update + counts.archive;
  const canApply = Boolean(changeSet?.canApply && changeSet.validation.token && !dirty && !conflict && !applySet.isPending);

  if (workspace.isLoading) return <div className="page master-ai-page"><p className="empty-copy">Preparazione del Master AI…</p></div>;
  if (workspace.isError) return <div className="page master-ai-page"><p className="form-error">{(workspace.error as Error).message}</p></div>;
  if (!proposerAgents.length) return <div className="page master-ai-page"><header className="page-header"><div><p className="eyebrow">Revisione controllata</p><h1>Master AI</h1></div></header>
    <section className="panel"><h2>Nessun agente proponente disponibile</h2><p>Configura un agente in modalità «Proposte di modifica», con ruolo minimo Master e almeno uno strumento di proposta.</p><Link className="button primary" to="/tools/ai">Apri Gestione AI</Link></section></div>;

  return <div className="page master-ai-page">
    <section className="panel master-ai-commandbar master-ai-statusbar" data-component-type="toolbar" data-theme="gold">
      <header><div><p className="eyebrow">Revisione controllata</p><h1>Master AI</h1></div><p>L'AI prepara una bozza. Convalida e applicazione restano azioni umane separate.</p></header>
      <div className="master-ai-controls">
        <label><span>Agente</span><select value={agentId} disabled={Boolean(isWorking(activeRun))} onChange={(event) => chooseAgent(Number(event.target.value))}>{proposerAgents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name} · {agent.effectiveProviderName || agent.providerName}</option>)}</select></label>
        <label><span>Chat</span><select value={conversationId || ""} disabled={Boolean(isWorking(activeRun))} onChange={(event) => chooseConversation(event.target.value ? Number(event.target.value) : null)}><option value="">Nuova chat</option>{proposerConversations.map((conversation) => <option key={conversation.id} value={conversation.id}>{conversation.title} · {new Date(conversation.updatedAt).toLocaleString("it", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</option>)}</select></label>
        <button type="button" className="button primary master-ai-new-chat" disabled={Boolean(isWorking(activeRun))} onClick={startNewChat}>Nuova chat</button>
        <label><span>Proposta</span><select value={changeSetId || ""} disabled={Boolean(isWorking(activeRun))} onChange={(event) => chooseChangeSet(event.target.value || null)}><option value="">Nessuna proposta</option>{(recentSets.data?.changeSets || []).map((entry) => <option key={entry.id} value={entry.id}>{entry.title || entry.id} · {entry.status}</option>)}</select></label>
        <span className="master-ai-status-chip" data-state={changeSet?.status || "empty"}>{changeSet ? `${changeSet.status} · rev. ${changeSet.revision}` : conversationId ? "Chat senza proposta" : "Nuova chat"}</span>
        <Link className="button secondary" to="/tools/ai">Configura AI</Link>
      </div>
    </section>
    {recentSets.isError && <p className="form-error" role="alert">Non è stato possibile caricare le proposte recenti.</p>}
    {changeSetQuery.isError && <p className="form-error" role="alert">{(changeSetQuery.error as Error).message}</p>}
    {conflict && <aside className="master-ai-conflict" role="alert"><strong>Conflitto di versione</strong><p>{conflict}</p><button type="button" className="button secondary" disabled={validateSet.isPending} onClick={() => validateSet.mutate()}>Ricarica e convalida di nuovo</button></aside>}

    <div className="master-ai-layout master-ai-request-row">
      <section className="master-ai-chat panel"><header><div><p className="eyebrow">Conversazione</p><h2>Richiesta</h2></div>{isWorking(activeRun) && <button type="button" className="button secondary small" onClick={() => activeRun && cancelMasterAIExecutionRun(activeRun.id).then((response) => setActiveRun(response.data.run)).catch((error: Error) => notify(error.message, "error"))}>Annulla</button>}</header>
        <div className="master-ai-transcript" ref={transcriptRef} aria-live="polite">{bubbles.length ? bubbles.map((bubble) => <article key={bubble.id} data-role={bubble.role}><strong>{bubble.role === "user" ? "Tu" : "Master AI"}</strong><p>{bubble.text}</p>{bubble.tools.length > 0 && <details><summary>{bubble.tools.length} strumenti usati</summary><ul>{bubble.tools.map((tool, index) => <li key={`${tool.name}-${index}`}>{tool.name}{tool.isError ? " · errore" : ""}</li>)}</ul></details>}</article>) : <div className="master-ai-chat-empty"><strong>Nuova chat</strong><p>Descrivi una creazione, modifica, clone o archiviazione. L'agente userà il database come fonte e aggiungerà operazioni alla proposta.</p><div className="button-row"><button type="button" className="button secondary small" onClick={() => setQuestion("Crea un nuovo oggetto simile a un oggetto esistente, ma chiedimi prima quale usare come modello.")}>Esempio oggetto</button><button type="button" className="button secondary small" onClick={() => setQuestion("Cerca una Skill e proponi una modifica senza applicarla.")}>Esempio Skill</button></div></div>}
          {isWorking(activeRun) && <article data-role="assistant" className="pending"><strong>Master AI</strong><p>{activeRun?.progress || "Elaborazione…"}</p></article>}</div>
        <form onSubmit={submit}><textarea rows={4} value={question} maxLength={8000} disabled={Boolean(isWorking(activeRun))} placeholder="Esempio: crea un incantesimo chiamato Tocco mortale simile a…" onChange={(event) => setQuestion(event.target.value)} /><button className="button primary" disabled={!question.trim() || !agentId || Boolean(isWorking(activeRun)) || ask.isPending}>Invia richiesta</button></form>
      </section>

      <section className="master-ai-operations panel" aria-label="Operazioni proposte"><header><div><p className="eyebrow">Coda di revisione</p><h2>Operazioni</h2></div><span>{changeSet?.operations.length || 0}</span></header>
        {changeSet ? <OperationList changeSet={changeSet} selectedId={selectedOperation?.id || null} dirty={dirty} onSelect={(id) => { if (!dirty || window.confirm("Scartare le modifiche locali non salvate?")) setSelectedOperationId(id); }}
          onToggle={(operation, selected) => { if (dirty && !window.confirm("La selezione invaliderà la convalida. Continuare?")) return; patchOperation.mutate({ operation, values: { selected } }); }}
          onRemove={(operation) => { if (window.confirm(`Rimuovere l'operazione «${operation.displayLabel}»?`)) removeOperation.mutate(operation); }} />
          : <div className="master-ai-operations-empty"><strong>Nessuna operazione</strong><p>Invia una richiesta oppure apri una proposta recente.</p></div>}
      </section>
    </div>

    <section className="master-ai-proposal-detail panel" aria-label="Dettagli della proposta">{changeSet && selectedOperation
      ? <OperationDetail operation={selectedOperation} changeSet={changeSet} localValues={localValues} dirty={dirty} saving={saveOperation.isPending} onChange={(name, value) => setLocalValues((current) => ({ ...current, [name]: value }))} onSave={() => saveOperation.mutate()} />
      : <div className="master-ai-no-proposal"><h2>Dettagli proposta</h2><p>Seleziona un'operazione per confrontare il record attuale o il modello esistente con la proposta dell'AI.</p></div>}
    </section>

    {changeSet && <footer className="master-ai-actionbar" aria-live="polite"><div><strong>{selectedCount} operazioni selezionate</strong><span>{changeSet.validation.errors.length} errori · {changeSet.validation.warnings.length} avvisi</span></div>
      <button type="button" className="button secondary" disabled={!changeSet.canDiscard || discardSet.isPending} onClick={() => setConfirm("discard")}>Scarta proposta</button>
      <button type="button" className="button secondary" disabled={!changeSet.canValidate || dirty || validateSet.isPending} onClick={() => validateSet.mutate()}>{changeSet.status === "ready" ? "Convalida di nuovo" : "Convalida proposta"}</button>
      <button type="button" className="button primary" disabled={!canApply} onClick={() => setConfirm("apply")}>Applica selezionate</button>
    </footer>}

    {confirm === "apply" && changeSet && <ConfirmDialog title="Applicare la proposta?" confirmLabel="Applica in transazione" pending={applySet.isPending} onClose={() => setConfirm(null)} onConfirm={() => applySet.mutate()}>
      <p><strong>{selectedCount}</strong> operazioni saranno applicate tutte insieme oppure nessuna.</p><ul><li>{counts.create} creazioni</li><li>{counts.update} modifiche</li><li>{counts.archive} archiviazioni</li></ul>
      {counts.archive > 0 && <p>Record da archiviare: {changeSet.operations.filter((operation) => operation.selected && operation.action === "archive").map((operation) => operation.displayLabel).join(", ")}.</p>}
      <p>{changeSet.validation.warnings.length} avvisi registrati. L'agente non può eseguire questa azione.</p>
    </ConfirmDialog>}
    {confirm === "discard" && changeSet && <ConfirmDialog title="Scartare la proposta?" confirmLabel="Scarta proposta" danger pending={discardSet.isPending} onClose={() => setConfirm(null)} onConfirm={() => discardSet.mutate()}>
      <p>Nessuna modifica di dominio è stata applicata. La proposta resterà disponibile come riepilogo di audit in sola lettura e la conversazione non verrà eliminata.</p>
    </ConfirmDialog>}
  </div>;
}

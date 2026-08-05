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
import type { AIChangeOperation, AIChangeSet, MasterAIChatResult, MasterAIExecutionRun, MasterAIWorkspaceData } from "./types";

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
    window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key);
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
  if (operation.action === "archive") return <section className="master-ai-archive-warning" role="note"><strong>Archiviazione proposta</strong><p>Il record «{operation.displayLabel}» verrà archiviato tramite il servizio di dominio. Non verrà eliminato fisicamente.</p></section>;
  const rows = showAll ? operation.diff : operation.diff.filter((entry) => entry.changed);
  return <section className="master-ai-diff"><header><h3>Differenze server</h3><label><input type="checkbox" checked={showAll} onChange={(event) => setShowAll(event.target.checked)} /> Mostra invariati</label></header>
    {rows.length ? <div className="master-ai-diff-list">{rows.map((entry) => <article key={entry.field} data-changed={entry.changed}><strong>{entry.label}</strong><div><span>Prima</span><DiffValue value={entry.before} /></div><div><span>Dopo</span><DiffValue value={entry.after} /></div></article>)}</div>
      : <p className="empty-copy">Nessuna differenza nei campi esposti.</p>}
  </section>;
}

function OperationList({ changeSet, selectedId, dirty, onSelect, onToggle, onRemove }: {
  changeSet: AIChangeSet; selectedId: number | null; dirty: boolean;
  onSelect: (id: number) => void; onToggle: (operation: AIChangeOperation, selected: boolean) => void; onRemove: (operation: AIChangeOperation) => void;
}) {
  return <aside className="master-ai-operation-list" aria-label="Operazioni proposte"><header><strong>Operazioni</strong><span>{changeSet.operations.length}</span></header>
    {changeSet.operations.length ? changeSet.operations.map((operation) => <article key={operation.id} className={selectedId === operation.id ? "active" : ""} data-action={operation.action}>
      <label className="master-ai-operation-select"><input type="checkbox" checked={operation.selected} disabled={!changeSet.canEdit} onChange={(event) => onToggle(operation, event.target.checked)} /><span className="sr-only">Seleziona {operation.displayLabel}</span></label>
      <button type="button" onClick={() => onSelect(operation.id)} aria-current={selectedId === operation.id ? "true" : undefined}>
        <span className="master-ai-action-icon" aria-hidden="true">{operation.action === "create" ? "+" : operation.action === "update" ? "↻" : "⌫"}</span>
        <span><small>{operation.entityLabel} · {actionLabel[operation.action]}</small><strong>{operation.displayLabel || "Senza nome"}</strong><em>{statusLabel[operation.status] || operation.status} · {operation.diff.filter((entry) => entry.changed).length} campi</em></span>
        {(operation.errors.length > 0 || operation.warnings.length > 0) && <b aria-label={`${operation.errors.length} errori e ${operation.warnings.length} avvisi`}>{operation.errors.length ? `!${operation.errors.length}` : `⚠${operation.warnings.length}`}</b>}
      </button>
      {changeSet.canEdit && <button type="button" className="icon-button" title="Rimuovi operazione" disabled={dirty && selectedId === operation.id} onClick={() => onRemove(operation)}>×</button>}
    </article>) : <p className="empty-copy">L'agente non ha ancora aggiunto operazioni.</p>}
  </aside>;
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
  useEffect(() => { if (!agentId && proposerAgents[0]) setAgentId(proposerAgents[0].id); }, [agentId, proposerAgents]);
  useEffect(() => { const node = transcriptRef.current; if (node) node.scrollTop = node.scrollHeight; }, [bubbles, activeRun?.progress]);
  useEffect(() => {
    if (hydrated.current || !workspace.data || !proposerAgents.length) return;
    hydrated.current = true;
    const restoredRun = workspace.data.activeRun;
    const restoredConversation = restoredRun?.conversation && proposerAgentIds.has(restoredRun.conversation.agentId || 0)
      ? restoredRun.conversation
      : workspace.data.conversations.find((conversation) => proposerAgentIds.has(conversation.agentId || 0));
    if (restoredRun && restoredConversation && isWorking(restoredRun)) setActiveRun(restoredRun);
    if (restoredConversation) {
      setConversationId(restoredConversation.id);
      setAgentId(restoredConversation.agentId || proposerAgents[0].id);
      setHistory(restoredConversation.history);
      setBubbles(restoredConversation.bubbles);
    }
    const runChangeSet = restoredRun?.result && "changeSet" in restoredRun.result ? (restoredRun.result as MasterAIChatResult).changeSet : undefined;
    if (runChangeSet) setChangeSetId(runChangeSet.id);
  }, [proposerAgentIds, proposerAgents, workspace.data]);

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
    setChangeSetId(next.id); queryClient.setQueryData(["aiChangeSet", next.id], next); void queryClient.invalidateQueries({ queryKey: ["aiChangeSets"] });
  };
  const chooseAgent = (nextId: number) => {
    if (nextId === agentId) return;
    if (dirty && !window.confirm("Scartare le modifiche locali non salvate e cambiare agente?")) return;
    setAgentId(nextId); setConversationId(null); setHistory([]); setBubbles([]); setChangeSetId(null); setSelectedOperationId(null); setConflict("");
  };
  const chooseChangeSet = (nextId: string | null) => {
    if (nextId === changeSetId) return;
    if (dirty && !window.confirm("Scartare le modifiche locali non salvate e cambiare proposta?")) return;
    changeSetPicked.current = true;
    setChangeSetId(nextId); setSelectedOperationId(null); setConflict("");
  };

  // Le proposte già esistenti non devono restare nascoste: alla prima apertura
  // si seleziona la bozza più recente (o quella legata alla conversazione
  // ripristinata) finché l'utente non ne sceglie esplicitamente una.
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

  if (workspace.isLoading) return <main className="master-ai-root"><p className="empty-copy">Preparazione del Master AI…</p></main>;
  if (workspace.isError) return <main className="master-ai-root"><p className="form-error">{(workspace.error as Error).message}</p></main>;
  if (!proposerAgents.length) return <main className="master-ai-root"><header><div><p className="eyebrow">Strumenti</p><h1>Master AI</h1></div><Link className="button secondary" to="/tools">Torna agli strumenti</Link></header>
    <section className="panel"><h2>Nessun agente proponente disponibile</h2><p>Configura un agente in modalità «Proposte di modifica», con ruolo minimo Master e almeno uno strumento di proposta.</p><Link className="button primary" to="/tools/ai">Apri Gestione AI</Link></section></main>;

  return <main className="master-ai-root">
    <header className="master-ai-header"><div><p className="eyebrow">Revisione controllata</p><h1>Master AI</h1><p>L'agente può preparare proposte, ma non può applicarle. Solo i pulsanti del pannello di revisione possono salvare le modifiche selezionate.</p></div>
      <nav><Link className="button secondary" to="/tools">Strumenti</Link><Link className="button secondary" to="/tools/ai">Configura agenti</Link></nav></header>
    <section className="master-ai-statusbar"><label>Agente<select value={agentId} disabled={Boolean(isWorking(activeRun))} onChange={(event) => chooseAgent(Number(event.target.value))}>{proposerAgents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name} · {agent.effectiveProviderName || agent.providerName}</option>)}</select></label>
      <label>Proposta<select value={changeSetId || ""} disabled={Boolean(isWorking(activeRun))} onChange={(event) => chooseChangeSet(event.target.value || null)}><option value="">Nuova proposta</option>{(recentSets.data?.changeSets || []).map((entry) => <option key={entry.id} value={entry.id}>{entry.title || entry.id} · {entry.status}</option>)}</select></label>
      <span data-state={changeSet?.status || "empty"}>{changeSet ? `${changeSet.status} · revisione ${changeSet.revision}` : "Nessuna proposta aperta"}</span></section>
    {recentSets.isError && <p className="form-error" role="alert">Non è stato possibile caricare le proposte recenti.</p>}
    {changeSetQuery.isError && <p className="form-error" role="alert">{(changeSetQuery.error as Error).message}</p>}
    {conflict && <aside className="master-ai-conflict" role="alert"><strong>Conflitto di versione</strong><p>{conflict}</p><button type="button" className="button secondary" disabled={validateSet.isPending} onClick={() => validateSet.mutate()}>Ricarica e convalida di nuovo</button></aside>}

    <div className="master-ai-layout">
      <section className="master-ai-chat panel"><header><h2>Richiesta</h2>{isWorking(activeRun) && <button type="button" className="button secondary small" onClick={() => activeRun && cancelMasterAIExecutionRun(activeRun.id).then((response) => setActiveRun(response.data.run)).catch((error: Error) => notify(error.message, "error"))}>Annulla</button>}</header>
        <div className="master-ai-transcript" ref={transcriptRef} aria-live="polite">{bubbles.length ? bubbles.map((bubble) => <article key={bubble.id} data-role={bubble.role}><strong>{bubble.role === "user" ? "Tu" : "Master AI"}</strong><p>{bubble.text}</p>{bubble.tools.length > 0 && <details><summary>{bubble.tools.length} strumenti usati</summary><ul>{bubble.tools.map((tool, index) => <li key={`${tool.name}-${index}`}>{tool.name}{tool.isError ? " · errore" : ""}</li>)}</ul></details>}</article>) : <div className="master-ai-chat-empty"><p>Descrivi una creazione, modifica, clone o archiviazione. L'agente userà il database come fonte e aggiungerà operazioni alla proposta.</p><button type="button" className="button secondary small" onClick={() => setQuestion("Crea un nuovo oggetto simile a un oggetto esistente, ma chiedimi prima quale usare come modello.")}>Esempio oggetto</button><button type="button" className="button secondary small" onClick={() => setQuestion("Cerca una Skill e proponi una modifica senza applicarla.")}>Esempio Skill</button></div>}
          {isWorking(activeRun) && <article data-role="assistant" className="pending"><strong>Master AI</strong><p>{activeRun?.progress || "Elaborazione…"}</p></article>}</div>
        <form onSubmit={submit}><textarea rows={4} value={question} maxLength={8000} disabled={Boolean(isWorking(activeRun))} placeholder="Esempio: crea un incantesimo chiamato Tocco mortale simile a…" onChange={(event) => setQuestion(event.target.value)} /><button className="button primary" disabled={!question.trim() || !agentId || Boolean(isWorking(activeRun)) || ask.isPending}>Invia richiesta</button></form>
      </section>

      <section className="master-ai-review panel" aria-label="Revisione proposta">{changeSet ? <>
        <OperationList changeSet={changeSet} selectedId={selectedOperation?.id || null} dirty={dirty} onSelect={(id) => { if (!dirty || window.confirm("Scartare le modifiche locali non salvate?")) setSelectedOperationId(id); }}
          onToggle={(operation, selected) => { if (dirty && !window.confirm("La selezione invaliderà la convalida. Continuare?")) return; patchOperation.mutate({ operation, values: { selected } }); }}
          onRemove={(operation) => { if (window.confirm(`Rimuovere l'operazione «${operation.displayLabel}»?`)) removeOperation.mutate(operation); }} />
        <div className="master-ai-operation-detail">{selectedOperation ? <>
          <header><div><p className="eyebrow">{selectedOperation.entityLabel}</p><h2>{actionLabel[selectedOperation.action]} · {selectedOperation.displayLabel}</h2></div><span data-state={selectedOperation.status}>{statusLabel[selectedOperation.status] || selectedOperation.status}</span></header>
          {selectedOperation.errors.length > 0 && <aside className="master-ai-problems error" role="alert" aria-live="polite"><strong>Errori</strong><ul>{selectedOperation.errors.map((error, index) => <li key={`${error.code}-${index}`}>{error.message}</li>)}</ul></aside>}
          {selectedOperation.warnings.length > 0 && <aside className="master-ai-problems warning" aria-live="polite"><strong>Avvisi</strong><ul>{selectedOperation.warnings.map((warning, index) => <li key={`${warning.code}-${index}`}>{warning.message}</li>)}</ul></aside>}
          {selectedOperation.action !== "archive" && <><ProposalFieldRenderer fields={selectedOperation.fields} values={localValues} errors={selectedOperation.errors} disabled={!changeSet.canEdit || saveOperation.isPending} onChange={(name, value) => setLocalValues((current) => ({ ...current, [name]: value }))} />
            <div className="master-ai-draft-actions"><span>{dirty ? "Modifiche locali non salvate" : "Bozza sincronizzata"}</span><button type="button" className="button primary" disabled={!dirty || saveOperation.isPending || !changeSet.canEdit} onClick={() => saveOperation.mutate()}>Salva bozza operazione</button></div></>}
          <ProposalDiff operation={selectedOperation} />
        </> : <p className="empty-copy">Seleziona un'operazione.</p>}</div>
      </> : <div className="master-ai-no-proposal"><h2>Nessuna proposta aperta</h2><p>Invia una richiesta al Master AI oppure apri una proposta recente. Le operazioni compariranno qui per la revisione umana.</p></div>}</section>
    </div>

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
  </main>;
}

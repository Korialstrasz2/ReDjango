import { type FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  askAssistant,
  cancelAIExecutionRun,
  generateAIImage,
  getAIExecutionRun,
  getData,
} from "../../lib/api";
import type {
  AIChatResult,
  AIConversationBubble,
  AIExecutionRun,
  AIHistoryEntry,
  AIWorkspaceData,
  MediaAsset,
} from "../../lib/types";

type Props = { notify: (message: string, kind?: "success" | "error" | "info") => void };
type Bubble = AIConversationBubble;

const bubbleId = () => globalThis.crypto?.randomUUID?.() ?? `b-${Date.now()}-${Math.random().toString(16).slice(2)}`;
const isWorking = (run: AIExecutionRun | null) => run?.status === "queued" || run?.status === "running";

function InlineText({ children }: { children: string }) {
  const parts = children.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean);
  return <>{parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    return <span key={index}>{part}</span>;
  })}</>;
}

function AnswerText({ text }: { text: string }) {
  const lines = text.split(/\r?\n/);
  const rendered: ReactNode[] = [];
  let inCode = false;
  let code: string[] = [];
  lines.forEach((line, index) => {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        rendered.push(<pre key={`code-${index}`}><code>{code.join("\n")}</code></pre>);
        code = [];
      }
      inCode = !inCode;
      return;
    }
    if (inCode) {
      code.push(line);
      return;
    }
    if (!line.trim()) {
      rendered.push(<span className="ai-markdown-gap" key={`gap-${index}`} />);
    } else if (/^#{1,3}\s/.test(line)) {
      rendered.push(<h4 key={index}><InlineText>{line.replace(/^#{1,3}\s+/, "")}</InlineText></h4>);
    } else if (/^[-*]\s/.test(line)) {
      rendered.push(<p className="ai-markdown-list-item" key={index}><span aria-hidden="true">•</span><InlineText>{line.replace(/^[-*]\s+/, "")}</InlineText></p>);
    } else {
      rendered.push(<p key={index}><InlineText>{line}</InlineText></p>);
    }
  });
  if (code.length) rendered.push(<pre key="code-final"><code>{code.join("\n")}</code></pre>);
  return <div className="ai-answer-text">{rendered}</div>;
}

export function AITool({ notify }: Props) {
  const workspace = useQuery({ queryKey: ["aiWorkspace"], queryFn: () => getData<AIWorkspaceData>("/api/ai/") });
  const transcriptRef = useRef<HTMLDivElement>(null);
  const handledRun = useRef("");
  const hydrated = useRef(false);
  const [mode, setMode] = useState<"chat" | "image">("chat");
  const [question, setQuestion] = useState("");
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [history, setHistory] = useState<AIHistoryEntry[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [agentId, setAgentId] = useState<number | "">("");
  const [activeProvider, setActiveProvider] = useState<AIChatResult["provider"] | null>(null);
  const [activeRun, setActiveRun] = useState<AIExecutionRun | null>(null);
  const [lastFailedMessage, setLastFailedMessage] = useState("");
  const [prompt, setPrompt] = useState("");
  const [imageProviderId, setImageProviderId] = useState<number | "">("");
  const [size, setSize] = useState("");
  const [quality, setQuality] = useState("");
  const [generated, setGenerated] = useState<MediaAsset | null>(null);
  const [proposalAlert, setProposalAlert] = useState(false);
  const proposerAgentIds = useMemo(
    () => new Set((workspace.data?.agents ?? []).filter((agent) => agent.mode === "proposer" || agent.canProposeChanges).map((agent) => agent.id)),
    [workspace.data?.agents],
  );

  useEffect(() => {
    const node = transcriptRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [bubbles, activeRun?.progress]);

  useEffect(() => {
    if (hydrated.current || !workspace.data) return;
    hydrated.current = true;
    const restoredRun = workspace.data.activeRun;
    if (restoredRun) {
      setActiveRun(restoredRun);
      if (restoredRun.kind === "image") {
        setMode("image");
        setPrompt(restoredRun.request.prompt);
      }
    }
    const recent = restoredRun?.conversation || workspace.data.conversations[0];
    if (recent) {
      setConversationId(recent.id);
      setAgentId(recent.agentId || "");
      setHistory(recent.history);
      const pendingMessage = restoredRun?.kind === "chat" ? restoredRun.request.message : "";
      const lastBubble = recent.bubbles.at(-1);
      setBubbles(pendingMessage && !(lastBubble?.role === "user" && lastBubble.text === pendingMessage)
        ? [...recent.bubbles, { id: bubbleId(), role: "user", text: pendingMessage, tools: [] }]
        : recent.bubbles);
      if (proposerAgentIds.has(recent.agentId || -1)) setProposalAlert(true);
    }
  }, [workspace.data]);

  useEffect(() => {
    if (!activeRun || !isWorking(activeRun)) return;
    const timer = window.setTimeout(() => {
      void getAIExecutionRun(activeRun.id)
        .then((response) => setActiveRun(response.data.run))
        .catch((error: Error) => {
          notify(error.message, "error");
          setActiveRun(null);
        });
    }, 800);
    return () => window.clearTimeout(timer);
  }, [activeRun, notify]);

  useEffect(() => {
    if (!activeRun || isWorking(activeRun) || handledRun.current === activeRun.id) return;
    handledRun.current = activeRun.id;
    if (activeRun.status === "completed" && activeRun.kind === "chat") {
      const result = activeRun.result as AIChatResult;
      setHistory(result.history);
      setActiveProvider(result.provider);
      if (activeRun.conversation) {
        setConversationId(activeRun.conversation.id);
        setBubbles(activeRun.conversation.bubbles);
      } else {
        setBubbles((current) => [...current, { id: bubbleId(), role: "assistant", text: result.reply, tools: result.toolTrace }]);
      }
      if (result.changeSet) setProposalAlert(true);
      setLastFailedMessage("");
      void workspace.refetch();
    } else if (activeRun.status === "completed" && activeRun.kind === "image") {
      const result = activeRun.result as { asset: MediaAsset };
      setGenerated(result.asset);
      notify("Immagine generata e aggiunta all'archivio.");
    } else if (activeRun.status === "failed") {
      const message = activeRun.error.message || "L'esecuzione AI non è riuscita.";
      notify(message, "error");
      if (activeRun.kind === "chat") {
        setBubbles((current) => [...current, { id: bubbleId(), role: "assistant", text: `⚠ ${message}`, tools: [] }]);
      }
    } else if (activeRun.status === "cancelled") {
      notify("Esecuzione annullata.", "info");
    }
    setActiveRun(null);
  }, [activeRun, notify, workspace]);

  const ask = useMutation({
    mutationFn: (message: string) => askAssistant({ message, history, agentId: agentId || undefined, conversationId: conversationId || undefined }),
    onSuccess: (result) => setActiveRun(result.data.run),
    onError: (error: Error) => {
      notify(error.message, "error");
      setLastFailedMessage((current) => current || question.trim());
      setBubbles((current) => [...current, { id: bubbleId(), role: "assistant", text: `⚠ ${error.message}`, tools: [] }]);
    },
  });

  const draw = useMutation({
    mutationFn: (values: { selectedSize: string; selectedQuality: string }) => generateAIImage({
      prompt,
      providerId: imageProviderId || undefined,
      size: values.selectedSize,
      quality: values.selectedQuality,
    }),
    onSuccess: (result) => setActiveRun(result.data.run),
    onError: (error: Error) => notify(error.message, "error"),
  });

  const startQuestion = (message: string, appendBubble = true) => {
    const cleaned = message.trim();
    if (!cleaned || ask.isPending || isWorking(activeRun)) return;
    setLastFailedMessage(cleaned);
    setBubbles((current) => {
      const withoutError = !appendBubble && current.at(-1)?.role === "assistant" && current.at(-1)?.text.startsWith("⚠")
        ? current.slice(0, -1)
        : current;
      return appendBubble ? [...withoutError, { id: bubbleId(), role: "user", text: cleaned, tools: [] }] : withoutError;
    });
    setQuestion("");
    ask.mutate(cleaned);
  };

  const copyAnswer = (text: string) => {
    if (!navigator.clipboard) {
      notify("Copia non disponibile in questo browser.", "error");
      return;
    }
    void navigator.clipboard.writeText(text)
      .then(() => notify("Risposta copiata."))
      .catch(() => notify("Non è stato possibile copiare la risposta.", "error"));
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    startQuestion(question);
  };

  const reset = () => {
    setHistory([]);
    setBubbles([]);
    setConversationId(null);
    setActiveProvider(null);
    setLastFailedMessage("");
    setProposalAlert(false);
  };

  const closeProposalAlert = () => {
    setProposalAlert(false);
    if (agentId && proposerAgentIds.has(agentId)) {
      reset();
      setAgentId("");
      notify("Conversazione di proposta chiusa: riparti dal workspace Master AI.", "info");
    }
  };

  const openConversation = (id: number) => {
    const conversation = workspace.data?.conversations.find((entry) => entry.id === id);
    if (!conversation || isWorking(activeRun)) return;
    if (proposerAgentIds.has(conversation.agentId || -1)) {
      setProposalAlert(true);
      return;
    }
    setConversationId(conversation.id);
    setAgentId(conversation.agentId || "");
    setHistory(conversation.history);
    setBubbles(conversation.bubbles);
    setActiveProvider(null);
  };

  const cancelRun = () => {
    if (!activeRun || !isWorking(activeRun)) return;
    void cancelAIExecutionRun(activeRun.id)
      .then((response) => setActiveRun(response.data.run))
      .catch((error: Error) => notify(error.message, "error"));
  };

  if (workspace.isLoading) return <p className="empty-copy">Risveglio dell'assistente…</p>;
  if (workspace.isError) return <p className="form-error">{(workspace.error as Error).message}</p>;

  const data = workspace.data!;
  const readOnlyAgents = data.agents.filter((agent) => !(agent.mode === "proposer" || agent.canProposeChanges));
  const selectedAgent = readOnlyAgents.find((entry) => entry.id === agentId) || readOnlyAgents[0] || null;
  const defaultProvider = data.chatProviders.find((entry) => entry.isDefault) || data.chatProviders[0] || null;
  const defaultImageProvider = data.imageProviders.find((entry) => entry.isDefault) || data.imageProviders[0] || null;
  const selectedImageProvider = data.imageProviders.find((entry) => entry.id === imageProviderId) || defaultImageProvider;
  const imageGeneration = selectedImageProvider?.imageGeneration;
  const selectedSize = imageGeneration?.sizes.some((entry) => entry.value === size) ? size : (imageGeneration?.defaultSize || "");
  const selectedQuality = imageGeneration?.qualities.some((entry) => entry.value === quality) ? quality : (imageGeneration?.defaultQuality || "");
  const providerLabel = activeProvider
    ? `${activeProvider.name}${activeProvider.model ? ` · ${activeProvider.model}` : ""}`
    : selectedAgent?.effectiveProviderName
      ? `${selectedAgent.effectiveProviderName}${selectedAgent.effectiveModel ? ` · ${selectedAgent.effectiveModel}` : ""}`
      : defaultProvider
        ? `${defaultProvider.name}${defaultProvider.model ? ` · ${defaultProvider.model}` : ""}`
        : "non disponibile";

  return <><div className="ai-tool" data-component-type="panel" data-theme="parchment">
    <nav className="ai-tabs" role="tablist" aria-label="Modalità assistente" data-component-type="tabset" data-theme="gold">
      <button type="button" role="tab" aria-selected={mode === "chat"} className={mode === "chat" ? "active" : ""} onClick={() => setMode("chat")}>Domande</button>
      <button type="button" role="tab" aria-selected={mode === "image"} className={mode === "image" ? "active" : ""} onClick={() => setMode("image")} disabled={!data.readiness.images || !data.canManage}>Immagini</button>
      {data.canManage && <Link className="ai-tabs-link" to="/tools/ai">Gestione AI</Link>}
    </nav>

    {mode === "chat" ? data.readiness.chat ? <section className="ai-chat" role="tabpanel" aria-label="Domande all'assistente">
      <div className="ai-chat-layout">
        <aside className="ai-conversation-list" aria-label="Conversazioni recenti">
          <header><strong>Ultime conversazioni</strong><small>Massimo 3</small></header>
          <button type="button" className={!conversationId ? "active" : ""} onClick={reset} disabled={Boolean(isWorking(activeRun))}>+ Nuova</button>
          {data.conversations.map((conversation) => <button key={conversation.id} type="button" className={conversation.id === conversationId ? "active" : ""} onClick={() => openConversation(conversation.id)} disabled={Boolean(isWorking(activeRun))}>
            <strong>{conversation.title}</strong>
            <small>{new Date(conversation.updatedAt).toLocaleString("it", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</small>
          </button>)}
        </aside>
        <div className="ai-chat-main">
          <div className="ai-transcript" ref={transcriptRef} aria-live="polite">
            {bubbles.length ? bubbles.map((bubble) => <article key={bubble.id} className={`ai-bubble ${bubble.role}`}>
              {bubble.tools.length > 0 && <details className="ai-tool-trace">
                <summary>{bubble.tools.length} {bubble.tools.length === 1 ? "fonte consultata" : "fonti consultate"}</summary>
                <ul>{bubble.tools.map((entry, index) => <li key={`${entry.name}-${index}`} data-state={entry.isError ? "error" : "ok"}>
                  <strong>{entry.name}</strong>{Object.keys(entry.arguments || {}).length > 0 && <code>{JSON.stringify(entry.arguments)}</code>}
                </li>)}</ul>
              </details>}
              {bubble.role === "assistant" ? <AnswerText text={bubble.text} /> : <p>{bubble.text}</p>}
              {bubble.role === "assistant" && <footer><button type="button" onClick={() => copyAnswer(bubble.text)}>Copia</button></footer>}
            </article>) : <div className="ai-suggestions">
              <p className="muted-copy">{selectedAgent?.description || "Scegli un agente configurato per iniziare."}</p>
              <div className="button-row">{["Quanto pesa una spada lunga in acciaio?", "Come funziona la stanchezza?", "Che reputazione abbiamo con le fazioni?"].map((example) => <button key={example} type="button" className="button secondary small" onClick={() => setQuestion(example)}>{example}</button>)}</div>
            </div>}
            {isWorking(activeRun) && <article className="ai-bubble assistant pending"><p>{activeRun?.progress || "Elaborazione…"}</p><button type="button" className="button secondary small" onClick={cancelRun} disabled={activeRun?.cancelRequested}>{activeRun?.cancelRequested ? "Annullamento…" : "Annulla"}</button></article>}
          </div>

          <form className="ai-composer" onSubmit={submit}>
            <label className="sr-only" htmlFor="ai-question">Domanda per l'assistente</label>
            <textarea id="ai-question" rows={2} value={question} maxLength={4000} placeholder="Fai una domanda sulla campagna…" onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(event); }
            }} />
            <div className="ai-composer-actions">
              <small className="muted-copy" title="Provider e modello risolti per questa conversazione">Provider: {providerLabel}</small>
              <label className="ai-provider-picker"><span className="sr-only">Agente</span><select value={agentId} disabled={Boolean(isWorking(activeRun))} onChange={(event) => { setAgentId(event.target.value ? Number(event.target.value) : ""); reset(); }}>
                <option value="">Agente predefinito</option>
                {readOnlyAgents.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}{entry.effectiveModel ? ` · ${entry.effectiveModel}` : ""}</option>)}
              </select></label>
              {lastFailedMessage && !ask.isPending && !isWorking(activeRun) && <button type="button" className="button secondary small" onClick={() => startQuestion(lastFailedMessage, false)}>Riprova</button>}
              <button className="button primary small" disabled={ask.isPending || Boolean(isWorking(activeRun)) || !question.trim() || proposalAlert}>{ask.isPending || isWorking(activeRun) ? "…" : "Chiedi"}</button>
            </div>
          </form>
        </div>
      </div>
    </section> : <div className="ai-empty" data-component-type="panel" data-theme="parchment"><h3>Chat non pronta</h3><p className="muted-copy">Serve almeno un agente con un provider chat attivo e completo.</p>{data.canManage ? <Link className="button primary" to="/tools/ai">Apri Gestione AI</Link> : <p className="muted-copy">Chiedi a un Master di completare la configurazione.</p>}</div>
    : <section className="ai-image" role="tabpanel" aria-label="Generazione immagini">
      <label>Descrizione<textarea rows={3} value={prompt} maxLength={2000} placeholder="Un portale daedrico nella nebbia, luce ambrata…" onChange={(event) => setPrompt(event.target.value)} /></label>
      <div className="ai-image-options">
        <label>Provider<select value={imageProviderId} onChange={(event) => { const providerId = event.target.value ? Number(event.target.value) : ""; const provider = data.imageProviders.find((entry) => entry.id === providerId) || defaultImageProvider; setImageProviderId(providerId); setSize(provider?.imageGeneration?.defaultSize || ""); setQuality(provider?.imageGeneration?.defaultQuality || ""); }}>
          <option value="">Predefinito</option>{data.imageProviders.map((entry) => <option key={entry.id} value={entry.id}>{entry.name} · {entry.model}</option>)}
        </select></label>
        <label>Formato<select value={selectedSize} onChange={(event) => setSize(event.target.value)} disabled={!imageGeneration}>{imageGeneration?.sizes.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>
        <label>Qualità<select value={selectedQuality} onChange={(event) => setQuality(event.target.value)} disabled={!imageGeneration}>{imageGeneration?.qualities.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>
      </div>
      <p className="muted-copy">La generazione prosegue in background e può essere annullata. Il risultato entra nell'Archivio immagini.</p>
      {isWorking(activeRun) && activeRun?.kind === "image" ? <div className="button-row"><span>{activeRun.progress}</span><button type="button" className="button secondary" onClick={cancelRun} disabled={activeRun.cancelRequested}>Annulla</button></div> : <button type="button" className="button primary" disabled={draw.isPending || Boolean(isWorking(activeRun)) || !prompt.trim()} onClick={() => draw.mutate({ selectedSize, selectedQuality })}>{draw.isPending ? "Avvio…" : "Genera immagine"}</button>}
      {generated && <figure className="ai-image-result"><img src={generated.url} alt={generated.title} /><figcaption>{generated.title}</figcaption></figure>}
    </section>}
    {proposalAlert && createPortal(
      <div className="master-ai-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) closeProposalAlert(); }}>
        <section className="master-ai-dialog" role="dialog" aria-modal="true" aria-labelledby="ai-proposal-alert-title">
          <h2 id="ai-proposal-alert-title">Proposta creata, ma non revisionabile qui</h2>
          <p>Impossibile creare proposte in questa interfaccia: questa chat non ha il pannello di revisione.</p>
          <p>Rifai la tua domanda da <Link to="/tools/master-ai" onClick={closeProposalAlert}><strong>QUI</strong></Link>: la proposta già creata ti aspetta nel selettore «Proposta» del workspace Master AI.</p>
          <footer>
            <button type="button" className="button secondary" onClick={closeProposalAlert}>Chiudi</button>
            <Link className="button primary" to="/tools/master-ai" onClick={closeProposalAlert}>Apri Master AI</Link>
          </footer>
        </section>
      </div>,
      document.body,
    )}
    </div>
  </>;
}

import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import { askAssistant, generateAIImage, getData } from "../../lib/api";
import type { AIChatResult, AIHistoryEntry, AIToolTraceEntry, AIWorkspaceData, MediaAsset } from "../../lib/types";

type Props = { notify: (message: string, kind?: "success" | "error" | "info") => void };

type Bubble = { id: string; role: "user" | "assistant"; text: string; tools: AIToolTraceEntry[] };

const bubbleId = () => globalThis.crypto?.randomUUID?.() ?? `b-${Date.now()}-${Math.random().toString(16).slice(2)}`;

export function AITool({ notify }: Props) {
  const workspace = useQuery({ queryKey: ["aiWorkspace"], queryFn: () => getData<AIWorkspaceData>("/api/ai/") });
  const transcriptRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<"chat" | "image">("chat");
  const [question, setQuestion] = useState("");
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  // La memoria resta client-side e provider-neutral; il backend non conserva conversazioni.
  const [history, setHistory] = useState<AIHistoryEntry[]>([]);
  const [agentId, setAgentId] = useState<number | "">("");
  const [prompt, setPrompt] = useState("");
  const [imageProviderId, setImageProviderId] = useState<number | "">("");
  const [size, setSize] = useState("1024x1024");
  const [quality, setQuality] = useState("medium");
  const [generated, setGenerated] = useState<MediaAsset | null>(null);

  useEffect(() => {
    const node = transcriptRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [bubbles]);

  const ask = useMutation({
    mutationFn: (message: string) => askAssistant({ message, history, agentId: agentId || undefined }),
    onSuccess: (result) => {
      const data: AIChatResult = result.data;
      setHistory(data.history);
      setBubbles((current) => [...current, { id: bubbleId(), role: "assistant", text: data.reply, tools: data.toolTrace }]);
    },
    onError: (error: Error) => {
      notify(error.message, "error");
      setBubbles((current) => [...current, { id: bubbleId(), role: "assistant", text: `⚠ ${error.message}`, tools: [] }]);
    },
  });

  const draw = useMutation({
    mutationFn: () => generateAIImage({ prompt, providerId: imageProviderId || undefined, size, quality }),
    onSuccess: (result) => {
      setGenerated(result.data.asset);
      notify(result.events[0]?.message || "Immagine generata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const message = question.trim();
    if (!message || ask.isPending) return;
    setBubbles((current) => [...current, { id: bubbleId(), role: "user", text: message, tools: [] }]);
    setQuestion("");
    ask.mutate(message);
  };

  const reset = () => {
    setHistory([]);
    setBubbles([]);
  };

  if (workspace.isLoading) return <p className="empty-copy">Risveglio dell'assistente…</p>;
  if (workspace.isError) return <p className="form-error">{(workspace.error as Error).message}</p>;

  const data = workspace.data!;
  const selectedAgent = data.agents.find((entry) => entry.id === agentId) || data.agents[0] || null;
  if (!data.ready) {
    return <div className="ai-empty" data-component-type="panel" data-theme="parchment">
      <h3>Nessun provider configurato</h3>
      <p className="muted-copy">L'assistente ha bisogno di un provider con una chiave API valida.</p>
      {data.canManage
        ? <Link className="button primary" to="/tools/ai">Apri Gestione AI</Link>
        : <p className="muted-copy">Chiedi a un Master di configurarlo da Gestione AI.</p>}
    </div>;
  }

  return <div className="ai-tool" data-component-type="panel" data-theme="parchment">
    <nav className="ai-tabs" role="tablist" aria-label="Modalità assistente" data-component-type="tabset" data-theme="gold">
      <button type="button" role="tab" aria-selected={mode === "chat"} className={mode === "chat" ? "active" : ""} onClick={() => setMode("chat")}>Domande</button>
      <button type="button" role="tab" aria-selected={mode === "image"} className={mode === "image" ? "active" : ""} onClick={() => setMode("image")} disabled={!data.imageProviders.length || !data.canManage}>Immagini</button>
      {data.canManage && <Link className="ai-tabs-link" to="/tools/ai">Gestione AI</Link>}
    </nav>

    {mode === "chat" ? <section className="ai-chat" role="tabpanel" aria-label="Domande all'assistente">
      <div className="ai-transcript" ref={transcriptRef} aria-live="polite">
        {bubbles.length ? bubbles.map((bubble) => <article key={bubble.id} className={`ai-bubble ${bubble.role}`}>
          {bubble.tools.length > 0 && <ul className="ai-tool-trace" aria-label="Strumenti consultati">
            {bubble.tools.map((entry, index) => <li key={`${entry.name}-${index}`} data-state={entry.isError ? "error" : "ok"}>
              <span aria-hidden="true">{entry.isError ? "⚠" : "◆"}</span>{entry.name}
            </li>)}
          </ul>}
          <p>{bubble.text}</p>
        </article>) : <div className="ai-suggestions">
          <p className="muted-copy">{selectedAgent?.description || "Scegli un agente configurato per iniziare."}</p>
          <div className="button-row">
            {["Quanto pesa una spada lunga in acciaio?", "Come funziona la stanchezza?", "Che reputazione abbiamo con le fazioni?"].map((example) => <button key={example} type="button" className="button secondary small" onClick={() => setQuestion(example)}>{example}</button>)}
          </div>
        </div>}
        {ask.isPending && <article className="ai-bubble assistant pending"><p>Sto consultando la campagna…</p></article>}
      </div>

      <form className="ai-composer" onSubmit={submit}>
        <label className="sr-only" htmlFor="ai-question">Domanda per l'assistente</label>
        <textarea
          id="ai-question"
          rows={2}
          value={question}
          maxLength={4000}
          placeholder="Fai una domanda sulla campagna…"
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit(event);
            }
          }}
        />
        <div className="ai-composer-actions">
          <label className="ai-provider-picker">
            <span className="sr-only">Agente</span>
            <select value={agentId} onChange={(event) => {
              setAgentId(event.target.value ? Number(event.target.value) : "");
              reset();
            }}>
              <option value="">Agente predefinito</option>
              {data.agents.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}{entry.model ? ` · ${entry.model}` : ""}</option>)}
            </select>
          </label>
          {bubbles.length > 0 && <button type="button" className="button secondary small" onClick={reset} disabled={ask.isPending}>Nuova conversazione</button>}
          <button className="button primary small" disabled={ask.isPending || !question.trim()}>{ask.isPending ? "…" : "Chiedi"}</button>
        </div>
      </form>
    </section> : <section className="ai-image" role="tabpanel" aria-label="Generazione immagini">
      <label>Descrizione<textarea rows={3} value={prompt} maxLength={2000} placeholder="Un portale daedrico nella nebbia, luce ambrata…" onChange={(event) => setPrompt(event.target.value)} /></label>
      <div className="ai-image-options">
        <label>Provider<select value={imageProviderId} onChange={(event) => setImageProviderId(event.target.value ? Number(event.target.value) : "")}>
          <option value="">Predefinito</option>
          {data.imageProviders.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}
        </select></label>
        <label>Formato<select value={size} onChange={(event) => setSize(event.target.value)}>
          {data.imageSizes.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
        </select></label>
        <label>Qualità<select value={quality} onChange={(event) => setQuality(event.target.value)}>
          {data.imageQualities.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
        </select></label>
      </div>
      <p className="muted-copy">L'immagine entra nell'Archivio immagini con il prompt registrato.</p>
      <button type="button" className="button primary" disabled={draw.isPending || !prompt.trim()} onClick={() => draw.mutate()}>{draw.isPending ? "Generazione…" : "Genera immagine"}</button>
      {generated && <figure className="ai-image-result">
        <img src={generated.url} alt={generated.title} />
        <figcaption>{generated.title}</figcaption>
      </figure>}
    </section>}
  </div>;
}

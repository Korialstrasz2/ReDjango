import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getData, saveAIProvider } from "../../lib/api";
import type { AIManagedProvider, AIManagementData } from "../../lib/types";
import { useApp } from "../../App";

type Draft = {
  name: string;
  baseUrl: string;
  model: string;
  secret: string;
  maxTokens: string;
  effort: string;
  disableTools: boolean;
  isEnabled: boolean;
};

const draftFrom = (provider: AIManagedProvider): Draft => ({
  name: provider.name,
  baseUrl: provider.baseUrl,
  model: provider.model,
  secret: "",
  maxTokens: provider.maxTokens ? String(provider.maxTokens) : "",
  effort: provider.effort || "",
  disableTools: provider.disableTools,
  isEnabled: provider.isEnabled,
});

export function AIManagementPage() {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const management = useQuery({ queryKey: ["aiManagement"], queryFn: () => getData<AIManagementData>("/api/ai/providers/") });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);

  const providers = management.data?.providers || [];
  const selected = providers.find((entry) => entry.id === selectedId) || providers[0] || null;

  useEffect(() => {
    if (selected && (selectedId !== selected.id || draft === null)) {
      setSelectedId(selected.id);
      setDraft(draftFrom(selected));
    }
  }, [draft, selected, selectedId]);

  const apply = (data: AIManagementData, message: string) => {
    queryClient.setQueryData(["aiManagement"], data);
    void queryClient.invalidateQueries({ queryKey: ["aiWorkspace"] });
    notify(message);
  };

  const save = useMutation({
    mutationFn: (values: Record<string, unknown>) => saveAIProvider({ values }),
    onSuccess: (result) => {
      apply(result.data, result.events[0]?.message || "Provider aggiornato.");
      setDraft((current) => current && { ...current, secret: "" });
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const probe = useMutation({
    mutationFn: (id: number) => saveAIProvider({ test: id }),
    onSuccess: (result) => apply(result.data, result.data.test?.message || "Prova completata."),
    onError: (error: Error) => notify(error.message, "error"),
  });

  if (management.isLoading) return <div className="page"><p className="empty-copy">Caricamento della configurazione…</p></div>;
  if (management.isError) return <div className="page"><p className="form-error">{(management.error as Error).message}</p></div>;
  if (!management.data?.canManage) return <div className="page"><p className="form-error">Questa pagina è riservata a Master e Amministratori.</p></div>;

  const submit = () => {
    if (!selected || !draft) return;
    save.mutate({
      id: selected.id,
      name: draft.name,
      baseUrl: draft.baseUrl,
      model: draft.model,
      isEnabled: draft.isEnabled,
      maxTokens: draft.maxTokens ? Number(draft.maxTokens) : null,
      effort: draft.effort,
      disableTools: draft.disableTools,
      ...(draft.secret ? { secret: draft.secret } : {}),
    });
  };

  const chat = providers.filter((entry) => entry.purpose === "chat");
  const images = providers.filter((entry) => entry.purpose === "image");

  return <div className="page ai-management">
    <header className="page-header">
      <div><p className="eyebrow">Strumenti</p><h1>Gestione AI</h1></div>
    </header>

    <section className="panel" data-component-type="panel" data-theme="gold">
      <p className="muted-copy">
        Le chiavi si scrivono e non si rileggono: restano cifrate nel database e non vengono mai inviate all'interfaccia.
        L'assistente esegue gli strumenti con i permessi di chi fa la domanda, quindi non può mostrare a un giocatore
        quello che la sua pagina gli nasconde.
      </p>
    </section>

    <div className="ai-management-layout">
      <aside className="ai-provider-list" aria-label="Provider configurati">
        {[["Chat", chat], ["Immagini", images]].map(([label, entries]) => <section key={String(label)}>
          <h2>{String(label)}</h2>
          {(entries as AIManagedProvider[]).map((entry) => <button
            key={entry.id}
            type="button"
            className={entry.id === selected?.id ? "active" : ""}
            onClick={() => { setSelectedId(entry.id); setDraft(draftFrom(entry)); }}
          >
            <strong>{entry.name}</strong>
            <span>{entry.model || "modello non impostato"}</span>
            <small data-state={entry.isEnabled ? "on" : "off"}>
              {entry.isEnabled ? "attivo" : "disattivato"}{entry.hasSecret ? " · chiave presente" : entry.authStrategy === "none" ? " · senza chiave" : " · chiave mancante"}
            </small>
          </button>)}
        </section>)}
      </aside>

      {selected && draft && <section className="ai-provider-form panel" data-component-type="panel" data-theme="parchment">
        <header><div><p className="eyebrow">{selected.kind}</p><h2>{selected.name}</h2></div></header>
        <p className="muted-copy">{selected.description}</p>

        <label>Nome<input value={draft.name} maxLength={120} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
        <label>Indirizzo API<input value={draft.baseUrl} placeholder="https://api.esempio.com/v1" onChange={(event) => setDraft({ ...draft, baseUrl: event.target.value })} /></label>
        <label>Modello
          <input list={`ai-models-${selected.id}`} value={draft.model} onChange={(event) => setDraft({ ...draft, model: event.target.value })} />
          <datalist id={`ai-models-${selected.id}`}>
            {selected.suggestedModels.map((model) => <option key={model} value={model} />)}
          </datalist>
        </label>

        {selected.authStrategy !== "none" && <label>
          Chiave API
          <input
            type="password"
            autoComplete="off"
            value={draft.secret}
            placeholder={selected.hasSecret ? "Configurata — scrivi per sostituirla" : "Incolla la chiave"}
            onChange={(event) => setDraft({ ...draft, secret: event.target.value })}
          />
          <small className="muted-copy">
            Serve una chiave della piattaforma del provider. L'accesso con l'account ChatGPT non è utilizzabile da un'applicazione multiutente come questa.
          </small>
        </label>}

        <div className="ai-provider-options">
          <label>Token massimi<input type="number" min={256} max={32000} value={draft.maxTokens} onChange={(event) => setDraft({ ...draft, maxTokens: event.target.value })} /></label>
          {selected.kind === "anthropic" && <label>Impegno
            <select value={draft.effort} onChange={(event) => setDraft({ ...draft, effort: event.target.value })}>
              <option value="">Predefinito</option>
              {["low", "medium", "high", "xhigh", "max"].map((level) => <option key={level} value={level}>{level}</option>)}
            </select>
          </label>}
        </div>

        <label className="ai-toggle"><input type="checkbox" checked={draft.isEnabled} onChange={(event) => setDraft({ ...draft, isEnabled: event.target.checked })} /><span>Attivo</span></label>
        {selected.purpose === "chat" && <label className="ai-toggle">
          <input type="checkbox" checked={draft.disableTools} onChange={(event) => setDraft({ ...draft, disableTools: event.target.checked })} />
          <span>Disattiva gli strumenti<small className="muted-copy">Necessario con i modelli di ragionamento che non accettano le funzioni.</small></span>
        </label>}

        <div className="button-row">
          <button type="button" className="button primary" disabled={save.isPending} onClick={submit}>Salva</button>
          <button type="button" className="button secondary" disabled={probe.isPending || !selected.isEnabled} onClick={() => probe.mutate(selected.id)}>{probe.isPending ? "Prova in corso…" : "Prova connessione"}</button>
        </div>
        {management.data.test && <p className={management.data.test.ok ? "muted-copy" : "form-error"}>{management.data.test.message}</p>}

        {selected.purpose === "chat" && <details className="inline-admin-tool">
          <summary>Strumenti disponibili all'assistente</summary>
          <ul className="ai-tool-list">
            {management.data.tools.map((tool) => <li key={tool.name}><strong>{tool.name}</strong><span>{tool.description}</span></li>)}
          </ul>
        </details>}
      </section>}
    </div>
  </div>;
}

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getData, refreshAIProviderModels, saveAIProvider, saveNpcGeneration } from "../../lib/api";
import type { AIManagedAgent, AIManagedProvider, AIManagementData, NpcGenerationConfig } from "../../lib/types";
import { useApp } from "../../App";

type ProviderDraft = {
  name: string; baseUrl: string; model: string; secret: string; maxTokens: string;
  effort: string; verbosity: string; disableTools: boolean; isEnabled: boolean; isDefault: boolean;
};
type AgentDraft = {
  name: string; description: string; instructions: string; minimumRole: "user" | "master" | "admin";
  providerId: number | null; toolNames: string[]; maxIterations: number; routingMode: "off" | "auto";
  isEnabled: boolean; isDefault: boolean;
};

const providerDraft = (item: AIManagedProvider): ProviderDraft => ({
  name: item.name, baseUrl: item.baseUrl, model: item.model, secret: "",
  maxTokens: item.maxTokens ? String(item.maxTokens) : "", effort: item.effort || "",
  verbosity: item.verbosity || "", disableTools: item.disableTools, isEnabled: item.isEnabled,
  isDefault: item.isDefault,
});
const agentDraft = (item: AIManagedAgent): AgentDraft => ({
  name: item.name, description: item.description, instructions: item.instructions,
  minimumRole: item.minimumRole, providerId: item.providerId,
  toolNames: item.configuredToolNames, maxIterations: item.maxIterations, routingMode: item.routingMode,
  isEnabled: item.isEnabled, isDefault: item.isDefault,
});
const emptyAgent = (): AgentDraft => ({
  name: "Nuovo agente", description: "", instructions: "", minimumRole: "user",
  providerId: null, toolNames: [], maxIterations: 6, routingMode: "auto", isEnabled: true, isDefault: false,
});

const SCOPE_LABELS: Record<string, string> = {
  personaggi: "Personaggi", cataloghi: "Cataloghi", mercato: "Mercato", campagna: "Campagna",
  dadi: "Dadi", combattimento: "Combattimento", regole: "Regole", gestione: "Gestione",
};
const REASONING_EFFORTS = ["none", "low", "medium", "high", "xhigh", "max"];
const VERBOSITY_OPTIONS = ["low", "medium", "high"];

export function AIManagementPage() {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const management = useQuery({ queryKey: ["aiManagement"], queryFn: () => getData<AIManagementData>("/api/ai/providers/") });
  const [section, setSection] = useState<"agents" | "providers" | "npc">("agents");
  const [npc, setNpc] = useState<NpcGenerationConfig | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState<number | null>(null);
  const [agent, setAgent] = useState<AgentDraft | null>(null);
  const [provider, setProvider] = useState<ProviderDraft | null>(null);

  const agents = management.data?.agents || [];
  const providers = management.data?.providers || [];
  const isNewAgent = selectedAgentId === -1;
  const selectedAgent = isNewAgent ? null : agents.find((item) => item.id === selectedAgentId) || agents[0] || null;
  const selectedProvider = providers.find((item) => item.id === selectedProviderId) || providers[0] || null;

  useEffect(() => {
    if (!isNewAgent && selectedAgent && (selectedAgentId !== selectedAgent.id || !agent)) {
      setSelectedAgentId(selectedAgent.id);
      setAgent(agentDraft(selectedAgent));
    }
  }, [agent, isNewAgent, selectedAgent, selectedAgentId]);
  useEffect(() => {
    if (selectedProvider && (selectedProviderId !== selectedProvider.id || !provider)) {
      setSelectedProviderId(selectedProvider.id);
      setProvider(providerDraft(selectedProvider));
    }
  }, [provider, selectedProvider, selectedProviderId]);
  useEffect(() => {
    if (!npc && management.data?.npcGeneration) setNpc({ ...management.data.npcGeneration });
  }, [management.data, npc]);

  const apply = (data: AIManagementData, message: string) => {
    queryClient.setQueryData(["aiManagement"], data);
    void queryClient.invalidateQueries({ queryKey: ["aiWorkspace"] });
    notify(message);
  };
  const saveAgent = useMutation({
    mutationFn: (agentValues: Record<string, unknown>) => saveAIProvider({ agentValues }),
    onSuccess: (result) => apply(result.data, result.events[0]?.message || "Agente aggiornato."),
    onError: (error: Error) => notify(error.message, "error"),
  });
  const saveProvider = useMutation({
    mutationFn: (values: Record<string, unknown>) => saveAIProvider({ values }),
    onSuccess: (result) => {
      apply(result.data, result.events[0]?.message || "Provider aggiornato.");
      setProvider((current) => current && { ...current, secret: "" });
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const probe = useMutation({
    mutationFn: (id: number) => saveAIProvider({ test: id }),
    onSuccess: (result) => apply(result.data, result.data.test?.message || "Prova completata."),
    onError: (error: Error) => notify(error.message, "error"),
  });
  const refreshModels = useMutation({
    mutationFn: (id: number) => refreshAIProviderModels(id),
    onSuccess: (result) => apply(result.data, result.events[0]?.message || "Catalogo modelli aggiornato."),
    onError: (error: Error) => notify(error.message, "error"),
  });
  const saveNpc = useMutation({
    mutationFn: (values: NpcGenerationConfig) => saveNpcGeneration(values),
    onSuccess: (result) => {
      apply(result.data, result.events[0]?.message || "Generazione personaggi aggiornata.");
      setNpc(result.data.npcGeneration);
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  if (management.isLoading) return <div className="page"><p className="empty-copy">Caricamento della configurazione…</p></div>;
  if (management.isError) return <div className="page"><p className="form-error">{(management.error as Error).message}</p></div>;
  const data = management.data!;
  if (!data.canManage) return <div className="page"><p className="form-error">Questa pagina è riservata a Master e Amministratori.</p></div>;
  const selectedModel = selectedProvider?.modelCatalog.find((entry) => entry.id === provider?.model);
  const draftCapabilities = selectedModel?.capabilities || selectedProvider?.capabilities;
  const maximumTokens = selectedModel?.contextWindow ? Math.min(128000, selectedModel.contextWindow) : 128000;

  return <div className="page ai-management">
    <header className="page-header">
      <div><p className="eyebrow">Strumenti</p><h1>Gestione AI</h1></div>
    </header>
    <section className="panel" data-component-type="panel" data-theme="gold">
      <p className="muted-copy">
        Gli agenti definiscono competenza, ruolo, provider, strumenti e autonomia. Tutti gli strumenti sono di sola lettura.
        I log registrano solo esito, tempi, modello e strumenti usati; mai domande o risposte.
      </p>
    </section>
    <nav className="ai-tabs" aria-label="Configurazione AI">
      <button type="button" className={section === "agents" ? "active" : ""} onClick={() => setSection("agents")}>Agenti</button>
      <button type="button" className={section === "providers" ? "active" : ""} onClick={() => setSection("providers")}>Provider</button>
      <button type="button" className={section === "npc" ? "active" : ""} onClick={() => setSection("npc")}>Generazione personaggi</button>
    </nav>

    {section === "npc" && npc && <section className="ai-provider-form panel ai-npc-generation" data-component-type="panel" data-theme="parchment">
      <header><div><p className="eyebrow">Strumento Nomi</p><h2>Generazione personaggi</h2></div></header>
      <p className="muted-copy">
        Il dossier di un PNG non costa quasi nulla; il ritratto sì. Queste impostazioni valgono per tutti i Master e
        decidono quanto può costare una rigenerazione.
      </p>
      <div className="ai-provider-options">
        <label>Formato del ritratto<select value={npc.portraitSize} onChange={(event) => setNpc({ ...npc, portraitSize: event.target.value })}>
          {data.imageSizes.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
        </select></label>
        <label>Qualità<select value={npc.portraitQuality} onChange={(event) => setNpc({ ...npc, portraitQuality: event.target.value })}>
          {data.portraitQualities.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
        </select></label>
      </div>
      <p className="muted-copy">
        640x1024 sono esattamente 655.360 pixel: il minimo che gpt-image-2 accetta, e quindi il ritratto più economico.
        Un 512x512 non esiste, sta sotto la soglia. La qualità pesa più del formato: «bassa» costa circa un ottavo di «media».
      </p>
      <label>Stile del ritratto
        <textarea rows={3} maxLength={400} value={npc.portraitStyle} onChange={(event) => setNpc({ ...npc, portraitStyle: event.target.value })} />
        <small className="muted-copy">Coda aggiunta a ogni prompt di ritratto, dopo aspetto e ruolo del personaggio.</small>
      </label>
      <label className="ai-toggle">
        <input type="checkbox" checked={npc.allowCampaignContext} onChange={(event) => setNpc({ ...npc, allowCampaignContext: event.target.checked })} />
        <span>Consenti il contesto della campagna nel dossier</span>
      </label>
      <small className="muted-copy">
        Con l'opzione attiva il Master può far leggere lore, fazioni e note condivise come sfondo. I permessi restano
        quelli dell'utente: un giocatore non vedrebbe comunque i dati riservati al Master.
      </small>
      <div className="button-row">
        <button type="button" className="button primary" disabled={saveNpc.isPending} onClick={() => saveNpc.mutate(npc)}>Salva</button>
        {management.data?.npcGeneration && <button type="button" className="button secondary" onClick={() => setNpc({ ...management.data!.npcGeneration })}>Annulla modifiche</button>}
      </div>
    </section>}

    {section === "agents" && agent && (selectedAgent || isNewAgent) && <div className="ai-management-layout">
      <aside className="ai-provider-list" aria-label="Agenti configurati">
        <section><h2>Workflow agentici</h2><button type="button" onClick={() => { setSelectedAgentId(-1); setAgent(emptyAgent()); }}>
          <strong>+ Nuovo agente</strong><span>Crea un workflow separato</span>
        </button>{agents.map((item) => <button
          key={item.id} type="button" className={item.id === selectedAgent?.id ? "active" : ""}
          onClick={() => { setSelectedAgentId(item.id); setAgent(agentDraft(item)); }}
        >
          <strong>{item.name}</strong><span>{item.effectiveProviderName || item.providerName || "provider non disponibile"}</span>
          <small data-state={item.isEnabled && item.isReady ? "on" : "off"}>{item.isReady ? `${item.minimumRole} · ${item.toolNames.length} strumenti` : item.availabilityIssues.join(" ")}</small>
        </button>)}</section>
      </aside>
      <section className="ai-provider-form panel" data-component-type="panel" data-theme="parchment">
        <header><div><p className="eyebrow">Policy agentica</p><h2>{selectedAgent?.name || "Nuovo agente"}</h2></div></header>
        <label>Nome<input value={agent.name} maxLength={120} onChange={(event) => setAgent({ ...agent, name: event.target.value })} /></label>
        <label>Scopo visibile<input value={agent.description} maxLength={1000} onChange={(event) => setAgent({ ...agent, description: event.target.value })} /></label>
        <label>Competenza e istruzioni
          <textarea rows={6} maxLength={8000} value={agent.instructions} onChange={(event) => setAgent({ ...agent, instructions: event.target.value })} />
          <small className="muted-copy">Definisci obiettivo, criteri di successo e limiti specifici. Il divieto di scrittura resta sempre applicato dal runtime.</small>
        </label>
        <div className="ai-provider-options">
          <label>Ruolo minimo<select value={agent.minimumRole} onChange={(event) => setAgent({ ...agent, minimumRole: event.target.value as AgentDraft["minimumRole"] })}>
            {data.roles.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}
          </select></label>
          <label>Provider<select value={agent.providerId || ""} onChange={(event) => setAgent({ ...agent, providerId: event.target.value ? Number(event.target.value) : null })}>
            <option value="">Provider chat predefinito</option>
            {providers.filter((item) => item.purpose === "chat").map((item) => <option key={item.id} value={item.id}>{item.name} · {item.model}{item.isReady ? "" : " · non pronto"}</option>)}
          </select></label>
          <label>Passi massimi<input type="number" min={1} max={12} value={agent.maxIterations} onChange={(event) => setAgent({ ...agent, maxIterations: Number(event.target.value) })} /></label>
          <label>Instradamento<select value={agent.routingMode} onChange={(event) => setAgent({ ...agent, routingMode: event.target.value as AgentDraft["routingMode"] })}>
            {data.routingModes.map((mode) => <option key={mode.value} value={mode.value}>{mode.label}</option>)}
          </select>
            <small className="muted-copy">Con «Automatico», una domanda che ha molti strumenti disponibili viene prima instradata a un sottoinsieme pertinente.</small>
          </label>
        </div>
        <fieldset className="inline-admin-tool">
          <legend>Permessi e ambiti di lettura ({agent.toolNames.length} selezionati)</legend>
          {Object.entries(
            data.tools.reduce<Record<string, typeof data.tools>>((groups, tool) => {
              (groups[tool.scope] ||= []).push(tool);
              return groups;
            }, {})
          ).map(([scope, tools]) => <div key={scope} className="ai-tool-scope-group">
            <h4>{SCOPE_LABELS[scope] || scope}</h4>
            <div className="ai-tool-list">{tools.map((tool) => <label key={tool.name} className="ai-toggle">
              <input type="checkbox" checked={agent.toolNames.includes(tool.name)} onChange={(event) => setAgent({
                ...agent,
                toolNames: event.target.checked ? [...agent.toolNames, tool.name] : agent.toolNames.filter((name) => name !== tool.name),
              })} />
              <span><strong>{tool.name}</strong> · {tool.minimumRole}<small className="muted-copy">{tool.description}</small></span>
            </label>)}</div>
          </div>)}
        </fieldset>
        <label className="ai-toggle"><input type="checkbox" checked={agent.isEnabled} onChange={(event) => setAgent({ ...agent, isEnabled: event.target.checked })} /><span>Agente attivo</span></label>
        <label className="ai-toggle"><input type="checkbox" checked={agent.isDefault} onChange={(event) => setAgent({ ...agent, isDefault: event.target.checked })} /><span>Agente predefinito</span></label>
        <button type="button" className="button primary" disabled={saveAgent.isPending} onClick={() => saveAgent.mutate({
          ...(selectedAgent ? { id: selectedAgent.id } : {}), ...agent,
        })}>Salva agente</button>
      </section>
    </div>}

    {section === "providers" && selectedProvider && provider && <div className="ai-management-layout">
      <aside className="ai-provider-list" aria-label="Provider configurati">
        {providers.map((item) => <button key={item.id} type="button" className={item.id === selectedProvider.id ? "active" : ""}
          onClick={() => { setSelectedProviderId(item.id); setProvider(providerDraft(item)); }}>
          <strong>{item.name}</strong><span>{item.model || "modello non impostato"}</span>
          <small data-state={item.isReady ? "on" : "off"}>{item.isReady ? "pronto" : item.configurationIssues.join(" ")} · {item.kind}</small>
        </button>)}
      </aside>
      <section className="ai-provider-form panel" data-component-type="panel" data-theme="parchment">
        <header><div><p className="eyebrow">{selectedProvider.kind}</p><h2>{selectedProvider.name}</h2></div></header>
        <p className="muted-copy">{selectedProvider.description}</p>
        <label>Nome<input value={provider.name} onChange={(event) => setProvider({ ...provider, name: event.target.value })} /></label>
        <label>Indirizzo API<input value={provider.baseUrl} disabled={!data.canManageCredentials} onChange={(event) => setProvider({ ...provider, baseUrl: event.target.value })} /></label>
        <label>Modello<input list={`ai-models-${selectedProvider.id}`} value={provider.model} onChange={(event) => {
          const model = event.target.value;
          const metadata = selectedProvider.modelCatalog.find((entry) => entry.id === model);
          setProvider({
            ...provider,
            model,
            effort: metadata && !metadata.capabilities.reasoning ? "" : provider.effort,
            verbosity: metadata && !metadata.capabilities.verbosity ? "" : provider.verbosity,
          });
        }} />
          <datalist id={`ai-models-${selectedProvider.id}`}>{(selectedProvider.modelCatalog.length ? selectedProvider.modelCatalog.map((entry) => entry.id) : selectedProvider.suggestedModels).map((model) => <option key={model} value={model} />)}</datalist>
          <small className="muted-copy">
            {selectedProvider.modelCatalogRefreshedAt
              ? `${selectedProvider.modelCatalog.length} modelli verificati · aggiornati ${new Date(selectedProvider.modelCatalogRefreshedAt).toLocaleString("it")}`
              : "Elenco iniziale locale: aggiorna per leggere i modelli realmente disponibili."}
          </small>
        </label>
        {selectedProvider.authStrategy !== "none" && <label>Chiave API<input type="password" autoComplete="off" disabled={!data.canManageCredentials}
          value={provider.secret} placeholder={selectedProvider.hasSecret ? "Configurata — scrivi per sostituirla" : "Incolla la chiave"}
          onChange={(event) => setProvider({ ...provider, secret: event.target.value })} />
          {!data.canManageCredentials && <small className="muted-copy">Chiavi e indirizzi sono modificabili solo dagli Amministratori.</small>}
        </label>}
        <div className="ai-provider-options">
          <label>Token massimi<input type="number" min={256} max={maximumTokens} value={provider.maxTokens} onChange={(event) => setProvider({ ...provider, maxTokens: event.target.value })} /><small className="muted-copy">Massimo per il modello: {maximumTokens.toLocaleString("it")}</small></label>
          {draftCapabilities?.reasoning && <label>Ragionamento<select value={provider.effort} onChange={(event) => setProvider({ ...provider, effort: event.target.value })}>
            <option value="">Predefinito</option>{REASONING_EFFORTS.map((value) => <option key={value}>{value}</option>)}
          </select></label>}
          {draftCapabilities?.verbosity && <label>Dettaglio<select value={provider.verbosity} onChange={(event) => setProvider({ ...provider, verbosity: event.target.value })}>
            <option value="">Predefinito</option>{VERBOSITY_OPTIONS.map((value) => <option key={value}>{value}</option>)}
          </select></label>}
        </div>
        {selectedProvider.configurationIssues.length > 0 && <aside className="ai-provider-health" data-state="warning"><strong>Configurazione incompleta</strong><ul>{selectedProvider.configurationIssues.map((issue) => <li key={issue}>{issue}</li>)}</ul></aside>}
        <label className="ai-toggle"><input type="checkbox" checked={provider.isEnabled} onChange={(event) => setProvider({ ...provider, isEnabled: event.target.checked })} /><span>Attivo</span></label>
        <label className="ai-toggle"><input type="checkbox" checked={provider.isDefault} disabled={!provider.isEnabled} onChange={(event) => setProvider({ ...provider, isDefault: event.target.checked })} /><span>Provider predefinito per {selectedProvider.purpose === "chat" ? "la chat" : "le immagini"}</span></label>
        {draftCapabilities?.chat && <label className="ai-toggle"><input type="checkbox" checked={provider.disableTools} onChange={(event) => setProvider({ ...provider, disableTools: event.target.checked })} /><span>Forza modalità senza strumenti</span></label>}
        <div className="button-row">
          <button type="button" className="button primary" disabled={saveProvider.isPending} onClick={() => saveProvider.mutate({
            id: selectedProvider.id, name: provider.name, model: provider.model, isEnabled: provider.isEnabled, isDefault: provider.isDefault,
            maxTokens: provider.maxTokens ? Number(provider.maxTokens) : null, effort: provider.effort,
            verbosity: provider.verbosity, disableTools: provider.disableTools,
            ...(data.canManageCredentials ? { baseUrl: provider.baseUrl, ...(provider.secret ? { secret: provider.secret } : {}) } : {}),
          })}>Salva provider</button>
          <button type="button" className="button secondary" disabled={refreshModels.isPending || !selectedProvider.canFetchModels} onClick={() => refreshModels.mutate(selectedProvider.id)}>{refreshModels.isPending ? "Aggiornamento…" : "Aggiorna modelli"}</button>
          <button type="button" className="button secondary" disabled={probe.isPending || !selectedProvider.isEnabled} onClick={() => probe.mutate(selectedProvider.id)}>Prova connessione</button>
        </div>
      </section>
    </div>}
  </div>;
}

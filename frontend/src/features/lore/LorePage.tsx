import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApp } from "../../App";
import { ImagePickerModal } from "../../components/ImagePickerModal";
import { Modal } from "../../components/Modal";
import { command, getData } from "../../lib/api";
import { TimelineSection, type LoreTimelineEvent } from "./TimelineSection";

type ReputationTier = { key: string; label: string };
type FactionRelation = { targetId: number; coefficient: number };
type Faction = {
  id: number; name: string; description: string; emblemId: number | null; emblemUrl: string;
  reputation: number; tier: ReputationTier; order: number; characterCount: number;
  baseReputation?: number; relations?: FactionRelation[];
};
type EventEffect = {
  id: number; factionId: number; factionName: string; delta: number; absoluteValue: number | null;
  propagated: boolean; previous: number; resulting: number;
};
type ReputationEvent = {
  id: number; title: string; reason: string; mode: "adjust" | "set"; campaignDay: number;
  campaignTime: string; recordedBy: string; createdAt: string; effects: EventEffect[];
  visibleToPlayers?: boolean;
};
type LoreNpc = {
  id: number; name: string; role: string; description: string; portraitId: number | null;
  portraitUrl: string; factionId: number | null; factionName: string; order: number;
  visibleToPlayers?: boolean;
};
type LoreData = {
  campaign: { id: number; name: string; currentDay: number; currentTime: string } | null;
  permissions: { canManage: boolean };
  factions: Faction[];
  npcs: LoreNpc[];
  events: ReputationEvent[];
  timelineEvents: LoreTimelineEvent[];
  limits: { min: number; max: number };
};

type FactionDraft = { id: number | null; name: string; description: string; emblemId: number | null; baseReputation: number };
type NpcDraft = { id: number | null; name: string; role: string; description: string; portraitId: number | null; factionId: number | null; visibleToPlayers: boolean };
type EventDraft = {
  id: number | null; mode: "adjust" | "set"; title: string; reason: string; campaignDay: string;
  campaignTime: string; visibleToPlayers: boolean; entries: Array<{ factionId: number; value: number }>;
};

const emptyFaction: FactionDraft = { id: null, name: "", description: "", emblemId: null, baseReputation: 0 };
const emptyNpc: NpcDraft = { id: null, name: "", role: "", description: "", portraitId: null, factionId: null, visibleToPlayers: true };

/** Position of a score on the -100..100 track, as a 0..100 percentage. */
export function reputationOffset(value: number, min: number, max: number): number {
  if (max <= min) return 50;
  const clamped = Math.max(min, Math.min(max, value));
  return ((clamped - min) / (max - min)) * 100;
}

/** Reading aid for a grid cell: how many points the target moves per source point. */
export function describeCoefficient(coefficient: number): string {
  if (!coefficient) return "Nessuna reazione";
  const rounded = Math.round(Math.abs(1 / coefficient));
  const direction = coefficient > 0 ? "guadagna" : "perde";
  const magnitude = Math.abs(coefficient);
  if (magnitude >= 1) {
    return `${direction} ${magnitude} ${magnitude === 1 ? "punto" : "punti"} per ogni punto`;
  }
  return `${direction} 1 punto ogni ${rounded}`;
}

function signed(value: number): string {
  return value > 0 ? `+${value}` : String(value);
}

function eventLabel(event: ReputationEvent): string {
  return event.title || event.reason.slice(0, 70) || "Evento";
}

export function LorePage() {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"personaggi" | "fazioni" | "timeline">("fazioni");
  const [sidebarTab, setSidebarTab] = useState<"aggiungi" | "storico">("aggiungi");
  const [factionDraft, setFactionDraft] = useState<FactionDraft | null>(null);
  const [npcDraft, setNpcDraft] = useState<NpcDraft | null>(null);
  const [eventDraft, setEventDraft] = useState<EventDraft | null>(null);
  const [openNpcId, setOpenNpcId] = useState<number | null>(null);
  const [gridOpen, setGridOpen] = useState(false);
  const [gridDraft, setGridDraft] = useState<Record<string, number>>({});
  const [historyFactionId, setHistoryFactionId] = useState<number | null>(null);
  const [pickerFor, setPickerFor] = useState<"faction" | "npc" | null>(null);
  const [npcQuery, setNpcQuery] = useState("");
  const [npcFactionFilter, setNpcFactionFilter] = useState("");

  const { data, isLoading } = useQuery({ queryKey: ["lore"], queryFn: () => getData<LoreData>("/api/v1/lore") });
  const canManage = data?.permissions.canManage ?? false;
  const factions = useMemo(() => data?.factions ?? [], [data]);
  const limits = data?.limits ?? { min: -100, max: 100 };

  const mutation = useMutation({
    mutationFn: ({ action, payload }: { action: string; payload: Record<string, unknown> }) =>
      command<{ lore: LoreData }>(action, payload, "lore"),
    onSuccess: (response) => {
      // The mutation already returns the refreshed projection: seed the cache
      // instead of spending a second request on a refetch.
      if (response.data.lore) queryClient.setQueryData(["lore"], response.data.lore);
      notify(response.events[0]?.message || "Aggiornato.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const run = (action: string, payload: Record<string, unknown>, done?: () => void) =>
    mutation.mutate({ action, payload }, { onSuccess: () => done?.() });

  const openGrid = () => {
    const draft: Record<string, number> = {};
    factions.forEach((faction) => {
      (faction.relations ?? []).forEach((relation) => {
        draft[`${faction.id}:${relation.targetId}`] = relation.coefficient;
      });
    });
    setGridDraft(draft);
    setGridOpen(true);
  };

  const saveGrid = () => {
    const relations = Object.entries(gridDraft)
      .map(([key, coefficient]) => {
        const [sourceId, targetId] = key.split(":").map(Number);
        return { sourceId, targetId, coefficient };
      })
      .filter((relation) => relation.coefficient);
    run("lore.relations.save", { relations }, () => setGridOpen(false));
  };

  const blankEvent = (factionId?: number): EventDraft => ({
    id: null,
    mode: "adjust",
    title: "",
    reason: "",
    campaignDay: String(data?.campaign?.currentDay ?? 0),
    campaignTime: data?.campaign?.currentTime ?? "",
    visibleToPlayers: true,
    entries: factionId ? [{ factionId, value: 5 }] : [],
  });

  const startEvent = (factionId?: number) => {
    setEventDraft(blankEvent(factionId));
    setSidebarTab("aggiungi");
  };

  const startEventEdit = (event: ReputationEvent) => {
    setEventDraft({
      id: event.id,
      mode: event.mode,
      title: event.title,
      reason: event.reason,
      campaignDay: String(event.campaignDay),
      campaignTime: event.campaignTime,
      visibleToPlayers: event.visibleToPlayers ?? true,
      entries: event.effects
        .filter((effect) => !effect.propagated)
        .map((effect) => ({
          factionId: effect.factionId,
          value: effect.absoluteValue === null ? effect.delta : effect.absoluteValue,
        })),
    });
    setSidebarTab("aggiungi");
  };

  const submitEvent = () => {
    if (!eventDraft) return;
    const values = {
      mode: eventDraft.mode,
      title: eventDraft.title,
      reason: eventDraft.reason,
      campaignDay: eventDraft.campaignDay === "" ? null : Number(eventDraft.campaignDay),
      campaignTime: eventDraft.campaignTime,
      visibleToPlayers: eventDraft.visibleToPlayers,
      entries: eventDraft.entries,
    };
    if (eventDraft.id) {
      run("lore.event.update", { values: { ...values, id: eventDraft.id } }, () => setEventDraft(blankEvent()));
    } else {
      run("lore.event.record", { values }, () => setEventDraft(blankEvent()));
    }
  };

  const historyFaction = factions.find((faction) => faction.id === historyFactionId) || null;
  const historyEvents = useMemo(() => {
    if (!historyFactionId || !data) return [];
    return data.events
      .map((event) => ({ event, effect: event.effects.find((entry) => entry.factionId === historyFactionId) }))
      .filter((row): row is { event: ReputationEvent; effect: EventEffect } => Boolean(row.effect));
  }, [data, historyFactionId]);

  const visibleNpcs = useMemo(() => {
    const needle = npcQuery.trim().toLocaleLowerCase("it");
    return (data?.npcs ?? []).filter((npc) => {
      const matches = !needle || `${npc.name} ${npc.role} ${npc.description} ${npc.factionName}`.toLocaleLowerCase("it").includes(needle);
      return matches && (!npcFactionFilter || String(npc.factionId ?? "") === npcFactionFilter);
    });
  }, [data, npcFactionFilter, npcQuery]);
  const openNpc = (data?.npcs ?? []).find((npc) => npc.id === openNpcId) || null;

  if (isLoading) return <div className="lore-page" data-component-type="view"><p className="lore-empty">Caricamento del lore…</p></div>;
  if (!data?.campaign) {
    return <div className="lore-page" data-component-type="view">
      <p className="lore-empty">Nessuna campagna attiva. Selezionane una per consultare il lore.</p>
    </div>;
  }

  const activeDraft = eventDraft ?? blankEvent();

  return (
    <div className="lore-page" data-component-type="view" data-theme="lore">
      <header className="lore-header" data-component-type="toolbar">
        <div>
          <h1>Lore</h1>
          <p>{data.campaign.name} · Giorno {data.campaign.currentDay}{data.campaign.currentTime ? ` · ${data.campaign.currentTime}` : ""}</p>
        </div>
        <div className="lore-tabs" role="tablist" aria-label="Sezioni del lore">
          <button id="lore-tab-fazioni" type="button" role="tab" aria-selected={tab === "fazioni"} aria-controls="lore-panel-fazioni" data-action="lore.tab" className={tab === "fazioni" ? "active" : ""} onClick={() => setTab("fazioni")}>Fazioni</button>
          <button id="lore-tab-personaggi" type="button" role="tab" aria-selected={tab === "personaggi"} aria-controls="lore-panel-personaggi" data-action="lore.tab" className={tab === "personaggi" ? "active" : ""} onClick={() => setTab("personaggi")}>Personaggi</button>
          <button id="lore-tab-timeline" type="button" role="tab" aria-selected={tab === "timeline"} aria-controls="lore-panel-timeline" data-action="lore.tab" className={tab === "timeline" ? "active" : ""} onClick={() => setTab("timeline")}>Timeline</button>
        </div>
      </header>

      {tab === "fazioni" && <div className="lore-layout">
        <section className="lore-section" data-component-type="panel" role="tabpanel" id="lore-panel-fazioni" aria-labelledby="lore-tab-fazioni">
          <div className="lore-section-header">
            <div>
              <h2>Reputazione del gruppo</h2>
              <p>Come ogni fazione considera il gruppo, da {limits.min} (ostilità aperta) a {limits.max} (alleati fidati).</p>
            </div>
            {canManage && <div className="lore-actions">
              <button type="button" data-action="lore.faction.create" onClick={() => setFactionDraft({ ...emptyFaction })}>Nuova fazione</button>
              <button type="button" data-action="lore.grid.open" onClick={openGrid} disabled={factions.length < 2}>Matrice reazioni</button>
            </div>}
          </div>

          {!factions.length && <p className="lore-empty">Nessuna fazione configurata per questa campagna.</p>}

          <div className="lore-faction-grid">
            {factions.map((faction) => <article key={faction.id} className="lore-faction-card" data-component-type="card" data-theme="lore">
              <header>
                {faction.emblemUrl
                  ? <img src={faction.emblemUrl} alt="" className="lore-emblem" />
                  : <span className="lore-emblem lore-emblem-placeholder" aria-hidden="true">⚑</span>}
                <div>
                  <button type="button" className="lore-faction-name" data-action="lore.faction.history" onClick={() => setHistoryFactionId(faction.id)}>
                    {faction.name}
                  </button>
                  <small>{faction.tier.label} · {signed(faction.reputation)}</small>
                </div>
              </header>
              <div className="lore-meter" role="img" aria-label={`Reputazione ${faction.reputation} su ${limits.max}: ${faction.tier.label}`}>
                <span className="lore-meter-zero" aria-hidden="true" />
                <span
                  className="lore-meter-fill"
                  data-tier={faction.tier.key}
                  style={{ left: `${Math.min(reputationOffset(0, limits.min, limits.max), reputationOffset(faction.reputation, limits.min, limits.max))}%`, width: `${Math.abs(reputationOffset(faction.reputation, limits.min, limits.max) - reputationOffset(0, limits.min, limits.max))}%` }}
                />
              </div>
              {faction.description && <p className="lore-faction-description">{faction.description}</p>}
              {faction.characterCount > 0 && <small className="lore-faction-meta">{faction.characterCount} personaggi collegati</small>}
              {canManage && <footer className="lore-card-actions">
                <button type="button" data-action="lore.event.create" onClick={() => startEvent(faction.id)}>Evento</button>
                <button type="button" data-action="lore.faction.edit" onClick={() => setFactionDraft({
                  id: faction.id, name: faction.name, description: faction.description,
                  emblemId: faction.emblemId, baseReputation: faction.baseReputation ?? 0,
                })}>Modifica</button>
                <button type="button" className="danger" data-action="lore.faction.delete" onClick={() => {
                  if (window.confirm(`Archiviare ${faction.name}? Gli eventi passati restano consultabili.`)) {
                    run("lore.faction.delete", { id: faction.id });
                  }
                }}>Archivia</button>
              </footer>}
            </article>)}
          </div>
        </section>

        <aside className="lore-sidebar" data-component-type="panel" data-theme="lore">
          {canManage
            ? <div className="lore-sidebar-tabs" role="tablist" aria-label="Strumenti reputazione">
                <button type="button" role="tab" aria-selected={sidebarTab === "aggiungi"} className={sidebarTab === "aggiungi" ? "active" : ""} onClick={() => setSidebarTab("aggiungi")}>Aggiungi</button>
                <button type="button" role="tab" aria-selected={sidebarTab === "storico"} className={sidebarTab === "storico" ? "active" : ""} onClick={() => setSidebarTab("storico")}>Storico</button>
              </div>
            : <div className="lore-sidebar-heading"><h3>Storico</h3></div>}

          {canManage && sidebarTab === "aggiungi" && <div className="lore-form lore-sidebar-form">
            <div className="lore-sidebar-form-header">
              <strong>{activeDraft.id ? "Modifica evento" : "Registra evento"}</strong>
              {activeDraft.id && <button type="button" className="lore-link-button" onClick={() => setEventDraft(blankEvent())}>Annulla modifica</button>}
            </div>
            <fieldset className="lore-modes">
              <legend>Tipo di modifica</legend>
              <label><input type="radio" name="lore-mode" checked={activeDraft.mode === "adjust"} onChange={() => setEventDraft({ ...activeDraft, mode: "adjust" })} /> <span>Aggiungi o sottrai</span></label>
              <label><input type="radio" name="lore-mode" checked={activeDraft.mode === "set"} onChange={() => setEventDraft({ ...activeDraft, mode: "set" })} /> <span>Imposta valore</span></label>
            </fieldset>
            <p className="lore-hint">
              {activeDraft.mode === "adjust"
                ? "La variazione si propaga alle fazioni collegate secondo la matrice delle reazioni."
                : "Un valore imposto è una correzione: vale solo per le fazioni indicate e non si propaga."}
            </p>
            <label><span>Titolo (facoltativo)</span>
              <input value={activeDraft.title} onChange={(event) => setEventDraft({ ...activeDraft, title: event.target.value })} />
            </label>
            <label><span>Motivo</span>
              <textarea rows={3} value={activeDraft.reason} onChange={(event) => setEventDraft({ ...activeDraft, reason: event.target.value })}
                placeholder="Descrivi cosa è accaduto" />
            </label>
            <div className="lore-form-row">
              <label><span>Giorno</span>
                <input type="number" min={0} value={activeDraft.campaignDay}
                  onChange={(event) => setEventDraft({ ...activeDraft, campaignDay: event.target.value })} />
              </label>
              <label><span>Momento</span>
                <input value={activeDraft.campaignTime} onChange={(event) => setEventDraft({ ...activeDraft, campaignTime: event.target.value })} placeholder="Sera" />
              </label>
            </div>
            <div className="lore-entry-editor">
              <span className="lore-entry-title">Fazioni coinvolte</span>
              {activeDraft.entries.map((entry, index) => <div key={index} className="lore-entry-row">
                <select value={String(entry.factionId)} onChange={(event) => {
                  const entries = [...activeDraft.entries];
                  entries[index] = { ...entry, factionId: Number(event.target.value) };
                  setEventDraft({ ...activeDraft, entries });
                }}>
                  {factions.map((faction) => <option key={faction.id} value={String(faction.id)}>{faction.name}</option>)}
                </select>
                <input type="number" min={limits.min} max={limits.max} value={entry.value} onChange={(event) => {
                  const entries = [...activeDraft.entries];
                  entries[index] = { ...entry, value: Number(event.target.value) };
                  setEventDraft({ ...activeDraft, entries });
                }} />
                <button type="button" className="danger" aria-label="Rimuovi fazione" onClick={() => setEventDraft({
                  ...activeDraft, entries: activeDraft.entries.filter((_, position) => position !== index),
                })}>×</button>
              </div>)}
              <button type="button" disabled={activeDraft.entries.length >= factions.length} onClick={() => {
                const used = new Set(activeDraft.entries.map((entry) => entry.factionId));
                const next = factions.find((faction) => !used.has(faction.id));
                if (next) setEventDraft({ ...activeDraft, entries: [...activeDraft.entries, { factionId: next.id, value: activeDraft.mode === "adjust" ? 5 : 0 }] });
              }}>Aggiungi fazione</button>
            </div>
            <label className="lore-checkbox">
              <input type="checkbox" checked={activeDraft.visibleToPlayers}
                onChange={(event) => setEventDraft({ ...activeDraft, visibleToPlayers: event.target.checked })} />
              <span>Visibile ai giocatori</span>
            </label>
            {activeDraft.id && <p className="lore-hint">Le reazioni vengono ricalcolate solo se cambi il tipo o i valori: correggere motivo o data lascia intatto lo storico registrato.</p>}
            <button type="button" className="lore-primary-button" data-action={activeDraft.id ? "lore.event.update" : "lore.event.record"}
              disabled={mutation.isPending || !activeDraft.entries.length} onClick={submitEvent}>
              {activeDraft.id ? "Salva modifiche" : "Salva evento"}
            </button>
          </div>}

          {(!canManage || sidebarTab === "storico") && <div className="lore-sidebar-history">
            <p className="lore-hint">La reputazione attuale nasce dalla somma di questi eventi, in ordine di giorno.</p>
            {!data.events.length && <p className="lore-empty">Nessun evento registrato.</p>}
            <ol className="lore-timeline">
              {data.events.map((event) => <li key={event.id} className="lore-event" data-component-type="card" data-theme="lore">
                <header>
                  <div>
                    <strong>{eventLabel(event)}</strong>
                    <small>Giorno {event.campaignDay}{event.campaignTime ? ` · ${event.campaignTime}` : ""}{event.recordedBy ? ` · ${event.recordedBy}` : ""}</small>
                  </div>
                  <div className="lore-event-tags">
                    <span className="lore-tag">{event.mode === "set" ? "Valore imposto" : "Variazione"}</span>
                    {canManage && !event.visibleToPlayers && <span className="lore-tag lore-tag-secret">Solo master</span>}
                  </div>
                </header>
                {event.title && <p className="lore-event-reason">{event.reason}</p>}
                <ul className="lore-effect-list">
                  {event.effects.map((effect) => <li key={effect.id}>
                    <span>{effect.factionName}</span>
                    <span className="lore-effect-change">
                      {effect.previous} → <strong>{effect.resulting}</strong>
                      {effect.absoluteValue === null && <em> ({signed(effect.delta)})</em>}
                      {effect.propagated && <span className="lore-tag lore-tag-chain">reazione</span>}
                    </span>
                  </li>)}
                </ul>
                {canManage && <footer className="lore-card-actions">
                  <button type="button" data-action="lore.event.edit" onClick={() => startEventEdit(event)}>Modifica</button>
                  <button type="button" className="danger" data-action="lore.event.delete" onClick={() => {
                    if (window.confirm("Rimuovere l'evento? Le reputazioni verranno ricalcolate senza di esso.")) {
                      run("lore.event.delete", { id: event.id });
                    }
                  }}>Rimuovi</button>
                </footer>}
              </li>)}
            </ol>
          </div>}
        </aside>
      </div>}

      {tab === "personaggi" && <section className="lore-section" data-component-type="panel" role="tabpanel" id="lore-panel-personaggi" aria-labelledby="lore-tab-personaggi">
        <div className="lore-section-header">
          <div>
            <h2>Personaggi della campagna</h2>
            <p>Volti, ruoli e appartenenze che il gruppo ha incontrato. Apri una scheda per leggerne la storia.</p>
          </div>
          {canManage && <div className="lore-actions">
            <button type="button" data-action="lore.character.create" onClick={() => setNpcDraft({ ...emptyNpc })}>Nuovo personaggio</button>
          </div>}
        </div>
        <div className="lore-filters">
          <label>
            <span>Cerca</span>
            <input type="search" value={npcQuery} onChange={(event) => setNpcQuery(event.target.value)} placeholder="Nome, ruolo o descrizione" />
          </label>
          <label>
            <span>Fazione</span>
            <select value={npcFactionFilter} onChange={(event) => setNpcFactionFilter(event.target.value)}>
              <option value="">Tutte</option>
              {factions.map((faction) => <option key={faction.id} value={String(faction.id)}>{faction.name}</option>)}
            </select>
          </label>
        </div>
        {!visibleNpcs.length && <p className="lore-empty">Nessun personaggio da mostrare.</p>}
        <div className="lore-npc-gallery">
          {visibleNpcs.map((npc) => <button
            key={npc.id}
            type="button"
            className="lore-npc-tile"
            data-component-type="card"
            data-theme="lore"
            data-action="lore.character.open"
            onClick={() => setOpenNpcId(npc.id)}
          >
            {npc.portraitUrl
              ? <img src={npc.portraitUrl} alt="" />
              : <span className="lore-npc-tile-placeholder" aria-hidden="true">☗</span>}
            <span className="lore-npc-tile-text">
              <span className="lore-npc-tile-name">
                {npc.name}
                {canManage && !npc.visibleToPlayers && <span className="lore-tag lore-tag-secret">Solo master</span>}
              </span>
              {npc.description && <span className="lore-npc-tile-description">{npc.description}</span>}
            </span>
          </button>)}
        </div>
      </section>}

      {tab === "timeline" && <TimelineSection
        events={data.timelineEvents ?? []}
        canManage={canManage}
        isPending={mutation.isPending}
        run={run}
      />}

      {openNpc && <Modal title={openNpc.name} onClose={() => setOpenNpcId(null)}>
        <div className="lore-npc-detail">
          {openNpc.portraitUrl && <img src={openNpc.portraitUrl} alt="" className="lore-npc-detail-portrait" />}
          <div className="lore-npc-detail-body">
            {openNpc.role && <p className="lore-npc-detail-role">{openNpc.role}</p>}
            <div className="lore-npc-detail-tags">
              {openNpc.factionName && <span className="lore-tag">{openNpc.factionName}</span>}
              {canManage && !openNpc.visibleToPlayers && <span className="lore-tag lore-tag-secret">Solo master</span>}
            </div>
            {openNpc.description
              ? <p className="lore-npc-detail-description">{openNpc.description}</p>
              : <p className="lore-empty">Nessuna descrizione registrata.</p>}
            {canManage && <footer className="lore-card-actions">
              <button type="button" data-action="lore.character.edit" onClick={() => {
                setNpcDraft({
                  id: openNpc.id, name: openNpc.name, role: openNpc.role, description: openNpc.description,
                  portraitId: openNpc.portraitId, factionId: openNpc.factionId, visibleToPlayers: openNpc.visibleToPlayers ?? true,
                });
                setOpenNpcId(null);
              }}>Modifica</button>
              <button type="button" className="danger" data-action="lore.character.delete" onClick={() => {
                if (window.confirm(`Archiviare ${openNpc.name}?`)) {
                  run("lore.character.delete", { id: openNpc.id }, () => setOpenNpcId(null));
                }
              }}>Archivia</button>
            </footer>}
          </div>
        </div>
      </Modal>}

      {factionDraft && <Modal title={factionDraft.id ? "Modifica fazione" : "Nuova fazione"} onClose={() => setFactionDraft(null)}>
        <div className="lore-form">
          <label><span>Nome</span>
            <input value={factionDraft.name} onChange={(event) => setFactionDraft({ ...factionDraft, name: event.target.value })} />
          </label>
          <label><span>Descrizione</span>
            <textarea rows={4} value={factionDraft.description} onChange={(event) => setFactionDraft({ ...factionDraft, description: event.target.value })} />
          </label>
          <label><span>Reputazione iniziale ({limits.min} … {limits.max})</span>
            <input type="number" min={limits.min} max={limits.max} value={factionDraft.baseReputation}
              onChange={(event) => setFactionDraft({ ...factionDraft, baseReputation: Number(event.target.value) })} />
          </label>
          <p className="lore-hint">La reputazione attuale resta la somma di questo valore e di tutti gli eventi registrati.</p>
          <div className="lore-form-row">
            <button type="button" onClick={() => setPickerFor("faction")}>Scegli emblema</button>
            {factionDraft.emblemId && <button type="button" onClick={() => setFactionDraft({ ...factionDraft, emblemId: null })}>Rimuovi emblema</button>}
          </div>
          <footer className="lore-card-actions">
            <button type="button" className="primary" data-action="lore.faction.save" disabled={mutation.isPending}
              onClick={() => run("lore.faction.save", {
                values: {
                  id: factionDraft.id, name: factionDraft.name, description: factionDraft.description,
                  emblemId: factionDraft.emblemId, baseReputation: factionDraft.baseReputation,
                },
              }, () => setFactionDraft(null))}>Salva</button>
            <button type="button" onClick={() => setFactionDraft(null)}>Annulla</button>
          </footer>
        </div>
      </Modal>}

      {npcDraft && <Modal title={npcDraft.id ? "Modifica personaggio" : "Nuovo personaggio"} onClose={() => setNpcDraft(null)}>
        <div className="lore-form">
          <label><span>Nome</span>
            <input value={npcDraft.name} onChange={(event) => setNpcDraft({ ...npcDraft, name: event.target.value })} />
          </label>
          <label><span>Ruolo</span>
            <input value={npcDraft.role} onChange={(event) => setNpcDraft({ ...npcDraft, role: event.target.value })} placeholder="Capitano della guardia" />
          </label>
          <label><span>Descrizione</span>
            <textarea rows={6} value={npcDraft.description} onChange={(event) => setNpcDraft({ ...npcDraft, description: event.target.value })} />
          </label>
          <label><span>Fazione</span>
            <select value={npcDraft.factionId === null ? "" : String(npcDraft.factionId)}
              onChange={(event) => setNpcDraft({ ...npcDraft, factionId: event.target.value ? Number(event.target.value) : null })}>
              <option value="">Nessuna</option>
              {factions.map((faction) => <option key={faction.id} value={String(faction.id)}>{faction.name}</option>)}
            </select>
          </label>
          <label className="lore-checkbox">
            <input type="checkbox" checked={npcDraft.visibleToPlayers}
              onChange={(event) => setNpcDraft({ ...npcDraft, visibleToPlayers: event.target.checked })} />
            <span>Visibile ai giocatori</span>
          </label>
          <div className="lore-form-row">
            <button type="button" onClick={() => setPickerFor("npc")}>Scegli ritratto</button>
            {npcDraft.portraitId && <button type="button" onClick={() => setNpcDraft({ ...npcDraft, portraitId: null })}>Rimuovi ritratto</button>}
          </div>
          <footer className="lore-card-actions">
            <button type="button" className="primary" data-action="lore.character.save" disabled={mutation.isPending}
              onClick={() => run("lore.character.save", {
                values: {
                  id: npcDraft.id, name: npcDraft.name, role: npcDraft.role, description: npcDraft.description,
                  portraitId: npcDraft.portraitId, factionId: npcDraft.factionId, visibleToPlayers: npcDraft.visibleToPlayers,
                },
              }, () => setNpcDraft(null))}>Salva</button>
            <button type="button" onClick={() => setNpcDraft(null)}>Annulla</button>
          </footer>
        </div>
      </Modal>}

      {gridOpen && <Modal title="Matrice delle reazioni" onClose={() => setGridOpen(false)}>
        <div className="lore-form">
          <p className="lore-hint">
            Ogni cella indica quanto cambia la fazione in colonna per ogni punto guadagnato o perso dalla fazione in riga.
            0,2 significa +1 ogni +5. La matrice è asimmetrica: le due direzioni si configurano separatamente.
          </p>
          <div className="lore-grid-scroll">
            <table className="lore-grid" data-component-type="table">
              <thead>
                <tr>
                  <th scope="col">Se cambia…</th>
                  {factions.map((faction) => <th key={faction.id} scope="col">{faction.name}</th>)}
                </tr>
              </thead>
              <tbody>
                {factions.map((source) => <tr key={source.id}>
                  <th scope="row">{source.name}</th>
                  {factions.map((target) => <td key={target.id}>
                    {source.id === target.id ? <span aria-hidden="true">—</span> : <input
                      type="number" step="0.1" min={-5} max={5}
                      aria-label={`Reazione di ${target.name} ai punti di ${source.name}`}
                      title={describeCoefficient(gridDraft[`${source.id}:${target.id}`] ?? 0)}
                      value={gridDraft[`${source.id}:${target.id}`] ?? 0}
                      onChange={(event) => setGridDraft({ ...gridDraft, [`${source.id}:${target.id}`]: Number(event.target.value) })}
                    />}
                  </td>)}
                </tr>)}
              </tbody>
            </table>
          </div>
          <footer className="lore-card-actions">
            <button type="button" className="primary" data-action="lore.relations.save" disabled={mutation.isPending} onClick={saveGrid}>Salva matrice</button>
            <button type="button" onClick={() => setGridOpen(false)}>Annulla</button>
          </footer>
        </div>
      </Modal>}

      {historyFaction && <Modal title={`Storico: ${historyFaction.name}`} onClose={() => setHistoryFactionId(null)}>
        <div className="lore-form">
          <p className="lore-hint">Reputazione attuale: <strong>{signed(historyFaction.reputation)}</strong> · {historyFaction.tier.label}</p>
          {!historyEvents.length && <p className="lore-empty">Nessun evento ha ancora toccato questa fazione.</p>}
          <ol className="lore-timeline">
            {historyEvents.map(({ event, effect }) => <li key={event.id} className="lore-event">
              <header>
                <div>
                  <strong>{eventLabel(event)}</strong>
                  <small>Giorno {event.campaignDay}{event.campaignTime ? ` · ${event.campaignTime}` : ""}</small>
                </div>
                <span className="lore-effect-change">{effect.previous} → <strong>{effect.resulting}</strong></span>
              </header>
              {event.title && <p className="lore-event-reason">{event.reason}</p>}
              {effect.propagated && <span className="lore-tag lore-tag-chain">reazione indiretta</span>}
            </li>)}
          </ol>
        </div>
      </Modal>}

      {pickerFor && <ImagePickerModal
        selectedId={pickerFor === "faction" ? factionDraft?.emblemId ?? null : npcDraft?.portraitId ?? null}
        usageType={pickerFor === "faction" ? "generic" : "character_portrait"}
        defaultGroup={pickerFor === "faction" ? "Fazioni" : "Personaggi"}
        defaultTitle={pickerFor === "faction" ? factionDraft?.name ?? "" : npcDraft?.name ?? ""}
        onSelect={(asset) => {
          if (pickerFor === "faction" && factionDraft) setFactionDraft({ ...factionDraft, emblemId: asset?.id ?? null });
          if (pickerFor === "npc" && npcDraft) setNpcDraft({ ...npcDraft, portraitId: asset?.id ?? null });
          setPickerFor(null);
        }}
        onClose={() => setPickerFor(null)}
      />}
    </div>
  );
}

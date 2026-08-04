import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { command } from "../../lib/api";
import type {
  BootstrapData,
  CampaignData,
  CampaignSpecialResource,
  CampaignSpecialResourceProposal,
} from "../../lib/types";

type Props = {
  campaign: CampaignData;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
};

type Draft = Pick<CampaignSpecialResource, "character" | "name" | "value" | "notes" | "highlighted">;
type CampaignActionData = { campaigns: Pick<BootstrapData, "activeCampaignId" | "campaigns"> };

const EMPTY_DRAFT: Draft = { character: "", name: "", value: "", notes: "", highlighted: false };

function proposalActionLabel(proposal: CampaignSpecialResourceProposal) {
  if (proposal.action === "archive") return "Archiviazione";
  if (proposal.action === "restore") return "Ripristino";
  return proposal.resourceId ? "Modifica" : "Nuova risorsa";
}

function dateLabel(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("it-IT", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  }).format(date);
}

export function CampaignSpecialResources({ campaign, notify }: Props) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [characterFilter, setCharacterFilter] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [editingId, setEditingId] = useState<string | null | undefined>(undefined);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [busy, setBusy] = useState<string | null>(null);
  const { resources, proposals, canManage } = campaign.specialResources;
  const pending = proposals.filter((proposal) => proposal.status === "pending");
  const isFiltered = Boolean(search.trim() || characterFilter);
  const characterOptions = useMemo(() => Array.from(new Set(resources.map((resource) => resource.character).filter(Boolean))).sort((a, b) => a.localeCompare(b, "it")), [resources]);

  const visibleResources = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase("it");
    return resources.filter((resource) => {
      if (Boolean(resource.archivedAt) !== showArchived) return false;
      if (characterFilter && resource.character !== characterFilter) return false;
      if (!needle) return true;
      return [resource.character, resource.name, resource.value, resource.notes]
        .some((value) => value.toLocaleLowerCase("it").includes(needle));
    });
  }, [characterFilter, resources, search, showArchived]);

  const updateCache = (payload: CampaignActionData["campaigns"]) => {
    queryClient.setQueryData<BootstrapData>(["bootstrap"], (current) => current ? { ...current, ...payload } : current);
  };

  const run = async (key: string, action: string, payload: Record<string, unknown>, success: string) => {
    setBusy(key);
    try {
      const result = await command<CampaignActionData>(action, { campaignId: campaign.id, ...payload }, "notes");
      updateCache(result.data.campaigns);
      notify(result.events[0]?.message || success, "success");
      return true;
    } catch (error) {
      notify(error instanceof Error ? error.message : "Operazione non riuscita.", "error");
      return false;
    } finally {
      setBusy(null);
    }
  };

  const openEditor = (resource?: CampaignSpecialResource) => {
    setEditingId(resource?.id ?? null);
    setDraft(resource ? {
      character: resource.character,
      name: resource.name,
      value: resource.value,
      notes: resource.notes,
      highlighted: resource.highlighted,
    } : EMPTY_DRAFT);
  };

  const save = async () => {
    if (!draft.name.trim()) {
      notify("Dai un nome alla risorsa speciale.", "error");
      return;
    }
    const ok = await run(
      `save-${editingId || "new"}`,
      "campaign.specialResources.save",
      { resourceId: editingId, values: draft },
      canManage ? "Risorsa salvata." : "Proposta inviata al Master.",
    );
    if (ok) setEditingId(undefined);
  };

  const archive = (resource: CampaignSpecialResource, archived: boolean) => run(
    `archive-${resource.id}`,
    "campaign.specialResources.archive",
    { resourceId: resource.id, archived },
    canManage ? (archived ? "Risorsa archiviata." : "Risorsa ripristinata.") : "Proposta inviata al Master.",
  );

  const move = async (resource: CampaignSpecialResource, direction: -1 | 1) => {
    const active = resources.filter((entry) => !entry.archivedAt);
    const index = active.findIndex((entry) => entry.id === resource.id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= active.length) return;
    const ids = active.map((entry) => entry.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    await run(`move-${resource.id}`, "campaign.specialResources.reorder", { resourceIds: ids }, "Ordine aggiornato.");
  };

  const review = (proposal: CampaignSpecialResourceProposal, approve: boolean) => run(
    `review-${proposal.id}`,
    "campaign.specialResources.review",
    { proposalId: proposal.id, approve },
    approve ? "Proposta approvata." : "Proposta rifiutata.",
  );

  return <section className="campaign-special-resources" data-component-type="collection" data-theme="parchment">
    <header className="special-resource-toolbar">
      <div>
        <p>{canManage ? "Modifiche immediate · proposte dei giocatori in revisione" : "Le modifiche vengono inviate al Master per approvazione"}</p>
        <strong>{resources.filter((resource) => !resource.archivedAt).length} risorse attive</strong>
      </div>
      <button type="button" className="button primary small" onClick={() => openEditor()}>Nuova risorsa</button>
    </header>

    {canManage && pending.length > 0 && <section className="special-resource-proposals" aria-label="Proposte in attesa">
      <header><strong>Proposte in attesa</strong><span>{pending.length}</span></header>
      <div>
        {pending.map((proposal) => <article key={proposal.id}>
          <div>
            <small>{proposalActionLabel(proposal)} · {proposal.proposedBy.name} · {dateLabel(proposal.createdAt)}</small>
            <strong>{proposal.resourceName}</strong>
            {proposal.action === "save" && <dl>
              {Object.entries(proposal.values).map(([field, value]) => {
                const before = proposal.before?.[field as keyof typeof proposal.before];
                const display = (entry: unknown) => typeof entry === "boolean" ? (entry ? "Sì" : "No") : String(entry || "—");
                return <div key={field}><dt>{field === "character" ? "Personaggio" : field === "name" ? "Risorsa" : field === "value" ? "Stato" : field === "notes" ? "Dettagli" : "In evidenza"}</dt><dd>{before !== undefined && <s>{display(before)}</s>}<b>{display(value)}</b></dd></div>;
              })}
            </dl>}
          </div>
          <footer>
            <button type="button" className="button primary small" disabled={busy !== null} onClick={() => review(proposal, true)}>Approva</button>
            <button type="button" className="button secondary small" disabled={busy !== null} onClick={() => review(proposal, false)}>Rifiuta</button>
          </footer>
        </article>)}
      </div>
    </section>}

    {!canManage && pending.length > 0 && <div className="special-resource-player-pending" role="status">
      <strong>{pending.length} {pending.length === 1 ? "proposta in attesa" : "proposte in attesa"}</strong>
      <span>Il Master le vedrà qui e potrà approvarle o rifiutarle.</span>
    </div>}

    <div className="special-resource-filters">
      <label><span>Cerca</span><input type="search" value={search} placeholder="Risorsa, stato o dettaglio…" onChange={(event) => setSearch(event.target.value)} /></label>
      <label><span>Personaggio</span><select value={characterFilter} onChange={(event) => setCharacterFilter(event.target.value)}><option value="">Tutti</option>{characterOptions.map((name) => <option key={name}>{name}</option>)}</select></label>
      {canManage && <label className="special-resource-archive-toggle"><input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} /><span>Mostra archiviate</span></label>}
    </div>

    <div className="special-resource-grid">
      {visibleResources.map((resource, index) => <article key={resource.id} className={resource.highlighted ? "highlighted" : ""} data-state={resource.archivedAt ? "archived" : "active"}>
        <header>
          <span>{resource.character || "Gruppo"}</span>
          {resource.highlighted && <i title="Risorsa in evidenza">In evidenza</i>}
        </header>
        <h3>{resource.name}</h3>
        <div className="special-resource-value">{resource.value || "Stato non indicato"}</div>
        {resource.notes && <p>{resource.notes}</p>}
        <small>Aggiornata da {resource.updatedBy?.name || "Sistema"}{dateLabel(resource.updatedAt) ? ` · ${dateLabel(resource.updatedAt)}` : ""}</small>
        <footer>
          {!resource.archivedAt && <button type="button" onClick={() => openEditor(resource)}>{canManage ? "Modifica" : "Proponi modifica"}</button>}
          {canManage && !resource.archivedAt && <>
            <button type="button" title={isFiltered ? "Rimuovi i filtri per riordinare" : undefined} aria-label={`Sposta ${resource.name} su`} disabled={isFiltered || index === 0 || busy !== null} onClick={() => move(resource, -1)}>↑</button>
            <button type="button" title={isFiltered ? "Rimuovi i filtri per riordinare" : undefined} aria-label={`Sposta ${resource.name} giù`} disabled={isFiltered || index === visibleResources.length - 1 || busy !== null} onClick={() => move(resource, 1)}>↓</button>
          </>}
          <button type="button" disabled={busy !== null} onClick={() => archive(resource, !resource.archivedAt)}>{resource.archivedAt ? "Ripristina" : canManage ? "Archivia" : "Proponi archiviazione"}</button>
        </footer>
      </article>)}
      {!visibleResources.length && <div className="special-resource-empty"><strong>Nessuna risorsa trovata</strong><p>{showArchived ? "Non ci sono risorse archiviate con questi filtri." : "Crea la prima scheda o modifica i filtri."}</p></div>}
    </div>

    {editingId !== undefined && <div className="special-resource-editor" role="dialog" aria-modal="true" aria-label={editingId ? "Modifica risorsa speciale" : "Nuova risorsa speciale"}>
      <form onSubmit={(event) => { event.preventDefault(); void save(); }}>
        <header><div><p className="eyebrow">{canManage ? "Gestione Master" : "Proposta al Master"}</p><h3>{editingId ? "Modifica risorsa" : "Nuova risorsa"}</h3></div><button type="button" aria-label="Chiudi" onClick={() => setEditingId(undefined)}>×</button></header>
        <div className="special-resource-form-grid">
          <label><span>Personaggio o gruppo</span><input maxLength={100} list="special-resource-characters" value={draft.character} placeholder="Es. Rhyss oppure Gruppo" onChange={(event) => setDraft((current) => ({ ...current, character: event.target.value }))} /></label>
          <datalist id="special-resource-characters">{characterOptions.map((name) => <option key={name} value={name} />)}</datalist>
          <label><span>Nome della risorsa</span><input required maxLength={120} value={draft.name} placeholder="Es. Dono di Sanguine" onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></label>
          <label className="wide"><span>Stato corrente</span><input maxLength={200} value={draft.value} placeholder="Es. 2 disponibili, oppure 6 umane · 3 animali" onChange={(event) => setDraft((current) => ({ ...current, value: event.target.value }))} /><small>Lo stato resta grande e immediatamente leggibile sulla scheda.</small></label>
          <label className="wide"><span>Regola, scadenza o promemoria</span><textarea maxLength={2000} rows={5} value={draft.notes} placeholder="Quando si rinnova? Come si consuma? Cosa bisogna ricordare?" onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))} /></label>
          <label className="special-resource-highlight"><input type="checkbox" checked={draft.highlighted} onChange={(event) => setDraft((current) => ({ ...current, highlighted: event.target.checked }))} /><span>Metti in evidenza</span></label>
        </div>
        <footer><button type="button" className="button secondary" onClick={() => setEditingId(undefined)}>Annulla</button><button type="submit" className="button primary" disabled={busy !== null}>{busy ? "Invio…" : canManage ? "Salva" : "Invia proposta"}</button></footer>
      </form>
    </div>}
  </section>;
}

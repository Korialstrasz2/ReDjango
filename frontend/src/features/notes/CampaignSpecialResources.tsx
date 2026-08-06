import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { command } from "../../lib/api";
import type {
  BootstrapData,
  CampaignData,
  CampaignSpecialResource,
  CampaignSpecialResourceProposal,
} from "../../lib/types";
import {
  specialResourceLineChanged,
  specialResourceLineDraft,
  specialResourceText,
  type SpecialResourceLineDraft,
} from "./specialResourceState";

type Props = {
  campaign: CampaignData;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
  reviewRequestToken?: number;
};

type CampaignActionData = { campaigns: Pick<BootstrapData, "activeCampaignId" | "campaigns"> };
type ProposalSnapshot = { character: string; name: string; text: string };

const EMPTY_LINE: SpecialResourceLineDraft = { character: "", name: "", text: "" };
const FREE_TEXT_LIMIT = 2_000;

function proposalActionLabel(proposal: CampaignSpecialResourceProposal) {
  if (proposal.action === "archive") return "Archiviazione";
  if (proposal.action === "restore") return "Ripristino";
  return proposal.resourceId ? "Modifica" : "Nuova riga";
}

function dateLabel(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function proposalSnapshots(
  proposal: CampaignSpecialResourceProposal,
  resource?: CampaignSpecialResource,
): { before: ProposalSnapshot; after: ProposalSnapshot } {
  const current = {
    character: resource?.character || "",
    name: resource?.name || "",
    value: resource?.value || "",
    notes: resource?.notes || "",
    highlighted: Boolean(resource?.highlighted),
  };
  const beforeFields = { ...current, ...proposal.before };
  const afterFields = { ...beforeFields, ...proposal.values };
  return {
    before: {
      character: String(beforeFields.character || ""),
      name: String(beforeFields.name || ""),
      text: specialResourceText(beforeFields),
    },
    after: {
      character: String(afterFields.character || ""),
      name: String(afterFields.name || proposal.resourceName || ""),
      text: specialResourceText(afterFields),
    },
  };
}

export function CampaignSpecialResources({ campaign, notify, reviewRequestToken = 0 }: Props) {
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, SpecialResourceLineDraft>>({});
  const [creating, setCreating] = useState(false);
  const [newLine, setNewLine] = useState<SpecialResourceLineDraft>(EMPTY_LINE);
  const [busy, setBusy] = useState<string | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const { resources, proposals, canManage } = campaign.specialResources;
  const activeResources = useMemo(() => resources.filter((resource) => !resource.archivedAt), [resources]);
  const pending = useMemo(() => proposals.filter((proposal) => proposal.status === "pending"), [proposals]);
  const pendingResourceIds = useMemo(
    () => new Set(pending.flatMap((proposal) => proposal.resourceId ? [proposal.resourceId] : [])),
    [pending],
  );

  useEffect(() => {
    setDrafts((current) => {
      const next: Record<string, SpecialResourceLineDraft> = {};
      activeResources.forEach((resource) => {
        next[resource.id] = current[resource.id] || specialResourceLineDraft(resource);
      });
      return next;
    });
  }, [activeResources]);

  useEffect(() => {
    if (canManage && pending.length > 0 && reviewRequestToken > 0) setReviewOpen(true);
  }, [canManage, pending.length, reviewRequestToken]);

  useEffect(() => {
    if (pending.length === 0) setReviewOpen(false);
  }, [pending.length]);

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

  const valuesFromLine = (draft: SpecialResourceLineDraft, resource?: CampaignSpecialResource) => ({
    character: draft.character,
    name: draft.name,
    value: "",
    notes: draft.text,
    highlighted: resource?.highlighted ?? false,
  });

  const validateLine = (draft: SpecialResourceLineDraft) => {
    if (!draft.name.trim()) {
      notify("Dai un nome alla riga.", "error");
      return false;
    }
    if (draft.text.length > FREE_TEXT_LIMIT) {
      notify(`Il testo libero può contenere al massimo ${FREE_TEXT_LIMIT} caratteri.`, "error");
      return false;
    }
    return true;
  };

  const saveLine = async (resource: CampaignSpecialResource, draft: SpecialResourceLineDraft) => {
    if (!validateLine(draft) || !specialResourceLineChanged(resource, draft)) return;
    await run(
      `save-${resource.id}`,
      "campaign.specialResources.save",
      { resourceId: resource.id, values: valuesFromLine(draft, resource) },
      canManage ? "Riga salvata." : "Modifica inviata al Master.",
    );
  };

  const createLine = async () => {
    if (!validateLine(newLine)) return;
    const changed = Boolean(newLine.character.trim() || newLine.name.trim() || newLine.text.trim());
    if (!changed) return;
    const ok = await run(
      "save-new",
      "campaign.specialResources.save",
      { resourceId: null, values: valuesFromLine(newLine) },
      canManage ? "Riga aggiunta." : "Nuova riga inviata al Master.",
    );
    if (ok) {
      setCreating(false);
      setNewLine(EMPTY_LINE);
    }
  };

  const review = (proposal: CampaignSpecialResourceProposal, approve: boolean) => run(
    `review-${proposal.id}`,
    "campaign.specialResources.review",
    { proposalId: proposal.id, approve },
    approve ? "Proposta approvata." : "Proposta rifiutata.",
  );

  const renderLine = (resource: CampaignSpecialResource) => {
    const draft = drafts[resource.id] || specialResourceLineDraft(resource);
    const changed = specialResourceLineChanged(resource, draft);
    const awaitingReview = !canManage && pendingResourceIds.has(resource.id);
    const actionLabel = canManage ? "Salva" : "Invia a Master";
    return <form className="special-resource-line" key={resource.id} onSubmit={(event) => {
      event.preventDefault();
      void saveLine(resource, draft);
    }}>
      <div className="special-resource-line-title">
        <label>
          <span className="sr-only">Personaggio</span>
          <input
            maxLength={100}
            value={draft.character}
            placeholder="Personaggio o gruppo"
            onChange={(event) => setDrafts((current) => ({
              ...current,
              [resource.id]: { ...draft, character: event.target.value },
            }))}
          />
        </label>
        <span aria-hidden="true">·</span>
        <label>
          <span className="sr-only">Nome riga</span>
          <input
            required
            maxLength={120}
            value={draft.name}
            placeholder="Nome riga"
            onChange={(event) => setDrafts((current) => ({
              ...current,
              [resource.id]: { ...draft, name: event.target.value },
            }))}
          />
        </label>
      </div>
      <div className="special-resource-line-content">
        <label>
          <span className="sr-only">Testo libero</span>
          <textarea
            rows={2}
            maxLength={FREE_TEXT_LIMIT}
            value={draft.text}
            placeholder="Testo libero…"
            onChange={(event) => setDrafts((current) => ({
              ...current,
              [resource.id]: { ...draft, text: event.target.value },
            }))}
          />
        </label>
        <button
          type="submit"
          className="button primary small"
          disabled={!changed || busy !== null || awaitingReview || draft.text.length > FREE_TEXT_LIMIT}
          title={awaitingReview ? "Questa modifica è già in attesa di revisione." : undefined}
        >
          {busy === `save-${resource.id}` ? (canManage ? "Salvataggio…" : "Invio…") : awaitingReview ? "In attesa" : actionLabel}
        </button>
      </div>
    </form>;
  };

  return <section className="campaign-special-resources special-resource-lines" data-component-type="collection" data-theme="parchment">
    <header className="special-resource-toolbar special-resource-line-toolbar">
      <div>
        <p>{canManage ? "Modifica diretta delle righe di campagna" : "Le modifiche vengono inviate al Master per approvazione"}</p>
        <strong>{activeResources.length} {activeResources.length === 1 ? "riga" : "righe"}</strong>
      </div>
      <div className="special-resource-toolbar-actions">
        {canManage && pending.length > 0 && <button type="button" className="button secondary small pending-review-glow" onClick={() => setReviewOpen(true)}>
          Richieste <span>{pending.length}</span>
        </button>}
        <button type="button" className="button primary small" onClick={() => setCreating(true)}>Aggiungi riga</button>
      </div>
    </header>

    {!canManage && pending.length > 0 && <div className="special-resource-player-pending" role="status">
      <strong>{pending.length} {pending.length === 1 ? "richiesta in attesa" : "richieste in attesa"}</strong>
      <span>Le righe restano modificabili dopo che il Master avrà accettato o rifiutato la richiesta.</span>
    </div>}

    <div className="special-resource-line-list">
      {activeResources.map(renderLine)}
      {creating && <form className="special-resource-line special-resource-line-new" onSubmit={(event) => {
        event.preventDefault();
        void createLine();
      }}>
        <div className="special-resource-line-title">
          <label><span className="sr-only">Personaggio</span><input autoFocus maxLength={100} value={newLine.character} placeholder="Personaggio o gruppo" onChange={(event) => setNewLine((current) => ({ ...current, character: event.target.value }))} /></label>
          <span aria-hidden="true">·</span>
          <label><span className="sr-only">Nome riga</span><input required maxLength={120} value={newLine.name} placeholder="Nome riga" onChange={(event) => setNewLine((current) => ({ ...current, name: event.target.value }))} /></label>
        </div>
        <div className="special-resource-line-content">
          <label><span className="sr-only">Testo libero</span><textarea rows={2} maxLength={FREE_TEXT_LIMIT} value={newLine.text} placeholder="Testo libero…" onChange={(event) => setNewLine((current) => ({ ...current, text: event.target.value }))} /></label>
          <div className="special-resource-new-actions">
            <button type="button" className="button secondary small" disabled={busy !== null} onClick={() => { setCreating(false); setNewLine(EMPTY_LINE); }}>Annulla</button>
            <button type="submit" className="button primary small" disabled={!newLine.name.trim() || busy !== null || newLine.text.length > FREE_TEXT_LIMIT}>
              {busy === "save-new" ? (canManage ? "Salvataggio…" : "Invio…") : canManage ? "Salva" : "Invia a Master"}
            </button>
          </div>
        </div>
      </form>}
      {!activeResources.length && !creating && <div className="special-resource-empty">
        <strong>Nessuna riga disponibile</strong>
        <p>Aggiungi la prima risorsa speciale della campagna.</p>
      </div>}
    </div>

    {canManage && reviewOpen && pending.length > 0 && <div className="special-resource-review-dialog" role="dialog" aria-modal="true" aria-label="Richieste Risorse speciali">
      <section>
        <header>
          <div><p className="eyebrow">Risorse speciali</p><h3>Richieste da revisionare</h3><small>{pending.length} {pending.length === 1 ? "richiesta in attesa" : "richieste in attesa"}</small></div>
          <button type="button" aria-label="Chiudi richieste" onClick={() => setReviewOpen(false)}>×</button>
        </header>
        <div className="special-resource-review-list">
          {pending.map((proposal) => {
            const resource = resources.find((entry) => entry.id === proposal.resourceId);
            const snapshots = proposalSnapshots(proposal, resource);
            return <article key={proposal.id}>
              <header>
                <div><small>{proposalActionLabel(proposal)} · {proposal.proposedBy.name} · {dateLabel(proposal.createdAt)}</small><strong>{snapshots.after.character || "Gruppo"} · {snapshots.after.name}</strong></div>
                <span>{proposal.action === "archive" ? "Archivia" : proposal.action === "restore" ? "Ripristina" : "Modifica"}</span>
              </header>
              {proposal.action === "save" ? <div className="special-resource-review-comparison">
                <section><h4>Valore precedente</h4><strong>{snapshots.before.character || "Gruppo"} · {snapshots.before.name || "—"}</strong><p>{snapshots.before.text || "—"}</p></section>
                <section><h4>Nuovo valore proposto</h4><strong>{snapshots.after.character || "Gruppo"} · {snapshots.after.name || "—"}</strong><p>{snapshots.after.text || "—"}</p></section>
              </div> : <p className="special-resource-review-status">La richiesta propone di <strong>{proposal.action === "archive" ? "archiviare" : "ripristinare"}</strong> questa riga.</p>}
              <footer>
                <button type="button" className="button primary small" disabled={busy !== null} onClick={() => void review(proposal, true)}>{busy === `review-${proposal.id}` ? "Elaborazione…" : "Accetta"}</button>
                <button type="button" className="button secondary small" disabled={busy !== null} onClick={() => void review(proposal, false)}>Rifiuta</button>
              </footer>
            </article>;
          })}
        </div>
      </section>
    </div>}
  </section>;
}

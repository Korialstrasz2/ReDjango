import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { command } from "../../lib/api";
import type { BootstrapData, CampaignData } from "../../lib/types";

type Props = {
  campaign: CampaignData;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
  rows?: number;
};

type CampaignActionData = {
  campaigns: Pick<BootstrapData, "activeCampaignId" | "campaigns">;
};

type SaveStatus = "idle" | "dirty" | "saving" | "saved" | "error";

export function CampaignSharedNoteEditor({ campaign, notify, rows = 22 }: Props) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(campaign.sharedNotes);
  const [status, setStatus] = useState<SaveStatus>("idle");
  const valueRef = useRef(value);
  const dirtyRef = useRef(false);
  const lastQueuedRef = useRef<string | null>(campaign.sharedNotes);
  const queueRef = useRef<Promise<void>>(Promise.resolve());

  useEffect(() => {
    setValue(campaign.sharedNotes);
    valueRef.current = campaign.sharedNotes;
    dirtyRef.current = false;
    lastQueuedRef.current = campaign.sharedNotes;
    setStatus("idle");
  }, [campaign.id, campaign.sharedNotes]);

  const updateCampaignCache = useCallback((payload: CampaignActionData["campaigns"]) => {
    queryClient.setQueryData<BootstrapData>(["bootstrap"], (current) => current ? {
      ...current,
      ...payload,
    } : current);
  }, [queryClient]);

  const persist = useCallback((content: string) => {
    if (content === lastQueuedRef.current) return;
    lastQueuedRef.current = content;
    setStatus("saving");
    queueRef.current = queueRef.current
      .catch(() => undefined)
      .then(async () => {
        const result = await command<CampaignActionData>(
          "campaign.notes.update",
          { campaignId: campaign.id, content },
          "notes",
        );
        updateCampaignCache(result.data.campaigns);
        const saved = result.data.campaigns.campaigns.find((entry) => entry.id === campaign.id)?.sharedNotes ?? content;
        if (valueRef.current === saved) {
          dirtyRef.current = false;
          setStatus("saved");
        } else {
          setStatus("dirty");
        }
      })
      .catch((error: Error) => {
        if (lastQueuedRef.current === content) lastQueuedRef.current = null;
        setStatus("error");
        notify(error.message, "error");
      });
  }, [campaign.id, notify, updateCampaignCache]);

  useEffect(() => {
    if (!dirtyRef.current || value === campaign.sharedNotes) return;
    const timer = window.setTimeout(() => persist(value), 800);
    return () => window.clearTimeout(timer);
  }, [campaign.sharedNotes, persist, value]);

  const changeValue = (content: string) => {
    setValue(content);
    valueRef.current = content;
    dirtyRef.current = content !== campaign.sharedNotes;
    setStatus(content === campaign.sharedNotes ? "idle" : "dirty");
  };

  const statusLabel = status === "saving" ? "Salvataggio…" : status === "saved" ? "Salvato" : status === "error" ? "Salvataggio non riuscito" : status === "dirty" ? "Da salvare" : "Salvataggio automatico";

  return <section className="note-section-editor minimal" data-component-type="form" data-theme="parchment" data-note-section="condivise">
    <div className="note-editor-minimal-meta">
      <span>Visibili e modificabili dagli utenti che selezionano {campaign.name}.</span>
      <small className={`note-save-status ${status}`} aria-live="polite">{statusLabel}</small>
    </div>
    <textarea
      aria-label={`Note condivise di ${campaign.name}`}
      maxLength={30000}
      rows={rows}
      value={value}
      placeholder="Scrivi qui le note condivise della campagna…"
      onChange={(event) => changeValue(event.target.value)}
      onBlur={() => persist(valueRef.current)}
      onKeyDown={(event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase("it") === "s") {
          event.preventDefault();
          persist(valueRef.current);
        }
      }}
    />
  </section>;
}

import { useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Modal } from "../../components/Modal";
import { command } from "../../lib/api";
import type { BootstrapData, CampaignData, SettingsData } from "../../lib/types";

type ClockField = "ora" | "giorno";
type ClockDirection = "increase" | "decrease";
type CampaignsPayload = Pick<BootstrapData, "activeCampaignId" | "campaigns">;

type Props = {
  campaign: CampaignData | null;
  settings: SettingsData;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
};

const MISSING = "—";

/** The weather name shown in the bar, plus the rule text kept for its tooltip. */
export function weatherSummary(campaign: CampaignData | null): { label: string; detail: string } {
  if (!campaign) return { label: MISSING, detail: "Nessuna campagna selezionata." };
  const label = campaign.weatherLabel.trim();
  if (!label) return { label: "Sconosciuto", detail: "Nessun meteo registrato per questa campagna." };
  return { label, detail: campaign.weatherEffects.trim() || "Nessun effetto sulle regole." };
}

export function clockLabel(campaign: CampaignData | null): string {
  return campaign?.currentTime.trim() || MISSING;
}

export function dayLabel(campaign: CampaignData | null): string {
  return campaign ? String(campaign.daysSinceStart) : MISSING;
}

export function CampaignStatus({ campaign, settings, notify }: Props) {
  const queryClient = useQueryClient();
  const [reminderOpen, setReminderOpen] = useState(false);
  const canControl = settings.security.canManageMasterSettings;
  const weather = weatherSummary(campaign);

  const applyCampaigns = (payload: CampaignsPayload) => queryClient.setQueryData<BootstrapData>(
    ["bootstrap"],
    (current) => current ? { ...current, ...payload } : current,
  );

  const clock = useMutation({
    mutationFn: ({ field, direction }: { field: ClockField; direction: ClockDirection }) => command<{ campaigns: CampaignsPayload; weatherReminder: boolean }>(
      "campaign.clock.update",
      { campaignId: campaign?.id, field, direction },
      "dashboard",
    ),
    onSuccess: (result) => {
      applyCampaigns(result.data.campaigns);
      // The backend owns the six-hour cadence, so the bar only reacts to it.
      if (result.data.weatherReminder) setReminderOpen(true);
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const weatherRoll = useMutation({
    mutationFn: () => command<{ campaigns: CampaignsPayload }>("campaign.weather.reroll", { campaignId: campaign?.id }, "dashboard"),
    onSuccess: (result) => {
      applyCampaigns(result.data.campaigns);
      setReminderOpen(false);
      notify(result.events[0]?.message || "Meteo aggiornato.", "info");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const busy = clock.isPending || weatherRoll.isPending;
  const rollWeather = () => { if (campaign && canControl && !busy) weatherRoll.mutate(); };
  const arrow = (field: ClockField, direction: ClockDirection, label: string) => <button
    type="button"
    className="campaign-status-arrow"
    disabled={!campaign || busy}
    aria-label={label}
    title={label}
    onClick={() => campaign && clock.mutate({ field, direction })}
  >{direction === "increase" ? "›" : "‹"}</button>;

  return <>
    <div className="campaign-status" data-component-type="panel" data-theme="dark" role="group" aria-label="Informazioni della campagna">
      <strong className="campaign-status-name">{campaign?.name || "Nessuna campagna"}</strong>
      <span className="campaign-status-entry">
        <small>Meteo:</small>
        {canControl ? <span
          className="campaign-status-weather actionable"
          role="button"
          tabIndex={0}
          aria-label={`Meteo ${weather.label}. Doppio clic o Invio per tirarlo di nuovo.`}
          aria-busy={weatherRoll.isPending}
          title={`${weather.detail}\n\nDoppio clic per tirare il meteo.`}
          onDoubleClick={rollWeather}
          onKeyDown={(event) => {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            rollWeather();
          }}
        >{weather.label}</span> : <span className="campaign-status-weather" title={weather.detail}>{weather.label}</span>}
      </span>
      <span className="campaign-status-entry">
        <small>Giorno:</small>
        {canControl && arrow("giorno", "decrease", "Giorno precedente")}
        <span className="campaign-status-value">{dayLabel(campaign)}</span>
        {canControl && arrow("giorno", "increase", "Giorno successivo")}
      </span>
      <span className="campaign-status-entry">
        <small>Ora:</small>
        {canControl && arrow("ora", "decrease", "Ora precedente")}
        <span className="campaign-status-value">{clockLabel(campaign)}</span>
        {canControl && arrow("ora", "increase", "Ora successiva")}
      </span>
    </div>
    {/* The bar blurs its backdrop, which would trap a fixed overlay inside it. */}
    {reminderOpen && createPortal(<Modal surface="weather"
      title="Tempo atmosferico"
      className="campaign-weather-reminder-modal"
      onClose={() => setReminderOpen(false)}
      footer={<>
        <button type="button" className="button secondary" onClick={() => setReminderOpen(false)}>Più tardi</button>
        <button type="button" className="button primary" disabled={weatherRoll.isPending} onClick={rollWeather}>Tira il meteo</button>
      </>}
    >
      <div className="campaign-weather-reminder">
        <p>L'orologio della campagna è avanzato: ricorda di tirare il tempo atmosferico.</p>
        <p className="campaign-weather-reminder-state">Giorno <strong>{dayLabel(campaign)}</strong>, ora <strong>{clockLabel(campaign)}</strong> · meteo attuale <strong>{weather.label}</strong>.</p>
        <p className="muted-copy">{weather.detail}</p>
      </div>
    </Modal>, document.body)}
  </>;
}

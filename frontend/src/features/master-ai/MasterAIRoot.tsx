import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getData } from "../../lib/api";
import type { AuthData, SettingsData } from "../../lib/types";
import { MasterAIPage } from "./MasterAIPage";

type Notice = { message: string; kind: "success" | "error" | "info" };

export function MasterAIRoot() {
  const [notice, setNotice] = useState<Notice | null>(null);
  const auth = useQuery({ queryKey: ["auth"], queryFn: () => getData<AuthData>("/api/auth/session/"), retry: false, staleTime: 0 });
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => getData<SettingsData>("/api/settings/"), enabled: auth.data?.authenticated === true });
  const notify = (message: string, kind: Notice["kind"] = "success") => setNotice({ message, kind });
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 4500);
    return () => window.clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    const theme = settings.data?.theme;
    if (!theme) return;
    document.documentElement.dataset.theme = theme.slug;
    document.documentElement.style.setProperty("--theme-overlay-opacity-target", String(theme.overlayOpacity));
    document.documentElement.style.setProperty("--theme-panel-opacity-target", String(theme.panelOpacity));
    Object.entries(theme.colors || {}).forEach(([key, value]) => {
      const variables: Record<string, string> = { background: "--background", panel: "--panel", panelStrong: "--panel-strong", text: "--text", mutedText: "--muted", line: "--line", accent: "--accent", accentStrong: "--accent-strong", gold: "--gold", sidebar: "--sidebar" };
      if (variables[key] && value) document.documentElement.style.setProperty(variables[key], value);
    });
  }, [settings.data]);

  if (auth.isLoading || settings.isLoading) return <div className="loading-screen"><span className="brand-rune">AI</span><p>Preparazione del Master AI…</p></div>;
  if (auth.isError || settings.isError) return <div className="fatal-error"><h1>Master AI non disponibile</h1><p>{((auth.error || settings.error) as Error).message}</p><a className="button secondary" href="/">Torna a ReDjango</a></div>;
  if (!auth.data?.authenticated) return <Navigate to="/" replace />;
  if (!settings.data?.security.canManageGameData) return <Navigate to="/" replace />;
  return <><MasterAIPage notify={notify} />{notice && <div className={`toast ${notice.kind}`} role="status">{notice.message}</div>}</>;
}

import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";

import { getAIChangeEntities, searchAIChangeEntities } from "./api";
import {
  buildMasterAIUrl,
  contextRecordId,
  parseMasterAILaunch,
  type MasterAILaunchRequest,
} from "./context";

export function MasterAIAssistButton({ children, className = "button secondary", ...request }: MasterAILaunchRequest & { children: ReactNode; className?: string }) {
  const navigate = useNavigate();
  return <button type="button" className={`${className} master-ai-assist-button`} onClick={() => navigate(buildMasterAIUrl(request))}>{children}</button>;
}

function useDomRevision(pathname: string) {
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let frame = 0;
    const refresh = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => { frame = 0; setRevision((value) => value + 1); });
    };
    refresh();
    const observer = new MutationObserver(refresh);
    observer.observe(document.getElementById("app") || document.body, { childList: true, subtree: true });
    return () => { observer.disconnect(); if (frame) window.cancelAnimationFrame(frame); };
  }, [pathname]);
  return revision;
}

function WorkspaceContextPortal({ search, revision }: { search: string; revision: number }) {
  const navigate = useNavigate();
  const parsed = useMemo(() => parseMasterAILaunch(search), [search]);
  const [label, setLabel] = useState("");
  const [error, setError] = useState("");
  const prefilled = useRef("");
  const host = document.querySelector<HTMLElement>(".master-ai-statusbar");

  useEffect(() => {
    let cancelled = false;
    setLabel(""); setError("");
    if (!parsed.context) return () => { cancelled = true; };
    const id = contextRecordId(parsed.context);
    const request = id
      ? searchAIChangeEntities(parsed.context.entityType, parsed.recordLabel, 10).then((payload) => {
        const record = payload.results.find((entry) => Number(entry.id) === id);
        if (!record) throw new Error("Il record contestuale non è accessibile o non esiste più.");
        return String(record.label || parsed.recordLabel || `#${id}`);
      })
      : getAIChangeEntities().then((payload) => {
        const descriptor = payload.entities.find((entry) => entry.type === parsed.context!.entityType);
        if (!descriptor) throw new Error("Questo tipo di entità non è accessibile con il ruolo attuale.");
        return String(descriptor.label || parsed.context!.entityType);
      });
    void request.then((value) => { if (!cancelled) setLabel(value); }).catch((caught: Error) => { if (!cancelled) setError(caught.message); });
    return () => { cancelled = true; };
  }, [parsed.context?.entityType, parsed.context?.targetId, parsed.context?.sourceId, parsed.recordLabel]);

  useEffect(() => {
    if (!parsed.prompt || prefilled.current === search) return;
    const textarea = document.querySelector<HTMLTextAreaElement>(".master-ai-chat textarea");
    if (!textarea) return;
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    setter?.call(textarea, parsed.prompt);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.dispatchEvent(new Event("change", { bubbles: true }));
    prefilled.current = search;
  }, [parsed.prompt, revision, search]);

  if (!host || !parsed.context) return null;
  const mode = parsed.context.sourceId ? "Sorgente" : parsed.context.targetId ? "Destinazione" : "Ambito";
  return createPortal(
    <aside className={`master-ai-context-chip ${error ? "error" : ""}`} role={error ? "alert" : "status"}>
      <span><small>{mode} · {parsed.context.entityType}</small><strong>{error || label || parsed.recordLabel || "Verifica del contesto…"}</strong></span>
      <button type="button" className="icon-button" aria-label="Rimuovi contesto" onClick={() => navigate("/tools/master-ai", { replace: true })}>×</button>
    </aside>,
    host,
    "master-ai-workspace-context",
  );
}

function AIModalMasterAIButton() {
  const navigate = useNavigate();
  const managementLink = document.querySelector<HTMLElement>(".ai-tool .ai-tabs .ai-tabs-link");
  const host = managementLink?.parentElement;
  if (!host) return null;
  return createPortal(
    <button type="button" className="button primary small master-ai-modal-launcher" onClick={() => navigate("/tools/master-ai")}>Master AI</button>,
    host,
    "master-ai-modal-launcher",
  );
}

function UnitManagementMasterAIButton({ revision }: { revision: number }) {
  const navigate = useNavigate();
  const host = document.querySelector<HTMLElement>(".unit-management-page .page-header .button-row");
  const active = document.querySelector<HTMLElement>(".unit-management-list button.active");
  const label = active?.querySelector("strong")?.textContent?.trim() || "";
  const identity = document.querySelector<HTMLElement>(".unit-management-editor .eyebrow")?.textContent || "";
  const targetId = Number(identity.match(/Unit\s+#(\d+)/i)?.[1] || 0) || undefined;
  if (!host) return null;
  const prompt = targetId && label
    ? `Rivedi la Unit «${label}». Cerca e leggi il record, confronta almeno cinque Unit meccanicamente simili, ispeziona ogni Skill e oggetto dipendente, poi proponi una modifica completa conforme al contratto Unit e all'audit di generazione.`
    : "Crea una nuova Unit completa. Leggi la configurazione live, confronta almeno cinque Unit meccanicamente simili, ispeziona Skill e oggetti dipendenti, quindi proponi un DTO completo conforme al contratto Unit e all'audit di generazione.";
  return createPortal(
    <button key={`${revision}-${targetId || "new"}`} type="button" className="button secondary master-ai-assist-button" onClick={() => navigate(buildMasterAIUrl({
      entityType: "unit",
      sourceSurface: "unit-management",
      targetId,
      recordLabel: label || undefined,
      defaultPrompt: prompt,
    }))}>Master AI Unit</button>,
    host,
    "master-ai-unit-management-launcher",
  );
}

export function MasterAILauncherRuntime() {
  const location = useLocation();
  const revision = useDomRevision(location.pathname);
  if (location.pathname === "/tools/master-ai") return <WorkspaceContextPortal search={location.search} revision={revision} />;
  return <>
    <AIModalMasterAIButton />
    {location.pathname === "/tools/units" && <UnitManagementMasterAIButton revision={revision} />}
  </>;
}

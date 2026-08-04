import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";

import { getAIChangeEntities, searchAIChangeEntities } from "./api";
import {
  buildMasterAIUrl,
  contextRecordId,
  parseMasterAILaunch,
  type MasterAIEntityType,
  type MasterAILaunchRequest,
} from "./context";

type RecordHint = { entityType: MasterAIEntityType; id?: number; name: string; sourceSurface: MasterAILaunchRequest["sourceSurface"] };
type ResolvedRecord = RecordHint & { id: number };

const normalize = (value: string) => value.trim().toLocaleLowerCase("it");
const text = (element: Element | null) => element?.textContent?.trim() || "";

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
    observer.observe(document.getElementById("app") || document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["class", "data-theme"] });
    return () => { observer.disconnect(); if (frame) window.cancelAnimationFrame(frame); };
  }, [pathname]);
  return revision;
}

function currentRecordHint(pathname: string): RecordHint | null {
  if (pathname === "/tools/items") {
    const inspector = document.querySelector(".item-management-inspector");
    const name = text(inspector?.querySelector("h2") || null);
    const match = text(inspector?.querySelector(".eyebrow") || null).match(/Oggetto\s+#(\d+)/i);
    return name && match ? { entityType: "item", id: Number(match[1]), name, sourceSurface: "item-management" } : null;
  }
  if (pathname === "/tools/skills") {
    const inspector = document.querySelector<HTMLElement>(".skill-management-inspector");
    const name = text(inspector?.querySelector("h2") || null);
    if (!name) return null;
    const magic = inspector?.dataset.theme === "arcane" || text(inspector).includes("Incantesimo");
    return { entityType: magic ? "spell" : "skill", name, sourceSurface: "skill-management" };
  }
  if (pathname === "/tools/themes") {
    const active = document.querySelector(".theme-list-items button.active");
    const name = text(active?.querySelector("strong") || null);
    return name ? { entityType: "theme", name, sourceSurface: "theme-management" } : null;
  }
  return null;
}

function useResolvedRecord(hint: RecordHint | null) {
  const [resolved, setResolved] = useState<ResolvedRecord | null>(null);
  const key = hint ? `${hint.entityType}:${hint.id || 0}:${hint.name}` : "";
  useEffect(() => {
    let cancelled = false;
    setResolved(null);
    if (!hint) return () => { cancelled = true; };
    if (hint.id) {
      setResolved({ ...hint, id: hint.id });
      return () => { cancelled = true; };
    }
    void searchAIChangeEntities(hint.entityType, hint.name, 10).then((payload) => {
      if (cancelled) return;
      const exact = payload.results.find((entry) => normalize(String(entry.label || "")) === normalize(hint.name));
      const id = Number(exact?.id);
      if (Number.isSafeInteger(id) && id > 0) setResolved({ ...hint, id });
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [key]);
  return resolved;
}

function LauncherPortals({ pathname, revision }: { pathname: string; revision: number }) {
  const hint = useMemo(() => currentRecordHint(pathname), [pathname, revision]);
  const selected = useResolvedRecord(hint);
  const pageActions = document.querySelector<HTMLElement>(".page-header .button-row");
  const itemActions = document.querySelector<HTMLElement>(".item-management-inspector > header");
  const skillActions = document.querySelector<HTMLElement>(".skill-management-inspector > footer");
  const themeActions = document.querySelector<HTMLElement>(".theme-editor-identity-actions");
  const portals: ReactNode[] = [];

  if (pageActions && pathname === "/tools/items") portals.push(createPortal(
    <MasterAIAssistButton key="item-page" entityType="item" sourceSurface="item-management" defaultPrompt="Aiutami a creare o aggiornare un oggetto del catalogo. Prepara soltanto una proposta da revisionare.">AI Assist</MasterAIAssistButton>,
    pageActions,
    "master-ai-item-page",
  ));
  if (pageActions && pathname === "/tools/skills") portals.push(createPortal(
    <MasterAIAssistButton key="skill-page" entityType="skill" sourceSurface="skill-management" defaultPrompt="Aiutami a creare o aggiornare una Skill o un incantesimo. Prepara soltanto una proposta da revisionare.">AI Assist</MasterAIAssistButton>,
    pageActions,
    "master-ai-skill-page",
  ));
  if (pageActions && pathname === "/tools/themes") portals.push(createPortal(
    <MasterAIAssistButton key="theme-page" entityType="theme" sourceSurface="theme-management" defaultPrompt="Aiutami a creare o aggiornare un tema. Prepara soltanto una proposta da revisionare.">AI Assist</MasterAIAssistButton>,
    pageActions,
    "master-ai-theme-page",
  ));

  if (selected && pathname === "/tools/items" && itemActions) portals.push(createPortal(
    <span className="master-ai-context-actions" key={`item-${selected.id}`}>
      <MasterAIAssistButton entityType="item" targetId={selected.id} sourceSurface="item-management" defaultPrompt={`Rivedi «${selected.name}» e proponi le modifiche necessarie senza applicarle.`}>Chiedi al Master AI</MasterAIAssistButton>
      <MasterAIAssistButton entityType="item" sourceId={selected.id} sourceSurface="item-management" defaultPrompt={`Crea un nuovo oggetto simile a «${selected.name}», ma attendi le mie indicazioni per le differenze.`}>Crea simile con AI</MasterAIAssistButton>
    </span>, itemActions, "master-ai-item-record",
  ));
  if (selected && pathname === "/tools/skills" && skillActions) portals.push(createPortal(
    <span className="master-ai-context-actions" key={`${selected.entityType}-${selected.id}`}>
      <MasterAIAssistButton entityType={selected.entityType} targetId={selected.id} sourceSurface="skill-management" defaultPrompt={`Rivedi «${selected.name}» e proponi le modifiche necessarie senza applicarle.`}>Chiedi al Master AI</MasterAIAssistButton>
      <MasterAIAssistButton entityType={selected.entityType} sourceId={selected.id} sourceSurface="skill-management" defaultPrompt={`Crea ${selected.entityType === "spell" ? "un incantesimo" : "una Skill"} simile a «${selected.name}», ma attendi le mie indicazioni per le differenze.`}>Crea simile con AI</MasterAIAssistButton>
    </span>, skillActions, "master-ai-skill-record",
  ));
  if (selected && pathname === "/tools/themes" && themeActions) portals.push(createPortal(
    <span className="master-ai-context-actions" key={`theme-${selected.id}`}>
      <MasterAIAssistButton entityType="theme" targetId={selected.id} sourceSurface="theme-management" defaultPrompt={`Rivedi il tema «${selected.name}» e proponi le modifiche necessarie senza applicarle.`}>Chiedi al Master AI</MasterAIAssistButton>
      <MasterAIAssistButton entityType="theme" sourceId={selected.id} sourceSurface="theme-management" defaultPrompt={`Crea un nuovo tema simile a «${selected.name}», ma attendi le mie indicazioni per le differenze.`}>Duplica con AI</MasterAIAssistButton>
    </span>, themeActions, "master-ai-theme-record",
  ));
  return <>{portals}</>;
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
      ? searchAIChangeEntities(parsed.context.entityType, "", 25).then((payload) => {
        const record = payload.results.find((entry) => Number(entry.id) === id);
        if (!record) throw new Error("Il record contestuale non è accessibile o non esiste più.");
        return String(record.label || `#${id}`);
      })
      : getAIChangeEntities().then((payload) => {
        const descriptor = payload.entities.find((entry) => entry.type === parsed.context!.entityType);
        if (!descriptor) throw new Error("Questo tipo di entità non è accessibile con il ruolo attuale.");
        return String(descriptor.label || parsed.context!.entityType);
      });
    void request.then((value) => { if (!cancelled) setLabel(value); }).catch((caught: Error) => { if (!cancelled) setError(caught.message); });
    return () => { cancelled = true; };
  }, [parsed.context?.entityType, parsed.context?.targetId, parsed.context?.sourceId]);

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
      <span><small>{mode} · {parsed.context.entityType}</small><strong>{error || label || "Verifica del contesto…"}</strong></span>
      <button type="button" className="icon-button" aria-label="Rimuovi contesto" onClick={() => navigate("/tools/master-ai", { replace: true })}>×</button>
    </aside>,
    host,
    "master-ai-workspace-context",
  );
}

export function MasterAILauncherRuntime() {
  const location = useLocation();
  const revision = useDomRevision(location.pathname);
  if (location.pathname === "/tools/master-ai") return <WorkspaceContextPortal search={location.search} revision={revision} />;
  if (!["/tools/items", "/tools/skills", "/tools/themes"].includes(location.pathname)) return null;
  return <LauncherPortals pathname={location.pathname} revision={revision} />;
}

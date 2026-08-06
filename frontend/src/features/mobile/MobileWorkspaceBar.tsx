import { type ReactNode, useEffect } from "react";
import type { NavigateFunction } from "react-router-dom";

type Props = {
  workspace: "combat" | "travel";
  title: string;
  backLabel?: string;
  navigate: NavigateFunction;
  onBeforeNavigate?: () => boolean;
  actions?: ReactNode;
};

export function closeTopWorkspaceDialog(): boolean {
  const top = document.querySelector<HTMLElement>("[data-modal-instance][data-modal-top]")
    || Array.from(document.querySelectorAll<HTMLElement>("[data-modal-instance]")).at(-1)
    || null;
  const close = top?.querySelector<HTMLButtonElement>(".modal-header [aria-label='Chiudi']");
  if (!close) return false;
  close.click();
  return true;
}

export function navigateBackOrHome(navigate: NavigateFunction) {
  const historyIndex = Number((window.history.state as { idx?: number } | null)?.idx ?? 0);
  if (historyIndex > 0) navigate(-1);
  else navigate("/", { replace: true });
}

export function MobileWorkspaceBar({ workspace, title, backLabel = "Indietro", navigate, onBeforeNavigate, actions }: Props) {
  useEffect(() => {
    const root = document.documentElement;
    const previous = root.dataset.mobileWorkspace;
    root.dataset.mobileWorkspace = workspace;
    return () => {
      if (previous) root.dataset.mobileWorkspace = previous;
      else delete root.dataset.mobileWorkspace;
    };
  }, [workspace]);

  const goBack = () => {
    if (closeTopWorkspaceDialog()) return;
    if (onBeforeNavigate?.()) return;
    navigateBackOrHome(navigate);
  };

  return <header className="mobile-workspace-bar" data-mobile-workspace-bar={workspace}>
    <button type="button" className="mobile-workspace-back" aria-label={`Indietro da ${title}`} onClick={goBack}>
      <span aria-hidden="true">←</span>
      <strong>{backLabel}</strong>
    </button>
    <div className="mobile-workspace-title">
      <small>Spazio mobile</small>
      <strong>{title}</strong>
    </div>
    <div className="mobile-workspace-actions">{actions}</div>
  </header>;
}

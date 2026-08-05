import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { useResponsiveLayout } from "../../lib/responsive";

export function CombatMobileNotesBridge() {
  const location = useLocation();
  const responsive = useResponsiveLayout();
  const enabled = responsive.isPhone && location.pathname.startsWith("/combat");
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    if (!enabled) {
      setAvailable(false);
      return;
    }
    const sync = () => setAvailable(Boolean(document.querySelector(".mobile-context-note-trigger")));
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [enabled]);

  if (!enabled) return null;

  return <button
    type="button"
    className="combat-mobile-notes-button"
    disabled={!available}
    aria-label="Apri note del combattimento"
    onClick={() => document.querySelector<HTMLButtonElement>(".mobile-context-note-trigger")?.click()}
  ><span aria-hidden="true">✎</span><strong>Note</strong></button>;
}

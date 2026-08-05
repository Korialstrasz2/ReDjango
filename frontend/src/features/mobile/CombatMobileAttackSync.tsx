import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { useResponsiveLayout } from "../../lib/responsive";

export function CombatMobileAttackSync() {
  const location = useLocation();
  const responsive = useResponsiveLayout();
  const enabled = responsive.isPhone && location.pathname.startsWith("/combat");

  useEffect(() => {
    if (!enabled) return;
    let previousOpen = Boolean(document.querySelector(".combat-attack-drawer.open"));

    const synchronize = () => {
      const open = Boolean(document.querySelector(".combat-attack-drawer.open"));
      if (open === previousOpen) return;
      previousOpen = open;
      if (open) {
        document.querySelector<HTMLButtonElement>("[data-combat-mobile-panel='attack']")?.click();
      } else if (document.documentElement.dataset.mobileCombatPanel === "attack") {
        document.querySelector<HTMLButtonElement>("[data-combat-mobile-panel='map']")?.click();
      }
    };

    const observer = new MutationObserver(synchronize);
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ["class"],
      childList: true,
      subtree: true,
    });
    return () => observer.disconnect();
  }, [enabled]);

  return null;
}

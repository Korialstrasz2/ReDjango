import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router-dom";

type TabletHeadingRoute = {
  prefix: string;
  selector: string;
  label: string;
};

const TABLET_HEADING_ROUTES: TabletHeadingRoute[] = [
  { prefix: "/combat", selector: ".combat-page", label: "Combattimento" },
  { prefix: "/travel", selector: ".travel-page", label: "Viaggio" },
];

/**
 * Combat and Travel intentionally keep their protected desktop workspaces and
 * their dedicated phone app bars. At tablet widths those presentations need a
 * visible semantic route heading without rewriting either page tree.
 */
export function TabletRouteHeadingRuntime() {
  const { pathname } = useLocation();
  const route = TABLET_HEADING_ROUTES.find((entry) => pathname.startsWith(entry.prefix)) || null;
  const [host, setHost] = useState<HTMLElement | null>(null);

  useEffect(() => {
    setHost(null);
    if (!route) return;

    let currentHost: HTMLElement | null = null;
    const attach = () => {
      const target = document.querySelector<HTMLElement>(route.selector);
      if (!target || currentHost?.parentElement === target) return;
      currentHost?.remove();
      currentHost = document.createElement("div");
      currentHost.className = "tablet-route-heading-host";
      target.prepend(currentHost);
      setHost(currentHost);
    };

    attach();
    const observer = new MutationObserver(attach);
    observer.observe(document.getElementById("app") || document.body, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      currentHost?.remove();
      setHost(null);
    };
  }, [pathname, route]);

  if (!route || !host) return null;
  return createPortal(<h1 className="tablet-route-heading">{route.label}</h1>, host);
}

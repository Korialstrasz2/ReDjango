import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { Modal } from "../../components/Modal";

export type MobileTool = "journal" | "dice" | "theft" | "audio" | "ai" | "names";

type ShellNavigationItem = {
  href: string;
  label: string;
  icon: string;
  management: boolean;
};

type Props = {
  characterName: string;
  campaignName: string;
  canManageGameData: boolean;
  activeTool: MobileTool | null;
  onSelectTool: (tool: MobileTool) => void;
};

const TOOL_ITEMS: Array<{ id: MobileTool; label: string; icon: string }> = [
  { id: "journal", label: "Diario", icon: "⌑" },
  { id: "dice", label: "Dadi", icon: "◆" },
  { id: "ai", label: "AI", icon: "✳" },
  { id: "audio", label: "Audio", icon: "♪" },
  { id: "theft", label: "Furto", icon: "⚿" },
  { id: "names", label: "Nomi", icon: "◈" },
];

function normalizeHref(anchor: HTMLAnchorElement): string {
  const raw = anchor.getAttribute("href") || "/";
  try {
    return new URL(raw, window.location.origin).pathname;
  } catch {
    return raw.startsWith("/") ? raw : "/";
  }
}

export function readDesktopShellNavigation(root: ParentNode = document): ShellNavigationItem[] {
  return Array.from(root.querySelectorAll<HTMLAnchorElement>(".side-nav .nav-list a")).map((anchor) => ({
    href: normalizeHref(anchor),
    label: anchor.querySelector<HTMLElement>(".nav-label")?.textContent?.trim()
      || anchor.textContent?.trim()
      || "Destinazione",
    icon: anchor.querySelector<HTMLElement>("[aria-hidden='true']")?.textContent?.trim() || "•",
    management: Boolean(anchor.closest(".nav-management-section")),
  }));
}

export function isMobileNavigationActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/characters" || href.startsWith("/character/")) return pathname.startsWith("/character/");
  return pathname === href || pathname.startsWith(`${href}/`);
}

function sameNavigation(left: ShellNavigationItem[], right: ShellNavigationItem[]): boolean {
  return left.length === right.length && left.every((item, index) => {
    const candidate = right[index];
    return candidate
      && item.href === candidate.href
      && item.label === candidate.label
      && item.icon === candidate.icon
      && item.management === candidate.management;
  });
}

export function MobileNavigation({ characterName, campaignName, canManageGameData, activeTool, onSelectTool }: Props) {
  const location = useLocation();
  const [navigation, setNavigation] = useState<ShellNavigationItem[]>([]);
  const [moreOpen, setMoreOpen] = useState(false);
  const [toolsOpen, setToolsOpen] = useState(false);

  useLayoutEffect(() => {
    const sync = () => {
      const next = readDesktopShellNavigation();
      setNavigation((current) => sameNavigation(current, next) ? current : next);
    };
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "href"],
    });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    setMoreOpen(false);
    setToolsOpen(false);
  }, [location.pathname]);

  const playerLinks = useMemo(() => navigation.filter((item) => !item.management), [navigation]);
  const home = playerLinks.find((item) => item.href === "/");
  const character = playerLinks.find((item) => item.href === "/characters" || item.href.startsWith("/character/"));
  const skills = playerLinks.find((item) => item.href === "/skills");
  const combat = playerLinks.find((item) => item.href === "/combat");
  const primary = [home, character, skills, combat].filter((item): item is ShellNavigationItem => Boolean(item));
  const primaryHrefs = new Set(primary.map((item) => item.href));
  const moreLinks = playerLinks.filter((item) => !primaryHrefs.has(item.href));
  const current = playerLinks.find((item) => isMobileNavigationActive(location.pathname, item.href));
  const managementAvailable = canManageGameData || navigation.some((item) => item.management);

  return <div className="mobile-shell-chrome" data-component-type="mobile-shell" data-theme="dark">
    <header className="mobile-app-bar">
      <Link className="mobile-app-brand" to="/" aria-label="Sala principale">RD</Link>
      <div className="mobile-app-context">
        <small>{campaignName || "ReDjango"}</small>
        <strong>{current?.label || characterName || "Sala principale"}</strong>
      </div>
      <button
        type="button"
        className="mobile-app-tools"
        aria-label="Apri strumenti rapidi"
        aria-expanded={toolsOpen}
        onClick={() => setToolsOpen(true)}
      >✦</button>
    </header>

    <nav className="mobile-bottom-navigation" aria-label="Navigazione principale">
      {primary.map((item) => <Link
        key={item.href}
        to={item.href}
        className={isMobileNavigationActive(location.pathname, item.href) ? "active" : ""}
        aria-current={isMobileNavigationActive(location.pathname, item.href) ? "page" : undefined}
      >
        <span aria-hidden="true">{item.icon}</span>
        <strong>{item.href === "/" ? "Home" : item.label}</strong>
      </Link>)}
      <button
        type="button"
        className={moreOpen || moreLinks.some((item) => isMobileNavigationActive(location.pathname, item.href)) ? "active" : ""}
        aria-expanded={moreOpen}
        onClick={() => setMoreOpen(true)}
      >
        <span aria-hidden="true">☰</span>
        <strong>Altro</strong>
      </button>
    </nav>

    {moreOpen && <Modal title="Navigazione" onClose={() => setMoreOpen(false)} responsiveMode="fullscreen" closeOnBackdrop={false}>
      <div className="mobile-navigation-sheet">
        <header>
          <p className="eyebrow">{campaignName || "Postazione di gioco"}</p>
          <h3>{characterName || "Nessun personaggio attivo"}</h3>
        </header>
        <nav aria-label="Altre destinazioni">
          {moreLinks.map((item) => <Link
            key={item.href}
            to={item.href}
            className={isMobileNavigationActive(location.pathname, item.href) ? "active" : ""}
            aria-current={isMobileNavigationActive(location.pathname, item.href) ? "page" : undefined}
            onClick={() => setMoreOpen(false)}
          >
            <span aria-hidden="true">{item.icon}</span>
            <strong>{item.label}</strong>
          </Link>)}
        </nav>
        {managementAvailable && <section className="mobile-management-notice" aria-label="Gestione non disponibile su telefono">
          <strong>Gestione da schermo più grande</strong>
          <p>Le schermate di gestione richiedono un tablet o un computer. Le funzioni giocatore restano disponibili qui.</p>
        </section>}
      </div>
    </Modal>}

    {toolsOpen && <Modal title="Strumenti rapidi" onClose={() => setToolsOpen(false)} responsiveMode="sheet">
      <div className="mobile-quick-tools-sheet">
        <p>Scegli uno strumento. Il contenuto si apre in uno spazio mobile dedicato.</p>
        <div>
          {TOOL_ITEMS.map((item) => <button
            key={item.id}
            type="button"
            className={activeTool === item.id ? "active" : ""}
            aria-pressed={activeTool === item.id}
            onClick={() => {
              setToolsOpen(false);
              onSelectTool(item.id);
            }}
          >
            <span aria-hidden="true">{item.icon}</span>
            <strong>{item.label}</strong>
          </button>)}
        </div>
      </div>
    </Modal>}
  </div>;
}

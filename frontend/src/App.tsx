import { createContext, type CSSProperties, type FormEvent, type MouseEvent, type ReactNode, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { Modal } from "./components/Modal";
import { LoginPage } from "./components/LoginPage";
import { AudioPlayerProvider } from "./features/audio/AudioPlayerProvider";
import { CharacterPage } from "./features/character/CharacterPage";
import { CompetenciesPage } from "./features/competencies/CompetenciesPage";
import { CreationPage } from "./features/creation/CreationPage";
import { CombatPage } from "./features/combat/CombatPage";
import { AIManagementPage } from "./features/management/AIManagementPage";
import { CharacterManagementPage } from "./features/management/CharacterManagementPage";
import { DamageRulesPage } from "./features/management/DamageRulesPage";
import { GameVariablesPage } from "./features/management/GameVariablesPage";
import { ItemManagementPage } from "./features/management/ItemManagementPage";
import { DungeonHelperPage } from "./features/management/DungeonHelperPage";
import { ManagementHub } from "./features/management/ManagementHub";
import { BackupManagementPage } from "./features/management/BackupManagementPage";
import { PlayerManagementPage } from "./features/management/PlayerManagementPage";
import { ShopManagementPage } from "./features/management/ShopManagementPage";
import { SkillManagementPage } from "./features/management/SkillManagementPage";
import { ThemeManagementPage } from "./features/management/ThemeManagementPage";
import { UnitManagementPage } from "./features/management/UnitManagementPage";
import { ItemCompendium } from "./features/guides/ItemCompendium";
import { LorePage } from "./features/lore/LorePage";
import { MarketPage } from "./features/market/MarketPage";
import { ContextNoteDock } from "./features/notes/ContextNoteDock";
import { DiceManagementPage } from "./features/management/DiceManagementPage";
import { QuickTools } from "./features/quick-tools/QuickTools";
import { SkillsPage } from "./features/skills/SkillsPage";
import { TravelPage } from "./features/TravelPage";
import { colorLuminance, contrastingTextOutline } from "./lib/appearance";
import { apiRequest, command, deleteMedia, getData, getMediaDetail, legacyAction, moveMedia, setMediaLimitedVisibility, uploadMedia } from "./lib/api";
import { FIXED_SHORTCUTS, pageShortcutTargets, quickToolShortcutTargets, SHORTCUT_CATEGORY, shortcutConflictKeys, shortcutFromKeyboardEvent, shortcutProfile, shortcutSettingValue, shortcutValue, type PageShortcutTarget } from "./lib/shortcuts";
import type { AuthData, BootstrapData, Guide, GuideEntry, GuideVariable, GuideVariableGroup, ImageCategory, MediaAsset, MediaDetailData, MediaLibraryData, NoteSection, PersonaggiData, SettingData, SettingsData, ThemeData } from "./lib/types";

type AppContextValue = {
  bootstrap: BootstrapData;
  personaggi: PersonaggiData;
  settings: SettingsData;
  media: MediaAsset[];
  mediaCategories: ImageCategory[];
  notify: (message: string, kind?: "success" | "error" | "info") => void;
};

const AppContext = createContext<AppContextValue | null>(null);
export const useApp = () => {
  const value = useContext(AppContext);
  if (!value) throw new Error("App context unavailable");
  return value;
};

const VALID_FONTS = new Set(["system", "serif", "book", "humanist", "accessible"]);
const VALID_DENSITIES = new Set(["spacious", "comfortable", "compact", "condensed"]);
const VALID_TEXT_OUTLINES = new Set(["off", "soft", "strong"]);
const TEXT_OUTLINE_COLOR_PROPERTY = "--text-aware-outline-color";
const outlinedTextElements = new Set<HTMLElement>();
let textOutlineObserver: MutationObserver | null = null;
let textOutlineFrame = 0;

// L'impostazione era un Sì/No: un valore booleano residuo va letto come bordo marcato.
function textOutlineLevel(value: unknown): string {
  if (typeof value === "boolean") return value ? "strong" : "off";
  const level = String(value ?? "off");
  return VALID_TEXT_OUTLINES.has(level) ? level : "off";
}

function rendersOwnText(element: HTMLElement): boolean {
  return element.matches("input, select, textarea")
    || Array.from(element.childNodes).some((node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim());
}

function refreshTextAwareOutlines() {
  textOutlineFrame = 0;
  const root = document.documentElement;
  if (root.dataset.textOutlineAware !== "true" || root.dataset.textOutline === "off") return;
  document.body.querySelectorAll<HTMLElement>("*").forEach((element) => {
    if (!rendersOwnText(element)) return;
    const outlineColor = contrastingTextOutline(getComputedStyle(element).color);
    if (element.style.getPropertyValue(TEXT_OUTLINE_COLOR_PROPERTY) !== outlineColor) {
      element.style.setProperty(TEXT_OUTLINE_COLOR_PROPERTY, outlineColor);
    }
    outlinedTextElements.add(element);
  });
}

function scheduleTextAwareOutlines() {
  if (textOutlineFrame) cancelAnimationFrame(textOutlineFrame);
  textOutlineFrame = requestAnimationFrame(refreshTextAwareOutlines);
}

function applyTextAwareOutlineMode(enabled: boolean) {
  const root = document.documentElement;
  root.dataset.textOutlineAware = enabled ? "true" : "false";
  textOutlineObserver?.disconnect();
  textOutlineObserver = null;
  if (!enabled || root.dataset.textOutline === "off") {
    if (textOutlineFrame) cancelAnimationFrame(textOutlineFrame);
    textOutlineFrame = 0;
    outlinedTextElements.forEach((element) => element.style.removeProperty(TEXT_OUTLINE_COLOR_PROPERTY));
    outlinedTextElements.clear();
    return;
  }
  textOutlineObserver = new MutationObserver(scheduleTextAwareOutlines);
  textOutlineObserver.observe(document.body, {
    attributes: true,
    attributeFilter: ["class"],
    childList: true,
    characterData: true,
    subtree: true,
  });
  scheduleTextAwareOutlines();
}
const MIN_FONT_SCALE = 75;
const MAX_FONT_SCALE = 175;

const THEME_COLOR_VARIABLES: Record<string, string> = {
  background: "--background",
  panel: "--panel",
  panelStrong: "--panel-strong",
  text: "--text",
  mutedText: "--muted",
  line: "--line",
  accent: "--accent",
  accentStrong: "--accent-strong",
  gold: "--gold",
  sidebar: "--sidebar",
  health: "--resource-pf",
  mana: "--resource-mana",
  energy: "--resource-energia",
  power: "--resource-potere",
  validSlot: "--slot-valid",
  invalidSlot: "--slot-invalid"
};

// I temi possono lasciare vuoti accento, oro e menu laterale: in quel caso valgono
// i colori globali di riserva configurati in Impostazioni → Amministrazione.
const THEME_COLOR_FALLBACK_KEYS: Record<string, string> = {
  accent: "appearance.accent_color",
  gold: "appearance.gold_color",
  sidebar: "appearance.sidebar_color"
};

export function resolveThemeColors(theme: ThemeData, ui: Record<string, unknown> = {}): Record<string, string> {
  return Object.fromEntries(Object.keys(THEME_COLOR_VARIABLES).map((key) => {
    const fallbackKey = THEME_COLOR_FALLBACK_KEYS[key];
    const fallback = fallbackKey ? String(ui[fallbackKey] || "") : "";
    return [key, String(theme.colors[key] || "") || fallback];
  }));
}

function applyTheme(theme: ThemeData | null, ui: Record<string, unknown> = {}) {
  if (!theme) return;
  const root = document.documentElement;
  const colors = resolveThemeColors(theme, ui);
  Object.entries(THEME_COLOR_VARIABLES).forEach(([key, variable]) => {
    if (colors[key]) root.style.setProperty(variable, colors[key]);
    else root.style.removeProperty(variable);
  });
  root.style.setProperty("--overlay-opacity", String(theme.overlayOpacity));
  root.style.setProperty("--panel-opacity", String(theme.panelOpacity));
  root.style.setProperty("--background-position", theme.backgroundPosition);
  root.style.setProperty("--background-blur", `${theme.backgroundBlur}px`);
  root.dataset.theme = theme.slug;
  root.dataset.colorMode = colorLuminance(colors.panelStrong || colors.panel || "") > 0.42 ? "light" : "dark";
  root.style.colorScheme = root.dataset.colorMode;
  root.style.setProperty("--accent-contrast", colorLuminance(colors.accent || "") > 0.18 ? "#101820" : "#ffffff");
  root.style.setProperty("--text-outline-color", contrastingTextOutline(colors.text || ""));
}

export function applyUiPreferences(settings: SettingsData | undefined, preview: Record<string, unknown> = {}) {
  if (!settings) return;
  const root = document.documentElement;
  const ui = { ...settings.ui, ...preview };
  const font = String(ui["appearance.font_family"] || "system");
  const density = String(ui["appearance.density"] || "comfortable");
  const requestedScale = Number(ui["appearance.font_scale"] ?? 100);
  const fontScale = Math.min(MAX_FONT_SCALE, Math.max(MIN_FONT_SCALE, Number.isFinite(requestedScale) ? requestedScale : 100));

  root.dataset.font = VALID_FONTS.has(font) ? font : "system";
  root.dataset.fontScale = fontScale >= 150 ? "large" : fontScale <= 85 ? "small" : "normal";
  root.dataset.density = VALID_DENSITIES.has(density) ? density : "comfortable";
  root.dataset.reducedMotion = ui["accessibility.reduced_motion"] ? "true" : "false";
  root.dataset.textOutline = textOutlineLevel(ui["accessibility.contrast_outline"]);
  const textOutlineAware = ui["accessibility.text_color_aware_outline"] === true;
  root.style.fontSize = `${fontScale}%`;
  applyTheme(settings.theme, ui);
  applyTextAwareOutlineMode(textOutlineAware);
}

function screenFromPath(path: string): string {
  if (path.startsWith("/creation")) return "personaggio";
  if (path.startsWith("/competencies")) return "personaggio";
  if (path.startsWith("/skills")) return "personaggio";
  if (path.startsWith("/character/")) return "personaggio";
  if (path.startsWith("/combat")) return "personaggio";
  // Reuse the campaign background until Theme has a dedicated Viaggio surface.
  if (path.startsWith("/travel")) return "dashboard";
  if (path.startsWith("/lore")) return "lore";
  if (path.startsWith("/characters")) return "characters";
  if (path.startsWith("/media")) return "media";
  if (path.startsWith("/market")) return "market";
  if (path.startsWith("/guides")) return "guide";
  if (path.startsWith("/settings")) return "settings";
  if (path.startsWith("/tools")) return "settings";
  return "dashboard";
}

function Shell({ children }: { children: ReactNode }) {
  const { bootstrap, personaggi, settings, notify } = useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const screen = screenFromPath(location.pathname);
  const background = settings.theme?.backgrounds?.[screen] || "";
  const characterPath = personaggi.giocatore.activePersonaggioId ? `/character/${personaggi.giocatore.activePersonaggioId}` : "/characters";
  const links: Array<[string, string, string, PageShortcutTarget?]> = [
    ["/", "Sala principale", "⌂", "dashboard"],
    [characterPath, "Scheda personaggio", "⚔", "character"],
    ["/skills", "Abilità", "✦", "skills"],
    ["/competencies", "Competenze", "✧", "competencies"],
    ["/creation", "Creazione", "⚗", "creation"],
    ["/combat", "Combattimento", "✦", "combat"],
    ["/travel", "Viaggio", "⌖", "travel"],
    ["/market", "Mercato", "¤", "market"],
    ["/lore", "Lore", "◈", "lore"],
    ["/media", "Archivio immagini", "▧", "media"],
    ["/guides", "Guide", "☷", "guides"],
    ["/settings", "Impostazioni", "⚙", "settings"]
  ];
  const managementLinks: Array<[string, string, string, PageShortcutTarget?]> = [
    ["/tools", "Strumenti", "◆", "tools"],
    ["/tools/characters", "Gestione Personaggi", "♙"],
    ["/tools/items", "Gestione Oggetti", "◇"],
    ["/tools/skills", "Gestione Skill", "✦"],
    ["/tools/units", "Gestione Unit", "⚔"],
    ["/tools/shops", "Gestione Negozi", "¤"],
    ["/tools/ai", "Gestione AI", "✳"],
    ...(settings.security.canManageAdminSettings
      ? [
        ["/tools/players", "Gestione Player", "☺"] as [string, string, string, PageShortcutTarget?],
        ["/tools/backups", "Gestione Backup", "▣"] as [string, string, string, PageShortcutTarget?],
        ["/tools/dice", "Gestisci Dadi", "◆"] as [string, string, string, PageShortcutTarget?],
        ["/tools/themes", "Gestione Temi", "◐"] as [string, string, string, PageShortcutTarget?],
        ["/tools/variables", "Gestione Variabili", "ƒ"] as [string, string, string, PageShortcutTarget?],
      ]
      : []),
  ];
  const routeCharacterId = Number(location.pathname.match(/^\/character\/(\d+)/)?.[1] || 0) || null;
  const activeCharacter = personaggi.personaggi.find((entry) => entry.id === personaggi.giocatore.activePersonaggioId);
  const activeCharacterFirstName = activeCharacter?.name.trim().split(/\s+/)[0];
  const activeCharacterPortrait = personaggi.activePersonaggio?.appearance.portraitUrl;
  const quickCharacterId = routeCharacterId || personaggi.giocatore.activePersonaggioId;
  const quickCharacter = personaggi.personaggi.find((entry) => entry.id === quickCharacterId);
  const activeCampaign = bootstrap.campaigns.find((entry) => entry.id === bootstrap.activeCampaignId) || null;
  const contextualNoteSection: NoteSection | null = location.pathname.startsWith("/character/")
    ? "zaino"
    : location.pathname.startsWith("/combat") ? "combat"
    : location.pathname.startsWith("/competencies") ? "competenze"
    : location.pathname.startsWith("/creation") ? "crafting" : null;
  useEffect(() => {
    const paths: Record<PageShortcutTarget, string> = {
      dashboard: "/",
      character: characterPath,
      skills: "/skills",
      competencies: "/competencies",
      creation: "/creation",
      combat: "/combat",
      travel: "/travel",
      market: "/market",
      lore: "/lore",
      media: "/media",
      guides: "/guides",
      settings: "/settings",
      tools: "/tools",
    };
    // Tutte le combinazioni assegnate (anche quelle degli strumenti rapidi) vengono bloccate qui,
    // così Chrome/Edge non eseguono la loro azione nativa (Alt+D sulla barra indirizzi, menu su Alt).
    const assigned = new Set([...pageShortcutTargets, ...quickToolShortcutTargets].map((entry) => shortcutValue(settings.ui, entry)).filter(Boolean));
    let altChordHandled = false;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return;
      const chord = shortcutFromKeyboardEvent(event);
      if (!chord || !assigned.has(chord)) return;
      altChordHandled = true;
      event.preventDefault();
      const target = pageShortcutTargets.find((entry) => shortcutValue(settings.ui, entry) === chord);
      if (target) navigate(paths[target]);
    };
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.key !== "Alt") return;
      if (altChordHandled) event.preventDefault();
      altChordHandled = false;
    };
    window.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("keyup", onKeyUp, true);
    return () => {
      window.removeEventListener("keydown", onKeyDown, true);
      window.removeEventListener("keyup", onKeyUp, true);
    };
  }, [characterPath, navigate, settings.ui]);
  return (
    <div className="app-shell" data-component-type="app-shell" data-theme={settings.theme?.slug || "default"}>
      <aside className="side-nav" data-component-type="nav" data-theme="dark">
        {/* Il ritratto apre la scheda del personaggio; il nome resta la via per la Sala principale. */}
        <div className="brand-block">
          {activeCharacterPortrait && <Link to={characterPath} className="brand-portrait" aria-label={`Scheda personaggio${activeCharacter ? ` di ${activeCharacter.name}` : ""}`} title="Scheda personaggio">
            <img src={activeCharacterPortrait} alt="" />
          </Link>}
          <Link to="/" className="brand-identity" title="Sala principale">
            <span style={{ "--name-len": (activeCharacterFirstName || "Sala principale").length, "--player-len": settings.giocatore.displayName.length } as CSSProperties}>
              <strong>{activeCharacterFirstName || "Sala principale"}</strong><small>{settings.giocatore.displayName}</small>
            </span>
          </Link>
        </div>
        <NavScroll label="Menu principale">
          {links.map(([href, label, icon, shortcutTarget]) => {
            const shortcut = shortcutTarget ? shortcutValue(settings.ui, shortcutTarget) : "";
            return <Link key={label} to={href} aria-keyshortcuts={shortcut || undefined} title={shortcut ? `${label} (${shortcut.replace("+", " + ")})` : label} className={location.pathname === href || (href !== "/" && location.pathname.startsWith(href)) ? "active" : ""}>
              <span aria-hidden="true">{icon}</span>
              <span className="nav-label" style={{ "--label-len": label.length } as CSSProperties}>{label}</span>
            </Link>;
          })}
          {settings.security.canManageGameData && <div className="nav-management-section">
            <small>Gestione</small>
            {managementLinks.map(([href, label, icon, shortcutTarget]) => {
              const shortcut = shortcutTarget ? shortcutValue(settings.ui, shortcutTarget) : "";
              return <Link key={href} to={href} aria-keyshortcuts={shortcut || undefined} title={shortcut ? `${label} (${shortcut.replace("+", " + ")})` : label} className={location.pathname === href ? "active" : ""}>
                <span aria-hidden="true">{icon}</span>
                <span className="nav-label" style={{ "--label-len": label.length } as CSSProperties}>{label}</span>
              </Link>;
            })}
          </div>}
        </NavScroll>
        {contextualNoteSection && quickCharacterId && quickCharacter && <ContextNoteDock
          key={`${quickCharacterId}:${contextualNoteSection}`}
          characterId={quickCharacterId}
          characterName={quickCharacter.name}
          section={contextualNoteSection}
          notify={notify}
        />}
        {bootstrap.security.showAdminLink && <div className="account-actions">
          <a className="admin-link" href={bootstrap.security.adminUrl} style={{ "--label-len": "Amministrazione Django".length } as CSSProperties}>Amministrazione Django</a>
        </div>}
      </aside>
      <QuickTools characterId={quickCharacterId} characterName={quickCharacter?.name || ""} campaign={activeCampaign} settings={settings} notify={notify} />
      <main className="workspace" data-screen={screen} style={{ "--screen-background": background ? `url(${background})` : "none" } as CSSProperties}>
        <div className="workspace-background" aria-hidden="true" />
        <div className="workspace-content">{children}</div>
      </main>
    </div>
  );
}

/* The native bar sizes its thumb to the content, so a barely-overflowing menu gets a full-height
   slab sitting in the link lane. This keeps a fixed-length ghost thumb in its own gutter instead,
   fading in while scrolling or hovering. */
const NAV_THUMB_HEIGHT = 44;
const NAV_TRACK_INSET = 10;

function NavScroll({ label, children }: { label: string; children: ReactNode }) {
  const scrollRef = useRef<HTMLElement | null>(null);
  const thumbRef = useRef<HTMLDivElement | null>(null);
  const fadeRef = useRef(0);
  const sync = useCallback((reveal?: boolean) => {
    const scroller = scrollRef.current, thumb = thumbRef.current;
    if (!scroller || !thumb) return;
    const range = scroller.scrollHeight - scroller.clientHeight;
    const track = scroller.clientHeight - NAV_THUMB_HEIGHT - NAV_TRACK_INSET * 2;
    thumb.hidden = range <= 1 || track <= 0;
    if (thumb.hidden) return;
    thumb.style.transform = `translateY(${NAV_TRACK_INSET + (scroller.scrollTop / range) * track}px)`;
    if (!reveal) return;
    thumb.dataset.active = "true";
    window.clearTimeout(fadeRef.current);
    fadeRef.current = window.setTimeout(() => { delete thumb.dataset.active; }, 900);
  }, []);
  useEffect(() => {
    const scroller = scrollRef.current;
    if (!scroller) return;
    const onScroll = () => sync(true);
    scroller.addEventListener("scroll", onScroll, { passive: true });
    return () => { scroller.removeEventListener("scroll", onScroll); window.clearTimeout(fadeRef.current); };
  }, [sync]);
  /* Re-run on every render so a changed link set is picked up, and watch the links themselves: the
     list only overflows once fonts and the portrait have settled, which resizes them and not it. */
  useLayoutEffect(() => {
    const scroller = scrollRef.current;
    if (!scroller) return;
    const observer = new ResizeObserver(() => sync());
    observer.observe(scroller);
    for (const child of Array.from(scroller.children)) observer.observe(child);
    return () => observer.disconnect();
  });
  return <div className="nav-scroll">
    <nav className="nav-list" aria-label={label} ref={scrollRef}>{children}</nav>
    <div className="nav-scroll-thumb" ref={thumbRef} aria-hidden="true" hidden />
  </div>;
}

function PageHeader({ eyebrow, title, actions }: { eyebrow?: string; title: string; actions?: ReactNode }) {
  return <header className="page-header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1></div>{actions}</header>;
}

function Dashboard() {
  const { personaggi, settings, notify } = useApp();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const active = personaggi.activePersonaggio;
  const [selected, setSelected] = useState(personaggi.giocatore.activePersonaggioId || personaggi.personaggi[0]?.id);
  const character = personaggi.personaggi.find((entry) => entry.id === selected);
  const selectMutation = useMutation({
    mutationFn: (id: number) => legacyAction<PersonaggiData>("/api/personaggi/select/", "personaggi.select", { personaggioId: id }),
    onSuccess: async (result) => {
      queryClient.setQueryData(["personaggi"], result.data);
      notify("Personaggio attivo aggiornato.");
      navigate(`/character/${result.data.giocatore.activePersonaggioId}`);
    },
    onError: (error: Error) => notify(error.message, "error")
  });
  const logoutMutation = useMutation({
    mutationFn: () => apiRequest<AuthData>("/api/auth/logout/", { method: "POST" }),
    onSuccess: () => {
      queryClient.clear();
      window.location.assign("/login/");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  return <div className="page dashboard-page">
    <PageHeader
      title={personaggi.giocatore.displayName}
      actions={<button className="button secondary dashboard-logout" type="button" onClick={() => logoutMutation.mutate()} disabled={logoutMutation.isPending}>{logoutMutation.isPending ? "Uscita…" : "Esci"}</button>}
    />
    <section className="panel dashboard-active-character" data-component-type="panel" data-theme="parchment">
      <div>
        <p className="eyebrow">Personaggio attivo</p>
        <h2>{active?.name || "Nessun personaggio selezionato"}</h2>
        <p>{active ? `${active.races.join(" / ") || "Razza sconosciuta"} · livello ${active.level}` : "Scegli un personaggio dalla compagnia per preparare la tua postazione di gioco."}</p>
      </div>
      {active && <div className="dashboard-shortcuts" aria-label="Azioni del personaggio attivo">
        <Link className="button primary" to={`/character/${active.id}`}>Apri la scheda</Link>
        <Link className="button secondary" to="/skills">Abilità</Link>
        <Link className="button secondary" to="/competencies">Competenze</Link>
        <Link className="button secondary" to="/creation">Creazione</Link>
      </div>}
    </section>
    <div className="selection-layout dashboard-character-selection">
      <section className="panel list-panel"><h2>{settings.security.canManageGameData ? "Personaggi della campagna" : "I miei personaggi"}</h2><div className="character-list">
        {personaggi.personaggi.map((entry) => <button key={entry.id} className={entry.id === selected ? "active" : ""} onClick={() => setSelected(entry.id)}><strong>{entry.name}</strong><span>{entry.races.join(" / ") || "Razza sconosciuta"} · livello {entry.level}</span></button>)}
      </div>{!personaggi.personaggi.length && <div className="management-empty-state"><strong>Nessun personaggio assegnato</strong><p>Vedi soltanto i personaggi che ti sono stati assegnati. Chiedine uno dalle Impostazioni → Profilo, oppure fatteli assegnare da un master.</p></div>}</section>
      <section className="panel character-preview">{character ? <><p className="eyebrow">{character.type}</p><h2>{character.name}</h2><p>{character.races.join(" / ")} · livello {character.level}</p><p className="long-copy">{character.details}</p><div className="stat-chip-row">{character.primaryTotals.map((stat) => <span key={stat.key}><small>{stat.label}</small><strong>{stat.value}</strong></span>)}</div><div className="button-row"><button className="button primary" disabled={selectMutation.isPending} onClick={() => selectMutation.mutate(character.id)}>Imposta e apri</button><Link className="button secondary" to={`/character/${character.id}`}>Apri senza cambiare</Link></div></> : <p>Nessun personaggio disponibile.</p>}</section>
    </div>
  </div>;
}

function renderGuideText(text?: string) {
  return (text ?? "").split(/(\[[^\]]+\]\(\/(?:[^)]*)\))/g).map((part, index) => {
    const match = part.match(/^\[([^\]]+)\]\((\/[^)]*)\)$/);
    return match ? <Link key={index} to={match[2]}>{match[1]}</Link> : part;
  });
}

function VariableReferenceBlock({ groups }: { groups: GuideVariableGroup[] }) {
  const flat = useMemo(
    () => groups.flatMap((group) => group.variables.map((variable) => ({ variable, group }))),
    [groups],
  );
  const [selectedKey, setSelectedKey] = useState<string | undefined>(flat[0]?.variable.key);
  const [query, setQuery] = useState("");
  const normalized = query.trim().toLocaleLowerCase("it");
  const matches = (variable: GuideVariable) =>
    !normalized || `${variable.label} ${variable.key} ${variable.description}`.toLocaleLowerCase("it").includes(normalized);
  const current = flat.find((entry) => entry.variable.key === selectedKey) ?? flat[0];
  return <div className="variable-reference">
    <div className="variable-reference-index">
      <input
        type="search"
        className="variable-reference-search"
        placeholder="Cerca una variabile…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-label="Cerca una variabile"
      />
      <div className="variable-reference-list" role="listbox" aria-label="Variabili del personaggio">
        {groups.map((group) => {
          const visible = group.variables.filter(matches);
          if (!visible.length) return null;
          return <div className="variable-reference-group" key={group.label}>
            <p className="variable-reference-group-label">{group.label}</p>
            {visible.map((variable) => <button
              type="button"
              key={variable.key}
              role="option"
              aria-selected={current?.variable.key === variable.key}
              className={current?.variable.key === variable.key ? "active" : ""}
              onClick={() => setSelectedKey(variable.key)}
            ><strong>{variable.label}</strong><code>{variable.key}</code></button>)}
          </div>;
        })}
      </div>
    </div>
    <div className="variable-reference-detail">
      {current ? <>
        <p className="eyebrow">{current.group.label}</p>
        <h4>{current.variable.label} <code>{current.variable.key}</code></h4>
        <p>{renderGuideText(current.variable.description)}</p>
        {current.variable.facts.length > 0 && <ul className="variable-reference-facts">
          {current.variable.facts.map((fact, index) => <li key={index}>{renderGuideText(fact)}</li>)}
        </ul>}
        {current.group.note && <aside className="callout">
          <strong>{current.group.note.title}</strong>
          <p>{renderGuideText(current.group.note.text)}</p>
        </aside>}
      </> : <p className="muted-copy">Nessuna variabile corrisponde alla ricerca.</p>}
    </div>
  </div>;
}

function GuidesPage() {
  const { bootstrap } = useApp();
  const [selected, setSelected] = useState<Guide | undefined>(bootstrap.guides[0]);
  // The Elder rules are injected as raw HTML, so cross-guide links arrive as
  // anchors carrying the target guide name instead of React elements.
  const openLinkedGuide = (event: MouseEvent<HTMLElement>) => {
    const anchor = (event.target as HTMLElement).closest<HTMLAnchorElement>("a[data-guide]");
    const target = anchor && bootstrap.guides.find((guide) => guide.name === anchor.dataset.guide);
    if (!target) return;
    event.preventDefault();
    setSelected(target);
  };
  const renderBlock = (block: Guide["content"][number], index: number) => {
    if (block.type === "legacy_html") return <section className="elder-rules-guide" key={index} onClick={openLinkedGuide} dangerouslySetInnerHTML={{ __html: block.html ?? "" }} />;
    if (block.type === "variable_reference") return <VariableReferenceBlock key={index} groups={block.groups ?? []} />;
    if (block.type === "item_compendium") return <ItemCompendium key={index} />;
    if (block.type === "heading") return <h3 key={index}>{renderGuideText(block.text)}</h3>;
    if (block.type === "list") return <ul key={index}>{(block.items as string[] | undefined)?.map((item) => <li key={item}>{renderGuideText(item)}</li>)}</ul>;
    if (block.type === "entries") return <div className="guide-entries" key={index}>{(block.items as GuideEntry[] | undefined)?.map((entry) => <article key={entry.title}><strong>{entry.title}</strong>{entry.meta && <span>{entry.meta}</span>}{entry.note && <p>{renderGuideText(entry.note)}</p>}</article>)}</div>;
    if (block.type === "code") return <pre data-language={block.language} key={index}>{block.text}</pre>;
    if (block.type === "callout") return <aside className="callout" key={index}><strong>{block.title}</strong><p>{renderGuideText(block.text)}</p></aside>;
    if (block.type === "warning") return <aside className="callout guide-warning" key={index}><strong>{block.title}</strong><p>{renderGuideText(block.text)}</p></aside>;
    return <p key={index}>{renderGuideText(block.text)}</p>;
  };
  return <div className="page"><PageHeader eyebrow="Conoscenza" title="Guide" /><div className="selection-layout guide-layout"><aside className="panel guide-index">{bootstrap.guides.map((guide) => <button className={selected?.name === guide.name ? "active" : ""} onClick={() => setSelected(guide)} key={guide.name}><strong>{guide.name}</strong><span>{guide.category}</span></button>)}</aside><article className="panel guide-reader"><p className="eyebrow">{selected?.category}</p><h2>{selected?.name}</h2>{selected?.content.map(renderBlock)}</article></div></div>;
}

type MediaConfirmState =
  | { kind: "delete"; detail: MediaDetailData }
  | { kind: "move"; detail: MediaDetailData; categoryId: number; group: string };

type MediaMoveDraft = { detail: MediaDetailData; categoryId: string; group: string };

function MediaAssetCard({ asset, busy, onOpen, onMove, onDelete, onLimitedVisibility }: {
  asset: MediaAsset;
  busy: boolean;
  onOpen: (asset: MediaAsset) => void;
  onMove: (asset: MediaAsset) => void;
  onDelete: (asset: MediaAsset) => void;
  onLimitedVisibility: (asset: MediaAsset) => void;
}) {
  return <figure className="media-asset-card">
    <button type="button" className="media-asset-open" onClick={() => onOpen(asset)} aria-label={`Apri ${asset.title}`}>
      <img src={asset.thumbnailUrl || asset.url} alt="" />
    </button>
    <figcaption><strong>{asset.title}</strong><span>{(asset.sizeBytes / 1024).toFixed(0)} KB</span></figcaption>
    {(asset.canMove || asset.canDelete || asset.canSetLimitedVisibility) && <div className="media-asset-actions">
      {asset.canMove && <button type="button" disabled={busy} onClick={() => onMove(asset)}>Sposta</button>}
      {asset.canDelete && <button type="button" className="danger" disabled={busy} onClick={() => onDelete(asset)}>Elimina</button>}
      {asset.canSetLimitedVisibility && <button type="button" className={asset.limitedVisibility ? "limited-on" : "limited-off"} disabled={busy} onClick={() => onLimitedVisibility(asset)} aria-pressed={asset.limitedVisibility}>Limitata</button>}
    </div>}
  </figure>;
}

function MediaUsageConfirmation({ state }: { state: MediaConfirmState }) {
  const verb = state.kind === "delete" ? "eliminare" : "spostare";
  if (!state.detail.usages.length) {
    return <div className="media-confirmation-copy"><p>Sei sicuro di voler {verb} l'immagine <strong>“{state.detail.asset.title}”</strong>?</p></div>;
  }
  return <div className="media-confirmation-copy usage-warning">
    <p>L'immagine è usata da <strong>{state.detail.usages.map((usage) => usage.label).join(", ")}</strong>. Sei sicuro di volerla {verb}?</p>
    <ul>{state.detail.usages.map((usage) => <li key={`${usage.model}-${usage.id}-${usage.field}`}><span>{usage.label}</span>{state.kind === "delete" && usage.deletionBehavior === "cascade" && <small>Il record collegato verrà eliminato.</small>}{state.kind === "delete" && usage.deletionBehavior === "clear" && <small>Il collegamento all'immagine verrà rimosso.</small>}</li>)}</ul>
  </div>;
}

function MediaPage() {
  const { media, mediaCategories, notify } = useApp();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const didSetDefaultCategory = useRef(false);
  const [group, setGroup] = useState("");
  const [loadingAssetId, setLoadingAssetId] = useState<number | null>(null);
  const [previewAsset, setPreviewAsset] = useState<MediaAsset | null>(null);
  const [moveDraft, setMoveDraft] = useState<MediaMoveDraft | null>(null);
  const [confirmation, setConfirmation] = useState<MediaConfirmState | null>(null);
  useEffect(() => {
    if (didSetDefaultCategory.current || !mediaCategories.length) return;
    const defaultCategory = mediaCategories.find((category) => category.slug === "scene-di-gioco");
    if (defaultCategory) setCategoryId(String(defaultCategory.id));
    didSetDefaultCategory.current = true;
  }, [mediaCategories]);
  const uploadMutation = useMutation({
    mutationFn: ({ file, title, notes, selectedCategoryId, selectedGroup, limitedVisibility }: { file: File; title: string; notes: string; selectedCategoryId: number; selectedGroup: string; limitedVisibility: boolean }) => uploadMedia(file, title, notes, "generic", selectedCategoryId, selectedGroup, { limitedVisibility }),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["media"] }); notify("Immagine aggiunta all'archivio."); },
    onError: (error: Error) => notify(error.message, "error")
  });
  const deleteMutation = useMutation({
    mutationFn: (assetId: number) => deleteMedia(assetId),
    onSuccess: async () => {
      setConfirmation(null);
      await queryClient.invalidateQueries({ queryKey: ["media"] });
      notify("Immagine eliminata dall'archivio.");
    },
    onError: (error: Error) => notify(error.message, "error")
  });
  const moveMutation = useMutation({
    mutationFn: ({ assetId, destinationCategoryId, destinationGroup }: { assetId: number; destinationCategoryId: number; destinationGroup: string }) => moveMedia(assetId, destinationCategoryId, destinationGroup),
    onSuccess: async () => {
      setConfirmation(null);
      await queryClient.invalidateQueries({ queryKey: ["media"] });
      notify("Immagine spostata.");
    },
    onError: (error: Error) => notify(error.message, "error")
  });
  const limitedMutation = useMutation({
    mutationFn: (asset: MediaAsset) => setMediaLimitedVisibility(asset.id, !asset.limitedVisibility),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["media"] });
      notify(result.events[0]?.message || "Visibilità immagine aggiornata.");
    },
    onError: (error: Error) => notify(error.message, "error")
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get("file");
    if (file instanceof File && file.size) uploadMutation.mutate({
      file,
      title: String(form.get("title") || ""),
      notes: String(form.get("notes") || ""),
      selectedCategoryId: Number(form.get("categoryId")),
      selectedGroup: String(form.get("group") || ""),
      limitedVisibility: form.get("limitedVisibility") === "on",
    });
  };
  const loadDetail = async (asset: MediaAsset) => {
    setLoadingAssetId(asset.id);
    try {
      return await getMediaDetail(asset.id);
    } catch (error) {
      notify((error as Error).message, "error");
      return null;
    } finally {
      setLoadingAssetId(null);
    }
  };
  const beginDelete = async (asset: MediaAsset) => {
    const detail = await loadDetail(asset);
    if (detail) setConfirmation({ kind: "delete", detail });
  };
  const beginMove = async (asset: MediaAsset) => {
    const detail = await loadDetail(asset);
    if (detail) setMoveDraft({ detail, categoryId: String(detail.asset.categoryId || ""), group: detail.asset.group });
  };
  const continueMove = () => {
    if (!moveDraft?.categoryId || !moveDraft.group.trim()) {
      notify("Scegli una categoria e inserisci il gruppo di destinazione.", "error");
      return;
    }
    setConfirmation({
      kind: "move",
      detail: moveDraft.detail,
      categoryId: Number(moveDraft.categoryId),
      group: moveDraft.group.trim(),
    });
    setMoveDraft(null);
  };
  const confirmAction = () => {
    if (!confirmation) return;
    if (confirmation.kind === "delete") {
      deleteMutation.mutate(confirmation.detail.asset.id);
      return;
    }
    moveMutation.mutate({
      assetId: confirmation.detail.asset.id,
      destinationCategoryId: confirmation.categoryId,
      destinationGroup: confirmation.group,
    });
  };
  const normalized = query.trim().toLocaleLowerCase("it");
  const visible = media.filter((asset) => {
    const matchesText = !normalized || `${asset.title} ${asset.category} ${asset.group} ${asset.notes}`.toLocaleLowerCase("it").includes(normalized);
    return matchesText && (!categoryId || asset.categoryId === Number(categoryId)) && (!group || asset.group === group);
  });
  const groups = [...new Set(media.filter((asset) => !categoryId || asset.categoryId === Number(categoryId)).map((asset) => asset.group))].sort((left, right) => left.localeCompare(right, "it"));
  const sections = mediaCategories.map((category) => ({
    category,
    groups: [...new Set(visible.filter((asset) => asset.categoryId === category.id).map((asset) => asset.group))].map((groupName) => ({
      name: groupName,
      assets: visible.filter((asset) => asset.categoryId === category.id && asset.group === groupName),
    })),
  })).filter((section) => section.groups.some((entry) => entry.assets.length));
  const uncategorized = visible.filter((asset) => !asset.categoryId);
  const actionPending = deleteMutation.isPending || moveMutation.isPending || limitedMutation.isPending;
  return <div className="page media-library-page"><PageHeader eyebrow="Archivio" title="Immagini" />
    <div className="media-library-layout">
      <aside className="panel media-upload-panel"><form className="stacked-form" onSubmit={submit}><h2>Aggiungi immagine</h2><label>Titolo<input name="title" maxLength={160} /></label><label>Categoria<select name="categoryId" required defaultValue=""><option value="" disabled>Scegli categoria</option>{mediaCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label>Gruppo<input name="group" maxLength={160} placeholder="Es. Oggetti, PNG, Bosco del Nord…" required /></label><label>File<input name="file" type="file" accept="image/*" required /></label><label>Note<textarea name="notes" rows={4} /></label><label className="media-limited-upload"><input name="limitedVisibility" type="checkbox" />Visibilità limitata</label><button className="button primary" disabled={uploadMutation.isPending || !mediaCategories.length}>Carica</button><small>Le immagini con visibilità limitata compaiono nell'Archivio soltanto a Master e Amministratori.</small><small>Le categorie si configurano esclusivamente dall'Amministrazione Django. Il gruppo è libero e serve a suddividere ogni categoria.</small></form></aside>
      <section className="media-browser"><div className="panel media-browser-toolbar" data-component-type="toolbar" data-theme="default"><label>Cerca<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Titolo, categoria, gruppo…" /></label><label>Categoria<select value={categoryId} onChange={(event) => { setCategoryId(event.target.value); setGroup(""); }}><option value="">Tutte</option>{mediaCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label>Gruppo<select value={group} onChange={(event) => setGroup(event.target.value)}><option value="">Tutti</option>{groups.map((entry) => <option key={entry}>{entry}</option>)}</select></label><strong>{visible.length} immagini</strong></div>
        {sections.map((section) => <section className="panel media-category-section" key={section.category.id} data-component-type="panel" data-theme="default"><header><div><p className="eyebrow">Categoria</p><h2>{section.category.name}</h2></div><span>{section.groups.reduce((total, entry) => total + entry.assets.length, 0)}</span></header>{section.groups.map((entry) => <div className="media-group-section" key={entry.name}><h3>{entry.name}</h3><div className="media-grid">{entry.assets.map((asset) => <MediaAssetCard key={asset.id} asset={asset} busy={loadingAssetId === asset.id || (limitedMutation.isPending && limitedMutation.variables?.id === asset.id)} onOpen={setPreviewAsset} onMove={beginMove} onDelete={beginDelete} onLimitedVisibility={(entry) => limitedMutation.mutate(entry)} />)}</div></div>)}</section>)}
        {uncategorized.length > 0 && <section className="panel media-category-section"><header><h2>Senza categoria</h2></header><div className="media-grid">{uncategorized.map((asset) => <MediaAssetCard key={asset.id} asset={asset} busy={loadingAssetId === asset.id || (limitedMutation.isPending && limitedMutation.variables?.id === asset.id)} onOpen={setPreviewAsset} onMove={beginMove} onDelete={beginDelete} onLimitedVisibility={(entry) => limitedMutation.mutate(entry)} />)}</div></section>}
        {!visible.length && <div className="management-empty-state"><strong>Nessuna immagine trovata</strong><p>Prova a cambiare categoria, gruppo o ricerca.</p></div>}
      </section>
    </div>
    {previewAsset && <Modal title={previewAsset.title} onClose={() => setPreviewAsset(null)} wide className="media-preview-modal">
      <div className="media-asset-preview">
        <img src={previewAsset.url} alt={previewAsset.title} />
        <footer><span>{previewAsset.category || "Senza categoria"} · {previewAsset.group}</span><a className="button secondary" href={previewAsset.url} target="_blank" rel="noreferrer">Apri originale</a></footer>
      </div>
    </Modal>}
    {moveDraft && <Modal title="Sposta immagine" onClose={() => setMoveDraft(null)} footer={<><button type="button" className="button secondary" onClick={() => setMoveDraft(null)}>Annulla</button><button type="button" className="button primary" onClick={continueMove}>Continua</button></>}>
      <div className="media-move-form"><div className="media-move-preview"><img src={moveDraft.detail.asset.thumbnailUrl || moveDraft.detail.asset.url} alt="" /><span><strong>{moveDraft.detail.asset.title}</strong><small>{moveDraft.detail.asset.category} · {moveDraft.detail.asset.group}</small></span></div><label>Categoria di destinazione<select value={moveDraft.categoryId} onChange={(event) => setMoveDraft({ ...moveDraft, categoryId: event.target.value })}><option value="" disabled>Scegli categoria</option>{mediaCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label>Gruppo di destinazione<input value={moveDraft.group} maxLength={160} onChange={(event) => setMoveDraft({ ...moveDraft, group: event.target.value })} /></label></div>
    </Modal>}
    {confirmation && <Modal title={confirmation.kind === "delete" ? "Elimina immagine" : "Conferma spostamento"} onClose={() => !actionPending && setConfirmation(null)} footer={<><button type="button" className="button secondary" disabled={actionPending} onClick={() => setConfirmation(null)}>Annulla</button><button type="button" className={`button ${confirmation.kind === "delete" ? "danger" : "primary"}`} disabled={actionPending} onClick={confirmAction}>{confirmation.kind === "delete" ? "Sì, elimina" : "Sì, sposta"}</button></>}>
      <MediaUsageConfirmation state={confirmation} />
      {confirmation.kind === "move" && <p className="media-move-destination">Destinazione: <strong>{mediaCategories.find((category) => category.id === confirmation.categoryId)?.name} · {confirmation.group}</strong></p>}
    </Modal>}
  </div>;
}

function SettingControl({ setting, value, invalid = false, onChange }: { setting: SettingData; value: unknown; invalid?: boolean; onChange: (value: unknown) => void }) {
  if (setting.valueType === "boolean") return <input type="checkbox" checked={Boolean(value)} disabled={!setting.editable} onChange={(event) => onChange(event.target.checked)} />;
  if (setting.valueType === "select") return <select value={String(value ?? "")} disabled={!setting.editable} aria-invalid={invalid || undefined} onChange={(event) => onChange(event.target.value)}>{setting.choices.map((choice) => { const data = typeof choice === "string" ? { value: choice, label: choice } : choice; return <option key={data.value} value={data.value}>{data.label}</option>; })}</select>;
  if (setting.valueType === "color") return <input type="color" value={String(value || "#000000")} disabled={!setting.editable} onChange={(event) => onChange(event.target.value)} />;
  if (setting.valueType === "integer" && setting.key === "appearance.font_scale") {
    const scale = Number(value ?? 100);
    return <div className="font-scale-control"><input aria-label={setting.label} type="range" value={scale} min={setting.constraints.minimum ?? MIN_FONT_SCALE} max={setting.constraints.maximum ?? MAX_FONT_SCALE} step={setting.constraints.step ?? 5} disabled={!setting.editable} onChange={(event) => onChange(Number(event.target.value))} /><output aria-live="polite">{scale}%</output></div>;
  }
  if (setting.valueType === "integer") return <input type="number" value={Number(value ?? 0)} min={setting.constraints.minimum} max={setting.constraints.maximum} step={setting.constraints.step} disabled={!setting.editable} onChange={(event) => onChange(Number(event.target.value))} />;
  return <input value={String(value ?? "")} disabled={!setting.editable} onChange={(event) => onChange(event.target.value)} />;
}

function PlayerSettingsPanel() {
  const { settings, notify } = useApp();
  const queryClient = useQueryClient();
  const [alias, setAlias] = useState(settings.player.alias);
  const [selectedCharacters, setSelectedCharacters] = useState<Set<number>>(() => new Set());
  const [assignmentMessage, setAssignmentMessage] = useState("");
  const [masterCode, setMasterCode] = useState("");
  const [adminCode, setAdminCode] = useState("");
  const [selectedRole, setSelectedRole] = useState(settings.security.role);
  useEffect(() => setAlias(settings.player.alias), [settings.player.alias]);
  useEffect(() => setSelectedRole(settings.security.role), [settings.security.role]);
  const mutation = useMutation({
    mutationFn: ({ action, payload }: { action: string; payload: Record<string, unknown> }) => legacyAction<SettingsData>("/api/settings/", action, payload),
    onSuccess: async (result) => {
      queryClient.setQueryData(["settings"], result.data);
      setSelectedCharacters(new Set());
      setAssignmentMessage("");
      setMasterCode("");
      setAdminCode("");
      // Permission-bearing payloads must not survive an active-role change.
      await queryClient.invalidateQueries();
      notify(result.events[0]?.message || "Profilo giocatore aggiornato.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const toggleCharacter = (characterId: number, checked: boolean) => setSelectedCharacters((current) => {
    const next = new Set(current);
    if (checked) next.add(characterId); else next.delete(characterId);
    return next;
  });
  const requestableCharacters = settings.player.characters.filter((character) => !character.assigned);
  const statusLabel = (status: string) => status === "pending" ? "Richiesta in attesa" : status === "approved" ? "Assegnato" : status === "rejected" ? "Richiesta rifiutata · puoi riprovare" : "Disponibile su richiesta";

  return <section className="panel player-settings-panel" data-component-type="panel" data-theme="gold">
    <header><div><p className="eyebrow">Profilo</p><h2>{settings.security.role === "admin" ? "Admin" : settings.security.role === "master" ? "Master" : "Giocatore"}</h2></div><p>Alias, personaggi richiesti e livello di accesso personale.</p></header>
    <div className="player-settings-grid">
      <form onSubmit={(event) => { event.preventDefault(); mutation.mutate({ action: "player.updateAlias", payload: { profile: { alias } } }); }}>
        <h3>Alias</h3><p>È il nome mostrato nell'interfaccia agli altri partecipanti.</p>
        <label>Alias giocatore<input value={alias} maxLength={120} onChange={(event) => setAlias(event.target.value)} /></label>
        <button className="button primary" disabled={mutation.isPending || !alias.trim()}>Salva alias</button>
      </form>
      <form className="player-character-request" onSubmit={(event) => { event.preventDefault(); mutation.mutate({ action: "player.requestCharacters", payload: { assignmentRequest: { characterIds: [...selectedCharacters], message: assignmentMessage } } }); }}>
        <h3>Richiedi personaggi</h3><p>La richiesta resta in attesa finché un amministratore Django non la approva.</p>
        <div>{requestableCharacters.length ? requestableCharacters.map((character) => {
          const pending = character.requestStatus === "pending";
          return <label key={character.id} data-status={character.requestStatus || "available"}><input type="checkbox" checked={selectedCharacters.has(character.id)} disabled={pending || mutation.isPending} onChange={(event) => toggleCharacter(character.id, event.target.checked)} /><span><strong>{character.name}</strong><small>{statusLabel(character.requestStatus)}</small></span></label>;
        }) : <p className="muted-copy">Tutti i personaggi disponibili sono già assegnati.</p>}</div>
        <label>Messaggio facoltativo<textarea rows={2} maxLength={1000} value={assignmentMessage} onChange={(event) => setAssignmentMessage(event.target.value)} /></label>
        <button className="button primary" disabled={mutation.isPending || !selectedCharacters.size}>Invia richiesta</button>
      </form>
      <section className="player-role-codes"><h3>Livello di accesso</h3><p>Il ruolo di gioco è separato dai permessi dell'Amministrazione Django.</p><form onSubmit={(event) => { event.preventDefault(); mutation.mutate({ action: "player.selectRole", payload: { roleSelection: { targetRole: selectedRole, code: selectedRole === "master" ? masterCode : selectedRole === "admin" ? adminCode : "" } } }); }}><label>Ruolo<select value={selectedRole} onChange={(event) => setSelectedRole(event.target.value as typeof selectedRole)}><option value="user">Giocatore</option><option value="master">Master</option><option value="admin">Admin</option></select></label>{!settings.security.canUseDjangoAdmin && selectedRole === "master" && selectedRole !== settings.security.role && <label>Codice Master<input type="password" autoComplete="off" value={masterCode} onChange={(event) => setMasterCode(event.target.value)} /></label>}{!settings.security.canUseDjangoAdmin && selectedRole === "admin" && selectedRole !== settings.security.role && <label>Codice Admin<input type="password" autoComplete="off" value={adminCode} onChange={(event) => setAdminCode(event.target.value)} /></label>}<button className="button secondary" disabled={mutation.isPending || (!settings.security.canUseDjangoAdmin && selectedRole === "master" && selectedRole !== settings.security.role && !masterCode.trim()) || (!settings.security.canUseDjangoAdmin && selectedRole === "admin" && selectedRole !== settings.security.role && !adminCode.trim())}>{selectedRole === settings.security.role ? "Ruolo attivo" : "Applica ruolo"}</button></form>{settings.security.canUseDjangoAdmin ? <small>Sei un amministratore Django: puoi passare liberamente tra tutti i ruoli di gioco senza perdere l'accesso a Django Admin.</small> : <small>Master e Admin richiedono il rispettivo codice configurato dall'amministratore Django. I codici non sono visibili qui.</small>}</section>
    </div>
  </section>;
}

type SettingsTabId = "profilo" | "aspetto" | "accessibilita" | "dadi" | "audio" | "scorciatoie" | "sessione" | "amministrazione" | "altro";

// Ordine deliberato: prima ciò che riguarda il giocatore, poi la sessione, infine l'amministrazione.
// Le categorie non elencate qui confluiscono nella scheda "Altro", così nessuna impostazione resta invisibile.
const SETTINGS_TABS: Array<{ id: SettingsTabId; label: string; categories: string[] }> = [
  { id: "profilo", label: "Profilo", categories: [] },
  { id: "aspetto", label: "Aspetto", categories: ["aspetto", "aspetto globale"] },
  { id: "accessibilita", label: "Accessibilità", categories: ["accessibilità"] },
  { id: "dadi", label: "Dadi", categories: ["dadi"] },
  { id: "audio", label: "Audio", categories: ["audio"] },
  { id: "scorciatoie", label: "Scorciatoie", categories: ["scorciatoie da tastiera"] },
  { id: "sessione", label: "Sessione", categories: ["sessione"] },
  { id: "amministrazione", label: "Amministrazione", categories: ["identità", "navigazione", "sicurezza", "funzioni"] },
  { id: "altro", label: "Altro", categories: [] },
];
const MAPPED_SETTING_CATEGORIES = new Set(SETTINGS_TABS.flatMap((tab) => tab.categories));

function SettingsPage() {
  const { bootstrap, settings, notify } = useApp();
  const queryClient = useQueryClient();
  const [values, setValues] = useState<Record<string, unknown>>(() => Object.fromEntries(settings.settings.map((setting) => [setting.key, setting.value])));
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(() => new Set());
  const [restartConfirmation, setRestartConfirmation] = useState(false);
  const [restartingMode, setRestartingMode] = useState<string | null>(null);
  useEffect(() => setValues((current) => Object.fromEntries(settings.settings.map((setting) => [setting.key, dirtyKeys.has(setting.key) ? current[setting.key] : setting.value]))), [settings, dirtyKeys]);
  useEffect(() => applyUiPreferences(settings, values), [settings, values]);
  useEffect(() => () => applyUiPreferences(settings), [settings]);
  const mutation = useMutation({
    mutationFn: ({ restart, modeChange }: { restart: boolean; modeChange: boolean }) => legacyAction<SettingsData>("/api/settings/", "settings.save", { settings: values }).then(async (result) => {
      if (restart) await apiRequest<{ accepted: boolean }>("/api/system/restart/", { method: "POST" });
      return { result, restart, modeChange };
    }),
    onSuccess: ({ result, restart, modeChange }) => {
      setDirtyKeys(new Set());
      setRestartConfirmation(false);
      queryClient.setQueryData(["settings"], result.data);
      if (restart) {
        setRestartingMode(String(values["security.access_mode"] || "locked"));
      } else if (modeChange) {
        notify("Modalità salvata. Riavvia ReDjango manualmente per applicarla.", "info");
      } else {
        notify("Impostazioni salvate.");
      }
    },
    onError: (error: Error) => notify(error.message, "error")
  });
  const campaignMutation = useMutation({
    mutationFn: (campaignId: number) => command<{ campaigns: Pick<BootstrapData, "activeCampaignId" | "campaigns"> }>("campaign.select", { campaignId }, "settings"),
    onSuccess: async (result) => {
      queryClient.setQueryData<BootstrapData>(["bootstrap"], (current) => current ? { ...current, ...result.data.campaigns } : current);
      await queryClient.invalidateQueries({ queryKey: ["personaggi"] });
      notify("Campagna selezionata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const groups = useMemo(() => settings.settings.reduce<Record<string, SettingData[]>>((result, setting) => {
    (result[setting.category] ||= []).push(setting);
    return result;
  }, {}), [settings.settings]);
  const selectedShortcutProfile = shortcutProfile(values);
  // Con i profili fissi il modulo mostra le assegnazioni del profilo, non i valori personalizzati salvati.
  const displayedValues = useMemo(
    () => (selectedShortcutProfile === "custom"
      ? values
      : Object.fromEntries(Object.entries(values).map(([key, value]) => [key, shortcutSettingValue(selectedShortcutProfile, key, value)]))),
    [values, selectedShortcutProfile],
  );
  const shortcutConflicts = useMemo(() => shortcutConflictKeys(displayedValues), [displayedValues]);
  const updateValue = (key: string, value: unknown) => { setDirtyKeys((current) => new Set(current).add(key)); setValues((current) => ({ ...current, [key]: value })); };
  const accessModeChanged = dirtyKeys.has("security.access_mode")
    && values["security.access_mode"] !== settings.runtime.configuredAccessMode;
  const requestedAccessMode = String(values["security.access_mode"] || "locked");
  const onlineConfigurationMissing = requestedAccessMode === "online" && !settings.runtime.onlineReady;
  const saveSettings = () => {
    if (accessModeChanged) {
      setRestartConfirmation(true);
      return;
    }
    mutation.mutate({ restart: false, modeChange: false });
  };

  const tabs = useMemo(() => {
    const unmapped = Object.keys(groups).filter((category) => !MAPPED_SETTING_CATEGORIES.has(category)).sort((left, right) => left.localeCompare(right, "it"));
    return SETTINGS_TABS.map((tab) => {
      const categories = (tab.id === "altro" ? unmapped : tab.categories).filter((category) => groups[category]?.length);
      const hasPanel = tab.id === "profilo"
        || (tab.id === "sessione" && settings.security.canManageMasterSettings)
        || (tab.id === "dadi" && settings.security.canManageAdminSettings);
      const pending = categories.reduce((total, category) => total + groups[category].filter((setting) => dirtyKeys.has(setting.key)).length, 0);
      return { ...tab, categories, pending, hasPanel };
    }).filter((tab) => tab.hasPanel || tab.categories.length);
  }, [groups, dirtyKeys, settings.security]);
  const [activeTabId, setActiveTabId] = useState<SettingsTabId>("profilo");
  const activeTab = tabs.find((tab) => tab.id === activeTabId) || tabs[0];

  return <div className="page"><PageHeader eyebrow="Preferenze" title="Impostazioni" />
    <nav className="settings-tabs" role="tablist" aria-label="Sezioni delle impostazioni">
      {tabs.map((tab) => <button
        key={tab.id}
        type="button"
        role="tab"
        id={`settings-tab-${tab.id}`}
        aria-controls={`settings-panel-${tab.id}`}
        aria-selected={activeTab?.id === tab.id}
        className={activeTab?.id === tab.id ? "active" : ""}
        onClick={() => setActiveTabId(tab.id)}
      >{tab.label}{tab.pending > 0 && <span title={`${tab.pending} modifiche non salvate`}>{tab.pending}</span>}</button>)}
    </nav>
    {activeTab && <div className="settings-tab-panel" role="tabpanel" id={`settings-panel-${activeTab.id}`} aria-labelledby={`settings-tab-${activeTab.id}`}>
      {activeTab.id === "profilo" && <PlayerSettingsPanel />}
      {activeTab.id === "sessione" && settings.security.canManageMasterSettings && <section className="panel campaign-settings-panel" data-component-type="panel" data-theme="gold"><div><p className="eyebrow">Sessione</p><h2>Campagna attiva</h2><p>Scegli la campagna mostrata nella postazione. Il cambio può deselezionare il personaggio attivo.</p></div><label><span>Campagna</span><select value={bootstrap.activeCampaignId ?? ""} disabled={campaignMutation.isPending || !bootstrap.campaigns.length} onChange={(event) => campaignMutation.mutate(Number(event.target.value))}>{bootstrap.campaigns.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.name}</option>)}</select></label></section>}
      {activeTab.categories.length > 0 && <form onSubmit={(event) => { event.preventDefault(); saveSettings(); }}>
        <div className="settings-grid" data-columns={activeTab.categories.length === 1 ? "1" : "2"}>{activeTab.categories.map((category) => <section className="panel" key={category}><h2>{category}</h2>{groups[category].map((setting) => {
          const shortcutConflict = shortcutConflicts.has(setting.key);
          const profileLocked = setting.key.startsWith("shortcuts.") && setting.key !== "shortcuts.profile" && selectedShortcutProfile !== "custom";
          const displayed = displayedValues[setting.key];
          return <label className={`setting-row ${shortcutConflict ? "setting-row-conflict" : ""}`} key={setting.key}><span><strong>{setting.label}</strong><small>{setting.description}</small>{shortcutConflict && <small className="setting-inline-warning" role="alert">Questa combinazione è già assegnata a un'altra azione.</small>}</span>{profileLocked
            ? <output className="setting-fixed-value" title={`Assegnazione del profilo ${selectedShortcutProfile === "fast" ? "Veloce" : "Standard"}`}>{String(displayed ?? "").replace("+", " + ")}</output>
            : <SettingControl setting={setting} value={displayed} invalid={shortcutConflict} onChange={(value) => updateValue(setting.key, value)} />}</label>;
        })}{category === SHORTCUT_CATEGORY && FIXED_SHORTCUTS.map((entry) => <div className="setting-row setting-row-fixed" key={entry.id}>
          <span><strong>{entry.label}</strong><small>{entry.description}</small></span>
          <output className="setting-fixed-value" title="Scorciatoia di sistema: non modificabile">{entry.chord}</output>
        </div>)}</section>)}</div>
        <div className="sticky-actions">{shortcutConflicts.size > 0 ? <small className="setting-save-warning" role="alert">Risolvi i conflitti tra scorciatoie prima di salvare.</small> : dirtyKeys.size > 0 && <small>{dirtyKeys.size === 1 ? "1 modifica non salvata" : `${dirtyKeys.size} modifiche non salvate`}</small>}<button className="button primary" disabled={mutation.isPending || !dirtyKeys.size || shortcutConflicts.size > 0}>Salva impostazioni</button></div>
      </form>}
    </div>}
    {restartConfirmation && <Modal
      title="Riavvio necessario"
      onClose={() => !mutation.isPending && setRestartConfirmation(false)}
      footer={<>
        <button type="button" className="button secondary" disabled={mutation.isPending} onClick={() => setRestartConfirmation(false)}>Annulla</button>
        <button type="button" className="button primary" disabled={mutation.isPending || onlineConfigurationMissing} onClick={() => mutation.mutate({ restart: settings.runtime.restartAvailable, modeChange: true })}>
          {settings.runtime.restartAvailable ? "Salva e riavvia" : "Salva; riavvierò manualmente"}
        </button>
      </>}
    >
      <p><strong>Cambiare questa impostazione richiede il riavvio del server. Riavviare?</strong></p>
      <p>La sessione verrà conservata. Passando alla modalità bloccata, i dispositivi collegati dalla rete perderanno immediatamente l’accesso.</p>
      {onlineConfigurationMissing && <p className="setting-inline-warning" role="alert">Prima di attivare il server online configura <code>REDJANGO_SECRET_KEY</code> e <code>REDJANGO_ALLOWED_HOSTS</code> nell'ambiente del launcher.</p>}
      {!settings.runtime.restartAvailable && <p className="setting-inline-warning">Il server non è stato avviato con <code>start_server.bat</code>: dopo il salvataggio dovrai riavviarlo manualmente.</p>}
    </Modal>}
    {restartingMode && <ServerRestartScreen mode={restartingMode} />}
  </div>;
}

function ServerRestartScreen({ mode }: { mode: string }) {
  useEffect(() => {
    let cancelled = false;
    let sawOffline = false;
    const startedAt = Date.now();
    const poll = async () => {
      try {
        const response = await fetch("/api/auth/session/", { credentials: "same-origin", cache: "no-store" });
        if (response.ok) {
          const body = await response.json();
          if (
            body?.data?.runtime?.activeAccessMode === mode
            && (sawOffline || Date.now() - startedAt > 3000)
          ) {
            window.location.reload();
            return;
          }
        } else {
          sawOffline = true;
        }
      } catch {
        sawOffline = true;
      }
      if (!cancelled) window.setTimeout(poll, 900);
    };
    window.setTimeout(poll, 500);
    return () => { cancelled = true; };
  }, [mode]);
  return <div className="restart-screen" role="status">
    <span className="brand-rune">RD</span>
    <h2>Riavvio di ReDjango…</h2>
    <p>La pagina si riconnetterà automaticamente quando il server sarà pronto.</p>
    {mode === "locked" && <small>Da un altro dispositivo la riconnessione non sarà possibile: la modalità bloccata accetta soltanto questo computer.</small>}
  </div>;
}

function Loading() { return <div className="loading-screen"><span className="brand-rune">ED</span><p>Preparazione della postazione…</p></div>; }

function GameManagerOnly({ children }: { children: ReactNode }) {
  const { settings } = useApp();
  return settings.security.canManageGameData ? children : <Navigate to="/" replace />;
}

function AdminOnly({ children }: { children: ReactNode }) {
  const { settings } = useApp();
  return settings.security.canManageAdminSettings ? children : <Navigate to="/" replace />;
}

export function App() {
  const [toast, setToast] = useState<{ message: string; kind: "success" | "error" | "info" } | null>(null);
  const auth = useQuery({ queryKey: ["auth"], queryFn: () => getData<AuthData>("/api/auth/session/"), retry: false, staleTime: 0 });
  const authenticated = auth.data?.authenticated === true;
  const bootstrap = useQuery({ queryKey: ["bootstrap"], queryFn: () => getData<BootstrapData>("/api/bootstrap/"), enabled: authenticated });
  const personaggi = useQuery({ queryKey: ["personaggi"], queryFn: () => getData<PersonaggiData>("/api/personaggi/"), enabled: authenticated });
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => getData<SettingsData>("/api/settings/"), enabled: authenticated });
  const media = useQuery({ queryKey: ["media"], queryFn: () => getData<MediaLibraryData>("/api/media/"), enabled: authenticated });
  const notify = (message: string, kind: "success" | "error" | "info" = "success") => { setToast({ message, kind }); window.setTimeout(() => setToast(null), 4200); };

  useEffect(() => applyUiPreferences(settings.data), [settings.data]);
  const error = auth.error || bootstrap.error || personaggi.error || settings.error || media.error;
  if (error) return <div className="fatal-error"><h1>ReDjango non può avviarsi</h1><p>{(error as Error).message}</p><button onClick={() => window.location.reload()}>Riprova</button></div>;
  if (!auth.data) return <Loading />;
  if (!auth.data.authenticated) return <LoginPage auth={auth.data} />;
  if (!bootstrap.data || !personaggi.data || !settings.data || !media.data) return <Loading />;

  const context = { bootstrap: bootstrap.data, personaggi: personaggi.data, settings: settings.data, media: media.data.assets, mediaCategories: media.data.categories, notify };
  // The player sits above the router: changing page must never cut the soundtrack.
  return <AppContext.Provider value={context}><AudioPlayerProvider settings={settings.data} notify={notify}><Shell><Routes><Route path="/" element={<Dashboard />} /><Route path="/characters" element={<Navigate to="/" replace />} /><Route path="/character/:characterId" element={<CharacterPage />} /><Route path="/skills" element={<SkillsPage />} /><Route path="/competencies" element={<CompetenciesPage />} /><Route path="/creation" element={<CreationPage />} /><Route path="/combat" element={<CombatPage />} /><Route path="/travel" element={<TravelPage categories={context.mediaCategories} notify={notify} />} /><Route path="/market" element={<MarketPage />} /><Route path="/lore" element={<LorePage />} /><Route path="/media" element={<MediaPage />} /><Route path="/guides" element={<GuidesPage />} /><Route path="/settings" element={<SettingsPage />} /><Route path="/tools" element={<GameManagerOnly><ManagementHub /></GameManagerOnly>} /><Route path="/tools/characters" element={<GameManagerOnly><CharacterManagementPage /></GameManagerOnly>} /><Route path="/tools/items" element={<GameManagerOnly><ItemManagementPage /></GameManagerOnly>} /><Route path="/tools/skills" element={<GameManagerOnly><SkillManagementPage /></GameManagerOnly>} /><Route path="/tools/units" element={<GameManagerOnly><UnitManagementPage /></GameManagerOnly>} /><Route path="/tools/shops" element={<GameManagerOnly><ShopManagementPage /></GameManagerOnly>} /><Route path="/tools/dungeon" element={<GameManagerOnly><DungeonHelperPage /></GameManagerOnly>} /><Route path="/tools/ai" element={<GameManagerOnly><AIManagementPage /></GameManagerOnly>} /><Route path="/tools/players" element={<AdminOnly><PlayerManagementPage /></AdminOnly>} /><Route path="/tools/backups" element={<AdminOnly><BackupManagementPage /></AdminOnly>} /><Route path="/tools/dice" element={<AdminOnly><DiceManagementPage /></AdminOnly>} /><Route path="/tools/themes" element={<AdminOnly><ThemeManagementPage /></AdminOnly>} /><Route path="/tools/variables" element={<AdminOnly><GameVariablesPage /></AdminOnly>} /><Route path="/tools/variables/damage" element={<AdminOnly><DamageRulesPage /></AdminOnly>} /><Route path="*" element={<Navigate to="/" replace />} /></Routes></Shell></AudioPlayerProvider>{toast && <div className={`toast ${toast.kind}`} role="status">{toast.message}</div>}</AppContext.Provider>;
}

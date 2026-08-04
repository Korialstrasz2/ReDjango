import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import { command, getData } from "../../lib/api";

const DEFAULT_HOLD_SECONDS = 0.5;
const DEFAULT_FADE_SECONDS = 1.0;

type RuntimeTheme = {
  slug: string;
  revealHoldSeconds?: number;
  revealFadeSeconds?: number;
};

type SettingsPayload = { theme: RuntimeTheme | null };

type ManagedTheme = RuntimeTheme & {
  id: number;
  name: string;
};

type ManagedThemesPayload = { themes: ManagedTheme[] };

function duration(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 && parsed <= 5 ? parsed : fallback;
}

function applyTiming(theme: RuntimeTheme | null) {
  const root = document.documentElement;
  root.style.setProperty("--theme-reveal-hold", `${duration(theme?.revealHoldSeconds, DEFAULT_HOLD_SECONDS)}s`);
  root.style.setProperty("--theme-reveal-fade", `${duration(theme?.revealFadeSeconds, DEFAULT_FADE_SECONDS)}s`);
}

function activeThemeSlug(): string {
  return document.documentElement.dataset.theme || "";
}

function selectedThemeSlug(): string {
  const active = document.querySelector<HTMLButtonElement>(".theme-list-items button.active");
  return active?.querySelector("small")?.textContent?.trim() || "";
}

function ThemeRevealConfigurator() {
  const [container, setContainer] = useState<Element | null>(null);
  const [themes, setThemes] = useState<ManagedTheme[]>([]);
  const [slug, setSlug] = useState("");
  const [hold, setHold] = useState(DEFAULT_HOLD_SECONDS);
  const [fade, setFade] = useState(DEFAULT_FADE_SECONDS);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const selected = useMemo(() => themes.find((theme) => theme.slug === slug) || null, [themes, slug]);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      if (!window.location.pathname.startsWith("/tools/themes")) {
        setContainer(null);
        return;
      }
      setContainer(document.querySelector(".theme-editor-surfaces"));
      const nextSlug = selectedThemeSlug();
      if (nextSlug) setSlug(nextSlug);
      if (!themes.length) {
        try {
          const data = await getData<ManagedThemesPayload>("/api/v1/management/themes");
          if (!cancelled) setThemes(data.themes || []);
        } catch {
          // The existing page owns the visible error state.
        }
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 300);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [themes.length]);

  useEffect(() => {
    if (!selected) return;
    setHold(duration(selected.revealHoldSeconds, DEFAULT_HOLD_SECONDS));
    setFade(duration(selected.revealFadeSeconds, DEFAULT_FADE_SECONDS));
    setMessage("");
  }, [selected?.id]);

  if (!container || !selected) return null;

  const save = async () => {
    setSaving(true);
    setMessage("");
    try {
      await command("management.themes.save", {
        themeId: selected.id,
        theme: { revealHoldSeconds: hold, revealFadeSeconds: fade },
      }, "settings");
      setThemes((current) => current.map((theme) => theme.id === selected.id
        ? { ...theme, revealHoldSeconds: hold, revealFadeSeconds: fade }
        : theme));
      if (activeThemeSlug() === selected.slug) applyTiming({ ...selected, revealHoldSeconds: hold, revealFadeSeconds: fade });
      setMessage("Tempi di entrata salvati.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Salvataggio non riuscito.");
    } finally {
      setSaving(false);
    }
  };

  return createPortal(
    <div className="theme-reveal-configurator">
      <h3>Entrata dello sfondo</h3>
      <p className="muted-copy">Lo sfondo appare sopra l'interfaccia al 75%, poi si dissolve mentre pannelli e velo raggiungono le opacità del tema.</p>
      <div className="theme-reveal-configurator-grid">
        <label>
          <span>Immagine in primo piano</span>
          <input type="range" min={0} max={5} step={0.1} value={hold} onChange={(event) => setHold(Number(event.target.value))} />
          <output>{hold.toFixed(1)} s</output>
        </label>
        <label>
          <span>Dissolvenza e assestamento</span>
          <input type="range" min={0} max={5} step={0.1} value={fade} onChange={(event) => setFade(Number(event.target.value))} />
          <output>{fade.toFixed(1)} s</output>
        </label>
      </div>
      <div className="theme-reveal-configurator-actions">
        <small>{message}</small>
        <button type="button" className="button secondary" disabled={saving} onClick={() => {
          applyTiming({ ...selected, revealHoldSeconds: hold, revealFadeSeconds: fade });
          document.querySelector<HTMLElement>(".theme-preview-replay")?.click();
        }}>Anteprima</button>
        <button type="button" className="button primary" disabled={saving} onClick={save}>Salva tempi</button>
      </div>
    </div>,
    container,
  );
}

export function ThemeRevealRuntime() {
  useEffect(() => {
    let cancelled = false;
    let loadedSlug = "";
    const loadTiming = async () => {
      try {
        const settings = await getData<SettingsPayload>("/api/settings/");
        if (!cancelled) {
          applyTiming(settings.theme);
          loadedSlug = settings.theme?.slug || "";
        }
      } catch {
        if (!cancelled) applyTiming(null);
      }
    };
    void loadTiming();
    const observer = new MutationObserver(() => {
      const slug = activeThemeSlug();
      if (slug && slug !== loadedSlug) void loadTiming();
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => { cancelled = true; observer.disconnect(); };
  }, []);

  useEffect(() => {
    const refreshPreviewImage = () => {
      document.querySelectorAll<HTMLElement>(".theme-preview.theme-reveal-surface").forEach((preview) => {
        const layer = preview.querySelector<HTMLElement>(".theme-preview-background");
        preview.style.setProperty("--theme-showcase-image", layer?.style.backgroundImage || "none");
        preview.style.setProperty("--theme-showcase-position", layer?.style.backgroundPosition || "center center");
        preview.style.setProperty("--theme-showcase-filter", layer?.style.filter || "none");
      });
    };
    refreshPreviewImage();
    const observer = new MutationObserver(refreshPreviewImage);
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["style", "class"] });
    return () => observer.disconnect();
  }, []);

  return <ThemeRevealConfigurator />;
}

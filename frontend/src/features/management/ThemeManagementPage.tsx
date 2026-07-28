import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ImagePickerModal } from "../../components/ImagePickerModal";
import { Modal } from "../../components/Modal";
import { command, getData } from "../../lib/api";
import type { ManagedTheme, ManagedThemesData } from "../../lib/types";
import { resolveThemeColors, useApp } from "../../App";

type Draft = {
  name: string;
  description: string;
  order: number;
  isActive: boolean;
  colors: Record<string, string>;
  overlayOpacity: number;
  panelOpacity: number;
  backgroundPosition: string;
  backgroundBlur: number;
  backgrounds: Record<string, number | null>;
};

function draftFromTheme(theme: ManagedTheme): Draft {
  return {
    name: theme.name,
    description: theme.description,
    order: theme.order,
    isActive: theme.isActive,
    colors: { ...theme.colors },
    overlayOpacity: theme.overlayOpacity,
    panelOpacity: theme.panelOpacity,
    backgroundPosition: theme.backgroundPosition,
    backgroundBlur: theme.backgroundBlur,
    backgrounds: Object.fromEntries(Object.entries(theme.backgrounds).map(([field, image]) => [field, image.id])),
  };
}

function sameDraft(left: Draft, right: Draft): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

// Anteprima autonoma: ricalcola gli stessi token CSS applicati dall'app, così il
// riquadro mostra il tema com'è davvero, riserve globali comprese.
function ThemePreview({ draft, fallbacks, backgroundUrl }: { draft: Draft; fallbacks: Record<string, string>; backgroundUrl: string }) {
  const colors = resolveThemeColors(
    {
      slug: "preview",
      name: draft.name,
      description: "",
      colors: {
        background: draft.colors.background_color,
        panel: draft.colors.panel_color,
        panelStrong: draft.colors.panel_strong_color,
        text: draft.colors.text_color,
        mutedText: draft.colors.muted_text_color,
        line: draft.colors.line_color,
        accent: draft.colors.accent_color,
        accentStrong: draft.colors.accent_strong_color,
        gold: draft.colors.gold_color,
        sidebar: draft.colors.sidebar_color,
        health: draft.colors.health_color,
        mana: draft.colors.mana_color,
        energy: draft.colors.energy_color,
        power: draft.colors.power_color,
        validSlot: draft.colors.valid_slot_color,
        invalidSlot: draft.colors.invalid_slot_color,
      },
      overlayOpacity: draft.overlayOpacity,
      panelOpacity: draft.panelOpacity,
      backgroundPosition: draft.backgroundPosition,
      backgroundBlur: draft.backgroundBlur,
      backgrounds: {},
    },
    {
      "appearance.accent_color": fallbacks["appearance.accent_color"],
      "appearance.gold_color": fallbacks["appearance.gold_color"],
      "appearance.sidebar_color": fallbacks["appearance.sidebar_color"],
    },
  );
  return <div className="theme-preview" style={{ background: colors.background }}>
    {backgroundUrl && <div className="theme-preview-background" style={{ backgroundImage: `url(${backgroundUrl})`, backgroundPosition: draft.backgroundPosition, filter: draft.backgroundBlur ? `blur(${draft.backgroundBlur}px)` : undefined, opacity: 1 - draft.overlayOpacity }} />}
    <div className="theme-preview-shell">
      <div className="theme-preview-nav" style={{ background: colors.sidebar }}>
        <strong style={{ color: colors.gold }}>ReDjango</strong>
        <span style={{ color: colors.line }}>Sala principale</span>
        <span style={{ color: colors.line }}>Personaggi</span>
        <span style={{ color: colors.line }}>Combattimento</span>
      </div>
      <div className="theme-preview-body">
        <div className="theme-preview-panel" style={{ background: colors.panelStrong, borderColor: colors.line, opacity: draft.panelOpacity }}>
          <strong style={{ color: colors.text }}>Titolo del pannello</strong>
          <small style={{ color: colors.mutedText }}>Testo secondario di esempio</small>
          <div className="theme-preview-buttons">
            <em style={{ background: colors.accent, color: "#fff" }}>Azione</em>
            <em style={{ background: "transparent", borderColor: colors.gold, color: colors.gold }}>Secondaria</em>
          </div>
        </div>
        <div className="theme-preview-resources">
          {[["PF", colors.health], ["Mana", colors.mana], ["Energia", colors.energy], ["Potere", colors.power]].map(([label, color]) => (
            <span key={label} style={{ background: color, color: "#fff" }}>{label}</span>
          ))}
        </div>
      </div>
    </div>
  </div>;
}

export function ThemeManagementPage() {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const themes = useQuery({ queryKey: ["managed-themes"], queryFn: () => getData<ManagedThemesData>("/api/v1/management/themes") });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [picker, setPicker] = useState<{ field: string; label: string } | null>(null);
  const [creating, setCreating] = useState<{ name: string; duplicateOfId: number | null } | null>(null);
  const [confirmArchive, setConfirmArchive] = useState<ManagedTheme | null>(null);

  const data = themes.data;
  const selected = useMemo(() => data?.themes.find((theme) => theme.id === selectedId) || data?.themes[0] || null, [data, selectedId]);
  const baseline = useMemo(() => (selected ? draftFromTheme(selected) : null), [selected]);

  useEffect(() => {
    if (selected && (selectedId !== selected.id || draft === null)) {
      setSelectedId(selected.id);
      setDraft(draftFromTheme(selected));
    }
  }, [selected, selectedId, draft]);

  const applyResult = async (result: { data: { management: { themes?: ManagedTheme[]; theme?: ManagedTheme } } }, message: string) => {
    queryClient.setQueryData<ManagedThemesData>(["managed-themes"], (current) => current && result.data.management.themes ? { ...current, ...result.data.management } : current);
    // I temi alimentano l'interfaccia di tutti: ricarica anche le impostazioni.
    await queryClient.invalidateQueries({ queryKey: ["settings"] });
    await queryClient.invalidateQueries({ queryKey: ["managed-themes"] });
    notify(message);
  };

  const saveMutation = useMutation({
    mutationFn: () => command<{ management: { themes: ManagedTheme[]; theme: ManagedTheme } }>("management.themes.save", { themeId: selected!.id, theme: draft as unknown as Record<string, unknown> }, "settings"),
    onSuccess: (result) => applyResult(result, "Tema salvato."),
    onError: (error: Error) => notify(error.message, "error"),
  });
  const createMutation = useMutation({
    mutationFn: (payload: { name: string; duplicateOfId: number | null }) => command<{ management: { themes: ManagedTheme[]; theme: ManagedTheme } }>("management.themes.create", { theme: payload }, "settings"),
    onSuccess: async (result) => {
      const created = result.data.management.theme;
      await applyResult(result, "Tema creato.");
      setCreating(null);
      if (created) { setSelectedId(created.id); setDraft(null); }
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const defaultMutation = useMutation({
    mutationFn: (themeId: number) => command<{ management: { themes: ManagedTheme[] } }>("management.themes.setDefault", { themeId }, "settings"),
    onSuccess: (result) => applyResult(result, "Tema predefinito aggiornato."),
    onError: (error: Error) => notify(error.message, "error"),
  });
  const archiveMutation = useMutation({
    mutationFn: (themeId: number) => command<{ management: { themes: ManagedTheme[] } }>("management.themes.archive", { themeId }, "settings"),
    onSuccess: async (result) => {
      await applyResult(result, "Tema archiviato.");
      setConfirmArchive(null);
      setSelectedId(null);
      setDraft(null);
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  if (themes.isLoading) return <div className="page management-page"><header className="page-header"><div><p className="eyebrow">Strumenti riservati</p><h1>Gestione Temi</h1></div></header><p className="muted-copy">Caricamento dei temi…</p></div>;
  if (themes.error) return <div className="page management-page"><header className="page-header"><div><p className="eyebrow">Strumenti riservati</p><h1>Gestione Temi</h1></div></header><p className="muted-copy">{(themes.error as Error).message}</p></div>;
  if (!data || !selected || !draft || !baseline) return null;

  const dirty = !sameDraft(draft, baseline);
  const update = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch });
  const previewBackground = selected.backgrounds.dashboard_background?.url || "";

  return <div className="page management-page theme-management-page">
    <header className="page-header">
      <div><p className="eyebrow">Strumenti riservati</p><h1>Gestione Temi</h1></div>
      <div className="button-row">
        <Link className="button secondary" to="/tools">Tutti gli strumenti</Link>
        <button type="button" className="button secondary" onClick={() => setCreating({ name: "", duplicateOfId: selected.id })}>Duplica</button>
        <button type="button" className="button primary" onClick={() => setCreating({ name: "", duplicateOfId: null })}>Nuovo tema</button>
      </div>
    </header>

    <div className="theme-management-layout">
      <aside className="panel theme-list" data-component-type="panel" data-theme="default">
        <h2>Temi</h2>
        <p className="muted-copy">{data.activeCount} attivi su {data.themes.length}. Il tema predefinito è quello proposto a chi non ne ha ancora scelto uno.</p>
        <div className="theme-list-items">
          {data.themes.map((theme) => <button
            key={theme.id}
            type="button"
            className={theme.id === selected.id ? "active" : ""}
            onClick={() => { setSelectedId(theme.id); setDraft(draftFromTheme(theme)); }}
          >
            <span className="theme-list-swatches" aria-hidden="true">
              {[theme.colors.background_color, theme.colors.panel_color, theme.colors.accent_color || data.fallbacks["appearance.accent_color"], theme.colors.gold_color || data.fallbacks["appearance.gold_color"]].map((color, index) => <i key={index} style={{ background: color }} />)}
            </span>
            <span><strong>{theme.name}</strong><small>{theme.slug}</small></span>
            <span className="theme-list-flags">{theme.isDefault && <b title="Predefinito">★</b>}{!theme.isActive && <em title="Non attivo">off</em>}</span>
          </button>)}
        </div>
      </aside>

      <section className="theme-editor">
        <div className="panel theme-editor-identity" data-component-type="panel" data-theme="gold">
          <div className="theme-editor-identity-fields">
            <label>Nome<input value={draft.name} maxLength={120} onChange={(event) => update({ name: event.target.value })} /></label>
            <label>Ordine<input type="number" min={0} value={draft.order} onChange={(event) => update({ order: Number(event.target.value) })} /></label>
            <label className="theme-editor-toggle"><input type="checkbox" checked={draft.isActive} onChange={(event) => update({ isActive: event.target.checked })} />Attivo nelle Impostazioni</label>
          </div>
          <label>Descrizione<textarea rows={2} value={draft.description} onChange={(event) => update({ description: event.target.value })} /></label>
          <div className="theme-editor-identity-actions">
            <span className="muted-copy">{selected.isDefault ? "Questo è il tema predefinito." : "Identificatore: " + selected.slug}</span>
            {!selected.isDefault && <button type="button" className="button secondary" disabled={defaultMutation.isPending || !selected.isActive} onClick={() => defaultMutation.mutate(selected.id)}>Rendi predefinito</button>}
            {!selected.isSeeded && !selected.isDefault && <button type="button" className="button danger" onClick={() => setConfirmArchive(selected)}>Archivia</button>}
          </div>
        </div>

        <ThemePreview draft={draft} fallbacks={data.fallbacks} backgroundUrl={previewBackground} />

        <section className="panel theme-editor-colors" data-component-type="panel" data-theme="default">
          <h2>Colori</h2>
          <p className="muted-copy">Principale, dorato e menu laterale possono restare vuoti: in quel caso valgono i colori globali di riserva delle Impostazioni.</p>
          <div className="theme-color-grid">
            {data.colorFields.map((field) => {
              const value = draft.colors[field.field] || "";
              const fallback = field.fallbackSetting ? data.fallbacks[field.fallbackSetting] || "" : "";
              return <div className="theme-color-field" key={field.field}>
                <label>
                  <span>{field.label}</span>
                  <input type="color" value={value || fallback || "#000000"} onChange={(event) => update({ colors: { ...draft.colors, [field.field]: event.target.value } })} />
                </label>
                {field.fallbackSetting && (value
                  ? <button type="button" className="theme-color-clear" onClick={() => update({ colors: { ...draft.colors, [field.field]: "" } })}>Usa la riserva globale</button>
                  : <small className="theme-color-inherited">Ereditato: {fallback || "non configurato"}</small>)}
              </div>;
            })}
          </div>
        </section>

        <section className="panel theme-editor-surfaces" data-component-type="panel" data-theme="default">
          <h2>Trasparenze e disposizione</h2>
          <div className="theme-surface-grid">
            <label className="theme-surface-slider"><span>Velo sugli sfondi</span><input type="range" min={0} max={1} step={0.02} value={draft.overlayOpacity} onChange={(event) => update({ overlayOpacity: Number(event.target.value) })} /><output>{Math.round(draft.overlayOpacity * 100)}%</output></label>
            <label className="theme-surface-slider"><span>Opacità dei pannelli</span><input type="range" min={0} max={1} step={0.02} value={draft.panelOpacity} onChange={(event) => update({ panelOpacity: Number(event.target.value) })} /><output>{Math.round(draft.panelOpacity * 100)}%</output></label>
            <label className="theme-surface-slider"><span>Sfocatura degli sfondi</span><input type="range" min={0} max={20} step={1} value={draft.backgroundBlur} onChange={(event) => update({ backgroundBlur: Number(event.target.value) })} /><output>{draft.backgroundBlur}px</output></label>
            <label><span>Posizione degli sfondi</span><input value={draft.backgroundPosition} maxLength={80} placeholder="center center" onChange={(event) => update({ backgroundPosition: event.target.value })} /></label>
          </div>
        </section>

        <section className="panel theme-editor-backgrounds" data-component-type="panel" data-theme="default">
          <h2>Sfondi delle schermate</h2>
          <p className="muted-copy">Ogni schermata può avere il proprio sfondo, oppure riusare la stessa immagine. Le immagini arrivano dall'Archivio.</p>
          <div className="theme-background-grid">
            {data.backgroundFields.map((field) => {
              const imageId = draft.backgrounds[field.field];
              const current = selected.backgrounds[field.field];
              const preview = imageId && current?.id === imageId ? (current.thumbnailUrl || current.url) : "";
              return <div className="theme-background-field" key={field.field}>
                <button type="button" onClick={() => setPicker({ field: field.field, label: field.label })}>
                  {preview ? <img src={preview} alt="" /> : <span className="theme-background-empty">{imageId ? "Immagine scelta" : "Nessuno sfondo"}</span>}
                  <strong>{field.label}</strong>
                </button>
                {imageId && <button type="button" className="theme-background-clear" onClick={() => update({ backgrounds: { ...draft.backgrounds, [field.field]: null } })}>Rimuovi</button>}
              </div>;
            })}
          </div>
        </section>

        <div className="sticky-actions">
          {dirty && <small>Modifiche non salvate</small>}
          <button type="button" className="button secondary" disabled={!dirty} onClick={() => setDraft(draftFromTheme(selected))}>Annulla</button>
          <button type="button" className="button primary" disabled={!dirty || saveMutation.isPending} onClick={() => saveMutation.mutate()}>Salva tema</button>
        </div>
      </section>
    </div>

    {picker && <ImagePickerModal
      selectedId={draft.backgrounds[picker.field]}
      usageType="theme_background"
      defaultGroup="Sfondi dei temi"
      defaultTitle={`${draft.name} · ${picker.label}`}
      onSelect={(asset) => update({ backgrounds: { ...draft.backgrounds, [picker.field]: asset?.id || null } })}
      onClose={() => setPicker(null)}
    />}

    {creating && <Modal
      title={creating.duplicateOfId ? "Duplica tema" : "Nuovo tema"}
      onClose={() => setCreating(null)}
      footer={<><button type="button" className="button secondary" onClick={() => setCreating(null)}>Annulla</button><button type="button" className="button primary" disabled={!creating.name.trim() || createMutation.isPending} onClick={() => createMutation.mutate(creating)}>Crea</button></>}
    >
      <div className="stacked-form">
        <label>Nome del tema<input autoFocus value={creating.name} maxLength={120} onChange={(event) => setCreating({ ...creating, name: event.target.value })} /></label>
        <p className="muted-copy">{creating.duplicateOfId ? `Colori, sfondi e trasparenze saranno copiati da «${selected.name}».` : "Il nuovo tema parte dai colori predefiniti e non è attivo finché non lo salvi."}</p>
      </div>
    </Modal>}

    {confirmArchive && <Modal
      title="Archivia tema"
      onClose={() => !archiveMutation.isPending && setConfirmArchive(null)}
      footer={<><button type="button" className="button secondary" disabled={archiveMutation.isPending} onClick={() => setConfirmArchive(null)}>Annulla</button><button type="button" className="button danger" disabled={archiveMutation.isPending} onClick={() => archiveMutation.mutate(confirmArchive.id)}>Sì, archivia</button></>}
    >
      <p>Il tema «{confirmArchive.name}» sparirà dalle Impostazioni. Chi lo sta usando tornerà al tema predefinito.</p>
    </Modal>}
  </div>;
}

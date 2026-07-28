import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useApp } from "../App";
import { uploadMedia } from "../lib/api";
import type { MediaAsset } from "../lib/types";
import { Modal } from "./Modal";

type Props = {
  selectedId: number | null;
  usageType: string;
  defaultGroup: string;
  defaultTitle: string;
  onSelect: (asset: MediaAsset | null) => void;
  onClose: () => void;
};

export function ImagePickerModal({ selectedId, usageType, defaultGroup, defaultTitle, onSelect, onClose }: Props) {
  const { media, mediaCategories, notify } = useApp();
  const queryClient = useQueryClient();
  const automaticCategory = mediaCategories.find((category) => category.usageTypes.includes(usageType)) || mediaCategories[0];
  const [draftId, setDraftId] = useState<number | null>(selectedId);
  const [query, setQuery] = useState("");
  const [categoryId, setCategoryId] = useState(automaticCategory ? String(automaticCategory.id) : "");
  const [group, setGroup] = useState("");
  const [actionAssetId, setActionAssetId] = useState<number | null>(null);
  const [previewAsset, setPreviewAsset] = useState<MediaAsset | null>(null);
  const groups = useMemo(() => [...new Set(media.filter((asset) => !categoryId || asset.categoryId === Number(categoryId)).map((asset) => asset.group))].sort((left, right) => left.localeCompare(right, "it")), [categoryId, media]);
  const normalized = query.trim().toLocaleLowerCase("it");
  const visible = media.filter((asset) => {
    const matches = !normalized || `${asset.title} ${asset.category} ${asset.group} ${asset.notes}`.toLocaleLowerCase("it").includes(normalized);
    return matches && (!categoryId || asset.categoryId === Number(categoryId)) && (!group || asset.group === group);
  });
  const selected = media.find((asset) => asset.id === draftId) || null;
  useEffect(() => {
    if (actionAssetId === null) return;
    const closeMenu = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Element && target.closest(`[data-image-picker-asset="${actionAssetId}"]`)) return;
      setActionAssetId(null);
    };
    document.addEventListener("pointerdown", closeMenu, true);
    return () => document.removeEventListener("pointerdown", closeMenu, true);
  }, [actionAssetId]);
  useEffect(() => {
    if (!previewAsset && actionAssetId === null) return;
    const closeTopLayer = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      if (previewAsset) setPreviewAsset(null);
      else setActionAssetId(null);
    };
    window.addEventListener("keydown", closeTopLayer, true);
    return () => window.removeEventListener("keydown", closeTopLayer, true);
  }, [actionAssetId, previewAsset]);
  const uploadMutation = useMutation({
    mutationFn: ({ file, title, selectedCategoryId, selectedGroup }: { file: File; title: string; selectedCategoryId: number; selectedGroup: string }) => uploadMedia(file, title, "Caricata dal selettore immagini degli oggetti.", usageType, selectedCategoryId, selectedGroup),
    onSuccess: async (response) => {
      setDraftId(response.data.asset.id);
      await queryClient.invalidateQueries({ queryKey: ["media"] });
      notify("Immagine caricata e selezionata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const upload = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get("file");
    if (!(file instanceof File) || !file.size) return;
    uploadMutation.mutate({
      file,
      title: String(form.get("title") || defaultTitle || file.name),
      selectedCategoryId: Number(form.get("categoryId")),
      selectedGroup: String(form.get("group") || defaultGroup),
    });
  };

  return <Modal
    title="Scegli un'immagine"
    onClose={onClose}
    wide
    footer={<><button className="button secondary" type="button" onClick={onClose}>Annulla</button><button className="button secondary" type="button" onClick={() => { onSelect(null); onClose(); }}>Nessuna immagine</button><button className="button primary" type="button" disabled={!selected} onClick={() => { onSelect(selected); onClose(); }}>Usa immagine selezionata</button></>}
  >
    <div className="image-picker-layout">
      <aside className="image-picker-upload">
        <p className="eyebrow">Caricamento contestuale</p><h3>Nuova immagine</h3>
        <form className="stacked-form" onSubmit={upload}>
          <label>Nome<input name="title" defaultValue={defaultTitle} required /></label>
          <label>Categoria<select name="categoryId" defaultValue={automaticCategory?.id || ""} required><option value="" disabled>Scegli categoria</option>{mediaCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
          <label>Gruppo<input name="group" defaultValue={defaultGroup} required /></label>
          <label>File<input name="file" type="file" accept="image/*" required /></label>
          <button className="button secondary" disabled={uploadMutation.isPending || !mediaCategories.length}>Carica e seleziona</button>
        </form>
        <p className="image-picker-hint">Categoria, gruppo e nome sono già preparati per questo contesto. Puoi correggerli prima del caricamento.</p>
      </aside>
      <section className="image-picker-browser">
        <div className="image-picker-filters"><label>Cerca<input type="search" value={query} onChange={(event) => { setQuery(event.target.value); setActionAssetId(null); }} placeholder="Nome o gruppo…" /></label><label>Categoria<select value={categoryId} onChange={(event) => { setCategoryId(event.target.value); setGroup(""); setActionAssetId(null); }}><option value="">Tutte</option>{mediaCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label>Gruppo<select value={group} onChange={(event) => { setGroup(event.target.value); setActionAssetId(null); }}><option value="">Tutti</option>{groups.map((entry) => <option key={entry}>{entry}</option>)}</select></label></div>
        <div className="image-picker-summary"><span>{visible.length} immagini</span>{selected && <strong>Selezionata: {selected.title}</strong>}</div>
        <div className="image-picker-grid" role="list" aria-label="Immagini disponibili">{visible.map((asset) => {
          const menuOpen = actionAssetId === asset.id;
          const isSelected = draftId === asset.id;
          return <article
            className="image-picker-card"
            data-component-type="card"
            data-theme="media"
            data-image-picker-asset={asset.id}
            data-state={isSelected ? "selected" : menuOpen ? "open" : "idle"}
            key={asset.id}
            role="listitem"
          >
            <button
              className="image-picker-card-trigger"
              type="button"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label={`Azioni per ${asset.title}`}
              onClick={() => setActionAssetId((current) => current === asset.id ? null : asset.id)}
            >
              <img src={asset.thumbnailUrl || asset.url} alt="" />
              <span><strong>{asset.title}</strong><small>{asset.category} · {asset.group}</small></span>
            </button>
            {isSelected && <span className="image-picker-selected-badge">Selezionata</span>}
            {menuOpen && <div className="image-picker-context-menu" data-component-type="context-menu" data-theme="media" role="menu" aria-label={`Azioni per ${asset.title}`}>
              <button className="button secondary" type="button" role="menuitem" onClick={() => { setPreviewAsset(asset); setActionAssetId(null); }}>Apri</button>
              <button className="button primary" type="button" role="menuitem" onClick={() => { setDraftId(asset.id); setActionAssetId(null); }}>Seleziona</button>
            </div>}
          </article>;
        })}</div>
        {!visible.length && <div className="management-empty-state"><strong>Nessuna immagine trovata</strong><p>Cambia i filtri oppure caricane una nuova.</p></div>}
      </section>
      {previewAsset && <section className="image-picker-preview" data-component-type="inspector" data-theme="media" role="dialog" aria-modal="true" aria-label={`Anteprima ${previewAsset.title}`}>
        <header><div><p className="eyebrow">Immagine originale</p><h3>{previewAsset.title}</h3></div><button className="icon-button" type="button" aria-label="Chiudi anteprima" onClick={() => setPreviewAsset(null)}>×</button></header>
        <img src={previewAsset.url} alt={previewAsset.title} />
        <footer><span>{previewAsset.category || "Senza categoria"} · {previewAsset.group}</span><button className="button secondary" type="button" onClick={() => setPreviewAsset(null)}>Chiudi</button></footer>
      </section>}
    </div>
  </Modal>;
}
